# Copiado de la skill data-governance (.agents/skills/data-governance/templates/schema_extractor.py).
"""
schema_extractor.py
Extrae automáticamente metadatos técnicos de columnas a partir de DataFrames
de Pandas o archivos Parquet.

Nota: `nullable` y `null_percentage` describen lo OBSERVADO en la muestra, no una
restricción del esquema. Un dataset ya validado (Silver) puede no tener nulos
aunque la columna los admita: revisar `nullable` a mano cuando corresponda.
"""

from typing import Any

import pandas as pd


def extract_column_metadata(df: pd.DataFrame) -> list[dict[str, Any]]:
    """
    Inspecciona cada columna de un DataFrame y genera su ficha técnica:
    nombre, tipo de dato, si se observaron nulos, porcentaje de nulos y un valor de ejemplo.
    """
    columns_meta = []
    total_rows = len(df)

    for col in df.columns:
        series = df[col]
        null_count = int(series.isna().sum())
        first_valid = series.first_valid_index()
        sample = str(series.loc[first_valid]) if first_valid is not None else None

        columns_meta.append({
            "name": str(col),
            "data_type": str(series.dtype),
            "nullable": null_count > 0,
            "null_percentage": round((null_count / total_rows * 100), 2) if total_rows > 0 else 0.0,
            "sample_value": sample
        })

    return columns_meta


def extract_from_parquet(parquet_path: str, sample_rows: int | None = None) -> list[dict[str, Any]]:
    """Carga un Parquet (o sus primeras `sample_rows` filas) y extrae sus metadatos de columnas."""
    df = pd.read_parquet(parquet_path)
    if sample_rows:
        df = df.head(sample_rows)
    return extract_column_metadata(df)
