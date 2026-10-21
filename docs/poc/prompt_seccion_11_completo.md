Actuá como redactor técnico de un documento universitario de Ingeniería de Software (UADE). Tengo que escribir la sección "11. Prueba de concepto (POC)" de mi Documento de Proyecto del TP final. Redactá la sección en español, en tono formal y claro, listo para pegar en el documento.

CONTEXTO DEL PROYECTO
- Consultora: Datum Sur. Cliente (ficticio): Grupo Agro del Litoral S.A., 8 campos (LIT-01 a LIT-08) en Entre Ríos, Santa Fe y Córdoba, unos 200 sensores, mediciones cada 15 minutos.
- Proyecto: pipeline DataOps para calidad de datos agroclimáticos IoT. Python + Pandas, arquitectura Medallion (Bronze, Silver y Quarantine en Parquet; Gold en PostgreSQL), 12 reglas de calidad (DQ01–DQ12) en config/rules.yaml, CI/CD con GitHub Actions, Docker Compose, Grafana.
- Clasificación de registros: VALID (sin hallazgos, pasa a Silver), WARNING (solo advertencias, pasa a Silver), INVALID (incumple regla de rechazo, va a Quarantine y no llega a Gold).
- Métricas: Data Quality Score = VALID / total × 100; % utilizable = (VALID + WARNING) / total × 100.
- Problema base del cliente: cerca del 14% de los registros tiene problemas de calidad (unos 2.700 por día). Ejemplo 1: humedad de suelo negativa en LIT-05 que lleva a un riego innecesario. Ejemplo 2: precipitaciones duplicadas en LIT-02 que llevan a postergar el riego. (Son los ejemplos de la sección 2.2 del documento.)
- Riesgo R03 (falla silenciosa de calidad): se mitiga con un test en CI que verifica 0 registros inválidos en Gold (RNF04).
- La POC no incluye alta disponibilidad, y los datos de sensores son simulados.

ESTRUCTURA OBLIGATORIA DE LA SECCIÓN
11.1 Entorno y ejecución: todo corre con docker compose up (pipeline + PostgreSQL + Grafana). Incluir link al repositorio y al video de la demo.
11.2 Datos ingestados: Open-Meteo para los 8 campos, período, y simulador IoT con su intervalo y la tasa de errores inyectados.
11.3 Reglas ejecutadas: tabla resumen de las 12 reglas con cantidad de hallazgos por regla en la corrida, más la tabla de resultados (Total, VALID, WARNING, INVALID, DQ Score, % utilizable).
11.4 Resultado en cada capa: un ejemplo por capa (Bronze, Silver, Quarantine, Gold). Incluir dentro de esta subsección el caso punta a punta: seguir el registro de humedad de suelo inválida de LIT-05 (DQ10) y el de precipitación duplicada de LIT-02 (DQ05) desde Bronze hasta Quarantine, y demostrar que no llegan a Gold. Cerrar el caso conectándolo con los ejemplos de la sección 2.2.
11.5 Evidencia de CI/CD: describir el test que falla y luego pasa (commit en rojo y commit en verde en GitHub Actions), explicando qué verifica el test y su relación con el riesgo R03 y el RNF04. Mencionar pytest y cobertura.
11.6 Dashboard: descripción del dashboard de Grafana (paneles, DQ Score por campo y por día), aclarando que lee solo el esquema gold con un usuario de solo lectura.
Cerrar la sección con un párrafo breve que vincule la POC con los objetivos específicos OE1 a OE5 de la sección 3.2 y con la meta transversal.

REGLAS DE REDACCIÓN
- Usá ÚNICAMENTE los datos que te doy abajo. No inventes cifras, fechas, nombres de archivos ni resultados. Si falta un dato, dejalo como [COMPLETAR: descripción del dato].
- Donde corresponda una imagen, insertá un marcador con el formato: [CAPTURA N: descripción de lo que debe mostrar] seguido de un epígrafe "Figura N. ...".
- Usá tablas en markdown para las métricas y para los ejemplos de registros.
- Mantené la numeración de subsecciones 11.1 a 11.6.
- Extensión objetivo: entre 2 y 3 páginas de texto (sin contar capturas), prosa concisa y sin relleno.
- Al final, agregá una lista de "Pendientes antes de entregar" con todos los [COMPLETAR] y las capturas que faltan.

