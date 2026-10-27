# Evidencia de la prueba de concepto (POC)

Todos los números de este documento salen de **una corrida real** del pipeline. No hay ningún dato inventado.

- **Cuándo y dónde:** 20/10/2026 23:07 UTC, en Docker Compose, con la configuración de STAGING (ambas fuentes, 8 campos, 14 % de errores inyectados).
- **Base y lake:** se usó una base y un lake nuevos y vacíos (`agro_poc` y `storage/poc`), para que no se mezclaran con datos de pruebas anteriores.
- **Salida completa:** está en los archivos `01` a `07` de esta carpeta. Las consultas SQL figuran junto a cada resultado.

| Archivo | Contenido |
|---|---|
| [01_docker_compose_up.txt](01_docker_compose_up.txt), [02_docker_compose_ps.txt](02_docker_compose_ps.txt) | Levantar el stack y su estado |
| [03_corrida_pipeline.txt](03_corrida_pipeline.txt) | Comando y salida de la corrida |
| [04_evidencia_corrida.md](04_evidencia_corrida.md) | Datos ingestados, métricas, hallazgos, DQ Score por campo y día, ejemplos por capa |
| [05_casos_punta_a_punta.md](05_casos_punta_a_punta.md) | Casos DQ10 (LIT-05) y DQ05 (LIT-02), de Bronze a Gold |
| [06a_test_en_rojo_local.txt](06a_test_en_rojo_local.txt), [06b_pytest_y_cobertura.txt](06b_pytest_y_cobertura.txt) | Test que falla y suite completa en verde con cobertura |
| [07_grafana_consultas.md](07_grafana_consultas.md), [07b_permisos_usuario_dashboard.txt](07b_permisos_usuario_dashboard.txt) | Consultas de los 37 paneles y prueba de permisos del usuario del dashboard |
| [08_backfill_monitoreo.txt](08_backfill_monitoreo.txt) | Columnas de monitoreo completadas en las bases de la POC (`agro_poc`, `agro_poc_grafana`) desde datos ya registrados |
| [../evidencia_alertas/](../evidencia_alertas/) | Monitoreo y alertas: escenarios provocados, capturas y RNF medidos (sección 8, ensayo del 26/10/2026) |

## 1. Ejecución

Los comandos son para PowerShell y se ejecutan desde la raíz del repositorio.

```powershell
# 1. Levantar todo: PostgreSQL, 3 schedulers (dev, staging, prod), Grafana y Mailpit (correo de las alertas)
docker compose up -d --build
docker compose ps

# 2. (Opcional, lo que se hizo para la evidencia) base y lake limpios solo para la POC
docker compose exec postgres sh -c 'psql -U "$POSTGRES_USER" -d postgres -c "CREATE DATABASE agro_poc"'
Get-Content sql/schema/01_schema.sql | docker compose exec -T postgres sh -c 'psql -U "$POSTGRES_USER" -d agro_poc'

# 3. Corrida completa sobre los 8 campos (configuración de STAGING: Open-Meteo + simulador IoT)
docker compose run --rm -e APP_ENV=staging -e STORAGE_PATH=/app/storage/poc pipeline sh -c 'DATABASE_URL="postgresql+psycopg://$POSTGRES_USER:$POSTGRES_PASSWORD@postgres:5432/agro_poc" python -m src.main'
```

Para correrlo sobre la base normal de STAGING, sin el paso 2, alcanza con `docker compose run --rm -e APP_ENV=staging pipeline`. En ese caso solo procesa la ventana nueva desde la última corrida del scheduler.

Salida real ([03_corrida_pipeline.txt](03_corrida_pipeline.txt)):

