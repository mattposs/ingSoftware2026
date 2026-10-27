"""
backfill_monitoreo.py
Completa las columnas de monitoreo (run_status, started_at, finished_at, duration_seconds, last_measured_at)
de corridas anteriores al monitoreo, a partir de datos que ya están registrados. No inventa nada:

  - run_status:        status de la corrida ('ok' -> SUCCESS, 'failed' -> FAILED).
  - started_at:        el inicio más temprano de sus etapas en gold.pipeline_layer_metrics (si no hay, run_start).
  - finished_at:       run_end.
  - duration_seconds:  finished_at - started_at.
  - last_measured_at:  máximo timestamp de los registros del lote en Silver (Parquet del lake indicado).

Solo toca filas con run_status NULL. Se usó para las bases de la POC (agro_poc y agro_poc_grafana), que no
tienen scheduler y por eso nunca migraron. En dev, staging y prod las corridas viejas quedan en NULL.

    python scripts/backfill_monitoreo.py --base agro_poc --lake storage/poc
"""

import argparse
import sys
from pathlib import Path

import pandas as pd
from dotenv import dotenv_values
from sqlalchemy import create_engine, text

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.common import lake, migrations  # noqa: E402
from src.config import load_pipeline  # noqa: E402
from src.metrics import quality  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Backfill de las columnas de monitoreo desde datos registrados")
    parser.add_argument("--base", required=True, help="base de datos (ej. agro_poc)")
    parser.add_argument("--lake", required=True, help="raíz del lake de esa base (ej. storage/poc)")
    args = parser.parse_args()
    if args.base in ("agro_dev", "agro_staging", "agro_prod"):
        sys.exit("Este backfill es para bases sin scheduler (POC). En los entornos las corridas viejas quedan en NULL.")

    env = {**dotenv_values(ROOT / ".env.example"), **dotenv_values(ROOT / ".env")}
    engine = create_engine(f"postgresql+psycopg://{env['POSTGRES_USER']}:{env['POSTGRES_PASSWORD']}"
                           f"@localhost:{env.get('POSTGRES_PORT', '5432')}/{args.base}")
    migrations.apply(engine)
    cfg = load_pipeline("staging")
    storage = (ROOT / args.lake) if not Path(args.lake).is_absolute() else Path(args.lake)

    with engine.connect() as conn:
        runs = conn.execute(text("SELECT _batch_id FROM gold.dq_run_metrics WHERE run_status IS NULL "
                                 "ORDER BY run_start")).scalars().all()
    for batch in runs:
        silver = lake.read_layer(storage, "silver", cfg["domain"], cfg["entity"], batch)
        last = quality.last_measured_at(silver) if not silver.empty else None
        with engine.begin() as conn:
            conn.execute(text("""
                UPDATE gold.dq_run_metrics r SET
                    run_status = CASE r.status WHEN 'ok' THEN 'SUCCESS' WHEN 'failed' THEN 'FAILED' END,
                    started_at = COALESCE((SELECT min(started_at) FROM gold.pipeline_layer_metrics l
                                           WHERE l._batch_id = r._batch_id), r.run_start),
                    finished_at = r.run_end,
                    last_measured_at = :last
                WHERE r._batch_id = :b AND r.run_status IS NULL AND r.status IN ('ok', 'failed')
            """), {"b": batch, "last": last})
            conn.execute(text("""
                UPDATE gold.dq_run_metrics SET duration_seconds =
                    round(extract(epoch FROM finished_at - started_at)::numeric, 2)
                WHERE _batch_id = :b AND finished_at IS NOT NULL
            """), {"b": batch})
    with engine.connect() as conn:
        out = pd.read_sql(text("SELECT _batch_id, status, run_status, started_at, finished_at, duration_seconds, "
                               "last_measured_at FROM gold.dq_run_metrics ORDER BY run_start"), conn)
    print(f"[BACKFILL] {args.base}: {len(runs)} corridas completadas.")
    print(out.to_string(index=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
