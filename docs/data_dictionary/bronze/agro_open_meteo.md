# Diccionario de Datos: `agro_open_meteo_bronze`

**Capa:** `BRONZE`  
**Dominio:** `agro` | **Entidad:** `open_meteo`  
**Ubicación / Destino:** `storage/staging/bronze/agro/open_meteo/`  
**Última Catalogación:** `2026-10-14T01:02:00.131003+00:00`  

> Lecturas horarias de Open-Meteo Historical Weather API tal como llegaron (append-only, sin correcciones).

## Definición de Columnas

| Columna | Tipo de Dato | Nulos observados | Ejemplo | Descripción |
|---|---|---|---|---|
| `timestamp` | `string` | No | `2026-10-07T00:00` | Fecha y hora de la medición. En Bronze es el texto crudo recibido; desde Silver, datetime UTC. |
| `field_id` | `string` | No | `LIT-01` | Identificador del campo del cliente (LIT-01 a LIT-08, ver gold.fields). |
| `latitude` | `float64` | No | `-32.03` | Latitud de la estación del campo, en grados decimales. |
| `longitude` | `float64` | No | `-60.31` | Longitud de la estación del campo, en grados decimales. |
| `temperature` | `float64` | No | `19.5` | Temperatura del aire a 2 m, en °C. |
| `temperature_unit` | `string` | No | `°C` | Unidad informada por la fuente para temperature (se espera °C, regla DQ06). |
| `humidity` | `float64` | No | `75.0` | Humedad relativa ambiental, en % (0 a 100). |
| `humidity_unit` | `string` | No | `%` | Unidad informada por la fuente para humidity (se espera %, regla DQ06). |
| `soil_moisture` | `float64` | No | `0.329` | Humedad volumétrica del suelo (0 a 7 cm), en m³/m³. |
| `soil_moisture_unit` | `string` | No | `m³/m³` | Unidad informada por la fuente para soil_moisture (se espera m³/m³, regla DQ06). |
| `precipitation` | `float64` | No | `0.0` | Precipitación acumulada en el intervalo de la lectura, en mm. |
| `precipitation_unit` | `string` | No | `mm` | Unidad informada por la fuente para precipitation (se espera mm, regla DQ06). |
| `wind_speed` | `float64` | No | `14.7` | Velocidad del viento a 10 m, en km/h. |
| `wind_speed_unit` | `string` | No | `km/h` | Unidad informada por la fuente para wind_speed (se espera km/h, regla DQ06). |
| `source` | `str` | No | `open_meteo` | Fuente del dato: open_meteo (API horaria) o iot_simulator (estaciones cada 15 min). |
| `_sim_injected_error` | `string` | Sí (100.0%) | - | Solo simulador: tipo de error inyectado a propósito, para medir la detección de las reglas (meta SMART 95%). Vacío en datos sin error y en Open-Meteo. |
| `_batch_id` | `str` | No | `9b1c8b81-0295-4b2f-83f8-5d3c13ed38e5` | Identificador UUID de la corrida que generó el registro (linaje). |
| `_ingested_at` | `datetime64[us, UTC]` | No | `2026-10-14 01:01:53.427774+00:00` | Instante UTC en que el registro se capturó desde la fuente (linaje). |
| `_source_system` | `str` | No | `open_meteo` | Conector que originó el registro: open_meteo o iot_simulator (linaje). |
