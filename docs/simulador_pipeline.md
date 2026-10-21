# Simulador del pipeline · guía de uso

[`simulador_pipeline.html`](simulador_pipeline.html) es una página interactiva, al estilo de Cisco Packet Tracer, que muestra cómo funciona el pipeline de datos de punta a punta. Se puede seguir un dato real desde que llega de un sensor hasta que aparece en el dashboard, y ver cómo Docker Compose levanta todo.

- **Cómo se abre:** con doble clic, en cualquier navegador moderno. No necesita internet, Docker ni instalar nada.
- **Público:** alumnos y docentes que quieran entender el proyecto sin leer el código.
- **Cómo se actualiza:** con la skill [`.agents/skills/simulador-pipeline`](../.agents/skills/simulador-pipeline/SKILL.md).

## Cómo leer el diagrama

El diagrama está ordenado **por rol**, en franjas de arriba hacia abajo:

| Franja | Color | Qué representa | Bloques |
|---|---|---|---|
| **1 · Origen** | Verde | De dónde vienen los datos. El pipeline no controla las fuentes: solo las lee. | Open-Meteo API (datos reales), Sensores IoT (simulados) |
| **2 · Procesamiento** | Azul | El código Python que lee, valida y transforma. No guarda nada por sí mismo: escribe en el almacenamiento. | Scheduler, Extracción (`run_bronze`), Validación (`run_silver`, 12 reglas), Transformación Gold (`run_gold`) |
| **3 · Almacenamiento (destino)** | Marrón | Dónde quedan los datos, en capas Medallion. | **Bronze** (crudo) → **Silver** (limpio) → **Gold** (negocio). **Quarantine** guarda los rechazados. `etl.watermarks` recuerda hasta dónde se leyó. |
| **Consumo** | Violeta | Quién usa el resultado. | Grafana (3 dashboards) y el navegador |
| **4 · Infraestructura** | Gris | Cómo se construye y se ejecuta. | GitHub, CI/CD, imagen Docker, `config/`, volumen `pgdata`, `docker-compose.yml` |

Para leerlo:

- **Flechas:** muestran hacia dónde va el dato y llevan un verbo, por ejemplo "escribe", "lee el lote", "escribe rechazados" o "consulta SQL". Las líneas punteadas son de control o de construcción.
- **Zigzag:** cada bloque de código está arriba de lo que escribe. El dato baja para guardarse y sube para procesarse.
- **Etiquetas de cada bloque:** arriba su **rol**, abajo **qué es** y **dónde corre o vive**. Por ejemplo, "🐳 contenedor scheduler" o "📁 carpeta ./storage".
- **Contenedores Docker:** el panel de arriba a la derecha muestra su estado ("detenido", "arrancando", "healthy", "en ejecución"). Con un clic se abre la ficha de cada uno.

## Los tres modos

### 1 · Viaje de un registro

Se elige un **paquete** (una lectura de un sensor) y se sigue en 15 eventos:

1. El Scheduler dispara la corrida (cada 15 minutos).
2. La Extracción pide y recibe el watermark: hasta dónde se leyó.
3. Llega la lectura desde la fuente.
4. La Extracción la **escribe en Bronze** tal como llegó, con linaje.
5. La Validación **lee el lote** y aplica las 12 reglas en tres tandas: identificación, valores y secuencia.
6. Veredicto: VALID, WARNING o INVALID.
7. Si es válido, se **escribe en Silver**. Si no, se **escribe en Quarantine** con el motivo.
8. La Transformación Gold **lee** Silver (y cuenta los rechazos) y **escribe en Gold** con upsert.
9. Grafana **consulta Gold** y el alumno lo ve en el navegador.

Paquetes de ejemplo:

| Paquete | Resultado | Qué enseña |
|---|---|---|
| Lectura válida | VALID | El camino feliz hasta Gold |
| Temperatura 46 °C | WARNING (DQ09) | Se publica con aviso, pero no cuenta en el score estricto |
| Humedad 135 % | INVALID (DQ07) | Un rechazo en una sola variable invalida el registro completo |
| Duplicado de precipitación | INVALID (DQ05) | El duplicado no se suma y va a Quarantine |
| Open-Meteo | VALID | La fuente real, que llega por Internet |

