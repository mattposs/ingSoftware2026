# Diccionario de Datos: `agro_watermarks_etl`

**Capa:** `ETL`  
**Dominio:** `agro` | **Entidad:** `watermarks`  
**Ubicación / Destino:** `postgres:etl.watermarks`  
**Última Catalogación:** `2026-10-02T22:15:41.651297+00:00`  

> Control de carga incremental: fin de la última ventana extraída por fuente.

## Definición de Columnas

| Columna | Tipo de Dato | Nulos observados | Ejemplo | Descripción |
|---|---|---|---|---|
| `domain` | `str` | No | `agro` | Dominio del pipeline (agro). |
| `entity` | `str` | No | `open_meteo` | Fuente a la que corresponde el watermark. |
| `watermark` | `datetime64[us, UTC]` | No | `2026-09-27 23:00:00+00:00` | Fin de la última ventana extraída de la fuente (UTC). La próxima corrida pide (watermark, ahora]. |
| `last_batch_id` | `str` | No | `ca89ae95-c758-435c-86e9-82d67695c9e9` | Corrida que movió el watermark por última vez. |
| `updated_at` | `datetime64[us, UTC]` | No | `2026-10-02 22:11:06.671164+00:00` | Última actualización del watermark. |