```
[PIPELINE] Entorno: STAGING · base agro_poc · lake /app/storage/poc
[BRONZE] 576 registros -> /app/storage/poc/bronze/agro/open_meteo/year=2026/month=10/batch_ece83881-91dc-4356-b6cf-eb7ddfa7f759.parquet
[STATE] Watermark agro.open_meteo = 2026-10-15T23:00:00+00:00
[BRONZE] 767 registros -> /app/storage/poc/bronze/agro/iot_simulator/year=2026/month=10/batch_ece83881-91dc-4356-b6cf-eb7ddfa7f759.parquet
[STATE] Watermark agro.iot_simulator = 2026-10-20T23:00:00+00:00
[SILVER] 1246 registros -> /app/storage/poc/silver/agro/measurements/year=2026/month=10/clean_ece83881-91dc-4356-b6cf-eb7ddfa7f759.parquet
[QUARANTINE] 97 registros -> /app/storage/poc/quarantine/agro/measurements/year=2026/month=10/rejected_ece83881-91dc-4356-b6cf-eb7ddfa7f759.parquet
[DQ] total=1343 valid=1193 warning=53 invalid=97 score=88.83% utilizable=92.78% errores=326
[DB] Upsert de 8 filas en gold.fields.
[DB] Upsert de 48 filas en gold.daily_field_metrics.
[PIPELINE] Lote ece83881-91dc-4356-b6cf-eb7ddfa7f759 procesado.
[PIPELINE] Duración: 9.9s (objetivo RNF08: < 300s)
```

## 2. Datos ingestados

| Fuente | Registros en Bronze | Ventana pedida (UTC) | Datos recibidos (UTC) | Campos |
|---|---|---|---|---|
| Open-Meteo | 576 | (2026-10-12 23:00, 2026-10-15 23:00] | 2026-10-13 00:00 a 2026-10-15 23:00 (horario) | LIT-01 a LIT-08 |
| Simulador IoT | 767 | (2026-10-19 23:00, 2026-10-20 23:00] | 2026-10-19 23:15 a 2026-10-20 23:00 | LIT-01 a LIT-08 |

- **Intervalo del simulador:** 15 minutos, medido sobre los datos (es el intervalo más frecuente entre lecturas consecutivas de un mismo campo).
- **Errores inyectados:** 108 de 767 registros = **14,08 %** (configurado: `error_rate: 0.14`).
- **Tipos de error inyectados:**

| Tipo | Registros |
|---|---|
| `humidity_out_of_range` | 15 |
| `bad_timestamp` | 13 |
| `temperature_extreme` | 10 |
| `soil_out_of_range` | 10 |
| `wrong_unit` | 9 |
| `null_field` | 9 |
| `future_timestamp` | 8 |
| `negative_precipitation` | 7 |
| `null_timestamp` | 7 |
| `spike` | 6 |
| `unknown_field` | 5 |
| `gap` | 5 |
| `duplicate` | 4 |

- **Datos fuera de la ventana:** el simulador también entrega registros que no corresponden a la ventana pedida, como el campo `LIT-99` (inexistente) o timestamps futuros. Son parte de los errores inyectados.

## 3. Métricas de la corrida

`gold.dq_run_metrics`:

| total | valid | warning | invalid | dq_score (VALID / total) | % utilizable ((VALID + WARNING) / total) |
|---|---|---|---|---|---|
| 1343 | 1193 | 53 | 97 | **88,83 %** | **92,78 %** |

Hallazgos por regla (`gold.dq_errors`). Un registro puede tener más de un hallazgo; DQ11 cuenta uno por variable con hueco.

| Regla | Tipo | Severidad | Acción | Hallazgos |
|---|---|---|---|---|
| DQ01 | Completitud | Crítica | REJECT | 7 |
| DQ02 | Completitud | Crítica | REJECT | 9 |
| DQ03 | Consistencia | Crítica | REJECT | 21 |
| DQ04 | Integridad | Crítica | REJECT | 5 |
| DQ05 | Unicidad | Crítica | REJECT | 6 |
| DQ06 | Consistencia | Crítica | REJECT | 9 |
| DQ07 | Validez | Alta | REJECT | 15 |
| DQ08 | Validez | Alta | REJECT | 7 |
| DQ09 | Validez | Alta | REJECT | 10 |
| DQ10 | Validez | Alta | REJECT | 10 |
| DQ11 | Completitud | Media | WARNING | 215 |
| DQ12 | Anomalía | Media | WARNING | 12 |

Por severidad: Crítica 57 (REJECT) · Alta 42 (REJECT) · Media 227 (WARNING). Total: 326 hallazgos.

DQ Score estricto por campo y día (`gold.daily_field_metrics.porcentaje_calidad`; el día es la fecha en hora local):

