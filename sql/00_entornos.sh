#!/bin/bash
# Crea una base por entorno (agro_dev, agro_staging, agro_prod) y aplica el esquema en cada una.
# Corre solo al crear el contenedor; es idempotente, así que también sirve para actualizar
# una instalación existente:
#   docker compose exec postgres bash /docker-entrypoint-initdb.d/00_entornos.sh
#   docker compose exec postgres bash /docker-entrypoint-initdb.d/99_app_users.sh
# Sin "set -u": el entrypoint de postgres hace source de este archivo si no es ejecutable.

SCHEMA_DIR=/docker-entrypoint-initdb.d/schema

for env in dev staging prod; do
  db="agro_${env}"
  psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname postgres -tAc \
    "SELECT 1 FROM pg_database WHERE datname = '${db}'" | grep -q 1 \
    || psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname postgres -c "CREATE DATABASE ${db}"
  for f in "$SCHEMA_DIR"/*.sql; do
    psql -v ON_ERROR_STOP=1 -q --username "$POSTGRES_USER" --dbname "$db" -f "$f"
  done
  echo "[INIT] Base ${db} lista."
done
