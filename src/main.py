"""
Punto de entrada del pipeline.

    python -m src.main                         # corrida incremental completa
    python -m src.main --source iot_simulator  # solo una fuente
    python -m src.main --reprocess <batch_id>  # backfill desde Bronze
    python -m src.main --env staging           # entorno dev (defecto), staging o prod

Solo para probar las alertas (apagadas por defecto):
    PIPELINE_FORCE_FAILURE=true      la corrida falla a propósito y queda registrada como FAILED (AL01)
    PIPELINE_IOT_ERROR_RATE=0.5      el simulador IoT inyecta más errores y baja el DQ Score (AL02)
"""

import argparse
import os
import time


def main() -> None:
    parser = argparse.ArgumentParser(description="Pipeline DataOps agroclimático (Medallion)")
    parser.add_argument("--source", action="append", choices=["open_meteo", "iot_simulator"],
                        help="limitar la ingesta a una fuente (se puede repetir)")
    parser.add_argument("--reprocess", metavar="BATCH_ID", help="regenerar Silver y Gold de un lote existente")
    parser.add_argument("--env", choices=["dev", "staging", "prod"], help="entorno (por defecto APP_ENV o dev)")
    args = parser.parse_args()
    if args.env:
        os.environ["APP_ENV"] = args.env

    from src import pipeline  # después de fijar el entorno
    from src.common import db, migrations
    from src.config import get_settings

    settings = get_settings()
    print(f"[PIPELINE] Entorno: {settings.environment.upper()} · base {settings.database_url.rsplit('/', 1)[-1]}"
          f" · lake {settings.storage_path}")

    migrations.ensure_schema(db.get_engine())   # bases creadas antes de las columnas de monitoreo
    started = time.perf_counter()
    if args.reprocess:
        pipeline.reprocess(args.reprocess)
    else:
        pipeline.run_all(sources=args.source)
    print(f"[PIPELINE] Duración: {time.perf_counter() - started:.1f}s (objetivo RNF08: < 300s)")


if __name__ == "__main__":
    main()
