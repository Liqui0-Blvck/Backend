FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

WORKDIR /app

COPY requirements.txt ./
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY . .

COPY docker-entrypoint-new.sh /app/docker-entrypoint.sh
RUN chmod +x /app/docker-entrypoint.sh
