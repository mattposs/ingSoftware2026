---
name: simulador-pipeline
description: Crea o actualiza un simulador HTML interactivo, estilo Cisco Packet Tracer, que enseña paso a paso cómo funciona un pipeline de datos (fuentes, código de procesamiento, capas Medallion Bronze/Silver/Gold/Quarantine, consumo) y cómo se levanta con Docker Compose. Usar siempre que se pida un HTML, demo, simulación, diagrama interactivo o material para alumnos que explique el pipeline, el ETL, las capas Medallion, Docker o docker-compose de este repo, o cuando cambie algo del pipeline (campos, reglas, contenedores, tablas) y haya que actualizar docs/simulador_pipeline.html.
---

# Simulador del pipeline (estilo Packet Tracer)

Esta skill produce y mantiene `docs/simulador_pipeline.html`: una sola página HTML, sin dependencias externas, que se abre con doble clic y muestra el pipeline como una red de Packet Tracer. Un "paquete" (una lectura de un sensor) viaja por los bloques y en cada evento se explica qué pasa, en qué archivo y qué hace Docker.

La plantilla completa y probada está en [`templates/simulador_pipeline.html`](templates/simulador_pipeline.html). **Partí siempre de ella** y cambiá los datos; no la reescribas desde cero. La guía para docentes y alumnos está en [`docs/simulador_pipeline.md`](../../../docs/simulador_pipeline.md).

## Principio de diseño: separar origen, procesamiento y almacenamiento

La primera versión mezclaba en un mismo recuadro bloques de código y capas de datos, y los alumnos no la entendían. Lo que funcionó es ordenar el diagrama **por rol**, en franjas horizontales que se leen de arriba hacia abajo:

| Franja | Qué va | Color (`cat`) | Ejemplos |
|---|---|---|---|
| 1 · ORIGEN | De dónde vienen los datos. El pipeline no las controla. | verde (`fuente`) | Open-Meteo API, sensores IoT |
| 2 · PROCESAMIENTO | Bloques de código que leen, validan y transforman. No guardan nada. | azul (`codigo`) | Scheduler, Extracción, Validación, Transformación Gold |
| 3 · ALMACENAMIENTO (destino) | Dónde quedan los datos: capas Medallion. | marrón (`alm`) | Bronze → Silver → Gold, Quarantine abajo, watermarks |
| 5 · CONSUMO (columna derecha) | Quién usa el resultado. | violeta (`consumo`) | Grafana, navegador |
| 4 · INFRAESTRUCTURA | Cómo se construye y se ejecuta. | gris (`infra`) | GitHub, CI/CD, imagen Docker, config, volumen, compose |

Reglas que hacen que se entienda:

- **Cada bloque de código queda arriba de lo que escribe.** Extracción arriba de Bronze, Validación arriba de Silver y Transformación Gold arriba de Gold. El dato hace zigzag: baja a guardarse y sube a procesarse. Así se ve que el código lee y escribe almacenamiento.
- **Las capas Medallion van en una sola fila, de izquierda a derecha:** Bronze → Silver → Gold. Quarantine va **debajo**, como el desvío de los rechazados.
- **Cada flecha lleva un verbo:** "escribe", "lee el lote", "escribe válidos", "escribe rechazados", "upsert SQL" o "consulta SQL". La flecha indica el sentido del dato.
- **Cada bloque tiene tres etiquetas:** arriba su rol ("CÓDIGO · PASO 2", "CAPA SILVER · LIMPIO"), abajo qué es (`run_silver()`) y **dónde corre o vive** ("🐳 contenedor scheduler", "📁 carpeta ./storage", "🐳 postgres · pgdata").
- **Docker no se mezcla con los roles.** El estado de los contenedores va en un panel propio (arriba a la derecha) y cada evento tiene una nota "🐳 En Docker". Dibujar los contenedores como recuadros que contienen bloques fue lo que confundió en la primera versión.
- **Las sub-zonas de almacenamiento dicen dónde están físicamente las capas.** Por ejemplo: "Lake Parquet · carpeta ./storage" y "PostgreSQL".

## Estructura de la plantilla

Todo vive en dos `<script>`:

1. **`<script id="logic">` es lógica pura, sin DOM**, y se puede probar con Node:
   - `FIELD_IDS`, `REF_NOW`, `RULE_NAMES`.
   - `evalRules(r)` evalúa DQ01–DQ12 sobre un registro con los umbrales de `config/rules.yaml`. `classify(rules)` devuelve VALID, WARNING o INVALID.
   - `goldImpact(status)` es el ejemplo del % de calidad diario estricto.
   - `buildRun(pdu)` arma los eventos del modo 3 (viaje de un registro). Hay 15 y se ramifican según el veredicto: Silver o Quarantine.
   - `DOCKER_STEPS` tiene los eventos del modo 1 (`docker compose up -d --build`, en el orden real). `PROJECT_STEPS` tiene los del modo 2 (Git, CI/CD, catálogo).
   - Al final exporta con `module.exports` cuando corre en Node.
