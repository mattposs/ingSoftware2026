"""
iot_simulator.py
Simulador de las estaciones IoT: una estación por campo (8 campos, ver config/fields.yaml), una lectura
cada 15 minutos con 5 variables. No simula sensores individuales (24-32 por campo); ver docs/revision/paso-1.md.
Inyecta errores realistas a una tasa configurable (error_rate en config/pipeline.yaml, hoy ~14%) y deja
registrado en `_sim_injected_error` qué se inyectó, para medir la detección de las reglas.
"""

from datetime import datetime, timedelta

import numpy as np
import pandas as pd

from src.ingestion.schema import to_bronze_frame

SOURCE = "iot_simulator"
UNITS = {"temperature": "°C", "humidity": "%", "soil_moisture": "m³/m³", "precipitation": "mm", "wind_speed": "km/h"}

# Cada error se diseñó para que lo detecte una regla concreta.
ERROR_TYPES = [
    "null_timestamp",          # DQ01
    "null_field",              # DQ02
    "bad_timestamp",           # DQ03
    "future_timestamp",        # DQ03
    "unknown_field",           # DQ04
    "duplicate",               # DQ05
    "wrong_unit",              # DQ06
    "humidity_out_of_range",   # DQ07
    "negative_precipitation",  # DQ08
    "temperature_extreme",     # DQ09
    "soil_out_of_range",       # DQ10
    "gap",                     # DQ11 (se marca la lectura posterior al hueco)
    "spike",                   # DQ12
]
NEEDS_PREVIOUS = {"gap", "spike"}


def window(watermark: datetime | None, now: datetime, cfg: dict) -> tuple[datetime, datetime] | None:
    step = timedelta(minutes=cfg["frequency_minutes"])
    end = now - (now - now.replace(hour=0, minute=0, second=0, microsecond=0)) % step
    start = watermark or (end - timedelta(hours=cfg["initial_hours"]))
    start = max(start, end - timedelta(hours=cfg["max_hours_per_run"]))
    return (start, end) if end > start else None


def _clean_readings(fields: list[dict], start: datetime, end: datetime, freq: int, rng) -> pd.DataFrame:
    times = pd.date_range(pd.Timestamp(start).tz_convert("UTC"), pd.Timestamp(end).tz_convert("UTC"),
                          freq=f"{freq}min", inclusive="right")
    rows = []
    hours = times.hour + times.minute / 60
    for i, field in enumerate(fields):
        base = 15 + i * 0.8
        temp = base + 6 * np.sin(2 * np.pi * (hours - 12) / 24) + rng.normal(0, 0.2, len(times))
        hum = np.clip(70 - 2.5 * (temp - base) + rng.normal(0, 1, len(times)), 15, 100)
        soil = np.clip(0.28 + i * 0.01 + np.cumsum(rng.normal(0, 0.001, len(times))), 0.05, 0.5)
        rain = np.where(rng.random(len(times)) < 0.02, rng.exponential(0.8, len(times)), 0.0)
        wind = np.abs(12 + 4 * np.sin(2 * np.pi * hours / 24) + rng.normal(0, 1.5, len(times)))
        for t, te, hu, so, ra, wi in zip(times, temp, hum, soil, rain, wind, strict=True):
            rows.append(
                {
                    "timestamp": t.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "field_id": field["field_id"],
                    "latitude": field["latitude"],
                    "longitude": field["longitude"],
                    "temperature": round(te, 2),
                    "humidity": round(hu, 1),
                    "soil_moisture": round(so, 3),
                    "precipitation": round(ra, 1),
                    "wind_speed": round(wi, 1),
                    "source": SOURCE,
                    **{f"{v}_unit": u for v, u in UNITS.items()},
                }
            )
    return pd.DataFrame(rows)


def generate(fields: list[dict], start: datetime, end: datetime, cfg: dict, now: datetime | None = None) -> pd.DataFrame:
    """Genera las lecturas de la ventana (start, end] con errores inyectados."""
    rng = np.random.default_rng(cfg.get("seed"))
    now = now or end
    df = _clean_readings(fields, start, end, cfg["frequency_minutes"], rng)
    df["_sim_injected_error"] = None
    if df.empty:
        return to_bronze_frame(df)

    n_errors = int(round(cfg["error_rate"] * len(df)))
    chosen = rng.choice(len(df), size=min(n_errors, len(df)), replace=False)
    used, drop, extra = set(int(c) for c in chosen), set(), []

    for idx in sorted(int(c) for c in chosen):
        kind = str(rng.choice(ERROR_TYPES))
        if kind in NEEDS_PREVIOUS:
            prev = idx - 1
            ok = prev >= 0 and df.at[prev, "field_id"] == df.at[idx, "field_id"] and prev not in drop
            if kind == "gap":
                # se borra la lectura anterior; hace falta otra antes para que exista el hueco
                ok = ok and prev not in used and prev - 1 >= 0 and df.at[prev - 1, "field_id"] == df.at[idx, "field_id"]
            if not ok:
                kind = "humidity_out_of_range"
        _inject(df, idx, kind, now, drop, extra, used)

    out = pd.concat([df.drop(index=list(drop)), pd.DataFrame(extra)], ignore_index=True)
    return to_bronze_frame(out)


def _inject(df: pd.DataFrame, idx: int, kind: str, now: datetime, drop: set, extra: list, used: set) -> None:
    if kind == "duplicate":
        copy = df.loc[idx].to_dict()
        copy["_sim_injected_error"] = kind
        extra.append(copy)
        return
    df.at[idx, "_sim_injected_error"] = kind
    if kind == "null_timestamp":
        df.at[idx, "timestamp"] = None
    elif kind == "null_field":
        df.at[idx, "field_id"] = None
    elif kind == "bad_timestamp":
        df.at[idx, "timestamp"] = "2026-13-45 25:61"
    elif kind == "future_timestamp":
        df.at[idx, "timestamp"] = (now + timedelta(days=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
    elif kind == "unknown_field":
        df.at[idx, "field_id"] = "LIT-99"
    elif kind == "wrong_unit":
        df.at[idx, "temperature"] = round(df.at[idx, "temperature"] * 9 / 5 + 32, 2)
        df.at[idx, "temperature_unit"] = "°F"
    elif kind == "humidity_out_of_range":
        df.at[idx, "humidity"] = 135.0
    elif kind == "negative_precipitation":
        df.at[idx, "precipitation"] = -3.0
    elif kind == "temperature_extreme":
        df.at[idx, "temperature"] = 75.0
    elif kind == "soil_out_of_range":
        df.at[idx, "soil_moisture"] = 1.35
    elif kind == "gap":
        drop.add(idx - 1)
        used.add(idx - 1)
    elif kind == "spike":
        df.at[idx, "temperature"] = round(df.at[idx, "temperature"] + 15, 2)
