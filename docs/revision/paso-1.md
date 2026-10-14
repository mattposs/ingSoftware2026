# Revisión del paso 1: cliente y campos

## 1. Qué pediste vs. qué hiciste

| Ítem de la especificación | Qué hice |
|---|---|
| Cliente ficticio Grupo Agro del Litoral S.A. | Cambiado en `config/fields.yaml`, `README.md` (autoría y contexto) y la descripción del dashboard `calidad-datos`. |
| Reemplazar `config/fields.yaml` por 8 campos con field_id, localidad, provincia, latitud, longitud, hectáreas y sensores | Hecho: `LIT-01` a `LIT-08` con los valores exactos de la especificación. Comprobado por script: 8 campos, 20.000 ha, 200 sensores, 200 × 96 = 19.200. |
| Corregir tests | `C01`–`C06` y `C99` reemplazados por `LIT-01`–`LIT-08` y `LIT-99` en 5 archivos de tests. El conjunto de campos válidos de `conftest.py` y `test_entornos_trazas.py` es ahora `LIT-01` a `LIT-08`. El test de volumen diario pasa de `6 * 96` a `8 * 96` y el de idempotencia de campos de `== 6` a `== 8` (`test_integration_db.py`). |
| Corregir simulador | Docstring actualizado y `C99` (campo inexistente inyectado para DQ04) cambiado a `LIT-99`. **No** se rediseñó a "por sensor" (ver sección 5). |
| Corregir notebooks | Revisados con grep: no tenían referencias a campos viejos ni al cliente. Sin cambios. |
| Corregir dashboards de Grafana | `calidad-datos.json`: consultas `f.nombre` a `f.localidad`; los 2 gráficos con colores por campo pasan de 6 a 8 overrides (`LIT-01.*` a `LIT-08.*`); descripción con el cliente nuevo. `etl-paso-a-paso.json` y `flujo-etl.json`: `f.nombre` a `f.localidad` y "6 campos" a "8 campos". |
| Corregir `catalog/` y `docs/data_dictionary` | Reemplazo de texto (ids, rango `LIT-01 a LIT-08`, descripción del simulador) y entrada `gold.fields` con `localidad` y `sensores`. Se regeneran por completo en el paso 5. |
| Corregir README | Cliente, contexto (8 campos, 20.000 ha, 200 sensores, 19.200 registros/día), diagrama, regla DQ04, estructura del repo y descripción del dashboard. |
| Corregir `.env.example` | Revisado: no tenía referencias a campos ni cliente. Sin cambios. |
| Si adaptar el simulador "por sensor" implica rediseño, no hacerlo y proponer el diseño | No lo hice. Propuesta en la sección 5. |
| Registrar decisiones nuevas en `docs/decisiones.md` | Agregada D20. |

Cambios que la especificación no pedía de forma explícita pero eran necesarios: `gold.fields` pasa de la columna `nombre` a `localidad` y suma `sensores` (los campos nuevos vienen con localidad y sensores, no con nombre). Está en `sql/schema/01_schema.sql` con una migración idempotente para bases existentes.

## 2. Archivos cambiados y hash del commit

Un commit no puede contener su propio hash. Este archivo viaja dentro del commit del paso 1, así que el hash se informa en el chat y se puede ver con:

```
git log --oneline -3
```

Commit padre (estado anterior al paso 1): `3b740e1`.

Archivos del paso (el listado exacto está en `git show --stat HEAD`):

- `config/fields.yaml`
- `sql/schema/01_schema.sql`
- `src/governance/catalog.py`
- `src/ingestion/iot_simulator.py`
- `tests/conftest.py`, `tests/test_entornos_trazas.py`, `tests/test_ingestion_governance.py`, `tests/test_integration_db.py`, `tests/test_pipeline_units.py`, `tests/test_rules.py`
- `grafana/dashboards/calidad-datos.json`, `etl-paso-a-paso.json`, `flujo-etl.json`
- `catalog/**/*.yaml` (8 archivos) y `docs/data_dictionary/**/*.md` (8 archivos)
- `README.md`, `docs/arquitectura.excalidraw`, `docs/decisiones.md`
- `docs/revision/paso-1.md` (este archivo)

