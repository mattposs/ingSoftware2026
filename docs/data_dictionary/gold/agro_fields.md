# Diccionario de Datos: `agro_fields_gold`

**Capa:** `GOLD`  
**Dominio:** `agro` | **Entidad:** `fields`  
**Ubicación / Destino:** `postgres:gold.fields`  
**Última Catalogación:** `2026-10-02T22:15:41.133264+00:00`  

> Campos del cliente (fuente: config/fields.yaml).

## Definición de Columnas

| Columna | Tipo de Dato | Nulos observados | Ejemplo | Descripción |
|---|---|---|---|---|
| `field_id` | `str` | No | `C01` | Identificador del campo del cliente (C01 a C06, ver gold.fields). |
| `nombre` | `str` | No | `La Aurora` | Nombre del campo. |
| `provincia` | `str` | No | `Buenos Aires` | Provincia donde está el campo. |
| `latitude` | `float64` | No | `-34.05` | Latitud de la estación del campo, en grados decimales. |
| `longitude` | `float64` | No | `-60.55` | Longitud de la estación del campo, en grados decimales. |
| `hectareas` | `int64` | No | `3200` | Superficie del campo en hectáreas. |
