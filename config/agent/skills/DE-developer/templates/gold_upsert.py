"""
gold_upsert.py
Módulo genérico para ejecución atómica de operaciones UPSERT (INSERT ... ON CONFLICT)
en PostgreSQL utilizando una tabla temporal de staging y SQLAlchemy.

IMPORTANTE: el upsert reemplaza los valores de la fila existente. Si el DataFrame
contiene agregados calculados solo sobre el lote nuevo (el "delta"), un día que
llega en dos lotes queda con las métricas del segundo lote únicamente. Para métricas
agregadas, recalcular cada clave afectada con TODO Silver antes de llamar a esta función.
"""

import uuid

import pandas as pd
from sqlalchemy import Engine


def build_upsert_sql(target: str, staging: str, columns: list[str], conflict_keys: list[str],
                     update_columns: list[str] | None = None) -> str:
    if update_columns is None:
        update_columns = [c for c in columns if c not in conflict_keys]
    cols = ", ".join(f'"{c}"' for c in columns)
    keys = ", ".join(f'"{c}"' for c in conflict_keys)
    if update_columns:
        action = "DO UPDATE SET " + ", ".join(f'"{c}" = EXCLUDED."{c}"' for c in update_columns)
    else:
        action = "DO NOTHING"  # todas las columnas son clave: no hay nada que actualizar
    return f"INSERT INTO {target} ({cols}) SELECT {cols} FROM {staging} ON CONFLICT ({keys}) {action};"


def upsert_to_postgres(
    df: pd.DataFrame,
    table_name: str,
    schema: str,
    engine: Engine,
    conflict_keys: list[str],
    update_columns: list[str] | None = None
) -> int:
    """
    Realiza un Upsert atómico e idempotente en PostgreSQL desde un DataFrame de Pandas.

    Estrategia:
    1. Deduplica el lote por conflict_keys (Postgres no permite que un mismo INSERT
       ... ON CONFLICT afecte dos veces la misma fila).
    2. Crea una tabla TEMPORAL con la estructura de la tabla destino (se borra sola
       al terminar la transacción, aunque falle) y vuelca el lote.
    3. Ejecuta INSERT INTO destino SELECT ... FROM staging ON CONFLICT ...

    Requisito: la tabla destino debe tener PRIMARY KEY o UNIQUE sobre conflict_keys.
    """
    if df.empty:
        print(f"[GOLD] DataFrame vacío. Se omite carga en {schema}.{table_name}.")
        return 0

    df = df.drop_duplicates(subset=conflict_keys, keep="last")
    staging = f"stg_{table_name}_{uuid.uuid4().hex[:8]}"
    sql = build_upsert_sql(f'"{schema}"."{table_name}"', f'"{staging}"', list(df.columns),
                           conflict_keys, update_columns)

    with engine.begin() as conn:
        conn.exec_driver_sql(
            f'CREATE TEMP TABLE "{staging}" (LIKE "{schema}"."{table_name}" INCLUDING DEFAULTS) ON COMMIT DROP'
        )
        df.to_sql(staging, con=conn, if_exists="append", index=False)
        conn.exec_driver_sql(sql)

    print(f"[GOLD] Upsert exitoso de {len(df)} registros en {schema}.{table_name}.")
    return len(df)
