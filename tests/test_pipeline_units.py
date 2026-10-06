"""Tests de las piezas del pipeline que no necesitan base de datos."""

from datetime import UTC, datetime, timedelta

import pandas as pd
import pytest

from src.common import lake
from src.common.db import build_upsert_sql
from src.config import load_fields, load_pipeline
from src.ingestion import iot_simulator, open_meteo
from src.metrics.quality import errors_frame
from src.transformation import gold
from src.validation import check_rules
from src.validation.engine import validate
from tests.conftest import NOW, bronze, reading, series

TZ = "America/Argentina/Buenos_Aires"


# ---- Simulador: meta SMART "detectar al menos el 95% de los errores inyectados" ----------

@pytest.mark.parametrize("seed", [1, 2, 3])
def test_reglas_detectan_al_menos_95_por_ciento_de_errores_inyectados(rules, field_ids, seed):
    cfg = dict(load_pipeline()["sources"]["iot_simulator"], seed=seed)
    df = iot_simulator.generate(load_fields(), NOW - timedelta(hours=24), NOW, cfg, now=NOW)
    r = validate(df, rules, field_ids, now=NOW)

    injected = int(df["_sim_injected_error"].notna().sum())
    missed = r.silver[r.silver["_sim_injected_error"].notna() & (r.silver["dq_status"] == "VALID")]
    assert injected > 0
    assert 1 - len(missed) / injected >= 0.95


def test_simulador_genera_una_lectura_cada_15_min_por_campo():
    cfg = dict(load_pipeline()["sources"]["iot_simulator"], seed=1, error_rate=0)
    df = iot_simulator.generate(load_fields(), NOW - timedelta(hours=24), NOW, cfg)
    assert len(df) == 6 * 96  # 576 registros por día (documento, sección 2.1)
    assert df["_sim_injected_error"].isna().all()


def test_ventana_simulador_respeta_watermark_y_tope():
    cfg = load_pipeline()["sources"]["iot_simulator"]
    now = datetime(2026, 10, 15, 12, 7, tzinfo=UTC)
    start, end = iot_simulator.window(None, now, cfg)
    assert end == datetime(2026, 10, 15, 12, 0, tzinfo=UTC)
    assert end - start == timedelta(hours=cfg["initial_hours"])
    assert iot_simulator.window(end, now, cfg) is None
    old = end - timedelta(days=30)
    assert iot_simulator.window(old, now, cfg)[0] == end - timedelta(hours=cfg["max_hours_per_run"])


def test_ventana_open_meteo_respeta_retraso_de_la_api():
    cfg = load_pipeline()["sources"]["open_meteo"]
    start, end = open_meteo.window(None, NOW, cfg)
    assert end == datetime(2026, 10, 10, 23, 0, tzinfo=UTC)
    assert open_meteo.window(end, NOW, cfg) is None


# ---- Lake ---------------------------------------------------------------------------

def test_lake_lote_vacio_no_escribe_ni_falla(tmp_path):
    assert lake.write_parquet(pd.DataFrame(), tmp_path, "silver", "agro", "m", "b1") is None


def test_lake_bronze_es_append_only(tmp_path):
    df = pd.DataFrame({"a": [1]})
    path = lake.write_parquet(df, tmp_path, "bronze", "agro", "iot", "b1")
    assert path.name == "batch_b1.parquet"
    with pytest.raises(FileExistsError):
        lake.write_parquet(df, tmp_path, "bronze", "agro", "iot", "b1")
    with pytest.raises(ValueError):
        lake.write_parquet(df, tmp_path, "bronze", "agro", "iot", "b1", replace=True)


def test_lake_silver_se_puede_regenerar(tmp_path):
    lake.write_parquet(pd.DataFrame({"a": [1, 2]}), tmp_path, "silver", "agro", "m", "b1")
    lake.write_parquet(pd.DataFrame({"a": [3]}), tmp_path, "silver", "agro", "m", "b1", replace=True)
    assert lake.read_layer(tmp_path, "silver", "agro", "m")["a"].tolist() == [3]


