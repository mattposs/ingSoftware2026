# Cambios sugeridos al documento de proyecto (v7 → v8)

Lista de correcciones para `TPO_Pipeline_DataOps_Documento_Final_v7.docx` surgidas de la auditoría
del repositorio. No se editó el .docx: aplicar a mano y regenerar el PDF.

## Inconsistencias internas

| # | Sección | Problema | Corrección sugerida |
|---|---|---|---|
| 1 | 5.4 Entregables | Dice "Base de datos con capas Bronze, Silver y Gold", pero la sección 6 pone Bronze/Silver en Parquet. | "Lake Parquet (Bronze, Silver, Quarantine) y base PostgreSQL con la capa Gold." |
| 2 | 10.1 Stack | Deja abiertas "Pandas / Polars" y "Great Expectations o Pytest", cuando 6 y 8.1 ya eligieron. | Pandas + PyArrow; tests propios con Pytest. Justificación: menos curva de aprendizaje (R03) y las reglas ya viven en `config/rules.yaml`. |
| 3 | 10.2 Herramientas | Sugiere Trello / Jira / Miro, pero 7.4 ya eligió ClickUp. | Completar con ClickUp (Kanban), GitHub (código y docs), el canal de chat que usen y la herramienta del Gantt. |
| 4 | 7.3 Hitos vs 7.1 EDT | Hito del 19/10 "Docker y CI funcionando", pero la tarea 7.2 (GitHub Actions) está en S4 (desde 20/10). | Mover 7.2 a S3, o el hito al 23/10. **El CI ya está implementado** (`.github/workflows/ci.yml`). |
| 5 | 8.1 Recursos | "15 a 25 h semanales" × 6 semanas = 90 a 150 h, pero el PM tiene 80 h. | "10 a 25 h semanales según el rol". |
| 6 | 6.2 DQ11 | "Hueco ≥ 30 min (2 lecturas seguidas de 15 min)" es ambiguo. | "Hueco ≥ 30 min entre lecturas consecutivas (al menos una lectura faltante); para Open-Meteo, que es horario, ≥ 120 min." (decisión D1). |
| 7 | 4.1 RF07 / 6.1 | No define si los WARNING cuentan como válidos en el DQ Score. | "DQ Score = (VALID + WARNING) / total × 100" (decisión D2). |
| 8 | 2.1 Sensores | "30 sensores… unos 576 registros por día" se entiende mejor aclarando qué es un registro. | "Cada estación envía un registro con sus 5 variables cada 15 min: 6 × 96 = 576 registros por día." |

## Ajustes al modelo de datos (figura 3)

- **Bronze:** una columna de unidad por variable (`temperature_unit`, `humidity_unit`, `soil_moisture_unit`, `precipitation_unit`, `wind_speed_unit`), no solo de temperatura (D3).
- **gold.dq_errors:** agregar `measured_at` y `source` (D10).
- **gold.dq_run_metrics:** agregar `status` (running / ok / failed).
- **6.1, tabla Gold:** mencionar `fuente` como parte de la clave (D4).

## Nuevo: entornos y ETL paso a paso (sumar a la v8)

- **5.1 Alcance / 6. Arquitectura:** agregar los tres entornos (DEV, STAGING, PROD) aislados por base, lake y configuración, con promoción por CI/CD (decisiones D17 y D18). Aclarar que corren en forma local: no cambia el costo (sigue sin nube).
- **7.1 EDT, tarea 7.3 "Ejecución programada y deploy":** detallar el *scheduler* por entorno y el flujo de promoción `:dev → :staging → :prod` con aprobación manual.
- **9.2 Riesgos:** el riesgo R02 (scope creep) se mitiga separando lo que se prueba en DEV de lo que se muestra en PROD.
- **11. POC:** para la demo, el dashboard *ETL paso a paso* sigue un registro real (por ejemplo, una humedad de 135 % rechazada por DQ07) desde la extracción hasta Quarantine, y uno válido hasta Gold.

## Secciones a completar con lo ya implementado

- **11. POC:** el pipeline corre con `python -m src.main`. Datos reales de Open-Meteo y del simulador, las 12 reglas, quarantine con motivos, Gold en PostgreSQL. El test `test_reglas_detectan_al_menos_95_por_ciento_de_errores_inyectados` es la evidencia de la meta SMART de detección. Para la evidencia de "test que falla y luego pasa en CI", alcanza con cambiar un umbral en `config/rules.yaml` en una rama y abrir un PR.
- **10.3 Buenas prácticas:** PR con revisión obligatoria y CI verde para integrar a `main` (activar *branch protection*), commits con `RFxx`, actas en `docs/`.
- **Datos pendientes:** grupo, integrantes, docente, versión y link de ClickUp.
