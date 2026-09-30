"""
bronze_writer.py
Módulo genérico para enriquecer datos crudos con metadatos técnicos de auditoría
y persistirlos en formato Apache Parquet particionado (Append-only).
"""

import os
import uuid
from datetime import datetime, timezone
import pandas as pd


def enrich_with_lineage(
    df: pd.DataFrame,
    source_system: str,
    batch_id: str | None = None
) -> pd.DataFrame:
    """
    Adjunta metadatos técnicos de linaje y auditoría obligatorios a cualquier DataFrame crudo.
    
    Campos agregados:
    - _batch_id: UUID de ejecución
    - _ingested_at: Timestamp UTC de captura
    - _source_system: Nombre o identificador del conector/origen
    """
    df_enriched = df.copy()
    df_enriched["_batch_id"] = batch_id or str(uuid.uuid4())
    df_enriched["_ingested_at"] = datetime.now(timezone.utc)
    df_enriched["_source_system"] = source_system
    return df_enriched


def write_to_parquet_lake(
    df: pd.DataFrame,
    layer: str,
    domain: str,
    entity: str,
    base_path: str = "data"
) -> str:
    """
    Persiste un DataFrame particionado por año y mes en el formato Parquet con compresión Snappy.
    
    Ruta generada:
    {base_path}/{layer}/{domain}/{entity}/year={YYYY}/month={MM}/{layer}_{batch_id}.parquet
    """
    now = datetime.now(timezone.utc)
    target_dir = os.path.join(
        base_path, layer, domain, entity, f"year={now.year}", f"month={now.month:02d}"
    )
    os.makedirs(target_dir, exist_ok=True)

    batch_id = df["_batch_id"].iloc[0] if "_batch_id" in df.columns else str(uuid.uuid4())
    target_file = os.path.join(target_dir, f"{layer}_{batch_id}.parquet")

    df.to_parquet(target_file, engine="pyarrow", compression="snappy", index=False)
    print(f"[{layer.upper()}] Persistido exitosamente: {target_file}")
    return target_file
