# Diccionario de Datos: `agro_iot_simulator_bronze`

**Capa:** `BRONZE`  
**Dominio:** `agro` | **Entidad:** `iot_simulator`  
**Ubicación / Destino:** `storage/staging/bronze/agro/iot_simulator/`  
**Última Catalogación:** `2026-10-05T22:33:52.881591+00:00`  

> Lecturas de las 6 estaciones IoT simuladas cada 15 minutos, con errores inyectados (append-only).

## Definición de Columnas

| Columna | Tipo de Dato | Nulos observados | Ejemplo | Descripción |
|---|---|---|---|---|
| `timestamp` | `string` | Sí (1.04%) | `2026-10-05T22:30:00Z` | Fecha y hora de la medición. En Bronze es el texto crudo recibido; desde Silver, datetime UTC. |
| `field_id` | `string` | No | `C01` | Identificador del campo del cliente (C01 a C06, ver gold.fields). |
| `latitude` | `float64` | No | `-34.05` | Latitud de la estación del campo, en grados decimales. |
| `longitude` | `float64` | No | `-60.55` | Longitud de la estación del campo, en grados decimales. |
| `temperature` | `float64` | No | `16.81` | Temperatura del aire a 2 m, en °C. |
| `temperature_unit` | `string` | No | `°C` | Unidad informada por la fuente para temperature (se espera °C, regla DQ06). |
| `humidity` | `float64` | No | `65.2` | Humedad relativa ambiental, en % (0 a 100). |
| `humidity_unit` | `string` | No | `%` | Unidad informada por la fuente para humidity (se espera %, regla DQ06). |
| `soil_moisture` | `float64` | No | `0.279` | Humedad volumétrica del suelo (0 a 7 cm), en m³/m³. |
| `soil_moisture_unit` | `string` | No | `m³/m³` | Unidad informada por la fuente para soil_moisture (se espera m³/m³, regla DQ06). |
| `precipitation` | `float64` | No | `0.0` | Precipitación acumulada en el intervalo de la lectura, en mm. |
| `precipitation_unit` | `string` | No | `mm` | Unidad informada por la fuente para precipitation (se espera mm, regla DQ06). |
| `wind_speed` | `float64` | No | `8.3` | Velocidad del viento a 10 m, en km/h. |
| `wind_speed_unit` | `string` | No | `km/h` | Unidad informada por la fuente para wind_speed (se espera km/h, regla DQ06). |
| `source` | `str` | No | `iot_simulator` | Fuente del dato: open_meteo (API horaria) o iot_simulator (estaciones cada 15 min). |
| `_sim_injected_error` | `string` | Sí (92.04%) | `null_timestamp` | Solo simulador: tipo de error inyectado a propósito, para medir la detección de las reglas (meta SMART 95%). Vacío en datos sin error y en Open-Meteo. |
| `_batch_id` | `str` | No | `54097779-734c-48c0-adbf-61f4b283aa89` | Identificador UUID de la corrida que generó el registro (linaje). |
| `_ingested_at` | `datetime64[us, UTC]` | No | `2026-10-05 22:32:05.767720+00:00` | Instante UTC en que el registro se capturó desde la fuente (linaje). |
| `_source_system` | `str` | No | `iot_simulator` | Conector que originó el registro: open_meteo o iot_simulator (linaje). |
