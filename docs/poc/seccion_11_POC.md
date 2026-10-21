## 11. Prueba de concepto (POC)

La prueba de concepto demuestra el funcionamiento de punta a punta del pipeline DataOps sobre los ocho campos de Grupo Agro del Litoral S.A. (LIT-01 a LIT-08). Integra datos meteorológicos reales de Open-Meteo y lecturas simuladas de sensores IoT, las valida con las doce reglas de calidad, separa lo utilizable de lo rechazado y publica en la capa Gold solo indicadores validados. Todas las cifras de esta sección provienen de una corrida real del pipeline (lote `ece83881-91dc-4356-b6cf-eb7ddfa7f759`, ejecutado el 20/10/2026), con la configuración del entorno de staging.

### 11.1 Entorno y ejecución

La solución corre localmente con Docker Compose. Un único comando levanta PostgreSQL, los procesos programados del pipeline (uno por entorno: desarrollo, staging y producción) y Grafana:

```
docker compose up -d --build
```

Para la evidencia, la corrida se ejecutó una vez en forma manual sobre una base de datos y un lake vacíos, de modo que los resultados no se mezclaran con corridas anteriores:

```
docker compose run --rm -e APP_ENV=staging pipeline
```

La corrida completa (extracción, validación y carga en Gold) tardó 9,9 segundos, por debajo del objetivo de 5 minutos por corrida.

- Repositorio: https://github.com/SebastianMB1/IngSoftwareETL
- Video de la demo: [COMPLETAR: link al video]

[CAPTURA 1: terminal con `docker compose ps` mostrando los cinco contenedores en ejecución y PostgreSQL en estado *healthy*.]
Figura 11.1. Servicios de la POC levantados con Docker Compose.

[CAPTURA 2: terminal con la salida de la corrida del pipeline: registros escritos en Bronze, Silver y Quarantine, línea `[DQ]` con los totales y duración.]
Figura 11.2. Salida de la corrida del pipeline.

### 11.2 Datos ingestados

| Fuente | Período (UTC) | Registros | Campos |
|---|---|---|---|
| Open-Meteo Historical Weather API (datos reales, horarios) | 13/10/2026 00:00 a 15/10/2026 23:00 | 576 | LIT-01 a LIT-08 |
| Simulador de sensores IoT | 19/10/2026 23:15 a 20/10/2026 23:00 | 767 | LIT-01 a LIT-08 |
| **Total** | | **1.343** | |

- **Intervalo:** el simulador genera una lectura por campo cada 15 minutos.
- **Tasa de errores:** inyecta errores a propósito a una tasa configurada del 14 %, en línea con la línea base de la sección 2.2. En la corrida, 108 de los 767 registros simulados (14,08 %) llevaban un error inyectado. Los errores cubren 13 tipos: humedad fuera de rango, timestamps inválidos o futuros, temperatura extrema, humedad de suelo fuera de rango, unidades incorrectas, campo nulo o inexistente, precipitación negativa, saltos bruscos, huecos y duplicados.
- **Simplificación de la POC:** el simulador produce una lectura por campo y no por cada uno de los 200 sensores del cliente.

### 11.3 Reglas ejecutadas

Las doce reglas de `config/rules.yaml` se ejecutaron sobre los 1.343 registros. Un mismo registro puede generar más de un hallazgo; DQ11, por ejemplo, registra uno por cada variable con hueco.

| Regla | Descripción | Tipo | Severidad | Acción | Hallazgos |
|---|---|---|---|---|---|
| DQ01 | Timestamp obligatorio | Completitud | Crítica | Rechazo | 7 |
| DQ02 | field_id obligatorio | Completitud | Crítica | Rechazo | 9 |
| DQ03 | Timestamp con formato válido | Consistencia | Crítica | Rechazo | 21 |
| DQ04 | Medición de un campo existente | Integridad | Crítica | Rechazo | 5 |
| DQ05 | Sin registros duplicados | Unicidad | Crítica | Rechazo | 6 |
| DQ06 | Unidades esperadas | Consistencia | Crítica | Rechazo | 9 |
| DQ07 | Humedad ambiental entre 0 % y 100 % | Validez | Alta | Rechazo | 15 |
| DQ08 | Precipitación ≥ 0 | Validez | Alta | Rechazo | 7 |
| DQ09 | Temperatura dentro de rango | Validez | Alta | Rechazo | 10 |
| DQ10 | Humedad del suelo dentro de rango | Validez | Alta | Rechazo | 10 |
| DQ11 | Sin períodos sin datos | Completitud | Media | Warning | 215 |
| DQ12 | Sin cambios anormales | Anomalía | Media | Warning | 12 |
| **Total** | | | | | **326** |

