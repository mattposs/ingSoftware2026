"""
catalog.py
Cataloga todos los datasets del pipeline (skill data-governance):
extrae el esquema real, lo fusiona con las descripciones de negocio en catalog/
y genera el diccionario de datos en docs/data_dictionary/.

    python -m src.governance.catalog   # requiere una corrida previa del pipeline
"""

import pandas as pd

from src.common import db, lake
from src.config import PROJECT_ROOT, get_settings, load_pipeline
from src.governance.catalog_manager import CatalogManager
from src.governance.dict_generator import generate_data_dictionary_md
from src.governance.schema_extractor import extract_column_metadata

LINEAGE = {
    "_batch_id": "Identificador UUID de la corrida que generó el registro (linaje).",
    "_ingested_at": "Instante UTC en que el registro se capturó desde la fuente (linaje).",
    "_source_system": "Conector que originó el registro: open_meteo o iot_simulator (linaje).",
    "_sim_injected_error": "Solo simulador: tipo de error inyectado a propósito, para medir la detección "
                           "de las reglas (meta SMART 95%). Vacío en datos sin error y en Open-Meteo.",
}

MEASUREMENTS = {
    "timestamp": "Fecha y hora de la medición. En Bronze es el texto crudo recibido; desde Silver, datetime UTC.",
    "field_id": "Identificador del campo del cliente (LIT-01 a LIT-08, ver gold.fields).",
    "latitude": "Latitud de la estación del campo, en grados decimales.",
    "longitude": "Longitud de la estación del campo, en grados decimales.",
    "temperature": "Temperatura del aire a 2 m, en °C.",
    "temperature_unit": "Unidad informada por la fuente para temperature (se espera °C, regla DQ06).",
    "humidity": "Humedad relativa ambiental, en % (0 a 100).",
    "humidity_unit": "Unidad informada por la fuente para humidity (se espera %, regla DQ06).",
    "soil_moisture": "Humedad volumétrica del suelo (0 a 7 cm), en m³/m³.",
    "soil_moisture_unit": "Unidad informada por la fuente para soil_moisture (se espera m³/m³, regla DQ06).",
    "precipitation": "Precipitación acumulada en el intervalo de la lectura, en mm.",
    "precipitation_unit": "Unidad informada por la fuente para precipitation (se espera mm, regla DQ06).",
    "wind_speed": "Velocidad del viento a 10 m, en km/h.",
    "wind_speed_unit": "Unidad informada por la fuente para wind_speed (se espera km/h, regla DQ06).",
    "source": "Fuente del dato: open_meteo (API horaria) o iot_simulator (estaciones cada 15 min).",
    "dq_status": "Resultado de Data Quality: VALID (sin hallazgos) o WARNING (publicable pero marcado para revisión).",
    "_dq_warnings": "Códigos de las reglas de warning que disparó el registro, separados por ';' (ej. DQ09;DQ11).",
    "_rejection_reasons": "Códigos de las reglas críticas que incumplió el registro, separados por ';' (ej. DQ05;DQ07).",
    "_rejected_at": "Instante UTC en que el registro fue enviado a quarantine.",
    **LINEAGE,
}

GOLD = {
    "fecha": "Día de las mediciones en hora local del negocio (America/Argentina/Buenos_Aires).",
    "fuente": "Fuente de las mediciones agregadas (open_meteo o iot_simulator).",
    "localidad": "Localidad donde está el campo.",
    "provincia": "Provincia donde está el campo.",
    "hectareas": "Superficie del campo en hectáreas.",
    "sensores": "Cantidad de sensores IoT instalados en el campo.",
    "temperatura_promedio": "Temperatura promedio del día, en °C, solo con registros VALID y WARNING.",
    "precipitacion_total": "Precipitación total del día, en mm.",
    "humedad_suelo_promedio": "Humedad del suelo promedio del día, en m³/m³.",
    "humedad_ambiental_promedio": "Humedad relativa ambiental promedio del día, en %.",
    "cantidad_mediciones": "Cantidad de registros publicados (VALID + WARNING) que componen el indicador.",
    "porcentaje_calidad": "Publicados / (publicados + rechazados atribuibles a ese día, campo y fuente) × 100.",
    "_updated_at": "Última vez que se recalculó la fila.",
    "run_start": "Inicio de la corrida (UTC).",
    "run_end": "Fin de la corrida (UTC); vacío si sigue en curso o falló antes de terminar.",
    "status": "Estado de la corrida: running, ok o failed.",
    "total": "Registros recibidos en el lote.",
    "valid": "Registros sin hallazgos.",
    "warning": "Registros publicados con al menos un warning.",
    "invalid": "Registros rechazados (enviados a quarantine).",
    "dq_score": "Data Quality Score = (valid + warning) / total × 100.",
    "error_id": "Identificador del hallazgo.",
    "detected_at": "Instante UTC en que se detectó el hallazgo.",
    "measured_at": "Fecha y hora de la medición afectada (vacío si el timestamp era inválido).",
    "variable": "Variable afectada (temperature, humidity, ...); vacío si la regla aplica al registro completo.",
    "rule_id": "Código de la regla incumplida (DQ01 a DQ12, ver config/rules.yaml).",
    "rule_type": "Tipo de regla: Completitud, Unicidad, Validez, Consistencia, Integridad o Anomalía.",
    "action": "REJECT (el registro fue a quarantine) o WARNING (publicado y marcado).",
    "severidad": "Criticidad de la regla: Crítica, Alta o Media.",
    "detalle": "Explicación legible del hallazgo.",
    "domain": "Dominio del pipeline (agro).",
    "entity": "Fuente a la que corresponde el watermark.",
    "watermark": "Fin de la última ventana extraída de la fuente (UTC). La próxima corrida pide (watermark, ahora].",
    "last_batch_id": "Corrida que movió el watermark por última vez.",
    "updated_at": "Última actualización del watermark.",
    "layer": "Capa del pipeline: bronze, silver, quarantine o gold.",
    "rows": "Registros que la capa procesó en el lote.",
    "location": "Dónde quedaron los datos: carpeta del lake o tabla de PostgreSQL.",
    "window_start": "Solo bronze: inicio (exclusivo) de la ventana incremental pedida a la fuente.",
    "window_end": "Solo bronze: fin de la ventana incremental (el nuevo watermark).",
    "started_at": "Inicio de la etapa (UTC).",
    "finished_at": "Fin de la etapa (UTC).",
    "trace_id": "Identificador del registro de muestra: <lote>-<n>.",
    "created_at": "Cuándo se guardó la traza.",
    "fecha_negocio": "Día de Gold (hora local) al que aporta el registro; vacío si fue rechazado.",
    "titulo": "Texto con el que se elige el registro en el dashboard «ETL paso a paso».",
    "step": "Paso del ETL: 1 Extracción, 2 Bronze, 3 Validación, 4 Silver/Quarantine, 5 Gold.",
    "orden": "Orden del dato dentro del paso.",
    "dato": "Qué se muestra (ej. «Temperatura», «DQ07 · Humedad ambiental entre 0% y 100%»).",
    "valor": "Valor del dato en ese paso (texto).",
    "resultado": "Solo en validación: OK, WARNING o REJECT.",
}

