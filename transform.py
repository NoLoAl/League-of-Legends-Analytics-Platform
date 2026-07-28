# transform.py
import pandas as pd

def enrich_players(df):
    """
    Добавляет рассчитанные поля: winrate, общее количество матчей,
    а также колонку 'region_api' для выбора правильного региона в Match API.
    """
    df = df.copy()
    df["winrate_%"] = round((df["wins"] / (df["wins"] + df["losses"])) * 100, 2)
    df["matches_total"] = df["wins"] + df["losses"]
    # Маппинг региона для Match API
    df["region_api"] = df["region"].apply(
        lambda x: "americas" if x == "NA1" else "europe"
    )
    # Переименовываем колонки для единообразия
    df.rename(columns={
        "puuid": "puu_id",
        "leaguePoints": "league_points",
        "tier": "range"
    }, inplace=True)
    return df

def process_match_data(match_json, match_id):
    """
    Из JSON одного матча извлекает данные по каждому участнику
    и возвращает список словарей (строк для DataFrame).
    """
    rows = []
    info = match_json.get("info")
    if not info:
        return rows
    participants = info.get("participants", [])
    game_duration = info.get("gameDuration")
    game_version = info.get("gameVersion")

    for p in participants:
        row = {
            "match_id": match_id,
            "puuid": p.get("puuid"),
            "champion": p.get("championName"),
            "kills": p.get("kills"),
            "deaths": p.get("deaths"),
            "assists": p.get("assists"),
            "gold_earned": p.get("goldEarned"),
            "damage_to_champions": p.get("totalDamageDealtToChampions"),
            "minions_killed": p.get("totalMinionsKilled"),
            "vision_score": p.get("visionScore"),
            "win": p.get("win"),
            "team_position": p.get("teamPosition"),
            "game_duration_sec": game_duration,
            "game_version": game_version,
            "item0": p.get("item0"),
            "item1": p.get("item1"),
            "item2": p.get("item2"),
            "item3": p.get("item3"),
            "item4": p.get("item4"),
            "item5": p.get("item5"),
        }
        rows.append(row)
    return rows
