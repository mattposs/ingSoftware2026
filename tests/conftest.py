import os
from datetime import UTC, datetime

import pandas as pd
import pytest

from src.config import load_fields, load_rules
from src.ingestion.iot_simulator import UNITS
from src.ingestion.schema import to_bronze_frame

NOW = datetime(2026, 10, 15, 12, 0, tzinfo=UTC)


@pytest.fixture
def rules():
    return load_rules()


@pytest.fixture
def field_ids():
    return {f["field_id"] for f in load_fields()}


def reading(ts="2026-10-15T10:00:00Z", field_id="C01", source="iot_simulator", **overrides) -> dict:
    """Una lectura válida; los kwargs pisan cualquier columna."""
    rec = {
        "timestamp": ts,
        "field_id": field_id,
        "latitude": -34.05,
        "longitude": -60.55,
        "temperature": 20.0,
        "humidity": 60.0,
        "soil_moisture": 0.30,
        "precipitation": 0.0,
        "wind_speed": 10.0,
        "source": source,
        **{f"{v}_unit": u for v, u in UNITS.items()},
        "_batch_id": "test-batch",
    }
    rec.update(overrides)
    return rec


def series(n=4, start="2026-10-15T10:00:00Z", freq_min=15, field_id="C01", **overrides) -> list[dict]:
    """n lecturas consecutivas válidas del mismo campo."""
    times = pd.date_range(start, periods=n, freq=f"{freq_min}min")
    return [reading(t.strftime("%Y-%m-%dT%H:%M:%SZ"), field_id, **overrides) for t in times]


def bronze(records: list[dict]) -> pd.DataFrame:
    df = to_bronze_frame(records)
    df["_batch_id"] = [r.get("_batch_id", "test-batch") for r in records]
    return df


@pytest.fixture
def database_url():
    url = os.getenv("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL no definida (tests de integración con PostgreSQL)")
    return url
