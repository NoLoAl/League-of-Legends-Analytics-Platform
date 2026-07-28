# config.py
import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # API
    API_KEY = os.getenv("RIOT_API_KEY")
    REGIONS = {'NA1': 'americas', 'EUW1': 'europe', 'RU': 'europe'}
    TIERS = ["challenger", "grandmaster", "master"]
    QUEUE = "RANKED_SOLO_5x5"
    MATCH_COUNT = 3                 # количество последних матчей на игрока
    DELAY = 0.85                    # задержка между запросами (сек)
    TIMEOUT = 20
    CHECKPOINT_FILE = "checkpoint.json"
    BATCH_SIZE = 10          # количество матчей для промежуточной записи

    # Фильтр
    MIN_WINS = 500
    log_level: "INFO"
    
    # Выходные данные
    OUTPUT_DIR = "data"
    SAVE_FORMAT = "parquet"         # "csv" или "parquet"

config = Config()