| Fuente | Campo | 12/10 | 13/10 | 14/10 | 15/10 | 19/10 | 20/10 |
|---|---|---|---|---|---|---|---|
| simulador IoT | LIT-01 | | | | | 86,67 | 82,19 |
| simulador IoT | LIT-02 | | | | | 76,92 | 76,06 |
| simulador IoT | LIT-03 | | | | | 93,33 | 82,19 |
| simulador IoT | LIT-04 | | | | | 80,00 | 88,46 |
| simulador IoT | LIT-05 | | | | | 86,67 | 80,00 |
| simulador IoT | LIT-06 | | | | | 85,71 | 91,46 |
| simulador IoT | LIT-07 | | | | | 69,23 | 91,14 |
| simulador IoT | LIT-08 | | | | | 86,67 | 89,87 |
| Open-Meteo | LIT-01 a LIT-08 | 100 | 100 | 100 | 100 | | |

**Cómo leer las fechas:**
- La "fecha" de Gold es el día en hora de Argentina. Por eso aparecen el 12/10 para Open-Meteo y el 19/10 para el simulador: son las primeras horas en UTC, que localmente todavía son el día anterior.
- El "19/10" del simulador tiene solo 12 a 14 mediciones por campo, porque corresponde a las primeras 3 horas de la ventana.
- Open-Meteo da 100 % en todos los días porque son datos reales sin errores inyectados.

## 4. Ejemplos por capa (registros reales)

**Bronze** (simulador, tal como llegó):

| timestamp | field_id | temperature | humidity | soil_moisture | precipitation | wind_speed | _batch_id | _ingested_at | _source_system |
|---|---|---|---|---|---|---|---|---|---|
| 2026-10-19T23:15:00Z (texto) | LIT-01 | 15.99 °C | 69.1 % | 0.281 m³/m³ | 0.0 mm | 9.8 km/h | ece83881-… | 2026-10-20 23:07:06.30 UTC | iot_simulator |

**Silver:**

| timestamp (UTC, tipado) | source | field_id | temperature | humidity | soil_moisture | precipitation | dq_status | _dq_warnings |
|---|---|---|---|---|---|---|---|---|
| 2026-10-13 00:00 | open_meteo | LIT-01 | 13.0 | 85.0 | 0.469 | 0.0 | **VALID** | — |
| 2026-10-20 04:15 | iot_simulator | LIT-01 | 9.56 | 85.3 | 0.281 | 0.0 | **WARNING** | DQ11 |

**Quarantine:**

| timestamp | field_id | precipitation | _sim_injected_error | _rejection_reasons | _rejected_at |
|---|---|---|---|---|---|
| 2026-10-20T00:15:00Z | LIT-01 | **-3.0** | negative_precipitation | **DQ08** | 2026-10-20 23:07:06.76 UTC |

**Gold** (`gold.daily_field_metrics`):

| fecha | field_id | fuente | temperatura_promedio | precipitacion_total | humedad_suelo_promedio | humedad_ambiental_promedio | cantidad_mediciones | porcentaje_calidad |
|---|---|---|---|---|---|---|---|---|
| 2026-10-20 | LIT-01 | iot_simulator | 15.219 | 2.9 | 0.280 | 69.338 | 66 | 82.19 |
| 2026-10-20 | LIT-02 | iot_simulator | 16.631 | 0.4 | 0.292 | 68.629 | 65 | 76.06 |
| 2026-10-20 | LIT-03 | iot_simulator | 16.923 | 0.0 | 0.301 | 69.684 | 68 | 82.19 |

Las filas completas, con todas las columnas, están en [04_evidencia_corrida.md](04_evidencia_corrida.md).

## 5. Casos punta a punta

El detalle completo, con cada registro y cada consulta, está en [05_casos_punta_a_punta.md](05_casos_punta_a_punta.md).

