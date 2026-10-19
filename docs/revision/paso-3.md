# Revisión del paso 3: Data Quality Score

## 1. Qué pediste vs. qué hiciste

| Ítem de la especificación | Qué hice |
|---|---|
| `dq_score = VALID / total * 100` (estricto) | `ValidationResult.dq_score` en `src/validation/engine.py` ahora es solo VALID sobre el total. |
| `pct_utilizable = (VALID + WARNING) / total * 100` | Nueva propiedad `ValidationResult.pct_utilizable` (misma fórmula que tenía el score anterior). |
| Guardar ambos en `gold.dq_run_metrics` (`sql/schema/01_schema.sql`) | Columna nueva `pct_utilizable`; `quality.record_quality` guarda las dos. |
| Migración para los tres entornos | `sql/schema/01_schema.sql` agrega la columna con `ADD COLUMN IF NOT EXISTS` y recalcula `dq_score` y `pct_utilizable` de las corridas existentes a partir de sus contadores (idempotente). La apliqué a `agro_dev`, `agro_staging` y `agro_prod` con `00_entornos.sh` (sección 3). |
| `porcentaje_calidad` de `gold.daily_field_metrics` con el mismo score estricto, por campo y por día | `src/transformation/gold.py`: ahora es `VALID / (publicados + rechazados atribuibles)`. Los WARNING siguen contando en `cantidad_mediciones` (se publican) pero no suman al porcentaje. |
| Actualizar tests | `test_pipeline_units.py`: el test del score se reescribió (33,33 estricto y 66,67 utilizable) y hay un test nuevo del porcentaje diario con un WARNING. `test_integration_db.py` verifica ambas columnas contra los contadores de la corrida. |
| Dashboard: mostrar ambos números rotulados | `calidad-datos.json`: dos paneles ("DQ Score estricto (solo VALID)" y "% utilizable (VALID + WARNING)"); la serie por corrida muestra las dos líneas con leyenda; el panel diario pasó a "% de calidad estricto por campo y día (solo VALID)". `flujo-etl.json`: la tabla de corridas tiene las dos columnas. |
| Actualizar la decisión D2 | D2 reescrita. Agregué D22 (un rechazo invalida el registro completo), que D2 referencia. |

También actualicé las descripciones del catálogo en `src/governance/catalog.py`, el rótulo del paso 5 del ETL paso a paso (`trace.py`) y tres líneas del README sobre el score.

## 2. Archivos cambiados y hash del commit

El hash se informa en el chat (un commit no puede contener su propio hash); se ve con `git log --oneline -3`. Commit padre: `78a38ff`.

- `src/validation/engine.py`, `src/metrics/quality.py`, `src/metrics/trace.py`, `src/transformation/gold.py`, `src/governance/catalog.py`
- `sql/schema/01_schema.sql`
- `tests/test_pipeline_units.py`, `tests/test_integration_db.py`
- `grafana/dashboards/calidad-datos.json`, `grafana/dashboards/flujo-etl.json`
- `docs/decisiones.md` (D2 y D22), `README.md`
- `docs/revision/paso-3.md` (este archivo)

## 3. Comandos que corrí y su salida real

`ruff check .`:

```
All checks passed!
```

(La primera corrida falló por una línea de más de 135 caracteres en `catalog.py`; la partí y volvió a pasar.)

`python -m src.validation.check_rules`:

```
[RULES] OK: 12 reglas y 8 campos válidos.
```

`python -m pytest -q`:

```
...................                                                      [100%]
87 passed, 4 skipped in 12.08s
```

Tests de integración con PostgreSQL contra una base descartable `agro_test` (ya borrada):

```
tests\test_integration_db.py ....                                        [100%]
============================== 4 passed in 4.36s ==============================
```

Migración probada sobre una base con el esquema del commit anterior (`78a38ff`) y tres corridas cargadas con la definición vieja (`dq_score` = 90 en las dos primeras); luego apliqué el esquema nuevo dos veces:

