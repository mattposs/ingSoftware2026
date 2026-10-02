#!/bin/bash
# Usuarios con permisos mínimos (RNF07). Las contraseñas vienen del entorno (.env),
# nunca del repositorio.
#   - pipeline: lee y escribe gold.* y etl.* (no puede crear esquemas ni borrar tablas).
#   - dashboard: solo lectura de gold.*.
# Sin "set -u": el entrypoint de postgres hace source de este archivo si no es ejecutable.

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
  -v pipeline_user="$PIPELINE_DB_USER" -v pipeline_pass="$PIPELINE_DB_PASSWORD" \
  -v dashboard_user="$DASHBOARD_DB_USER" -v dashboard_pass="$DASHBOARD_DB_PASSWORD" <<'EOSQL'
CREATE ROLE :"pipeline_user" LOGIN PASSWORD :'pipeline_pass';
GRANT CONNECT ON DATABASE :"DBNAME" TO :"pipeline_user";
GRANT USAGE ON SCHEMA gold, etl TO :"pipeline_user";
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA gold, etl TO :"pipeline_user";
GRANT USAGE ON ALL SEQUENCES IN SCHEMA gold TO :"pipeline_user";
-- tablas temporales para el staging del upsert
GRANT TEMPORARY ON DATABASE :"DBNAME" TO :"pipeline_user";

CREATE ROLE :"dashboard_user" LOGIN PASSWORD :'dashboard_pass';
GRANT CONNECT ON DATABASE :"DBNAME" TO :"dashboard_user";
GRANT USAGE ON SCHEMA gold TO :"dashboard_user";
GRANT SELECT ON ALL TABLES IN SCHEMA gold TO :"dashboard_user";
EOSQL
