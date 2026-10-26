# Diagramas para el documento

Tres diagramas en Mermaid, armados para que entren legibles en una página A4 del documento: arquitectura general, esquema Medallion y base de datos. Todo lo que muestran sale del repositorio (`docker-compose.yml`, `src/pipeline.py`, `config/`, `sql/schema/01_schema.sql` y `grafana/`).

Para verlos: GitHub y VS Code (con la extensión *Markdown Preview Mermaid Support*) los dibujan solos. También se pueden pegar en https://mermaid.live.

## Cómo pasarlos al Word sin que se pierda la letra

1. **Exportá a imagen grande, nunca captura de pantalla.** En mermaid.live: *Actions → PNG* con *scale* 3, o *SVG* si el Word lo acepta (Word 365 inserta SVG y queda nítido a cualquier zoom). Con la consola: `npx -p @mermaid-js/mermaid-cli mmdc -i diagrama.mmd -o diagrama.png -s 3 -b white`.
2. **Insertalo al ancho de la página** (unos 16 cm de ancho útil en A4 con márgenes de 2,5 cm) y no lo achiques más. Si la letra queda menor a 8 pt, el diagrama tiene demasiadas cosas: partilo.
3. **Una idea por diagrama.** Por eso la base de datos está en dos versiones: una **compacta** (tablas, claves y relaciones) para el cuerpo del documento y una **completa** (todas las columnas) para el anexo.
4. **Orientación según la hoja.** `flowchart LR` (izquierda → derecha) aprovecha el ancho y `flowchart TB` (arriba → abajo), el alto. La arquitectura va en `TB` para una hoja vertical y el Medallion en `LR`, porque es una secuencia. Si un diagrama queda muy chato o muy alto, cambiá `LR` por `TB` (o al revés) en la primera línea. En los `erDiagram` no uses `direction LR`: algunas versiones de Mermaid (como la de mermaid.live hasta la 11.4) lo dibujan como dos tablas llamadas «direction» y «LR».
5. **Textos cortos en las cajas** y el detalle en la tabla o el párrafo que acompaña a la figura. Los saltos de línea dentro de una caja se escriben `<br/>`.
6. **Pie de figura en el Word**, no dentro del diagrama: «Figura N. …».

---

## 1. Arquitectura general

Qué se ve: de dónde vienen los datos, qué código los procesa, dónde quedan, quién los consume y qué corre en cada contenedor de Docker Compose.

```mermaid
flowchart TB
    subgraph ORIGEN["1 · Origen de los datos"]
        OM["Open-Meteo<br/>API histórica<br/>(datos reales)"]
        IOT["Sensores IoT<br/>simulador · 8 campos<br/>cada 15 min"]
    end

    subgraph DOCKER["Docker Compose"]
        subgraph PROC["2 · Procesamiento"]
            SCH["Scheduler<br/>cada 15 min"]
            EXT["Extracción<br/>run_bronze"]
            VAL["Validación<br/>run_silver<br/>12 reglas DQ"]
            GLD["Transformación<br/>run_gold"]
        end
        subgraph ALM["3 · Almacenamiento"]
            LAKE[("Lake Parquet<br/>./storage<br/>Bronze · Silver · Quarantine")]
            PG[("PostgreSQL 16<br/>agro_dev · agro_staging · agro_prod<br/>esquemas gold y etl")]
        end
        subgraph CONS["4 · Consumo y monitoreo"]
            GRA["Grafana 11.4<br/>3 dashboards<br/>alertas AL01 · AL02"]
            MAIL["Mailpit<br/>correo de alertas"]
        end
    end

    USR(["Usuarios del cliente<br/>navegador"])

    OM -->|HTTPS| EXT
    IOT --> EXT
    SCH -.dispara.-> EXT
    EXT --> VAL --> GLD
    EXT -->|escribe| LAKE
    VAL <-->|lee y escribe| LAKE
    GLD -->|upsert| PG
    VAL -->|métricas y errores| PG
    PG -->|solo lectura de gold| GRA
    GRA -->|SMTP| MAIL
    GRA --> USR

    subgraph CICD["5 · Infraestructura y CI/CD"]
        GH["GitHub<br/>ramas dev · staging · main"]
        GA["GitHub Actions<br/>lint · tests · build"]
        IMG["Imagen Docker<br/>GHCR :dev :staging :prod"]
    end
    GH --> GA --> IMG -.despliega.-> PROC
```

Notas para el texto:
- Todo corre con Docker Compose en una sola máquina, sin nube. Hay un contenedor scheduler por entorno (`scheduler-dev`, `scheduler-staging` y `scheduler-prod`). Los tres entornos usan el **mismo código**; cambian la base (`agro_<entorno>`), la carpeta del lake (`storage/<entorno>/`) y `config/environments/<entorno>.yaml`.
- Grafana entra con el usuario `dashboard`, que solo puede leer `gold` (RNF04).

---

## 2. Esquema Medallion

Qué se ve: qué contiene cada capa, qué la transforma en la siguiente y adónde van los rechazos.

