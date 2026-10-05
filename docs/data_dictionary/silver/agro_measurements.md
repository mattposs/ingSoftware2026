# Diccionario de Datos: `agro_measurements_silver`

**Capa:** `SILVER`  
**Dominio:** `agro` | **Entidad:** `measurements`  
**Ubicación / Destino:** `storage/staging/silver/agro/measurements/`  
**Última Catalogación:** `2026-10-05T22:33:53.074670+00:00`  

> Mediciones tipadas y validadas con DQ01–DQ12: registros VALID y WARNING de ambas fuentes.

## Definición de Columnas

| Columna | Tipo de Dato | Nulos observados | Ejemplo | Descripción |
|---|---|---|---|---|
| `timestamp` | `datetime64[us, UTC]` | No | `2026-10-05 22:30:00+00:00` | Fecha y hora de la medición. En Bronze es el texto crudo recibido; desde Silver, datetime UTC. |
| `source` | `str` | No | `iot_simulator` | Fuente del dato: open_meteo (API horaria) o iot_simulator (estaciones cada 15 min). |
| `field_id` | `string` | No | `C01` | Identificador del campo del cliente (C01 a C06, ver gold.fields). |
| `latitude` | `float64` | No | `-34.05` | Latitud de la estación del campo, en grados decimales. |
| `longitude` | `float64` | No | `-60.55` | Longitud de la estación del campo, en grados decimales. |
| `temperature` | `float64` | No | `16.81` | Temperatura del aire a 2 m, en °C. |
| `humidity` | `float64` | No | `65.2` | Humedad relativa ambiental, en % (0 a 100). |
| `soil_moisture` | `float64` | No | `0.279` | Humedad volumétrica del suelo (0 a 7 cm), en m³/m³. |
| `precipitation` | `float64` | No | `0.0` | Precipitación acumulada en el intervalo de la lectura, en mm. |
| `wind_speed` | `float64` | No | `8.3` | Velocidad del viento a 10 m, en km/h. |
| `dq_status` | `str` | No | `VALID` | Resultado de Data Quality: VALID (sin hallazgos) o WARNING (publicable pero marcado para revisión). |
| `_dq_warnings` | `str` | Sí (96.92%) | `DQ11` | Códigos de las reglas de warning que disparó el registro, separados por ';' (ej. DQ09;DQ11). |
| `_sim_injected_error` | `string` | Sí (98.97%) | `gap` | Solo simulador: tipo de error inyectado a propósito, para medir la detección de las reglas (meta SMART 95%). Vacío en datos sin error y en Open-Meteo. |
| `_batch_id` | `str` | No | `54097779-734c-48c0-adbf-61f4b283aa89` | Identificador UUID de la corrida que generó el registro (linaje). |
| `_ingested_at` | `datetime64[us, UTC]` | No | `2026-10-05 22:32:05.767720+00:00` | Instante UTC en que el registro se capturó desde la fuente (linaje). |
| `_source_system` | `str` | No | `iot_simulator` | Conector que originó el registro: open_meteo o iot_simulator (linaje). |
