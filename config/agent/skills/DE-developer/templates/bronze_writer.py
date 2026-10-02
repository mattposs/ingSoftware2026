"""
bronze_writer.py
Módulo genérico para enriquecer datos crudos con metadatos técnicos de auditoría
y persistirlos en formato Apache Parquet particionado.

Convención de nombres (sección 3 de la skill):
    bronze     -> batch_{batch_id}.parquet     (inmutable, append-only)
    silver     -> clean_{batch_id}.parquet     (derivado, se puede regenerar)
    quarantine -> rejected_{batch_id}.parquet  (derivado, se puede regenerar)
"""

import os
import uuid
from datetime import datetime, timezone
from glob import glob

import pandas as pd

LAYER_PREFIX = {"bronze": "batch", "silver": "clean", "quarantine": "rejected"}


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
    batch_id: str,
    base_path: str = "storage",
    replace: bool = False
) -> str | None:
    """
    Persiste un lote particionado por año y mes en Parquet con compresión Snappy.

    Ruta generada:
    {base_path}/{layer}/{domain}/{entity}/year={YYYY}/month={MM}/{prefijo}_{batch_id}.parquet

    - El batch_id se recibe explícito: así funciona también con DataFrames vacíos.
    - Bronze nunca se reescribe. Silver/Quarantine aceptan replace=True para reprocesos.
    - Un DataFrame vacío no genera archivo y devuelve None.
    """
    if replace and layer == "bronze":
        raise ValueError("Bronze es append-only: no se puede reemplazar un lote.")

    file_name = f"{LAYER_PREFIX[layer]}_{batch_id}.parquet"
    existing = glob(os.path.join(base_path, layer, domain, entity, "year=*", "month=*", file_name))
    if existing and not replace:
        raise FileExistsError(f"{existing[0]} ya existe: el lote ya fue escrito.")
    for old in existing:
        os.remove(old)

    if df.empty:
        print(f"[{layer.upper()}] Lote vacío: no se escribe archivo.")
        return None

    now = datetime.now(timezone.utc)
    target_dir = os.path.join(
        base_path, layer, domain, entity, f"year={now.year}", f"month={now.month:02d}"
    )
    os.makedirs(target_dir, exist_ok=True)
    target_file = os.path.join(target_dir, file_name)

    df.to_parquet(target_file, engine="pyarrow", compression="snappy", index=False)
    print(f"[{layer.upper()}] Persistido exitosamente: {target_file}")
    return target_file
