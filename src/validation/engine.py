"""
engine.py
Motor de Data Quality: evalúa DQ01–DQ12 (config/rules.yaml) sobre un lote de Bronze
y clasifica cada registro como VALID, WARNING o INVALID (RF03, RF04, RF05).

Orden de evaluación:
  1. Reglas críticas de identificación: DQ01–DQ05 (sin esto el registro no se puede usar).
  2. Reglas de valor: DQ06–DQ10 (unidades y rangos; DQ09/DQ10 pueden ser warning).
  3. Reglas de secuencia: DQ11 (huecos) y DQ12 (saltos), que comparan con la lectura
     anterior. Como el pipeline es incremental, la lectura anterior suele estar en un
     lote previo: por eso reciben `context` (histórico de Silver). Ver docs/decisiones.md (D5).
"""

from dataclasses import dataclass
from datetime import UTC, datetime

import pandas as pd

from src.config import MEASUREMENT_VARIABLES

REJECT = "REJECT"
WARNING = "WARNING"

STATUS_VALID = "VALID"
STATUS_WARNING = "WARNING"
STATUS_INVALID = "INVALID"

FINDING_COLUMNS = ["_row", "rule_id", "variable", "action", "detalle"]


@dataclass
class ValidationResult:
    silver: pd.DataFrame       # registros VALID + WARNING, tipados
    quarantine: pd.DataFrame   # registros INVALID tal como vinieron de Bronze + motivos
    findings: pd.DataFrame     # una fila por (registro, regla, variable) -> gold.dq_errors
    total: int
    valid: int
    warning: int
    invalid: int

    @property
    def dq_score(self) -> float:
        """Data Quality Score estricto = registros VALID / totales × 100 (D2). Un WARNING no cuenta como limpio."""
        return round(self.valid / self.total * 100, 2) if self.total else 100.0

    @property
    def pct_utilizable(self) -> float:
        """% utilizable = registros publicados en Silver (VALID + WARNING) / totales × 100 (D2)."""
        return round((self.valid + self.warning) / self.total * 100, 2) if self.total else 100.0


def parse_timestamps(series: pd.Series) -> pd.Series:
    """ISO 8601 a datetime UTC. Lo que no se puede parsear queda NaT. Sin zona horaria = UTC."""
    return pd.to_datetime(series, utc=True, format="ISO8601", errors="coerce")


def _blank(series: pd.Series) -> pd.Series:
    return series.isna() | series.astype("string").str.strip().eq("")


class _Findings:
    def __init__(self):
        self.rows: list[dict] = []

    def add(self, mask: pd.Series, rule_id: str, action: str, variable: str | None, detalle: str):
        for idx in mask[mask].index:
            self.rows.append(
                {"_row": idx, "rule_id": rule_id, "variable": variable, "action": action, "detalle": detalle}
            )

    def frame(self) -> pd.DataFrame:
        return pd.DataFrame(self.rows, columns=FINDING_COLUMNS)

    def rejected_rows(self) -> set:
        return {r["_row"] for r in self.rows if r["action"] == REJECT}


