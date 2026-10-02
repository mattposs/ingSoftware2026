# Diccionario de Datos: `agro_dq_errors_gold`

**Capa:** `GOLD`  
**Dominio:** `agro` | **Entidad:** `dq_errors`  
**Ubicación / Destino:** `postgres:gold.dq_errors`  
**Última Catalogación:** `2026-10-02T22:15:41.533621+00:00`  

> Registro de hallazgos de Data Quality (rechazos y warnings) por registro, regla y variable.

## Definición de Columnas

| Columna | Tipo de Dato | Nulos observados | Ejemplo | Descripción |
|---|---|---|---|---|
| `error_id` | `int64` | No | `447` | Identificador del hallazgo. |
| `_batch_id` | `str` | No | `ca89ae95-c758-435c-86e9-82d67695c9e9` | Identificador UUID de la corrida que generó el registro (linaje). |
| `detected_at` | `datetime64[us, UTC]` | No | `2026-10-02 22:11:08.849569+00:00` | Instante UTC en que se detectó el hallazgo. |
| `measured_at` | `datetime64[us, UTC]` | Sí (3.41%) | `2026-10-02 01:45:00+00:00` | Fecha y hora de la medición afectada (vacío si el timestamp era inválido). |
| `source` | `str` | No | `iot_simulator` | Fuente del dato: open_meteo (API horaria) o iot_simulator (estaciones cada 15 min). |
| `field_id` | `str` | Sí (3.41%) | `C02` | Identificador del campo del cliente (C01 a C06, ver gold.fields). |
| `variable` | `str` | Sí (14.2%) | `temperature` | Variable afectada (temperature, humidity, ...); vacío si la regla aplica al registro completo. |
| `rule_id` | `str` | No | `DQ01` | Código de la regla incumplida (DQ01 a DQ12, ver config/rules.yaml). |
| `rule_type` | `str` | No | `Completitud` | Tipo de regla: Completitud, Unicidad, Validez, Consistencia, Integridad o Anomalía. |
| `action` | `str` | No | `REJECT` | REJECT (el registro fue a quarantine) o WARNING (publicado y marcado). |
| `severidad` | `str` | No | `Crítica` | Criticidad de la regla: Crítica, Alta o Media. |
| `detalle` | `str` | No | `timestamp nulo o vacío` | Explicación legible del hallazgo. |
