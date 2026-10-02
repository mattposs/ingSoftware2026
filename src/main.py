"""
Punto de entrada del pipeline.

    python -m src.main                         # corrida incremental completa
    python -m src.main --source iot_simulator  # solo una fuente
    python -m src.main --reprocess <batch_id>  # backfill desde Bronze
"""

import argparse
import time

from src import pipeline


def main() -> None:
    parser = argparse.ArgumentParser(description="Pipeline DataOps agroclimático (Medallion)")
    parser.add_argument("--source", action="append", choices=list(pipeline.CONNECTORS),
                        help="limitar la ingesta a una fuente (se puede repetir)")
    parser.add_argument("--reprocess", metavar="BATCH_ID", help="regenerar Silver y Gold de un lote existente")
    args = parser.parse_args()

    started = time.perf_counter()
    if args.reprocess:
        pipeline.reprocess(args.reprocess)
    else:
        pipeline.run_all(sources=args.source)
    print(f"[PIPELINE] Duración: {time.perf_counter() - started:.1f}s (objetivo RNF08: < 300s)")


if __name__ == "__main__":
    main()
