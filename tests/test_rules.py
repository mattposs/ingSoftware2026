"""Un test (o más) por regla DQ01–DQ12 — meta SMART: al menos 12 tests de reglas."""

import pandas as pd
import pytest

from src.validation.engine import REJECT, WARNING, validate
from tests.conftest import NOW, bronze, reading, series


def run(records, rules, field_ids, context=None):
    return validate(bronze(records), rules, field_ids, context=context, now=NOW)


def hits(result, rule_id, action=None):
    f = result.findings[result.findings["rule_id"] == rule_id]
    return f if action is None else f[f["action"] == action]


def test_registro_valido_no_genera_hallazgos(rules, field_ids):
    r = run(series(4), rules, field_ids)
    assert (r.valid, r.warning, r.invalid) == (4, 0, 0)
    assert r.findings.empty


@pytest.mark.parametrize("ts", [None, "", "   "])
def test_dq01_timestamp_obligatorio(rules, field_ids, ts):
    r = run([reading(ts=ts)], rules, field_ids)
    assert len(hits(r, "DQ01", REJECT)) == 1
    assert r.invalid == 1


@pytest.mark.parametrize("field_id", [None, ""])
def test_dq02_field_id_obligatorio(rules, field_ids, field_id):
    r = run([reading(field_id=field_id)], rules, field_ids)
    assert len(hits(r, "DQ02", REJECT)) == 1
    assert "DQ04" not in set(r.findings["rule_id"])  # un campo vacío no es "inexistente"


@pytest.mark.parametrize(
    "ts",
    ["2026-13-45 25:61", "ayer", "2026-10-17T12:00:00Z", "1999-12-31T23:00:00Z"],
    ids=["formato", "texto", "futuro", "antes_2000"],
)
def test_dq03_timestamp_invalido(rules, field_ids, ts):
    r = run([reading(ts=ts)], rules, field_ids)
    assert len(hits(r, "DQ03", REJECT)) == 1


def test_dq03_tolera_10_minutos_de_reloj(rules, field_ids):
    r = run([reading(ts="2026-10-15T12:09:00Z")], rules, field_ids)
    assert hits(r, "DQ03").empty


def test_dq04_campo_inexistente(rules, field_ids):
    r = run([reading(field_id="LIT-99")], rules, field_ids)
    assert len(hits(r, "DQ04", REJECT)) == 1


def test_dq05_duplicado_en_el_lote_conserva_el_primero(rules, field_ids):
    first = reading(temperature=20.0)
    copy = reading(temperature=21.0)
    r = run([first, copy], rules, field_ids)
    assert r.invalid == 1
    assert r.silver["temperature"].tolist() == [20.0]
    assert hits(r, "DQ05", REJECT)["_row"].tolist() == [1]


def test_dq05_distinta_fuente_no_es_duplicado(rules, field_ids):
    r = run([reading(), reading(source="open_meteo")], rules, field_ids)
    assert hits(r, "DQ05").empty


def test_dq05_duplicado_contra_lotes_anteriores(rules, field_ids):
    context = pd.DataFrame(
        [{"source": "iot_simulator", "field_id": "LIT-01", "timestamp": pd.Timestamp("2026-10-15T10:00:00Z")}]
    )
    r = run([reading()], rules, field_ids, context=context)
    assert len(hits(r, "DQ05", REJECT)) == 1


def test_dq06_unidad_inesperada(rules, field_ids):
    r = run([reading(temperature=68.0, temperature_unit="°F")], rules, field_ids)
    f = hits(r, "DQ06", REJECT)
    assert f["variable"].tolist() == ["temperature"]
    assert hits(r, "DQ09").empty  # con la unidad mal no tiene sentido evaluar el rango


def test_dq06_unidad_faltante_con_valor(rules, field_ids):
    r = run([reading(wind_speed_unit=None)], rules, field_ids)
    assert hits(r, "DQ06", REJECT)["variable"].tolist() == ["wind_speed"]


@pytest.mark.parametrize("value,expected", [(-1, 1), (0, 0), (100, 0), (100.5, 1)])
def test_dq07_humedad_entre_0_y_100(rules, field_ids, value, expected):
    r = run([reading(humidity=value)], rules, field_ids)
    assert len(hits(r, "DQ07", REJECT)) == expected


