# Grafana: dashboards, paneles y consultas SQL (tomadas de grafana/dashboards/*.json)

## Calidad de datos agroclimáticos (`calidad-datos.json`, uid `agro-calidad`)

### Panel: DQ Score estricto (solo VALID) (stat)

```sql
SELECT dq_score AS "DQ Score estricto" FROM gold.dq_run_metrics WHERE status = 'ok' ORDER BY run_start DESC LIMIT 1
```

### Panel: % utilizable (VALID + WARNING) (stat)

```sql
SELECT pct_utilizable AS "% utilizable" FROM gold.dq_run_metrics WHERE status = 'ok' ORDER BY run_start DESC LIMIT 1
```

### Panel: Registros procesados (stat)

```sql
SELECT total FROM gold.dq_run_metrics WHERE status = 'ok' ORDER BY run_start DESC LIMIT 1
```

### Panel: ✔ VALID (stat)

```sql
SELECT valid FROM gold.dq_run_metrics WHERE status = 'ok' ORDER BY run_start DESC LIMIT 1
```

### Panel: ⚠ WARNING (stat)

```sql
SELECT warning FROM gold.dq_run_metrics WHERE status = 'ok' ORDER BY run_start DESC LIMIT 1
```

### Panel: ✖ INVALID (stat)

```sql
SELECT invalid FROM gold.dq_run_metrics WHERE status = 'ok' ORDER BY run_start DESC LIMIT 1
```

### Panel: Última corrida (stat)

```sql
SELECT extract(epoch FROM run_end) * 1000 AS "Última corrida" FROM gold.dq_run_metrics WHERE status = 'ok' ORDER BY run_start DESC LIMIT 1
```

### Panel: DQ Score estricto y % utilizable por corrida (timeseries)

```sql
SELECT run_start AS time, dq_score AS "DQ Score estricto (solo VALID)", pct_utilizable AS "% utilizable (VALID + WARNING)" FROM gold.dq_run_metrics WHERE status = 'ok' AND $__timeFilter(run_start) ORDER BY 1
```

### Panel: Hallazgos por regla (todas las fuentes) (barchart)

```sql
WITH reglas(rule_id) AS (SELECT 'DQ' || lpad(g::text, 2, '0') FROM generate_series(1, 12) g) SELECT r.rule_id AS "Regla", NULLIF(count(e.*) FILTER (WHERE e.action = 'REJECT'), 0) AS "Rechazos", NULLIF(count(e.*) FILTER (WHERE e.action = 'WARNING'), 0) AS "Warnings" FROM reglas r LEFT JOIN gold.dq_errors e ON e.rule_id = r.rule_id AND e._batch_id IN (SELECT _batch_id FROM gold.dq_run_metrics WHERE $__timeFilter(run_start)) GROUP BY 1 ORDER BY 1
```

### Panel: Temperatura promedio diaria (timeseries)

```sql
SELECT ((m.fecha + time '12:00') AT TIME ZONE 'America/Argentina/Buenos_Aires') AS time, f.field_id || ' · ' || f.localidad AS metric, m.temperatura_promedio AS value FROM gold.daily_field_metrics m JOIN gold.fields f USING (field_id) WHERE m.fuente = '$fuente' AND m.field_id IN ($campo) AND $__timeFilter(((m.fecha + time '12:00') AT TIME ZONE 'America/Argentina/Buenos_Aires')) ORDER BY 1, 2
```

### Panel: Humedad del suelo promedio diaria (timeseries)

```sql
SELECT ((m.fecha + time '12:00') AT TIME ZONE 'America/Argentina/Buenos_Aires') AS time, f.field_id || ' · ' || f.localidad AS metric, m.humedad_suelo_promedio AS value FROM gold.daily_field_metrics m JOIN gold.fields f USING (field_id) WHERE m.fuente = '$fuente' AND m.field_id IN ($campo) AND $__timeFilter(((m.fecha + time '12:00') AT TIME ZONE 'America/Argentina/Buenos_Aires')) ORDER BY 1, 2
```

### Panel: Campos del cliente (geomap)

