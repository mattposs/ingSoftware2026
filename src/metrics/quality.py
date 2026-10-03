"""
quality.py
Registro de la corrida (gold.dq_run_metrics) y de los errores detectados (gold.dq_errors).
Data Quality Score = (VALID + WARNING) / total × 100 (RF07, decisión D2).
"""

from datetime import UTC, datetime

import pandas as pd
from sqlalchemy import Engine, text

from src.validation.engine import ValidationResult

ERROR_COLUMNS = [
    "_batch_id", "detected_at", "measured_at", "source", "field_id",
    "variable", "rule_id", "rule_type", "action", "severidad", "detalle",
]


def start_run(engine: Engine, batch_id: str) -> None:
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO gold.dq_run_metrics (_batch_id, run_start, status)
                VALUES (:b, now(), 'running')
                ON CONFLICT (_batch_id) DO UPDATE SET run_end = NULL, status = 'running'
                """
            ),
            {"b": batch_id},
        )


def finish_run(engine: Engine, batch_id: str, status: str) -> None:
    with engine.begin() as conn:
        conn.execute(
            text("UPDATE gold.dq_run_metrics SET run_end = now(), status = :s WHERE _batch_id = :b"),
            {"b": batch_id, "s": status},
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
                SET total = :t, valid = :v, warning = :w, invalid = :i, dq_score = :s
                WHERE _batch_id = :b
                """
            ),
            {"b": batch_id, "t": result.total, "v": result.valid, "w": result.warning,
             "i": result.invalid, "s": result.dq_score},
        )
    print(
        f"[DQ] total={result.total} valid={result.valid} warning={result.warning} "
        f"invalid={result.invalid} score={result.dq_score}% errores={len(errors)}"
    )
