# Diccionario de Datos: `agro_dq_run_metrics_gold`

**Capa:** `GOLD`  
**Dominio:** `agro` | **Entidad:** `dq_run_metrics`  
**Ubicación / Destino:** `postgres:gold.dq_run_metrics`  
**Última Catalogación:** `2026-10-02T22:15:41.409178+00:00`  

> Resumen de cada corrida del pipeline y su Data Quality Score.

## Definición de Columnas

| Columna | Tipo de Dato | Nulos observados | Ejemplo | Descripción |
|---|---|---|---|---|
| `_batch_id` | `str` | No | `ca89ae95-c758-435c-86e9-82d67695c9e9` | Identificador UUID de la corrida que generó el registro (linaje). |
| `run_start` | `datetime64[us, UTC]` | No | `2026-10-02 22:11:08.378468+00:00` | Inicio de la corrida (UTC). |
| `run_end` | `datetime64[us, UTC]` | No | `2026-10-02 22:11:09.237352+00:00` | Fin de la corrida (UTC); vacío si sigue en curso o falló antes de terminar. |
| `status` | `str` | No | `ok` | Estado de la corrida: running, ok o failed. |
| `total` | `int64` | No | `1580` | Registros recibidos en el lote. |
| `valid` | `int64` | No | `1510` | Registros sin hallazgos. |
| `warning` | `int64` | No | `30` | Registros publicados con al menos un warning. |
| `invalid` | `int64` | No | `40` | Registros rechazados (enviados a quarantine). |
| `dq_score` | `float64` | No | `97.47` | Data Quality Score = (valid + warning) / total × 100. |