## 3. Comandos que corrí y su salida real

La primera corrida de `ruff` encontró un error que corregí antes de volver a correrlo.

`ruff check .` (primera corrida, falló):

```
E501 Line too long (148 > 135)
   --> src\governance\catalog.py:114:136
Found 1 error.
```

`ruff check .` (después de partir la línea):

```
All checks passed!
```

`python -m src.validation.check_rules`:

```
[RULES] OK: 12 reglas y 8 campos válidos.
```

`python -m pytest -q -rs`:

```
........................ssss............................................ [ 80%]
..................                                                       [100%]
=========================== short test summary info ===========================
SKIPPED [1] tests\test_integration_db.py:32: TEST_DATABASE_URL no definida (tests de integración con PostgreSQL)
SKIPPED [1] tests\test_integration_db.py:40: TEST_DATABASE_URL no definida (tests de integración con PostgreSQL)
SKIPPED [1] tests\test_integration_db.py:49: TEST_DATABASE_URL no definida (tests de integración con PostgreSQL)
SKIPPED [1] tests\test_integration_db.py:90: TEST_DATABASE_URL no definida (tests de integración con PostgreSQL)
86 passed, 4 skipped in 6.69s
```

Validación de formato de los archivos tocados (JSON de Grafana y YAML de `catalog/`): ambos cargan sin error.

Con Docker Desktop encendido corrí además lo siguiente. Todo contra bases descartables (`agro_test` y `agro_migracion`, ya borradas), nunca contra `agro_dev`, `agro_staging` ni `agro_prod`.

Tests de integración con PostgreSQL (`TEST_DATABASE_URL` apuntando a `agro_test`):

```
tests/test_integration_db.py::test_watermark_ida_y_vuelta PASSED         [ 25%]
tests/test_integration_db.py::test_upsert_es_idempotente PASSED          [ 50%]
tests/test_integration_db.py::test_corrida_completa_con_simulador PASSED [ 75%]
tests/test_integration_db.py::test_gold_no_tiene_registros_invalidos PASSED [100%]
============================== 4 passed in 6.96s ==============================
```

Estos tests encontraron un error mío: `test_upsert_es_idempotente` tenía `== 6` fijo (cantidad de campos viejos) y lo cambié a `== 8`. No lo vio la búsqueda de `C01`–`C06` porque no menciona ningún id.

Migración de `gold.fields` (esquema anterior del commit `3b740e1` con una fila `C01`, luego el esquema nuevo aplicado dos veces):

```
  Column   |     Type     | Nullable
-----------+--------------+----------
 field_id  | text         | not null
 localidad | text         | not null
 provincia | text         | not null
 latitude  | numeric(8,5) | not null
 longitude | numeric(8,5) | not null
 hectareas | integer      |
 sensores  | integer      |

 C01      | La Aurora | Buenos Aires | -34.05000 | -60.55000 |      3200 |
```

La fila vieja se conservó, `nombre` pasó a `localidad` y `sensores` quedó en `NULL`. La segunda aplicación no falló (idempotente).

Migración de las tres bases del stack (`docker compose exec postgres bash /docker-entrypoint-initdb.d/00_entornos.sh` y `99_app_users.sh`):

```
[INIT] Base agro_dev lista.
[INIT] Base agro_staging lista.
[INIT] Base agro_prod lista.
[INIT] Permisos aplicados en agro_dev.
[INIT] Permisos aplicados en agro_staging.
[INIT] Permisos aplicados en agro_prod.
```

Columnas de `gold.fields` en las tres bases después de migrar: `field_id,localidad,provincia,latitude,longitude,hectareas,sensores`.

`docker compose up -d --build`: los 5 contenedores levantaron. Los schedulers de DEV, STAGING y PROD arrancaron con la imagen nueva y su primera corrida dijo "Nada nuevo para procesar".