def _sequence_frame(batch: pd.DataFrame, rows: pd.Index, context: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    """Une las filas elegibles del lote con el histórico, marcando cuáles son del lote."""
    current = batch.loc[rows, ["source", "field_id", "_ts", *cols]].assign(_row=rows, _in_batch=True)
    if context.empty:
        return current
    ctx = context.reindex(columns=["source", "field_id", "timestamp", *cols]).rename(columns={"timestamp": "_ts"})
    ctx = ctx.assign(_row=-1, _in_batch=False)
    return pd.concat([ctx, current], ignore_index=True)


def validate(
    batch: pd.DataFrame,
    rules: dict,
    valid_field_ids: set[str],
    context: pd.DataFrame | None = None,
    now: datetime | None = None,
) -> ValidationResult:
    """
    Args:
        batch: registros de Bronze (timestamp como texto crudo).
        rules: contenido de config/rules.yaml -> rules.
        valid_field_ids: campos existentes (config/fields.yaml).
        context: histórico de Silver (timestamp ya tipado) para DQ05, DQ11 y DQ12.
        now: instante de referencia para DQ03 (inyectable en tests).
    """
    now = pd.Timestamp(now or datetime.now(UTC))
    context = context if context is not None else pd.DataFrame()
    df = batch.reset_index(drop=True).copy()
    df["_ts"] = parse_timestamps(df["timestamp"])
    f = _Findings()

    # ---- 1. Identificación (críticas) --------------------------------------------
    ts_blank = _blank(df["timestamp"])
    f.add(ts_blank, "DQ01", REJECT, None, "timestamp nulo o vacío")

    f.add(_blank(df["field_id"]), "DQ02", REJECT, None, "field_id nulo o vacío")

    r = rules["DQ03"]
    min_ts = pd.Timestamp(r["min_timestamp"])
    max_ts = now + pd.Timedelta(minutes=r["future_tolerance_minutes"])
    f.add(~ts_blank & df["_ts"].isna(), "DQ03", REJECT, None, "timestamp no es ISO 8601")
    f.add(df["_ts"].notna() & (df["_ts"] > max_ts), "DQ03", REJECT, None, "timestamp en el futuro")
    f.add(df["_ts"].notna() & (df["_ts"] < min_ts), "DQ03", REJECT, None, f"timestamp anterior a {min_ts.date()}")

    field_ok = ~_blank(df["field_id"])
    f.add(field_ok & ~df["field_id"].isin(valid_field_ids), "DQ04", REJECT, None, "field_id inexistente")

    identifiable = df["_ts"].notna() & field_ok
    key = rules["DQ05"]["key"]
    dup_in_batch = identifiable & df.assign(timestamp=df["_ts"]).duplicated(subset=key, keep="first")
    dup_in_history = pd.Series(False, index=df.index)
    if not context.empty and identifiable.any():
        hist_keys = set(map(tuple, context[key].itertuples(index=False, name=None)))
        batch_keys = df.loc[identifiable].assign(timestamp=df["_ts"])[key].itertuples(index=False, name=None)
        dup_in_history.loc[identifiable] = [k in hist_keys for k in batch_keys]
    f.add(dup_in_batch, "DQ05", REJECT, None, "registro duplicado en el lote")
    f.add(dup_in_history & ~dup_in_batch, "DQ05", REJECT, None, "registro ya procesado en un lote anterior")

    identified_rows = df.index[identifiable & ~df.index.isin(f.rejected_rows())]

    # ---- 2. Valores --------------------------------------------------------------
    unit_ok = {}
    for var, expected in rules["DQ06"]["expected_units"].items():
        bad = df[var].notna() & ~df[f"{var}_unit"].fillna("").eq(expected)
        unit_ok[var] = ~bad
        f.add(bad, "DQ06", REJECT, var, f"unidad distinta de {expected}")

    r = rules["DQ07"]
    h = df["humidity"]
    f.add(unit_ok["humidity"] & h.notna() & ~h.between(r["min"], r["max"]), "DQ07", REJECT, "humidity",
          f"humedad fuera de [{r['min']}, {r['max']}] %")

    r = rules["DQ08"]
    p = df["precipitation"]
    f.add(unit_ok["precipitation"] & p.notna() & (p < r["min"]), "DQ08", REJECT, "precipitation",
          "precipitación negativa")

    for rule_id, var in (("DQ09", "temperature"), ("DQ10", "soil_moisture")):
        r = rules[rule_id]
        v = df[var]
        checkable = unit_ok[var] & v.notna()
        out_reject = checkable & ~v.between(r["reject"]["min"], r["reject"]["max"])
        out_warning = checkable & ~out_reject & ~v.between(r["warning"]["min"], r["warning"]["max"])
        f.add(out_reject, rule_id, REJECT, var, f"fuera del rango físico [{r['reject']['min']}, {r['reject']['max']}]")
        f.add(out_warning, rule_id, WARNING, var,
              f"fuera del rango esperado [{r['warning']['min']}, {r['warning']['max']}]")

    # ---- 3. Secuencia ------------------------------------------------------------
    # DQ11: un registro identificado (aunque tenga un valor rechazado) cuenta como dato recibido.
    gaps = rules["DQ11"]["min_gap_minutes"]
    if len(identified_rows):
        for var in MEASUREMENT_VARIABLES:
            rows = identified_rows[df.loc[identified_rows, var].notna()]
            if not len(rows):
                continue
            seq = _sequence_frame(df, rows, context, [var])
            seq = seq[seq[var].notna()].sort_values(["source", "field_id", "_ts"])
            delta = seq.groupby(["source", "field_id"])["_ts"].diff()
            limit = pd.to_timedelta(seq["source"].map(gaps), unit="min")
            hit = seq["_in_batch"] & limit.notna() & (delta >= limit)
            for row, d in zip(seq.loc[hit, "_row"], delta[hit], strict=True):
                f.add(pd.Series(True, index=[row]), "DQ11", WARNING, var,
                      f"hueco de {int(d.total_seconds() // 60)} min sin datos")

    # DQ12: solo se compara contra valores confiables (registros no rechazados).
    trusted = df.index[identifiable & ~df.index.isin(f.rejected_rows())]
    if len(trusted):
        for var, max_rate in rules["DQ12"]["max_change_per_hour"].items():
            rows = trusted[df.loc[trusted, var].notna()]
            if not len(rows):
                continue
            seq = _sequence_frame(df, rows, context, [var])
            seq = seq[seq[var].notna()].sort_values(["source", "field_id", "_ts"])
            grp = seq.groupby(["source", "field_id"])
            hours = grp["_ts"].diff().dt.total_seconds() / 3600
            rate = grp[var].diff().abs() / hours
            hit = seq["_in_batch"] & (hours > 0) & (rate > max_rate)
            for row, rt in zip(seq.loc[hit, "_row"], rate[hit], strict=True):
                f.add(pd.Series(True, index=[row]), "DQ12", WARNING, var,
                      f"cambio de {rt:.2f}/h (máximo {max_rate}/h)")

    return _classify(df, f.frame())


def _classify(df: pd.DataFrame, findings: pd.DataFrame) -> ValidationResult:
    def codes(action: str) -> pd.Series:
        sel = findings[findings["action"] == action]
        return sel.groupby("_row")["rule_id"].agg(lambda s: ";".join(sorted(set(s))))

    reject_codes = codes(REJECT)
    warning_codes = codes(WARNING)

    status = pd.Series(STATUS_VALID, index=df.index)
    status[df.index.isin(warning_codes.index)] = STATUS_WARNING
    status[df.index.isin(reject_codes.index)] = STATUS_INVALID

    invalid = status == STATUS_INVALID
    lineage = [c for c in df.columns if c.startswith("_") and c != "_ts"]

    silver_cols = ["source", "field_id", "latitude", "longitude", *MEASUREMENT_VARIABLES]
    silver = df.loc[~invalid, silver_cols].copy()
    silver.insert(0, "timestamp", df.loc[~invalid, "_ts"])
    silver["dq_status"] = status[~invalid]
    silver["_dq_warnings"] = warning_codes.reindex(silver.index)
    silver = pd.concat([silver, df.loc[~invalid, lineage]], axis=1)

    quarantine = df.loc[invalid].drop(columns="_ts").copy()
    quarantine["_rejection_reasons"] = reject_codes.reindex(quarantine.index)
    quarantine["_rejected_at"] = pd.Timestamp(datetime.now(UTC))

    # Enriquecer hallazgos con la identificación del registro (para gold.dq_errors / RF08).
    ident = df[["source", "field_id", "_ts"]].rename(columns={"_ts": "measured_at"})
    findings = findings.join(ident, on="_row")

    return ValidationResult(
        silver=silver.reset_index(drop=True),
        quarantine=quarantine.reset_index(drop=True),
        findings=findings,
        total=len(df),
        valid=int((status == STATUS_VALID).sum()),
        warning=int((status == STATUS_WARNING).sum()),
        invalid=int(invalid.sum()),
    )
