# Revisión del paso 6: verificación final

## 1. Qué pediste vs. qué hiciste

| Ítem de la especificación | Resultado |
|---|---|
| `ruff check .` | Pasa (`All checks passed!`). |
| `python -m src.validation.check_rules` | Pasa: 12 reglas y 8 campos válidos. |
| `pytest --cov=src` | 92 pasados, 0 omitidos. Lo corrí con una base PostgreSQL descartable (`TEST_DATABASE_URL`), como hace el CI; sin esa variable, 5 tests de integración se omiten. Cobertura total 87 %. |
| `coverage report --include="src/validation/*" --fail-under=80` | Pasa: 92 % (`engine.py` 99 %, `check_rules.py` 72 %). |
| `docker compose up -d` | Los 5 contenedores están arriba (`postgres` saludable, 3 *schedulers* y Grafana). |
| Una corrida en dev | Hecha con `docker compose run --rm -e APP_ENV=dev pipeline`: lote procesado con los campos nuevos `LIT-01` a `LIT-08` hasta Gold. |

## 2. Archivos cambiados y hash del commit

Este paso solo agrega este informe: `docs/revision/paso-6.md`. No cambié código. El hash se informa en el chat (un commit no puede contener su propio hash); se ve con `git log --oneline -3`. Commit padre: `ac32b5c`.

## 3. Comandos que corrí y su salida real

`ruff check .`:

```
All checks passed!
```

`python -m src.validation.check_rules`:

```
[RULES] OK: 12 reglas y 8 campos válidos.
```

Tests y cobertura (contra una base `agro_test` descartable, ya borrada):

```
$ python -m pytest --cov=src --cov-report=term-missing -q -p no:cacheprovider
........................................................................ [ 78%]
....................                                                     [100%]
=============================== tests coverage ================================
_______________ coverage: platform win32, python 3.13.5-final-0 _______________

Name                                 Stmts   Miss  Cover   Missing
------------------------------------------------------------------
src\__init__.py                          0      0   100%
src\common\__init__.py                   0      0   100%
src\common\db.py                        28      2    93%   51-52
src\common\lake.py                      37      0   100%
src\common\state.py                     12      0   100%
src\config.py                           57      0   100%
src\governance\__init__.py               0      0   100%
src\governance\catalog.py               34     34     0%   10-170
src\governance\catalog_manager.py       34      1    97%   75
src\governance\dict_generator.py        34      0   100%
src\governance\schema_extractor.py      17      4    76%   44-47
src\ingestion\__init__.py                0      0   100%
src\ingestion\iot_simulator.py          83      1    99%   84
src\ingestion\open_meteo.py             40      7    82%   41-47
src\ingestion\schema.py                 13      0   100%
src\main.py                             22     22     0%   10-41
src\metrics\__init__.py                  0      0   100%
src\metrics\quality.py                  28      1    96%   77
src\metrics\trace.py                   112      2    98%   174, 180
src\pipeline.py                         92      6    93%   73, 128-130, 137-138
src\scheduler.py                        22     22     0%   10-36
src\transformation\__init__.py           0      0   100%
src\transformation\gold.py              35      2    94%   25, 45
src\validation\__init__.py               0      0   100%
src\validation\check_rules.py           46     13    72%   27, 36-37, 47, 51, 55, 60-65, 69
src\validation\engine.py               144      2    99%   172, 188
------------------------------------------------------------------
TOTAL                                  890    119    87%
92 passed in 52.10s

[código de salida: 0]

$ python -m coverage report --include=src/validation/* --fail-under=80
Name                            Stmts   Miss  Cover
---------------------------------------------------
src\validation\__init__.py          0      0   100%
src\validation\check_rules.py      46     13    72%
src\validation\engine.py          144      2    99%
---------------------------------------------------
TOTAL                             190     15    92%

[código de salida: 0]
```

`docker compose up -d --build` (no recreó nada: la imagen no cambió desde el paso 3, porque los pasos 4 y 5 no tocaron código) y estado:

```
ingsoftwareetl-1-grafana-1 Up 5 days
ingsoftwareetl-1-postgres-1 Up 5 days (healthy)
ingsoftwareetl-1-scheduler-dev-1 Up 5 days
ingsoftwareetl-1-scheduler-prod-1 Up 5 days
ingsoftwareetl-1-scheduler-staging-1 Up 5 days
```

Corrida en dev. Antes paré `scheduler-dev` para que no tomara la ventana de datos nueva, esperé al siguiente cuarto de hora (15:00 UTC) y corrí a mano; después volví a arrancar el *scheduler*:

```
Container ingsoftwareetl-1-postgres-1  Running
[PIPELINE] Entorno: DEV · base agro_dev · lake /app/storage/dev
[BRONZE] 8 registros -> /app/storage/dev/bronze/agro/iot_simulator/year=2026/month=10/batch_9c617b88-90f5-4d2d-97e6-ddd18aeed7fc.parquet
[STATE] Watermark agro.iot_simulator = 2026-10-19T15:00:00+00:00
[SILVER] 6 registros -> /app/storage/dev/silver/agro/measurements/year=2026/month=10/clean_9c617b88-90f5-4d2d-97e6-ddd18aeed7fc.parquet
[QUARANTINE] 2 registros -> /app/storage/dev/quarantine/agro/measurements/year=2026/month=10/rejected_9c617b88-90f5-4d2d-97e6-ddd18aeed7fc.parquet
[DQ] total=8 valid=6 warning=0 invalid=2 score=75.0% utilizable=75.0% errores=7
[DB] Upsert de 8 filas en gold.fields.
[DB] Upsert de 6 filas en gold.daily_field_metrics.
[PIPELINE] Lote 9c617b88-90f5-4d2d-97e6-ddd18aeed7fc procesado.
[PIPELINE] Duración: 17.9s (objetivo RNF08: < 300s)
```

Estado de `agro_dev` después de la corrida (campos de `gold.fields`; filas de `daily_field_metrics` con campos nuevos y viejos; última corrida: lote, total, valid, warning, invalid, dq_score, pct_utilizable, status):

```
C01,C02,C03,C04,C05,C06,LIT-01,LIT-02,LIT-03,LIT-04,LIT-05,LIT-06,LIT-07,LIT-08
38 | 30
9c617b88-90f5-4d2d-97e6-ddd18aeed7fc | 8 | 6 | 0 | 2 | 75.00 | 75.00 | ok
```

## 4. Qué NO pude verificar o dejé pendiente

- **Dashboards a ojo.** Probé las consultas SQL en los pasos anteriores, pero no abrí Grafana en un navegador. No vi la disposición ni los colores.
- **`pytest` sin base de datos.** Con `TEST_DATABASE_URL` indefinida, 5 tests de integración se omiten y la cobertura baja; la corrida de arriba incluye la base. No corrí el CI de GitHub Actions.
- **Una sola corrida de DEV, de 8 registros** (un solo intervalo de 15 minutos), porque el *scheduler* ya había consumido los anteriores. Sirve para probar el flujo completo, no para medir tasas de error: 2 de 8 inválidos no es una muestra.
- **Los datos viejos siguen ahí.** `agro_dev`, `agro_staging` y `agro_prod` tienen las filas de los campos `C01` a `C06` mezcladas con las nuevas `LIT-*`. Sigue pendiente tu respuesta a si las borro. Hasta entonces los gráficos de Grafana por campo muestran 14 campos.
- **Simulador por sensor y distribución de errores (paso 2).** No se implementaron: esperan tu aprobación (ver `paso-1.md` y `paso-2.md`). El README y la especificación hablan de 200 sensores y 19.200 registros por día; el código genera 768 por día.
- **Historial remoto.** Estos commits están solo en tu PC (el primer commit del paso 1 ya estaba en GitHub).
- **`agro_test` y `agro_cat`.** Las bases descartables que usé están borradas.

## 5. Desvíos respecto de la especificación y por qué

1. **Tests con base de datos descartable**, no con las bases del stack, porque esos tests borran tablas (`DELETE`) y no quería tocar los datos de `agro_dev`, `agro_staging` ni `agro_prod`.
2. **Paré y volví a arrancar `scheduler-dev`** durante la corrida manual, para que el lote de prueba fuera mío. Quedó funcionando como antes.