DATOS REALES DE LA POC
Repositorio: https://github.com/SebastianMB1/IngSoftwareETL (rama feature/entornos-etl-paso-a-paso)
Video de la demo: [COMPLETAR: link]
Comando de ejecución: `docker compose up -d --build` (levanta PostgreSQL 16, los 3 schedulers del pipeline —dev, staging y prod— y Grafana) y, para la corrida manual completa sobre los 8 campos: `docker compose run --rm -e APP_ENV=staging pipeline`. La corrida de la evidencia se hizo con esa misma configuración (STAGING: Open-Meteo + simulador IoT) sobre una base y un lake vacíos (agro_poc, storage/poc).

Datos ingestados
- Período Open-Meteo: 13/10/2026 00:00 – 15/10/2026 23:00 UTC (datos horarios; ventana pedida: (12/10/2026 23:00, 15/10/2026 23:00] UTC)
- Registros Open-Meteo: 576 (8 campos × 72 horas)
- Registros del simulador IoT: 767 (19/10/2026 23:15 – 20/10/2026 23:00 UTC; una lectura por campo, no por sensor)
- Intervalo del simulador: 15 min
- Tasa de errores inyectados: 14 % configurado (error_rate: 0.14); medido en la corrida: 108 de 767 registros = 14,08 %

Resultados de la corrida (batch_id: ece83881-91dc-4356-b6cf-eb7ddfa7f759, 20/10/2026 23:07 UTC, duración 9,9 s)
- Total: 1.343 | VALID: 1.193 | WARNING: 53 | INVALID: 97
- DQ Score: 88,83 % | % utilizable: 92,78 %

Hallazgos por regla
DQ01: [7] | DQ02: [9] | DQ03: [21] | DQ04: [5] | DQ05: [6] | DQ06: [9]
DQ07: [15] | DQ08: [7] | DQ09: [10] | DQ10: [10] | DQ11: [215] | DQ12: [12]
(DQ01–DQ10 = rechazos; DQ11 y DQ12 = warnings. Total 326 hallazgos: Crítica 57, Alta 42, Media 227.)

DQ Score por campo
(Dato real disponible por campo y por día: gold.daily_field_metrics.porcentaje_calidad, estricto. Simulador IoT, días 19/10 y 20/10 en hora local; Open-Meteo = 100 % en todos los días, 12/10 a 15/10, para los 8 campos.)
LIT-01: [86,67 % · 82,19 %] | LIT-02: [76,92 % · 76,06 %] | LIT-03: [93,33 % · 82,19 %] | LIT-04: [80,00 % · 88,46 %] | LIT-05: [86,67 % · 80,00 %] | LIT-06: [85,71 % · 91,46 %] | LIT-07: [69,23 % · 91,14 %] | LIT-08: [86,67 % · 89,87 %]

Ejemplos por capa (pegar filas reales)
- Bronze: timestamp "2026-10-19T23:15:00Z" (texto) · field_id LIT-01 · temperature 15.99 °C · humidity 69.1 % · soil_moisture 0.281 m³/m³ · precipitation 0.0 mm · wind_speed 9.8 km/h · source iot_simulator · _batch_id ece83881-91dc-4356-b6cf-eb7ddfa7f759 · _ingested_at 2026-10-20 23:07:06.303658+00 · _source_system iot_simulator
- Silver (VALID y WARNING):
  - VALID: timestamp 2026-10-13 00:00:00+00 · source open_meteo · field_id LIT-01 · temperature 13.0 · humidity 85.0 · soil_moisture 0.469 · precipitation 0.0 · wind_speed 10.3 · dq_status VALID · _dq_warnings (vacío)
  - WARNING: timestamp 2026-10-20 04:15:00+00 · source iot_simulator · field_id LIT-01 · temperature 9.56 · humidity 85.3 · soil_moisture 0.281 · precipitation 0.0 · wind_speed 15.3 · dq_status WARNING · _dq_warnings DQ11
- Quarantine: timestamp "2026-10-20T00:15:00Z" · field_id LIT-01 · temperature 14.34 · humidity 70.9 · soil_moisture 0.279 · precipitation -3.0 mm · wind_speed 10.7 · source iot_simulator · _sim_injected_error negative_precipitation · _rejection_reasons DQ08 · _rejected_at 2026-10-20 23:07:06.761632+00
- Gold (3 filas de daily_field_metrics):
  - 2026-10-20 · LIT-01 · iot_simulator · temperatura_promedio 15.219 · precipitacion_total 2.9 · humedad_suelo_promedio 0.280 · humedad_ambiental_promedio 69.338 · cantidad_mediciones 66 · porcentaje_calidad 82.19
  - 2026-10-20 · LIT-02 · iot_simulator · 16.631 · 0.4 · 0.292 · 68.629 · 65 · 76.06
  - 2026-10-20 · LIT-03 · iot_simulator · 16.923 · 0.0 · 0.301 · 69.684 · 68 · 82.19

