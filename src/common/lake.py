"""
lake.py
Linaje y persistencia en el lake Parquet (skill de-developer: bronze_writer).

Ruta: {base}/{layer}/{domain}/{entity}/year=YYYY/month=MM/{prefix}_{batch_id}.parquet
Prefijos: bronze -> batch_, silver -> clean_, quarantine -> rejected_.
"""

import uuid
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

LAYER_PREFIX = {"bronze": "batch", "silver": "clean", "quarantine": "rejected"}


def new_batch_id() -> str:
    return str(uuid.uuid4())


def enrich_with_lineage(df: pd.DataFrame, source_system: str, batch_id: str) -> pd.DataFrame:
    """Agrega las columnas de linaje obligatorias (_batch_id, _ingested_at, _source_system)."""
    out = df.copy()
    out["_batch_id"] = batch_id
    out["_ingested_at"] = pd.Timestamp(datetime.now(UTC))
    out["_source_system"] = source_system
    return out


def write_parquet(
    df: pd.DataFrame,
    base_path: Path,
    layer: str,
    domain: str,
    entity: str,
    batch_id: str,
    replace: bool = False,
) -> Path | None:
    """
    Escribe un lote en el lake.

    Bronze es inmutable: nunca se reescribe un lote. Silver y Quarantine son derivados y
    pueden regenerarse desde Bronze (reproceso / backfill, RNF03) con replace=True, que
    reemplaza los archivos previos de ese mismo lote.
    Un DataFrame vacío no genera archivo y devuelve None.
    """
    if replace and layer == "bronze":
        raise ValueError("Bronze es append-only: no se puede reemplazar un lote.")

    existing = list(Path(base_path, layer, domain, entity).glob(f"year=*/month=*/{LAYER_PREFIX[layer]}_{batch_id}.parquet"))
    if existing and not replace:
        raise FileExistsError(f"{existing[0]} ya existe: el lote ya fue escrito.")
    for old in existing:
        old.unlink()

    if df.empty:
        print(f"[{layer.upper()}] Lote vacío para {domain}/{entity}: no se escribe archivo.")
        return None

    now = datetime.now(UTC)
    target_dir = Path(base_path, layer, domain, entity, f"year={now.year}", f"month={now.month:02d}")
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / f"{LAYER_PREFIX[layer]}_{batch_id}.parquet"

    df.to_parquet(target, engine="pyarrow", compression="snappy", index=False)
    print(f"[{layer.upper()}] {len(df)} registros -> {target}")
    return target


def read_layer(
    base_path: Path,
    layer: str,
    domain: str,
    entity: str,
    batch_id: str | None = None,
) -> pd.DataFrame:
    """Lee todos los archivos de una capa/entidad, o solo los del batch indicado."""
    pattern = f"{LAYER_PREFIX[layer]}_{batch_id or '*'}.parquet"
    files = sorted(Path(base_path, layer, domain, entity).glob(f"year=*/month=*/{pattern}"))
    if not files:
        return pd.DataFrame()
    return pd.concat([pd.read_parquet(f) for f in files], ignore_index=True)
