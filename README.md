# 🎮 League of Legends ETL Pipeline

ETL-пайплайн для сбора, трансформации и загрузки данных о топ-игроках **League of Legends** (Challenger / Grandmaster / Master) через [Riot Games API](https://developer.riotgames.com/). Проект поддерживает инкрементальную загрузку с чекпоинтами, оркестрацию через Apache Airflow и выгрузку в Parquet / CSV. Также включён модуль для построения дашборда.

---

## 📁 Структура проекта
```text
├── dags/                       # Модули для Airflow (монтируются в контейнер)
│   ├── config.py
│   ├── extract.py
│   ├── load.py
│   ├── lol_etl_dag.py
│   └── transform.py
├── data/                       # Выходные данные (Parquet / Excel)
│   ├── champions.parquet
│   ├── items.parquet
│   ├── matches.parquet
│   ├── matches.xlsx            # экспорт для анализа в Excel
│   └── players.parquet
├── .env                        # Переменные окружения 
├── checkpoint.json             # Чекпоинт обработанных матчей и игроков
├── config.py                   # Конфигурация пайплайна
├── dashboard                   # Скрипт / ноутбук для визуализации
├── docker-compose.yml          # Инфраструктура Airflow + PostgreSQL + Redis
├── Dockerfile                  # Образ для Airflow
├── extract.py                  # Извлечение данных из Riot API и DDragon
├── load.py                     # Сохранение в CSV / Parquet
├── main.py                     # Локальный запуск ETL без оркестратора
├── requirements.txt            # Python-зависимости
└── transform.py                # Трансформация и обогащение данных
```
> **Примечание:** файлы `config.py`, `extract.py`, `load.py`, `transform.py` продублированы в папке `dags/`, чтобы DAG Airflow мог импортировать их напрямую при запуске внутри Docker.

---

## 🏗️ Архитектура

| Этап | Описание |
|------|----------|
| **Extract** | Загрузка списка топ-игроков по регионам, сбор ID последних матчей, загрузка деталей матчей и справочников (чемпионы, предметы) |
| **Transform** | Расчёт винрейта, общего числа матчей, нормализация полей, извлечение статистики по каждому участнику |
| **Load** | Сохранение в CSV или Parquet с промежуточной batch-записью |
| **Orchestrate** | Apache Airflow DAG с ежедневным расписанием `@daily` и retry-политикой |

### Поддерживаемые регионы
- `NA1` → Americas
- `EUW1` → Europe
- `RU` → Europe

---

## ⚙️ Конфигурация

Все параметры задаются через переменные окружения (`.env`) и `config.py`:

```bash
# .env
RIOT_API_KEY=RGAPI-xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
AIRFLOW__CORE__EXECUTOR=LocalExecutor
AIRFLOW__CORE__SQL_ALCHEMY_CONN=postgresql+psycopg2://airflow:airflow@postgres/airflow
AIRFLOW__CORE__FERNET_KEY=your_fernet_key_here
AIRFLOW__WEBSERVER__SECRET_KEY=your_secret_key_here

Ключевые параметры (config.py)

| Параметр          | По умолчанию        | Описание                                      |
| ----------------- | ------------------- | --------------------------------------------- |
| `MATCH_COUNT`     | `3`                 | Количество последних матчей на игрока         |
| `MIN_WINS`        | `500`               | Минимальное число побед для фильтрации        |
| `DELAY`           | `0.85`              | Задержка между запросами к API (сек)          |
| `BATCH_SIZE`      | `10`                | Размер промежуточного батча при записи матчей |
| `SAVE_FORMAT`     | `"parquet"`         | Формат выходных файлов: `csv` или `parquet`   |
| `CHECKPOINT_FILE` | `"checkpoint.json"` | Файл для возобновления работы                 |
```
---

## 🚀 Быстрый старт

# 1. Локальный запуск (без Airflow)
```
# Установка зависимостей
pip install -r requirements.txt
# Создайте .env и добавьте RIOT_API_KEY
echo "RIOT_API_KEY=your_key_here" > .env
# Запуск ETL
python main.py

Результаты появятся в папке data/:
players.parquet — данные игроков
matches.csv / matches.parquet — детали матчей
champions.parquet, items.parquet — справочники
```
## 2. Запуск через Docker + Airflow
```
# Инициализация базы Airflow
docker compose --profile init up -d init
# Запуск полного стека
docker compose up -d
# Веб-интерфейс Airflow
open http://localhost:8080

DAG lol_etl_pipeline будет доступен в интерфейсе Airflow и запускается по расписанию @daily.
```
---

## 📊 Описание данных

players.parquet
| Поле              | Тип    | Описание                               |
| ----------------- | ------ | -------------------------------------- |
| `puu_id`          | string | Уникальный ID игрока                   |
| `league_points`   | int    | Очки лиги                              |
| `wins` / `losses` | int    | Победы / поражения                     |
| `winrate_%`       | float  | Расчётный винрейт                      |
| `matches_total`   | int    | Общее число игр                        |
| `range`           | string | Лига (CHALLENGER, GRANDMASTER, MASTER) |
| `region`          | string | Регион игрока                          |
| `region_api`      | string | Регион для Match API                   |

matches.parquet
| Поле                           | Тип    | Описание                                    |
| ------------------------------ | ------ | ------------------------------------------- |
| `match_id`                     | string | ID матча                                    |
| `puuid`                        | string | ID участника                                |
| `champion`                     | string | Имя чемпиона                                |
| `kills` / `deaths` / `assists` | int    | KDA                                         |
| `gold_earned`                  | int    | Заработанное золото                         |
| `damage_to_champions`          | int    | Урон по чемпионам                           |
| `vision_score`                 | int    | Очки обзора                                 |
| `team_position`                | string | Роль (TOP, JUNGLE, MIDDLE, BOTTOM, UTILITY) |
| `game_duration_sec`            | int    | Длительность матча                          |
| `item0` … `item5`              | int    | ID предметов                                |
| `win`                          | bool   | Победа / поражение                          |

---

## 🛡️ Надёжность

- Retry-логика — при ошибках сети запросы повторяются до 3 раз с экспоненциальным backoff и учётом заголовка Retry-After.
- Чекпоинты (checkpoint.json) — если процесс прервётся, повторный запуск продолжит с места остановки. Уже обработанные матчи и игроки пропускаются.
- Batch-запись — данные матчей сохраняются порциями (BATCH_SIZE), чтобы не терять прогресс при длительной загрузке.
- Rate limiting — встроенная задержка (DELAY) между запросами для соблюдения лимитов Riot API.

---

## 🛠️ Стек технологий

Python 3.10+
Pandas / PyArrow — обработка и сохранение данных
Requests — HTTP-клиент для API
Apache Airflow 2.9 — оркестрация
PostgreSQL 13 — метаданные Airflow
Redis 7 — брокер сообщений
Docker & Compose — контейнеризация

---

## ⚠️ Важно

API-ключ Riot Games (Development Key) действует 24 часа. Обновляйте ключ в .env перед каждым запуском.