DESCRIPTIONS = {**MEASUREMENTS, **GOLD}


def _datasets(settings, cfg) -> list[dict]:
    base, domain, entity = settings.storage_path, cfg["domain"], cfg["entity"]
    sets = [
        {"layer": "bronze", "entity": "open_meteo",
         "description": "Lecturas horarias de Open-Meteo Historical Weather API tal como llegaron (append-only, sin correcciones).",
         "location": f"storage/{settings.environment}/bronze/{domain}/open_meteo/",
         "load": lambda: lake.read_layer(base, "bronze", domain, "open_meteo")},
        {"layer": "bronze", "entity": "iot_simulator",
         "description": "Lecturas de las estaciones IoT simuladas (una por campo, 8 campos) cada 15 minutos, "
                        "con errores inyectados (append-only).",
         "location": f"storage/{settings.environment}/bronze/{domain}/iot_simulator/",
         "load": lambda: lake.read_layer(base, "bronze", domain, "iot_simulator")},
        {"layer": "silver", "entity": entity,
         "description": "Mediciones tipadas y validadas con DQ01–DQ12: registros VALID y WARNING de ambas fuentes.",
         "location": f"storage/{settings.environment}/silver/{domain}/{entity}/",
         "load": lambda: lake.read_layer(base, "silver", domain, entity)},
        {"layer": "quarantine", "entity": entity,
         "description": "Registros rechazados (INVALID), sin modificar, con los motivos de rechazo.",
         "location": f"storage/{settings.environment}/quarantine/{domain}/{entity}/",
         "load": lambda: lake.read_layer(base, "quarantine", domain, entity)},
    ]
    engine = db.get_engine()
    tables = {
        "gold.fields": "Campos del cliente (fuente: config/fields.yaml).",
        "gold.daily_field_metrics": "Indicadores diarios por campo y fuente. Única tabla que consume el dashboard.",
        "gold.dq_run_metrics": "Resumen de cada corrida del pipeline y su Data Quality Score.",
        "gold.dq_errors": "Registro de hallazgos de Data Quality (rechazos y warnings) por registro, regla y variable.",
        "etl.watermarks": "Control de carga incremental: fin de la última ventana extraída por fuente.",
        "gold.pipeline_layer_metrics": "Qué hizo cada capa (bronze, silver, quarantine, gold) en cada lote: "
                                       "registros, duración y ventana incremental.",
        "gold.etl_trace": "Registros de muestra de cada lote (válidos, con warning y rechazados) para seguirlos "
                          "paso a paso.",
        "gold.etl_trace_steps": "Lo que le pasó a cada registro de muestra en cada uno de los 5 pasos del ETL.",
    }
    for table, desc in tables.items():
        schema, name = table.split(".")
        sets.append({"layer": schema, "entity": name, "description": desc, "location": f"postgres:{table}",
                     "load": lambda t=table: pd.read_sql(f"SELECT * FROM {t} LIMIT 5000", engine)})
    return sets


def main() -> None:
    settings, cfg = get_settings(), load_pipeline()
    catalog = CatalogManager(catalog_dir=str(PROJECT_ROOT / "catalog"))
    for ds in _datasets(settings, cfg):
        df = ds["load"]()
        if df.empty:
            print(f"[CATALOG] {ds['location']} vacío: se omite (correr el pipeline primero).")
            continue
        missing = [c for c in df.columns if c not in DESCRIPTIONS]
        if missing:
            print(f"[CATALOG] {ds['location']}: columnas sin descripción {missing}")
        path = catalog.register_or_update_dataset(
            domain=cfg["domain"], entity=ds["entity"], layer=ds["layer"],
            description=ds["description"], location=ds["location"],
            columns_technical=extract_column_metadata(df),
            column_descriptions={c: DESCRIPTIONS[c] for c in df.columns if c in DESCRIPTIONS},
        )
        generate_data_dictionary_md(path, output_docs_dir=str(PROJECT_ROOT / "docs" / "data_dictionary"))


if __name__ == "__main__":
    main()
