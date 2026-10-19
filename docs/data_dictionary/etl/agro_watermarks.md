# Diccionario de Datos: `agro_watermarks_etl`

**Capa:** `ETL`  
**Dominio:** `agro` | **Entidad:** `watermarks`  
**Ubicación / Destino:** `postgres:etl.watermarks`  
**Última Catalogación:** `2026-10-14T01:02:01.188675+00:00`  

> Control de carga incremental: fin de la última ventana extraída por fuente.

## Definición de Columnas

| Columna | Tipo de Dato | Nulos observados | Ejemplo | Descripción |
|---|---|---|---|---|
| `domain` | `str` | No | `agro` | Dominio del pipeline (agro). |
| `entity` | `str` | No | `open_meteo` | Fuente a la que corresponde el watermark. |
| `watermark` | `datetime64[us, UTC]` | No | `2026-10-09 23:00:00+00:00` | Fin de la última ventana extraída de la fuente (UTC). La próxima corrida pide (watermark, ahora]. |
| `last_batch_id` | `str` | No | `9b1c8b81-0295-4b2f-83f8-5d3c13ed38e5` | Corrida que movió el watermark por última vez. |
| `updated_at` | `datetime64[us, UTC]` | No | `2026-10-14 01:01:53.533142+00:00` | Última actualización del watermark. |
