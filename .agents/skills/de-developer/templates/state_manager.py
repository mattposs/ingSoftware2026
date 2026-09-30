"""
state_manager.py
Helper genérico para consultar y persistir marcas de agua (Watermarking)
de pipelines ETL incrementales.
"""

import json
import os
from datetime import datetime, timezone


class StateManager:
    """Gestiona el watermark incremental de cada entidad/pipeline en formato JSON."""

    def __init__(self, state_file_path: str = "config/pipeline_state.json"):
        self.state_file_path = state_file_path
        self._ensure_file_exists()

    def _ensure_file_exists(self):
        if not os.path.exists(self.state_file_path):
            os.makedirs(os.path.dirname(self.state_file_path), exist_ok=True)
            with open(self.state_file_path, "w", encoding="utf-8") as f:
                json.dump({}, f)

    def get_watermark(self, domain: str, entity: str, default: str = "1970-01-01T00:00:00Z") -> str:
        """Obtiene la última marca de agua registrada para un dominio y entidad."""
        key = f"{domain}.{entity}"
        with open(self.state_file_path, "r", encoding="utf-8") as f:
            state = json.load(f)
        return state.get(key, {}).get("last_watermark", default)

    def set_watermark(self, domain: str, entity: str, new_watermark: str, last_batch_id: str | None = None):
        """Actualiza la marca de agua tras confirmar la persistencia exitosa del lote."""
        key = f"{domain}.{entity}"
        with open(self.state_file_path, "r", encoding="utf-8") as f:
            state = json.load(f)

        state[key] = {
            "last_watermark": new_watermark,
            "last_batch_id": last_batch_id,
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
        with open(self.state_file_path, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)
        print(f"[STATE] Watermark actualizado para '{key}': {new_watermark}")
