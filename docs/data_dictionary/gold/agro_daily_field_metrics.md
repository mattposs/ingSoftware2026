# Diccionario de Datos: `agro_daily_field_metrics_gold`

**Capa:** `GOLD`  
**Dominio:** `agro` | **Entidad:** `daily_field_metrics`  
**Ubicación / Destino:** `postgres:gold.daily_field_metrics`  
**Última Catalogación:** `2026-10-02T22:15:41.279311+00:00`  

> Indicadores diarios por campo y fuente. Única tabla que consume el dashboard.

## Definición de Columnas

| Columna | Tipo de Dato | Nulos observados | Ejemplo | Descripción |
|---|---|---|---|---|
| `fecha` | `object` | No | `2026-09-20` | Día de las mediciones en hora local del negocio (America/Argentina/Buenos_Aires). |
| `field_id` | `str` | No | `C01` | Identificador del campo del cliente (C01 a C06, ver gold.fields). |
| `fuente` | `str` | No | `open_meteo` | Fuente de las mediciones agregadas (open_meteo o iot_simulator). |
| `temperatura_promedio` | `float64` | No | `12.633` | Temperatura promedio del día, en °C, solo con registros VALID y WARNING. |
| `precipitacion_total` | `float64` | No | `0.0` | Precipitación total del día, en mm. |
| `humedad_suelo_promedio` | `float64` | No | `0.406` | Humedad del suelo promedio del día, en m³/m³. |
| `humedad_ambiental_promedio` | `float64` | No | `81.333` | Humedad relativa ambiental promedio del día, en %. |
| `cantidad_mediciones` | `int64` | No | `3` | Cantidad de registros publicados (VALID + WARNING) que componen el indicador. |
| `porcentaje_calidad` | `float64` | No | `100.0` | Publicados / (publicados + rechazados atribuibles a ese día, campo y fuente) × 100. |
| `_batch_id` | `str` | No | `ca89ae95-c758-435c-86e9-82d67695c9e9` | Identificador UUID de la corrida que generó el registro (linaje). |
| `_updated_at` | `datetime64[us, UTC]` | No | `2026-10-02 22:11:09.451622+00:00` | Última vez que se recalculó la fila. |