```sql
SELECT f.localidad AS "Campo", f.provincia AS "Provincia", f.latitude::float AS latitude, f.longitude::float AS longitude, round(avg(m.porcentaje_calidad), 1)::float AS "Calidad (%)", sum(m.precipitacion_total)::float AS "Lluvia (mm)", round(avg(m.temperatura_promedio), 1)::float AS "Temp. media (°C)" FROM gold.fields f JOIN gold.daily_field_metrics m USING (field_id) WHERE m.fuente = '$fuente' AND m.field_id IN ($campo) AND $__timeFilter(((m.fecha + time '12:00') AT TIME ZONE 'America/Argentina/Buenos_Aires')) GROUP BY 1, 2, 3, 4
```

### Panel: Lluvia acumulada por campo (barchart)

```sql
SELECT f.field_id || ' · ' || f.localidad AS "Campo", sum(m.precipitacion_total) AS "Lluvia (mm)" FROM gold.daily_field_metrics m JOIN gold.fields f USING (field_id) WHERE m.fuente = '$fuente' AND m.field_id IN ($campo) AND $__timeFilter(((m.fecha + time '12:00') AT TIME ZONE 'America/Argentina/Buenos_Aires')) GROUP BY 1 ORDER BY 1
```

### Panel: % de calidad estricto por campo y día (solo VALID) (status-history)

```sql
SELECT ((m.fecha + time '12:00') AT TIME ZONE 'America/Argentina/Buenos_Aires') AS time, f.field_id || ' · ' || f.localidad AS metric, m.porcentaje_calidad AS value FROM gold.daily_field_metrics m JOIN gold.fields f USING (field_id) WHERE m.fuente = '$fuente' AND m.field_id IN ($campo) AND $__timeFilter(((m.fecha + time '12:00') AT TIME ZONE 'America/Argentina/Buenos_Aires')) ORDER BY 1, 2
```

### Panel: Últimos registros rechazados (table)

```sql
SELECT e.measured_at AS "Medición", e.field_id AS "Campo", e.source AS "Fuente", e.rule_id AS "Regla", coalesce(e.variable, '—') AS "Variable", e.detalle AS "Detalle" FROM gold.dq_errors e WHERE e.action = 'REJECT' ORDER BY e.detected_at DESC, e.error_id LIMIT 100
```

## ETL paso a paso (`etl-paso-a-paso.json`, uid `agro-paso-a-paso`)

### Panel: ¿Por dónde pasó el registro elegido? (nodeGraph)

```sql
SELECT 'fuente' AS id, '1 · EXTRACCIÓN' AS title, 'fuente' AS subtitle, (t.source) AS secondarystat, ('#898781') AS color FROM (SELECT * FROM gold.etl_trace WHERE trace_id = '$registro') t UNION ALL SELECT 'bronze' AS id, '2 · BRONZE' AS title, 'Parquet · crudo' AS subtitle, ('guardado') AS secondarystat, ('#d95926') AS color FROM (SELECT * FROM gold.etl_trace WHERE trace_id = '$registro') t UNION ALL SELECT 'reglas' AS id, '3 · VALIDACIÓN' AS title, 'reglas DQ01–DQ12' AS subtitle, (CASE t.dq_status WHEN 'VALID' THEN '✔ cumple' WHEN 'WARNING' THEN '⚠ warning' ELSE '✖ rechaza' END) AS secondarystat, ('#898781') AS color FROM (SELECT * FROM gold.etl_trace WHERE trace_id = '$registro') t UNION ALL SELECT 'silver' AS id, '4 · SILVER' AS title, 'Parquet · validado' AS subtitle, (CASE WHEN t.dq_status = 'INVALID' THEN 'no pasa' ELSE '✔ llega' END) AS secondarystat, (CASE WHEN t.dq_status = 'INVALID' THEN '#3a3d42' ELSE '#3987e5' END) AS color FROM (SELECT * FROM gold.etl_trace WHERE trace_id = '$registro') t UNION ALL SELECT 'quarantine' AS id, '4 · QUARANTINE' AS title, 'Parquet · rechazados' AS subtitle, (CASE WHEN t.dq_status = 'INVALID' THEN '✖ queda' ELSE 'no pasa' END) AS secondarystat, (CASE WHEN t.dq_status = 'INVALID' THEN '#d03b3b' ELSE '#3a3d42' END) AS color FROM (SELECT * FROM gold.etl_trace WHERE trace_id = '$registro') t UNION ALL SELECT 'gold' AS id, '5 · GOLD' AS title, 'PostgreSQL · indicadores' AS subtitle, (CASE WHEN t.dq_status = 'INVALID' THEN 'no llega' ELSE '✔ aporta' END) AS secondarystat, (CASE WHEN t.dq_status = 'INVALID' THEN '#3a3d42' ELSE '#c98500' END) AS color FROM (SELECT * FROM gold.etl_trace WHERE trace_id = '$registro') t
```

