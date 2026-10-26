"""
pipeline.py
Etapas del pipeline Medallion. Cada etapa es independiente y se identifica por batch_id,
para poder correrlas juntas (src.main) o por separado (notebooks/, reprocesos).

  run_bronze  -> extrae la ventana incremental de cada fuente y la guarda en Bronze.
  run_silver  -> tipa, deduplica y valida DQ01–DQ12; escribe Silver / Quarantine y dq_errors.
  run_gold    -> recalcula los indicadores diarios afectados y hace upsert en PostgreSQL.
  run_all     -> las tres etapas, registrando la corrida (SUCCESS o FAILED) en gold.dq_run_metrics.
"""

import os
from datetime import UTC, datetime

import pandas as pd
from sqlalchemy import Engine

from src.common import db, lake
from src.common.state import WatermarkStore
from src.config import get_settings, load_fields, load_pipeline, load_rules
from src.ingestion import iot_simulator, open_meteo
from src.metrics import quality, trace
from src.transformation import gold
from src.validation.engine import ValidationResult, validate

CONNECTORS = {
    open_meteo.SOURCE: (open_meteo.window, lambda fields, w, cfg, now: open_meteo.fetch(fields, *w, cfg)),
    iot_simulator.SOURCE: (iot_simulator.window, lambda fields, w, cfg, now: iot_simulator.generate(fields, *w, cfg, now)),
}


def run_bronze(engine: Engine, batch_id: str | None = None, now: datetime | None = None,
               sources: list[str] | None = None) -> str | None:
    """Ingesta incremental. Devuelve el batch_id, o None si ninguna fuente trajo datos nuevos."""
    settings, cfg, fields = get_settings(), load_pipeline(), load_fields()
    now = now or datetime.now(UTC)
    batch_id = batch_id or lake.new_batch_id()
    state = WatermarkStore(engine)
    wrote_any = False

    for source, (window_fn, extract_fn) in CONNECTORS.items():
        src_cfg = cfg["sources"][source]
        if not src_cfg.get("enabled", True) or (sources and source not in sources):
            continue
        win = window_fn(state.get(cfg["domain"], source), now, src_cfg)
        if win is None:
            print(f"[BRONZE] {source}: sin datos nuevos.")
            continue
        started = datetime.now(UTC)
        df = extract_fn(fields, win, src_cfg, now)
        if not wrote_any:
            quality.start_run(engine, batch_id, started_at=now)
        df = lake.enrich_with_lineage(df, source_system=source, batch_id=batch_id)
        if lake.write_parquet(df, settings.storage_path, "bronze", cfg["domain"], source, batch_id):
            wrote_any = True
        quality.record_layer(engine, batch_id, "bronze", source, len(df), started, datetime.now(UTC),
                             location=f"storage/{settings.environment}/bronze/{cfg['domain']}/{source}/", window=win)
        # El watermark avanza al fin de la ventana una vez que el lote quedó en Bronze:
        # Silver y Gold se pueden reprocesar desde Bronze sin volver a llamar a la fuente.
        state.set(cfg["domain"], source, win[1], batch_id)

    return batch_id if wrote_any else None


def run_silver(engine: Engine, batch_id: str, now: datetime | None = None) -> ValidationResult:
    settings, cfg, rules = get_settings(), load_pipeline(), load_rules()
    domain, entity = cfg["domain"], cfg["entity"]
    started = datetime.now(UTC)

    batch = pd.concat(
        [lake.read_layer(settings.storage_path, "bronze", domain, s, batch_id) for s in CONNECTORS],
        ignore_index=True,
    )
    if batch.empty:
        raise ValueError(f"No hay datos en Bronze para el lote {batch_id}.")

    context = lake.read_layer(settings.storage_path, "silver", domain, entity)
    if not context.empty:
        context = context[context["_batch_id"] != batch_id]  # reproceso: no compararse consigo mismo

    result = validate(batch, rules, {f["field_id"] for f in load_fields()}, context=context, now=now)
    lake.write_parquet(result.silver, settings.storage_path, "silver", domain, entity, batch_id, replace=True)
    lake.write_parquet(result.quarantine, settings.storage_path, "quarantine", domain, entity, batch_id, replace=True)
    quality.start_run(engine, batch_id)  # asegura la fila de la corrida (también en reprocesos)
    quality.record_quality(engine, result, rules, batch_id)
    traces, steps = trace.build_traces(batch, result.findings, rules, batch_id, cfg["business_timezone"],
                                       settings.environment, domain, entity)
    trace.save_traces(engine, batch_id, traces, steps)
    finished = datetime.now(UTC)
    for layer, df in (("silver", result.silver), ("quarantine", result.quarantine)):
        quality.record_layer(engine, batch_id, layer, entity, len(df), started, finished,
                             location=f"storage/{settings.environment}/{layer}/{domain}/{entity}/")
    return result


