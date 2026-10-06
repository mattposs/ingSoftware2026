"""Conector Open-Meteo (con la API simulada), chequeo de rules.yaml y catalogación."""

import copy
from datetime import UTC, datetime

import pandas as pd
import yaml

from src.config import load_fields, load_pipeline, load_rules
from src.governance.catalog_manager import CatalogManager
from src.governance.dict_generator import generate_data_dictionary_md
from src.governance.schema_extractor import extract_column_metadata
from src.ingestion import open_meteo
from src.validation import check_rules
from src.validation.engine import validate
from tests.conftest import NOW


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self.payload


def _payload(times):
    n = len(times)
    return {
        "hourly_units": {"temperature_2m": "°C", "relative_humidity_2m": "%", "soil_moisture_0_to_7cm": "m³/m³",
                         "precipitation": "mm", "wind_speed_10m": "km/h"},
        "hourly": {"time": times, "temperature_2m": [18.5] * n, "relative_humidity_2m": [70] * n,
                   "soil_moisture_0_to_7cm": [0.31] * n, "precipitation": [0.0] * n, "wind_speed_10m": [11.2] * n},
    }


def test_open_meteo_respeta_la_ventana_y_las_unidades(monkeypatch):
    times = ["2026-10-05T22:00", "2026-10-05T23:00", "2026-10-06T00:00", "2026-10-06T01:00"]
    calls = []

    def fake_get(url, params, timeout):
        calls.append(params)
        return FakeResponse(_payload(times))

    monkeypatch.setattr(open_meteo.requests, "get", fake_get)
    cfg = load_pipeline()["sources"]["open_meteo"]
    start = datetime(2026, 10, 5, 22, tzinfo=UTC)   # exclusivo
    end = datetime(2026, 10, 6, 0, tzinfo=UTC)      # inclusivo
    df = open_meteo.fetch(load_fields()[:1], start, end, cfg)

    assert df["timestamp"].tolist() == ["2026-10-05T23:00", "2026-10-06T00:00"]
    assert calls[0]["start_date"] == "2026-10-05" and calls[0]["timezone"] == "GMT"
    # Los datos reales de Open-Meteo pasan las reglas sin hallazgos.
    r = validate(df, load_rules(), {f["field_id"] for f in load_fields()}, now=NOW)
    assert (r.valid, r.invalid) == (2, 0)


def test_check_rules_detecta_configuracion_rota(monkeypatch):
    broken = copy.deepcopy(load_rules())
    del broken["DQ12"]
    broken["DQ09"]["warning"] = {"min": -50, "max": 45}   # warning fuera del rango de rechazo
    broken["DQ01"]["severidad"] = "Altísima"
    monkeypatch.setattr(check_rules, "load_rules", lambda: broken)
    errors = check_rules.check()
    assert any("DQ12" in e for e in errors)
    assert any("DQ09" in e for e in errors)
    assert any("DQ01" in e for e in errors)


def test_catalogo_preserva_descripciones_y_genera_diccionario(tmp_path):
    df = pd.DataFrame({"field_id": ["C01", None], "detalle": ["con | pipe\ny salto", "ok"]})
    mgr = CatalogManager(str(tmp_path / "catalog"))
    path = mgr.register_or_update_dataset("agro", "x", "silver", "desc", "storage/x",
                                          extract_column_metadata(df), {"field_id": "Campo."})
    # Segunda pasada sin descripciones: se conservan las anteriores.
    path = mgr.register_or_update_dataset("agro", "x", "silver", "desc", "storage/x", extract_column_metadata(df))
    cols = {c["name"]: c for c in yaml.safe_load(open(path, encoding="utf-8"))["columns"]}
    assert cols["field_id"]["description"] == "Campo."
    assert cols["field_id"]["null_percentage"] == 50.0

    md = open(generate_data_dictionary_md(path, str(tmp_path / "docs")), encoding="utf-8").read()
    table_rows = [line for line in md.splitlines() if line.startswith("| `")]
    assert len(table_rows) == 2  # el salto de línea del ejemplo no rompe la tabla
    assert "con \\| pipe y salto" in md