### Panel: ¿Por dónde pasó el registro elegido? (nodeGraph)

```sql
SELECT 'e1' AS id, 'fuente' AS source, 'bronze' AS target UNION ALL SELECT 'e2' AS id, 'bronze' AS source, 'reglas' AS target UNION ALL SELECT 'e3' AS id, 'reglas' AS source, 'silver' AS target UNION ALL SELECT 'e4' AS id, 'reglas' AS source, 'quarantine' AS target UNION ALL SELECT 'e5' AS id, 'silver' AS source, 'gold' AS target
```

### Panel: Resultado (stat)

```sql
SELECT dq_status FROM (SELECT * FROM gold.etl_trace WHERE trace_id = '$registro') t
```

### Panel: Fuente (stat)

```sql
SELECT source FROM (SELECT * FROM gold.etl_trace WHERE trace_id = '$registro') t
```

### Panel: Campo (stat)

```sql
SELECT coalesce(t.field_id || ' · ' || f.localidad, coalesce(t.field_id, '(sin campo)')) FROM (SELECT * FROM gold.etl_trace WHERE trace_id = '$registro') t LEFT JOIN gold.fields f USING (field_id)
```

### Panel: Momento de la medición (stat)

```sql
SELECT coalesce(to_char(measured_at AT TIME ZONE 'America/Argentina/Buenos_Aires', 'DD/MM/YYYY HH24:MI'), '(timestamp inválido)') FROM (SELECT * FROM gold.etl_trace WHERE trace_id = '$registro') t
```

### Panel:  (table)

```sql
SELECT dato AS "Dato", coalesce(valor, '—') AS "Valor" FROM gold.etl_trace_steps WHERE trace_id = '$registro' AND step = 1 ORDER BY orden
```

### Panel:  (table)

```sql
SELECT dato AS "Dato", coalesce(valor, '—') AS "Valor" FROM gold.etl_trace_steps WHERE trace_id = '$registro' AND step = 2 ORDER BY orden
```

### Panel:  (table)

```sql
SELECT resultado AS "Resultado", dato AS "Dato", coalesce(valor, '—') AS "Valor" FROM gold.etl_trace_steps WHERE trace_id = '$registro' AND step = 3 ORDER BY orden
```

### Panel:  (table)

```sql
SELECT dato AS "Dato", coalesce(valor, '—') AS "Valor" FROM gold.etl_trace_steps WHERE trace_id = '$registro' AND step = 4 ORDER BY orden
```

### Panel:  (table)

```sql
SELECT dato AS "Dato", coalesce(valor, '—') AS "Valor" FROM gold.etl_trace_steps WHERE trace_id = '$registro' AND step = 5 ORDER BY orden
```

## Flujo del ETL (Bronze · Silver · Gold) (`flujo-etl.json`, uid `agro-flujo`)

### Panel: Flujo Medallion: recorrido de los datos en el período (nodeGraph)

