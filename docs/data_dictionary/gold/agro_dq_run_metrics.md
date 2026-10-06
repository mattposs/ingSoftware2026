# Diccionario de Datos: `agro_dq_run_metrics_gold`

**Capa:** `GOLD`  
**Dominio:** `agro` | **Entidad:** `dq_run_metrics`  
**Ubicación / Destino:** `postgres:gold.dq_run_metrics`  
**Última Catalogación:** `2026-10-05T22:33:53.738686+00:00`  

> Resumen de cada corrida del pipeline y su Data Quality Score.

## Definición de Columnas

| Columna | Tipo de Dato | Nulos observados | Ejemplo | Descripción |
|---|---|---|---|---|
| `_batch_id` | `str` | No | `54097779-734c-48c0-adbf-61f4b283aa89` | Identificador UUID de la corrida que generó el registro (linaje). |
| `run_start` | `datetime64[us, UTC]` | No | `2026-10-05 22:32:05.757785+00:00` | Inicio de la corrida (UTC). |
| `run_end` | `datetime64[us, UTC]` | No | `2026-10-05 22:32:09.443668+00:00` | Fin de la corrida (UTC); vacío si sigue en curso o falló antes de terminar. |
| `status` | `str` | No | `ok` | Estado de la corrida: running, ok o failed. |
| `total` | `int64` | No | `6` | Registros recibidos en el lote. |
| `valid` | `int64` | No | `5` | Registros sin hallazgos. |
| `warning` | `int64` | No | `1` | Registros publicados con al menos un warning. |
| `invalid` | `int64` | No | `0` | Registros rechazados (enviados a quarantine). |
| `dq_score` | `float64` | No | `100.0` | Data Quality Score = (valid + warning) / total × 100. |
