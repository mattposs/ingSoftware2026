"""
trace.py
"ETL paso a paso": por cada lote se eligen unos pocos registros de muestra (válidos, con
warning y rechazados) y se guarda lo que le pasó a cada uno en las 5 etapas, para poder
seguirlos en el dashboard:

  1. Extracción  -> cómo llegó de la fuente (texto crudo y unidades)
  2. Bronze      -> el mismo registro + linaje, sin cambios
  3. Validación  -> resultado de cada regla DQ01–DQ12
  4. Destino     -> Silver (tipado) o Quarantine (con el motivo)
  5. Gold        -> a qué indicador diario aportó (o por qué no llegó)
"""

from datetime import UTC, datetime

import pandas as pd
from sqlalchemy import Engine, text

from src.config import MEASUREMENT_VARIABLES
from src.validation.engine import REJECT, WARNING, parse_timestamps

LABELS = {
    "temperature": "Temperatura",
    "humidity": "Humedad ambiental",
    "soil_moisture": "Humedad del suelo",
    "precipitation": "Precipitación",
    "wind_speed": "Viento",
}
ICON = {"VALID": "✔", "WARNING": "⚠", "INVALID": "✖"}


def _fmt(value) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)) or value is pd.NA:
        return "(vacío)"
    return str(value)


def _status_by_row(n_rows: int, findings: pd.DataFrame) -> pd.Series:
    status = pd.Series("VALID", index=range(n_rows))
    status[findings.loc[findings["action"] == WARNING, "_row"].unique()] = "WARNING"
    status[findings.loc[findings["action"] == REJECT, "_row"].unique()] = "INVALID"
    return status


def _pick(df: pd.DataFrame, status: pd.Series, findings: pd.DataFrame, per_status: int) -> list[int]:
    """Elige registros variados: válidos de distintas fuentes y errores de distintas reglas."""
    chosen = []
    value_rules = {"DQ06", "DQ07", "DQ08", "DQ09", "DQ10"}  # rechazos por valor: los más ilustrativos
    for st, action in (("VALID", None), ("WARNING", WARNING), ("INVALID", REJECT)):
        seen, picked = set(), []
        candidates = list(status[status == st].index)
        if action == REJECT:
            first_rule = findings[findings["action"] == REJECT].groupby("_row")["rule_id"].min()
            candidates.sort(key=lambda r: first_rule.get(r) not in value_rules)
        for row in candidates:
            if action is None:
                key = df.at[row, "source"]
            else:
                rules = findings.loc[(findings["_row"] == row) & (findings["action"] == action), "rule_id"]
                key = rules.min()
            if key in seen:
                continue
            seen.add(key)
            picked.append(int(row))
            if len(picked) == per_status:
                break
        chosen += picked
    return chosen


