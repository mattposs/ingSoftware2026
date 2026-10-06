"""Esquema común de Bronze: ambas fuentes entregan exactamente estas columnas (RF01, RF02)."""

import pandas as pd

from src.config import MEASUREMENT_VARIABLES

BRONZE_COLUMNS = [
    "timestamp",  # texto crudo tal como llegó (se tipa recién en Silver)
    "field_id",
    "latitude",
    "longitude",
    *[c for v in MEASUREMENT_VARIABLES for c in (v, f"{v}_unit")],
    "source",
    "_sim_injected_error",  # solo simulador: error inyectado, para medir la detección (meta SMART 95%)
]


def to_bronze_frame(records: list[dict] | pd.DataFrame) -> pd.DataFrame:
    df = pd.DataFrame(records)
    df = df.reindex(columns=BRONZE_COLUMNS)
    df["timestamp"] = df["timestamp"].astype("string")
    df["field_id"] = df["field_id"].astype("string")
    df["_sim_injected_error"] = df["_sim_injected_error"].astype("string")
    for v in MEASUREMENT_VARIABLES:
        df[v] = pd.to_numeric(df[v], errors="coerce").astype("float64")
        df[f"{v}_unit"] = df[f"{v}_unit"].astype("string")
    return df
