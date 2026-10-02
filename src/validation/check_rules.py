"""
check_rules.py
Valida la estructura de config/rules.yaml y config/fields.yaml (paso de CI).
Detecta umbrales mal escritos antes de que lleguen al pipeline.

    python -m src.validation.check_rules
"""

import sys

from src.config import MEASUREMENT_VARIABLES, load_fields, load_rules

EXPECTED_RULES = [f"DQ{i:02d}" for i in range(1, 13)]
SEVERITIES = {"Crítica", "Alta", "Media"}


def check() -> list[str]:
    rules, fields = load_rules(), load_fields()
    errors = []

    missing = set(EXPECTED_RULES) - set(rules)
    if missing:
        errors.append(f"Faltan reglas: {sorted(missing)}")
    for rid, r in rules.items():
        for key in ("nombre", "tipo", "severidad"):
            if not r.get(key):
                errors.append(f"{rid}: falta '{key}'")
        if r.get("severidad") not in SEVERITIES:
            errors.append(f"{rid}: severidad inválida {r.get('severidad')!r}")

    def rng(rid, block) -> dict | None:
        """Devuelve el rango si es válido; si no, registra el error y devuelve None."""
        b = rules.get(rid, {}).get(block, {}) if block else rules.get(rid, {})
        if isinstance(b.get("min"), (int, float)) and isinstance(b.get("max"), (int, float)) and b["min"] < b["max"]:
            return b
        errors.append(f"{rid}{'.' + block if block else ''}: min/max inválidos")
        return None

    rng("DQ07", None)
    for rid in ("DQ09", "DQ10"):
        rej, warn = rng(rid, "reject"), rng(rid, "warning")
        if rej and warn and not (rej["min"] <= warn["min"] < warn["max"] <= rej["max"]):
            errors.append(f"{rid}: el rango de warning debe estar dentro del de rechazo")

    units = rules.get("DQ06", {}).get("expected_units", {})
    if set(units) != set(MEASUREMENT_VARIABLES):
        errors.append(f"DQ06: expected_units debe cubrir {MEASUREMENT_VARIABLES}")

    for name, value in rules.get("DQ11", {}).get("min_gap_minutes", {}).items():
        if not isinstance(value, int) or value <= 0:
            errors.append(f"DQ11.min_gap_minutes.{name}: debe ser un entero positivo")

    ids = [f.get("field_id") for f in fields]
    if len(ids) != len(set(ids)) or not all(ids):
        errors.append("fields.yaml: field_id vacío o repetido")
    return errors


def main() -> None:
    errors = check()
    for e in errors:
        print(f"[RULES] ERROR {e}")
    if errors:
        sys.exit(1)
    print(f"[RULES] OK: {len(load_rules())} reglas y {len(load_fields())} campos válidos.")


if __name__ == "__main__":
    main()
