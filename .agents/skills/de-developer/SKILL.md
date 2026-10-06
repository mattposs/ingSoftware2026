---
name: de-developer
description: Guía genérica y estándares de desarrollo para pipelines ETL/ELT con Python y Pandas bajo arquitectura Medallion Lakehouse (Bronze/Silver en Parquet y Gold con Upsert en PostgreSQL).
---

# Guía Genérica de Desarrollo Data Engineering: Pipeline Medallion con Pandas & PostgreSQL

Esta skill define el blueprint, patrones de diseño y estándares de código reutilizables para cualquier pipeline ETL/ELT implementado con **Python**, **Pandas**, almacenamiento columnar **Parquet** y **PostgreSQL** como capa de consumo.

Es aplicable a cualquier dominio (IoT, Finanzas, E-commerce, Logística, Marketing, etc.).

---

## 1. Arquitectura Medallion + Serving Relacional

```mermaid
flowchart LR
    subgraph Ingestion ["1. Bronze (Raw Landing)"]
        Source[Cualquier Origen<br/>REST API / DB / S3 / Archivos] --> Extract[Extractor Genérico<br/>Filtro por Watermark]
        Extract -->|Append Metadatos Técnicos| BronzeLake[(Bronze Storage<br/>Raw Parquet Inmutable)]
    end

    subgraph Processing ["2. Silver (Curated & Quality)"]
        BronzeLake --> Transform[Limpieza, Tipado & DQ Rules<br/>Procesa solo el nuevo Batch]
        Transform -->|Válidos / Warnings| SilverLake[(Silver Storage<br/>Clean Parquet)]
        Transform -->|Inválidos| QuarantineLake[(Quarantine Storage<br/>Rejected Parquet + Motivo)]
    end

    subgraph Serving ["3. Gold (Business & Serving)"]
        SilverLake --> Modeling[Modelado Dimensional / KPIs<br/>Agregación del Delta]
        Modeling -->|Upsert Idempotente| PostgresDB[(PostgreSQL Gold<br/>Tablas Finales / Serving Layer)]
    end
```

### Roles de cada capa:
* **Bronze (Lakehouse Raw):** Preserva la verdad original de la fuente sin alteraciones. Almacena en **Parquet** con compresión (`snappy`) y metadatos técnicos de auditoría. Es estrictamente **Append-only**.
* **Silver (Lakehouse Curated):** Aplica tipos de datos estrictos, normalización, deduplicación y reglas de calidad sobre el lote nuevo. **Bifurca** los registros fallidos a una sub-capa de **Quarantine** para no contaminar los datos buenos sin perder trazabilidad de errores.
* **Gold (PostgreSQL Serving Layer):** Capa modelada para el negocio (modelos estrella, tablas agregadas, indicadores). Se carga mediante **Upsert idempotente** (`ON CONFLICT DO UPDATE`), permitiendo insertar registros nuevos o actualizar métricas preexistentes en milisegundos.

---

## 2. Estrategia de Carga Incremental y Control de Estado (Watermarking)

Procesar toda la historia en cada ejecución (*Full Refresh*) es ineficiente y no escala. Los pipelines deben operar de forma **incremental por deltas**:

```mermaid
flowchart TD
    subgraph Ingesta Incremental
        State[Control de Estado / Watermark<br/>Última marca procesada: T_last] --> Query[Llamada API / Origen<br/>start = T_last, end = now]
        Query --> NewBatch[batch_{uuid}.parquet]
    end

    subgraph Procesamiento Incremental
        NewBatch --> SilverRun[Notebook Silver: procesa<br/>ÚNICAMENTE el nuevo batch]
        SilverRun --> CleanBatch[clean_{uuid}.parquet]
        SilverRun --> RejectBatch[rejected_{uuid}.parquet]
    end

    subgraph Carga Incremental
        CleanBatch --> GoldAgg[Calcular KPIs/Agregados<br/>para las entidades/fechas del batch]
        GoldAgg --> UpsertPostgres[UPSERT atómico en PostgreSQL<br/>ON CONFLICT DO UPDATE]
        UpsertPostgres --> UpdateState[Actualizar Watermark en Estado: T_now]
    end
```

### Comportamiento Incremental por Capa:

1. **Bronze (Watermark Extraction):**
   * Se consulta el **Watermark** (último timestamp, ID secuencial o fecha procesada).
   * La extracción consulta a la fuente únicamente el rango comprendido entre `[watermark, now()]`.
   * El resultado se escribe como un nuevo archivo Parquet con su propio `_batch_id`. **Bronze nunca reescribe el pasado.**

2. **Silver (Batch Isolation):**
   * La notebook de Silver procesa únicamente el nuevo `batch_{uuid}.parquet` generado por la ingesta.
   * Valida la calidad de ese lote y persiste `clean_{uuid}.parquet` y/o `rejected_{uuid}.parquet`.