Consultas SQL de los dashboards que usan `gold.fields` (7 en total, con las variables y macros de Grafana reemplazadas a mano), ejecutadas contra `agro_dev`:

```
ok    calidad-datos.json  (6 consultas)
ok    etl-paso-a-paso.json (1 consulta)
consultas probadas: 7 con error: 0
```

## 4. Qué NO pude verificar o dejé pendiente

- **Dashboards en pantalla.** Probé que las 7 consultas con `gold.fields` se ejecutan, pero no abrí Grafana para ver los gráficos ni los 8 colores por campo.
- **Corrida real de un lote con campos nuevos en las bases del stack.** Los schedulers aún no procesaron un lote nuevo (su primera corrida no tenía datos nuevos). Los campos `LIT-01` a `LIT-08` se cargan en `gold.fields` recién cuando haya un lote (cada 15 minutos). La sincronización de campos sí está probada con `test_upsert_es_idempotente` en `agro_test`.
- **Datos viejos en las bases del stack.** `agro_dev`, `agro_staging` y `agro_prod` siguen teniendo las filas `C01`–`C06` en `gold.fields` y `gold.daily_field_metrics` (la sincronización hace upsert, no borra) y los Parquet viejos en `storage/`. No los borré porque falta tu decisión.
- **Cobertura.** No corrí `coverage report` en este paso (corresponde al paso 6).
- **Datos de ejemplo del catálogo.** Los `sample_value` de latitud/longitud en `catalog/` y `docs/data_dictionary` que no son de `gold.fields` siguen con valores de los campos viejos. Se regeneran en el paso 5.
- **Lake local (`storage/`).** Los Parquet existentes tienen `C01`–`C06`; no los toqué (están ignorados por Git).
- **`README.md`** sigue diciendo "alrededor del 8%" de errores y "DQ Score = (VALID + WARNING)". Eso corresponde a los pasos 2, 3 y 5.
- **`docs/cambios_documento_v7.md`** y el documento v7 (`.docx` y `.pdf`) describen al cliente anterior (6 campos, 576 registros/día). No los modifiqué: son el documento del proyecto y su lista de correcciones. Decime si querés que los actualice.

## 5. Desvíos respecto de la especificación y por qué

1. **Simulador por campo, no por sensor.** La especificación dice 200 sensores y 19.200 registros/día. El simulador genera una lectura por campo cada 15 min: 8 × 96 = **768 registros/día**. No lo rediseñé porque pediste proponer el diseño y esperar tu OK.

   Propuesta de diseño:
   - Agregar una columna `sensor_id` (por ejemplo `LIT-01-S01`) a Bronze y Silver, y a Quarantine por herencia.
   - El simulador recorre los sensores de cada campo (la cantidad sale de `sensores` en `fields.yaml`) y genera una lectura por sensor cada 15 min, con una pequeña variación respecto del valor base del campo.
   - Las claves de DQ05 (duplicados), DQ11 (huecos) y DQ12 (saltos) pasan a incluir `sensor_id`.
   - Gold sigue agregando por (fecha, campo, fuente).
   - Impacto: cambia el esquema de Bronze, el motor de reglas, Gold, el catálogo y los tests; el volumen sube de 768 a 19.200 registros por día. Open-Meteo no tiene sensores, así que `sensor_id` quedaría nulo para esa fuente.
   - Pregunta abierta: ¿DQ04 debe validar también que el `sensor_id` pertenezca al campo?

   Hasta que lo apruebes, el documento y el README dicen 200 sensores / 19.200 registros por día, pero el código genera 768.

2. **Columna `nombre` reemplazada por `localidad`** en `gold.fields` (la especificación no dice qué hacer con `nombre`, solo da localidad). Decisión mía, registrada en D20. Si preferís conservar `nombre`, hay que definir un nombre para cada campo.

3. **Colores de LIT-07 y LIT-08 en Grafana** (`#e08a3c` y `#7a5fc7`): los elegí yo, porque la especificación no los define.