def test_lake_linaje_obligatorio():
    out = lake.enrich_with_lineage(pd.DataFrame({"a": [1]}), "iot_simulator", "b1")
    assert {"_batch_id", "_ingested_at", "_source_system"} <= set(out.columns)


# ---- Gold ---------------------------------------------------------------------------

def _silver(records, rules, field_ids, batch):
    recs = [dict(r, _batch_id=batch) for r in records]
    return validate(bronze(recs), rules, field_ids, now=NOW)


def test_gold_recalcula_el_dia_completo_con_varios_lotes(rules, field_ids):
    a = _silver(series(2, start="2026-10-15T10:00:00Z", temperature=10.0), rules, field_ids, "b1")
    b = _silver(series(2, start="2026-10-15T10:30:00Z", temperature=20.0), rules, field_ids, "b2")
    silver_all = pd.concat([a.silver, b.silver], ignore_index=True)

    keys = gold.affected_keys(b.silver, TZ)
    out = gold.daily_metrics(silver_all, pd.DataFrame(), keys, TZ, "b2")
    assert len(out) == 1
    assert out.loc[0, "cantidad_mediciones"] == 4
    assert out.loc[0, "temperatura_promedio"] == 15.0  # no 20.0 (solo el delta)


def test_gold_no_contiene_registros_invalidos(rules, field_ids):
    r = _silver([reading(), reading(ts="2026-10-15T10:15:00Z", temperature=99.0)], rules, field_ids, "b1")
    out = gold.daily_metrics(r.silver, r.quarantine, gold.affected_keys(r.silver, TZ), TZ, "b1")
    assert out.loc[0, "cantidad_mediciones"] == 1
    assert out.loc[0, "temperatura_promedio"] == 20.0
    assert out.loc[0, "porcentaje_calidad"] == 50.0


def test_gold_usa_la_fecha_local_del_negocio(rules, field_ids):
    # 02:00 UTC del 15/10 es 23:00 del 14/10 en Argentina.
    r = _silver([reading(ts="2026-10-15T02:00:00Z")], rules, field_ids, "b1")
    keys = gold.affected_keys(r.silver, TZ)
    assert str(keys.loc[0, "fecha"]) == "2026-10-14"


# ---- Métricas y SQL ------------------------------------------------------------------

def test_dq_score_cuenta_valid_y_warning(rules, field_ids):
    r = validate(bronze([reading(), reading(ts="2026-10-15T10:15:00Z", temperature=46),
                         reading(ts="2026-10-15T10:30:00Z", humidity=200)]), rules, field_ids, now=NOW)
    assert (r.valid, r.warning, r.invalid) == (1, 1, 1)
    assert r.dq_score == pytest.approx(66.67)


def test_errores_tienen_el_detalle_de_rf08(rules, field_ids):
    r = validate(bronze([reading(humidity=200)]), rules, field_ids, now=NOW)
    e = errors_frame(r, rules, "b1")
    row = e.iloc[0]
    assert (row.rule_id, row.variable, row.action, row.severidad, row.field_id) == (
        "DQ07", "humidity", "REJECT", "Alta", "C01")
    assert row.measured_at == pd.Timestamp("2026-10-15T10:00:00Z")


def test_upsert_sql_actualiza_columnas_no_clave():
    sql = build_upsert_sql("t", "s", ["k", "v"], ["k"])
    assert 'ON CONFLICT ("k") DO UPDATE SET "v" = EXCLUDED."v"' in sql


def test_upsert_sql_sin_columnas_para_actualizar_usa_do_nothing():
    assert build_upsert_sql("t", "s", ["k"], ["k"]).endswith("DO NOTHING;")


def test_configuracion_de_reglas_valida():
    assert check_rules.check() == []
