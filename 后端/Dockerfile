FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    SURVEY_HOST=0.0.0.0 \
    SURVEY_PORT=8000 \
    SURVEY_DB_PATH=/mnt/sqlite/survey_data.db \
    SURVEY_PROJECT_ROOT=/app

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY . /app

RUN mkdir -p /mnt/sqlite

EXPOSE 8000

CMD ["python", "survey_server.py"]
