"""El dashboard provisionado es válido y consume solo la capa Gold (RNF04)."""

import json
import re

import pytest
import yaml

from src.config import PROJECT_ROOT

DASHBOARDS = sorted((PROJECT_ROOT / "grafana" / "dashboards").glob("*.json"))
DATASOURCE = PROJECT_ROOT / "grafana" / "provisioning" / "datasources" / "agro.yml"


def _queries(path):
    dash = json.loads(path.read_text(encoding="utf-8"))
    sqls = [t["rawSql"] for p in dash["panels"] for t in p.get("targets", [])]
    sqls += [v["query"] for v in dash["templating"]["list"] if v["type"] == "query"]
    return dash, sqls


def test_hay_dashboards_provisionados():
    assert {p.name for p in DASHBOARDS} >= {"calidad-datos.json", "flujo-etl.json"}


@pytest.mark.parametrize("path", DASHBOARDS, ids=lambda p: p.stem)
def test_dashboard_lee_solo_tablas_gold(path):
    _, sqls = _queries(path)
    assert sqls
    for sql in sqls:
        # "extract(epoch FROM m.col)" no es una tabla
        tables = re.findall(r"(?<!epoch )\b(?:FROM|JOIN)\s+([a-z_]+\.[a-z_]+)", sql, flags=re.IGNORECASE)
        assert tables, sql
        assert all(t.startswith("gold.") for t in tables), sql


@pytest.mark.parametrize("path", DASHBOARDS, ids=lambda p: p.stem)
def test_paneles_usan_la_fuente_provisionada(path):
    dash, _ = _queries(path)
    uid = yaml.safe_load(DATASOURCE.read_text(encoding="utf-8"))["datasources"][0]["uid"]
    for p in dash["panels"]:
        if p["type"] != "row":
            assert p["datasource"]["uid"] == uid, p["title"]


def test_datasource_usa_usuario_de_solo_lectura():
    ds = yaml.safe_load(DATASOURCE.read_text(encoding="utf-8"))["datasources"][0]
    assert ds["user"] == "${DASHBOARD_DB_USER}"
    assert ds["secureJsonData"]["password"] == "${DASHBOARD_DB_PASSWORD}"
