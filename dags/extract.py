# extract.py
import requests
import time
import pandas as pd
from config import config
import logging
import sys
import os
import json

# ═══════════════════════════════════════════════════════════
# НАСТРОЙКА ЛОГИРОВАНИЯ
# ═══════════════════════════════════════════════════════════
def setup_logging(level: str = "INFO") -> None:
    """
    Настраивает единый формат логов для всего скрипта.
    Пишет в stdout с временной меткой, уровнем и сообщением.
    Уровень по умолчанию INFO, можно переопределить в config.yaml.
    """
    level_name = getattr(logging, str(level).upper(), logging.INFO)
    logging.basicConfig(
        level=level_name,
        format="%(asctime)s %(levelname)s — %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )

# ═══════════════════════════════════════════════════════════
#  HTTP-ЗАПРОСЫ
# ═══════════════════════════════════════════════════════════
def _request_with_retry(url, headers, timeout, retries=3, backoff=1.5):
    """Выполняет GET-запрос с повторными попытками при ошибках."""
    for attempt in range(retries):
        try:
            resp = requests.get(url, timeout=timeout, headers=headers)
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.RequestException as e:
            if attempt == retries - 1:
                raise
            wait = backoff * (2 ** attempt)
            if hasattr(e, 'response') and e.response is not None:
                retry_after = e.response.headers.get('Retry-After')
                if retry_after:
                    try:
                        wait = int(retry_after)
                    except ValueError:
                        # если это дата, можно распарсить, но для простоты оставляем экспоненциальную
                        pass
            logging.error(f"Ошибка: {e}. Повтор через {wait:.1f} сек...")
            time.sleep(wait)

def load_checkpoint():
    if os.path.exists(config.CHECKPOINT_FILE):
        with open(config.CHECKPOINT_FILE, "r") as f:
            return json.load(f)
    return {"processed_match_ids": [], "players_done": []}

def save_checkpoint(data):
    with open(config.CHECKPOINT_FILE, "w") as f:
        json.dump(data, f)

def fetch_players():
    """
    Получает список топ-игроков (Challenger, Grandmaster, Master)
    для всех регионов.
    Возвращает DataFrame с колонками: puuid, leaguePoints, wins, losses, tier, region.
    """
    all_entries = []
    headers = {"X-Riot-Token": config.API_KEY}

    for region in config.REGIONS:
        for tier in config.TIERS:
            url = f"https://{region}.api.riotgames.com/lol/league/v4/{tier}leagues/by-queue/{config.QUEUE}"
            try:
                data = _request_with_retry(url, headers, config.TIMEOUT)
                entries = pd.DataFrame(data["entries"])
                entries["region"] = region.upper()
                entries["tier"] = tier.upper()
                all_entries.append(entries)
                time.sleep(config.DELAY)
            except Exception as e:
                logging.error(f"Не удалось загрузить {region}/{tier}: {e}")
                
    if not all_entries:
        raise RuntimeError("Не получено ни одной записи о игроках.")

    df = pd.concat(all_entries, ignore_index=True)
    # Оставляем только нужные колонки
    df = df[["puuid", "leaguePoints", "wins", "losses", "tier", "region"]]
    return df

def fetch_match_ids_for_player(puuid, region):
    """
    Получает список ID последних матчей для одного игрока.
    Возвращает список строк (match_id).
    """
    headers = {"X-Riot-Token": config.API_KEY}
    # Для NA1 используем americas, для EUW1 и RU – europe
    if region == "NA1":
        api_region = "americas"
    else:
        api_region = "europe"

    url = f"https://{api_region}.api.riotgames.com/lol/match/v5/matches/by-puuid/{puuid}/ids?queue=420&type=ranked&count={config.MATCH_COUNT}"
    try:
        data = _request_with_retry(url, headers, config.TIMEOUT)
        return data
    except Exception as e:
        logging.error(f"Ошибка получения ID матчей для {puuid}: {e}")
        return []

def fetch_match_details(match_id, region):
    """
    Загружает детальную информацию об одном матче по его ID.
    Возвращает JSON-ответ API.
    """
    headers = {"X-Riot-Token": config.API_KEY}
    if region == "NA1":
        api_region = "americas"
    else:
        api_region = "europe"

    url = f"https://{api_region}.api.riotgames.com/lol/match/v5/matches/{match_id}"
    try:
        return _request_with_retry(url, headers, config.TIMEOUT)
    except Exception as e:
        logging.error(f"Ошибка загрузки матча {match_id}: {e}")
        return None

def fetch_champions(version=None):
    """Загружает справочник чемпионов с DDragon."""
    if version is None:
        versions = requests.get("https://ddragon.leagueoflegends.com/api/versions.json").json()
        version = versions[0]
    url = f"https://ddragon.leagueoflegends.com/cdn/{version}/data/en_US/champion.json"
    data = requests.get(url).json()
    champions = []
    for name, info in data["data"].items():
        champions.append({
            "champion": name,
            "tags": ",".join(info["tags"])
        })
    return pd.DataFrame(champions)

def fetch_items(version=None):
    """Загружает справочник предметов с DDragon."""
    if version is None:
        versions = requests.get("https://ddragon.leagueoflegends.com/api/versions.json").json()
        version = versions[0]
    url = f"https://ddragon.leagueoflegends.com/cdn/{version}/data/en_US/item.json"
    data = requests.get(url).json()
    items = []
    for item_id, info in data["data"].items():
        items.append({
            "item_id": item_id,
            "item_name": info.get("name"),
            "gold_total": info.get("gold", {}).get("total"),
            "gold_sell": info.get("gold", {}).get("sell"),
        })
    return pd.DataFrame(items)
