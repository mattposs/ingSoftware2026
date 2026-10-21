# Comparación del documento: «TPO - Entrega Final - Grupo 2» (V2) vs. v7 y vs. el código

Fecha de la revisión: 20/10/2026. Documento revisado: `TPO - Entrega Final - Grupo 2.docx` (versión V2). Se compara contra `docs/TPO_Pipeline_DataOps_Documento_Final_v7.docx` y contra el repositorio (rama `feature/entornos-etl-paso-a-paso`, igual a `main` salvo el simulador HTML).

**En resumen:** la V2 avanzó mucho. Completó casi todo lo que la v7 tenía pendiente, cambió el cliente y la consultora, y agregó la matriz RACI, el mapa de stakeholders con nombres, los planes de contingencia, los costos de producción y las conclusiones. Los datos del cliente, las reglas y el Data Quality Score coinciden con el código. Hay **8 afirmaciones que contradicen lo implementado** (sección 2). La más repetida dice que la ejecución programada se hace con GitHub Actions, cuando en realidad la hacen los *schedulers* de Docker. También quedan 6 inconsistencias internas, algunos errores de tipeo y la **sección 11 (POC) sin completar**.

## 1. Qué cambió de la v7 a la V2

| Sección | v7 | V2 |
|---|---|---|
| Portada | Grupo, docente y versión «[Completar]» | Integrantes, docente (José Ramón Castiñeiras) y versión V2. Se agregó un índice. |
| 1. Consultora | UnaCocuCha SRL, 5 años | **Datum Sur**, 4 años; servicios, enfoque y propuesta de valor reescritos |
| 1.1 Equipo | Roles sin nombres | Nombres y responsabilidades detalladas (Maver PM, Martínez Benegas DE, Pisera QA, Posse Presa DevOps) |
| 2.1 Cliente | Agropecuaria Los Tres Ombúes, 6 campos, 18.000 ha, 30 sensores, 576 registros/día | **Grupo Agro del Litoral S.A.**, 8 campos LIT-01 a LIT-08, 20.000 ha, 200 sensores, 19.200 registros/día, con la tabla de campos |
| 2.2 Problema | ~8 % de errores y un ejemplo | ~14 % (≈ 2.700 registros/día), tabla por tipo de problema (6/3/3/2 %) y dos ejemplos de riego cuantificados |
| 2.3 Criticidad | Un párrafo | Tabla por área, urgencia y escenarios de «caída visible» y «falla silenciosa» |
| 3.2 Objetivos | Lista + metas SMART generales | Tabla OE1 a OE5 con indicador, plazo y responsable |
| 4. Requerimientos | Con columna Prioridad; RNF07 (Seguridad) y RNF08 (Rendimiento) | **Sin prioridad y sin RNF07 ni RNF08**; RF05 y RNF04 hablan de «reglas de rechazo» |
| 5.3 Stakeholders | Roles genéricos (8 filas) | Personas con nombre (6 filas); el equipo consultor y Open-Meteo ya no figuran |
| 5.4 Matriz RACI | No existía | **Nueva**: 9 paquetes de la EDT + 5 decisiones con el cliente |
| 5.5 Entregables | «Base de datos con capas Bronze, Silver y Gold» | «Lake Parquet (Bronze, Silver y Quarantine) y PostgreSQL con Gold»: se corrigió la inconsistencia 1 de `cambios_documento_v7.md` |
| 6. Arquitectura | 6.1 Medallion y 6.2 Reglas | Se reorganizó en 6.1 a 6.5: arquitectura general, Medallion, reglas, **modelo de datos** y **flujo de CI/CD** |
| 6.2 Medallion | Sin métricas | **DQ Score estricto y % utilizable**, igual que el código |
| 6.3 Reglas | DQ04 «C01 a C06»; DQ11 solo 30 min | Severidad + acción; DQ11 con 30 min (IoT) y 120 min (Open-Meteo); definición de «regla de rechazo» |
| 7.1 EDT | 9 paquetes con 22 sub-tareas | 9 paquetes descriptos en un renglón cada uno, con responsable por nombre |
| 7.3 Hitos | Entregas + 5 hitos técnicos | Solo las 4 entregas de la cátedra |
| 7.4 Kanban | 4 columnas | 6 estados (Backlog, Blocked, Doing, Test interno, Test cliente, Done), etiquetas y reglas de uso |
| 8. Recursos y costos | 430 h, USD 12.914, POC local sin nube | 360 h, **USD 11.000**, **con hosting cloud (USD 100)**, facturación por hito y costo de producción (USD 860/mes) |
| 9. Riesgos | 9 riesgos | 8 riesgos reescritos (R01 ahora es la concentración en el Data Engineer), matriz y **planes de contingencia** |
| 10. Herramientas | 10.1 a medias; 10.2 y 10.3 «[Completar]» | Completas: Teams, ClickUp, Drive, GitHub; plan de comunicación y bitácora de decisiones |
| 11. POC | «[Completar]» | **Sigue «[Completar]»** |
| 12. Conclusiones | «[Completar]» | Completas: beneficios, limitaciones y recomendaciones |