```sql
SELECT 'om' AS id, 'Open-Meteo' AS title, 'Fuente · API horaria' AS subtitle, to_char((SELECT coalesce(sum(rows), 0)::int FROM gold.pipeline_layer_metrics WHERE _batch_id IN (SELECT _batch_id FROM gold.dq_run_metrics WHERE status = 'ok' AND $__timeFilter(run_start)) AND layer = 'bronze' AND entity = 'open_meteo'), 'FM999G999G990') AS secondarystat, 'extraídos' AS detail__registros, '#898781' AS color, 'archive-api.open-meteo.com' AS detail__ubicacion, 'Datos meteorológicos reales de los 8 campos' AS detail__que_hace UNION ALL SELECT 'iot' AS id, 'Simulador IoT' AS title, 'Fuente · cada 15 min' AS subtitle, to_char((SELECT coalesce(sum(rows), 0)::int FROM gold.pipeline_layer_metrics WHERE _batch_id IN (SELECT _batch_id FROM gold.dq_run_metrics WHERE status = 'ok' AND $__timeFilter(run_start)) AND layer = 'bronze' AND entity = 'iot_simulator'), 'FM999G999G990') AS secondarystat, 'extraídos' AS detail__registros, '#898781' AS color, 'src/ingestion/iot_simulator.py' AS detail__ubicacion, 'Estaciones simuladas con ~8% de errores inyectados' AS detail__que_hace UNION ALL SELECT 'bronze' AS id, 'BRONZE' AS title, 'Parquet · crudo' AS subtitle, to_char((SELECT coalesce(sum(rows), 0)::int FROM gold.pipeline_layer_metrics WHERE _batch_id IN (SELECT _batch_id FROM gold.dq_run_metrics WHERE status = 'ok' AND $__timeFilter(run_start)) AND layer = 'bronze'), 'FM999G999G990') AS secondarystat, 'guardados' AS detail__registros, '#d95926' AS color, 'storage/bronze/' AS detail__ubicacion, 'Guarda el lote tal como llegó + linaje. Nunca se modifica' AS detail__que_hace UNION ALL SELECT 'reglas' AS id, 'Reglas DQ01–DQ12' AS title, 'Validación' AS subtitle, to_char((SELECT coalesce(sum(rows), 0)::int FROM gold.pipeline_layer_metrics WHERE _batch_id IN (SELECT _batch_id FROM gold.dq_run_metrics WHERE status = 'ok' AND $__timeFilter(run_start)) AND layer = 'bronze'), 'FM999G999G990') AS secondarystat, 'evaluados' AS detail__registros, '#898781' AS color, 'config/rules.yaml' AS detail__ubicacion, 'Tipa, deduplica y clasifica en VALID / WARNING / INVALID' AS detail__que_hace UNION ALL SELECT 'silver' AS id, 'SILVER' AS title, 'Parquet · validado' AS subtitle, to_char((SELECT coalesce(sum(rows), 0)::int FROM gold.pipeline_layer_metrics WHERE _batch_id IN (SELECT _batch_id FROM gold.dq_run_metrics WHERE status = 'ok' AND $__timeFilter(run_start)) AND layer = 'silver'), 'FM999G999G990') AS secondarystat, 'válidos' AS detail__registros, '#3987e5' AS color, 'storage/silver/' AS detail__ubicacion, 'Registros utilizables, tipados, con sus warnings' AS detail__que_hace UNION ALL SELECT 'quarantine' AS id, 'QUARANTINE' AS title, 'Parquet · rechazados' AS subtitle, to_char((SELECT coalesce(sum(rows), 0)::int FROM gold.pipeline_layer_metrics WHERE _batch_id IN (SELECT _batch_id FROM gold.dq_run_metrics WHERE status = 'ok' AND $__timeFilter(run_start)) AND layer = 'quarantine'), 'FM999G999G990') AS secondarystat, 'rechazados' AS detail__registros, '#d03b3b' AS color, 'storage/quarantine/' AS detail__ubicacion, 'Registros rechazados sin modificar + motivo de rechazo' AS detail__que_hace UNION ALL SELECT 'errores' AS id, 'gold.dq_errors' AS title, 'PostgreSQL · hallazgos' AS subtitle, to_char((SELECT count(*)::int FROM gold.dq_errors WHERE _batch_id IN (SELECT _batch_id FROM gold.dq_run_metrics WHERE status = 'ok' AND $__timeFilter(run_start))), 'FM999G999G990') AS secondarystat, 'hallazgos' AS detail__registros, '#c98500' AS color, 'postgres: gold.dq_errors' AS detail__ubicacion, 'Cada regla incumplida, con variable y severidad' AS detail__que_hace UNION ALL SELECT 'gold' AS id, 'GOLD' AS title, 'PostgreSQL · indicadores' AS subtitle, to_char((SELECT coalesce(sum(rows), 0)::int FROM gold.pipeline_layer_metrics WHERE _batch_id IN (SELECT _batch_id FROM gold.dq_run_metrics WHERE status = 'ok' AND $__timeFilter(run_start)) AND layer = 'gold'), 'FM999G999G990') AS secondarystat, 'filas' AS detail__registros, '#c98500' AS color, 'postgres: gold.daily_field_metrics' AS detail__ubicacion, 'Indicadores diarios recalculados para los días afectados' AS detail__que_hace UNION ALL SELECT 'dash' AS id, 'Dashboards' AS title, 'Grafana · solo Gold' AS subtitle, to_char((SELECT coalesce(sum(rows), 0)::int FROM gold.pipeline_layer_metrics WHERE _batch_id IN (SELECT _batch_id FROM gold.dq_run_metrics WHERE status = 'ok' AND $__timeFilter(run_start)) AND layer = 'gold'), 'FM999G999G990') AS secondarystat, 'filas leídas' AS detail__registros, '#898781' AS color, 'http://localhost:3000' AS detail__ubicacion, 'Lee únicamente tablas gold con un usuario de solo lectura' AS detail__que_hace
```

