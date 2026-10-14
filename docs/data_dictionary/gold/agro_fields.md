# Diccionario de Datos: `agro_fields_gold`

**Capa:** `GOLD`  
**Dominio:** `agro` | **Entidad:** `fields`  
**Ubicación / Destino:** `postgres:gold.fields`  
**Última Catalogación:** `2026-10-14T01:02:00.759353+00:00`  

> Campos del cliente (fuente: config/fields.yaml).

## Definición de Columnas

| Columna | Tipo de Dato | Nulos observados | Ejemplo | Descripción |
|---|---|---|---|---|
| `field_id` | `str` | No | `LIT-01` | Identificador del campo del cliente (LIT-01 a LIT-08, ver gold.fields). |
| `localidad` | `str` | No | `Crespo` | Localidad donde está el campo. |
| `provincia` | `str` | No | `Entre Ríos` | Provincia donde está el campo. |
| `latitude` | `float64` | No | `-32.03` | Latitud de la estación del campo, en grados decimales. |
| `longitude` | `float64` | No | `-60.31` | Longitud de la estación del campo, en grados decimales. |
| `hectareas` | `int64` | No | `2200` | Superficie del campo en hectáreas. |
| `sensores` | `int64` | No | `24` | Cantidad de sensores IoT instalados en el campo. |