## 2. Afirmaciones que contradicen el código (corregir)

| # | Sección del documento | Qué dice | Qué hace el código | Corrección sugerida |
|---|---|---|---|---|
| 1 | 10.1, 12.2 y bitácora (6/10) | «La ejecución programada se resuelve con GitHub Actions» | La hacen tres contenedores *scheduler* (`src/scheduler.py`, uno por entorno) que corren el pipeline cada 15 min (D15). GitHub Actions solo corre CI y despliegue. | «La ejecución programada la hace un servicio *scheduler* en Docker, cada 15 minutos.» Corregirlo en las tres secciones. |
| 2 | 6.1 | «El watermark se actualiza después de confirmar la escritura en Gold; una corrida fallida se reintenta sin perder ni duplicar datos» | El watermark avanza cuando el lote queda escrito en **Bronze** (`src/pipeline.py`, D8). Si falla Silver o Gold, el lote **no se vuelve a extraer**: se reprocesa desde Bronze con `python -m src.main --reprocess <batch_id>`. | «El watermark avanza cuando el lote queda guardado en Bronze. Si una etapa posterior falla, se reprocesa desde Bronze sin volver a llamar a la fuente.» |
| 3 | 6 (intro) y 12.2 | «Corre en un único entorno local con Docker Compose» | Hay **tres entornos** (DEV, STAGING, PROD) en el mismo Docker Compose: tres bases (`agro_dev`, `agro_staging`, `agro_prod`), tres carpetas de lake y tres *schedulers* (D17). El documento no los menciona en ninguna parte. | Agregar los entornos en 6.1 (o en una 6.6) y cambiar «único entorno» por «entorno local con tres ambientes aislados». |
| 4 | 6.5 | «Ramas feature/* que se integran a main mediante pull request […] al integrar a main se construye y publica la imagen» | El flujo es feature/* → dev → staging → main (D18). `deploy.yml` publica la imagen en cada push a **dev, staging y main** (tags `:dev`, `:staging`, `:prod`). | Describir el flujo de tres ramas y que cada una despliega su entorno; producción con aprobación manual. |
| 5 | 6.4 | Tabla `fields` con «nombre, provincia, coordenadas y hectáreas» | Es `gold.fields`, con **localidad** (no nombre) y **sensores** (paso 1). | «gold.fields: maestro de campos (localidad, provincia, coordenadas, hectáreas y sensores).» |
| 6 | 6.4 | `gold.dq_run_metrics` «con totales y Data Quality Score»; el modelo tiene 5 tablas | También guarda `pct_utilizable` (paso 3). Faltan 3 tablas que existen: `gold.pipeline_layer_metrics`, `gold.etl_trace` y `gold.etl_trace_steps` (trazabilidad del dashboard «ETL paso a paso»). | Agregar `pct_utilizable` y las 3 tablas, o aclarar que el modelo muestra solo las principales. |
| 7 | 8.1, 10.1 y 7.1 | «Pandas / Polars»; «PostgreSQL: base de datos con las capas Bronze, Silver y Gold» (8.1); «creación de las capas en PostgreSQL» (EDT, paquete 5) | Se usa **Pandas + PyArrow**, sin Polars (D12). Bronze, Silver y Quarantine están en **Parquet**; solo Gold en PostgreSQL, como dice el propio 6.2. | «Pandas + PyArrow» y «Parquet para Bronze/Silver/Quarantine y PostgreSQL para Gold». |
| 8 | 4.2 | Se eliminaron RNF07 (Seguridad) y RNF08 (Rendimiento) | El código y el README los citan: `sql/99_app_users.sh`, `src/config.py` y `grafana/.../agro.yml` (RNF07), `src/main.py` (RNF08: «objetivo < 300 s»). Además el README presenta como metas «< 5 min» y «≥ 95 % de errores detectados», que ya no figuran en los OE. | **Volver a agregar RNF07 y RNF08** (la seguridad sigue implementada y es un requisito real), o actualizar el código y el README. Lo primero es menos trabajo y suma al documento. |

## 3. Inconsistencias internas del documento

1. **Nube sí o no.** 8.1 y 8.2 incluyen «Hosting cloud (VM + PostgreSQL), USD 100». Pero 6, 12.2 y R08 dicen que la POC corre local con Docker. El código no usa nube. **Opciones:** quitar la línea (el total pasa a USD 10.890 con contingencia) o justificar para qué sería la VM (por ejemplo, la demo).
2. **Herramientas «o».** 8.1 dice «Pytest (o Great Expectations)» y «Grafana o Power BI Desktop», pero la bitácora ya decidió Pytest y Grafana (6/10). Hay que dejar solo lo elegido.
3. **14 % y la distribución por tipo.** El 2.2 plantea 6 % suelo / 3 % duplicados / 3 % huecos / 2 % otros, y R04 dice que el simulador inyecta errores «de forma controlada (cerca del 14 %, según 2.2)». El simulador inyecta un 14 %, pero reparte los tipos de error al azar en partes iguales (`docs/revision/paso-2.md`). **Opciones:** aclararlo en 12.2 o implementar los pesos por tipo (propuesta en `paso-2.md`).
4. **200 sensores y 19.200 registros/día vs. simulador.** El simulador genera **una lectura por campo** (8 × 96 = 768/día), no una por sensor. Conviene decirlo en 11 (POC) o en 12.2 (limitaciones). La alternativa es implementar el simulador por sensor (propuesta en `paso-1.md`).
5. **Stakeholder con el nombre del docente.** En 5.3 y en la RACI, el patrocinador del cliente es «José Ramón Castiñeiras, Director General», el mismo nombre que figura como docente en la portada. Si es intencional, está bien. Si no, conviene usar otro nombre.
6. **Riesgos sin la poca experiencia del equipo.** El riesgo R03 de la v7 («poca experiencia con CI/CD y Parquet») ya no está. Es una decisión válida; solo verificar que fue a propósito.

## 4. Errores de tipeo

- 6 (intro): «y **pública** en PostgreSQL» → «publica».
- 6.1: «extrae de forma incremental, **válida** contra las reglas» → «valida».
- 4.1 RF05: «**losregistros**» → «los registros».
- 6.4: «fields» → «gold.fields».

## 5. Lo que coincide con el código (verificado)

- **Tabla de campos (2.1):** idéntica a `config/fields.yaml` (8 campos, coordenadas, hectáreas y sensores; total 20.000 ha y 200 sensores).
- **Reglas DQ01 a DQ12 (6.3):** umbrales iguales a `config/rules.yaml`, incluido DQ11 con 30/120 min.
- **Métricas:** DQ Score estricto (VALID / total) y % utilizable ((VALID + WARNING) / total), iguales a `src/validation/engine.py` y `gold.dq_run_metrics`.
- **Esquema Medallion (6.2):** Parquet para Bronze/Silver/Quarantine, Gold en PostgreSQL; Grafana con usuario de solo lectura.
- **`dq_errors.field_id` sin clave foránea:** es correcto, el esquema lo tiene así a propósito.
- **Tasa de error de 14 %:** igual a `config/pipeline.yaml` (STAGING y PROD; DEV usa 20 %).
- **Cuentas verificadas, todas correctas:**
  - 6 % / 3 % / 2 % de 19.200 = 1.152 / 576 / 384, y 14 % ≈ 2.688.
  - 19.200 × 365 ≈ 7 millones.
  - 20 mm × 400 ha = 80.000 m³.
  - Horas: 360 h.
  - Costos: USD 10.000 + 10 % = USD 11.000.
  - Facturación: 1.100 / 6.600 / 3.300.
  - Producción: USD 860/mes = USD 10.320/año.
  - Exposiciones de los riesgos R01 a R08.

## 6. Pendientes

1. **Sección 11 (POC): sigue «[Completar]».** Es lo más importante que falta. Se puede armar con material que ya existe:
   - la corrida real de `docs/revision/paso-6.md` (92 tests, 92 % de cobertura en validación, corrida en DEV);
   - el ejemplo de la humedad 135 % rechazada por DQ07;
   - el test de mutación del duplicado de `paso-4.md` («test que falla y luego pasa»);
   - las capturas de Grafana;
   - el simulador `docs/simulador_pipeline.html`.
2. **Nombre de la consultora en el repo:** el README y la descripción del dashboard `calidad-datos` todavía dicen «UnaCocuCha SRL». Si el nombre definitivo es **Datum Sur**, hay que actualizar el repo.
3. **Figuras:** la V2 tiene 9 imágenes. No pude verlas (extraje solo el texto). Revisar que el diagrama de arquitectura y el modelo de datos muestren los campos LIT-01 a LIT-08, `localidad` y `sensores`, y Parquet + PostgreSQL.
