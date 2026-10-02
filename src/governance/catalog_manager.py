# Copiado de la skill data-governance (.agents/skills/data-governance/templates/catalog_manager.py).
"""
catalog_manager.py
Crea y actualiza entradas de catálogo de datos en formato YAML.
Permite fusionar esquemas técnicos con descripciones de negocio preservando
las anotaciones previas en caso de cambios de esquema (Schema Drift).
"""

import os
from datetime import UTC, datetime
from typing import Any

import yaml


class CatalogManager:
    """Gestiona el catálogo de datasets en archivos YAML versionados."""

    def __init__(self, catalog_dir: str = "catalog"):
        self.catalog_dir = catalog_dir

    def get_catalog_path(self, layer: str, domain: str, entity: str) -> str:
        return os.path.join(self.catalog_dir, layer.lower(), f"{domain}_{entity}.yaml")

    def register_or_update_dataset(
        self,
        domain: str,
        entity: str,
        layer: str,
        description: str,
        location: str,  # ej. "storage/silver/iot/weather/" o "postgres:gold.daily_weather"
        columns_technical: list[dict[str, Any]],
        column_descriptions: dict[str, str] | None = None
    ) -> str:
        """
        Registra un dataset o actualiza sus columnas preservando descripciones previas.
        Las columnas que desaparecieron del dataset se informan por consola.
        """
        column_descriptions = column_descriptions or {}
        file_path = self.get_catalog_path(layer, domain, entity)
        os.makedirs(os.path.dirname(file_path), exist_ok=True)

        existing_data = {}
        existing_col_descriptions = {}

        # 1. Si ya existe, conservar descripciones existentes
        if os.path.exists(file_path):
            with open(file_path, encoding="utf-8") as f:
                existing_data = yaml.safe_load(f) or {}
            for col in existing_data.get("columns", []):
                if col.get("description") and col["description"] != "Sin descripción.":
                    existing_col_descriptions[col["name"]] = col["description"]

        # 2. Construir lista actualizada de columnas
        merged_columns = []
        for tech_col in columns_technical:
            col_name = tech_col["name"]
            # Prioridad de descripción: nueva pasada > existente previa > por defecto
            desc = column_descriptions.get(
                col_name,
                existing_col_descriptions.get(col_name, "Sin descripción.")
            )

            merged_columns.append({
                "name": col_name,
                "data_type": tech_col["data_type"],
                "nullable": tech_col["nullable"],
                "null_percentage": tech_col.get("null_percentage"),
                "sample_value": tech_col.get("sample_value"),
                "description": desc
            })

        removed = set(existing_col_descriptions) - {c["name"] for c in columns_technical}
        if removed:
            print(f"[CATALOG] Columnas que ya no existen en el dataset: {sorted(removed)}")

        # 3. Armar documento de catálogo
        catalog_entry = {
            "dataset_name": f"{domain}_{entity}_{layer}",
            "domain": domain,
            "entity": entity,
            "layer": layer.lower(),
            "description": description or existing_data.get("description", "Dataset de pipeline."),
            "location": location,
            "last_cataloged_at": datetime.now(UTC).isoformat(),
            "columns": merged_columns
        }

        with open(file_path, "w", encoding="utf-8") as f:
            yaml.dump(catalog_entry, f, allow_unicode=True, sort_keys=False, indent=2)

        print(f"[CATALOG] Dataset catalogado con éxito en: {file_path}")
        return file_path
