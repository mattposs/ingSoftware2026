"""
Monitoreo de corridas (alertas AL01 / AL02): migración de gold.dq_run_metrics, registro de corridas
exitosas y fallidas, y cálculo de last_measured_at. Los tests marcados db necesitan TEST_DATABASE_URL.
"""

from datetime import UTC, datetime

import pandas as pd
import pytest
from sqlalchemy import text

from src import config, pipeline
from src.common import db, lake, migrations
from src.config import PROJECT_ROOT, get_settings, load_pipeline
from src.metrics import quality

# --- sin base de datos -------------------------------------------------------------------------


def test_last_measured_at_es_el_maximo_timestamp_de_silver():
    silver = pd.DataFrame({"timestamp": pd.to_datetime(
        ["2026-10-20T10:00:00Z", "2026-10-20T10:45:00Z", "2026-10-20T10:15:00Z"], utc=True)})
    assert quality.last_measured_at(silver) == datetime(2026, 10, 20, 10, 45, tzinfo=UTC)


def test_last_measured_at_ignora_timestamps_vacios_y_lote_sin_silver():
    silver = pd.DataFrame({"timestamp": pd.to_datetime(["2026-10-20T10:00:00Z", None], utc=True)})
    assert quality.last_measured_at(silver) == datetime(2026, 10, 20, 10, 0, tzinfo=UTC)
    assert quality.last_measured_at(pd.DataFrame()) is None
    assert quality.last_measured_at(pd.DataFrame({"timestamp": pd.to_datetime([None], utc=True)})) is None


def test_falla_forzada_apagada_por_defecto(monkeypatch):
    monkeypatch.delenv(pipeline.FORCE_FAILURE_ENV, raising=False)
    assert not pipeline.force_failure_enabled()
    monkeypatch.setenv(pipeline.FORCE_FAILURE_ENV, "true")
    assert pipeline.force_failure_enabled()


def test_error_rate_se_puede_pisar_solo_por_variable(monkeypatch):
    base = load_pipeline("staging")["sources"]["iot_simulator"]["error_rate"]
    monkeypatch.setenv("PIPELINE_IOT_ERROR_RATE", "0.5")
    config._pipeline_for.cache_clear()
    try:
        assert load_pipeline("staging")["sources"]["iot_simulator"]["error_rate"] == 0.5
    finally:
        monkeypatch.delenv("PIPELINE_IOT_ERROR_RATE")
        config._pipeline_for.cache_clear()
    assert load_pipeline("staging")["sources"]["iot_simulator"]["error_rate"] == base


def test_sql_de_init_tiene_las_mismas_columnas_que_la_migracion():
    sql = (PROJECT_ROOT / "sql" / "schema" / "01_schema.sql").read_text(encoding="utf-8")
    for col in migrations.RUN_MONITORING_COLUMNS:
        assert f"ADD COLUMN IF NOT EXISTS {col} " in sql, col


# --- con PostgreSQL ----------------------------------------------------------------------------


@pytest.fixture
def engine(database_url, tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("STORAGE_PATH", str(tmp_path / "storage"))
    monkeypatch.delenv(pipeline.FORCE_FAILURE_ENV, raising=False)
    eng = db.get_engine(database_url)
    migrations.ensure_schema(eng)
    with eng.begin() as conn:
        for table in ("gold.dq_errors", "gold.dq_run_metrics", "gold.daily_field_metrics", "etl.watermarks"):
            conn.exec_driver_sql(f"DELETE FROM {table}")
    yield eng
    eng.dispose()


def _run(engine, batch_id):
    with engine.connect() as conn:
        return conn.execute(text("SELECT * FROM gold.dq_run_metrics WHERE _batch_id = :b"),
                            {"b": batch_id}).mappings().one()


@pytest.mark.db
def test_migracion_agrega_las_columnas_en_una_base_vieja(engine):
    # Simula una base creada antes del monitoreo: sin las columnas nuevas.
    with engine.begin() as conn:
        for col in migrations.RUN_MONITORING_COLUMNS:
            conn.exec_driver_sql(f"ALTER TABLE gold.dq_run_metrics DROP COLUMN IF EXISTS {col}")
    assert migrations.missing_columns(engine) == list(migrations.RUN_MONITORING_COLUMNS)

    assert migrations.ensure_schema(engine) == list(migrations.RUN_MONITORING_COLUMNS)
    assert migrations.missing_columns(engine) == []
    assert migrations.ensure_schema(engine) == []   # idempotente: la segunda vez no hace nada
    migrations.apply(engine)                         # y volver a correr el DDL no falla


@pytest.mark.db
def test_usuario_dashboard_puede_leer_las_columnas_nuevas(engine):
    with engine.connect() as conn:
        if not conn.execute(text("SELECT 1 FROM pg_roles WHERE rolname = 'dashboard'")).scalar():
            pytest.skip("la base de prueba no tiene el usuario dashboard (lo crea sql/99_app_users.sh)")
        for col in migrations.RUN_MONITORING_COLUMNS:
            assert conn.execute(text(
                "SELECT has_column_privilege('dashboard', 'gold.dq_run_metrics', :c, 'SELECT')"), {"c": col}).scalar()


@pytest.mark.db
def test_corrida_exitosa_queda_registrada_con_tiempos_y_frescura(engine):
    batch = pipeline.run_all(engine, sources=["iot_simulator"])
    run = _run(engine, batch)
    assert run["run_status"] == "SUCCESS" and run["status"] == "ok"
    assert run["started_at"] <= run["finished_at"]
    assert run["duration_seconds"] >= 0
    assert run["finished_at"] == run["run_end"]

    cfg, settings = load_pipeline(), get_settings()
    silver = lake.read_layer(settings.storage_path, "silver", cfg["domain"], cfg["entity"], batch)
    assert run["last_measured_at"] == silver["timestamp"].max().to_pydatetime()
    assert run["last_measured_at"] <= run["finished_at"]


@pytest.mark.db
def test_falla_forzada_queda_registrada_como_failed_y_se_relanza(engine, monkeypatch):
    monkeypatch.setenv(pipeline.FORCE_FAILURE_ENV, "true")
    with pytest.raises(RuntimeError, match="Falla forzada"):
        pipeline.run_all(engine, sources=["iot_simulator"])

    with engine.connect() as conn:
        runs = conn.execute(text("SELECT * FROM gold.dq_run_metrics")).mappings().all()
    assert len(runs) == 1
    run = runs[0]
    assert run["run_status"] == "FAILED" and run["status"] == "failed"
    assert run["started_at"] <= run["finished_at"] and run["duration_seconds"] >= 0
    assert run["total"] is None and run["last_measured_at"] is None


@pytest.mark.db
def test_falla_en_una_etapa_intermedia_queda_registrada_como_failed(engine, monkeypatch):
    def gold_roto(*args, **kwargs):
        raise ValueError("Gold no disponible")

    monkeypatch.setattr(pipeline, "run_gold", gold_roto)
    with pytest.raises(ValueError, match="Gold no disponible"):
        pipeline.run_all(engine, sources=["iot_simulator"])

    with engine.connect() as conn:
        run = conn.execute(text("SELECT * FROM gold.dq_run_metrics")).mappings().one()
    assert run["run_status"] == "FAILED"
    assert run["total"] is not None          # Silver llegó a correr: los contadores quedan
    assert run["finished_at"] is not None
