# Diccionario de Datos: `agro_etl_trace_gold`

**Capa:** `GOLD`  
**Dominio:** `agro` | **Entidad:** `etl_trace`  
**Ubicación / Destino:** `postgres:gold.etl_trace`  
**Última Catalogación:** `2026-10-05T22:33:54.360758+00:00`  

> Registros de muestra de cada lote (válidos, con warning y rechazados) para seguirlos paso a paso.

## Definición de Columnas

| Columna | Tipo de Dato | Nulos observados | Ejemplo | Descripción |
|---|---|---|---|---|
| `trace_id` | `str` | No | `54097779-1` | Identificador del registro de muestra: <lote>-<n>. |
| `_batch_id` | `str` | No | `54097779-734c-48c0-adbf-61f4b283aa89` | Identificador UUID de la corrida que generó el registro (linaje). |
| `created_at` | `datetime64[us, UTC]` | No | `2026-10-05 22:32:08.482456+00:00` | Cuándo se guardó la traza. |
| `dq_status` | `str` | No | `VALID` | Resultado de Data Quality: VALID (sin hallazgos) o WARNING (publicable pero marcado para revisión). |
| `source` | `str` | No | `iot_simulator` | Fuente del dato: open_meteo (API horaria) o iot_simulator (estaciones cada 15 min). |
| `field_id` | `str` | No | `C01` | Identificador del campo del cliente (C01 a C06, ver gold.fields). |
| `measured_at` | `datetime64[us, UTC]` | No | `2026-10-05 22:30:00+00:00` | Fecha y hora de la medición afectada (vacío si el timestamp era inválido). |
| `fecha_negocio` | `object` | Sí (25.0%) | `2026-10-05` | Día de Gold (hora local) al que aporta el registro; vacío si fue rechazado. |
| `titulo` | `str` | No | `✔ VALID · C01 · iot_simulator · 2026-10-05T22:30:00Z` | Texto con el que se elige el registro en el dashboard «ETL paso a paso». |
