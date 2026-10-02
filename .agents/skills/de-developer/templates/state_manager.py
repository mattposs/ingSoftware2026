"""
state_manager.py
Helper genérico para consultar y persistir marcas de agua (Watermarking)
de pipelines ETL incrementales.

Qué guardar como watermark: el FIN DE LA VENTANA consultada a la fuente, no el
máximo timestamp de los datos limpios. Si se usa el máximo de los datos:
  - un registro con timestamp futuro adelanta el watermark y se pierden datos;
  - si los registros más nuevos fueron rechazados, se vuelven a extraer (duplicados);
  - un lote vacío deja el watermark en "NaT".
La ventana siguiente es (watermark, ahora]: inicio EXCLUSIVO para no repetir el borde.

Este helper usa un JSON local (útil para prototipos). En producción guardar el
watermark en la base de datos (ej. tabla etl.watermarks) junto con los datos.
"""

import json
import os
from datetime import datetime, timezone


class StateManager:
    """Gestiona el watermark incremental de cada entidad/pipeline en formato JSON."""

    def __init__(self, state_file_path: str = "state/pipeline_state.json"):
        self.state_file_path = state_file_path
        self._ensure_file_exists()

    def _ensure_file_exists(self):
        if not os.path.exists(self.state_file_path):
            parent = os.path.dirname(self.state_file_path)
            if parent:
                os.makedirs(parent, exist_ok=True)
            with open(self.state_file_path, "w", encoding="utf-8") as f:
                json.dump({}, f)

    def get_watermark(self, domain: str, entity: str, default: str | None = None) -> str | None:
        """Obtiene la última marca de agua registrada (None = primera corrida)."""
        key = f"{domain}.{entity}"
        with open(self.state_file_path, encoding="utf-8") as f:
            state = json.load(f)
        return state.get(key, {}).get("last_watermark", default)

    def set_watermark(self, domain: str, entity: str, new_watermark: str, last_batch_id: str | None = None):
        """Actualiza la marca de agua tras confirmar la persistencia del lote en Bronze."""
        key = f"{domain}.{entity}"
        with open(self.state_file_path, encoding="utf-8") as f:
            state = json.load(f)

        state[key] = {
            "last_watermark": new_watermark,
            "last_batch_id": last_batch_id,
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
        tmp = self.state_file_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)
        os.replace(tmp, self.state_file_path)  # escritura atómica
        print(f"[STATE] Watermark actualizado para '{key}': {new_watermark}")
