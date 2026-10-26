"""
verify_rnf.py
Mide los requerimientos no funcionales con datos reales y los vuelca en docs/evidencia_alertas/rnf_medidos.md.

    python scripts/verify_rnf.py                   # lee STAGING + pruebas en una base aislada
    python scripts/verify_rnf.py --entorno prod    # lee PROD (solo lectura; las pruebas siguen aisladas)

Dos tipos de mediciones:
  - Solo lectura sobre el entorno elegido: RNF07 (corridas por día), RNF08 (frescura), RNF09 (duración),
    RNF02 (linaje en Bronze) y RNF04 (INVALID en Gold).
  - Pruebas que escriben, SIEMPRE en una base aislada (agro_rnf) y un lake temporal, nunca en el entorno:
    RNF10 (reproceso de un día de 19.200 registros), RNF03 (reproceso idempotente) y RNF06 (umbral en
    config/rules.yaml aplicado sin tocar código; el archivo se restaura al terminar y se verifica su hash).

Ningún objetivo se ajusta: si algo no cumple, la tabla dice "No cumple" y el motivo.
Necesita el stack levantado (PostgreSQL en localhost) y las credenciales de .env / .env.example.
"""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pandas as pd
import yaml
from dotenv import dotenv_values
from sqlalchemy import create_engine, text

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "evidencia_alertas"
ISOLATED_DB = "agro_rnf"
_files = {**dotenv_values(ROOT / ".env.example"), **dotenv_values(ROOT / ".env")}


def cfg(name: str, default: str = "") -> str:
    return os.getenv(name) or _files.get(name) or default


def url(db: str, admin: bool = False) -> str:
    user, pw = ((cfg("POSTGRES_USER", "postgres"), cfg("POSTGRES_PASSWORD")) if admin else
                (cfg("PIPELINE_DB_USER", "pipeline"), cfg("PIPELINE_DB_PASSWORD")))
    return f"postgresql+psycopg://{user}:{pw}@localhost:{cfg('POSTGRES_PORT', '5432')}/{db}"


def log(msg: str) -> None:
    print(f"[RNF] {msg}", flush=True)


# =================================================================================================
# Tareas aisladas: corren en un proceso aparte, con DATABASE_URL / STORAGE_PATH / PIPELINE_CONFIG_DIR
# apuntando a la base y al lake aislados. Imprimen su resultado como JSON en la última línea.
# =================================================================================================

def _write_bronze(df: pd.DataFrame, batch_id: str) -> None:
    from src.common import lake
    from src.config import get_settings, load_pipeline
    from src.ingestion import iot_simulator
    cfg_ = load_pipeline()
    df = lake.enrich_with_lineage(df, source_system=iot_simulator.SOURCE, batch_id=batch_id)
    lake.write_parquet(df, get_settings().storage_path, "bronze", cfg_["domain"], iot_simulator.SOURCE, batch_id)


def _gold_snapshot(engine) -> pd.DataFrame:
    with engine.connect() as conn:
        df = pd.read_sql(text("SELECT * FROM gold.daily_field_metrics"), conn)
    return df.drop(columns=["_updated_at"]).sort_values(["fecha", "field_id", "fuente"]).reset_index(drop=True)


