"""
open_meteo.py
Conector a Open-Meteo Historical Weather API (datos horarios, UTC).
La API publica con unos días de retraso: la ventana termina en hoy - lag_days.
"""

import time
from datetime import datetime, timedelta

import pandas as pd
import requests

from src.ingestion.schema import to_bronze_frame

SOURCE = "open_meteo"

# variable del pipeline -> variable horaria de Open-Meteo
HOURLY = {
    "temperature": "temperature_2m",
    "humidity": "relative_humidity_2m",
    "soil_moisture": "soil_moisture_0_to_7cm",
    "precipitation": "precipitation",
    "wind_speed": "wind_speed_10m",
}


def window(watermark: datetime | None, now: datetime, cfg: dict) -> tuple[datetime, datetime] | None:
    """Ventana (inicio exclusivo, fin inclusivo) en horas UTC, o None si no hay datos nuevos."""
    last_day = (now - timedelta(days=cfg["lag_days"])).replace(hour=0, minute=0, second=0, microsecond=0)
    end = last_day + timedelta(hours=23)
    start = watermark or (end - timedelta(days=cfg["initial_days"]))
    return (start, end) if end > start else None


def _get(url: str, params: dict, cfg: dict) -> dict:
    for attempt in range(1, cfg["retries"] + 1):
        try:
            resp = requests.get(url, params=params, timeout=cfg["timeout_seconds"])
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as exc:
            if attempt == cfg["retries"]:
                raise
            wait = 2**attempt
            print(f"[OPEN-METEO] Error ({exc}); reintento {attempt} en {wait}s")
            time.sleep(wait)
    raise RuntimeError("unreachable")


def fetch(fields: list[dict], start: datetime, end: datetime, cfg: dict) -> pd.DataFrame:
    """Descarga la ventana (start, end] para cada campo y la devuelve con el esquema de Bronze."""
    records = []
    for field in fields:
        data = _get(
            cfg["base_url"],
            {
                "latitude": field["latitude"],
                "longitude": field["longitude"],
                "start_date": start.date().isoformat(),
                "end_date": end.date().isoformat(),
                "hourly": ",".join(HOURLY.values()),
                "timezone": "GMT",
            },
            cfg,
        )
        hourly, units = data.get("hourly", {}), data.get("hourly_units", {})
        for i, ts in enumerate(hourly.get("time", [])):
            rec = {
                "timestamp": ts,  # "2026-09-20T13:00" (UTC, se conserva crudo)
                "field_id": field["field_id"],
                "latitude": field["latitude"],
                "longitude": field["longitude"],
                "source": SOURCE,
            }
            for var, om in HOURLY.items():
                rec[var] = hourly.get(om, [None] * (i + 1))[i]
                rec[f"{var}_unit"] = units.get(om)
            records.append(rec)

    df = to_bronze_frame(records)
    ts = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")
    in_window = (ts > pd.Timestamp(start)) & (ts <= pd.Timestamp(end))
    return df[in_window | ts.isna()].reset_index(drop=True)