**Caso A: DQ10 en LIT-05 (dato real de la corrida, sin provocarlo)**
- **Bronze:** 2026-10-20T23:00:00Z, LIT-05, `soil_moisture = 1.35` m³/m³. Es físicamente imposible porque el máximo es 1. Fue inyectado por el simulador como `soil_out_of_range`.
- **Regla:** DQ10 · Validez · Alta · REJECT · "fuera del rango físico [0, 1]".
- **Quarantine:** la misma fila, con `_rejection_reasons = DQ10`.
- **No llegó a Gold:**
  - Hay 0 registros en Silver con esa identidad.
  - La fila de Gold del 2026-10-20 de LIT-05 tiene `cantidad_mediciones = 68`, que es exactamente la cantidad de registros de Silver de ese día.
  - `humedad_suelo_promedio = 0.316`, y la máxima humedad que alimenta esa fila es 0.321. El 1,35 no está.
- **Aclaración:** el simulador inyecta este error con un valor **mayor a 1**, no negativo. Un valor negativo también lo rechaza DQ10 (rango [0, 1]), pero en esta corrida no apareció.

```sql
SELECT rule_id, severidad, action, variable, detalle FROM gold.dq_errors
WHERE field_id = 'LIT-05' AND measured_at = '2026-10-20 23:00:00+00';
SELECT fecha, cantidad_mediciones, humedad_suelo_promedio, porcentaje_calidad FROM gold.daily_field_metrics
WHERE field_id = 'LIT-05' AND fuente = 'iot_simulator' AND fecha = '2026-10-20';
```

**Caso B: DQ05, precipitación duplicada en LIT-02 (inyección controlada)**
- **Cómo se provocó:** en la corrida no hubo duplicados en LIT-02. Se volvió a enviar, en un lote aparte (`poc-dq05-ba8db9eb`), la lectura **real** de LIT-02 con lluvia: 2026-10-20T00:00:00Z, **2,6 mm**. Pasó por el código real del pipeline.
- **Regla:** DQ05 · Crítica · REJECT · "registro ya procesado en un lote anterior".
- **Quarantine:** `_rejection_reasons = DQ05`, `_sim_injected_error = poc_duplicado_controlado`.
- **No se duplicó en Gold:**
  - Gold de LIT-02 del 19/10 (las 00:00 UTC son las 21:00 del 19 en hora local) tenía `precipitacion_total = 2.6` mm antes y sigue en **2.6** mm después, no 5,2.
  - En Silver hay 1 sola copia de la lectura.
  - El lote del duplicado escribió 0 filas en Gold.

```sql
SELECT rule_id, detalle FROM gold.dq_errors WHERE _batch_id = 'poc-dq05-ba8db9eb';
SELECT fecha, precipitacion_total, cantidad_mediciones FROM gold.daily_field_metrics
WHERE field_id = 'LIT-02' AND fuente = 'iot_simulator' AND fecha = '2026-10-19';
SELECT count(*) FROM gold.daily_field_metrics WHERE _batch_id = 'poc-dq05-ba8db9eb';   -- 0
```

**Hallazgo de la POC: un bug real, corregido**
- **Qué pasó:** el primer intento del caso B falló. Un lote que trae **solo** registros rechazados dejaba vacía la columna `fecha_negocio` de las trazas, y PostgreSQL la rechazaba (`column "fecha_negocio" is of type date but expression is of type character varying`). La corrida se cortaba antes de Gold. En corridas normales nunca pasa, porque siempre hay algún registro válido.
- **Arreglo:** se indica el tipo de la columna al guardar, en `src/metrics/trace.py`.
- **Test de regresión:** `test_lote_solo_con_rechazados_no_rompe_las_trazas`. Se comprobó que falla sin el arreglo y pasa con él.
- **Recuperación:** el lote fallido **no se perdió**. Bronze ya estaba guardado y se recuperó con `pipeline.reprocess(batch_id)` desde Bronze, sin volver a enviar el dato. Es un ejemplo concreto de la reproducibilidad (RNF03).

## 6. Evidencia de CI/CD: un test en rojo y después en verde

- **Workflow:** `CI` (`.github/workflows/ci.yml`). Corre en cada **pull request** y en cada push a `main`.
- **Job:** `test`, paso "Tests (Pytest) + cobertura mínima del 80% en validación". Usa un PostgreSQL 16 real como servicio del workflow.
- **Test que se usa:** `tests/test_integration_db.py::test_gold_no_tiene_registros_invalidos`.

**Pasos.** El cambio de demostración ya se probó localmente y hace fallar ese test ([06a](06a_test_en_rojo_local.txt)).

