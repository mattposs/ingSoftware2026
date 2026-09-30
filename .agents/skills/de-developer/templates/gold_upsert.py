"""
gold_upsert.py
Módulo genérico para ejecución atómica de operaciones UPSERT (INSERT ... ON CONFLICT DO UPDATE)
en PostgreSQL utilizando tablas temporales de staging y SQLAlchemy.
"""

from sqlalchemy import Engine
import pandas as pd


def upsert_to_postgres(
    df: pd.DataFrame,
    table_name: str,
    schema: str,
    engine: Engine,
    conflict_keys: list[str],
    update_columns: list[str] | None = None
):
    """
    Realiza un Upsert atómico e idempotente en PostgreSQL desde un DataFrame de Pandas.

    Estrategia:
    1. Carga el lote a una tabla temporal de staging dentro de una transacción.
    2. Ejecuta un INSERT INTO target_table SELECT ... FROM staging ON CONFLICT DO UPDATE.
    3. Dropea la tabla de staging.

    Args:
        df: DataFrame de Pandas con los registros agregados o modelados (delta del lote).
        table_name: Nombre de la tabla destino en PostgreSQL.
        schema: Esquema de base de datos (ej. 'gold' o 'public').
        engine: Instancia de SQLAlchemy Engine conectada a PostgreSQL.
        conflict_keys: Lista de nombres de columnas que forman la Primary Key o Unique Constraint.
        update_columns: Lista explícita de columnas a actualizar ante conflicto.
                        Si es None, se actualizan todas excepto las claves en conflict_keys.
    """
    if df.empty:
        print(f"[GOLD] DataFrame vacío. Se omite carga en {schema}.{table_name}.")
        return

    full_target_table = f'"{schema}"."{table_name}"'
    staging_table = f"staging_{table_name}_{int(pd.Timestamp.now().timestamp())}"

    all_columns = list(df.columns)
    if update_columns is None:
        update_columns = [col for col in all_columns if col not in conflict_keys]

    cols_quoted = [f'"{c}"' for c in all_columns]
    conflict_quoted = [f'"{c}"' for c in conflict_keys]
    update_assignments = [f'"{c}" = EXCLUDED."{c}"' for c in update_columns]

    cols_sql = ", ".join(cols_quoted)
    conflict_sql = ", ".join(conflict_quoted)
    update_sql = ", ".join(update_assignments)

    with engine.begin() as conn:
        # 1. Volcar datos a staging
        df.to_sql(staging_table, con=conn, schema=schema, if_exists="replace", index=False)

        # 2. Ejecutar Upsert atómico
        upsert_query = f"""
            INSERT INTO {full_target_table} ({cols_sql})
            SELECT {cols_sql} FROM "{schema}"."{staging_table}"
            ON CONFLICT ({conflict_sql})
            DO UPDATE SET {update_sql};
        """
        conn.exec_driver_sql(upsert_query)

        # 3. Eliminar staging
        conn.exec_driver_sql(f'DROP TABLE IF EXISTS "{schema}"."{staging_table}";')

    print(f"[GOLD] Upsert exitoso de {len(df)} registros en {full_target_table}.")
