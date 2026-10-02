# Diccionario de Datos: `agro_measurements_silver`

**Capa:** `SILVER`  
**Dominio:** `agro` | **Entidad:** `measurements`  
**Ubicación / Destino:** `storage/silver/agro/measurements/`  
**Última Catalogación:** `2026-10-02T22:15:40.456781+00:00`  

> Mediciones tipadas y validadas con DQ01–DQ12: registros VALID y WARNING de ambas fuentes.

## Definición de Columnas

| Columna | Tipo de Dato | Nulos observados | Ejemplo | Descripción |
|---|---|---|---|---|
| `timestamp` | `datetime64[us, UTC]` | No | `2026-09-21 00:00:00+00:00` | Fecha y hora de la medición. En Bronze es el texto crudo recibido; desde Silver, datetime UTC. |
| `source` | `str` | No | `open_meteo` | Fuente del dato: open_meteo (API horaria) o iot_simulator (estaciones cada 15 min). |
| `field_id` | `string` | No | `C01` | Identificador del campo del cliente (C01 a C06, ver gold.fields). |
| `latitude` | `float64` | No | `-34.05` | Latitud de la estación del campo, en grados decimales. |
| `longitude` | `float64` | No | `-60.55` | Longitud de la estación del campo, en grados decimales. |
| `temperature` | `float64` | No | `12.8` | Temperatura del aire a 2 m, en °C. |
| `humidity` | `float64` | No | `82.0` | Humedad relativa ambiental, en % (0 a 100). |
| `soil_moisture` | `float64` | No | `0.407` | Humedad volumétrica del suelo (0 a 7 cm), en m³/m³. |
| `precipitation` | `float64` | No | `0.0` | Precipitación acumulada en el intervalo de la lectura, en mm. |
| `wind_speed` | `float64` | No | `1.5` | Velocidad del viento a 10 m, en km/h. |
| `dq_status` | `str` | No | `VALID` | Resultado de Data Quality: VALID (sin hallazgos) o WARNING (publicable pero marcado para revisión). |
| `_dq_warnings` | `str` | Sí (98.05%) | `DQ12` | Códigos de las reglas de warning que disparó el registro, separados por ';' (ej. DQ09;DQ11). |
| `_sim_injected_error` | `string` | Sí (99.61%) | `gap` | Solo simulador: tipo de error inyectado a propósito, para medir la detección de las reglas (meta SMART 95%). Vacío en datos sin error y en Open-Meteo. |
| `_batch_id` | `str` | No | `ca89ae95-c758-435c-86e9-82d67695c9e9` | Identificador UUID de la corrida que generó el registro (linaje). |
| `_ingested_at` | `datetime64[us, UTC]` | No | `2026-10-02 22:11:06.638697+00:00` | Instante UTC en que el registro se capturó desde la fuente (linaje). |
| `_source_system` | `str` | No | `open_meteo` | Conector que originó el registro: open_meteo o iot_simulator (linaje). |