```powershell
git checkout dev
git pull
git checkout -b feature/demo-ci-fallo
# Editar config/rules.yaml, regla DQ08:   min: 0   ->   min: -100   (acepta lluvia negativa)
git commit -am "demo CI: aflojar DQ08 para que pase lluvia negativa a Gold"
git push -u origin feature/demo-ci-fallo
# En GitHub: abrir un Pull Request de feature/demo-ci-fallo hacia dev  -> CI en ROJO
git revert --no-edit HEAD
git push                                                              # -> CI en VERDE en el mismo PR
# Cerrar el PR sin mergear y borrar la rama.
```

Resultado local con el cambio (rojo):

```
FAILED tests/test_integration_db.py::test_gold_no_tiene_registros_invalidos
    tests/test_integration_db.py:109  assert (df["precipitacion_total"] >= 0).all()   -> Gold con lluvia negativa
FAILED tests/test_pipeline_units.py::test_reglas_detectan_al_menos_95_por_ciento_de_errores_inyectados[2]
FAILED tests/test_pipeline_units.py::test_reglas_detectan_al_menos_95_por_ciento_de_errores_inyectados[3]
FAILED tests/test_rules.py::test_dq08_precipitacion_no_negativa[-0.1-1]
FAILED tests/test_rules.py::test_multiples_motivos_de_rechazo
5 failed, 88 passed in 23.75s
```

Resultado sin el cambio (verde), [06b](06b_pytest_y_cobertura.txt):
- `ruff`: All checks passed.
- `check_rules`: 12 reglas y 8 campos válidos.
- **pytest: 93 passed**.
- Cobertura total: 87 %.
- **Cobertura de `src/validation`: 92 %** (mínimo exigido 80 %): `engine.py` 99 %, `check_rules.py` 72 %.

**Variante:** si se prefiere tocar código en vez de configuración, se puede comentar en `src/validation/engine.py` la línea `status[df.index.isin(reject_codes.index)] = STATUS_INVALID`. El test también falla, pero lo frena la clave foránea de PostgreSQL (el campo inexistente `LIT-99` no puede entrar a Gold), no la aserción. Es otra capa de defensa, aunque menos clara para mostrar.

**No verificado:** las corridas en GitHub Actions no las ejecuté yo, porque requieren el push y el PR. Lo de arriba es la verificación local.

## 7. Dashboard

- **URL:** http://localhost:3000. Se ve sin iniciar sesión, como lector; para editar, `admin` / `GRAFANA_ADMIN_PASSWORD`.
- **Usuario de base de datos de la fuente de datos:** `dashboard`, de solo lectura (`grafana/provisioning/datasources/agro.yml`, `sql/99_app_users.sh`). Hay una fuente por entorno: `Agro · PROD`, `Agro · STAGING` y `Agro · DEV`.
- **Solo lee `gold`:** las 37 consultas de los 3 dashboards usan únicamente tablas `gold.*` ([07_grafana_consultas.md](07_grafana_consultas.md)). Además se probó con el usuario `dashboard` ([07b](07b_permisos_usuario_dashboard.txt)):
  - `SELECT` en `gold.daily_field_metrics`: funciona (217 filas en STAGING).
  - `SELECT` en `etl.watermarks`: `permission denied for schema etl`.
  - `INSERT` en `gold.fields`: `permission denied for table fields`.

Consultas de los paneles pedidos (dashboard «Calidad de datos agroclimáticos»):