```mermaid
flowchart LR
    SRC["Fuentes<br/>Open-Meteo + IoT"]

    subgraph BRONZE["BRONZE · crudo"]
        B[("Parquet<br/>tal como llegó<br/>+ linaje: _batch_id,<br/>_ingested_at, _source_system<br/><b>nunca se modifica</b>")]
    end

    subgraph SILVER["SILVER · limpio"]
        S[("Parquet<br/>tipado (UTC)<br/>VALID + WARNING")]
    end

    subgraph QUAR["QUARANTINE · rechazados"]
        Q[("Parquet<br/>INVALID sin tocar<br/>+ _rejection_reasons")]
    end

    subgraph GOLD["GOLD · negocio (PostgreSQL)"]
        G[("daily_field_metrics<br/>por fecha · campo · fuente<br/>+ dq_run_metrics, dq_errors")]
    end

    DASH["Dashboards<br/>Grafana"]

    SRC -->|"extracción incremental<br/>(watermark)"| B
    B -->|"tipado · deduplicación<br/>reglas DQ01–DQ12"| S
    B -->|"1 regla de rechazo<br/>invalida el registro"| Q
    S -->|"recalcula los días afectados<br/>upsert idempotente"| G
    Q -.->|"solo cuenta para<br/>el % de calidad"| G
    G --> DASH
    B -.->|"reproceso sin volver<br/>a llamar a la fuente"| S
```

Notas para el texto:
- **DQ Score estricto** = VALID / total × 100. **% utilizable** = (VALID + WARNING) / total × 100.
- Un WARNING se publica marcado; un rechazo en cualquier variable manda el registro completo a Quarantine (decisión D22).
- Reproceso: `python -m src.main --reprocess <batch_id>` regenera Silver, Quarantine y Gold desde Bronze.

---

## 3. Base de datos

### 3a. Versión compacta (para el cuerpo del documento)

Solo tablas, claves y relaciones. Línea continua: clave foránea real. Línea punteada: relación lógica sin clave foránea.

```mermaid
erDiagram
    GOLD_FIELDS["gold.fields"] {
        text field_id PK
    }
    GOLD_DAILY["gold.daily_field_metrics"] {
        date fecha PK
        text field_id PK, FK
        text fuente PK
    }
    GOLD_RUNS["gold.dq_run_metrics"] {
        text _batch_id PK
        text run_status "SUCCESS / FAILED"
    }
    GOLD_ERRORS["gold.dq_errors"] {
        bigserial error_id PK
        text _batch_id FK
    }
    GOLD_LAYERS["gold.pipeline_layer_metrics"] {
        text _batch_id PK, FK
        text layer PK
        text entity PK
    }
    GOLD_TRACE["gold.etl_trace"] {
        text trace_id PK
        text _batch_id FK
    }
    GOLD_TRACE_STEPS["gold.etl_trace_steps"] {
        text trace_id PK, FK
        integer step PK
        integer orden PK
    }
    ETL_WATERMARKS["etl.watermarks"] {
        text domain PK
        text entity PK
    }

    GOLD_FIELDS ||--o{ GOLD_DAILY : "field_id"
    GOLD_RUNS ||--o{ GOLD_ERRORS : "_batch_id"
    GOLD_RUNS ||--o{ GOLD_LAYERS : "_batch_id"
    GOLD_RUNS ||--o{ GOLD_TRACE : "_batch_id"
    GOLD_TRACE ||--|{ GOLD_TRACE_STEPS : "trace_id"
    GOLD_DAILY }o..o| GOLD_RUNS : "último lote"
    ETL_WATERMARKS }o..o| GOLD_RUNS : "último lote"
```

### 3b. Versión completa (para el anexo)

```mermaid
erDiagram
    ETL_WATERMARKS["etl.watermarks"] {
        text domain PK "agro"
        text entity PK "open_meteo / iot_simulator"
        timestamptz watermark "fin de la última ventana"
        text last_batch_id
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
        date fecha PK "hora local"
        text field_id PK, FK
        text fuente PK
        numeric temperatura_promedio
        numeric precipitacion_total
        numeric humedad_suelo_promedio
        numeric humedad_ambiental_promedio
        integer cantidad_mediciones "VALID + WARNING"
        numeric porcentaje_calidad "estricto"
        text _batch_id
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
        numeric dq_score "VALID / total"
        numeric pct_utilizable "(VALID + WARNING) / total"
        text run_status "SUCCESS / FAILED"
        timestamptz started_at
        timestamptz finished_at
        numeric duration_seconds
        timestamptz last_measured_at "frescura"
    }
    GOLD_ERRORS["gold.dq_errors"] {
        bigserial error_id PK
        text _batch_id FK
        timestamptz detected_at
        timestamptz measured_at
        text source
        text field_id "sin FK (DQ04)"
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
        text location
        timestamptz window_start
        timestamptz window_end
        timestamptz started_at
        timestamptz finished_at
    }
    GOLD_TRACE["gold.etl_trace"] {
        text trace_id PK
        text _batch_id FK
        timestamptz created_at
        text dq_status
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
    GOLD_RUNS ||--o{ GOLD_ERRORS : "_batch_id (CASCADE)"
    GOLD_RUNS ||--o{ GOLD_LAYERS : "_batch_id (CASCADE)"
    GOLD_RUNS ||--o{ GOLD_TRACE : "_batch_id (CASCADE)"
    GOLD_TRACE ||--|{ GOLD_TRACE_STEPS : "trace_id (CASCADE)"
    GOLD_DAILY }o..o| GOLD_RUNS : "_batch_id, sin FK"
    GOLD_FIELDS |o..o{ GOLD_ERRORS : "field_id, sin FK"
    GOLD_FIELDS |o..o{ GOLD_TRACE : "field_id, sin FK"
    ETL_WATERMARKS }o..o| GOLD_RUNS : "last_batch_id, sin FK"
```

Bronze, Silver y Quarantine no aparecen: viven en el lake Parquet, no en PostgreSQL. La explicación de cada tabla está en [`modelo_datos.md`](modelo_datos.md).
