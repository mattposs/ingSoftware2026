# Pipeline DataOps para calidad de datos agroclimáticos IoT

[![CI](https://github.com/SebastianMB1/IngSoftwareETL/actions/workflows/ci.yml/badge.svg)](https://github.com/SebastianMB1/IngSoftwareETL/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/Python-3.11+-blue)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-336791)
![Docker](https://img.shields.io/badge/Docker-compose-2496ED)

> Prueba de concepto (POC) del Proyecto Grupal de Ingeniería de Software – UADE (2026).
> Consultora: **Datum Sur** · Cliente (ficticio): **Grupo Agro del Litoral S.A.**
> Documento de proyecto: [`docs/TPO_Pipeline_DataOps_Documento_Final_v7.pdf`](docs/TPO_Pipeline_DataOps_Documento_Final_v7.pdf)
> Evidencia de la POC: [`docs/poc/EVIDENCIA_POC.md`](docs/poc/EVIDENCIA_POC.md) · Simulador para clase: [`docs/simulador_pipeline.html`](docs/simulador_pipeline.html)

## Tabla de contenidos

- [Contexto](#contexto)
- [Objetivos](#objetivos)
- [Alcance](#alcance)
- [Arquitectura](#arquitectura)
- [Modelo de datos](#modelo-de-datos)
- [Reglas de Data Quality](#reglas-de-data-quality)
- [Prueba de concepto (POC)](#prueba-de-concepto-poc)
- [Simulador interactivo](#simulador-interactivo)
- [Stack tecnológico](#stack-tecnológico)
- [Estructura del repositorio](#estructura-del-repositorio)
- [Instalación y ejecución](#instalación-y-ejecución)
- [Entornos: dev, staging y prod](#entornos-dev-staging-y-prod)
- [Dashboards](#dashboards)
- [Alertas del pipeline](#alertas-del-pipeline)
- [Tests](#tests)
- [CI/CD](#cicd)
- [Catálogo y diccionario de datos](#catálogo-y-diccionario-de-datos)
- [Convenciones de trabajo](#convenciones-de-trabajo)
- [Equipo](#equipo)
- [Documentación](#documentación)

## Contexto

Una empresa agropecuaria tiene 8 campos (20.000 ha en Entre Ríos, Santa Fe y Córdoba) con 200 sensores IoT en total. Cada sensor mide temperatura, humedad ambiental, humedad del suelo, precipitación y viento, y reporta cada 15 minutos (96 lecturas por día; 19.200 registros por día entre los 200 sensores). El simulador de la POC genera una lectura por campo (8 × 96 = 768 por día), no por sensor; ver [`docs/revision/paso-1.md`](docs/revision/paso-1.md).

Los datos llegan con faltantes, duplicados, valores fuera de rango, unidades incorrectas y períodos sin información. Alrededor del 14% de los registros tiene algún problema (tasa que simula la POC), y eso termina en decisiones de riego y siembra tomadas con datos equivocados.

Nuestro equipo actúa como consultora de Data Engineering y DataOps. El encargo es un pipeline que ingiera, valide, transforme y monitoree esos datos, con CI/CD.

## Objetivos

**Objetivo general:** diseñar e implementar un pipeline DataOps que garantice la calidad y confiabilidad de los datos agroclimáticos IoT, automatizando su validación, transformación, monitoreo y despliegue mediante CI/CD.

**Metas medibles (SMART), verificadas en la POC:**

| Meta | Cómo se verifica en el repo |
|---|---|
| 100% de los datos en Bronze con origen y fecha de ingesta | Columnas de linaje `_batch_id`, `_ingested_at`, `_source_system` |
| Las 12 reglas detectan ≥ 95% de los errores inyectados | `tests/test_pipeline_units.py::test_reglas_detectan_al_menos_95_por_ciento_de_errores_inyectados` |
| 100% de rechazos en quarantine con motivo; Gold sin inválidos | `_rejection_reasons` en quarantine; `test_gold_no_contiene_registros_invalidos` (unitario) y `test_gold_no_tiene_registros_invalidos` (integración) |
| ≥ 12 tests de reglas y ≥ 80% de cobertura en validación | `tests/test_rules.py`; el CI falla si la cobertura de `src/validation` baja de 80% |
| 100% de los cambios a `main` pasan por GitHub Actions | `.github/workflows/ci.yml` + *branch protection* (ver [CI/CD](#cicd)) |
| DQ Score por campo y día; dashboard solo sobre Gold | `gold.daily_field_metrics.porcentaje_calidad` (estricto), `gold.dq_run_metrics.dq_score` (estricto) y `pct_utilizable`, usuario `dashboard` de solo lectura |
| Corrida de un día de datos en < 5 minutos | El pipeline informa la duración al terminar: 9,9 s en la corrida de la POC ([`docs/poc/03_corrida_pipeline.txt`](docs/poc/03_corrida_pipeline.txt)) |

## Alcance

**Incluido:** ingesta desde Open-Meteo Historical Weather API y simulador de sensores IoT; almacenamiento raw; validación, clasificación y quarantine; métricas de calidad; CI/CD; dataset final para dashboards.

**Fuera de alcance:** aplicación móvil, control físico de sensores, automatización de maquinaria, predicción con Machine Learning, alta disponibilidad, integración con todos los sistemas del cliente y gestión formal de incidentes de calidad.

## Arquitectura

```mermaid
flowchart TD
    A[Open-Meteo<br/>Historical API · horario] --> X
    B[Simulador IoT<br/>8 campos · cada 15 min] --> X
    X[Extracción incremental<br/>watermark + linaje] --> C
    W[(etl.watermarks)] <-.-> X
    subgraph Lake["Lake Parquet (storage/)"]
        C[(Bronze<br/>append-only, sin corregir)]
        D[(Silver<br/>VALID + WARNING)]
        F[(Quarantine<br/>INVALID + motivo)]
    end
    C -->|tipado, dedup,<br/>reglas DQ01–DQ12| D
    C --> F
    subgraph PG["PostgreSQL"]
        E[(gold.daily_field_metrics)]
        M[(gold.dq_run_metrics)]
        R[(gold.dq_errors)]
        T[(gold.etl_trace ·<br/>pipeline_layer_metrics)]
    end
    D -->|recálculo de días afectados<br/>+ upsert idempotente| E
    F -->|motivos| R
    E --> G[Dashboards<br/>Grafana]
    M --> G
    R --> G
    T --> G
```

| Capa | Dónde | Contenido |
|---|---|---|
| **Bronze** | `storage/bronze/agro/{fuente}/…/batch_{id}.parquet` | Datos tal como llegaron: `timestamp` (texto crudo), `field_id`, coordenadas, las 5 variables con su unidad, `source` y linaje. Nunca se modifica. |
| **Silver** | `storage/silver/agro/measurements/…/clean_{id}.parquet` | Registros tipados (timestamp UTC) clasificados `VALID` o `WARNING`, con `_dq_warnings`. |
| **Quarantine** | `storage/quarantine/agro/measurements/…/rejected_{id}.parquet` | Registros `INVALID` sin modificar, con `_rejection_reasons` (ej. `DQ05;DQ07`). |
| **Gold** | PostgreSQL, esquema `gold` | Indicadores diarios por campo y fuente, métricas de cada corrida, registro de errores, métricas por capa y trazas de registros de muestra. |

Los lakes están separados por entorno (`storage/dev/`, `storage/staging/`, `storage/prod/`) y Gold vive en una base por entorno (`agro_dev`, `agro_staging`, `agro_prod`).

**Incremental:** cada corrida trae solo la ventana `(watermark, ahora]` de cada fuente. Hoy el watermark (`etl.watermarks`) se actualiza al terminar Bronze; si una etapa posterior falla, el lote queda en Bronze y se recupera con `--reprocess`. Gold recalcula con todo Silver los días y campos afectados, así que un día que llega en varios lotes queda correcto.

**Reproceso:** si cambia una regla, `python -m src.main --reprocess <batch_id>` regenera Silver, Quarantine y Gold desde Bronze, sin volver a llamar a la API.

**Data Quality Score (estricto)** = VALID / total × 100; **% utilizable** = (VALID + WARNING) / total × 100. Las decisiones de diseño están en [`docs/decisiones.md`](docs/decisiones.md).

## Modelo de datos

![Diagrama de base de datos](<docs/Diagrama de base de datos.png>)

Ocho tablas en dos esquemas: `etl.watermarks` (control de la extracción) y, en `gold`, `fields` (los 8 campos LIT-01 a LIT-08), `daily_field_metrics`, `dq_run_metrics`, `dq_errors`, `pipeline_layer_metrics`, `etl_trace` y `etl_trace_steps`. El script está en [`sql/schema/01_schema.sql`](sql/schema/01_schema.sql). El diagrama en Mermaid, con la explicación de cada tabla y relación, está en [`docs/modelo_datos.md`](docs/modelo_datos.md) (versión vectorial: [`docs/modelo_datos.svg`](docs/modelo_datos.svg)).

## Reglas de Data Quality

Los umbrales están en [`config/rules.yaml`](config/rules.yaml), versionados en Git. Cambiar un rango no requiere tocar código (RNF06).

| ID | Regla | Tipo | Criticidad | Criterio | Acción |
|---|---|---|---|---|---|
| DQ01 | `timestamp` obligatorio | Completitud | Crítica | No nulo ni vacío | Rechazar |
| DQ02 | `field_id` obligatorio | Completitud | Crítica | No nulo ni vacío | Rechazar |
| DQ03 | Timestamp con formato válido | Consistencia | Crítica | ISO 8601; no futuro (tolerancia 10 min); posterior a 2000 | Rechazar |
| DQ04 | Campo existente | Integridad | Crítica | `field_id` en `config/fields.yaml` (LIT-01 a LIT-08) | Rechazar |
| DQ05 | Sin duplicados | Unicidad | Crítica | Clave `(source, field_id, timestamp)`, también contra lotes anteriores; se conserva el primero | Rechazar |
| DQ06 | Unidades esperadas | Consistencia | Crítica | °C · % · m³/m³ · mm · km/h | Rechazar |
| DQ07 | Humedad ambiental | Validez | Alta | 0 ≤ humedad ≤ 100 | Rechazar |
| DQ08 | Precipitación | Validez | Alta | ≥ 0 mm | Rechazar |
| DQ09 | Temperatura | Validez | Alta | Rechazo fuera de −40 a 60 °C; warning fuera de −15 a 45 °C | Rechazar / Warning |
| DQ10 | Humedad del suelo | Validez | Alta | Rechazo fuera de 0 a 1 m³/m³; warning fuera de 0,02 a 0,60 | Rechazar / Warning |
| DQ11 | Sin períodos sin datos | Completitud | Media | Hueco ≥ 30 min (IoT) o ≥ 120 min (Open-Meteo) por campo y variable | Warning |
| DQ12 | Sin cambios anormales | Anomalía | Media | Temperatura > 8 °C/h · humedad > 40 pts/h · suelo > 0,15 m³/m³ por hora | Warning |

**Un rechazo en una sola variable invalida el registro completo.** Cada registro trae las cinco variables a la vez. Si una sola incumple una regla de rechazo (por ejemplo, humedad ambiental de 135 %, regla DQ07), el registro entero va a Quarantine con ese motivo: las otras cuatro variables, aunque estén bien, no llegan a Silver ni a Gold. Un WARNING, en cambio, no rechaza: el registro se publica y queda marcado. Ver la decisión D22 en [`docs/decisiones.md`](docs/decisiones.md).

## Prueba de concepto (POC)

Corrida real del pipeline, sin datos inventados: lote `ece83881-91dc-4356-b6cf-eb7ddfa7f759`, 20/10/2026 23:07 UTC, en Docker Compose con la configuración de STAGING, sobre una base y un lake vacíos (`agro_poc`).

| Indicador | Resultado |
|---|---|
| Registros ingestados | 1.343: 576 de Open-Meteo (13/10 a 15/10, horarios) y 767 del simulador IoT (cada 15 min, 14,08 % con errores inyectados) |
| Clasificación | 1.193 VALID · 53 WARNING · 97 INVALID (a Quarantine) |
| DQ Score estricto | 88,83 % |
| % utilizable | 92,78 % |
| Hallazgos | 326 (el más frecuente: DQ11, períodos sin datos, con 215) |
| Duración | 9,9 s (objetivo < 300 s) |
| Tests | 93 passed · cobertura de `src/validation` 92 % |

Casos seguidos de punta a punta: **LIT-05** con humedad de suelo 1,35 m³/m³ (rechazo DQ10) y **LIT-02** con una lluvia de 2,6 mm duplicada (rechazo DQ05; Gold no la suma dos veces).

| Archivo | Contenido |
|---|---|
| [`docs/poc/EVIDENCIA_POC.md`](docs/poc/EVIDENCIA_POC.md) | Índice de la evidencia, comandos y resultados |
| [`docs/poc/seccion_11_POC.md`](docs/poc/seccion_11_POC.md) | Sección 11 del documento, redactada con estos datos |
| [`docs/poc/05_casos_punta_a_punta.md`](docs/poc/05_casos_punta_a_punta.md) | Los casos DQ10 y DQ05, de Bronze a Gold |
| [`docs/poc/capturas/`](docs/poc/capturas/) | Capturas de Grafana: indicadores de calidad, hallazgos y calidad por campo y día, mapa / lluvia / rechazados y flujo por capa |

## Simulador interactivo

[`docs/simulador_pipeline.html`](docs/simulador_pipeline.html) es una página estilo Cisco Packet Tracer para mostrar en clase cómo funciona todo, paso a paso. Se abre con doble clic, sin instalar nada. Separa en franjas el **origen** de los datos, el **código de procesamiento** y el **almacenamiento** (capas Medallion), y tiene tres modos: el viaje de un registro (incluye los dos casos de la POC), `docker compose up` paso a paso y el proyecto completo (Git, CI/CD, catálogo).

Guía de uso: [`docs/simulador_pipeline.md`](docs/simulador_pipeline.md). Para actualizarlo cuando cambia el pipeline: skill [`.agents/skills/simulador-pipeline`](.agents/skills/simulador-pipeline/SKILL.md).

## Stack tecnológico

| Componente | Tecnología |
|---|---|
| Fuente meteorológica | Open-Meteo Historical Weather API |
| Lenguaje y procesamiento | Python 3.11 · Pandas · PyArrow (Parquet) |
| Base de datos | PostgreSQL 16 (SQLAlchemy 2 + psycopg 3) |
| Data Quality | Motor propio de reglas (`src/validation`) + Pytest |
| CI/CD | GitHub Actions |
| Contenedores | Docker · Docker Compose |
| Dashboard | Grafana 11.4 (3 dashboards provisionados, solo lectura sobre `gold`) |
| Alertas | Grafana Alerting (reglas como código) + Mailpit (correo local de prueba) |
| Registro de imágenes | GitHub Container Registry (`ghcr.io`) |
| Gestión | ClickUp (Kanban) · GitHub |
| Orquestación | Apache Airflow *(opcional, no incluido en la POC)* |

## Estructura del repositorio

```
.
├── .agents/skills/            # Skills del agente: de-developer, data-governance y simulador-pipeline
├── .github/workflows/
│   ├── ci.yml                 # Lint + validación de reglas + tests + build Docker
│   └── deploy.yml             # Imagen por entorno en GHCR (push a dev / staging / main)
├── catalog/                   # Catálogo de datasets en YAML (skill data-governance)
├── config/
│   ├── rules.yaml             # Reglas DQ01–DQ12 y umbrales
│   ├── fields.yaml            # Campos del cliente (LIT-01 a LIT-08)
│   ├── pipeline.yaml          # Fuentes, ventanas, zona horaria, rutas (base de todos los entornos)
│   └── environments/          # dev.yaml, staging.yaml, prod.yaml: lo que cambia en cada entorno
├── data/                      # Datos manuales para tests (no se versionan datos reales)
├── grafana/                   # Fuentes de datos, 3 dashboards y alertas (alerting/ + render-alertas.sh)
├── docs/
│   ├── TPO_Pipeline_DataOps_Documento_Final_v7.{docx,pdf}
│   ├── arquitectura.excalidraw
│   ├── modelo_datos.md / .svg # Modelo de datos (Mermaid) + "Diagrama de base de datos.png"
│   ├── simulador_pipeline.html / .md  # Simulador interactivo para clase y su guía
│   ├── poc/                   # Evidencia de la POC, sección 11 y capturas de Grafana
│   ├── revision/              # Pasos 1 a 6 de la adaptación y comparación con la entrega final
│   ├── data_dictionary/       # Diccionario de datos por capa (generado)
│   ├── decisiones.md          # Registro de decisiones técnicas
│   ├── cambios_documento_v7.md
│   └── kanban/                # Capturas semanales del tablero
├── scripts/                   # simulate_alerts.py (evidencia de alertas) y verify_rnf.py (RNF medidos)
├── notebooks/                 # Runners delgados por etapa: 01_bronze, 02_silver, 03_gold
├── sql/                       # Crea agro_dev / agro_staging / agro_prod, esquema (schema/) y usuarios
├── src/
│   ├── main.py                # Punto de entrada (python -m src.main)
│   ├── pipeline.py            # Etapas run_bronze / run_silver / run_gold
│   ├── config.py              # Carga de config/*.yaml y .env
│   ├── common/                # Lake Parquet, conexión y upsert, watermarks
│   ├── ingestion/             # Open-Meteo y simulador IoT
│   ├── validation/            # Motor de reglas DQ01–DQ12 y chequeo de rules.yaml
│   ├── transformation/        # Gold: indicadores diarios
│   ├── metrics/               # DQ Score, dq_run_metrics y dq_errors
│   └── governance/            # Catalogación de datasets
├── storage/                   # Lake Parquet generado (ignorado por Git)
├── tests/                     # Pytest: reglas, pipeline, dashboards, entornos e integración con PostgreSQL
├── Dockerfile
├── docker-compose.yml
├── requirements.txt / requirements-dev.txt
└── .env.example
```

## Instalación y ejecución

### Requisitos

- Python 3.11+
- Docker Desktop (Docker Compose)
- Git

### Pasos

```bash
# 1. Clonar el repositorio
git clone https://github.com/SebastianMB1/IngSoftwareETL.git
cd IngSoftwareETL

# 2. Variables de entorno: no hace falta nada, el código y Docker usan .env.example.
#    Para usar contraseñas propias: cp .env.example .env y editarlo (.env pisa a .env.example y no se sube a Git)

# 3. Levantar todo: PostgreSQL + pipeline programado en DEV, STAGING y PROD (cada 15 min) + dashboards
docker compose up -d
# Dashboards: http://localhost:3000 (se ven sin login; admin / GRAFANA_ADMIN_PASSWORD para editar)
# Correos de las alertas: http://localhost:8025 (Mailpit)

# 4. Instalar dependencias en un entorno virtual
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt

# 5. Ejecutar el pipeline (corrida incremental de ambas fuentes)
python -m src.main

# 6. Ejecutar los tests
pytest
```

Otras formas de correrlo:

```bash
python -m src.main --env staging              # elegir entorno: dev (defecto), staging o prod
python -m src.main --source iot_simulator     # una sola fuente (no necesita internet)
python -m src.main --reprocess <batch_id>     # regenerar Silver y Gold de un lote desde Bronze
docker compose --profile run run --rm pipeline  # el pipeline completo dentro de Docker
```

Para correr las etapas por separado y explorar los datos están las notebooks de `notebooks/`.

> **Seguridad (RNF07):** nunca subir credenciales. `.env` está en `.gitignore`. En el pipeline de CI se usan GitHub Secrets, y el pipeline se conecta con un usuario de permisos mínimos.
>
> **Windows + OneDrive:** si la ruta del repo es muy larga, los archivos del lake pueden superar el límite de 260 caracteres. En ese caso, apuntar `STORAGE_PATH` a una ruta corta (ej. `C:\agro-storage`).

## Entornos: dev, staging y prod

El mismo código corre en tres entornos aislados. Cada uno tiene su propia base, su propio lake y su propio *scheduler*. Los tres son **locales**: corren con Docker Compose en la misma máquina (un PostgreSQL con tres bases), sin nube y sin costo adicional (decisión D17):

| Entorno | Para qué | Base | Lake | Configuración |
|---|---|---|---|---|
| **DEV** | Probar código y reglas nuevas | `agro_dev` | `storage/dev/` | Solo simulador IoT, 20% de errores inyectados (para ejercitar todas las reglas); STAGING y PROD usan el 14% |
| **STAGING** | Ensayo general antes de producción | `agro_staging` | `storage/staging/` | Igual que PROD (ambas fuentes), con datos propios |
| **PROD** | Lo que consume el cliente | `agro_prod` | `storage/prod/` | Configuración base ([`config/pipeline.yaml`](config/pipeline.yaml)) |

- Lo que cambia por entorno está en [`config/environments/`](config/environments/) y se superpone a `config/pipeline.yaml`. Las **reglas de calidad son las mismas** en los tres.
- El entorno se elige con `APP_ENV` (o `--env`). Por defecto es **dev**, así nunca se escribe en producción por accidente.
- En Grafana, el selector **Entorno** (arriba a la izquierda) cambia los tres dashboards entre DEV, STAGING y PROD.

**Ramas y despliegue** ([`.github/workflows/deploy.yml`](.github/workflows/deploy.yml)). Cada rama es un entorno, y los cambios avanzan por PR:

```mermaid
flowchart LR
    F[feature/*] -->|PR| D[dev]
    D -->|PR| S[staging]
    S -->|PR + revisión| M[main]
    D -.->|push: CI + deploy| DE[development · APP_ENV=dev]
    S -.->|push: CI + deploy| SE[staging · APP_ENV=staging]
    M -.->|push: CI + aprobación + deploy| PE[production · APP_ENV=prod]
```

Cada push a `dev`, `staging` o `main` corre el CI completo, publica la imagen `ghcr.io/sebastianmb1/ingsoftwareetl:<entorno>` y ejecuta el paso **Deploy**. Mientras no haya servidor (la POC corre local), ese paso solo informa la imagen publicada. Para que un entorno local use la imagen publicada: `PROD_IMAGE=ghcr.io/sebastianmb1/ingsoftwareetl:prod docker compose up -d scheduler-prod`.

**Configuración pendiente en GitHub** (Settings → Environments):
- En `production`, activar *Required reviewers* para que el deploy a producción pida aprobación.
- Cuando haya hosting, cargar en cada entorno los secrets `DEPLOY_HOST`, `DEPLOY_USER` y `DEPLOY_SSH_KEY`: el paso Deploy pasa a desplegar solo, por SSH, con `docker compose`.
- En Settings → Branches, proteger `main` (y conviene también `staging`) con PR obligatorio y los checks del CI.

## Dashboards

Con `docker compose up -d`, Grafana queda en **http://localhost:3000** con tres dashboards enlazados entre sí (botones arriba a la derecha) y el selector de **Entorno**. El primero es *Calidad de datos agroclimáticos* ([`grafana/dashboards/calidad-datos.json`](grafana/dashboards/calidad-datos.json)). Lee solo tablas de `gold`, con el usuario de solo lectura `dashboard`.

| Sección | Qué muestra |
|---|---|
| Última corrida | DQ Score estricto, % utilizable, registros procesados, VALID / WARNING / INVALID y hace cuánto corrió |
| Evolución de la calidad | DQ Score estricto y % utilizable por corrida (meta 95%) y hallazgos por regla DQ01–DQ12 |
| Clima por campo | Temperatura y humedad del suelo diarias por campo, mapa de los 8 campos (tamaño = lluvia, color = calidad) y lluvia acumulada |
| Calidad por campo y día | % de calidad por campo y día, y los últimos registros rechazados con su regla |

Un segundo dashboard, **Flujo del ETL (Bronze · Silver · Gold)** ([`grafana/dashboards/flujo-etl.json`](grafana/dashboards/flujo-etl.json)), muestra cómo se mueve cada lote por las capas. Los dos dashboards están enlazados entre sí (botón arriba a la derecha).

| Sección | Qué muestra |
|---|---|
| Recorrido de los datos | Diagrama Fuentes → Bronze → Reglas DQ → Silver / Quarantine → Gold → Dashboards, con la cantidad de registros de cada etapa en el período |
| ¿Qué hace cada capa? | Dónde vive cada capa, qué pasa en ella y su regla principal |
| Lote a lote | Cómo se reparte cada lote entre Silver y Quarantine, cuánto tarda cada etapa, las ventanas incrementales por fuente y el historial de lotes |

El tercero, **ETL paso a paso** ([`grafana/dashboards/etl-paso-a-paso.json`](grafana/dashboards/etl-paso-a-paso.json)), sigue **un registro real** por las 5 etapas. Con el selector **Registro** se elige uno válido, uno con warning o uno rechazado de los últimos lotes:

| Paso | Qué se ve |
|---|---|
| Camino del registro | Diagrama con las etapas que recorrió en color y las que no le tocaron en gris |
| 1 · Extracción | Cómo llegó de la fuente: timestamp como texto y cada valor con su unidad |
| 2 · Bronze | El archivo Parquet donde quedó y su linaje, sin ningún cambio |
| 3 · Validación | Las 12 reglas con ✔ Cumple / ⚠ Warning / ✖ Rechaza y el detalle |
| 4 · Silver o Quarantine | A dónde fue: tipado en Silver, o sin tocar y con el motivo en Quarantine |
| 5 · Gold | El indicador diario al que aportó, o por qué nunca llegó |

Las muestras salen de `gold.etl_trace` y `gold.etl_trace_steps` (unos pocos registros por lote, priorizando variedad). Las métricas por capa salen de `gold.pipeline_layer_metrics`, donde cada etapa registra cuántos registros procesó, cuánto tardó y qué ventana pidió a la fuente.

Los filtros de arriba eligen la **fuente** (Open-Meteo o Simulador IoT) y los **campos**. El servicio `scheduler` corre el pipeline cada `PIPELINE_INTERVAL_SECONDS` (15 min por defecto), así que el tablero se actualiza solo.

Colores: un color fijo por campo (paleta validada para daltonismo) y verde / amarillo / rojo solo para estados de calidad, siempre acompañados de un texto o un ícono.

## Alertas del pipeline

Grafana evalúa cada minuto dos reglas, provisionadas como código, para STAGING y PROD. DEV no tiene alertas porque inyecta errores a propósito (decisión D25).

| ID | Alerta | Severidad | Se dispara si… |
|---|---|---|---|
| AL01 | Corrida fallida o ausente | crítica | la última corrida terminó `FAILED`, o no hay filas nuevas en `gold.dq_run_metrics` hace más de 30 min (2 ciclos) |
| AL02 | Caída del DQ Score | alta | el DQ Score estricto de la última corrida es < 80 %, o cae más de 10 puntos contra el promedio de las 24 h anteriores |

- **Notificaciones:** por correo a **Mailpit**, un servidor SMTP local de prueba que guarda los correos sin enviarlos: http://localhost:8025. La dirección sale de `ALERT_EMAIL_TO`.
- **Umbrales:** `ALERT_AL01_MINUTOS_SIN_CORRIDAS`, `ALERT_AL02_DQ_SCORE_MINIMO` y `ALERT_AL02_CAIDA_MAXIMA_PUNTOS` en `.env.example` (o `.env`). Se aplican con `docker compose up -d grafana`, sin tocar las consultas. Las reglas están en [`grafana/alerting/reglas-pipeline.yml.tmpl`](grafana/alerting/reglas-pipeline.yml.tmpl); [`grafana/render-alertas.sh`](grafana/render-alertas.sh) completa los umbrales al arrancar Grafana.
- **Panel de salud:** el dashboard de calidad suma la fila *Salud del pipeline*: estado de la última corrida, duración, minutos desde la última corrida, frescura (`finished_at − last_measured_at`) y corridas fallidas en 24 h.
- **Registro de corridas:** cada corrida guarda `run_status` (SUCCESS / FAILED), `started_at`, `finished_at`, `duration_seconds` y `last_measured_at`, también las que fallan. El pipeline agrega esas columnas al arrancar si la base es anterior (decisiones D23 y D24).
- **Probarlas (solo STAGING):** `python scripts/simulate_alerts.py` provoca una corrida fallida (AL01) y una caída del score (AL02), toma capturas y escribe [`docs/evidencia_alertas/resumen.md`](docs/evidencia_alertas/resumen.md). `python scripts/verify_rnf.py` mide los RNF con datos reales en [`docs/evidencia_alertas/rnf_medidos.md`](docs/evidencia_alertas/rnf_medidos.md). Las capturas necesitan `pip install -r scripts/requirements-evidencia.txt` y `python -m playwright install chromium`.
- **Variables solo para pruebas** (apagadas por defecto): `PIPELINE_FORCE_FAILURE=true` hace fallar la corrida y `PIPELINE_IOT_ERROR_RATE=0.5` sube los errores del simulador. El script las pasa solo a un contenedor de un solo uso: `docker compose run --rm -e APP_ENV=staging -e PIPELINE_FORCE_FAILURE=true pipeline`.

## Tests

```bash
pytest                                   # unitarios (los de integración se saltean)
pytest --cov=src --cov-report=term-missing
TEST_DATABASE_URL=postgresql+psycopg://pipeline:<pass>@localhost:5432/agro_dev pytest -m db   # integración
```

- `tests/test_rules.py`: al menos un test por regla DQ01–DQ12, con los bordes de cada rango.
- `tests/test_pipeline_units.py`: simulador (detección ≥ 95%), lake append-only, Gold recalculado, DQ Score, upsert.
- `tests/test_dashboard.py`: los dashboards provisionados son válidos y leen solo `gold`.
- `tests/test_entornos_trazas.py`: configuración de dev / staging / prod y trazas del ETL paso a paso.
- `tests/test_ingestion_governance.py`: conector Open-Meteo (con la API simulada), chequeo de `rules.yaml` y catalogación.
- `tests/test_monitoreo_corridas.py`: migración de las columnas de monitoreo, corrida exitosa y fallida registradas, y `last_measured_at`.
- `tests/test_integration_db.py`: corrida completa contra PostgreSQL, idempotencia del reproceso, Gold sin inválidos (rangos, campos existentes, claves únicas, mismos conteos que Silver), lluvia duplicada que no se suma y lote con solo rechazados.

Resultado actual: **103 passed** con PostgreSQL, cobertura de `src/validation` 92 %. (En la POC eran 93: [`docs/poc/06b_pytest_y_cobertura.txt`](docs/poc/06b_pytest_y_cobertura.txt).)

## CI/CD

Cada push a `main` y cada pull request ejecutan [`.github/workflows/ci.yml`](.github/workflows/ci.yml):

1. Instalación de dependencias
2. Lint (`ruff check`)
3. Validación de `config/rules.yaml` y de las notebooks
4. Tests con PostgreSQL de servicio, más cobertura mínima de 80% en `src/validation`
5. Build de la imagen Docker

Además, cada push a `dev`, `staging` o `main` ejecuta [`.github/workflows/deploy.yml`](.github/workflows/deploy.yml), que publica la imagen del entorno en GHCR (`:dev`, `:staging`, `:prod`); ver [Entornos](#entornos-dev-staging-y-prod).

**Pendiente (configuración en GitHub):** activar *branch protection* en `main` (Settings → Branches), con PR obligatorio, una aprobación y los checks `lint` y `test` en verde. Sin eso no se cumple la meta "100% de los cambios pasan por CI".

## Catálogo y diccionario de datos

Cada dataset (Bronze, Silver, Quarantine y las tablas de Gold) está catalogado siguiendo la skill `data-governance`:

- [`catalog/`](catalog/): esquema técnico y descripciones en YAML.
- [`docs/data_dictionary/`](docs/data_dictionary/): diccionario legible en Markdown.

Para regenerarlos después de cambiar un dataset: `python -m src.governance.catalog`. Las descripciones existentes se conservan.

## Convenciones de trabajo

- Ramas por funcionalidad (`feature/nombre`) y pull request con revisión cruzada antes de integrar a `main`.
- Commits descriptivos que referencien el requerimiento (`RF03: …`) cuando corresponda.
- Una tarjeta del Kanban pasa a *Completado* solo con el PR aprobado.
- Tablero Kanban (ClickUp): <!-- TODO: link al tablero --> · capturas semanales en [`docs/kanban/`](docs/kanban/).
- Decisiones técnicas: [`docs/decisiones.md`](docs/decisiones.md).

## Equipo

| Integrante | Rol |
|---|---|
| Kiara Pisera | Project Manager |
| Sebastian Martinez Benega | Data Engineer |
| Joaquin Maver | QA / Data Quality |
| Matias Posse Presa | DevOps / CI-CD |

**Materia:** Ingeniería de Software – UADE · **Docente:** <!-- TODO --> · **Entrega final:** 10 de noviembre de 2026

## Documentación

- Documento de proyecto v7: [PDF](docs/TPO_Pipeline_DataOps_Documento_Final_v7.pdf) · [DOCX](docs/TPO_Pipeline_DataOps_Documento_Final_v7.docx)
- Cambios sugeridos para la v8: [`docs/cambios_documento_v7.md`](docs/cambios_documento_v7.md)
- Comparación con la entrega final y pasos de la adaptación: [`docs/revision/`](docs/revision/)
- Decisiones técnicas (D1–D27): [`docs/decisiones.md`](docs/decisiones.md)
- Diagramas para el documento (arquitectura, Medallion y base de datos, en Mermaid): [`docs/diagramas.md`](docs/diagramas.md)
- Evidencia de alertas y RNF medidos: [`docs/evidencia_alertas/`](docs/evidencia_alertas/)
- Diagrama de arquitectura: [`docs/arquitectura.excalidraw`](docs/arquitectura.excalidraw)
- Modelo de datos: [`docs/modelo_datos.md`](docs/modelo_datos.md) · [imagen](<docs/Diagrama de base de datos.png>)
- Evidencia de la POC y sección 11: [`docs/poc/`](docs/poc/)
- Simulador interactivo del pipeline (para clase): [`docs/simulador_pipeline.html`](docs/simulador_pipeline.html) · guía: [`docs/simulador_pipeline.md`](docs/simulador_pipeline.md) · skill para actualizarlo: [`.agents/skills/simulador-pipeline`](.agents/skills/simulador-pipeline/SKILL.md)
- Presentación final: <!-- TODO: link -->
- Demo / video: <!-- TODO: link -->

## Licencia

Proyecto académico, de uso exclusivamente educativo.
