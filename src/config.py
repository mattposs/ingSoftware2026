"""
config.py
Carga de configuración versionada (config/*.yaml) y de credenciales por entorno (.env).
Las credenciales nunca se leen de archivos versionados (RNF07).

Entornos (APP_ENV): dev, staging y prod. Cada uno tiene su propia base de datos
(agro_<entorno>), su propio lake (storage/<entorno>/) y un archivo
config/environments/<entorno>.yaml que pisa los valores de config/pipeline.yaml.
Por defecto se usa dev: nunca se escribe en producción por accidente.
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
ENVIRONMENTS = ("dev", "staging", "prod")


def _load_yaml(name: str) -> dict[str, Any]:
    with open(CONFIG_DIR / name, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


@lru_cache
def load_rules() -> dict[str, Any]:
    return _load_yaml("rules.yaml")["rules"]


@lru_cache
def load_fields() -> list[dict[str, Any]]:
    return _load_yaml("fields.yaml")["fields"]


def current_env() -> str:
    load_dotenv(PROJECT_ROOT / ".env")           # propio de cada máquina (ignorado por Git)
    load_dotenv(PROJECT_ROOT / ".env.example")   # valores por defecto: no pisa lo ya definido
    env = os.getenv("APP_ENV", "dev").strip().lower()
    if env not in ENVIRONMENTS:
        raise ValueError(f"APP_ENV={env!r} no es válido. Opciones: {', '.join(ENVIRONMENTS)}")
    return env


def _deep_merge(base: dict, override: dict) -> dict:
    out = dict(base)
    for key, value in override.items():
        out[key] = _deep_merge(out[key], value) if isinstance(value, dict) and isinstance(out.get(key), dict) else value
    return out


@lru_cache
def _pipeline_for(env: str) -> dict[str, Any]:
    override = _load_yaml(f"environments/{env}.yaml")
    return {**_deep_merge(_load_yaml("pipeline.yaml"), override), "environment": env}


def load_pipeline(env: str | None = None) -> dict[str, Any]:
    """Configuración del pipeline para el entorno (base + override del entorno)."""
    return _pipeline_for(env or current_env())


@dataclass(frozen=True)
class Settings:
    environment: str
    database_url: str
    storage_path: Path


def get_settings() -> Settings:
    env = current_env()
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        user = os.getenv("PIPELINE_DB_USER", "pipeline")
        password = os.getenv("PIPELINE_DB_PASSWORD", "")
        host = os.getenv("POSTGRES_HOST", "localhost")
        port = os.getenv("POSTGRES_PORT", "5432")
        database_url = f"postgresql+psycopg://{user}:{password}@{host}:{port}/agro_{env}"

    storage = os.getenv("STORAGE_PATH")
    storage = Path(storage) if storage else Path(load_pipeline(env).get("storage_path", "storage")) / env
    if not storage.is_absolute():
        storage = PROJECT_ROOT / storage
    return Settings(environment=env, database_url=database_url, storage_path=storage)
