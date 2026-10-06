# Diccionario de Datos: `agro_dq_errors_gold`

**Capa:** `GOLD`  
**Dominio:** `agro` | **Entidad:** `dq_errors`  
**Ubicación / Destino:** `postgres:gold.dq_errors`  
**Última Catalogación:** `2026-10-05T22:33:53.962415+00:00`  

> Registro de hallazgos de Data Quality (rechazos y warnings) por registro, regla y variable.

## Definición de Columnas

| Columna | Tipo de Dato | Nulos observados | Ejemplo | Descripción |
|---|---|---|---|---|
| `error_id` | `int64` | No | `158` | Identificador del hallazgo. |
| `_batch_id` | `str` | No | `54097779-734c-48c0-adbf-61f4b283aa89` | Identificador UUID de la corrida que generó el registro (linaje). |
| `detected_at` | `datetime64[us, UTC]` | No | `2026-10-05 22:32:08.192404+00:00` | Instante UTC en que se detectó el hallazgo. |
| `measured_at` | `datetime64[us, UTC]` | Sí (7.41%) | `2026-10-05 22:30:00+00:00` | Fecha y hora de la medición afectada (vacío si el timestamp era inválido). |
| `source` | `str` | No | `iot_simulator` | Fuente del dato: open_meteo (API horaria) o iot_simulator (estaciones cada 15 min). |
| `field_id` | `str` | No | `C04` | Identificador del campo del cliente (C01 a C06, ver gold.fields). |
| `variable` | `str` | Sí (13.58%) | `temperature` | Variable afectada (temperature, humidity, ...); vacío si la regla aplica al registro completo. |
| `rule_id` | `str` | No | `DQ11` | Código de la regla incumplida (DQ01 a DQ12, ver config/rules.yaml). |
| `rule_type` | `str` | No | `Completitud` | Tipo de regla: Completitud, Unicidad, Validez, Consistencia, Integridad o Anomalía. |
| `action` | `str` | No | `WARNING` | REJECT (el registro fue a quarantine) o WARNING (publicado y marcado). |
| `severidad` | `str` | No | `Media` | Criticidad de la regla: Crítica, Alta o Media. |
| `detalle` | `str` | No | `hueco de 30 min sin datos` | Explicación legible del hallazgo. |
