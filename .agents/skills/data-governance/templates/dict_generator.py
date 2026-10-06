"""
dict_generator.py
Genera diccionarios de datos legibles en formato Markdown a partir de
los archivos de catálogo YAML.
"""

import os

import yaml


def _cell(value) -> str:
    """Texto seguro para una celda de tabla Markdown (sin pipes ni saltos de línea)."""
    return " ".join(str(value).split()).replace("|", "\\|")


def _code(value) -> str:
    """Valor en formato código; usa doble backtick si el valor contiene backticks."""
    text = _cell(value)
    return f"`` {text} ``" if "`" in text else f"`{text}`"


def generate_data_dictionary_md(catalog_yaml_path: str, output_docs_dir: str = "docs/data_dictionary") -> str:
    """
    Lee un archivo YAML de catálogo y produce un archivo Markdown con formato
    de tabla limpia y profesional para documentación del proyecto.
    """
    with open(catalog_yaml_path, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    dataset_name = data.get("dataset_name", "Dataset")
    domain = data.get("domain", "")
    entity = data.get("entity", "")
    layer = data.get("layer", "").upper()
    description = data.get("description", "")
    location = data.get("location", "")
    last_cataloged = data.get("last_cataloged_at", "N/D")
    columns = data.get("columns", [])

    lines = [
        f"# Diccionario de Datos: `{dataset_name}`",
        "",
        f"**Capa:** `{layer}`  ",
        f"**Dominio:** `{domain}` | **Entidad:** `{entity}`  ",
        f"**Ubicación / Destino:** `{location}`  ",
        f"**Última Catalogación:** `{last_cataloged}`  ",
        "",
        f"> {_cell(description)}",
        "",
        "## Definición de Columnas",
        "",
        "| Columna | Tipo de Dato | Nulos observados | Ejemplo | Descripción |",
        "|---|---|---|---|---|"
    ]

    for col in columns:
        pct = col.get("null_percentage")
        nullable_str = ("Sí" if col.get("nullable") else "No") + (f" ({pct}%)" if pct else "")
        sample = col.get("sample_value")
        sample_str = _code(sample) if sample not in (None, "") else "-"
        desc = _cell(col.get("description") or "-")

        lines.append(
            f"| `{col.get('name')}` | `{col.get('data_type')}` | {nullable_str} | {sample_str} | {desc} |"
        )

    md_content = "\n".join(lines) + "\n"

    target_dir = os.path.join(output_docs_dir, layer.lower())
    os.makedirs(target_dir, exist_ok=True)
    target_path = os.path.join(target_dir, f"{domain}_{entity}.md")

    with open(target_path, "w", encoding="utf-8") as f:
        f.write(md_content)

    print(f"[DOCS] Diccionario de datos generado en: {target_path}")
    return target_path
