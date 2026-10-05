# Diccionario de Datos: `agro_etl_trace_steps_gold`

**Capa:** `GOLD`  
**Dominio:** `agro` | **Entidad:** `etl_trace_steps`  
**Ubicación / Destino:** `postgres:gold.etl_trace_steps`  
**Última Catalogación:** `2026-10-05T22:33:54.479828+00:00`  

> Lo que le pasó a cada registro de muestra en cada uno de los 5 pasos del ETL.

## Definición de Columnas

| Columna | Tipo de Dato | Nulos observados | Ejemplo | Descripción |
|---|---|---|---|---|
| `trace_id` | `str` | No | `dbe6e15b-3` | Identificador del registro de muestra: <lote>-<n>. |
| `step` | `int64` | No | `4` | Paso del ETL: 1 Extracción, 2 Bronze, 3 Validación, 4 Silver/Quarantine, 5 Gold. |
| `orden` | `int64` | No | `2` | Orden del dato dentro del paso. |
| `dato` | `str` | No | `dq_status` | Qué se muestra (ej. «Temperatura», «DQ07 · Humedad ambiental entre 0% y 100%»). |
| `valor` | `str` | No | `WARNING` | Valor del dato en ese paso (texto). |
| `resultado` | `str` | Sí (70.55%) | `OK` | Solo en validación: OK, WARNING o REJECT. |
