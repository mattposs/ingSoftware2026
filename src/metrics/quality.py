"""
quality.py
Registro de la corrida (gold.dq_run_metrics) y de los errores detectados (gold.dq_errors).
Data Quality Score estricto = VALID / total × 100 y % utilizable = (VALID + WARNING) / total × 100 (RF07, decisión D2).
Cada corrida guarda además run_status (SUCCESS / FAILED), started_at, finished_at, duration_seconds y
last_measured_at, que usan las alertas AL01 / AL02 y el panel de salud del pipeline.
"""

from datetime import UTC, datetime

import pandas as pd
from sqlalchemy import Engine, text

from src.validation.engine import ValidationResult

ERROR_COLUMNS = [
    "_batch_id", "detected_at", "measured_at", "source", "field_id",
    "variable", "rule_id", "rule_type", "action", "severidad", "detalle",
]


RUN_STATUS = {"ok": "SUCCESS", "failed": "FAILED"}


def start_run(engine: Engine, batch_id: str, restart: bool = False, started_at: datetime | None = None) -> None:
    """Crea la fila de la corrida. restart=True (reproceso) vuelve a tomar el tiempo desde cero."""
    restart_sql = ", started_at = now(), finished_at = NULL, run_status = NULL, duration_seconds = NULL" if restart else ""
    with engine.begin() as conn:
        conn.execute(
            text(
                f"""
                INSERT INTO gold.dq_run_metrics (_batch_id, run_start, started_at, status)
                VALUES (:b, now(), COALESCE(:s, now()), 'running')
                ON CONFLICT (_batch_id) DO UPDATE SET run_end = NULL, status = 'running'{restart_sql}
                """
            ),
            {"b": batch_id, "s": started_at},
        )


def finish_run(
    engine: Engine,
    batch_id: str,
    status: str,
    started_at: datetime | None = None,
    last_measured_at: datetime | None = None,
) -> None:
    """
    Cierra la corrida con su estado, tiempos y frescura. Si la fila no existe (la corrida falló antes
    de escribir en Bronze) la crea, así una falla temprana también queda registrada como FAILED.
    """
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO gold.dq_run_metrics (_batch_id, run_start, started_at, run_end, finished_at,
                                                 status, run_status, duration_seconds, last_measured_at)
                VALUES (:b, COALESCE(:s, now()), COALESCE(:s, now()), now(), now(), :st, :rs,
                        round(extract(epoch FROM now() - COALESCE(:s, now()))::numeric, 2), :lm)
                ON CONFLICT (_batch_id) DO UPDATE SET
                    run_end = now(), finished_at = now(), status = EXCLUDED.status, run_status = EXCLUDED.run_status,
                    duration_seconds = round(extract(epoch FROM now() - COALESCE(
                        gold.dq_run_metrics.started_at, gold.dq_run_metrics.run_start))::numeric, 2),
                    last_measured_at = COALESCE(EXCLUDED.last_measured_at, gold.dq_run_metrics.last_measured_at)
                """
            ),
            {"b": batch_id, "st": status, "rs": RUN_STATUS[status], "s": started_at, "lm": last_measured_at},
        )


def last_measured_at(silver: pd.DataFrame) -> datetime | None:
    """
    Timestamp máximo de medición del lote, tomado de Silver (VALID + WARNING). No se usa Bronze
    porque ahí están los timestamps futuros o inválidos que rechaza DQ03 y falsearían la frescura.
    """
    if silver.empty or "timestamp" not in silver:
        return None
    latest = pd.to_datetime(silver["timestamp"], utc=True, errors="coerce").max()
    return None if pd.isna(latest) else latest.to_pydatetime()


def record_layer(
    engine: Engine,
    batch_id: str,
    layer: str,
    entity: str,
    rows: int,
    started_at: datetime,
    finished_at: datetime,
    location: str | None = None,
    window: tuple[datetime, datetime] | None = None,
) -> None:
    """Registra qué hizo una capa en el lote (gold.pipeline_layer_metrics). Idempotente."""
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO gold.pipeline_layer_metrics
                    (_batch_id, layer, entity, rows, location, window_start, window_end, started_at, finished_at)
                VALUES (:b, :l, :e, :r, :loc, :ws, :we, :s, :f)
                ON CONFLICT (_batch_id, layer, entity) DO UPDATE
                SET rows = EXCLUDED.rows, location = EXCLUDED.location,
                    window_start = COALESCE(EXCLUDED.window_start, gold.pipeline_layer_metrics.window_start),
                    window_end = COALESCE(EXCLUDED.window_end, gold.pipeline_layer_metrics.window_end),
                    started_at = EXCLUDED.started_at, finished_at = EXCLUDED.finished_at
                """
            ),
            {"b": batch_id, "l": layer, "e": entity, "r": int(rows), "loc": location,
             "ws": window[0] if window else None, "we": window[1] if window else None,
             "s": started_at, "f": finished_at},
        )


def errors_frame(result: ValidationResult, rules: dict, batch_id: str) -> pd.DataFrame:
    f = result.findings
    if f.empty:
        return pd.DataFrame(columns=ERROR_COLUMNS)
    out = f.assign(
        _batch_id=batch_id,
        detected_at=pd.Timestamp(datetime.now(UTC)),
        rule_type=f["rule_id"].map(lambda r: rules[r]["tipo"]),
        severidad=f["rule_id"].map(lambda r: rules[r]["severidad"]),
    )
    return out[ERROR_COLUMNS]


def record_quality(engine: Engine, result: ValidationResult, rules: dict, batch_id: str) -> None:
    """Reemplaza los errores y contadores del lote (idempotente ante reprocesos)."""
    errors = errors_frame(result, rules, batch_id)
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM gold.dq_errors WHERE _batch_id = :b"), {"b": batch_id})
        if not errors.empty:
            errors.to_sql("dq_errors", con=conn, schema="gold", if_exists="append", index=False)
        conn.execute(
            text(
                """
                UPDATE gold.dq_run_metrics
                SET total = :t, valid = :v, warning = :w, invalid = :i, dq_score = :s, pct_utilizable = :u
                WHERE _batch_id = :b
                """
            ),
            {"b": batch_id, "t": result.total, "v": result.valid, "w": result.warning,
             "i": result.invalid, "s": result.dq_score, "u": result.pct_utilizable},
        )
    print(
        f"[DQ] total={result.total} valid={result.valid} warning={result.warning} "
        f"invalid={result.invalid} score={result.dq_score}% utilizable={result.pct_utilizable}% errores={len(errors)}"
    )
