# Diccionario de Datos: `agro_etl_trace_steps_gold`

**Capa:** `GOLD`  
**Dominio:** `agro` | **Entidad:** `etl_trace_steps`  
**Ubicación / Destino:** `postgres:gold.etl_trace_steps`  
**Última Catalogación:** `2026-10-14T01:02:01.464145+00:00`  

> Lo que le pasó a cada registro de muestra en cada uno de los 5 pasos del ETL.

## Definición de Columnas

| Columna | Tipo de Dato | Nulos observados | Ejemplo | Descripción |
|---|---|---|---|---|
| `trace_id` | `str` | No | `9b1c8b81-1` | Identificador del registro de muestra: <lote>-<n>. |
| `step` | `int64` | No | `1` | Paso del ETL: 1 Extracción, 2 Bronze, 3 Validación, 4 Silver/Quarantine, 5 Gold. |
| `orden` | `int64` | No | `1` | Orden del dato dentro del paso. |
| `dato` | `str` | No | `Fuente` | Qué se muestra (ej. «Temperatura», «DQ07 · Humedad ambiental entre 0% y 100%»). |
| `valor` | `str` | No | `open_meteo` | Valor del dato en ese paso (texto). |
| `resultado` | `str` | Sí (69.75%) | `OK` | Solo en validación: OK, WARNING o REJECT. |
