"""
migrations.py
Migraciones idempotentes del esquema que se aplican al arrancar el pipeline.

Los volúmenes de PostgreSQL que ya existen no vuelven a correr sql/ (el entrypoint de la imagen
solo lo hace con la base vacía), así que una columna nueva no llegaría a las bases creadas antes.
Por eso el pipeline revisa al arrancar si faltan columnas y, si faltan, las agrega.

El usuario del pipeline no es dueño de las tablas (RNF07: permisos mínimos) y no puede hacer
ALTER TABLE. La migración usa otra conexión, en este orden:
  1. MIGRATION_DATABASE_URL, si está definida;
  2. DATABASE_URL, si está definida (tests y CI, que ya usan un usuario con permisos);
  3. el superusuario POSTGRES_USER / POSTGRES_PASSWORD sobre la base del entorno.
Esa conexión se abre solo si falta algo y se cierra enseguida.
"""

import os

from sqlalchemy import Engine, create_engine, text

from src.config import current_env

# Monitoreo de corridas (alertas AL01 / AL02, RNF08 y RNF09).
RUN_MONITORING_COLUMNS = {
    "run_status": "TEXT CHECK (run_status IN ('SUCCESS', 'FAILED'))",
    "started_at": "TIMESTAMPTZ",
    "finished_at": "TIMESTAMPTZ",
    "duration_seconds": "NUMERIC(10, 2)",
    "last_measured_at": "TIMESTAMPTZ",   # timestamp máximo de medición del lote (frescura)
}

MIGRATIONS = [
    f"ALTER TABLE gold.dq_run_metrics ADD COLUMN IF NOT EXISTS {col} {ddl}"
    for col, ddl in RUN_MONITORING_COLUMNS.items()
]


def missing_columns(engine: Engine) -> list[str]:
    """Columnas de monitoreo que todavía no existen en gold.dq_run_metrics."""
    with engine.connect() as conn:
        present = set(conn.execute(text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema = 'gold' AND table_name = 'dq_run_metrics'"
        )).scalars())
    return [c for c in RUN_MONITORING_COLUMNS if c not in present]


def apply(engine: Engine) -> None:
    """Corre todas las migraciones (idempotentes: ADD COLUMN IF NOT EXISTS)."""
    with engine.begin() as conn:
        for sql in MIGRATIONS:
            conn.execute(text(sql))
        # El usuario de solo lectura del dashboard ve las columnas nuevas por el GRANT a nivel tabla;
        # se repite por si la base se creó sin sql/99_app_users.sh.
        dashboard = os.getenv("DASHBOARD_DB_USER", "dashboard")
        if conn.execute(text("SELECT 1 FROM pg_roles WHERE rolname = :r"), {"r": dashboard}).scalar():
            conn.execute(text(f'GRANT SELECT ON gold.dq_run_metrics TO "{dashboard}"'))


def migration_url() -> str:
    url = os.getenv("MIGRATION_DATABASE_URL") or os.getenv("DATABASE_URL")
    if url:
        return url
    user = os.getenv("POSTGRES_USER", "postgres")
    password = os.getenv("POSTGRES_PASSWORD", "")
    host = os.getenv("POSTGRES_HOST", "localhost")
    port = os.getenv("POSTGRES_PORT", "5432")
    return f"postgresql+psycopg://{user}:{password}@{host}:{port}/agro_{current_env()}"


def ensure_schema(engine: Engine) -> list[str]:
    """Agrega las columnas que falten. Devuelve las que se agregaron (vacío si no hacía falta)."""
    missing = missing_columns(engine)
    if not missing:
        return []
    admin = create_engine(migration_url())
    try:
        apply(admin)
    finally:
        admin.dispose()
    print(f"[MIGRACIÓN] gold.dq_run_metrics: columnas agregadas {', '.join(missing)}.")
    return missing
