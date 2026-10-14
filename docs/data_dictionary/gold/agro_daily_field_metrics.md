# Diccionario de Datos: `agro_daily_field_metrics_gold`

**Capa:** `GOLD`  
**Dominio:** `agro` | **Entidad:** `daily_field_metrics`  
**Ubicación / Destino:** `postgres:gold.daily_field_metrics`  
**Última Catalogación:** `2026-10-05T22:33:53.655680+00:00`  

> Indicadores diarios por campo y fuente. Única tabla que consume el dashboard.

## Definición de Columnas

| Columna | Tipo de Dato | Nulos observados | Ejemplo | Descripción |
|---|---|---|---|---|
| `fecha` | `object` | No | `2026-09-27` | Día de las mediciones en hora local del negocio (America/Argentina/Buenos_Aires). |
| `field_id` | `str` | No | `LIT-01` | Identificador del campo del cliente (LIT-01 a LIT-08, ver gold.fields). |
| `fuente` | `str` | No | `open_meteo` | Fuente de las mediciones agregadas (open_meteo o iot_simulator). |
| `temperatura_promedio` | `float64` | No | `15.333` | Temperatura promedio del día, en °C, solo con registros VALID y WARNING. |
| `precipitacion_total` | `float64` | No | `0.0` | Precipitación total del día, en mm. |
| `humedad_suelo_promedio` | `float64` | No | `0.478` | Humedad del suelo promedio del día, en m³/m³. |
| `humedad_ambiental_promedio` | `float64` | No | `85.667` | Humedad relativa ambiental promedio del día, en %. |
| `cantidad_mediciones` | `int64` | No | `3` | Cantidad de registros publicados (VALID + WARNING) que componen el indicador. |
| `porcentaje_calidad` | `float64` | No | `100.0` | Publicados / (publicados + rechazados atribuibles a ese día, campo y fuente) × 100. |
| `_batch_id` | `str` | No | `dbe6e15b-39eb-4e4b-9102-7e9909146eb7` | Identificador UUID de la corrida que generó el registro (linaje). |
| `_updated_at` | `datetime64[us, UTC]` | No | `2026-10-05 22:32:12.376737+00:00` | Última vez que se recalculó la fila. |
