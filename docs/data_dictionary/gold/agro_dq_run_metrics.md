# Diccionario de Datos: `agro_dq_run_metrics_gold`

**Capa:** `GOLD`  
**Dominio:** `agro` | **Entidad:** `dq_run_metrics`  
**Ubicación / Destino:** `postgres:gold.dq_run_metrics`  
**Última Catalogación:** `2026-10-14T01:02:00.964897+00:00`  

> Resumen de cada corrida del pipeline y su Data Quality Score.

## Definición de Columnas

| Columna | Tipo de Dato | Nulos observados | Ejemplo | Descripción |
|---|---|---|---|---|
| `_batch_id` | `str` | No | `9b1c8b81-0295-4b2f-83f8-5d3c13ed38e5` | Identificador UUID de la corrida que generó el registro (linaje). |
| `run_start` | `datetime64[us, UTC]` | No | `2026-10-14 01:01:53.421180+00:00` | Inicio de la corrida (UTC). |
| `run_end` | `datetime64[us, UTC]` | No | `2026-10-14 01:01:55.844484+00:00` | Fin de la corrida (UTC); vacío si sigue en curso o falló antes de terminar. |
| `status` | `str` | No | `ok` | Estado de la corrida: running, ok o failed. |
| `total` | `int64` | No | `1339` | Registros recibidos en el lote. |
| `valid` | `int64` | No | `1191` | Registros sin hallazgos. |
| `warning` | `int64` | No | `57` | Registros publicados con al menos un warning. |
| `invalid` | `int64` | No | `91` | Registros rechazados (enviados a quarantine). |
| `dq_score` | `float64` | No | `88.95` | Data Quality Score estricto = valid / total × 100 (los warning no cuentan). |
| `pct_utilizable` | `float64` | No | `93.2` | % utilizable = (valid + warning) / total × 100: registros publicados en Silver. |
