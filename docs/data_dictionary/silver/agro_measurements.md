# Diccionario de Datos: `agro_measurements_silver`

**Capa:** `SILVER`  
**Dominio:** `agro` | **Entidad:** `measurements`  
**Ubicación / Destino:** `storage/staging/silver/agro/measurements/`  
**Última Catalogación:** `2026-10-14T01:02:00.424548+00:00`  

> Mediciones tipadas y validadas con DQ01–DQ12: registros VALID y WARNING de ambas fuentes.

## Definición de Columnas

| Columna | Tipo de Dato | Nulos observados | Ejemplo | Descripción |
|---|---|---|---|---|
| `timestamp` | `datetime64[us, UTC]` | No | `2026-10-07 00:00:00+00:00` | Fecha y hora de la medición. En Bronze es el texto crudo recibido; desde Silver, datetime UTC. |
| `source` | `str` | No | `open_meteo` | Fuente del dato: open_meteo (API horaria) o iot_simulator (estaciones cada 15 min). |
| `field_id` | `string` | No | `LIT-01` | Identificador del campo del cliente (LIT-01 a LIT-08, ver gold.fields). |
| `latitude` | `float64` | No | `-32.03` | Latitud de la estación del campo, en grados decimales. |
| `longitude` | `float64` | No | `-60.31` | Longitud de la estación del campo, en grados decimales. |
| `temperature` | `float64` | No | `19.5` | Temperatura del aire a 2 m, en °C. |
| `humidity` | `float64` | No | `75.0` | Humedad relativa ambiental, en % (0 a 100). |
| `soil_moisture` | `float64` | No | `0.329` | Humedad volumétrica del suelo (0 a 7 cm), en m³/m³. |
| `precipitation` | `float64` | No | `0.0` | Precipitación acumulada en el intervalo de la lectura, en mm. |
| `wind_speed` | `float64` | No | `14.7` | Velocidad del viento a 10 m, en km/h. |
| `dq_status` | `str` | No | `VALID` | Resultado de Data Quality: VALID (sin hallazgos) o WARNING (publicable pero marcado para revisión). |
| `_dq_warnings` | `str` | Sí (95.43%) | `DQ12` | Códigos de las reglas de warning que disparó el registro, separados por ';' (ej. DQ09;DQ11). |
| `_sim_injected_error` | `string` | Sí (98.64%) | `gap` | Solo simulador: tipo de error inyectado a propósito, para medir la detección de las reglas (meta SMART 95%). Vacío en datos sin error y en Open-Meteo. |
| `_batch_id` | `str` | No | `9b1c8b81-0295-4b2f-83f8-5d3c13ed38e5` | Identificador UUID de la corrida que generó el registro (linaje). |
| `_ingested_at` | `datetime64[us, UTC]` | No | `2026-10-14 01:01:53.427774+00:00` | Instante UTC en que el registro se capturó desde la fuente (linaje). |
| `_source_system` | `str` | No | `open_meteo` | Conector que originó el registro: open_meteo o iot_simulator (linaje). |
