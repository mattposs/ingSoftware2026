"""Entornos dev / staging / prod y trazas del ETL paso a paso."""

import pandas as pd
import pytest

from src.config import _load_yaml, get_settings, load_pipeline, load_rules
from src.metrics.trace import build_traces
from src.validation.engine import validate
from tests.conftest import NOW, bronze, reading, series

TZ = "America/Argentina/Buenos_Aires"


# ---- Entornos ------------------------------------------------------------------------

def test_dev_usa_solo_el_simulador_y_mas_errores():
    cfg = load_pipeline("dev")
    assert cfg["environment"] == "dev"
    assert cfg["sources"]["open_meteo"]["enabled"] is False
    assert cfg["sources"]["iot_simulator"]["error_rate"] == 0.20
    # El override no borra el resto de la configuración de la fuente.
    assert cfg["sources"]["open_meteo"]["base_url"].startswith("https://")


def test_prod_es_la_configuracion_base():
    base = _load_yaml("pipeline.yaml")
    prod = load_pipeline("prod")
    assert {k: v for k, v in prod.items() if k != "environment"} == base


def test_staging_igual_a_prod_salvo_ventana_inicial():
    staging, prod = load_pipeline("staging"), load_pipeline("prod")
    assert staging["sources"]["iot_simulator"] == prod["sources"]["iot_simulator"]
    assert staging["sources"]["open_meteo"]["initial_days"] == 3


@pytest.mark.parametrize("env", ["dev", "staging", "prod"])
def test_cada_entorno_tiene_su_base_y_su_lake(monkeypatch, env):
    monkeypatch.setenv("APP_ENV", env)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("STORAGE_PATH", raising=False)
    s = get_settings()
    assert s.environment == env
    assert s.database_url.endswith(f"/agro_{env}")
    assert s.storage_path.parts[-2:] == ("storage", env)


def test_entorno_invalido_falla(monkeypatch):
    monkeypatch.setenv("APP_ENV", "produccion")
    with pytest.raises(ValueError, match="APP_ENV"):
        get_settings()


# ---- Trazas --------------------------------------------------------------------------

def _traces(records):
    df = bronze(records)
    df["_ingested_at"] = pd.Timestamp(NOW)
    df["_source_system"] = df["source"]
    rules = load_rules()
    r = validate(df, rules, {f"LIT-0{i}" for i in range(1, 9)}, now=NOW)
    return build_traces(df, r.findings, rules, "abcdef12-0000", TZ, "dev", "agro", "measurements")


def test_trazas_cubren_valido_warning_y_rechazado():
    recs = series(3) + [reading(ts="2026-10-15T11:00:00Z", temperature=46),
                        reading(ts="2026-10-15T11:15:00Z", humidity=150)]
    traces, steps = _traces(recs)
    assert set(traces["dq_status"]) == {"VALID", "WARNING", "INVALID"}
    assert traces["trace_id"].str.startswith("abcdef12-").all()

    for t in traces.itertuples():
        s = steps[steps["trace_id"] == t.trace_id]
        expected_steps = {1, 2, 3, 4, 5} if t.dq_status == "INVALID" else {1, 2, 3, 4}  # el 5 lo completa Gold
        assert set(s["step"]) == expected_steps
        assert len(s[s["step"] == 3]) == 12  # una fila por regla


def test_traza_de_rechazado_explica_la_regla_y_el_destino():
    traces, steps = _traces([reading(humidity=150)])
    t = traces.iloc[0]
    assert t.dq_status == "INVALID" and "DQ07" in t.titulo
    s = steps[steps["trace_id"] == t.trace_id]
    dq07 = s[(s["step"] == 3) & s["dato"].str.startswith("DQ07")].iloc[0]
    assert dq07.resultado == "REJECT" and "humidity" in dq07.valor
    assert s[(s["step"] == 4) & (s["dato"] == "Destino")].iloc[0].valor.startswith("QUARANTINE")
    assert s[s["step"] == 5].iloc[0].valor.startswith("No.")


def test_traza_muestra_el_dato_crudo_y_sin_cambios_en_bronze():
    traces, steps = _traces([reading(temperature=21.5)])
    s = steps[steps["trace_id"] == traces.iloc[0].trace_id]
    assert s[(s["step"] == 1) & (s["dato"] == "Temperatura")].iloc[0].valor == "21.5 °C"
    assert s[(s["step"] == 2) & (s["dato"] == "Cambios sobre el dato")].iloc[0].valor.startswith("Ninguno")


def test_la_imagen_docker_incluye_toda_la_configuracion():
    from src.config import PROJECT_ROOT

    dockerfile = (PROJECT_ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert "COPY config/ config/" in dockerfile  # incluye config/environments/


def test_rechazos_de_muestra_priorizan_reglas_de_valor():
    recs = [reading(ts=None), reading(ts="2026-10-15T10:15:00Z", field_id="LIT-99"),
            reading(ts="2026-10-15T10:30:00Z", humidity=150)]
    traces, _ = _traces(recs)
    invalid = traces[traces["dq_status"] == "INVALID"]
    assert "DQ07" in invalid.iloc[0].titulo  # el rechazo por valor va primero
