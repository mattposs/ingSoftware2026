"""
config.py
Carga de configuración versionada (config/*.yaml) y de credenciales por entorno (.env).
Las credenciales nunca se leen de archivos versionados (RNF07).
"""

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = Path(os.getenv("PIPELINE_CONFIG_DIR", PROJECT_ROOT / "config"))

MEASUREMENT_VARIABLES = ["temperature", "humidity", "soil_moisture", "precipitation", "wind_speed"]


def _load_yaml(name: str) -> dict[str, Any]:
    with open(CONFIG_DIR / name, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


@lru_cache
def load_rules() -> dict[str, Any]:
    return _load_yaml("rules.yaml")["rules"]


@lru_cache
def load_fields() -> list[dict[str, Any]]:
    return _load_yaml("fields.yaml")["fields"]


@lru_cache
def load_pipeline() -> dict[str, Any]:
    return _load_yaml("pipeline.yaml")


@dataclass(frozen=True)
class Settings:
    database_url: str
    storage_path: Path


def get_settings() -> Settings:
    load_dotenv(PROJECT_ROOT / ".env")
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        user = os.getenv("PIPELINE_DB_USER", "pipeline")
        password = os.getenv("PIPELINE_DB_PASSWORD", "")
        host = os.getenv("POSTGRES_HOST", "localhost")
        port = os.getenv("POSTGRES_PORT", "5432")
        db = os.getenv("POSTGRES_DB", "agro")
        database_url = f"postgresql+psycopg://{user}:{password}@{host}:{port}/{db}"

    storage = Path(os.getenv("STORAGE_PATH", load_pipeline().get("storage_path", "storage")))
    if not storage.is_absolute():
        storage = PROJECT_ROOT / storage
    return Settings(database_url=database_url, storage_path=storage)