```
 _batch_id | status  | total | valid | warning | invalid | dq_score | pct_utilizable
-----------+---------+-------+-------+---------+---------+----------+----------------
 a         | ok      |   100 |    80 |      10 |      10 |    80.00 |          90.00
 b         | ok      |   200 |   150 |      30 |      20 |    75.00 |          90.00
 c         | running |       |       |         |         |          |
```

Migración aplicada a las tres bases del stack (`docker compose exec postgres bash /docker-entrypoint-initdb.d/00_entornos.sh` y `99_app_users.sh`):

```
[INIT] Base agro_dev lista.
[INIT] Base agro_staging lista.
[INIT] Base agro_prod lista.
[INIT] Permisos aplicados en agro_dev.
[INIT] Permisos aplicados en agro_staging.
[INIT] Permisos aplicados en agro_prod.
```

Promedios por entorno después de migrar (corridas con datos; columnas: cantidad, DQ estricto, % utilizable, corridas sin % utilizable):

```
agro_dev     23 | 70.13 | 82.84 | 0
agro_staging 23 | 96.32 | 98.23 | 0
agro_prod    28 | 95.50 | 98.38 | 0
```

Reconstrucción del stack (`docker compose up -d --build`): los tres schedulers y Grafana arrancaron con el código nuevo.

Consultas SQL de los dashboards (las 37, con las variables y macros de Grafana reemplazadas a mano) ejecutadas contra `agro_dev` y `agro_prod`:

```
dev consultas ok: 37 con error: 0
prod consultas ok: 37 con error: 0
```

La API de Grafana ya lista los paneles `DQ Score estricto (solo VALID)`, `% utilizable (VALID + WARNING)` y `DQ Score estricto y % utilizable por corrida`.

## 4. Qué NO pude verificar o dejé pendiente

- **Dashboards a ojo.** Probé que las consultas ejecuten y que Grafana cargue los paneles, pero no los abrí en un navegador: no vi la disposición (los paneles de la fila superior cambiaron de ancho) ni los colores.
- **Valores históricos de `porcentaje_calidad` en `gold.daily_field_metrics`.** Las filas ya existentes siguen con la definición anterior, porque recalcularlas necesita el `dq_status` de Silver (en Parquet), no solo la base. Una fila se recalcula con la definición estricta cuando un lote nuevo toca esa combinación (fecha, campo, fuente). No hice un reproceso masivo; si lo querés, es `python -m src.main --reprocess <batch_id>` por lote.
- **Metas del dashboard.** Los umbrales de color (90 y 95 %) no cambiaron. Con el score estricto los valores de DEV (promedio 70 %) y los de PROD (95,5 %) caen más abajo que antes; no sé si la meta del 95 % de la especificación debe aplicarse al estricto o al utilizable. Necesito tu decisión.
- **Filas sin total.** Las corridas en estado `running` o sin `total` quedan con `dq_score` y `pct_utilizable` nulos (la migración las ignora a propósito).
- **Datos ya cargados en el stack.** Siguen teniendo los campos viejos `C01`–`C06` (ver paso 1).

## 5. Desvíos respecto de la especificación y por qué

1. **El porcentaje diario no ve algunos rechazos.** La especificación pide "la misma definición del score estricto", y es lo que implementé: el denominador es publicados + rechazados atribuibles a ese día. Los rechazos sin fecha o sin campo (DQ01, DQ02, DQ03, DQ04) no se pueden asignar a un día y campo, así que el score diario no los ve y el de la corrida sí. Por eso el score diario promedio puede ser mayor que el de la corrida. Era una limitación anterior; no la cambié.
2. **Agregué D22**, que la especificación recién pide documentar en el paso 5, porque D2 lo referencia.
3. **Ancho de los paneles de la fila superior.** Para sumar un panel hubo que achicar los de "Registros procesados" y "Última corrida" (de 4 a 3 y de 6 a 4 columnas). Es una decisión de diseño mía.