Con **＋ Crear paquete propio** los alumnos cambian los valores y ven qué regla lo frena.

### 2 · Docker Compose paso a paso

Todo arranca apagado. En 12 eventos se ve qué hace `docker compose up -d --build`, en el orden real:

1. Lee `docker-compose.yml` y las variables de `.env.example` / `.env`.
2. Construye la imagen `agro-pipeline` con el `Dockerfile`.
3. Descarga `postgres:16` y `grafana/grafana-oss:11.4.0`.
4. Crea la red interna y los volúmenes (`pgdata`, `grafana-data`).
5. Arranca `postgres`, que ejecuta los scripts de `sql/` solo la primera vez.
6. Espera el **healthcheck** (`pg_isready`).
7. Arranca los tres schedulers: dev, staging y prod.
8. Arranca Grafana y publica el puerto 3000.
9. Hace la primera corrida.
10. Muestra el `docker compose ps`.
11. Explica por qué hay que reconstruir la imagen si cambia `config/` o `src/`.
12. Explica la diferencia entre `stop`, `down` y `down -v`.

### 3 · Proyecto completo

Git, configuración versionada, CI (ruff, tests, cobertura), publicación de imágenes por rama, flujo de Pull Requests, catálogo de datos y verificación final.

## Controles

| Control | Qué hace |
|---|---|
| **⏭ Capturar / Avanzar** (o flecha →) | Avanza un evento |
| **◀ Atrás** (o flecha ←) | Retrocede un evento |
| **▶ Auto** | Reproduce solo; la velocidad se ajusta con el control deslizante |
| **⏮ Reiniciar** | Vuelve al inicio del modo |
| Clic en un evento de la lista | Salta a ese evento |
| Clic en un bloque | Abre su ventana: Resumen, Archivos, Código, CLI y, si corre en Docker, su contenedor |
| **docker-compose.yml explicado** | El archivo real, línea por línea |
| **Dockerfile explicado** | El Dockerfile real, línea por línea |
| **Comandos Docker** | Los comandos que más se usan y qué hacen |

En el panel **Información del evento** se ve, para cada paso:
- el movimiento, con colores (por ejemplo "Código: Extracción → Almacenamiento: Bronze · escribe");
- la explicación;
- la nota "🐳 En Docker";
- el archivo del repositorio;
- y el registro tal como queda en esa capa.

## Recorrido sugerido para una clase (unos 20 minutos)

1. **Orientación (3 min).** Mostrar las franjas: origen, procesamiento, almacenamiento. Remarcar que el código no guarda nada por sí mismo: escribe en una capa.
2. **Camino feliz (5 min).** Modo 1 con el paquete "Lectura válida", avanzando de a un evento. Detenerse en Bronze (linaje, inmutable) y en Gold (upsert).
3. **Un rechazo (4 min).** Repetir con "Humedad 135 %". Ver la tabla de reglas en la tanda 2 y el desvío a Quarantine. Preguntar por qué las otras cuatro variables, que estaban bien, tampoco llegan a Gold.
4. **Que los alumnos prueben (3 min).** "Crear paquete propio" con una temperatura de 50 °C, una unidad °F o un campo inexistente.
5. **Docker (5 min).** Modo 2. Detenerse en el healthcheck (por qué los schedulers esperan) y en el evento 11 (por qué hay que reconstruir la imagen). Abrir "docker-compose.yml explicado".

## Qué es simulado y qué es real

- **Los nombres y la configuración son reales.** Los archivos, funciones, reglas, umbrales, contenedores, puertos y volúmenes salen del repositorio.
- **Las salidas de consola son reales.** Las de la pestaña CLI y las del evento "Primera corrida" son corridas del proyecto.
- **Los paquetes de ejemplo son inventados**, con valores elegidos para mostrar cada regla. La fecha de referencia de la demo está fija en 2026-10-19 15:00 UTC.
- **La página no se conecta a la base ni a Docker.** Es una simulación didáctica: no muestra datos en vivo.
- **El simulador del proyecto genera una lectura por campo** (8 × 96 = 768 por día), no una por sensor. El cliente tiene 200 sensores y 19.200 registros por día. La página lo aclara en el bloque "Sensores IoT".
