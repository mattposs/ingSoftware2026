# Diccionario de Datos: `agro_dq_run_metrics_gold`

**Capa:** `GOLD`  
**Dominio:** `agro` | **Entidad:** `dq_run_metrics`  
**Ubicación / Destino:** `postgres:gold.dq_run_metrics`  
**Última Catalogación:** `2026-10-26T23:06:38.872103+00:00`  

> Resumen de cada corrida del pipeline: Data Quality Score y monitoreo (estado, duración y frescura).

## Definición de Columnas

| Columna | Tipo de Dato | Nulos observados | Ejemplo | Descripción |
|---|---|---|---|---|
| `_batch_id` | `str` | No | `4d5e5f19-f0b0-41f9-9be3-df7e8ffc4184` | Identificador UUID de la corrida que generó el registro (linaje). |
| `run_start` | `datetime64[us, UTC]` | No | `2026-10-26 23:02:42.542173+00:00` | Inicio de la corrida (UTC). |
| `run_end` | `datetime64[us, UTC]` | No | `2026-10-26 23:02:42.577302+00:00` | Fin de la corrida (UTC); vacío si sigue en curso o falló antes de terminar. |
| `status` | `str` | No | `failed` | Estado de la corrida: running, ok o failed. |
| `total` | `float64` | Sí (50.0%) | `8.0` | Registros recibidos en el lote. |
| `valid` | `float64` | Sí (50.0%) | `7.0` | Registros sin hallazgos. |
| `warning` | `float64` | Sí (50.0%) | `0.0` | Registros publicados con al menos un warning. |
| `invalid` | `float64` | Sí (50.0%) | `1.0` | Registros rechazados (enviados a quarantine). |
| `dq_score` | `float64` | Sí (50.0%) | `87.5` | Data Quality Score estricto = valid / total × 100 (los warning no cuentan). |
| `pct_utilizable` | `float64` | Sí (50.0%) | `87.5` | % utilizable = (valid + warning) / total × 100: registros publicados en Silver. |
| `run_status` | `str` | No | `FAILED` | Resultado de la corrida para el monitoreo: SUCCESS o FAILED (alerta AL01). NULL en corridas anteriores. |
| `started_at` | `datetime64[us, UTC]` | No | `2026-10-26 23:02:42.542173+00:00` | Inicio de la etapa o de la corrida (UTC). |
| `finished_at` | `datetime64[us, UTC]` | No | `2026-10-26 23:02:42.577302+00:00` | Fin de la etapa o de la corrida (UTC). |
| `duration_seconds` | `float64` | No | `0.04` | Duración de la corrida en segundos, de started_at a finished_at (RNF09). |
| `last_measured_at` | `datetime64[us, UTC]` | Sí (50.0%) | `2026-10-26 23:00:00+00:00` | Timestamp máximo de medición de los registros válidos del lote (para la frescura, RNF08). |