def build_traces(
    batch: pd.DataFrame,
    findings: pd.DataFrame,
    rules: dict,
    batch_id: str,
    tz: str,
    env: str,
    domain: str,
    entity: str,
    per_status: int = 2,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Arma las trazas (pasos 1 a 4, y el 5 de los rechazados) de un lote ya validado."""
    df = batch.reset_index(drop=True)
    status = _status_by_row(len(df), findings)
    ts = parse_timestamps(df["timestamp"])
    traces, steps = [], []

    for n, row in enumerate(_pick(df, status, findings, per_status), start=1):
        rec, st = df.loc[row], status[row]
        trace_id = f"{batch_id[:8]}-{n}"
        f_row = findings[findings["_row"] == row]
        reject_codes = ";".join(sorted(set(f_row.loc[f_row["action"] == REJECT, "rule_id"])))
        warn_codes = ";".join(sorted(set(f_row.loc[f_row["action"] == WARNING, "rule_id"])))
        measured = ts[row] if pd.notna(ts[row]) else None
        fecha = measured.tz_convert(tz).date() if measured is not None else None
        codes = reject_codes or warn_codes
        traces.append({
            "trace_id": trace_id, "_batch_id": batch_id, "dq_status": st,
            "source": rec["source"], "field_id": None if pd.isna(rec["field_id"]) else rec["field_id"],
            "measured_at": measured, "fecha_negocio": fecha if st != "INVALID" else None,
            "titulo": f"{ICON[st]} {st} · {_fmt(rec['field_id'])} · {rec['source']} · {_fmt(rec['timestamp'])}"
                      + (f" ({codes})" if codes else ""),
        })

        def add(step, dato, valor, resultado=None, _tid=trace_id):
            steps.append({"trace_id": _tid, "step": step, "orden": sum(1 for s in steps if s["trace_id"] == _tid
                                                                         and s["step"] == step) + 1,
                          "dato": dato, "valor": valor, "resultado": resultado})

        # 1. Extracción
        add(1, "Fuente", rec["source"])
        add(1, "timestamp (texto crudo)", _fmt(rec["timestamp"]))
        add(1, "field_id", _fmt(rec["field_id"]))
        add(1, "Latitud / longitud", f"{_fmt(rec['latitude'])} / {_fmt(rec['longitude'])}")
        for v in MEASUREMENT_VARIABLES:
            unit = rec[f"{v}_unit"]
            add(1, LABELS[v], _fmt(rec[v]) + (f" {unit}" if pd.notna(rec[v]) and pd.notna(unit) else ""))

        # 2. Bronze
        add(2, "Archivo", f"storage/{env}/bronze/{domain}/{rec['source']}/year=…/batch_{batch_id}.parquet")
        add(2, "_batch_id (lote)", batch_id)
        add(2, "_ingested_at (captura UTC)", _fmt(rec.get("_ingested_at")))
        add(2, "_source_system (conector)", _fmt(rec.get("_source_system")))
        add(2, "Cambios sobre el dato", "Ninguno: Bronze guarda el registro tal cual llegó")

        # 3. Validación: las 12 reglas, una por fila
        for rid in sorted(rules):
            hits = f_row[f_row["rule_id"] == rid]
            if hits.empty:
                add(3, f"{rid} · {rules[rid]['nombre']}", "Cumple", "OK")
                continue
            result = REJECT if (hits["action"] == REJECT).any() else WARNING
            detail = "; ".join(f"{h.variable}: {h.detalle}" if pd.notna(h.variable) else h.detalle
                               for h in hits.itertuples())
            add(3, f"{rid} · {rules[rid]['nombre']}", detail, result)

        # 4. Destino
        if st == "INVALID":
            add(4, "Destino", f"QUARANTINE · storage/{env}/quarantine/{domain}/{entity}/")
            add(4, "_rejection_reasons", reject_codes)
            add(4, "¿Se modifica el dato?", "No: se guarda igual que en Bronze para poder auditarlo")
            # 5. Gold (los rechazados no llegan)
            add(5, "¿Llega a Gold?", "No. Un dato rechazado nunca llega a los indicadores (RNF04)")
            add(5, "Dónde queda registrado", f"gold.dq_errors · {len(f_row)} hallazgo(s) de este registro")
        else:
            add(4, "Destino", f"SILVER · storage/{env}/silver/{domain}/{entity}/")
            add(4, "dq_status", st)
            add(4, "_dq_warnings", warn_codes or "—")
            add(4, "timestamp tipado (UTC)", measured.isoformat())
            add(4, "Fecha de negocio (hora local)", str(fecha))
            for v in MEASUREMENT_VARIABLES:
                add(4, f"{LABELS[v]} (número)", _fmt(rec[v]))

    return pd.DataFrame(traces), pd.DataFrame(steps)


def save_traces(engine: Engine, batch_id: str, traces: pd.DataFrame, steps: pd.DataFrame) -> None:
    """Reemplaza las trazas del lote (idempotente ante reprocesos)."""
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM gold.etl_trace WHERE _batch_id = :b"), {"b": batch_id})
        if not traces.empty:
            traces.assign(created_at=pd.Timestamp(datetime.now(UTC))).to_sql(
                "etl_trace", con=conn, schema="gold", if_exists="append", index=False)
            steps.to_sql("etl_trace_steps", con=conn, schema="gold", if_exists="append", index=False)


def add_gold_step(engine: Engine, batch_id: str, metrics: pd.DataFrame) -> None:
    """Paso 5 de los registros publicados: el indicador diario al que aportaron."""
    with engine.connect() as conn:
        traces = pd.read_sql(
            text("SELECT trace_id, field_id, source, fecha_negocio FROM gold.etl_trace "
                 "WHERE _batch_id = :b AND dq_status <> 'INVALID'"), conn, params={"b": batch_id})
    if traces.empty or metrics.empty:
        return
    rows = []
    for t in traces.itertuples():
        m = metrics[(metrics["fecha"] == t.fecha_negocio) & (metrics["field_id"] == t.field_id)
                    & (metrics["fuente"] == t.source)]
        if m.empty:
            continue
        m = m.iloc[0]
        values = [
            ("Tabla", "gold.daily_field_metrics (PostgreSQL)"),
            ("Clave (fecha · campo · fuente)", f"{m['fecha']} · {m['field_id']} · {m['fuente']}"),
            ("Temperatura promedio del día", f"{m['temperatura_promedio']} °C"),
            ("Precipitación total del día", f"{m['precipitacion_total']} mm"),
            ("Humedad del suelo promedio", f"{m['humedad_suelo_promedio']} m³/m³"),
            ("Humedad ambiental promedio", f"{m['humedad_ambiental_promedio']} %"),
            ("Mediciones del día", f"{m['cantidad_mediciones']} (este registro es una de ellas)"),
            ("% de calidad del día (estricto: solo VALID)", f"{m['porcentaje_calidad']} %"),
        ]
        rows += [{"trace_id": t.trace_id, "step": 5, "orden": i, "dato": d, "valor": v, "resultado": None}
                 for i, (d, v) in enumerate(values, start=1)]
    if rows:
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM gold.etl_trace_steps WHERE step = 5 AND trace_id IN "
                              "(SELECT trace_id FROM gold.etl_trace WHERE _batch_id = :b AND dq_status <> 'INVALID')"),
                         {"b": batch_id})
            pd.DataFrame(rows).to_sql("etl_trace_steps", con=conn, schema="gold", if_exists="append", index=False)
