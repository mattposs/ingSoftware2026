# Diccionario de Datos: `agro_dq_errors_gold`

**Capa:** `GOLD`  
**Dominio:** `agro` | **Entidad:** `dq_errors`  
**Ubicación / Destino:** `postgres:gold.dq_errors`  
**Última Catalogación:** `2026-10-14T01:02:01.099413+00:00`  

> Registro de hallazgos de Data Quality (rechazos y warnings) por registro, regla y variable.

## Definición de Columnas

| Columna | Tipo de Dato | Nulos observados | Ejemplo | Descripción |
|---|---|---|---|---|
| `error_id` | `int64` | No | `1` | Identificador del hallazgo. |
| `_batch_id` | `str` | No | `9b1c8b81-0295-4b2f-83f8-5d3c13ed38e5` | Identificador UUID de la corrida que generó el registro (linaje). |
| `detected_at` | `datetime64[us, UTC]` | No | `2026-10-14 01:01:54.565662+00:00` | Instante UTC en que se detectó el hallazgo. |
| `measured_at` | `datetime64[us, UTC]` | Sí (5.06%) | `2026-10-13 10:00:00+00:00` | Fecha y hora de la medición afectada (vacío si el timestamp era inválido). |
| `source` | `str` | No | `iot_simulator` | Fuente del dato: open_meteo (API horaria) o iot_simulator (estaciones cada 15 min). |
| `field_id` | `str` | Sí (2.68%) | `LIT-02` | Identificador del campo del cliente (LIT-01 a LIT-08, ver gold.fields). |
| `variable` | `str` | Sí (13.39%) | `temperature` | Variable afectada (temperature, humidity, ...); vacío si la regla aplica al registro completo. |
| `rule_id` | `str` | No | `DQ01` | Código de la regla incumplida (DQ01 a DQ12, ver config/rules.yaml). |
| `rule_type` | `str` | No | `Completitud` | Tipo de regla: Completitud, Unicidad, Validez, Consistencia, Integridad o Anomalía. |
| `action` | `str` | No | `REJECT` | REJECT (el registro fue a quarantine) o WARNING (publicado y marcado). |
| `severidad` | `str` | No | `Crítica` | Criticidad de la regla: Crítica, Alta o Media. |
| `detalle` | `str` | No | `timestamp nulo o vacío` | Explicación legible del hallazgo. |