Por severidad hubo 57 hallazgos críticos, 42 de severidad alta (todos rechazos) y 227 de severidad media (advertencias).

| Total | VALID | WARNING | INVALID | DQ Score (VALID / total) | % utilizable ((VALID + WARNING) / total) |
|---|---|---|---|---|---|
| 1.343 | 1.193 | 53 | 97 | **88,83 %** | **92,78 %** |

Los 1.246 registros VALID y WARNING pasaron a Silver; los 97 INVALID, a Quarantine. La capa Gold quedó con 48 filas de indicadores diarios.

### 11.4 Resultado en cada capa

Cada capa conserva el dato en un estado distinto. Los siguientes son registros reales de la corrida.

**Bronze** (Parquet): el registro tal como llegó, con el timestamp como texto y las columnas de linaje.

| timestamp | field_id | temperature | humidity | soil_moisture | precipitation | _batch_id | _ingested_at | _source_system |
|---|---|---|---|---|---|---|---|---|
| 2026-10-19T23:15:00Z | LIT-01 | 15,99 °C | 69,1 % | 0,281 m³/m³ | 0,0 mm | ece83881-… | 2026-10-20 23:07:06 UTC | iot_simulator |

**Silver** (Parquet): registros tipados (timestamp en UTC) con su estado de calidad.

| timestamp (UTC) | fuente | field_id | temperature | humidity | soil_moisture | dq_status | _dq_warnings |
|---|---|---|---|---|---|---|---|
| 2026-10-13 00:00 | open_meteo | LIT-01 | 13,0 | 85,0 | 0,469 | VALID | — |
| 2026-10-20 04:15 | iot_simulator | LIT-01 | 9,56 | 85,3 | 0,281 | WARNING | DQ11 |

**Quarantine** (Parquet): el registro sin modificar, con el motivo de rechazo.

| timestamp | field_id | precipitation | _rejection_reasons | _rejected_at |
|---|---|---|---|---|
| 2026-10-20T00:15:00Z | LIT-01 | −3,0 mm | DQ08 | 2026-10-20 23:07:06 UTC |

**Gold** (PostgreSQL, `gold.daily_field_metrics`): indicadores diarios por fecha (hora local), campo y fuente.

| fecha | field_id | fuente | temp. prom. | precip. total | hum. suelo prom. | hum. ambiental prom. | mediciones | % calidad |
|---|---|---|---|---|---|---|---|---|
| 2026-10-20 | LIT-01 | iot_simulator | 15,219 | 2,9 | 0,280 | 69,338 | 66 | 82,19 |
| 2026-10-20 | LIT-02 | iot_simulator | 16,631 | 0,4 | 0,292 | 68,629 | 65 | 76,06 |
| 2026-10-20 | LIT-03 | iot_simulator | 16,923 | 0,0 | 0,301 | 69,684 | 68 | 82,19 |

[CAPTURA 3: explorador de archivos con las carpetas `bronze`, `silver` y `quarantine` del lake y sus archivos Parquet.]
Figura 11.3. Capas Bronze, Silver y Quarantine en el lake Parquet.

#### Caso punta a punta

Se siguieron dos registros problemáticos de los tipos descriptos en la sección 2.2, desde su llegada hasta la capa Gold.

**Caso 1: humedad de suelo físicamente imposible en LIT-05 (DQ10).** El registro surgió en la corrida, inyectado por el simulador.

| Etapa | Evidencia |
|---|---|
| Bronze | 2026-10-20T23:00:00Z · LIT-05 · `soil_moisture = 1,35` m³/m³ |
| Regla | DQ10 · Validez · severidad Alta · rechazo: "fuera del rango físico [0, 1]" |
| Quarantine | Mismo registro, con `_rejection_reasons = DQ10` |
| Gold | Fila LIT-05 del 20/10: 68 mediciones (las mismas 68 que hay en Silver para ese día), humedad de suelo promedio 0,316 m³/m³; el valor máximo que la alimenta es 0,321 |

**Caso 2: precipitación duplicada en LIT-02 (DQ05).** En la corrida no hubo duplicados en LIT-02, así que se provocó en forma controlada. La lectura real de LIT-02 con lluvia (2026-10-20T00:00:00Z, 2,6 mm) se envió por segunda vez en un lote aparte, que pasó por el mismo código del pipeline.

