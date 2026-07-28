# main.py
import time
import pandas as pd
from tqdm import tqdm
import logging
import os

from config import config
from extract import (
    fetch_players,
    fetch_match_ids_for_player,
    fetch_match_details,
    fetch_champions,
    fetch_items,
    setup_logging,
    load_checkpoint,
    save_checkpoint
)
from transform import enrich_players, process_match_data
from load import save_dataframe, append_dataframe

def main():
    log_level = getattr(config, "LOG_LEVEL", "INFO")
    setup_logging(log_level)

    start_full = time.time()
    logging.info("=" * 50)
    logging.info("Запуск ETL-пайплайна для League of Legends")
    logging.info("=" * 50)

    # Загружаем чекпоинт
    checkpoint = load_checkpoint()
    players_done = checkpoint.get("players_done", [])
    all_match_ids = checkpoint.get("match_ids", [])
    processed_match_ids = checkpoint.get("processed_match_ids", [])

    # Шаг 1: Игроки
    start = time.time()
    logging.info("\n1. Загрузка данных о топ-игроках...")
    players_raw = fetch_players()
    players = enrich_players(players_raw)

    # Фильтруем по количеству побед
    players = players[players["wins"] > config.MIN_WINS].copy()
    elapsed = time.time() - start
    logging.info(f"Найдено {len(players)} игроков с > {config.MIN_WINS} побед.")
    logging.info(f"Время: {elapsed:.2f} сек.")
    save_dataframe(players, "players")

    # Шаг 2: ID матчей
    start = time.time()
    logging.info("\n2. Сбор ID матчей для каждого игрока...")
    new_match_ids = []
    for idx, row in players.iterrows():
        puuid = row["puu_id"]
        region = row["region"]
        if puuid in players_done:
            continue
        ids = fetch_match_ids_for_player(puuid, region)
        new_match_ids.extend(ids)
        players_done.append(puuid)

        # Обновляем чекпоинт после каждого игрока
        checkpoint["players_done"] = players_done
        checkpoint["match_ids"] = list(set(all_match_ids + new_match_ids))
        save_checkpoint(checkpoint)
        time.sleep(config.DELAY)
        # Прогресс
        if (idx + 1) % 10 == 0:
            logging.info(f"Обработано {idx+1} игроков, собрано {len(all_match_ids) + len(new_match_ids)} ID.")

    # Добавляем новые ID в общий список и сохраняем
    if new_match_ids:
        all_match_ids = list(set(all_match_ids + new_match_ids))
        checkpoint["match_ids"] = all_match_ids
        save_checkpoint(checkpoint)

    elapsed = time.time() - start
    logging.info(f"Уникальных ID матчей: {len(all_match_ids)}")
    logging.info(f"Время: {elapsed:.2f} сек.")

    # Шаг 3: Детали матчей
    start = time.time()
    logging.info("\n3. Загрузка детальной информации по матчам...")
    # Определяем, какие матчи ещё не обработаны
    match_ids_to_process = [mid for mid in all_match_ids if mid not in processed_match_ids]

    logging.info(f"Осталось обработать матчей: {len(match_ids_to_process)}")   
    
    rows_buffer = []
    # Если уже есть сохранённый CSV, загружаем его для финального объединения позже
    csv_path = os.path.join(config.OUTPUT_DIR, "matches.csv")

    for match_id in tqdm(match_ids_to_process, desc="Загрузка матчей"):
        # Определяем регион по префиксу
        if match_id.startswith("NA1_"):
            region = "NA1"
        else:  # EUW1_ или RU_
            region = "EUW1"   # для простоты считаем, что все остальные — EUW1

        match_json = fetch_match_details(match_id, region)
        if match_json is not None:
            rows = process_match_data(match_json, match_id)
            rows_buffer.extend(rows)
        # Обновляем чекпоинт (отмечаем матч как обработанный)
        processed_match_ids.append(match_id)
        checkpoint["processed_match_ids"] = processed_match_ids
        save_checkpoint(checkpoint)
        # Периодически сохраняем накопленные строки в CSV
        if len(rows_buffer) >= config.BATCH_SIZE:
            temp_df = pd.DataFrame(rows_buffer)
            append_dataframe(temp_df, "matches.csv")
            rows_buffer.clear()
        time.sleep(config.DELAY)
    # Сохраняем остаток строк
    if rows_buffer:
        temp_df = pd.DataFrame(rows_buffer)
        append_dataframe(temp_df, "matches.csv")
        rows_buffer.clear()

    elapsed = time.time() - start
    logging.info(f"Собрано строк в таблице матчей: {len(csv_path)}")
    logging.info(f"Время: {elapsed:.2f} сек.")

    # Если нужен не CSV, конвертируем и сохраняем в нужный формат
    if config.SAVE_FORMAT != "csv":
        logging.info(f"Конвертация {csv_path} в {config.SAVE_FORMAT}...")
        matches_df = pd.read_csv(csv_path)
        save_dataframe(matches_df, "matches")
        # (опционально) можно удалить CSV, чтобы не дублировать
        # os.remove(csv_path)

    # Шаг 4: Справочники
    logging.info("\n4. Загрузка справочников чемпионов и предметов...")
    champions = fetch_champions()
    items = fetch_items()
    save_dataframe(champions, "champions")
    save_dataframe(items, "items")

    elapsed_full = time.time() - start_full
    logging.info("\n" + "=" * 50)
    logging.info("ETL завершён успешно!")
    logging.info(f"Всего затрачено время: {elapsed_full:.2f} сек.")
    logging.info("=" * 50)

if __name__ == "__main__":
    main()
