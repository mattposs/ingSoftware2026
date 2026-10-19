"""
gold.py
Indicadores diarios por campo y fuente (gold.daily_field_metrics).

Gold NO agrega solo el delta: para cada (fecha, campo, fuente) tocado por el lote se
recalcula el indicador con TODO Silver y se carga con upsert. Así, si un día llega en
varios lotes, el promedio y el conteo siguen siendo correctos (documento, sección 6.1).
"""

from datetime import UTC, datetime

import pandas as pd

from src.validation.engine import parse_timestamps

GOLD_KEYS = ["fecha", "field_id", "fuente"]


def _local_date(ts: pd.Series, tz: str) -> pd.Series:
    return ts.dt.tz_convert(tz).dt.date


def affected_keys(silver_batch: pd.DataFrame, tz: str) -> pd.DataFrame:
    if silver_batch.empty:
        return pd.DataFrame(columns=GOLD_KEYS)
    keys = pd.DataFrame(
        {
            "fecha": _local_date(silver_batch["timestamp"], tz),
            "field_id": silver_batch["field_id"],
            "fuente": silver_batch["source"],
        }
    )
    return keys.drop_duplicates().reset_index(drop=True)


def daily_metrics(
    silver_all: pd.DataFrame,
    quarantine_all: pd.DataFrame,
    keys: pd.DataFrame,
    tz: str,
    batch_id: str,
) -> pd.DataFrame:
    """Recalcula los indicadores de las claves pedidas a partir del histórico completo."""
    if keys.empty or silver_all.empty:
        return pd.DataFrame()

    s = silver_all.assign(fecha=_local_date(silver_all["timestamp"], tz), fuente=silver_all["source"])
    s = s.merge(keys, on=GOLD_KEYS, how="inner")

    gold = (
        s.groupby(GOLD_KEYS)
        .agg(
            temperatura_promedio=("temperature", "mean"),
            precipitacion_total=("precipitation", "sum"),
            humedad_suelo_promedio=("soil_moisture", "mean"),
            humedad_ambiental_promedio=("humidity", "mean"),
            cantidad_mediciones=("timestamp", "size"),
            validos=("dq_status", lambda x: int((x == "VALID").sum())),
        )
        .reset_index()
    )

    # Rechazados atribuibles a la misma clave (los que no tienen fecha o campo no se pueden asignar).
    rejected = pd.DataFrame(columns=[*GOLD_KEYS, "rechazados"])
    if not quarantine_all.empty:
        q = quarantine_all.assign(_ts=parse_timestamps(quarantine_all["timestamp"]))
        q = q[q["_ts"].notna() & q["field_id"].notna()]
        if not q.empty:
            q = q.assign(fecha=_local_date(q["_ts"], tz), fuente=q["source"])
            rejected = q.groupby(GOLD_KEYS).size().rename("rechazados").reset_index()

    gold = gold.merge(rejected, on=GOLD_KEYS, how="left")
    rech = gold["rechazados"].fillna(0)
    # Mismo score estricto que la corrida (D2): solo los VALID cuentan como limpios; los WARNING están en
    # cantidad_mediciones (se publican) pero no suman al porcentaje. Total = publicados + rechazados atribuibles.
    gold["porcentaje_calidad"] = (gold["validos"] / (gold["cantidad_mediciones"] + rech) * 100).round(2)
    gold = gold.drop(columns=["rechazados", "validos"])

    for col in ["temperatura_promedio", "humedad_suelo_promedio", "humedad_ambiental_promedio"]:
        gold[col] = gold[col].round(3)
    gold["precipitacion_total"] = gold["precipitacion_total"].round(2)
    gold["cantidad_mediciones"] = gold["cantidad_mediciones"].astype(int)
    gold["_batch_id"] = batch_id
    gold["_updated_at"] = pd.Timestamp(datetime.now(UTC))
    return gold
