"""
state.py
Watermarks de carga incremental en la tabla etl.watermarks (skill de-developer: state_manager).

El watermark guarda el FIN DE LA VENTANA consultada (no el máximo timestamp de los
datos): así un registro con timestamp futuro o un lote vacío no lo corrompen, y los
registros rechazados no se vuelven a extraer. La ventana siguiente es (watermark, fin].
"""

from datetime import datetime

from sqlalchemy import Engine, text


class WatermarkStore:
    def __init__(self, engine: Engine):
        self.engine = engine

    def get(self, domain: str, entity: str) -> datetime | None:
        with self.engine.connect() as conn:
            return conn.execute(
                text("SELECT watermark FROM etl.watermarks WHERE domain = :d AND entity = :e"),
                {"d": domain, "e": entity},
            ).scalar_one_or_none()

    def set(self, domain: str, entity: str, watermark: datetime, batch_id: str) -> None:
        with self.engine.begin() as conn:
            conn.execute(
                text(
                    """
                    INSERT INTO etl.watermarks (domain, entity, watermark, last_batch_id, updated_at)
                    VALUES (:d, :e, :w, :b, now())
                    ON CONFLICT (domain, entity) DO UPDATE
                    SET watermark = EXCLUDED.watermark,
                        last_batch_id = EXCLUDED.last_batch_id,
                        updated_at = now()
                    """
                ),
                {"d": domain, "e": entity, "w": watermark, "b": batch_id},
            )
        print(f"[STATE] Watermark {domain}.{entity} = {watermark.isoformat()}")
