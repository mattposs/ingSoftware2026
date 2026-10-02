-- Esquema de PostgreSQL (documento v7, figura 3: modelo de datos).
-- Bronze, Silver y Quarantine viven en el lake Parquet (storage/); acá solo Gold y control.
-- Se ejecuta automáticamente al crear el contenedor de PostgreSQL (docker-entrypoint-initdb.d).

CREATE SCHEMA IF NOT EXISTS gold;
CREATE SCHEMA IF NOT EXISTS etl;

-- Control de carga incremental: fin de la última ventana extraída por fuente.
CREATE TABLE IF NOT EXISTS etl.watermarks (
    domain         TEXT        NOT NULL,
    entity         TEXT        NOT NULL,
    watermark      TIMESTAMPTZ NOT NULL,
    last_batch_id  TEXT,
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (domain, entity)
);

-- Campos del cliente (se sincroniza desde config/fields.yaml en cada corrida).
CREATE TABLE IF NOT EXISTS gold.fields (
    field_id   TEXT PRIMARY KEY,
    nombre     TEXT          NOT NULL,
    provincia  TEXT          NOT NULL,
    latitude   NUMERIC(8, 5) NOT NULL,
    longitude  NUMERIC(8, 5) NOT NULL,
    hectareas  INTEGER
);

-- Indicadores diarios por campo y fuente: lo único que consume el dashboard (RF10, RNF04).
CREATE TABLE IF NOT EXISTS gold.daily_field_metrics (
    fecha                       DATE         NOT NULL,
    field_id                    TEXT         NOT NULL REFERENCES gold.fields (field_id),
    fuente                      TEXT         NOT NULL,
    temperatura_promedio        NUMERIC(6, 3),
    precipitacion_total         NUMERIC(8, 2),
    humedad_suelo_promedio      NUMERIC(6, 3),
    humedad_ambiental_promedio  NUMERIC(6, 3),
    cantidad_mediciones         INTEGER      NOT NULL,
    porcentaje_calidad          NUMERIC(5, 2) NOT NULL,
    _batch_id                   TEXT         NOT NULL,
    _updated_at                 TIMESTAMPTZ  NOT NULL DEFAULT now(),
    PRIMARY KEY (fecha, field_id, fuente)
);

-- Resumen de cada corrida (Data Quality Score, RF07).
CREATE TABLE IF NOT EXISTS gold.dq_run_metrics (
    _batch_id  TEXT PRIMARY KEY,
    run_start  TIMESTAMPTZ NOT NULL,
    run_end    TIMESTAMPTZ,
    status     TEXT        NOT NULL CHECK (status IN ('running', 'ok', 'failed')),
    total      INTEGER,
    valid      INTEGER,
    warning    INTEGER,
    invalid    INTEGER,
    dq_score   NUMERIC(5, 2)
);

-- Registro de errores detectados (RF08): rechazos y warnings, con la identificación del registro.
CREATE TABLE IF NOT EXISTS gold.dq_errors (
    error_id     BIGSERIAL PRIMARY KEY,
    _batch_id    TEXT        NOT NULL REFERENCES gold.dq_run_metrics (_batch_id) ON DELETE CASCADE,
    detected_at  TIMESTAMPTZ NOT NULL,
    measured_at  TIMESTAMPTZ,          -- fecha de la medición (NULL si el timestamp era inválido)
    source       TEXT,
    field_id     TEXT,                 -- sin FK: puede ser un campo inexistente (DQ04)
    variable     TEXT,
    rule_id      TEXT        NOT NULL,
    rule_type    TEXT        NOT NULL,
    action       TEXT        NOT NULL CHECK (action IN ('REJECT', 'WARNING')),
    severidad    TEXT        NOT NULL,
    detalle      TEXT
);

CREATE INDEX IF NOT EXISTS ix_dq_errors_batch ON gold.dq_errors (_batch_id);
CREATE INDEX IF NOT EXISTS ix_dq_errors_field_date ON gold.dq_errors (field_id, measured_at);
