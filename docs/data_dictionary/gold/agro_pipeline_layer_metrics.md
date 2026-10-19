# Diccionario de Datos: `agro_pipeline_layer_metrics_gold`

**Capa:** `GOLD`  
**Dominio:** `agro` | **Entidad:** `pipeline_layer_metrics`  
**Ubicación / Destino:** `postgres:gold.pipeline_layer_metrics`  
**Última Catalogación:** `2026-10-14T01:02:01.283028+00:00`  

> Qué hizo cada capa (bronze, silver, quarantine, gold) en cada lote: registros, duración y ventana incremental.

## Definición de Columnas

| Columna | Tipo de Dato | Nulos observados | Ejemplo | Descripción |
|---|---|---|---|---|
| `_batch_id` | `str` | No | `9b1c8b81-0295-4b2f-83f8-5d3c13ed38e5` | Identificador UUID de la corrida que generó el registro (linaje). |
| `layer` | `str` | No | `bronze` | Capa del pipeline: bronze, silver, quarantine o gold. |
| `entity` | `str` | No | `open_meteo` | Fuente a la que corresponde el watermark. |
| `rows` | `int64` | No | `576` | Registros que la capa procesó en el lote. |
| `location` | `str` | No | `storage/staging/bronze/agro/open_meteo/` | Dónde quedaron los datos: carpeta del lake o tabla de PostgreSQL. |
| `window_start` | `datetime64[us, UTC]` | Sí (60.0%) | `2026-10-06 23:00:00+00:00` | Solo bronze: inicio (exclusivo) de la ventana incremental pedida a la fuente. |
| `window_end` | `datetime64[us, UTC]` | Sí (60.0%) | `2026-10-09 23:00:00+00:00` | Solo bronze: fin de la ventana incremental (el nuevo watermark). |
| `started_at` | `datetime64[us, UTC]` | No | `2026-10-14 01:01:26.539856+00:00` | Inicio de la etapa (UTC). |
| `finished_at` | `datetime64[us, UTC]` | No | `2026-10-14 01:01:53.510122+00:00` | Fin de la etapa (UTC). |
