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
    assert {p.name for p in DASHBOARDS} >= {"calidad-datos.json", "flujo-etl.json", "etl-paso-a-paso.json"}


@pytest.mark.parametrize("path", DASHBOARDS, ids=lambda p: p.stem)
def test_dashboard_lee_solo_tablas_gold(path):
    _, sqls = _queries(path)
    assert sqls
    for sql in sqls:
        # "extract(epoch FROM m.col)" no es una tabla
        tables = re.findall(r"(?<!epoch )\b(?:FROM|JOIN)\s+([a-z_]+\.[a-z_]+)", sql, flags=re.IGNORECASE)
        assert all(t.startswith("gold.") for t in tables), sql  # sin tablas = valores fijos (ej. flechas)
    assert any(re.search(r"\bgold\.", sql) for sql in sqls)


@pytest.mark.parametrize("path", DASHBOARDS, ids=lambda p: p.stem)
def test_paneles_usan_el_selector_de_entorno(path):
    dash, _ = _queries(path)
    entorno = next(v for v in dash["templating"]["list"] if v["name"] == "entorno")
    assert entorno["type"] == "datasource" and entorno["current"]["value"] == "agro-prod"
    for p in dash["panels"]:
        if p["type"] not in ("row", "text"):
            assert p["datasource"]["uid"] == "${entorno}", p["title"]


def _datasources():
    return yaml.safe_load(DATASOURCE.read_text(encoding="utf-8"))["datasources"]


def test_una_fuente_por_entorno():
    dbs = {ds["uid"]: ds["jsonData"]["database"] for ds in _datasources()}
    assert dbs == {"agro-dev": "agro_dev", "agro-staging": "agro_staging", "agro-prod": "agro_prod"}


def test_datasource_usa_usuario_de_solo_lectura():
    for ds in _datasources():
        assert ds["user"] == "${DASHBOARD_DB_USER}"
        assert ds["secureJsonData"]["password"] == "${DASHBOARD_DB_PASSWORD}"