def task_volumen() -> dict:
    """RNF10 y RNF03: un día simulado de 200 sensores × 96 lecturas, reprocesado desde Bronze dos veces."""
    from src import pipeline
    from src.common import db, lake
    from src.config import load_fields, load_pipeline
    from src.ingestion import iot_simulator

    fields = load_fields()   # config aislada: un field_id por sensor (200)
    real = yaml.safe_load((ROOT / "config" / "fields.yaml").read_text(encoding="utf-8"))["fields"]
    real_ids = {f["field_id"] for f in real}
    sim = load_pipeline()["sources"]["iot_simulator"]
    end = datetime(2026, 10, 20, 3, 0, tzinfo=UTC)          # un día de negocio completo (00:00 a 24:00 ART)
    # El simulador arma el perfil de cada campo según su posición en la lista: se generan los 8 campos reales
    # una vez por número de sensor (semilla distinta) y cada lectura toma el id de su sensor (LIT-01-S01...).
    parts = []
    for k in range(max(int(f["sensores"]) for f in real)):
        g = iot_simulator.generate(real, end - timedelta(days=1), end, dict(sim, seed=20261020 + k),
                                   now=end + timedelta(minutes=5))
        con_sensor = {f["field_id"] for f in real if int(f["sensores"]) > k}
        g = g[g["field_id"].isin(con_sensor) | ~g["field_id"].isin(real_ids)].copy()
        g["field_id"] = g["field_id"].map(lambda x, k=k: f"{x}-S{k + 1:02d}" if x in real_ids else x)
        parts.append(g)
    df = pd.concat(parts, ignore_index=True)
    batch = lake.new_batch_id()
    _write_bronze(df, batch)
    engine = db.get_engine()

    t0 = time.perf_counter()
    pipeline.reprocess(batch, engine)
    primera = time.perf_counter() - t0
    antes = _gold_snapshot(engine)
    with engine.connect() as conn:
        run = conn.execute(text("SELECT total, valid, warning, invalid, dq_score FROM gold.dq_run_metrics "
                                "WHERE _batch_id = :b"), {"b": batch}).mappings().one()

    t0 = time.perf_counter()
    pipeline.reprocess(batch, engine)
    segunda = time.perf_counter() - t0
    despues = _gold_snapshot(engine)
    with engine.connect() as conn:
        dups = conn.execute(text("SELECT count(*) FROM (SELECT fecha, field_id, fuente FROM gold.daily_field_metrics "
                                 "GROUP BY 1, 2, 3 HAVING count(*) > 1) d")).scalar()
    identico = antes.equals(despues)
    return {"sensores": len(fields), "registros_bronze": len(df),
            "lecturas_esperadas": len(fields) * 96, "reproceso_s": round(primera, 2),
            "segundo_reproceso_s": round(segunda, 2), "run": {k: (float(v) if v is not None else None)
                                                             for k, v in run.items()},
            "gold_filas_antes": len(antes), "gold_filas_despues": len(despues),
            "gold_identico": bool(identico), "claves_duplicadas": int(dups)}


def task_umbral() -> dict:
    """RNF06 (una corrida): procesa un lote fijo de 8 campos y cuenta los WARNING de DQ09."""
    from src import pipeline
    from src.common import db, lake
    from src.config import load_fields, load_pipeline, load_rules
    from src.ingestion import iot_simulator

    sim = dict(load_pipeline()["sources"]["iot_simulator"], seed=7, error_rate=0.0)
    end = datetime(2026, 10, 20, 3, 0, tzinfo=UTC)
    df = iot_simulator.generate(load_fields(), end - timedelta(days=1), end, sim, now=end + timedelta(minutes=5))
    batch = lake.new_batch_id()
    _write_bronze(df, batch)
    engine = db.get_engine()
    pipeline.reprocess(batch, engine)
    with engine.connect() as conn:
        warnings = conn.execute(text("SELECT count(*) FROM gold.dq_errors WHERE _batch_id = :b AND rule_id = 'DQ09' "
                                     "AND action = 'WARNING'"), {"b": batch}).scalar()
    return {"umbral_warning_max": load_rules()["DQ09"]["warning"]["max"], "registros": len(df),
            "temperatura_max": float(df["temperature"].max()), "warnings_dq09": int(warnings)}


def run_task(name: str, env: dict) -> dict:
    res = subprocess.run([sys.executable, str(Path(__file__)), "--tarea", name], cwd=ROOT, capture_output=True,
                         text=True, encoding="utf-8", errors="replace", env={**os.environ, **env})
    if res.returncode != 0:
        raise RuntimeError(f"La tarea {name} falló:\n{res.stdout[-3000:]}\n{res.stderr[-3000:]}")
    return json.loads(res.stdout.strip().splitlines()[-1])


def isolated_env(storage: Path, config_dir: Path | None = None) -> dict:
    env = {"APP_ENV": "staging", "DATABASE_URL": url(ISOLATED_DB, admin=True), "STORAGE_PATH": str(storage),
           "PYTHONIOENCODING": "utf-8"}
    if config_dir:
        env["PIPELINE_CONFIG_DIR"] = str(config_dir)
    return env


