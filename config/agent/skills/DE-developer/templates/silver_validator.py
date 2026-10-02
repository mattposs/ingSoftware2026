"""
silver_validator.py
Módulo genérico para evaluación vectorizada de reglas de Data Quality y
bifurcación hacia Silver (Clean Parquet) y Quarantine (Rejected Parquet).

Soporta tres estados por registro:
    VALID   -> no falló ninguna regla.
    WARNING -> solo fallaron reglas de advertencia: va a Silver marcado.
    INVALID -> falló al menos una regla de rechazo: va a Quarantine con los motivos.
"""

import pandas as pd

try:  # importado como paquete: from templates.silver_validator import ...
    from .bronze_writer import write_to_parquet_lake
except ImportError:  # ejecutado desde la carpeta templates/
    from bronze_writer import write_to_parquet_lake


def _failures(rules: dict[str, pd.Series]) -> pd.DataFrame:
    # Matriz de fallos: True = la regla falló. Un NaN en la condición cuenta como fallo.
    return pd.DataFrame({code: ~cond.fillna(False).astype(bool) for code, cond in rules.items()})


def _codes(failures: pd.DataFrame) -> pd.Series:
    return failures.apply(lambda row: ";".join(row.index[row].tolist()), axis=1)


def validate_and_quarantine(
    df: pd.DataFrame,
    rules: dict[str, pd.Series],
    domain: str,
    entity: str,
    batch_id: str,
    warning_rules: dict[str, pd.Series] | None = None,
    base_path: str = "storage"
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Evalúa reglas booleanas declarativas sobre el lote y bifurca los registros.

    Args:
        df: DataFrame del batch que se está procesando.
        rules: reglas de RECHAZO { "CODIGO": Serie booleana (True = válido) }.
        warning_rules: reglas de ADVERTENCIA con la misma estructura (opcional).
        domain / entity: ubicación en el lake.
        batch_id: identificador del lote (se usa para nombrar los archivos).
        base_path: raíz del lake.

    Returns:
        (df_silver con columnas dq_status y _dq_warnings, df_quarantine con _rejection_reasons)
    """
    reject = _failures(rules) if rules else pd.DataFrame(index=df.index)
    warn = _failures(warning_rules) if warning_rules else pd.DataFrame(index=df.index)

    is_invalid = reject.any(axis=1) if not reject.empty else pd.Series(False, index=df.index)
    has_warning = warn.any(axis=1) if not warn.empty else pd.Series(False, index=df.index)

    df_valid = df[~is_invalid].copy()
    df_valid["dq_status"] = has_warning[~is_invalid].map({True: "WARNING", False: "VALID"})
    df_valid["_dq_warnings"] = _codes(warn[~is_invalid]).replace("", None) if not warn.empty else None

    df_invalid = df[is_invalid].copy()
    if not df_invalid.empty:
        df_invalid["_rejection_reasons"] = _codes(reject[is_invalid])
        df_invalid["_rejected_at"] = pd.Timestamp.now(tz="UTC")

    # replace=True: reprocesar el mismo lote regenera Silver/Quarantine sin duplicar.
    write_to_parquet_lake(df_invalid, "quarantine", domain, entity, batch_id, base_path, replace=True)
    write_to_parquet_lake(df_valid, "silver", domain, entity, batch_id, base_path, replace=True)
    print(f"[SILVER] {len(df_valid)} limpios ({int(has_warning[~is_invalid].sum())} con warning) | "
          f"[QUARANTINE] {len(df_invalid)} rechazados.")

    return df_valid, df_invalid