3. **Gold (Recálculo de claves afectadas + Upsert):**
   * Del lote limpio recién generado se obtienen las **claves de negocio afectadas** (ej. `(fecha, entidad_id)`).
   * Para esas claves se **recalculan las métricas con TODO el histórico de Silver**, no solo con el lote.
     > ⚠️ Agregar solo el delta y hacer `DO UPDATE SET col = EXCLUDED.col` **pisa** las métricas: si un día llega en dos lotes, el promedio y el conteo quedan con los valores del segundo lote solamente.
   * Al ejecutar el **Upsert (`ON CONFLICT DO UPDATE`)** en PostgreSQL:
     - Si la clave es nueva $\rightarrow$ se **inserta**.
     - Si la clave ya existía $\rightarrow$ se **reemplaza** por el valor recalculado (correcto e idempotente).

### Qué guardar como Watermark
* Guardar el **fin de la ventana consultada**, no el máximo timestamp de los datos limpios (un timestamp futuro lo adelantaría, un lote vacío lo dejaría en `NaT` y los registros rechazados se volverían a extraer).
* La ventana siguiente es `(watermark, now]`: **inicio exclusivo** para no repetir el registro del borde.
* Actualizar el watermark cuando el lote quedó persistido en **Bronze**: Silver y Gold se reprocesan desde Bronze sin volver a llamar a la fuente.

### Reglas que comparan con la lectura anterior
Deduplicación contra lotes previos, detección de huecos y de saltos bruscos necesitan la **lectura anterior**, que con carga incremental suele estar en otro lote. Silver debe recibir como contexto las últimas lecturas de Silver histórico para evaluarlas.

### Reprocesamiento Histórico (*Backfills*):
Si una regla de negocio o transformación cambia en el futuro, no es necesario volver a consultar las fuentes externas: basta con leer la colección histórica de Parquets inmutables en Bronze y re-ejecutar Silver y Gold.

---

## 3. Convención Universal de Particionado y Rutas

Estructura de paths estandarizada para sistemas de archivos locales, S3 o Azure Blob Storage:

```text
storage/   (ignorado por Git; no usar data/, que es para fixtures de tests)
├── bronze/{domain}/{entity}/year={YYYY}/month={MM}/batch_{batch_id}.parquet
├── silver/{domain}/{entity}/year={YYYY}/month={MM}/clean_{batch_id}.parquet
└── quarantine/{domain}/{entity}/year={YYYY}/month={MM}/rejected_{batch_id}.parquet
```

### Metadatos de Linaje Obligatorios
Todo registro procesado desde Bronze en adelante debe conservar las siguientes columnas técnicas:
- `_batch_id`: Identificador único de ejecución (UUIDv4).
- `_ingested_at`: Timestamp UTC del momento exacto de captura.
- `_source_system`: Nombre del origen o conector (ej: `crm_api`, `sap_db`, `iot_devices`).

---

## 4. Templates de Código Reutilizables

Para mantener la skill concisa y modular, el código ejecutable de cada patrón se encuentra separado en archivos de plantilla listos para importar o copiar a `src/`:

| Componente | Template | Descripción |
|---|---|---|
| **Control de Estado** | [state_manager.py](./templates/state_manager.py) | Clase `StateManager` para persistir y consultar el watermark incremental en JSON/DB. |
| **Ingesta Bronze** | [bronze_writer.py](./templates/bronze_writer.py) | Inyección de columnas de linaje (`enrich_with_lineage`) y guardado Parquet particionado (`write_to_parquet_lake`). |
| **Validación Silver** | [silver_validator.py](./templates/silver_validator.py) | Evaluación vectorizada de reglas de calidad y bifurcación a `clean` y `quarantine` (`validate_and_quarantine`). |
| **Upsert Gold** | [gold_upsert.py](./templates/gold_upsert.py) | Carga idempotente y atómica en PostgreSQL con staging temporal y `ON CONFLICT DO UPDATE` (`upsert_to_postgres`). |

### Guía Rápida de Uso en Notebooks / Módulos:

> La carpeta `templates/` incluye `__init__.py`, así que se importa como paquete (`from templates.x import ...`).
> Los umbrales de las reglas deben venir de un archivo de configuración versionado (ej. `config/rules.yaml`), no hardcodeados.

#### 1. Ingesta Incremental (Bronze)
```python
import uuid
from datetime import datetime, timezone
from templates.state_manager import StateManager
from templates.bronze_writer import enrich_with_lineage, write_to_parquet_lake

state = StateManager()
batch_id = str(uuid.uuid4())
window_start = state.get_watermark(domain="telemetry", entity="devices")  # None = primera corrida
window_end = datetime.now(timezone.utc).isoformat()

# 1. Extraer la ventana (window_start, window_end] desde la fuente externa
df_raw = extract_from_api(start_exclusive=window_start, end=window_end)

# 2. Agregar linaje, persistir en Bronze y recién ahí avanzar el watermark al FIN DE LA VENTANA
df_bronze = enrich_with_lineage(df_raw, source_system="iot_hub", batch_id=batch_id)
write_to_parquet_lake(df_bronze, layer="bronze", domain="telemetry", entity="devices", batch_id=batch_id)
state.set_watermark("telemetry", "devices", new_watermark=window_end, last_batch_id=batch_id)
```