def reset_isolated_db() -> None:
    admin = create_engine(url("postgres", admin=True), isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.exec_driver_sql(f"DROP DATABASE IF EXISTS {ISOLATED_DB} WITH (FORCE)")
        conn.exec_driver_sql(f"CREATE DATABASE {ISOLATED_DB}")
    admin.dispose()
    eng = create_engine(url(ISOLATED_DB, admin=True))
    raw = eng.raw_connection()   # sin parámetros: el SQL tiene "%" en comentarios
    try:
        raw.cursor().execute((ROOT / "sql" / "schema" / "01_schema.sql").read_text(encoding="utf-8"))
        raw.commit()
    finally:
        raw.close()
    eng.dispose()


def config_200_sensores(dest: Path) -> Path:
    """Copia config/ y reemplaza fields.yaml por un 'campo' por sensor (200), con los datos de su campo real."""
    shutil.copytree(ROOT / "config", dest)
    fields = yaml.safe_load((ROOT / "config" / "fields.yaml").read_text(encoding="utf-8"))["fields"]
    sensores = [{**f, "field_id": f"{f['field_id']}-S{n:02d}", "sensores": 1}
                for f in fields for n in range(1, int(f["sensores"]) + 1)]
    (dest / "fields.yaml").write_text(yaml.safe_dump({"fields": sensores}, allow_unicode=True, sort_keys=False),
                                      encoding="utf-8")
    return dest


# =================================================================================================
# Mediciones de solo lectura sobre el entorno
# =================================================================================================

def measure_env(entorno: str) -> dict:
    eng = create_engine(url(f"agro_{entorno}"))
    with eng.connect() as conn:
        runs = pd.read_sql(text("SELECT _batch_id, run_start, status, run_status, started_at, finished_at, "
                                "duration_seconds, last_measured_at FROM gold.dq_run_metrics"), conn)
    eng.dispose()
    runs["dia"] = pd.to_datetime(runs["run_start"], utc=True).dt.tz_convert("America/Argentina/Buenos_Aires").dt.date
    por_dia = runs.groupby("dia").size()
    nuevas = runs[runs["run_status"].notna()]
    exitosas = nuevas[nuevas["run_status"] == "SUCCESS"]
    fres = ((pd.to_datetime(exitosas["finished_at"], utc=True) - pd.to_datetime(exitosas["last_measured_at"], utc=True))
            .dt.total_seconds() / 60).dropna()
    dur = pd.to_numeric(exitosas["duration_seconds"], errors="coerce").dropna()

    # RNF02: linaje en Bronze (todos los Parquet del entorno).
    from src.common import lake
    from src.config import load_pipeline
    from src.transformation import gold
    pcfg = load_pipeline(entorno)
    storage = ROOT / "storage" / entorno
    bronze_files = list((storage / "bronze").rglob("*.parquet"))
    lineage = ["_batch_id", "_ingested_at", "_source_system"]
    nulos, filas_bronze = 0, 0
    for f in bronze_files:
        df = pd.read_parquet(f, columns=lineage)
        filas_bronze += len(df)
        nulos += int(df[lineage].isna().any(axis=1).sum())

    # RNF04: Gold se calcula solo desde Silver. INVALID en Silver + filas de Gold que no cuadran con Silver.
    silver = lake.read_layer(storage, "silver", pcfg["domain"], pcfg["entity"])
    invalid_silver = int((silver["dq_status"] == "INVALID").sum()) if not silver.empty else 0
    eng = create_engine(url(f"agro_{entorno}"))
    with eng.connect() as conn:
        gold_df = pd.read_sql(text("SELECT fecha, field_id, fuente, cantidad_mediciones FROM gold.daily_field_metrics"),
                              conn)
    eng.dispose()
    esperado = (silver.assign(fecha=gold._local_date(silver["timestamp"], pcfg["business_timezone"]),
                              fuente=silver["source"]).groupby(gold.GOLD_KEYS).size().rename("en_silver").reset_index())
    gold_df["fecha"] = pd.to_datetime(gold_df["fecha"]).dt.date
    cruce = gold_df.merge(esperado, on=gold.GOLD_KEYS, how="left")
    no_cuadran = int((cruce["cantidad_mediciones"] != cruce["en_silver"]).sum())

    return {
        "corridas_total": len(runs), "corridas_por_dia": {str(k): int(v) for k, v in por_dia.items()},
        "corridas_con_monitoreo": len(nuevas), "exitosas": len(exitosas),
        "fallidas": int((nuevas["run_status"] == "FAILED").sum()),
        "desde": str(nuevas["run_start"].min()) if len(nuevas) else None,
        "frescura_p95": round(float(fres.quantile(0.95)), 2) if len(fres) else None,
        "frescura_max": round(float(fres.max()), 2) if len(fres) else None, "frescura_n": len(fres),
        "duracion_p95": round(float(dur.quantile(0.95)), 2) if len(dur) else None,
        "duracion_max": round(float(dur.max()), 2) if len(dur) else None, "duracion_n": len(dur),
        "bronze_archivos": len(bronze_files), "bronze_filas": filas_bronze, "bronze_linaje_nulo": nulos,
        "silver_filas": len(silver), "silver_invalid": invalid_silver, "gold_filas": len(gold_df),
        "gold_no_cuadra_con_silver": no_cuadran,
    }


# =================================================================================================

def rnf06(storage_root: Path) -> dict:
    rules_path = ROOT / "config" / "rules.yaml"
    original = rules_path.read_bytes()
    sha = hashlib.sha256(original).hexdigest()
    texto = original.decode("utf-8")
    viejo = "    warning: {min: -15, max: 45}"
    nuevo = "    warning: {min: -15, max: 25}"
    bloque = texto[texto.index("  DQ09:"):texto.index("  DQ10:")]
    if viejo not in bloque:
        raise RuntimeError("No encontré el umbral de warning de DQ09 en config/rules.yaml.")
    try:
        reset_isolated_db()
        antes = run_task("umbral", isolated_env(storage_root / "rnf06_a"))
        rules_path.write_bytes(texto.replace(bloque, bloque.replace(viejo, nuevo)).encode("utf-8"))
        reset_isolated_db()
        despues = run_task("umbral", isolated_env(storage_root / "rnf06_b"))
    finally:
        rules_path.write_bytes(original)
    restaurado = hashlib.sha256(rules_path.read_bytes()).hexdigest() == sha
    return {"antes": antes, "despues": despues, "restaurado": restaurado}


def cumple(ok: bool | None) -> str:
    return "—" if ok is None else ("Cumple" if ok else "**No cumple**")


def write_table(entorno: str, m: dict, vol: dict | None, r06: dict | None, errores: dict) -> str:
    hoy = datetime.now().astimezone()
    dias = m["corridas_por_dia"]
    dias_completos = {d: n for d, n in dias.items() if d < str(hoy.date())}
    rnf07_ok = bool(dias_completos) and all(n >= 96 for n in dias_completos.values())
    rows = []
    detalle_dias = ", ".join(f"{d}: {n}" for d, n in sorted(dias.items())[-7:]) or "sin corridas"
    rows.append(("RNF07", "Corridas por día en gold.dq_run_metrics",
                 f"Últimos días: {detalle_dias}" + ("" if dias_completos else " (no hay ningún día completo medido)"),
                 "96 por día (una cada 15 min)", cumple(rnf07_ok if dias_completos else False)))
    rows.append(("RNF08", "Frescura: finished_at − last_measured_at",
                 (f"p95 = {m['frescura_p95']} min · máximo = {m['frescura_max']} min ({m['frescura_n']} corridas)"
                  if m["frescura_n"] else "sin corridas con last_measured_at"),
                 "p95 ≤ 20 min y máximo ≤ 30 min",
                 cumple(m["frescura_n"] > 0 and m["frescura_p95"] <= 20 and m["frescura_max"] <= 30)
                 if m["frescura_n"] else "—"))
    rows.append(("RNF09", "duration_seconds de las corridas incrementales",
                 (f"p95 = {m['duracion_p95']} s · máximo = {m['duracion_max']} s ({m['duracion_n']} corridas)"
                  if m["duracion_n"] else "sin corridas con duration_seconds"),
                 "≤ 2 min (120 s)", cumple(m["duracion_max"] <= 120) if m["duracion_n"] else "—"))
    if vol:
        rows.append(("RNF10", f"Reproceso completo de un día simulado ({vol['sensores']} sensores × 96)",
                     f"{vol['reproceso_s']} s para {vol['registros_bronze']:,} registros de Bronze "
                     f"({vol['lecturas_esperadas']:,} lecturas + duplicados inyectados)".replace(",", "."),
                     "≤ 5 min (300 s)", cumple(vol["reproceso_s"] <= 300)))
    else:
        rows.append(("RNF10", "Reproceso de un día de 19.200 registros", f"No se pudo medir: {errores.get('volumen')}",
                     "≤ 5 min", "—"))
    rows.append(("RNF02", "Registros de Bronze con _batch_id, _ingested_at o _source_system nulos",
                 f"{m['bronze_linaje_nulo']} de {m['bronze_filas']:,} filas ({m['bronze_archivos']} archivos)".replace(",", "."),
                 "0", cumple(m["bronze_linaje_nulo"] == 0)))
    if vol:
        rows.append(("RNF03", "Reprocesar un día desde Bronze y comparar gold.daily_field_metrics",
                     f"{vol['gold_filas_antes']} filas antes y {vol['gold_filas_despues']} después; "
                     f"{'idénticas' if vol['gold_identico'] else 'DISTINTAS'}; {vol['claves_duplicadas']} claves duplicadas",
                     "Idéntico, sin duplicados", cumple(vol["gold_identico"] and vol["claves_duplicadas"] == 0)))
    else:
        rows.append(("RNF03", "Reproceso idempotente", f"No se pudo medir: {errores.get('volumen')}", "Idéntico", "—"))
    rows.append(("RNF04", "Registros INVALID en Gold",
                 f"{m['silver_invalid']} INVALID en Silver (única fuente de Gold, {m['silver_filas']:,} filas); "
                 f"{m['gold_no_cuadra_con_silver']} de {m['gold_filas']} filas de Gold no cuadran con Silver".replace(",", "."),
                 "0", cumple(m["silver_invalid"] == 0 and m["gold_no_cuadra_con_silver"] == 0)))
    if r06:
        a, b = r06["antes"], r06["despues"]
        ok = b["warnings_dq09"] > a["warnings_dq09"] and r06["restaurado"]
        rows.append(("RNF06", "Cambiar un umbral en config/rules.yaml sin tocar código",
                     f"DQ09 warning máx. {a['umbral_warning_max']} °C → {a['warnings_dq09']} warnings; "
                     f"con {b['umbral_warning_max']} °C → {b['warnings_dq09']} warnings (mismo lote, temp. máx. "
                     f"{a['temperatura_max']} °C). Archivo restaurado: {'sí' if r06['restaurado'] else 'NO'}",
                     "La corrida aplica el umbral nuevo", cumple(ok)))
    else:
        rows.append(("RNF06", "Umbral en config/rules.yaml", f"No se pudo medir: {errores.get('umbral')}", "—", "—"))

    lines = [
        "# Requerimientos no funcionales medidos",
        "",
        f"Generado por `scripts/verify_rnf.py` el {hoy:%d/%m/%Y %H:%M} (hora local). Entorno leído: **{entorno.upper()}** "
        f"(solo lectura). Las pruebas que escriben (RNF10, RNF03 y RNF06) corrieron en una base aislada "
        f"(`{ISOLATED_DB}`) con un lake temporal.",
        "",
        "| RNF | Qué se midió | Valor medido | Objetivo | Resultado |",
        "|---|---|---|---|---|",
        *[f"| {a} | {b} | {c} | {d} | {e} |" for a, b, c, d, e in rows],
        "",
        "## Cómo se midió y qué tener en cuenta",
        "",
        f"- **Corridas leídas:** {m['corridas_total']} en `gold.dq_run_metrics`; {m['corridas_con_monitoreo']} tienen "
        f"las columnas de monitoreo ({m['exitosas']} SUCCESS, {m['fallidas']} FAILED), desde {m['desde'] or '—'}. "
        "RNF08 y RNF09 solo pueden medirse sobre esas corridas; las anteriores tienen las columnas en NULL.",
        "- **RNF07** cuenta las filas por día calendario (hora Argentina). Solo se evalúan los días completos: "
        "el de hoy está en curso. El scheduler corre en Docker en una computadora personal: si la máquina estuvo "
        "apagada o suspendida, ese día tiene menos corridas. Además, una corrida sin datos nuevos no deja fila.",
        "- **RNF08** se mide sobre las corridas SUCCESS. last_measured_at sale de Silver: es el timestamp máximo "
        "de los registros válidos del lote.",
        "- **RNF10** usa una copia de `config/` con un `field_id` por sensor (200, por ejemplo `LIT-01-S01`), porque "
        "el pipeline identifica las lecturas por campo. Las lecturas las genera el simulador IoT con su tasa de error "
        "normal: los 8 campos reales, una vez por número de sensor y con otra semilla, para conservar el perfil "
        "climático de cada campo. "
        "El tiempo es el de `reprocess()` (Silver + Gold) leyendo desde Bronze, en esta computadora.",
        "- **RNF04**: Gold no guarda el estado de cada registro, porque se calcula solo con Silver. Se mide que "
        "Silver no tenga INVALID y que la cantidad de mediciones de cada fila de Gold coincida con Silver.",
        "- **RNF06** modifica `config/rules.yaml` (warning de DQ09, de 45 °C a 25 °C), corre el mismo lote en un "
        "proceso nuevo y lo restaura; se comprueba con el hash SHA-256 que el archivo quedó igual que antes.",
        "",
    ]
    if errores:
        lines += ["## Errores", ""] + [f"- {k}: {v}" for k, v in errores.items()] + [""]
    (OUT / "rnf_medidos.md").write_text("\n".join(lines), encoding="utf-8")
    (OUT / "rnf_medidos.json").write_text(json.dumps({"entorno": entorno, "medido": m, "volumen": vol,
                                                       "rnf06": r06, "errores": errores}, ensure_ascii=False,
                                                      indent=2, default=str), encoding="utf-8")
    return "\n".join(rows_to_text(rows))


def rows_to_text(rows):
    return [f"{a}: {e.replace('*', '')} · {c}" for a, b, c, d, e in rows]


def main() -> int:
    parser = argparse.ArgumentParser(description="Medición de RNF con datos reales")
    parser.add_argument("--entorno", choices=["staging", "prod", "dev"], default="staging")
    parser.add_argument("--tarea", choices=["volumen", "umbral"], help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.tarea:
        sys.path.insert(0, str(ROOT))
        result = task_volumen() if args.tarea == "volumen" else task_umbral()
        print(json.dumps(result, default=str))
        return 0

    sys.path.insert(0, str(ROOT))
    os.environ.setdefault("APP_ENV", args.entorno)
    OUT.mkdir(parents=True, exist_ok=True)
    errores: dict = {}
    log(f"Leyendo {args.entorno.upper()}...")
    m = measure_env(args.entorno)
    vol = r06 = None
    tmp = Path(tempfile.mkdtemp(prefix="rnf_"))
    try:
        try:
            log("RNF10 / RNF03: generando un día de 200 sensores y reprocesándolo en la base aislada...")
            reset_isolated_db()
            vol = run_task("volumen", isolated_env(tmp / "volumen", config_200_sensores(tmp / "config")))
        except Exception as exc:
            errores["volumen"] = str(exc)[:2000]
        try:
            log("RNF06: cambiando el umbral de DQ09 en config/rules.yaml (se restaura al terminar)...")
            r06 = rnf06(tmp)
        except Exception as exc:
            errores["umbral"] = str(exc)[:2000]
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
        admin = create_engine(url("postgres", admin=True), isolation_level="AUTOCOMMIT")
        with admin.connect() as conn:
            conn.exec_driver_sql(f"DROP DATABASE IF EXISTS {ISOLATED_DB} WITH (FORCE)")
        admin.dispose()
    print(write_table(args.entorno, m, vol, r06, errores))
    log(f"Listo: {OUT / 'rnf_medidos.md'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