def sync_fields(engine: Engine) -> None:
    db.upsert(pd.DataFrame(load_fields()), engine, "gold", "fields", ["field_id"])


def run_gold(engine: Engine, batch_id: str) -> int:
    settings, cfg = get_settings(), load_pipeline()
    domain, entity, tz = cfg["domain"], cfg["entity"], cfg["business_timezone"]
    started = datetime.now(UTC)

    sync_fields(engine)
    silver_batch = lake.read_layer(settings.storage_path, "silver", domain, entity, batch_id)
    keys = gold.affected_keys(silver_batch, tz)
    metrics = gold.daily_metrics(
        lake.read_layer(settings.storage_path, "silver", domain, entity),
        lake.read_layer(settings.storage_path, "quarantine", domain, entity),
        keys, tz, batch_id,
    )
    rows = db.upsert(metrics, engine, "gold", "daily_field_metrics", gold.GOLD_KEYS)
    trace.add_gold_step(engine, batch_id, metrics)
    quality.record_layer(engine, batch_id, "gold", "daily_field_metrics", rows, started, datetime.now(UTC),
                         location="postgres:gold.daily_field_metrics")
    quality.finish_run(engine, batch_id, "ok", last_measured_at=quality.last_measured_at(silver_batch))
    return rows


FORCE_FAILURE_ENV = "PIPELINE_FORCE_FAILURE"


def force_failure_enabled() -> bool:
    """Falla inyectada a propósito, SOLO para probar las alertas (scripts/simulate_alerts.py). Apagada por defecto."""
    return os.getenv(FORCE_FAILURE_ENV, "false").strip().lower() in ("1", "true", "yes", "si", "sí")


def run_all(engine: Engine | None = None, sources: list[str] | None = None) -> str | None:
    """
    Corrida incremental completa. Toda corrida que llega a escribir datos, o que falla en cualquier
    etapa, deja su fila en gold.dq_run_metrics (run_status SUCCESS o FAILED, tiempos y frescura).
    Si la base no responde, la fila no se puede escribir: esa ausencia la detecta la alerta AL01.
    """
    engine = engine or db.get_engine()
    batch_id, started = lake.new_batch_id(), datetime.now(UTC)
    wrote = False
    try:
        if force_failure_enabled():
            raise RuntimeError(f"Falla forzada para probar las alertas ({FORCE_FAILURE_ENV}=true).")
        wrote = run_bronze(engine, batch_id=batch_id, now=started, sources=sources) is not None
        if not wrote:
            print("[PIPELINE] Nada nuevo para procesar.")
            return None
        run_silver(engine, batch_id)
        run_gold(engine, batch_id)
    except Exception:
        try:
            quality.finish_run(engine, batch_id, "failed", started_at=started)
            print(f"[PIPELINE] Corrida {batch_id} registrada como FAILED.")
        except Exception as exc:  # la base no responde: no hay fila (lo cubre AL01 por ausencia)
            print(f"[PIPELINE] No se pudo registrar la falla en gold.dq_run_metrics: {exc}")
        raise
    finally:
        print(f"[PIPELINE] Corrida {batch_id}: {(datetime.now(UTC) - started).total_seconds():.1f}s.")
    print(f"[PIPELINE] Lote {batch_id} procesado.")
    return batch_id


def latest_batch_id(engine: Engine) -> str | None:
    """Último lote con datos en Bronze (útil para correr las etapas por separado desde notebooks)."""
    with engine.connect() as conn:
        return conn.exec_driver_sql(
            "SELECT _batch_id FROM gold.dq_run_metrics WHERE _batch_id IN "
            "(SELECT _batch_id FROM gold.pipeline_layer_metrics WHERE layer = 'bronze') "
            "ORDER BY run_start DESC LIMIT 1"
        ).scalar_one_or_none()


def reprocess(batch_id: str, engine: Engine | None = None) -> None:
    """Backfill: regenera Silver, Quarantine y Gold de un lote a partir de Bronze."""
    engine = engine or db.get_engine()
    quality.start_run(engine, batch_id, restart=True)
    try:
        run_silver(engine, batch_id)
        run_gold(engine, batch_id)
    except Exception:
        quality.finish_run(engine, batch_id, "failed")
        raise
