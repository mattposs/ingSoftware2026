# Diccionario de Datos: `agro_open_meteo_bronze`

**Capa:** `BRONZE`  
**Dominio:** `agro` | **Entidad:** `open_meteo`  
**Ubicación / Destino:** `storage/bronze/agro/open_meteo/`  
**Última Catalogación:** `2026-10-02T22:15:40.057332+00:00`  

> Lecturas horarias de Open-Meteo Historical Weather API tal como llegaron (append-only, sin correcciones).

## Definición de Columnas

| Columna | Tipo de Dato | Nulos observados | Ejemplo | Descripción |
|---|---|---|---|---|
| `timestamp` | `string` | No | `2026-09-21T00:00` | Fecha y hora de la medición. En Bronze es el texto crudo recibido; desde Silver, datetime UTC. |
| `field_id` | `string` | No | `C01` | Identificador del campo del cliente (C01 a C06, ver gold.fields). |
| `latitude` | `float64` | No | `-34.05` | Latitud de la estación del campo, en grados decimales. |
| `longitude` | `float64` | No | `-60.55` | Longitud de la estación del campo, en grados decimales. |
| `temperature` | `float64` | No | `12.8` | Temperatura del aire a 2 m, en °C. |
| `temperature_unit` | `string` | No | `°C` | Unidad informada por la fuente para temperature (se espera °C, regla DQ06). |
| `humidity` | `float64` | No | `82.0` | Humedad relativa ambiental, en % (0 a 100). |
| `humidity_unit` | `string` | No | `%` | Unidad informada por la fuente para humidity (se espera %, regla DQ06). |
| `soil_moisture` | `float64` | No | `0.407` | Humedad volumétrica del suelo (0 a 7 cm), en m³/m³. |
| `soil_moisture_unit` | `string` | No | `m³/m³` | Unidad informada por la fuente para soil_moisture (se espera m³/m³, regla DQ06). |
| `precipitation` | `float64` | No | `0.0` | Precipitación acumulada en el intervalo de la lectura, en mm. |
| `precipitation_unit` | `string` | No | `mm` | Unidad informada por la fuente para precipitation (se espera mm, regla DQ06). |
| `wind_speed` | `float64` | No | `1.5` | Velocidad del viento a 10 m, en km/h. |
| `wind_speed_unit` | `string` | No | `km/h` | Unidad informada por la fuente para wind_speed (se espera km/h, regla DQ06). |
| `source` | `str` | No | `open_meteo` | Fuente del dato: open_meteo (API horaria) o iot_simulator (estaciones cada 15 min). |
| `_sim_injected_error` | `string` | Sí (100.0%) | - | Solo simulador: tipo de error inyectado a propósito, para medir la detección de las reglas (meta SMART 95%). Vacío en datos sin error y en Open-Meteo. |
| `_batch_id` | `str` | No | `ca89ae95-c758-435c-86e9-82d67695c9e9` | Identificador UUID de la corrida que generó el registro (linaje). |
| `_ingested_at` | `datetime64[us, UTC]` | No | `2026-10-02 22:11:06.638697+00:00` | Instante UTC en que el registro se capturó desde la fuente (linaje). |
| `_source_system` | `str` | No | `open_meteo` | Conector que originó el registro: open_meteo o iot_simulator (linaje). |
