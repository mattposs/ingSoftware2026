# Evidencia de las alertas del pipeline (sección 11.6)

Generado por `scripts/simulate_alerts.py` el 2026-10-26 23:47:21 UTC (20:47:21 hora Argentina), contra el entorno **STAGING**. Todos los datos salen de la ejecución: la hora de la falla, de `gold.dq_run_metrics`; la hora de disparo y el estado, de la API de Grafana (`activeAt` de la instancia en Firing o, en un escenario rearmado con `--recuperar`, la transición a Alerting del historial de estados); la notificación, de Mailpit.

## Texto para la sección 11.6

**Escenario A – Corrida del pipeline con PIPELINE_FORCE_FAILURE=true (falla antes de la extracción).** Se provocó con `docker compose run --rm -e APP_ENV=staging -e PIPELINE_FORCE_FAILURE=true pipeline`. La corrida quedó registrada a las 2026-10-26 23:45:36 UTC (20:45:36 hora Argentina). Grafana disparó la alerta **AL01** a las 2026-10-26 23:46:00 UTC (20:46:00 hora Argentina), **0,39 minutos** después. La notificación llegó por correo (Mailpit) a las 2026-10-26 23:46:12 UTC (20:46:12 hora Argentina), con el asunto «[FIRING:1] AL01 · Corrida fallida o ausente · STAGING staging Alertas del pipeline (AL01 critica)». RNF11 (alerta en ≤ 30 minutos): **se cumple**.

**Escenario B – Corrida del simulador IoT con 50 % de registros con errores inyectados.** Se provocó con `docker compose run --rm -e APP_ENV=staging -e PIPELINE_IOT_ERROR_RATE=0.5 pipeline python -m src.main --env staging --source iot_simulator`. La corrida quedó registrada a las 2026-10-26 23:16:14 UTC (20:16:14 hora Argentina). El DQ Score de esa corrida fue de **44,44 %** (4 registros VALID de 9; 1 WARNING y 4 INVALID). Grafana disparó la alerta **AL02** a las 2026-10-26 23:17:00 UTC (20:17:00 hora Argentina), **0,76 minutos** después. La notificación llegó por correo (Mailpit) a las 2026-10-26 23:17:17 UTC (20:17:17 hora Argentina), con el asunto «[FIRING:1] AL02 · Caída del DQ Score · STAGING staging Alertas del pipeline (AL02 alta)». RNF11 (alerta en ≤ 30 minutos): **se cumple**.

## Datos

| Escenario | Falla provocada | Alerta | Hora de la falla | Hora del disparo | Minutos | DQ Score | RNF11 (≤ 30 min) |
|---|---|---|---|---|---|---|---|
| A | Corrida del pipeline con PIPELINE_FORCE_FAILURE=true (falla antes de la extracción) | AL01 | 2026-10-26 23:45:36 UTC (20:45:36 hora Argentina) | 2026-10-26 23:46:00 UTC (20:46:00 hora Argentina) | 0,39 | — | Cumple |
| B | Corrida del simulador IoT con 50 % de registros con errores inyectados | AL02 | 2026-10-26 23:16:14 UTC (20:16:14 hora Argentina) | 2026-10-26 23:17:00 UTC (20:17:00 hora Argentina) | 0,76 | 44,44 % | Cumple |

## Notas

- Escenario B: rearmado con `--recuperar` (no se repitió la falla). La captura de la lista de alertas se tomó después, con AL02 todavía en Firing desde el disparo original.

## Capturas

En cada captura se ve, abajo a la derecha, la hora en que se tomó.

| Archivo | Escenario | Qué muestra | Tomada |
|---|---|---|---|
| [AL01_firing.png](AL01_firing.png) | A | Lista de alertas con la regla en Firing | 2026-10-26 23:46:28 UTC (20:46:28 hora Argentina) |
| [AL01_detalle_regla.png](AL01_detalle_regla.png) | A | Detalle de la regla | 2026-10-26 23:46:34 UTC (20:46:34 hora Argentina) |
| [AL01_panel_salud.png](AL01_panel_salud.png) | A | Panel de salud del pipeline (dashboard de calidad, STAGING) | 2026-10-26 23:46:40 UTC (20:46:40 hora Argentina) |
| [AL01_notificacion_mailpit.png](AL01_notificacion_mailpit.png) | A | Notificación recibida en Mailpit | 2026-10-26 23:46:49 UTC (20:46:49 hora Argentina) |
| [AL02_firing.png](AL02_firing.png) | B | Lista de alertas con la regla en Firing | 2026-10-26 23:45:05 UTC (20:45:05 hora Argentina) |
| [AL02_detalle_regla.png](AL02_detalle_regla.png) | B | Detalle de la regla | 2026-10-26 23:17:35 UTC (20:17:35 hora Argentina) |
| [AL02_panel_salud.png](AL02_panel_salud.png) | B | Panel de salud del pipeline (dashboard de calidad, STAGING) | 2026-10-26 23:17:43 UTC (20:17:43 hora Argentina) |
| [AL02_notificacion_mailpit.png](AL02_notificacion_mailpit.png) | B | Notificación recibida en Mailpit | 2026-10-26 23:17:52 UTC (20:17:52 hora Argentina) |

## Restauración del entorno

- scheduler-staging: en ejecución al terminar (igual que al empezar).
- PIPELINE_FORCE_FAILURE y PIPELINE_IOT_ERROR_RATE se pasaron solo a contenedores de un solo uso (docker compose run --rm): ningún archivo ni scheduler quedó con esos valores.
- Las corridas de prueba quedan en gold.dq_run_metrics de STAGING (son la evidencia). La del escenario B también aportó su lote al Gold de STAGING.

Detalle completo: [`resultados.json`](resultados.json) y la salida de cada corrida (`<escenario>_salida_pipeline.txt`).
