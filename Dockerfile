FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY config/rules.yaml config/fields.yaml config/pipeline.yaml config/
COPY src/ src/

RUN useradd --create-home --uid 1000 pipeline && mkdir -p /app/storage && chown pipeline /app/storage
USER pipeline

CMD ["python", "-m", "src.main"]
