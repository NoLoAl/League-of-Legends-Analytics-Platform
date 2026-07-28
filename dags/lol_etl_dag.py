# dags/lol_etl_dag.py
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.exceptions import AirflowSkipException
from airflow.utils.dates import days_ago
from datetime import timedelta
import logging
import os
import sys
import time
import json

# Добавляем путь к модулям проекта (если они не в PYTHONPATH)
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import config
from extract import (
    fetch_players,
    fetch_match_ids_for_player,
    fetch_match_details,
    fetch_champions,
    fetch_items,
    load_checkpoint,
    save_checkpoint,
    setup_logging
)
from transform import enrich_players, process_match_data
from load import save_dataframe, append_dataframe
import pandas as pd

# Настройка логирования (будет использоваться внутри функций)
log_level = getattr(config, "LOG_LEVEL", "INFO")
setup_logging(log_level)

default_args = {
    'owner': 'data_team',
    'depends_on_past': False,
    'start_date': days_ago(1),
    'retries': 2,
    'retry_delay': timedelta(minutes=5),
    'email_on_failure': False,
    'email_on_retry': False,
}

dag = DAG(
    'lol_etl_pipeline',
    default_args=default_args,
    description='ETL для топ-игроков League of Legends',
    schedule_interval='@daily',
    catchup=False,
    tags=['lol', 'etl'],
)

def task_get_players(**context):
    """Загружает и обогащает данные игроков, сохраняет в parquet."""
    logging.info("Начало get_players")
    players_raw = fetch_players()
    players = enrich_players(players_raw)

    players = players[players["wins"] > config.MIN_WINS].copy()
    logging.info(f"Сохранено {len(players)} игроков")
    save_dataframe(players, 'players')

    return f"Загружено {len(players)} игроков"

def task_get_match_ids(**context):
    """Получает ID матчей для каждого игрока, обновляет чекпоинт."""
    logging.info("Начало get_match_ids")
    checkpoint = load_checkpoint()
    players_done = checkpoint.get('players_done', [])
    all_match_ids = checkpoint.get('match_ids', [])

    # Загружаем список игроков из файла (чтобы не зависеть от XCom)
    players_df = pd.read_parquet(os.path.join(config.OUTPUT_DIR, 'players.parquet'))
    puuids = players_df['puu_id'].tolist()
    regions = players_df['region'].tolist()
    player_region_map = dict(zip(puuids, regions))

    new_ids = []
    for idx, puuid in enumerate(puuids):
        if puuid in players_done:
            continue
        region = player_region_map[puuid]
        ids = fetch_match_ids_for_player(puuid, region)
        new_ids.extend(ids)
        players_done.append(puuid)
        # Обновляем чекпоинт после каждого игрока
        checkpoint['players_done'] = players_done
        checkpoint['match_ids'] = list(set(all_match_ids + new_ids))
        save_checkpoint(checkpoint)
        time.sleep(config.DELAY)
        if (idx + 1) % 10 == 0:
            logging.info(f"Обработано {idx+1} игроков, собрано {len(all_match_ids) + len(new_ids)} ID")

    if new_ids:
        all_match_ids = list(set(all_match_ids + new_ids))
        checkpoint['match_ids'] = all_match_ids
        save_checkpoint(checkpoint)

    # Сохраняем список всех ID в файл для следующей задачи
    with open(os.path.join(config.OUTPUT_DIR, 'match_ids.json'), 'w') as f:
        json.dump(all_match_ids, f)

    logging.info(f"Всего уникальных ID матчей: {len(all_match_ids)}")
    return f"Собрано {len(all_match_ids)} ID"

def task_get_match_details(**context):
    """Загружает детали матчей, которые ещё не обработаны."""
    logging.info("Начало get_match_details")
    checkpoint = load_checkpoint()
    processed_match_ids = checkpoint.get('processed_match_ids', [])

    # Загружаем полный список ID
    with open(os.path.join(config.OUTPUT_DIR, 'match_ids.json'), 'r') as f:
        all_match_ids = json.load(f)

    to_process = [mid for mid in all_match_ids if mid not in processed_match_ids]
    logging.info(f"Осталось обработать матчей: {len(to_process)}")

    rows_buffer = []
    for match_id in to_process:
        # Определяем регион по префиксу
        if match_id.startswith('NA1_'):
            region = 'NA1'
        else:
            region = 'EUW1'   # упрощённо

        match_json = fetch_match_details(match_id, region)
        if match_json is not None:
            rows = process_match_data(match_json, match_id)
            rows_buffer.extend(rows)

        # Отмечаем матч как обработанный
        processed_match_ids.append(match_id)
        checkpoint['processed_match_ids'] = processed_match_ids
        save_checkpoint(checkpoint)

        # Периодически сохраняем накопленные строки
        if len(rows_buffer) >= config.BATCH_SIZE:
            temp_df = pd.DataFrame(rows_buffer)
            append_dataframe(temp_df, 'matches.csv')
            rows_buffer.clear()
        time.sleep(config.DELAY)

    # Сохраняем остаток
    if rows_buffer:
        temp_df = pd.DataFrame(rows_buffer)
        append_dataframe(temp_df, 'matches.csv')
        rows_buffer.clear()

    logging.info(f"Обработано матчей: {len(processed_match_ids)}")
    return f"Загружено деталей для {len(processed_match_ids)} матчей"

def task_finalize(**context):
    """Финальное сохранение (конвертация в нужный формат, справочники)."""
    logging.info("Финальная стадия")
    # Если нужен не CSV, конвертируем matches.csv в parquet
    if config.SAVE_FORMAT != 'csv':
        csv_path = os.path.join(config.OUTPUT_DIR, 'matches.csv')
        if os.path.exists(csv_path):
            matches_df = pd.read_csv(csv_path)
            save_dataframe(matches_df, 'matches')
            logging.info(f"Конвертировано в {config.SAVE_FORMAT}")
            # опционально удаляем CSV
            # os.remove(csv_path)

    # Загружаем справочники
    champions = fetch_champions()
    items = fetch_items()
    save_dataframe(champions, 'champions')
    save_dataframe(items, 'items')
    logging.info("Справочники сохранены")
    return "Финализация завершена"

# Определяем задачи
t1 = PythonOperator(
    task_id='get_players',
    python_callable=task_get_players,
    dag=dag,
)

t2 = PythonOperator(
    task_id='get_match_ids',
    python_callable=task_get_match_ids,
    dag=dag,
)

t3 = PythonOperator(
    task_id='get_match_details',
    python_callable=task_get_match_details,
    dag=dag,
)

t4 = PythonOperator(
    task_id='finalize',
    python_callable=task_finalize,
    dag=dag,
)

# Задаём порядок выполнения
t1 >> t2 >> t3 >> t4
