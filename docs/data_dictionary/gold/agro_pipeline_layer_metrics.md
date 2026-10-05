# Diccionario de Datos: `agro_pipeline_layer_metrics_gold`

**Capa:** `GOLD`  
**Dominio:** `agro` | **Entidad:** `pipeline_layer_metrics`  
**Ubicación / Destino:** `postgres:gold.pipeline_layer_metrics`  
**Última Catalogación:** `2026-10-05T22:33:54.201548+00:00`  

> Qué hizo cada capa (bronze, silver, quarantine, gold) en cada lote: registros, duración y ventana incremental.

## Definición de Columnas

| Columna | Tipo de Dato | Nulos observados | Ejemplo | Descripción |
|---|---|---|---|---|
| `_batch_id` | `str` | No | `dbe6e15b-39eb-4e4b-9102-7e9909146eb7` | Identificador UUID de la corrida que generó el registro (linaje). |
| `layer` | `str` | No | `bronze` | Capa del pipeline: bronze, silver, quarantine o gold. |
| `entity` | `str` | No | `open_meteo` | Fuente a la que corresponde el watermark. |
| `rows` | `int64` | No | `432` | Registros que la capa procesó en el lote. |
| `location` | `str` | No | `storage/bronze/agro/open_meteo/` | Dónde quedaron los datos: carpeta del lake o tabla de PostgreSQL. |
| `window_start` | `datetime64[us, UTC]` | Sí (66.67%) | `2026-09-27 23:00:00+00:00` | Solo bronze: inicio (exclusivo) de la ventana incremental pedida a la fuente. |
| `window_end` | `datetime64[us, UTC]` | Sí (66.67%) | `2026-09-30 23:00:00+00:00` | Solo bronze: fin de la ventana incremental (el nuevo watermark). |
| `started_at` | `datetime64[us, UTC]` | No | `2026-10-05 22:28:54.666047+00:00` | Inicio de la etapa (UTC). |
| `finished_at` | `datetime64[us, UTC]` | No | `2026-10-05 22:29:01.661555+00:00` | Fin de la etapa (UTC). |
