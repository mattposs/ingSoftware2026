---
name: data-governance
description: Guía práctica y reutilizable para la catalogación de datasets, extracción automática de esquemas y generación de diccionarios de datos en pipelines Medallion.
---

# Guía Práctica de Catalogación de Datos (Data Cataloging)

Esta skill define el flujo de trabajo estándar, formatos y herramientas para **catalogar datasets** y **generar diccionarios de datos** en cada capa del pipeline (Bronze, Silver y Gold).

Catalogar un dataset consiste en registrar:
1. **Qué es y dónde reside:** Nombre, dominio, entidad, capa (Bronze/Silver/Gold) y ruta física o tabla SQL.
2. **Qué columnas contiene:** Nombre, tipo de dato técnico, si permite nulos (`nullable`) y valores de ejemplo.
3. **Qué significa cada dato:** Descripción funcional y significado de negocio de cada campo.

---

## 1. Flujo de Trabajo de Catalogación

```mermaid
flowchart LR
    Dataset[(Dataset Real<br/>Parquet / SQL / DF)] --> Extract[1. schema_extractor<br/>Extrae tipos, nulos y muestras]
    Extract --> Merge[2. catalog_manager<br/>Fusiona esquema con descripciones]
    Merge --> YamlFile[(catalog/{layer}/{entity}.yaml<br/>Catálogo en YAML)]
    YamlFile --> Export[3. dict_generator<br/>Exporta tabla Markdown]
    Export --> DocsFile[docs/data_dictionary/<br/>Diccionario de Datos legible]
```

### Principios del Catálogo:
* **Automatización del esquema:** Nunca escribir tipos de datos a mano; se extraen directamente de los datos reales para evitar inconsistencias.
* **Preservación de descripciones:** Si el esquema de un dataset cambia (nuevas columnas o cambios de tipo), el catalogador actualiza la firma técnica sin borrar las descripciones que el equipo ya redactó.
* **Dos formatos complementarios:**
  - **YAML (`catalog/`):** Estructurado y legible por máquinas para validaciones o herramientas externas.
  - **Markdown (`docs/data_dictionary/`):** Formateado en tablas para lectura humana en GitHub, wikis y documentación de entrega.

---

## 2. Estructura del Archivo de Catálogo (`.yaml`)

Cada dataset se representa en un archivo YAML bajo el siguiente estándar:

```yaml
dataset_name: telemetry_devices_silver
domain: telemetry
entity: devices
layer: silver
description: Mediciones telemétricas de sensores IoT depuradas y validadas.
location: storage/silver/telemetry/devices/
last_cataloged_at: "2026-03-30T14:40:00Z"
columns:
  - name: device_id
    data_type: object
    nullable: false
    sample_value: "SENSOR-001"
    description: "Identificador unívoco del hardware del sensor instalado en campo."
  - name: temperature
    data_type: float64
    nullable: true
    sample_value: "23.4"
    description: "Temperatura ambiental medida en grados Celsius."
  - name: event_time
    data_type: datetime64[ns, UTC]
    nullable: false
    sample_value: "2026-03-30 10:00:00+00:00"
    description: "Fecha y hora UTC en la que el sensor tomó la medición."
```

---

## 3. Convención de Ubicación de Archivos

```text
catalog/                                # Fuente de la verdad en YAML (Machine-readable)
├── bronze/{domain}_{entity}.yaml
├── silver/{domain}_{entity}.yaml
└── gold/{domain}_{entity}.yaml

docs/data_dictionary/                   # Diccionarios legibles en Markdown (Docs as Code)
├── bronze/{domain}_{entity}.md
├── silver/{domain}_{entity}.md
└── gold/{domain}_{entity}.md
```

---

## 4. Templates de Código Reutilizables

El código ejecutable se encuentra modularizado en archivos independientes dentro de `templates/`:

| Componente | Template | Descripción |
|---|---|---|
| **Extracción Técnica** | [schema_extractor.py](./templates/schema_extractor.py) | Extrae automáticamente nombres, tipos, nullabilidad y muestras desde un DataFrame o archivo Parquet. |
| **Gestor de Catálogo** | [catalog_manager.py](./templates/catalog_manager.py) | Crea o actualiza el archivo YAML del catálogo, preservando descripciones previas ante cambios de esquema. |
| **Generador de Diccionario** | [dict_generator.py](./templates/dict_generator.py) | Transforma el archivo YAML en una tabla Markdown limpia y profesional para la documentación. |

---

## 5. Guía Paso a Paso para Catalogar un Dataset

Cualquier dataset de Bronze, Silver o Gold se cataloga con este flujo en un script o notebook:

```python
from templates.schema_extractor import extract_from_parquet, extract_column_metadata
from templates.catalog_manager import CatalogManager
from templates.dict_generator import generate_data_dictionary_md

# Paso 1: Extraer firma técnica desde el Parquet (o desde un DataFrame con extract_column_metadata)
# Los archivos siguen la convención de la skill de-developer: clean_{batch_id}.parquet
from glob import glob
latest_clean = sorted(glob("storage/silver/telemetry/devices/year=*/month=*/clean_*.parquet"))[-1]
columns_info = extract_from_parquet(latest_clean)

# Paso 2: Redactar descripciones funcionales de las columnas
descriptions = {
    "device_id": "Identificador unívoco del sensor físico.",
    "temperature": "Temperatura ambiente registrada en grados Celsius.",
    "humidity": "Porcentaje relativo de humedad (0-100%).",
    "event_time": "Timestamp UTC de la captura."
}

# Paso 3: Registrar en el catálogo YAML (crea o actualiza)
catalog_mgr = CatalogManager(catalog_dir="catalog")
yaml_path = catalog_mgr.register_or_update_dataset(
    domain="telemetry",
    entity="devices",
    layer="silver",
    description="Lecturas de sensores IoT tras pasar por las reglas de Data Quality.",
    location="storage/silver/telemetry/devices/",
    columns_technical=columns_info,
    column_descriptions=descriptions
)

# Paso 4: Generar el Diccionario de Datos en Markdown para la documentación
generate_data_dictionary_md(yaml_path, output_docs_dir="docs/data_dictionary")
```

---

## 6. Checklist de Catalogación

Al crear o modificar un dataset en el pipeline:

- [ ] ¿Se extrajo el esquema técnico directamente de los datos reales con `schema_extractor`?
- [ ] ¿Se revisó `nullable`? Es lo observado en la muestra, no una restricción: en Silver puede figurar "No" aunque la columna admita nulos.
- [ ] ¿Todas las columnas relevantes tienen una descripción funcional clara de negocio?
- [ ] ¿Se especificó correctamente la capa (`bronze`, `silver`, `gold`) y la ubicación física o tabla?
- [ ] ¿Se guardó el archivo YAML en `catalog/{layer}/{domain}_{entity}.yaml`?
- [ ] ¿Se generó el diccionario Markdown en `docs/data_dictionary/{layer}/{domain}_{entity}.md`?
- [ ] ¿Ambos archivos (`.yaml` y `.md`) están commiteados en el repositorio Git?