### Panel: Flujo Medallion: recorrido de los datos en el período (nodeGraph)

```sql
SELECT 'e1' AS id, 'om' AS source, 'bronze' AS target, (SELECT coalesce(sum(rows), 0)::int FROM gold.pipeline_layer_metrics WHERE _batch_id IN (SELECT _batch_id FROM gold.dq_run_metrics WHERE status = 'ok' AND $__timeFilter(run_start)) AND layer = 'bronze' AND entity = 'open_meteo') || ' registros' AS mainstat UNION ALL SELECT 'e2' AS id, 'iot' AS source, 'bronze' AS target, (SELECT coalesce(sum(rows), 0)::int FROM gold.pipeline_layer_metrics WHERE _batch_id IN (SELECT _batch_id FROM gold.dq_run_metrics WHERE status = 'ok' AND $__timeFilter(run_start)) AND layer = 'bronze' AND entity = 'iot_simulator') || ' registros' AS mainstat UNION ALL SELECT 'e3' AS id, 'bronze' AS source, 'reglas' AS target, (SELECT coalesce(sum(rows), 0)::int FROM gold.pipeline_layer_metrics WHERE _batch_id IN (SELECT _batch_id FROM gold.dq_run_metrics WHERE status = 'ok' AND $__timeFilter(run_start)) AND layer = 'bronze') || ' registros' AS mainstat UNION ALL SELECT 'e4' AS id, 'reglas' AS source, 'silver' AS target, (SELECT coalesce(sum(rows), 0)::int FROM gold.pipeline_layer_metrics WHERE _batch_id IN (SELECT _batch_id FROM gold.dq_run_metrics WHERE status = 'ok' AND $__timeFilter(run_start)) AND layer = 'silver') || ' válidos' AS mainstat UNION ALL SELECT 'e5' AS id, 'reglas' AS source, 'quarantine' AS target, (SELECT coalesce(sum(rows), 0)::int FROM gold.pipeline_layer_metrics WHERE _batch_id IN (SELECT _batch_id FROM gold.dq_run_metrics WHERE status = 'ok' AND $__timeFilter(run_start)) AND layer = 'quarantine') || ' rechazados' AS mainstat UNION ALL SELECT 'e6' AS id, 'reglas' AS source, 'errores' AS target, (SELECT count(*)::int FROM gold.dq_errors WHERE _batch_id IN (SELECT _batch_id FROM gold.dq_run_metrics WHERE status = 'ok' AND $__timeFilter(run_start))) || ' hallazgos' AS mainstat UNION ALL SELECT 'e7' AS id, 'silver' AS source, 'gold' AS target, (SELECT coalesce(sum(rows), 0)::int FROM gold.pipeline_layer_metrics WHERE _batch_id IN (SELECT _batch_id FROM gold.dq_run_metrics WHERE status = 'ok' AND $__timeFilter(run_start)) AND layer = 'gold') || ' filas (agregación diaria)' AS mainstat UNION ALL SELECT 'e8' AS id, 'gold' AS source, 'dash' AS target, '' || ' consulta' AS mainstat
```

### Panel: 🟠 Bronze · registros crudos (período) (stat)

```sql
SELECT (SELECT coalesce(sum(rows), 0)::int FROM gold.pipeline_layer_metrics WHERE _batch_id IN (SELECT _batch_id FROM gold.dq_run_metrics WHERE status = 'ok' AND $__timeFilter(run_start)) AND layer = 'bronze') AS v
```

