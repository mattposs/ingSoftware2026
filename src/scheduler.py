"""
scheduler.py
Ejecución programada del pipeline (EDT 7.3, RNF01): corre una corrida incremental
cada PIPELINE_INTERVAL_SECONDS (por defecto 15 minutos, la frecuencia de los sensores).
Una corrida fallida se registra y no detiene las siguientes.

    python -m src.scheduler
"""

import os
import time
import traceback
from datetime import UTC, datetime

from src import pipeline
from src.common import db
from src.config import get_settings


def main() -> None:
    interval = int(os.getenv("PIPELINE_INTERVAL_SECONDS", "900"))
    engine = db.get_engine()
    print(f"[SCHEDULER] Entorno {get_settings().environment.upper()} · corrida cada {interval}s.")
    while True:
        started = time.monotonic()
        print(f"[SCHEDULER] {datetime.now(UTC):%Y-%m-%d %H:%M:%S} UTC - inicio de corrida")
        try:
            pipeline.run_all(engine)
        except Exception:
            traceback.print_exc()
            print("[SCHEDULER] La corrida falló; se reintenta en el próximo ciclo.")
        time.sleep(max(0, interval - (time.monotonic() - started)))


if __name__ == "__main__":
    main()
