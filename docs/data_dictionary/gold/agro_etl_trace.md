# Diccionario de Datos: `agro_etl_trace_gold`

**Capa:** `GOLD`  
**Dominio:** `agro` | **Entidad:** `etl_trace`  
**Ubicación / Destino:** `postgres:gold.etl_trace`  
**Última Catalogación:** `2026-10-14T01:02:01.366698+00:00`  

> Registros de muestra de cada lote (válidos, con warning y rechazados) para seguirlos paso a paso.

## Definición de Columnas

| Columna | Tipo de Dato | Nulos observados | Ejemplo | Descripción |
|---|---|---|---|---|
| `trace_id` | `str` | No | `9b1c8b81-1` | Identificador del registro de muestra: <lote>-<n>. |
| `_batch_id` | `str` | No | `9b1c8b81-0295-4b2f-83f8-5d3c13ed38e5` | Identificador UUID de la corrida que generó el registro (linaje). |
| `created_at` | `datetime64[us, UTC]` | No | `2026-10-14 01:01:55.188044+00:00` | Cuándo se guardó la traza. |
| `dq_status` | `str` | No | `VALID` | Resultado de Data Quality: VALID (sin hallazgos) o WARNING (publicable pero marcado para revisión). |
| `source` | `str` | No | `open_meteo` | Fuente del dato: open_meteo (API horaria) o iot_simulator (estaciones cada 15 min). |
| `field_id` | `str` | No | `LIT-01` | Identificador del campo del cliente (LIT-01 a LIT-08, ver gold.fields). |
| `measured_at` | `datetime64[us, UTC]` | No | `2026-10-07 00:00:00+00:00` | Fecha y hora de la medición afectada (vacío si el timestamp era inválido). |
| `fecha_negocio` | `object` | Sí (33.33%) | `2026-10-06` | Día de Gold (hora local) al que aporta el registro; vacío si fue rechazado. |
| `titulo` | `str` | No | `✔ VALID · LIT-01 · open_meteo · 2026-10-07T00:00` | Texto con el que se elige el registro en el dashboard «ETL paso a paso». |