```sql
-- DQ Score estricto (última corrida)
SELECT dq_score AS "DQ Score estricto" FROM gold.dq_run_metrics WHERE status = 'ok' ORDER BY run_start DESC LIMIT 1
-- % utilizable (última corrida)
SELECT pct_utilizable AS "% utilizable" FROM gold.dq_run_metrics WHERE status = 'ok' ORDER BY run_start DESC LIMIT 1
-- DQ Score estricto y % utilizable por corrida
SELECT run_start AS time, dq_score AS "DQ Score estricto (solo VALID)", pct_utilizable AS "% utilizable (VALID + WARNING)"
FROM gold.dq_run_metrics WHERE status = 'ok' AND $__timeFilter(run_start) ORDER BY 1
-- % de calidad estricto por campo y día
SELECT ((m.fecha + time '12:00') AT TIME ZONE 'America/Argentina/Buenos_Aires') AS time, f.field_id || ' · ' || f.localidad AS metric,
       m.porcentaje_calidad AS value
FROM gold.daily_field_metrics m JOIN gold.fields f USING (field_id)
WHERE m.fuente = '$fuente' AND m.field_id IN ($campo) AND $__timeFilter(((m.fecha + time '12:00') AT TIME ZONE 'America/Argentina/Buenos_Aires')) ORDER BY 1, 2
-- Hallazgos por regla
WITH reglas(rule_id) AS (SELECT 'DQ' || lpad(g::text, 2, '0') FROM generate_series(1, 12) g)
SELECT r.rule_id AS "Regla", NULLIF(count(e.*) FILTER (WHERE e.action = 'REJECT'), 0) AS "Rechazos",
       NULLIF(count(e.*) FILTER (WHERE e.action = 'WARNING'), 0) AS "Warnings"
FROM reglas r LEFT JOIN gold.dq_errors e ON e.rule_id = r.rule_id
 AND e._batch_id IN (SELECT _batch_id FROM gold.dq_run_metrics WHERE $__timeFilter(run_start))
GROUP BY 1 ORDER BY 1
```

**Importante para las capturas:**
- Grafana lee las bases `agro_dev`, `agro_staging` y `agro_prod`, no `agro_poc`. Por eso sus números no van a coincidir exactamente con la tabla de este documento.
- Esas bases todavía tienen datos viejos de los campos `C01` a `C06` mezclados con los nuevos.
- **Opciones para tener capturas limpias:**
  - **(a)** Autorizar que borre esos datos viejos.
  - **(b)** Agregar una fuente de datos "Agro · POC" que apunte a `agro_poc`.
  - **(c)** Sacar las capturas igual, filtrando por los campos `LIT-*` en el selector «Campo».

## 8. Monitoreo y alertas

Ensayo del **26/10/2026** en STAGING, posterior a la corrida de la POC. Los datos salen de `gold.dq_run_metrics`, de la API de Grafana y de Mailpit. Detalle completo en [`../evidencia_alertas/resumen.md`](../evidencia_alertas/resumen.md).

