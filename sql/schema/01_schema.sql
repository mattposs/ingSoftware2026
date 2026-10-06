-- Esquema de PostgreSQL (documento v7, figura 3: modelo de datos).
-- Bronze, Silver y Quarantine viven en el lake Parquet (storage/); acá solo Gold y control.
-- Lo aplica sql/00_entornos.sh en cada base (agro_dev, agro_staging, agro_prod) al crear el
-- contenedor. Es idempotente: se puede volver a correr para agregar tablas nuevas.

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

-- Trazabilidad del flujo Medallion (RNF02): qué hizo cada capa en cada lote.
-- El lake Parquet no es legible desde el dashboard; esta tabla resume cada etapa.
CREATE TABLE IF NOT EXISTS gold.pipeline_layer_metrics (
    _batch_id     TEXT        NOT NULL REFERENCES gold.dq_run_metrics (_batch_id) ON DELETE CASCADE,
    layer         TEXT        NOT NULL CHECK (layer IN ('bronze', 'silver', 'quarantine', 'gold')),
    entity        TEXT        NOT NULL,  -- fuente (bronze) o tabla/entidad destino
    rows          INTEGER     NOT NULL,
    location      TEXT,                  -- carpeta del lake o tabla de PostgreSQL
    window_start  TIMESTAMPTZ,           -- solo bronze: ventana incremental (inicio exclusivo)
    window_end    TIMESTAMPTZ,
    started_at    TIMESTAMPTZ,
    finished_at   TIMESTAMPTZ,
    PRIMARY KEY (_batch_id, layer, entity)
);

-- ETL paso a paso: por cada lote se guardan unos pocos registros de muestra (válidos, con
-- warning y rechazados) con lo que les pasó en cada etapa, para mostrarlo en el dashboard.
CREATE TABLE IF NOT EXISTS gold.etl_trace (
    trace_id       TEXT PRIMARY KEY,           -- <lote>-<n>
    _batch_id      TEXT        NOT NULL REFERENCES gold.dq_run_metrics (_batch_id) ON DELETE CASCADE,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    dq_status      TEXT        NOT NULL CHECK (dq_status IN ('VALID', 'WARNING', 'INVALID')),
    source         TEXT,
    field_id       TEXT,
    measured_at    TIMESTAMPTZ,
    fecha_negocio  DATE,                       -- día de Gold al que aporta (si llega a Gold)
    titulo         TEXT        NOT NULL        -- texto para elegir el registro en el dashboard
);

CREATE TABLE IF NOT EXISTS gold.etl_trace_steps (
    trace_id   TEXT    NOT NULL REFERENCES gold.etl_trace (trace_id) ON DELETE CASCADE,
    step       INTEGER NOT NULL CHECK (step BETWEEN 1 AND 5),
    orden      INTEGER NOT NULL,
    dato       TEXT    NOT NULL,
    valor      TEXT,
    resultado  TEXT,                           -- OK / WARNING / REJECT (solo en validación)
    PRIMARY KEY (trace_id, step, orden)
);

CREATE INDEX IF NOT EXISTS ix_dq_errors_batch ON gold.dq_errors (_batch_id);
CREATE INDEX IF NOT EXISTS ix_dq_errors_field_date ON gold.dq_errors (field_id, measured_at);
