# Registro de decisiones técnicas

Decisiones que el documento de proyecto v7 dejaba abiertas o ambiguas y que hubo que tomar para
implementar el pipeline. **Estado "Propuesta"** = implementada así, pendiente de validar con el
equipo (y, si aplica, con los agrónomos en el taller de reglas de S2). Para cambiarlas, en general
alcanza con editar `config/*.yaml`.

| ID | Tema | Decisión | Dónde se cambia | Estado |
|---|---|---|---|---|
| D1 | DQ11: qué es un "hueco" | Diferencia entre dos lecturas consecutivas **≥ 30 min** (IoT) o **≥ 120 min** (Open-Meteo, que es horario), por campo, fuente y variable. Con lecturas cada 15 min, 30 min = **una** lectura faltante. Se marca la lectura posterior al hueco. Un valor nulo en una variable cuenta como dato faltante de esa variable. | `config/rules.yaml` → `DQ11.min_gap_minutes` | Propuesta |
| D2 | Data Quality Score | `(VALID + WARNING) / total × 100`: los WARNING se publican en Gold, así que cuentan como utilizables. Los contadores se guardan por separado en `gold.dq_run_metrics`, para poder mostrar también el % estrictamente VALID. | `src/validation/engine.py` → `dq_score` | Propuesta |
| D3 | Unidades (DQ06) | Bronze tiene una columna de unidad por variable (`temperature_unit`, `humidity_unit`, …). Open-Meteo informa sus unidades en `hourly_units` y se guardan tal cual. | `config/rules.yaml` → `DQ06.expected_units` | Propuesta |
| D4 | Clave de Gold | `gold.daily_field_metrics` tiene PK `(fecha, field_id, fuente)`, como en la figura 3. No se mezclan Open-Meteo e IoT en un mismo promedio. | `sql/01_schema.sql` | Propuesta |
| D5 | Reglas que cruzan lotes | DQ05 (duplicados), DQ11 y DQ12 se evalúan contra el histórico de Silver, no solo dentro del lote. Sin esto, un duplicado que llega en otra corrida o un salto en el borde del lote pasan sin detectarse. | `src/validation/engine.py` (`context`) | Implementada |
| D6 | "Fecha" de Gold | Día en hora local (`America/Argentina/Buenos_Aires`), no UTC: es como lo leen agrónomos y jefes de campo. 23:30 hora local sigue siendo "hoy". | `config/pipeline.yaml` → `business_timezone` | Propuesta |
| D7 | Campos válidos (DQ04) | La lista sale de `config/fields.yaml` y se sincroniza a `gold.fields` en cada corrida. Así Silver no depende de leer Gold. | `config/fields.yaml` | Implementada |
| D8 | Watermark | Se guarda el **fin de la ventana** consultada (no el máximo timestamp de los datos) y avanza cuando el lote quedó en Bronze. Silver y Gold se reprocesan desde Bronze con `python -m src.main --reprocess <batch_id>`. | `src/common/state.py`, `src/pipeline.py` | Implementada |
| D9 | Gold incremental | Para cada `(fecha, campo, fuente)` tocado por el lote se recalcula el indicador con **todo** Silver y se hace upsert. Agregar solo el delta pisaría los valores de días que llegan en varios lotes. | `src/transformation/gold.py` | Implementada |
| D10 | `gold.dq_errors` | Se agregaron `measured_at` y `source` (RF08 pide la fecha del dato, no solo la de detección). Se registran rechazos **y** warnings (columna `action`). | `sql/01_schema.sql` | Propuesta |
| D11 | Lake en `storage/` | El lake Parquet va en `storage/` (ignorado por Git). `data/` queda para datos manuales de tests. | `config/pipeline.yaml` → `storage_path` | Implementada |
| D12 | Stack | Pandas + PyArrow + Pytest (sin Polars ni Great Expectations), como en 8.1. Airflow sigue siendo opcional. | `requirements.txt` | Propuesta |
| D13 | Ubicación de las skills | Hay copias en `.agents/skills/` y en `config/agent/skills/`. Se recomienda dejar una sola, `.agents/skills/` (convención de agentes), y que `config/` quede solo para la configuración del pipeline. Las dos copias de `data-governance` quedaron idénticas. | — | **Pendiente (equipo)** |

## Preguntas abiertas para el taller de reglas (S2)

1. **Valores faltantes en una variable** (ej. temperatura nula con el resto presente): hoy solo los detecta DQ11 como hueco de esa variable. ¿Hace falta una regla propia (DQ13, warning)?
2. **Rangos de DQ09 y DQ10**: ¿son razonables para los seis campos o hay que diferenciarlos por provincia?
3. **DQ12 con Open-Meteo**: al ser horario, ¿el umbral por hora es el mismo que para los sensores?