- **Registro de corridas:** `gold.dq_run_metrics` guarda `run_status` (SUCCESS / FAILED), `started_at`, `finished_at`, `duration_seconds` y `last_measured_at`, también en las corridas que fallan. El pipeline agrega esas columnas al arrancar si la base es anterior.
- **Panel de salud:** el dashboard de calidad tiene la fila «Salud del pipeline», con el estado de la última corrida, la duración, los minutos desde la última corrida, la frescura y las corridas fallidas en 24 h.
- **Alertas** (Grafana Alerting, provisionadas como código, evaluadas cada 1 min, STAGING y PROD):
  - **AL01**, crítica: la última corrida falló, o pasaron más de 30 min sin corridas nuevas.
  - **AL02**, alta: el DQ Score es menor que 80 %, o cayó más de 10 puntos contra el promedio de 24 h.
  - Las notificaciones llegan por correo a Mailpit (http://localhost:8025).

```powershell
python scripts/simulate_alerts.py --escenario A   # corrida fallida  -> AL01
python scripts/simulate_alerts.py --escenario B   # DQ Score bajo    -> AL02
python scripts/verify_rnf.py                      # RNF medidos
```

| Escenario | Falla provocada | Alerta | Falla (UTC) | Disparo (UTC) | Minutos | Correo (UTC) |
|---|---|---|---|---|---|---|
| A | Corrida con `PIPELINE_FORCE_FAILURE=true` | AL01 | 23:45:36 | 23:46:00 | 0,39 | 23:46:12 |
| B | Corrida IoT con `PIPELINE_IOT_ERROR_RATE=0.5`: DQ Score 44,44 % (4 VALID de 9) | AL02 | 23:16:14 | 23:17:00 | 0,76 | 23:17:17 |

RNF11 (alerta en ≤ 30 min): **cumple** en los dos escenarios.

**Dashboard de la POC:** las bases de la POC (`agro_poc` y `agro_poc_grafana`, la de la fuente «Agro · POC») no tienen scheduler, así que no migraron solas. Les apliqué la misma migración y completé las columnas de monitoreo con `scripts/backfill_monitoreo.py` ([08_backfill_monitoreo.txt](08_backfill_monitoreo.txt)), usando solo datos ya registrados:
- `started_at`: el inicio de la primera etapa en `gold.pipeline_layer_metrics`.
- `finished_at`: `run_end`.
- `last_measured_at`: el máximo timestamp de Silver del lote.

Resultado para la corrida de la POC:
- SUCCESS, con duración de 9,67 s (de 23:06:58 a 23:07:07 UTC). La consola informó 9,9 s porque incluye el arranque del proceso.
- Última medición a las 23:00 UTC, es decir, frescura de 7,1 min.
- Captura: [capturas/grafana_05_salud_pipeline.png](capturas/grafana_05_salud_pipeline.png). El «6,0 days» desde la última corrida es real: la POC corrió el 20/10 y esa base no tiene scheduler.

RNF medidos ([`../evidencia_alertas/rnf_medidos.md`](../evidencia_alertas/rnf_medidos.md)):
- **Cumplen:** RNF02, RNF03, RNF04, RNF06, RNF08, RNF09 y RNF10.
- **No cumple RNF07:** el máximo fue 41 corridas en un día contra 96 pedidas, porque el stack no corre las 24 h.
- RNF08 y RNF09 se midieron sobre solo 4 corridas.

**Hallazgo:** cada corrida incremental procesa 8 registros. Con tan pocos, un par de rechazos deja el score debajo de 80 %. Una corrida normal de STAGING dio 50 % y AL02 se disparó sin una falla real. Está anotado como decisión pendiente D26.

## 9. Resumen

| Dato | Valor |
|---|---|
| Lote de la corrida | `ece83881-91dc-4356-b6cf-eb7ddfa7f759` (20/10/2026 23:07 UTC, configuración STAGING) |
| Duración de la corrida | 9,9 s (objetivo < 300 s) |
| Open-Meteo | 576 registros, 2026-10-13 00:00 a 2026-10-15 23:00 UTC, 8 campos |
| Simulador IoT | 767 registros, cada 15 min, 2026-10-19 23:15 a 2026-10-20 23:00 UTC, 14,08 % con error inyectado |
| Total / VALID / WARNING / INVALID | 1343 / 1193 / 53 / 97 |
| DQ Score estricto | 88,83 % |
| % utilizable | 92,78 % |
| Silver / Quarantine / filas de Gold | 1246 / 97 / 48 |
| Hallazgos | 326 (Crítica 57, Alta 42, Media 227) |
| DQ Score diario por campo (simulador) | entre 69,23 % y 93,33 % |
| Caso DQ10 (LIT-05) | humedad de suelo 1,35 → Quarantine; Gold sin cambios (68 mediciones, promedio 0,316) |
| Caso DQ05 (LIT-02) | 2,6 mm duplicados → Quarantine; Gold sigue en 2,6 mm |
| Tests | 93 passed; cobertura de validación 92 % (mínimo 80 %) |
| Test en rojo (local) | 5 failed con DQ08 `min: -100`, incluido `test_gold_no_tiene_registros_invalidos` |
| Bug encontrado por la POC | Lote con solo rechazos rompía las trazas; corregido, con test de regresión |
| Alerta AL01 (corrida fallida) | disparada 0,39 min después de la falla (26/10/2026, STAGING) |
| Alerta AL02 (DQ Score 44,44 %) | disparada 0,76 min después de la corrida (26/10/2026, STAGING) |
| Tests hoy (con el monitoreo) | 103 passed; cobertura de validación 92 % |

### Capturas para sacar a mano

1. `captura_01_docker_ps.png`: terminal con `docker compose ps` (6 contenedores: postgres *healthy*, 3 schedulers, Grafana y Mailpit). El archivo [02_docker_compose_ps.txt](02_docker_compose_ps.txt) es de la corrida del 20/10, antes de Mailpit, y muestra 5.
2. `captura_02_corrida_pipeline.png`: terminal con la salida de la corrida (sección 1).
3. `captura_03_lake_carpetas.png`: Explorador de archivos en `storage/poc/` mostrando las carpetas `bronze`, `silver` y `quarantine` con sus Parquet.
4. `captura_04_bronze.png`, `captura_05_silver.png` y `captura_06_quarantine.png`: los registros de ejemplo. Lo más simple es capturar las tablas de [04_evidencia_corrida.md](04_evidencia_corrida.md) abiertas en VS Code (vista previa de Markdown). Para verlos en los notebooks de `notebooks/`, hay que abrirlos con `STORAGE_PATH=storage/poc` y `APP_ENV=staging`; si no, leen el lake de DEV.
5. `captura_07_gold_sql.png`: consola SQL (`docker compose exec postgres psql …`) con la consulta de `gold.daily_field_metrics` y `gold.dq_run_metrics`.
6. `captura_08_caso_dq10_lit05.png` y `captura_09_caso_dq05_lit02.png`: las consultas SQL de la sección 5 con sus resultados.
7. `captura_10_grafana_calidad.png`: dashboard «Calidad de datos agroclimáticos», fila superior (DQ Score estricto, % utilizable, VALID / WARNING / INVALID).
8. `captura_11_grafana_hallazgos_por_regla.png`: el panel de hallazgos por regla.
9. `captura_12_grafana_calidad_por_campo_dia.png`: el panel «% de calidad estricto por campo y día».
10. `captura_13_grafana_etl_paso_a_paso.png`: dashboard «ETL paso a paso» con un registro rechazado seleccionado.
11. `captura_14_grafana_flujo_etl.png`: dashboard «Flujo del ETL» (Bronze → Silver / Quarantine → Gold).
12. `captura_15_ci_rojo.png`: el PR `feature/demo-ci-fallo` con el check `CI / test` en rojo, y el log con `FAILED … test_gold_no_tiene_registros_invalidos`.
13. `captura_16_ci_verde.png`: el mismo PR después del `git revert`, con todos los checks en verde.
14. `captura_17_cobertura.png`: el log de CI (o la terminal) con la cobertura de `src/validation` (92 %).
15. `captura_18_permisos_dashboard.png`: el resultado de [07b](07b_permisos_usuario_dashboard.txt) (`permission denied` en `etl` y en `INSERT`).
16. **Alertas: ya generadas**, no hay que sacarlas a mano. Están en [`../evidencia_alertas/`](../evidencia_alertas/): `AL01_*.png` y `AL02_*.png` (lista de alertas en Firing, detalle de la regla, panel de salud y correo en Mailpit), con la hora de la captura en pantalla.

### Repositorio

- Repositorio: https://github.com/SebastianMB1/IngSoftwareETL
- Ramas de trabajo: `feature/entornos-etl-paso-a-paso` (POC) y `feature/alertas-pipeline` (monitoreo y alertas)
- Evidencia: `docs/poc/` y `docs/evidencia_alertas/`

### Qué grabar en el video de la demo (unos 5 a 7 minutos)

1. **(30 s)** El problema: el 14 % de datos con errores y las decisiones de riego. Mostrar el diagrama de arquitectura o el simulador `docs/simulador_pipeline.html`.
2. **(1 min)** `docker compose up -d --build` y `docker compose ps`: el sistema completo levanta con un comando.
3. **(1 min)** La corrida del pipeline en la terminal: Bronze → Silver / Quarantine → Gold, con el DQ Score y el % utilizable.
4. **(1 min)** Un registro rechazado: el caso DQ10 de LIT-05, en Bronze, en `gold.dq_errors` y en Quarantine, y la consulta que demuestra que no llegó a Gold.
5. **(1,5 min)** Grafana: DQ Score, hallazgos por regla, calidad por campo y día, y el «ETL paso a paso» siguiendo el mismo registro.
6. **(1 min)** CI/CD: el PR en rojo por el cambio en `rules.yaml` y en verde después del revert.
7. **(1 min)** Alertas: `python scripts/simulate_alerts.py --escenario A`, AL01 en Firing en Grafana y el correo en Mailpit (http://localhost:8025).
8. **(30 s)** Cierre: el bug que encontró la POC y cómo se recuperó el lote desde Bronze sin perder datos.