| Etapa | Evidencia |
|---|---|
| Bronze | Lectura repetida, idéntica a la original (2,6 mm), en el lote `poc-dq05-ba8db9eb` |
| Regla | DQ05 · Unicidad · severidad Crítica · rechazo: "registro ya procesado en un lote anterior" |
| Quarantine | Registro repetido, con `_rejection_reasons = DQ05` |
| Gold | Fila LIT-02 del 19/10 (las 00:00 UTC son las 21:00 del 19 en hora local): precipitación total 2,6 mm antes y después del duplicado; el lote no escribió ninguna fila en Gold |

Consultas que demuestran que ninguno de los dos registros llegó a Gold:

```sql
-- Caso 1: el hallazgo queda registrado y la fila de Gold no lo incluye
SELECT rule_id, severidad, action, detalle FROM gold.dq_errors
WHERE field_id = 'LIT-05' AND measured_at = '2026-10-20 23:00:00+00';
SELECT cantidad_mediciones, humedad_suelo_promedio FROM gold.daily_field_metrics
WHERE field_id = 'LIT-05' AND fuente = 'iot_simulator' AND fecha = '2026-10-20';   -- 68 | 0,316

-- Caso 2: la lluvia no se duplica y el lote no escribe en Gold
SELECT precipitacion_total FROM gold.daily_field_metrics
WHERE field_id = 'LIT-02' AND fuente = 'iot_simulator' AND fecha = '2026-10-19';   -- 2,6
SELECT count(*) FROM gold.daily_field_metrics WHERE _batch_id = 'poc-dq05-ba8db9eb';   -- 0
```

[CAPTURA 4: consola SQL con las consultas del caso 1 y sus resultados.]
Figura 11.4. Caso DQ10 en LIT-05: el registro queda en Quarantine y no altera Gold.

[CAPTURA 5: consola SQL con las consultas del caso 2 y sus resultados.]
Figura 11.5. Caso DQ05 en LIT-02: la precipitación no se duplica en Gold.

Estos dos casos son los que originaban las decisiones erróneas de la sección 2.2.

- **Primer ejemplo de 2.2:** una humedad de suelo imposible hacía caer el promedio del campo y llevaba a un riego innecesario. Con el pipeline, ese valor se rechaza antes de llegar al indicador diario. En la POC el valor imposible estuvo por encima del máximo físico (1,35), no fue negativo; DQ10 rechaza ambos casos, porque exige que la humedad esté entre 0 y 1.
- **Segundo ejemplo de 2.2:** una lluvia registrada dos veces duplicaba el acumulado y postergaba el riego. Con el pipeline, la lectura repetida se aparta y el acumulado permanece en su valor real.

La POC también encontró un defecto: un lote compuesto solo por registros rechazados hacía fallar el guardado de las trazas. Se corrigió y se agregó un test de regresión. El lote afectado se recuperó reprocesándolo desde Bronze, sin pérdida de datos, lo que confirma en la práctica la reproducibilidad (RNF03).

### 11.5 Evidencia de CI/CD

Cada pull request ejecuta en GitHub Actions el workflow **CI** (`.github/workflows/ci.yml`), que corre el linter (ruff), la validación de `rules.yaml` y los tests con pytest sobre una base PostgreSQL real, con una cobertura mínima del 80 % en el módulo de validación.

El test de control es `test_gold_no_tiene_registros_invalidos` (`tests/test_integration_db.py`). Ejecuta una corrida y verifica cuatro condiciones:
- que los indicadores de Gold estén dentro de los rangos físicos;
- que todo campo de Gold exista en el maestro de campos;
- que no haya filas repetidas;
- que ningún registro rechazado aparezca en Silver ni se cuente en Gold.

Es el control que mitiga la falla silenciosa de calidad (riesgo R03) y verifica el requerimiento RNF04.

Para la evidencia se creó una rama de prueba. En un primer commit se aflojó la regla DQ08 en `config/rules.yaml` (`min: 0` → `min: -100`) para dejar pasar precipitaciones negativas: el workflow falla porque Gold queda con un total de lluvia negativo. En un segundo commit se revierte el cambio y el workflow vuelve a pasar. En la verificación local previa, el cambio hizo fallar 5 tests, entre ellos el test de control. Sin el cambio pasan los 93 tests, con 92 % de cobertura en el módulo de validación (mínimo exigido: 80 %).

- Run en rojo: [COMPLETAR: link o ID del run en GitHub Actions]
- Run en verde: [COMPLETAR: link o ID del run en GitHub Actions]

