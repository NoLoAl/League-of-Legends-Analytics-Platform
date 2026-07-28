# load.py
import os
import pandas as pd
from config import config

def save_dataframe(df, filename):
    """Сохраняет DataFrame в формате, указанном в конфиге."""
    os.makedirs(config.OUTPUT_DIR, exist_ok=True)
    path = os.path.join(config.OUTPUT_DIR, filename)

    if config.SAVE_FORMAT == "csv":
        df.to_csv(f"{path}.csv", index=False)
    elif config.SAVE_FORMAT == "parquet":
        df.to_parquet(f"{path}.parquet", index=False)
    else:
        raise ValueError(f"Неподдерживаемый формат: {config.SAVE_FORMAT}")

    print(f"Сохранено: {path}.{config.SAVE_FORMAT}")

def append_dataframe(df, filename):
    """Дописывает DataFrame в CSV-файл (без заголовков)."""
    os.makedirs(config.OUTPUT_DIR, exist_ok=True)
    path = os.path.join(config.OUTPUT_DIR, filename)
    
    if not os.path.exists(path):
        df.to_csv(path, index=False)
    else:
        df.to_csv(path, mode='a', header=False, index=False)