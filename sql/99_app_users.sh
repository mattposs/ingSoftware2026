#!/bin/bash
# Usuarios con permisos mínimos (RNF07). Las contraseñas vienen del entorno (.env),
# nunca del repositorio.
#   - pipeline: lee y escribe gold.* y etl.* (no puede crear esquemas ni borrar tablas).
#   - dashboard: solo lectura de gold.*.
# Se aplican en las tres bases (agro_dev, agro_staging, agro_prod). Idempotente.
# Sin "set -u": el entrypoint de postgres hace source de este archivo si no es ejecutable.

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname postgres \
  -v pipeline_user="$PIPELINE_DB_USER" -v pipeline_pass="$PIPELINE_DB_PASSWORD" \
  -v dashboard_user="$DASHBOARD_DB_USER" -v dashboard_pass="$DASHBOARD_DB_PASSWORD" <<'EOSQL'
SELECT format('CREATE ROLE %I LOGIN PASSWORD %L', :'pipeline_user', :'pipeline_pass')
WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname = :'pipeline_user') \gexec
SELECT format('CREATE ROLE %I LOGIN PASSWORD %L', :'dashboard_user', :'dashboard_pass')
WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname = :'dashboard_user') \gexec
EOSQL

for env in dev staging prod; do
  psql -v ON_ERROR_STOP=1 -q --username "$POSTGRES_USER" --dbname "agro_${env}" \
    -v pipeline_user="$PIPELINE_DB_USER" -v dashboard_user="$DASHBOARD_DB_USER" <<'EOSQL'
GRANT CONNECT, TEMPORARY ON DATABASE :"DBNAME" TO :"pipeline_user";  -- TEMPORARY: staging del upsert
GRANT USAGE ON SCHEMA gold, etl TO :"pipeline_user";
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA gold, etl TO :"pipeline_user";
GRANT USAGE ON ALL SEQUENCES IN SCHEMA gold TO :"pipeline_user";

GRANT CONNECT ON DATABASE :"DBNAME" TO :"dashboard_user";
GRANT USAGE ON SCHEMA gold TO :"dashboard_user";
GRANT SELECT ON ALL TABLES IN SCHEMA gold TO :"dashboard_user";

-- Tablas que se agreguen más adelante heredan los mismos permisos.
ALTER DEFAULT PRIVILEGES IN SCHEMA gold, etl GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO :"pipeline_user";
ALTER DEFAULT PRIVILEGES IN SCHEMA gold GRANT USAGE ON SEQUENCES TO :"pipeline_user";
ALTER DEFAULT PRIVILEGES IN SCHEMA gold GRANT SELECT ON TABLES TO :"dashboard_user";
EOSQL
  echo "[INIT] Permisos aplicados en agro_${env}."
done