@pytest.mark.parametrize("value,expected", [(-0.1, 1), (0, 0), (12.5, 0)])
def test_dq08_precipitacion_no_negativa(rules, field_ids, value, expected):
    r = run([reading(precipitation=value)], rules, field_ids)
    assert len(hits(r, "DQ08", REJECT)) == expected


@pytest.mark.parametrize(
    "value,action",
    [(-41, REJECT), (61, REJECT), (-20, WARNING), (46, WARNING), (25, None)],
)
def test_dq09_temperatura_rechazo_y_warning(rules, field_ids, value, action):
    r = run([reading(temperature=value)], rules, field_ids)
    f = hits(r, "DQ09")
    assert f["action"].tolist() == ([action] if action else [])


@pytest.mark.parametrize(
    "value,action",
    [(-0.01, REJECT), (1.2, REJECT), (0.01, WARNING), (0.75, WARNING), (0.3, None)],
)
def test_dq10_humedad_suelo_rechazo_y_warning(rules, field_ids, value, action):
    r = run([reading(soil_moisture=value)], rules, field_ids)
    assert hits(r, "DQ10")["action"].tolist() == ([action] if action else [])


def test_warning_llega_a_silver_con_su_codigo(rules, field_ids):
    r = run([reading(temperature=46)], rules, field_ids)
    assert r.silver.loc[0, "dq_status"] == "WARNING"
    assert r.silver.loc[0, "_dq_warnings"] == "DQ09"


def test_dq11_hueco_de_30_minutos(rules, field_ids):
    recs = series(4)
    del recs[1]  # falta 10:15 -> 10:00 a 10:30 son 30 min
    r = run(recs, rules, field_ids)
    f = hits(r, "DQ11", WARNING)
    assert set(f["_row"]) == {1}
    assert set(f["variable"]) == {"temperature", "humidity", "soil_moisture", "precipitation", "wind_speed"}


def test_dq11_sin_hueco_con_frecuencia_normal(rules, field_ids):
    assert hits(run(series(6), rules, field_ids), "DQ11").empty


def test_dq11_usa_umbral_por_fuente(rules, field_ids):
    # Open-Meteo es horario: 60 min entre lecturas no es un hueco.
    r = run(series(3, freq_min=60, source="open_meteo"), rules, field_ids)
    assert hits(r, "DQ11").empty


def test_dq11_valor_nulo_genera_hueco_en_esa_variable(rules, field_ids):
    recs = series(3)
    recs[1]["humidity"] = None
    r = run(recs, rules, field_ids)
    f = hits(r, "DQ11")
    assert f["variable"].tolist() == ["humidity"]


def test_dq11_compara_con_el_lote_anterior(rules, field_ids):
    context = pd.DataFrame(
        [{"source": "iot_simulator", "field_id": "LIT-01", "timestamp": pd.Timestamp("2026-10-15T09:00:00Z"),
          "temperature": 20.0, "humidity": 60.0, "soil_moisture": 0.3, "precipitation": 0.0, "wind_speed": 10.0}]
    )
    r = run([reading(ts="2026-10-15T10:00:00Z")], rules, field_ids, context=context)
    assert len(hits(r, "DQ11")) == 5


def test_dq12_salto_brusco_de_temperatura(rules, field_ids):
    recs = series(3)
    recs[1]["temperature"] = 24.0  # +4 °C en 15 min = 16 °C/h > 8
    r = run(recs, rules, field_ids)
    f = hits(r, "DQ12", WARNING)
    assert set(f["_row"]) == {1, 2}  # la subida y la bajada
    assert set(f["variable"]) == {"temperature"}


def test_dq12_cambio_gradual_no_es_anomalia(rules, field_ids):
    recs = series(3)
    for i, rec in enumerate(recs):
        rec["temperature"] = 20.0 + i * 1.5  # 6 °C/h
    assert hits(run(recs, rules, field_ids), "DQ12").empty


def test_dq12_ignora_valores_rechazados(rules, field_ids):
    recs = series(3)
    recs[1]["temperature"] = 75.0  # rechazado por DQ09: no debe disparar saltos en sus vecinos
    r = run(recs, rules, field_ids)
    assert hits(r, "DQ12").empty


def test_multiples_motivos_de_rechazo(rules, field_ids):
    r = run([reading(humidity=150, precipitation=-1)], rules, field_ids)
    assert r.quarantine.loc[0, "_rejection_reasons"] == "DQ07;DQ08"