Caso punta a punta
- DQ10 en LIT-05: registro Bronze [timestamp "2026-10-20T23:00:00Z" · LIT-05 · soil_moisture 1.35 m³/m³ (mayor al máximo físico de 1; el simulador inyecta este error con valores > 1, no negativos) · temperature 19.82 · humidity 65.6 · precipitation 0.0 · _sim_injected_error soil_out_of_range · _batch_id ece83881-…; regla disparada en gold.dq_errors: DQ10 · Validez · Alta · REJECT · variable soil_moisture · "fuera del rango físico [0, 1]"], fila en Quarantine [el mismo registro con _rejection_reasons = DQ10, _rejected_at 2026-10-20 23:07:06.761632+00], consulta que prueba que no está en Gold [`SELECT cantidad_mediciones, humedad_suelo_promedio, porcentaje_calidad FROM gold.daily_field_metrics WHERE field_id = 'LIT-05' AND fuente = 'iot_simulator' AND fecha = '2026-10-20';` → 68 | 0.316 | 80.00. Silver tiene 68 registros de LIT-05 ese día y 0 con la identidad del registro rechazado; la humedad de suelo máxima que alimenta esa fila es 0.321]
- DQ05 en LIT-02: registro Bronze [en la corrida no hubo duplicados en LIT-02; se provocó en forma controlada reenviando, en el lote poc-dq05-ba8db9eb, la lectura real "2026-10-20T00:00:00Z" · LIT-02 · precipitation 2.6 mm · soil_moisture 0.289 · temperature 15.8 · humidity 69.2, idéntica a la original del lote ece83881-…, marcada _sim_injected_error = poc_duplicado_controlado; regla disparada: DQ05 · Crítica · REJECT · "registro ya procesado en un lote anterior"], fila en Quarantine [el registro repetido con _rejection_reasons = DQ05, _rejected_at 2026-10-20 23:10:12.560515+00], consulta que prueba que no está en Gold [`SELECT precipitacion_total, cantidad_mediciones FROM gold.daily_field_metrics WHERE field_id = 'LIT-02' AND fuente = 'iot_simulator' AND fecha = '2026-10-19';` → 2.6 | 12 antes y después del duplicado (las 00:00 UTC son las 21:00 del 19/10 en hora local); `SELECT count(*) FROM gold.daily_field_metrics WHERE _batch_id = 'poc-dq05-ba8db9eb';` → 0. Silver tiene 1 sola copia de la lectura]

CI/CD
- Nombre del workflow: CI (.github/workflows/ci.yml; job "test", paso "Tests (Pytest) + cobertura mínima del 80% en validación"; corre en cada pull request y en cada push a main)
- Nombre del test de control (Gold sin inválidos): tests/test_integration_db.py::test_gold_no_tiene_registros_invalidos
- Cambio que provocó la falla: en config/rules.yaml, regla DQ08, `min: 0` → `min: -100` (acepta precipitación negativa). Verificado localmente: 5 tests fallan, entre ellos el de control (`assert (df["precipitacion_total"] >= 0).all()`); al revertir pasan los 93 tests
- Link/ID del run en rojo: [COMPLETAR] | Link/ID del run en verde: [COMPLETAR]
- Cobertura del módulo de validación: 92 % (mínimo exigido 80 %; engine.py 99 %, check_rules.py 72 %); pytest: 93 passed; cobertura total del código: 87 %

Dashboard
- Herramienta y paneles: Grafana 11.4 (http://localhost:3000), 3 tableros. «Calidad de datos agroclimáticos»: DQ Score estricto (solo VALID), % utilizable (VALID + WARNING), registros procesados, VALID / WARNING / INVALID, última corrida, DQ Score estricto y % utilizable por corrida, hallazgos por regla, temperatura y humedad de suelo promedio diaria, mapa de los campos, lluvia acumulada por campo, % de calidad estricto por campo y día, últimos registros rechazados. «ETL paso a paso»: recorrido de un registro de muestra por las 5 etapas. «Flujo del ETL (Bronze · Silver · Gold)»: registros por capa y por lote, duración de cada etapa, ventanas incrementales e historial de lotes
- Usuario/permisos de conexión: usuario de PostgreSQL `dashboard`, solo lectura (SELECT) sobre el esquema gold; las 37 consultas de los 3 tableros usan solo tablas gold.*; verificado: SELECT en gold.daily_field_metrics funciona, SELECT en etl.watermarks → "permission denied for schema etl", INSERT en gold.fields → "permission denied for table fields". Acceso anónimo de Grafana con rol Viewer (solo ver)
