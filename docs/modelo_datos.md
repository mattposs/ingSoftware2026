# Modelo de datos (PostgreSQL)

Diagrama de las tablas de `sql/schema/01_schema.sql`. Se repite igual en las tres bases (`agro_dev`, `agro_staging`, `agro_prod`). Bronze, Silver y Quarantine **no** están acá: viven en el lake Parquet (`storage/<entorno>/`).

- Línea continua: clave foránea real en la base.
- Línea punteada: relación lógica sin clave foránea, explicada en la etiqueta.

Imagen exportada: [`Diagrama de base de datos.png`](Diagrama%20de%20base%20de%20datos.png) (alta resolución) y [`modelo_datos.svg`](modelo_datos.svg) (vectorial).

```mermaid
erDiagram
    direction LR
    ETL_WATERMARKS["etl.watermarks"] {
        text domain PK "agro"
        text entity PK "fuente: open_meteo / iot_simulator"
        timestamptz watermark "fin de la última ventana extraída"
        text last_batch_id "lote que lo movió"
        timestamptz updated_at
    }

    GOLD_FIELDS["gold.fields"] {
        text field_id PK "LIT-01 a LIT-08"
        text localidad
        text provincia
        numeric latitude
        numeric longitude
        integer hectareas
        integer sensores
    }

    GOLD_DAILY["gold.daily_field_metrics"] {
        date fecha PK "día en hora local (Buenos Aires)"
        text field_id PK, FK
        text fuente PK "open_meteo / iot_simulator"
        numeric temperatura_promedio
        numeric precipitacion_total
        numeric humedad_suelo_promedio
        numeric humedad_ambiental_promedio
        integer cantidad_mediciones "VALID + WARNING"
        numeric porcentaje_calidad "estricto: VALID / (publicados + rechazados)"
        text _batch_id "último lote que la recalculó"
        timestamptz _updated_at
    }

    GOLD_RUNS["gold.dq_run_metrics"] {
        text _batch_id PK "una fila por corrida"
        timestamptz run_start
        timestamptz run_end
        text status "running / ok / failed"
        integer total
        integer valid
        integer warning
        integer invalid
        numeric dq_score "estricto: VALID / total"
        numeric pct_utilizable "(VALID + WARNING) / total"
    }

    GOLD_ERRORS["gold.dq_errors"] {
        bigserial error_id PK
        text _batch_id FK
        timestamptz detected_at
        timestamptz measured_at "NULL si el timestamp era inválido"
        text source
        text field_id "sin FK: puede ser inexistente (DQ04)"
        text variable
        text rule_id "DQ01 a DQ12"
        text rule_type
        text action "REJECT / WARNING"
        text severidad
        text detalle
    }

    GOLD_LAYERS["gold.pipeline_layer_metrics"] {
        text _batch_id PK, FK
        text layer PK "bronze / silver / quarantine / gold"
        text entity PK
        integer rows
        text location "carpeta del lake o tabla"
        timestamptz window_start "solo bronze"
        timestamptz window_end "solo bronze"
        timestamptz started_at
        timestamptz finished_at
    }

    GOLD_TRACE["gold.etl_trace"] {
        text trace_id PK "lote-n"
        text _batch_id FK
        timestamptz created_at
        text dq_status "VALID / WARNING / INVALID"
        text source
        text field_id
        timestamptz measured_at
        date fecha_negocio
        text titulo
    }

    GOLD_TRACE_STEPS["gold.etl_trace_steps"] {
        text trace_id PK, FK
        integer step PK "1 a 5"
        integer orden PK
        text dato
        text valor
        text resultado "OK / WARNING / REJECT"
    }

    GOLD_FIELDS ||--o{ GOLD_DAILY : "field_id"
    GOLD_RUNS ||--o{ GOLD_ERRORS : "_batch_id (ON DELETE CASCADE)"
    GOLD_RUNS ||--o{ GOLD_LAYERS : "_batch_id (ON DELETE CASCADE)"
    GOLD_RUNS ||--o{ GOLD_TRACE : "_batch_id (ON DELETE CASCADE)"
    GOLD_TRACE ||--|{ GOLD_TRACE_STEPS : "trace_id (ON DELETE CASCADE)"

    GOLD_DAILY }o..o| GOLD_RUNS : "_batch_id, sin FK"
    GOLD_FIELDS |o..o{ GOLD_ERRORS : "field_id, sin FK (DQ04)"
    GOLD_FIELDS |o..o{ GOLD_TRACE : "field_id, sin FK"
    ETL_WATERMARKS }o..o| GOLD_RUNS : "last_batch_id, sin FK"
```

## Qué guarda cada tabla

| Tabla | Para qué sirve | Quién la usa |
|---|---|---|
| `etl.watermarks` | Hasta dónde se leyó cada fuente (carga incremental) | La extracción (`run_bronze`) |
| `gold.fields` | Maestro de los 8 campos, sincronizado desde `config/fields.yaml` | Gold y los dashboards |
| `gold.daily_field_metrics` | Indicadores diarios por fecha, campo y fuente. **Es lo que consume el dashboard.** | Grafana |
| `gold.dq_run_metrics` | Una fila por corrida, con sus contadores, el DQ Score estricto y el % utilizable | Grafana, CI |
| `gold.dq_errors` | Cada hallazgo de las reglas (rechazos y warnings), con el registro que lo originó (RF08) | Grafana |
| `gold.pipeline_layer_metrics` | Qué hizo cada capa en cada lote: registros, duración y ventana (RNF02) | Dashboard «Flujo del ETL» |
| `gold.etl_trace` y `gold.etl_trace_steps` | Registros de muestra y lo que les pasó en cada uno de los 5 pasos | Dashboard «ETL paso a paso» |

Usuarios: `pipeline` lee y escribe `gold.*` y `etl.*`. `dashboard` solo lee `gold.*` (`sql/99_app_users.sh`).
