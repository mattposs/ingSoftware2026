"""
Integración con PostgreSQL (se saltean si no hay TEST_DATABASE_URL).
En CI corren contra el servicio postgres del workflow, con el esquema de sql/.
"""

from datetime import UTC, datetime

import pandas as pd
import pytest
from sqlalchemy import text

from src import pipeline
from src.common import db
from src.common.state import WatermarkStore

pytestmark = pytest.mark.db


@pytest.fixture
def engine(database_url, tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("STORAGE_PATH", str(tmp_path / "storage"))
    eng = db.get_engine(database_url)
    with eng.begin() as conn:
        # DELETE y no TRUNCATE: el usuario del pipeline no tiene (ni necesita) permiso de TRUNCATE.
        for table in ("gold.dq_errors", "gold.dq_run_metrics", "gold.daily_field_metrics", "etl.watermarks"):
            conn.exec_driver_sql(f"DELETE FROM {table}")
    yield eng
    eng.dispose()


def test_watermark_ida_y_vuelta(engine):
    store = WatermarkStore(engine)
    assert store.get("agro", "x") is None
    w = datetime(2026, 10, 1, 12, tzinfo=UTC)
    store.set("agro", "x", w, "b1")
    assert store.get("agro", "x") == w


def test_upsert_es_idempotente(engine):
    pipeline.sync_fields(engine)
    with engine.connect() as conn:
        before = conn.execute(text("SELECT count(*) FROM gold.fields")).scalar()
    pipeline.sync_fields(engine)
    with engine.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM gold.fields")).scalar() == before == 8


def test_corrida_completa_con_simulador(engine):
    batch = pipeline.run_all(engine, sources=["iot_simulator"])
    assert batch

    with engine.connect() as conn:
        run = conn.execute(text("SELECT * FROM gold.dq_run_metrics WHERE _batch_id = :b"), {"b": batch}).mappings().one()
        gold_rows = conn.execute(text("SELECT count(*) FROM gold.daily_field_metrics")).scalar()
        errors = conn.execute(text("SELECT count(*) FROM gold.dq_errors WHERE _batch_id = :b"), {"b": batch}).scalar()

    assert run["status"] == "ok"
    assert run["run_start"] < run["run_end"]  # run_start es el inicio de la ingesta, no de Silver
    assert run["total"] == run["valid"] + run["warning"] + run["invalid"]
    assert gold_rows > 0 and errors > 0

    # El flujo por capas cierra: lo que entra a Bronze sale por Silver o por Quarantine.
    with engine.connect() as conn:
        layers = dict(conn.execute(
            text("SELECT layer, sum(rows) FROM gold.pipeline_layer_metrics WHERE _batch_id = :b GROUP BY layer"),
            {"b": batch}).all())
    assert layers["bronze"] == layers["silver"] + layers["quarantine"] == run["total"]
    assert layers["gold"] > 0

    # ETL paso a paso: hay trazas y las publicadas llegan hasta Gold (paso 5).
    with engine.connect() as conn:
        steps = pd.read_sql(text(
            "SELECT t.dq_status, s.step FROM gold.etl_trace t JOIN gold.etl_trace_steps s USING (trace_id) "
            "WHERE t._batch_id = :b"), conn, params={"b": batch})
    assert "VALID" in set(steps["dq_status"]) and "INVALID" in set(steps["dq_status"])
    assert 5 in set(steps.loc[steps["dq_status"] == "VALID", "step"])

    # Reprocesar el mismo lote deja la base igual (idempotencia).
    pipeline.reprocess(batch, engine)
    with engine.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM gold.daily_field_metrics")).scalar() == gold_rows
        assert conn.execute(text("SELECT count(*) FROM gold.dq_errors WHERE _batch_id = :b"),
                            {"b": batch}).scalar() == errors

    # Segunda corrida inmediata: no hay ventana nueva.
    assert pipeline.run_all(engine, sources=["iot_simulator"]) is None


def test_gold_no_tiene_registros_invalidos(engine):
    pipeline.run_all(engine, sources=["iot_simulator"])
    with engine.connect() as conn:
        df = pd.read_sql("SELECT * FROM gold.daily_field_metrics", conn)
    assert df["humedad_ambiental_promedio"].between(0, 100).all()
    assert (df["precipitacion_total"] >= 0).all()
    assert df["temperatura_promedio"].between(-40, 60).all()
