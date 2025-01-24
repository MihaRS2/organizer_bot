FROM python:3.9-slim

ENV TZ=Europe/Moscow
ENV PYTHONUNBUFFERED=1

RUN apt-get update && \
    apt-get install -y build-essential libpq-dev tzdata && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "-m", "bot.main"]
