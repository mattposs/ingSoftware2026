"""
Integración con PostgreSQL (se saltean si no hay TEST_DATABASE_URL).
En CI corren contra el servicio postgres del workflow, con el esquema de sql/.
"""

from datetime import UTC, datetime

import pandas as pd
import pytest
from sqlalchemy import text

from src import pipeline
from src.common import db, lake
from src.common.state import WatermarkStore
from src.config import get_settings, load_pipeline
from src.transformation import gold
from src.validation.engine import parse_timestamps
from tests.conftest import NOW, bronze, reading

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
    # D2: score estricto (solo VALID) y % utilizable (VALID + WARNING), ambos guardados.
    assert float(run["dq_score"]) == pytest.approx(run["valid"] / run["total"] * 100, abs=0.01)
    assert float(run["pct_utilizable"]) == pytest.approx((run["valid"] + run["warning"]) / run["total"] * 100, abs=0.01)
    assert run["pct_utilizable"] >= run["dq_score"]
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
    cfg = load_pipeline()
    settings = get_settings()
    with engine.connect() as conn:
        df = pd.read_sql("SELECT * FROM gold.daily_field_metrics", conn)
        known_fields = set(pd.read_sql("SELECT field_id FROM gold.fields", conn)["field_id"])
    assert not df.empty

    # Valores dentro de los rangos físicos.
    assert df["humedad_ambiental_promedio"].between(0, 100).all()
    assert (df["precipitacion_total"] >= 0).all()
    assert df["temperatura_promedio"].between(-40, 60).all()

    # Todo field_id de Gold existe en gold.fields.
    assert set(df["field_id"]) <= known_fields

    # (fecha, field_id, fuente) es única.
    assert not df.duplicated(subset=gold.GOLD_KEYS).any()

    # Ningún registro de Quarantine llegó a Silver, y Gold cuenta exactamente lo que hay en Silver.
    # Se excluyen los rechazados solo por DQ05: un duplicado comparte la clave de su original (que sí es válido).
    domain, entity, tz = cfg["domain"], cfg["entity"], cfg["business_timezone"]
    silver = lake.read_layer(settings.storage_path, "silver", domain, entity)
    quarantine = lake.read_layer(settings.storage_path, "quarantine", domain, entity)
    assert not silver.empty and not quarantine.empty
    rejected = quarantine[quarantine["_rejection_reasons"] != "DQ05"]
    rejected = rejected.assign(timestamp=parse_timestamps(rejected["timestamp"]))
    rejected = rejected[rejected["timestamp"].notna() & rejected["field_id"].notna()]
    identity = ["source", "field_id", "timestamp"]
    assert silver.merge(rejected[identity].drop_duplicates(), on=identity).empty

    expected = (silver.assign(fecha=gold._local_date(silver["timestamp"], tz), fuente=silver["source"])
                .groupby(gold.GOLD_KEYS).size().rename("en_silver").reset_index())
    check = df.merge(expected, on=gold.GOLD_KEYS, how="left")
    assert (check["cantidad_mediciones"] == check["en_silver"]).all()


def test_precipitacion_duplicada_no_se_suma_y_el_segundo_registro_va_a_quarantine(engine):
    cfg, settings = load_pipeline(), get_settings()
    batch = "lote-con-duplicado"
    original = reading(precipitation=5.0, _batch_id=batch)
    df = lake.enrich_with_lineage(bronze([original, dict(original)]).drop(columns="_batch_id"),
                                  source_system="iot_simulator", batch_id=batch)
    lake.write_parquet(df, settings.storage_path, "bronze", cfg["domain"], "iot_simulator", batch)

    pipeline.run_silver(engine, batch, now=NOW)
    pipeline.run_gold(engine, batch)

    with engine.connect() as conn:
        daily = pd.read_sql("SELECT * FROM gold.daily_field_metrics", conn)
        errors = pd.read_sql(text("SELECT rule_id, action FROM gold.dq_errors WHERE _batch_id = :b"), conn,
                             params={"b": batch})
    assert len(daily) == 1
    assert float(daily.loc[0, "precipitacion_total"]) == 5.0       # no 10.0: el duplicado no se suma
    assert daily.loc[0, "cantidad_mediciones"] == 1
    assert float(daily.loc[0, "porcentaje_calidad"]) == 50.0      # 1 VALID de 2 (el duplicado cuenta como rechazado)

    silver = lake.read_layer(settings.storage_path, "silver", cfg["domain"], cfg["entity"], batch)
    quarantine = lake.read_layer(settings.storage_path, "quarantine", cfg["domain"], cfg["entity"], batch)
    assert len(silver) == 1
    assert len(quarantine) == 1
    assert quarantine.loc[0, "_rejection_reasons"] == "DQ05"
    assert quarantine.loc[0, "precipitation"] == 5.0
    assert list(zip(errors["rule_id"], errors["action"], strict=True)) == [("DQ05", "REJECT")]
