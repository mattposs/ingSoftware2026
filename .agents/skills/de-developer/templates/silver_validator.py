"""
silver_validator.py
Módulo genérico para evaluación vectorizada de reglas de Data Quality y
bifurcación hacia Silver (Clean Parquet) y Quarantine (Rejected Parquet).
"""

import pandas as pd
from bronze_writer import write_to_parquet_lake


def validate_and_quarantine(
    df: pd.DataFrame,
    rules: dict[str, pd.Series],
    domain: str,
    entity: str,
    base_path: str = "data"
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Evalúa un conjunto declarativo de reglas de calidad booleanas sobre el DataFrame.
    Bifurca los datos válidos hacia Silver y los datos que violan reglas hacia Quarantine,
    adjuntando en estos últimos la lista de motivos de fallo.

    Args:
        df: DataFrame de Pandas correspondiente al batch que se está procesando.
        rules: Diccionario con la estructura:
               { "CODIGO_ERROR": Serie booleana donde True = Válido y False = Inválido }
        domain: Dominio del negocio (ej. 'iot', 'finanzas').
        entity: Entidad procesada (ej. 'sensores', 'facturas').
        base_path: Ruta base del storage de datos.

    Returns:
        tuple[pd.DataFrame, pd.DataFrame]: (df_validos, df_rechazados)
    """
    failure_matrix = pd.DataFrame(
        {rule_code: ~condition for rule_code, condition in rules.items()}
    )

    is_valid_mask = ~failure_matrix.any(axis=1)

    df_valid = df[is_valid_mask].copy()
    df_invalid = df[~is_valid_mask].copy()

    if not df_invalid.empty:
        rejection_reasons = failure_matrix[~is_valid_mask].apply(
            lambda row: ";".join(row.index[row].tolist()), axis=1
        )
        df_invalid["_rejection_reasons"] = rejection_reasons
        df_invalid["_rejected_at"] = pd.Timestamp.now(tz="UTC")
        write_to_parquet_lake(
            df_invalid, layer="quarantine", domain=domain, entity=entity, base_path=base_path
        )
        print(f"[QUARANTINE] {len(df_invalid)} registros rechazados almacenados.")

    write_to_parquet_lake(
        df_valid, layer="silver", domain=domain, entity=entity, base_path=base_path
    )
    print(f"[SILVER] {len(df_valid)} registros limpios almacenados.")

    return df_valid, df_invalid
