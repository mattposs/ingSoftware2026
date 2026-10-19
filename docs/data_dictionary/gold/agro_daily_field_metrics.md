# Diccionario de Datos: `agro_daily_field_metrics_gold`

**Capa:** `GOLD`  
**Dominio:** `agro` | **Entidad:** `daily_field_metrics`  
**Ubicación / Destino:** `postgres:gold.daily_field_metrics`  
**Última Catalogación:** `2026-10-14T01:02:00.848453+00:00`  

> Indicadores diarios por campo y fuente. Única tabla que consume el dashboard.

## Definición de Columnas

| Columna | Tipo de Dato | Nulos observados | Ejemplo | Descripción |
|---|---|---|---|---|
| `fecha` | `object` | No | `2026-10-06` | Día de las mediciones en hora local del negocio (America/Argentina/Buenos_Aires). |
| `field_id` | `str` | No | `LIT-01` | Identificador del campo del cliente (LIT-01 a LIT-08, ver gold.fields). |
| `fuente` | `str` | No | `open_meteo` | Fuente de las mediciones agregadas (open_meteo o iot_simulator). |
| `temperatura_promedio` | `float64` | No | `19.367` | Temperatura promedio del día, en °C, solo con registros VALID y WARNING. |
| `precipitacion_total` | `float64` | No | `0.0` | Precipitación total del día, en mm. |
| `humedad_suelo_promedio` | `float64` | No | `0.329` | Humedad del suelo promedio del día, en m³/m³. |
| `humedad_ambiental_promedio` | `float64` | No | `77.333` | Humedad relativa ambiental promedio del día, en %. |
| `cantidad_mediciones` | `int64` | No | `3` | Cantidad de registros publicados (VALID + WARNING) que componen el indicador. |
| `porcentaje_calidad` | `float64` | No | `100.0` | Score estricto del día: registros VALID / (publicados + rechazados atribuibles a ese día, campo y fuente) × 100. Los WARNING no cuentan como válidos. |
| `_batch_id` | `str` | No | `9b1c8b81-0295-4b2f-83f8-5d3c13ed38e5` | Identificador UUID de la corrida que generó el registro (linaje). |
| `_updated_at` | `datetime64[us, UTC]` | No | `2026-10-14 01:01:55.656158+00:00` | Última vez que se recalculó la fila. |
