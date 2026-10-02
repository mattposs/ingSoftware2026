"""
db.py
Conexión a PostgreSQL y upsert idempotente (skill de-developer: gold_upsert).
"""

import uuid

import pandas as pd
from sqlalchemy import Engine, create_engine

from src.config import get_settings


def get_engine(database_url: str | None = None) -> Engine:
    return create_engine(database_url or get_settings().database_url, pool_pre_ping=True)


def build_upsert_sql(
    target: str,
    staging: str,
    columns: list[str],
    conflict_keys: list[str],
    update_columns: list[str] | None = None,
) -> str:
    """Arma el INSERT ... ON CONFLICT. Si no hay columnas para actualizar usa DO NOTHING."""
    if update_columns is None:
        update_columns = [c for c in columns if c not in conflict_keys]
    cols = ", ".join(f'"{c}"' for c in columns)
    keys = ", ".join(f'"{c}"' for c in conflict_keys)
    if update_columns:
        action = "DO UPDATE SET " + ", ".join(f'"{c}" = EXCLUDED."{c}"' for c in update_columns)
    else:
        action = "DO NOTHING"
    return f"INSERT INTO {target} ({cols}) SELECT {cols} FROM {staging} ON CONFLICT ({keys}) {action};"


def upsert(
    df: pd.DataFrame,
    engine: Engine,
    schema: str,
    table: str,
    conflict_keys: list[str],
    update_columns: list[str] | None = None,
) -> int:
    """
    Upsert atómico: staging TEMPORAL (se borra al cerrar la transacción) + ON CONFLICT.
    Si el lote trae la misma clave repetida se conserva la última aparición, porque
    Postgres no permite que un INSERT ... ON CONFLICT toque dos veces la misma fila.
    """
    if df.empty:
        print(f"[DB] Lote vacío: se omite upsert en {schema}.{table}.")
        return 0

    df = df.drop_duplicates(subset=conflict_keys, keep="last")
    staging = f"stg_{table}_{uuid.uuid4().hex[:8]}"
    sql = build_upsert_sql(f'"{schema}"."{table}"', f'"{staging}"', list(df.columns), conflict_keys, update_columns)

    with engine.begin() as conn:
        conn.exec_driver_sql(
            f'CREATE TEMP TABLE "{staging}" (LIKE "{schema}"."{table}" INCLUDING DEFAULTS) ON COMMIT DROP'
        )
        df.to_sql(staging, con=conn, if_exists="append", index=False)
        conn.exec_driver_sql(sql)

    print(f"[DB] Upsert de {len(df)} filas en {schema}.{table}.")
    return len(df)