2. **`<script id="app">` es la interfaz:**
   - `PDUS` son los paquetes de ejemplo.
   - `DEVICES` son los bloques. Cada uno tiene `x`, `y`, `cat`, `cap`, `type` (ícono), `label`, `sub`, `run` y `ct` (contenedor Docker).
   - `BANDS`, `ZONES` y `LINKS` definen las franjas, las sub-zonas y los enlaces. Un enlace tiene `a→b` = sentido del dato, más `label`, `ctl` (punteado), `both` (doble flecha), `via` (puntos intermedios) y `lp` (posición de la etiqueta).
   - `CONTAINERS` guarda la ficha técnica de cada contenedor, copiada de `docker-compose.yml`.
   - `INFO` tiene el contenido de la ventana de cada bloque (Resumen, Archivos, Código, CLI).
   - `YML_ANN`, `DF_ANN` y `CMDS` son el `docker-compose.yml` y el `Dockerfile` explicados línea por línea, y los comandos Docker.

Cada evento (paso) tiene esta forma:

```js
{from:"extract", to:"bronze", type:"Escritura", status:"OK|WARNING|REJECT",
 title:"...", text:"qué pasa", docker:"nota HTML opcional", file:"archivo real",
 code:"fragmento", record:"raw|bronze|final|silver|quarantine",   // solo modo 3
 rules:[...],                                                      // solo tandas de validación
 on:["id", ...], frames:{postgres:"starting|healthy|running"}}     // solo modos 1 y 2
```

## Cómo actualizarlo cuando cambia el pipeline

1. **Leé las fuentes reales antes de escribir:** `config/fields.yaml`, `config/rules.yaml`, `config/pipeline.yaml`, `config/environments/`, `docker-compose.yml`, `Dockerfile`, `sql/` y `src/pipeline.py`. **Solo escribí lo que esté en esos archivos.** Si algo no se puede verificar, no lo pongas. Lo mismo vale si es simulado: hay que decirlo ("FUENTE SIMULADA", "el simulador genera una lectura por campo").
2. **Datos que suelen cambiar y dónde tocarlos:**
   - **Campos:** `FIELD_IDS`, los `PDUS` y los textos de `iot` / `cfg`.
   - **Umbrales de reglas:** `evalRules` y `RULE_NAMES`.
   - **Contenedores, puertos o volúmenes:** `CONTAINERS`, `YML_ANN`, `DOCKER_STEPS` y el panel `dockerPanel`.
   - **Salidas reales de consola** (pestaña CLI y eventos "Primera corrida"): pegá logs de una corrida real, no inventados.
3. **Si agregás un bloque:** elegí su franja según el rol, no según el contenedor. Usá una separación de ≥ 200 px entre centros en la misma fila. La caja mide 150 × 128 y las franjas tienen la altura justa para una fila (la de almacenamiento tiene dos). Si un enlace cruza otro bloque, usá `via`. Si su etiqueta choca, usá `lp`. Las etiquetas de los enlaces entre franjas van en el hueco debajo de la fila de código (y ≈ 399).
4. **Mantené los tres modos, en este orden de pestañas:** 1 · Docker Compose (el que se abre por defecto), 2 · Proyecto completo y 3 · Viaje de un registro. Mantené también que cada evento de los modos 1 y 2 encienda (`on`) lo que corresponde.

## Cómo verificarlo (no lo des por terminado sin esto)

1. **Sintaxis y lógica:** extraé el contenido de `<script id="logic">` a un `.js`, cargalo con `require` y probá `evalRules` con casos conocidos. Por ejemplo: humedad 135 → INVALID por DQ07; temperatura 46 → WARNING por DQ09; duplicado → INVALID por DQ05; unidad °F → INVALID por DQ06. Comprobá también que todos los `from`, `to` y `on` de los eventos existan en `DEVICES`. Para la sintaxis de los dos scripts juntos: `node --check`.
2. **Prueba de interacción:** corré `node templates/smoke_test.js docs/simulador_pipeline.html` (necesita `npm install jsdom` en una carpeta temporal). Recorre los 3 modos, todos los paquetes, todas las ventanas y el formulario, y tiene que terminar en `ERRORES: ninguno`.
3. **Mirar cómo se ve:** sacá capturas con Edge o Chrome en modo headless, inyectando antes de `</body>` un script que avance algunos eventos, y miralas. Algunos detalles del entorno:
   - **Edge headless a veces se cuelga en Windows.** Usá `timeout 45`, un `--user-data-dir` distinto por captura, `taskkill //F //IM msedge.exe` después de cada una, y corrélo en segundo plano.
   - Buscá textos encimados (etiquetas de enlaces sobre títulos de franjas), títulos tapados por cajas y flechas que atraviesen bloques.
4. **La animación del paquete no se ve en una captura.** Avisale al usuario que la pruebe en el navegador.

## Errores que ya cometimos (evitalos)

- **Recuadros de contenedor que contienen bloques de distinto rol:** el diagrama no se entendía. Hay que ordenar por rol y mostrar Docker aparte.
- **Etiquetas de enlaces en el punto medio de la línea:** caían justo sobre el título de la franja siguiente. Hay que posicionarlas con `lp`.
- **Títulos de contenedor tapados** por la primera fila de cajas: hay que dejar al menos 60 px libres arriba.
- **Afirmar números que no salieron de una corrida real**, por ejemplo cantidades de registros. Hay que copiarlos de la consola o de `docs/revision/`.
