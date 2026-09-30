"""
schema_extractor.py
Extrae automáticamente metadatos técnicos de columnas a partir de DataFrames
de Pandas o archivos Parquet.
"""

from typing import Any
import pandas as pd


def extract_column_metadata(df: pd.DataFrame) -> list[dict[str, Any]]:
    """
    Inspecciona cada columna de un DataFrame y genera su ficha técnica:
    nombre, tipo de dato, si permite nulos, porcentaje de nulos y un valor de ejemplo.
    """
    columns_meta = []
    total_rows = len(df)

    for col in df.columns:
        series = df[col]
        null_count = int(series.isnull().sum())
        non_null_samples = series.dropna().tolist()
        sample = str(non_null_samples[0]) if non_null_samples else None

        columns_meta.append({
            "name": str(col),
            "data_type": str(series.dtype),
            "nullable": null_count > 0,
            "null_percentage": round((null_count / total_rows * 100), 2) if total_rows > 0 else 0.0,
            "sample_value": sample
        })

    return columns_meta


def extract_from_parquet(parquet_path: str) -> list[dict[str, Any]]:
    """Carga una muestra de un Parquet y extrae sus metadatos de columnas."""
    df = pd.read_parquet(parquet_path)
    return extract_column_metadata(df)
