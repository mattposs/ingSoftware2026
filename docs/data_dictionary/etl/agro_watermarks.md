# Diccionario de Datos: `agro_watermarks_etl`

**Capa:** `ETL`  
**Dominio:** `agro` | **Entidad:** `watermarks`  
**Ubicación / Destino:** `postgres:etl.watermarks`  
**Última Catalogación:** `2026-10-05T22:33:54.106305+00:00`  

> Control de carga incremental: fin de la última ventana extraída por fuente.

## Definición de Columnas

| Columna | Tipo de Dato | Nulos observados | Ejemplo | Descripción |
|---|---|---|---|---|
| `domain` | `str` | No | `agro` | Dominio del pipeline (agro). |
| `entity` | `str` | No | `open_meteo` | Fuente a la que corresponde el watermark. |
| `watermark` | `datetime64[us, UTC]` | No | `2026-09-30 23:00:00+00:00` | Fin de la última ventana extraída de la fuente (UTC). La próxima corrida pide (watermark, ahora]. |
| `last_batch_id` | `str` | No | `dbe6e15b-39eb-4e4b-9102-7e9909146eb7` | Corrida que movió el watermark por última vez. |
| `updated_at` | `datetime64[us, UTC]` | No | `2026-10-05 22:29:01.669848+00:00` | Última actualización del watermark. |
