# League of Legends ETL Pipeline

## О проекте

League of Legends Analytics — аналитическая платформа для автоматизированного сбора, хранения, обработки и визуализации игровых данных League of Legends с использованием официального Riot Games API.

Проект реализует полный цикл работы с данными:

- получение данных из Riot API;
- хранение данных в Parquet;
- аналитическую обработку данных;
- построение аналитических витрин;
- визуализацию данных через интерактивный веб-дашборд.

---

## 🎯 Цель проекта

Разработка системы аналитики игровых данных, позволяющей исследовать:

- активность игроков высоких рангов;
- эффективность чемпионов;
- распределение рейтинговых очков (LP);
- различия между игровыми регионами;
- динамику показателей во времени.

---

## 🏗 Архитектура решения

```text
                    Riot API
                        │
                        ▼
                    LOL_ETL.py
                        │
                        ▼
                   transform
                        │
                        ▼
                      load 
                     ┌──┴─────┐
                     ▼        ▼
                    CSV    Parquet
                     │        │
                     └────┬───┘
                          ▼
                   Dash Dashboard
```
---

## 📊 Источники данных

### Riot Games API

Используется для получения:

- информации об игроках;
- рейтинговых таблиц;
- истории матчей;
- статистики участников матчей.

### Riot Data Dragon

Используется для получения:

- списка чемпионов;
- названий чемпионов.


## 🌍 Анализируемые регионы

- Europe West (EUW1)
- North America (NA1)

---

## 🏆 Анализируемые лиги

- Challenger
- Grandmaster
- Master

Для внализа взяты игроки у которых больше 500 побед.

---

# 🗄 Структура базы данных

## Основные таблицы

### matches_data

Хранит информацию о матчах:

- match_id
- puuid	champion
- kills
- deaths
- assists
- gold_earned
- damage_to_champions
- minions_killed
- vision_score
- win
- team_position
- game_duration_sec
- game_version
- item0_5

### players_data

Содержит информацию о игроках:

- puu_id
- region
- server
- range
- league_points
- wins
- losses
- winrate_%
- matches_month

### champions_data

Содержит информацию о героях:

- champion
- tags

### items_data

Содержит информацию о предметах:

- item_id
- item_name
- gold_total
- gold_sell

---

# 🔄 ETL-процесс

## LOL_ETL.py

Выполняет:

- получение данных из Riot API;
- сбор информации об игроках и матчах;
- формирование реестра игроков;
- сохранение сырых данных в CSV/Parquet файлы.

---

# 🛠 Используемые технологии

- Python
- Parquet
- Pandas
- NumPy
- Dash
- Plotly

## API

- Riot Games API
- Riot Data Dragon

---

### 🔑 Важное примечание по `RIOT_API_KEY`

1. Перейдите на [Riot Developer Portal](https://riotgames.com).
2. Войдите в аккаунт и обновите/скопируйте ваш текущий ключ `RGAPI-...`.
3. Вставьте его в файл `.env` вместо старого значения `YOUR_API_KEY`.
4. **Важно:** После обновления ключа на сайте Riot, подождите **2–3 минуты** перед запуском скрипта. Серверам авторизации Riot требуется время, чтобы новый ключ активировался глобально.

---

# 📚 Полезные ссылки

- Riot Developer Portal: https://developer.riotgames.com/
- Riot Data Dragon: https://developer.riotgames.com/docs/lol#data-dragon
- League of Legends: https://www.leagueoflegends.com/