### Panel: 🔵 Silver · válidos (período) (stat)

```sql
SELECT (SELECT coalesce(sum(rows), 0)::int FROM gold.pipeline_layer_metrics WHERE _batch_id IN (SELECT _batch_id FROM gold.dq_run_metrics WHERE status = 'ok' AND $__timeFilter(run_start)) AND layer = 'silver') AS v
```

### Panel: 🔴 Quarantine · rechazados (período) (stat)

```sql
SELECT (SELECT coalesce(sum(rows), 0)::int FROM gold.pipeline_layer_metrics WHERE _batch_id IN (SELECT _batch_id FROM gold.dq_run_metrics WHERE status = 'ok' AND $__timeFilter(run_start)) AND layer = 'quarantine') AS v
```

### Panel: 🟡 Gold · filas actualizadas (período) (stat)

```sql
SELECT (SELECT coalesce(sum(rows), 0)::int FROM gold.pipeline_layer_metrics WHERE _batch_id IN (SELECT _batch_id FROM gold.dq_run_metrics WHERE status = 'ok' AND $__timeFilter(run_start)) AND layer = 'gold') AS v
```

### Panel: ⏱ Duración del último lote (stat)

```sql
SELECT extract(epoch FROM (max(finished_at) - min(started_at))) AS v FROM gold.pipeline_layer_metrics WHERE _batch_id = (SELECT r._batch_id FROM gold.dq_run_metrics r WHERE r.status = 'ok' AND EXISTS (SELECT 1 FROM gold.pipeline_layer_metrics m WHERE m._batch_id = r._batch_id) ORDER BY r.run_start DESC LIMIT 1)
```

### Panel: Cómo se reparte cada lote de Bronze (timeseries)

```sql
SELECT r.run_start AS time, sum(m.rows) FILTER (WHERE m.layer = 'silver') AS "Silver (válidos)", sum(m.rows) FILTER (WHERE m.layer = 'quarantine') AS "Quarantine (rechazados)" FROM gold.pipeline_layer_metrics m JOIN gold.dq_run_metrics r USING (_batch_id) WHERE $__timeFilter(r.run_start) GROUP BY 1 ORDER BY 1
```

### Panel: Cuánto tarda cada etapa (timeseries)

```sql
SELECT r.run_start AS time, sum(extract(epoch FROM m.finished_at - m.started_at)) FILTER (WHERE m.layer = 'bronze') AS "Bronze (extracción)", sum(extract(epoch FROM m.finished_at - m.started_at)) FILTER (WHERE m.layer = 'silver') AS "Silver (validación)", sum(extract(epoch FROM m.finished_at - m.started_at)) FILTER (WHERE m.layer = 'gold') AS "Gold (carga)" FROM gold.pipeline_layer_metrics m JOIN gold.dq_run_metrics r USING (_batch_id) WHERE $__timeFilter(r.run_start) AND m.started_at IS NOT NULL GROUP BY 1 ORDER BY 1
```

### Panel: Ventanas incrementales por fuente (table)

```sql
SELECT m.entity AS "Fuente", m.window_start AS "Desde (exclusivo)", m.window_end AS "Hasta", m.rows AS "Registros", left(m._batch_id, 8) AS "Lote" FROM gold.pipeline_layer_metrics m JOIN gold.dq_run_metrics r USING (_batch_id) WHERE m.layer = 'bronze' ORDER BY r.run_start DESC, m.entity LIMIT 30
```

### Panel: Historial de lotes (table)

```sql
SELECT r.run_start AS "Inicio", sum(m.rows) FILTER (WHERE m.layer = 'bronze') AS "Bronze", sum(m.rows) FILTER (WHERE m.layer = 'silver') AS "Silver", sum(m.rows) FILTER (WHERE m.layer = 'quarantine') AS "Quarantine", sum(m.rows) FILTER (WHERE m.layer = 'gold') AS "Gold", r.dq_score AS "DQ Score (estricto)", r.pct_utilizable AS "% utilizable" FROM gold.dq_run_metrics r JOIN gold.pipeline_layer_metrics m USING (_batch_id) GROUP BY r._batch_id, r.run_start, r.dq_score, r.pct_utilizable, r.status ORDER BY r.run_start DESC LIMIT 30
```

## Esquemas usados por todas las consultas

gold
