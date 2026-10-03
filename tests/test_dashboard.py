"""El dashboard provisionado es válido y consume solo la capa Gold (RNF04)."""

import json
import re

import yaml

from src.config import PROJECT_ROOT

DASHBOARD = PROJECT_ROOT / "grafana" / "dashboards" / "calidad-datos.json"
DATASOURCE = PROJECT_ROOT / "grafana" / "provisioning" / "datasources" / "agro.yml"


def _queries():
    dash = json.loads(DASHBOARD.read_text(encoding="utf-8"))
    sqls = [t["rawSql"] for p in dash["panels"] for t in p.get("targets", [])]
    sqls += [v["query"] for v in dash["templating"]["list"] if v["type"] == "query"]
    return dash, sqls


def test_dashboard_lee_solo_tablas_gold():
    _, sqls = _queries()
    assert sqls
    for sql in sqls:
        tables = re.findall(r"\b(?:FROM|JOIN)\s+([a-z_]+\.[a-z_]+)", sql, flags=re.IGNORECASE)
        assert tables, sql
        assert all(t.startswith("gold.") for t in tables), sql


def test_paneles_usan_la_fuente_provisionada():
    dash, _ = _queries()
    uid = yaml.safe_load(DATASOURCE.read_text(encoding="utf-8"))["datasources"][0]["uid"]
    for p in dash["panels"]:
        if p["type"] != "row":
            assert p["datasource"]["uid"] == uid, p["title"]


def test_datasource_usa_usuario_de_solo_lectura():
    ds = yaml.safe_load(DATASOURCE.read_text(encoding="utf-8"))["datasources"][0]
    assert ds["user"] == "${DASHBOARD_DB_USER}"
    assert ds["secureJsonData"]["password"] == "${DASHBOARD_DB_PASSWORD}"