#### 2. Limpieza y Data Quality (Silver)
```python
from templates.silver_validator import validate_and_quarantine

# Reglas declarativas: True si es válido, False si viola la regla
reject_rules = {
    "ERR_NULL_ID": df_bronze["device_id"].notnull(),
    "ERR_TEMP_OUT_OF_BOUNDS": df_bronze["temperature"].between(-40, 85),
    "ERR_INVALID_TIMESTAMP": pd.to_datetime(df_bronze["event_time"], errors="coerce", utc=True).notna(),
}
warning_rules = {
    "WARN_TEMP_UNUSUAL": df_bronze["temperature"].between(-15, 45),
}

df_clean, df_rejected = validate_and_quarantine(
    df=df_bronze, rules=reject_rules, warning_rules=warning_rules,
    domain="telemetry", entity="devices", batch_id=batch_id,
)
```

#### 3. Modelado y Upsert Idempotente (Gold)
```python
from templates.gold_upsert import upsert_to_postgres

# 1. Claves de negocio tocadas por el lote
keys = df_clean[["event_date", "device_id"]].drop_duplicates()

# 2. Recalcular esas claves con TODO Silver (no solo con df_clean)
silver_all = read_all_silver("telemetry", "devices")
df_gold = (silver_all.merge(keys, on=["event_date", "device_id"])
           .groupby(["event_date", "device_id"])
           .agg(avg_temp=("temperature", "mean"), total_events=("temperature", "count"))
           .reset_index())

# 3. Upsert en PostgreSQL
upsert_to_postgres(
    df=df_gold, table_name="daily_device_metrics", schema="gold",
    engine=db_engine, conflict_keys=["event_date", "device_id"],
)
```

---

## 5. Estructura y Buenas Prácticas para Notebooks

Cuando el pipeline se organiza en Notebooks Jupyter (`.ipynb`), seguir el patrón **Notebook como Runner**:

1. **Una Notebook por Etapa y Entidad:**
   - `01_bronze_{entity}.ipynb`: Ingesta incremental por watermark y aterrizaje a Parquet.
   - `02_silver_{entity}.ipynb`: Limpieza del batch, reglas de Data Quality y guardado en Silver/Quarantine.
   - `03_gold_{entity}.ipynb`: Agregación del delta y Upsert a PostgreSQL.
2. **Notebook como Orquestador Delgado (Thin Runner):**
   - No programar lógica compleja dentro de las celdas de la notebook.
   - La lógica reutilizable (StateManager, validadores, helpers de DB) debe ubicarse en módulos `.py` (ej. en `src/`).
   - La notebook debe simplemente **importar** las funciones, pasar parámetros y mostrar tablas/gráficos interactivos para monitoreo visual.
3. **Idempotencia y Sin Estado Oculto:**
   - Debe poder ejecutarse `Kernel -> Restart & Run All` sin errores.
   - Nunca hardcodear credenciales: consumir siempre variables de entorno (`os.getenv` o `python-dotenv`).

---

## 6. Checklist para Validar Cualquier Pipeline ETL

- [ ] **Estrategia Incremental:** ¿La ingesta utiliza un watermark o ventana de tiempo en lugar de extraer toda la historia?
- [ ] **Linaje:** ¿Cada fila contiene `_batch_id`, `_ingested_at` y `_source_system`?
- [ ] **Inmutabilidad:** ¿Los datos en Bronze permanecen intactos ante reprocesamientos?
- [ ] **Quarantine:** ¿Los registros inválidos se almacenan con su lista de motivos (`_rejection_reasons`) para auditoría y KPIs de calidad?
- [ ] **Upsert:** ¿La tabla en PostgreSQL tiene definida una clave primaria / restricción única (`UNIQUE`) sobre las `conflict_keys`?
- [ ] **Idempotencia:** ¿Si ejecuto el pipeline dos veces con el mismo batch, el estado final de la base de datos es consistente y sin duplicados?
- [ ] **Gold correcto:** ¿Las métricas agregadas se recalculan con todo Silver para las claves afectadas (y no solo con el delta)?
- [ ] **Watermark:** ¿Guarda el fin de la ventana consultada y la ventana siguiente arranca de forma exclusiva?
- [ ] **Lotes vacíos:** ¿El pipeline funciona cuando un lote viene vacío o todos sus registros son rechazados?
- [ ] **Desacoplamiento:** ¿Las funciones clave pueden ser importadas y testeadas con `pytest` en un pipeline de CI/CD?