[CAPTURA 6: pull request de la rama de prueba con el check "CI / test" en rojo y el log con el fallo de `test_gold_no_tiene_registros_invalidos`.]
Figura 11.6. Commit en rojo: el test de control detecta datos inválidos en Gold.

[CAPTURA 7: el mismo pull request después de revertir el cambio, con todos los checks en verde y el resumen de cobertura.]
Figura 11.7. Commit en verde: el pipeline vuelve a cumplir las reglas.

### 11.6 Dashboard

El dashboard se construyó en Grafana y se publica en `http://localhost:3000`. Tiene tres tableros:

- **«Calidad de datos agroclimáticos».** Muestra:
  - el DQ Score estricto y el % utilizable de la última corrida;
  - los conteos VALID, WARNING e INVALID;
  - la evolución de ambos indicadores por corrida;
  - los hallazgos por regla (DQ01 a DQ12);
  - la temperatura y la humedad de suelo diarias por campo y un mapa de los campos;
  - el **porcentaje de calidad estricto por campo y por día** y los últimos registros rechazados.
- **«ETL paso a paso».** Sigue un registro de muestra por las cinco etapas del pipeline.
- **«Flujo del ETL (Bronze · Silver · Gold)».** Resume cuántos registros pasaron por cada capa en cada lote.

En la corrida de la POC, el DQ Score diario por campo de los datos simulados osciló entre 69,23 % y 93,33 %. Los datos de Open-Meteo alcanzaron el 100 % en todos los días.

Grafana se conecta a PostgreSQL con el usuario `dashboard`, que solo tiene permiso de lectura sobre el esquema `gold`. Las 37 consultas de los tres tableros leen únicamente tablas `gold.*`. Además, se comprobó que ese usuario no puede leer el esquema `etl` (`permission denied for schema etl`) ni insertar datos en `gold` (`permission denied for table fields`). Así, el dashboard nunca consume datos crudos ni rechazados.

[CAPTURA 8: tablero «Calidad de datos agroclimáticos», fila superior con DQ Score estricto, % utilizable y conteos.]
Figura 11.8. Indicadores de calidad de la última corrida.

[CAPTURA 9: panel «% de calidad estricto por campo y día».]
Figura 11.9. DQ Score estricto por campo y por día.

[CAPTURA 10: panel «Hallazgos por regla».]
Figura 11.10. Hallazgos por regla de calidad.

### Relación con los objetivos

La POC cumple los objetivos específicos de la sección 3.2:

- **OE1:** integró las dos fuentes para los ocho campos en las tres capas Medallion: Bronze y Silver en Parquet, Gold en PostgreSQL.
- **OE2:** ejecutó las doce reglas, clasificó el 100 % de los registros (1.193 + 53 + 97 = 1.343) y registró 326 hallazgos con fecha, campo, variable, regla y severidad.
- **OE3:** apartó los 97 registros inválidos en Quarantine con su motivo y publicó en Gold solo datos validados, que es lo único que consume el dashboard.
- **OE4:** automatizó la validación con 93 tests y el workflow de CI, que bloquea cualquier cambio que permita datos inválidos en Gold.
- **OE5:** calculó el Data Quality Score por corrida, por campo y por día.

En términos de la meta transversal, cada registro erróneo de la corrida fue detectado, registrado y excluido de los indicadores que respaldan las decisiones de riego, en lugar de usarse sin distinción como ocurre hoy.

---

### Pendientes antes de entregar

1. [COMPLETAR: link al video de la demo] (11.1).
2. [COMPLETAR: link o ID del run en rojo] y [COMPLETAR: link o ID del run en verde] de GitHub Actions (11.5). Se obtienen al crear la rama de prueba, abrir el pull request y revertir el cambio.
3. Capturas 1 a 10, según los marcadores de cada subsección.
4. **Capturas de Grafana (8 a 10):** el dashboard lee las bases de los entornos de desarrollo, staging y producción, no la base limpia usada para esta corrida. Antes de capturar conviene dejar esas bases solo con los campos LIT-01 a LIT-08, o filtrar por esos campos, para que las cifras coincidan con las de esta sección.
5. Ajustar la numeración de figuras (11.1 a 11.10) a la numeración general del documento, si corresponde.
6. Comando de ejecución: en el documento figura `docker compose run --rm -e APP_ENV=staging pipeline`. La corrida de la evidencia usó además una base y un lake aislados; el comando completo está en `docs/poc/EVIDENCIA_POC.md`. Confirmar cuál se quiere mostrar.
