# Используем официальный образ Airflow
FROM apache/airflow:2.9.0-python3.11

# Переключаемся на пользователя root для установки системных пакетов (если нужно)
USER root
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Возвращаемся к пользователю airflow
USER airflow

# Копируем requirements.txt и устанавливаем зависимости
COPY --chown=airflow:airflow requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем исходный код приложения и DAG
COPY --chown=airflow:airflow config.py extract.py transform.py load.py /opt/airflow/
COPY --chown=airflow:airflow dags/ /opt/airflow/dags/

# Устанавливаем PYTHONPATH, чтобы модули были доступны
ENV PYTHONPATH="${PYTHONPATH}:/opt/airflow"

# Создаём директорию для данных (будет перезаписана volume)
RUN mkdir -p /opt/airflow/data