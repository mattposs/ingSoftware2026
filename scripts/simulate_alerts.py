"""
simulate_alerts.py
Provoca fallas a propósito en STAGING y junta la evidencia de que las alertas AL01 y AL02 se disparan.
Nunca toca PROD: todos los comandos fijan APP_ENV=staging y solo se consultan las reglas de STAGING.

    python scripts/simulate_alerts.py                    # escenarios A y B (≈ 5 a 20 min)
    python scripts/simulate_alerts.py --escenario A      # solo uno
    python scripts/simulate_alerts.py --escenario C      # ausencia de corridas: tarda entre 31 y 47 min

Escenarios:
  A · Corrida fallida: una corrida con PIPELINE_FORCE_FAILURE=true queda FAILED → AL01.
  B · Caída del DQ Score: una corrida del simulador IoT con PIPELINE_IOT_ERROR_RATE=0.5 → AL02.
  C · Corrida ausente: se detiene scheduler-staging hasta que pasan 30 min sin filas nuevas → AL01.

Requisitos: el stack levantado (docker compose up -d) y, para las capturas,
    pip install -r scripts/requirements-evidencia.txt && python -m playwright install chromium

Qué modifica y cómo lo restaura (siempre, aunque el script falle):
  - Detiene scheduler-staging durante cada escenario, para que una corrida normal no tape la falla,
    y lo vuelve a levantar al terminar.
  - La falla forzada y el error_rate alto se pasan con -e a un contenedor de un solo uso
    (docker compose run --rm): no se edita ningún archivo ni la configuración de los schedulers.
  - Las corridas de prueba quedan registradas en gold.dq_run_metrics de STAGING (es la evidencia).

Salida: docs/evidencia_alertas/ (capturas PNG, resultados.json, salida de cada corrida y resumen.md).
Credenciales de Grafana: GRAFANA_USER (admin por defecto) y GRAFANA_ADMIN_PASSWORD, desde el entorno,
.env o .env.example. Nada de esto se escribe en la evidencia.
"""

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import requests
from dotenv import dotenv_values
from sqlalchemy import create_engine, text

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "evidencia_alertas"
ENV = "staging"                       # fijo: este script nunca corre contra PROD
SERVICE = "scheduler-staging"
RULES = {"AL01": "al01-staging", "AL02": "al02-staging"}
TZ_LOCAL = ZoneInfo("America/Argentina/Buenos_Aires")

_files = {**dotenv_values(ROOT / ".env.example"), **dotenv_values(ROOT / ".env")}


def cfg(name: str, default: str = "") -> str:
    return os.getenv(name) or _files.get(name) or default


GRAFANA = cfg("GRAFANA_URL", f"http://localhost:{cfg('GRAFANA_PORT', '3000')}")
MAILPIT = cfg("MAILPIT_URL", f"http://localhost:{cfg('MAILPIT_PORT', '8025')}")
AUTH = (cfg("GRAFANA_USER", "admin"), cfg("GRAFANA_ADMIN_PASSWORD"))
AL01_MINUTOS = float(cfg("ALERT_AL01_MINUTOS_SIN_CORRIDAS", "30"))
DB_URL = (f"postgresql+psycopg://{cfg('PIPELINE_DB_USER', 'pipeline')}:{cfg('PIPELINE_DB_PASSWORD')}"
          f"@localhost:{cfg('POSTGRES_PORT', '5432')}/agro_{ENV}")


def log(msg: str) -> None:
    print(f"[{datetime.now(UTC):%H:%M:%S} UTC] {msg}", flush=True)


def fmt(ts: datetime | None) -> str:
    if ts is None:
        return "—"
    return f"{ts.astimezone(UTC):%Y-%m-%d %H:%M:%S} UTC ({ts.astimezone(TZ_LOCAL):%H:%M:%S} hora Argentina)"


def iso(ts: datetime | None) -> str | None:
    return ts.astimezone(UTC).isoformat() if ts else None


# --- Docker --------------------------------------------------------------------------------------

def compose(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    env = {**os.environ, "MSYS_NO_PATHCONV": "1"}
    res = subprocess.run(["docker", "compose", *args], cwd=ROOT, env=env, capture_output=True, text=True,
                         encoding="utf-8", errors="replace")
    if check and res.returncode != 0:
        raise RuntimeError(f"docker compose {' '.join(args)} falló:\n{res.stdout}\n{res.stderr}")
    return res


def scheduler_running() -> bool:
    return SERVICE in compose("ps", "--status", "running", "--services").stdout.split()


def pipeline_run(name: str, *extra_env: str, args: tuple[str, ...] = ()) -> subprocess.CompletedProcess:
    """Corrida de un solo uso en STAGING (contenedor 'pipeline', se borra al terminar)."""
    env_args = ["-e", f"APP_ENV={ENV}"]
    for e in extra_env:
        env_args += ["-e", e]
    res = compose("--profile", "run", "run", "--rm", "--no-deps", *env_args, "pipeline", "python", "-m", "src.main",
                  "--env", ENV, *args, check=False)
    (OUT / f"{name}_salida_pipeline.txt").write_text(
        f"$ docker compose run --rm {' '.join(env_args)} pipeline python -m src.main --env {ENV} {' '.join(args)}\n"
        f"(código de salida: {res.returncode})\n\n{res.stdout}\n{res.stderr}", encoding="utf-8")
    return res


# --- Base y Grafana ------------------------------------------------------------------------------

_engine = None


def db():
    global _engine
    _engine = _engine or create_engine(DB_URL)
    return _engine


def last_run() -> dict | None:
    with db().connect() as conn:
        row = conn.execute(text(
            "SELECT _batch_id, run_start, run_status, status, started_at, finished_at, duration_seconds, "
            "last_measured_at, total, valid, warning, invalid, dq_score, pct_utilizable "
            "FROM gold.dq_run_metrics ORDER BY run_start DESC LIMIT 1")).mappings().first()
    return dict(row) if row else None


def iot_watermark() -> datetime | None:
    with db().connect() as conn:
        return conn.execute(text("SELECT watermark FROM etl.watermarks WHERE entity = 'iot_simulator'")).scalar()


def rule_state(alert_id: str) -> dict:
    """Estado de la regla desde la API de Grafana: state (inactive/pending/firing) y activeAt de la instancia."""
    r = requests.get(f"{GRAFANA}/api/prometheus/grafana/api/v1/rules", auth=AUTH, timeout=15)
    r.raise_for_status()
    for group in r.json()["data"]["groups"]:
        for rule in group["rules"]:
            if rule.get("labels", {}).get("alert_id") == alert_id and rule.get("labels", {}).get("entorno") == ENV:
                alerts = rule.get("alerts") or []
                active = [a for a in alerts if a.get("state", "").lower().startswith("alerting")]
                active_at = active[0].get("activeAt") if active else None
                return {"state": rule["state"], "health": rule.get("health"), "last_error": rule.get("lastError"),
                        "active_at": datetime.fromisoformat(active_at.replace("Z", "+00:00")) if active_at else None,
                        "valores": active[0].get("value") if active else None,
                        "evaluado": rule.get("lastEvaluation")}
    raise RuntimeError(f"No encontré la regla {alert_id} de {ENV} en Grafana. ¿Está provisionada?")


def first_alerting_after(alert_id: str, after: datetime) -> tuple[datetime, dict] | None:
    """Primera transición a Alerting después de 'after', según el historial de estados de Grafana."""
    now = int(time.time())
    r = requests.get(f"{GRAFANA}/api/v1/rules/history", auth=AUTH, timeout=15,
                     params={"ruleUID": RULES[alert_id], "from": int(after.timestamp()) - 60, "to": now})
    r.raise_for_status()
    t, _, prev, nxt, data = r.json()["data"]["values"]
    hits = sorted((datetime.fromtimestamp(t[i] / 1e6, UTC), json.loads(data[i])) for i in range(len(t))
                  if nxt[i] == "Alerting" and prev[i] != "Alerting" and t[i] / 1e6 >= after.timestamp() - 60)
    return hits[0] if hits else None


def wait_firing(alert_id: str, after: datetime, timeout_min: float) -> dict:
    deadline = time.monotonic() + timeout_min * 60
    while time.monotonic() < deadline:
        st = rule_state(alert_id)
        if st["state"] == "firing" and st["active_at"] and st["active_at"] >= after - timedelta(minutes=1):
            return st
        time.sleep(10)
    raise TimeoutError(f"{alert_id} no pasó a Firing en {timeout_min:.0f} minutos.")


def wait_inactive(alert_id: str, timeout_min: float) -> bool:
    deadline = time.monotonic() + timeout_min * 60
    while time.monotonic() < deadline:
        if rule_state(alert_id)["state"] == "inactive":
            return True
        time.sleep(10)
    return False


def wait_mail(alert_id: str, after: datetime, timeout_min: float = 4) -> dict | None:
    deadline = time.monotonic() + timeout_min * 60
    while time.monotonic() < deadline:
        r = requests.get(f"{MAILPIT}/api/v1/messages", params={"limit": 50}, timeout=10)
        r.raise_for_status()
        for m in r.json().get("messages", []):
            created = datetime.fromisoformat(m["Created"].replace("Z", "+00:00"))
            subject = m.get("Subject", "")
            if alert_id in subject and "FIRING" in subject.upper() and created >= after - timedelta(minutes=1):
                return {"id": m["ID"], "asunto": subject, "recibido": created}
        time.sleep(10)
    return None


# --- Capturas ------------------------------------------------------------------------------------

def screenshots(alert_id: str, escenario: str, mail: dict | None, solo: set[str] | None = None) -> list[dict]:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        log("Playwright no está instalado: no hay capturas (pip install -r scripts/requirements-evidencia.txt).")
        return []
    shots = []
    uid = RULES[alert_id]
    pages = [
        (f"{alert_id}_firing.png", "Lista de alertas con la regla en Firing",
         f"{GRAFANA}/alerting/list", "lista"),
        (f"{alert_id}_detalle_regla.png", "Detalle de la regla",
         f"{GRAFANA}/alerting/grafana/{uid}/view?tab=instances", None),
        (f"{alert_id}_panel_salud.png", "Panel de salud del pipeline (dashboard de calidad, STAGING)",
         f"{GRAFANA}/d/agro-calidad/?var-entorno=agro-{ENV}&orgId=1&kiosk", "salud"),
    ]
    if mail:
        pages.append((f"{alert_id}_notificacion_mailpit.png", "Notificación recibida en Mailpit",
                      f"{MAILPIT}/view/{mail['id']}", None))
    if solo:
        pages = [pg for pg in pages if pg[0] in solo]
    with sync_playwright() as p:
        try:
            browser = p.chromium.launch(headless=True)
        except Exception:
            browser = p.chromium.launch(headless=True, channel="msedge")   # Edge también es Chromium
        ctx = browser.new_context(viewport={"width": 1600, "height": 1000},
                                  timezone_id="America/Argentina/Buenos_Aires", locale="es-AR")
        # Sesión de Grafana (la lista de alertas no se ve con acceso anónimo ni con autenticación básica).
        login = ctx.request.post(f"{GRAFANA}/login", data={"user": AUTH[0], "password": AUTH[1]})
        if not login.ok:
            log(f"Aviso: no se pudo iniciar sesión en Grafana ({login.status}); las capturas pueden salir incompletas.")
        page = ctx.new_page()
        for name, desc, url, mode in pages:
            page.goto(url, wait_until="networkidle", timeout=60000)
            page.wait_for_timeout(4000)
            if mode == "lista":   # despliega el grupo de STAGING para que se vea la regla en Firing
                group = page.locator('[data-testid="rule-group"]').filter(has_text=f"Pipeline {ENV.upper()}")
                group.locator('[data-testid="data-testid group-collapse-toggle"]').first.click()
                page.wait_for_timeout(2500)
            stamp = datetime.now(UTC)
            # Franja con la hora de la captura, para que se vea en pantalla.
            page.evaluate(
                """([t]) => { const d = document.createElement('div'); d.textContent = t;
                Object.assign(d.style, {position:'fixed', right:'12px', bottom:'12px', zIndex:99999,
                background:'#111', color:'#fff', font:'600 14px monospace', padding:'6px 10px',
                borderRadius:'6px', border:'2px solid #f5b73b'}); document.body.appendChild(d); }""",
                [f"Escenario {escenario} · captura {stamp.astimezone(TZ_LOCAL):%d/%m/%Y %H:%M:%S} (ART) · "
                 f"{stamp:%H:%M:%S} UTC"])
            kwargs = {"path": str(OUT / name)}
            if mode == "salud":
                kwargs["clip"] = {"x": 0, "y": 0, "width": 1600, "height": 560}
            page.screenshot(**kwargs)
            shots.append({"archivo": name, "que_muestra": desc, "escenario": escenario, "tomada": iso(stamp)})
            log(f"Captura: {name}")
        browser.close()
    return shots


# --- Escenarios ----------------------------------------------------------------------------------

def check_rule_ready(alert_id: str) -> dict:
    st = rule_state(alert_id)
    if st["state"] != "inactive":
        log(f"Aviso: {alert_id} ya estaba en {st['state']} antes del escenario.")
    return st


def escenario_a(timeout_min: float) -> dict:
    antes = check_rule_ready("AL01")
    log("A · Corrida con falla forzada (PIPELINE_FORCE_FAILURE=true)...")
    res = pipeline_run("A", "PIPELINE_FORCE_FAILURE=true")
    run = last_run()
    if res.returncode == 0 or not run or run["run_status"] != "FAILED":
        raise RuntimeError("La corrida forzada no quedó registrada como FAILED; ver A_salida_pipeline.txt.")
    falla = run["finished_at"]
    log(f"A · Corrida {run['_batch_id']} FAILED a las {fmt(falla)}. Esperando AL01...")
    st = wait_firing("AL01", falla, timeout_min)
    mail = wait_mail("AL01", st["active_at"])
    return {"escenario": "A", "alerta": "AL01", "estado_previo": antes["state"],
            "falla": "Corrida del pipeline con PIPELINE_FORCE_FAILURE=true (falla antes de la extracción)",
            "como": "docker compose run --rm -e APP_ENV=staging -e PIPELINE_FORCE_FAILURE=true pipeline",
            "batch_id": run["_batch_id"], "codigo_salida": res.returncode,
            "hora_falla": iso(falla), "hora_disparo": iso(st["active_at"]), "valores_regla": st["valores"],
            "minutos": round((st["active_at"] - falla).total_seconds() / 60, 2),
            "notificacion": {**mail, "recibido": iso(mail["recibido"])} if mail else None,
            "capturas": screenshots("AL01", "A", mail)}


def escenario_b(timeout_min: float) -> dict:
    antes = check_rule_ready("AL02")
    # El simulador genera una lectura por campo cada 15 min: hace falta un turno nuevo después del watermark.
    wm = iot_watermark()
    now = datetime.now(UTC)
    slot = now.replace(second=0, microsecond=0) - timedelta(minutes=now.minute % 15)
    if wm and wm >= slot:
        espera = (slot + timedelta(minutes=15, seconds=20) - now).total_seconds()
        log(f"B · El último turno de 15 min ya se procesó; espero {espera / 60:.1f} min al siguiente...")
        time.sleep(max(0, espera))
    log("B · Corrida del simulador IoT con PIPELINE_IOT_ERROR_RATE=0.5...")
    res = pipeline_run("B", "PIPELINE_IOT_ERROR_RATE=0.5", args=("--source", "iot_simulator"))
    run = last_run()
    if res.returncode != 0 or not run or run["run_status"] != "SUCCESS":
        raise RuntimeError("La corrida con error_rate alto no terminó bien; ver B_salida_pipeline.txt.")
    falla = run["finished_at"]
    log(f"B · Corrida {run['_batch_id']}: DQ Score {run['dq_score']} % ({run['valid']} VALID de {run['total']}), "
        f"publicada a las {fmt(falla)}. Esperando AL02...")
    if float(run["dq_score"]) >= float(cfg("ALERT_AL02_DQ_SCORE_MINIMO", "80")):
        log("B · Aviso: el score no quedó por debajo del mínimo; AL02 solo se dispara si cae 10 puntos vs 24 h.")
    st = wait_firing("AL02", falla, timeout_min)
    mail = wait_mail("AL02", st["active_at"])
    return {"escenario": "B", "alerta": "AL02", "estado_previo": antes["state"],
            "falla": "Corrida del simulador IoT con 50 % de registros con errores inyectados",
            "como": "docker compose run --rm -e APP_ENV=staging -e PIPELINE_IOT_ERROR_RATE=0.5 pipeline "
                    "python -m src.main --env staging --source iot_simulator",
            "batch_id": run["_batch_id"], "codigo_salida": res.returncode,
            "dq_score": float(run["dq_score"]), "total": run["total"], "valid": run["valid"],
            "warning": run["warning"], "invalid": run["invalid"],
            "hora_falla": iso(falla), "hora_disparo": iso(st["active_at"]), "valores_regla": st["valores"],
            "minutos": round((st["active_at"] - falla).total_seconds() / 60, 2),
            "notificacion": {**mail, "recibido": iso(mail["recibido"])} if mail else None,
            "capturas": screenshots("AL02", "B", mail)}


def escenario_c(timeout_min: float) -> dict:
    antes = check_rule_ready("AL01")
    run = last_run()
    detenido = datetime.now(UTC)
    limite = (run["run_start"] if run else detenido) + timedelta(minutes=AL01_MINUTOS)
    log(f"C · scheduler-staging detenido a las {fmt(detenido)}. Última corrida: {fmt(run and run['run_start'])}. "
        f"AL01 debería dispararse después de {fmt(limite)} (≈ {(limite - detenido).total_seconds() / 60:.0f} min).")
    st = wait_firing("AL01", limite, timeout_min)
    mail = wait_mail("AL01", st["active_at"])
    return {"escenario": "C", "alerta": "AL01", "estado_previo": antes["state"],
            "falla": f"Scheduler de STAGING detenido: más de {AL01_MINUTOS:.0f} min sin filas nuevas",
            "como": "docker compose stop scheduler-staging",
            "hora_detencion": iso(detenido), "ultima_corrida": iso(run["run_start"]) if run else None,
            "hora_falla": iso(limite), "hora_disparo": iso(st["active_at"]), "valores_regla": st["valores"],
            "minutos": round((st["active_at"] - limite).total_seconds() / 60, 2),
            "minutos_desde_detencion": round((st["active_at"] - detenido).total_seconds() / 60, 2),
            "notificacion": {**mail, "recibido": iso(mail["recibido"])} if mail else None,
            "capturas": screenshots("AL01", "C", mail)}


def recuperar(escenario: str, batch_id: str) -> dict:
    """
    Rearma el resultado de un escenario ya ejecutado a partir de las fuentes reales: la corrida en
    gold.dq_run_metrics, la transición a Alerting en el historial de Grafana y el correo en Mailpit.
    Rehace solo la captura de la lista de alertas, que tiene que mostrar la regla todavía en Firing.
    """
    alerta = "AL02" if escenario == "B" else "AL01"
    with db().connect() as conn:
        run = conn.execute(text("SELECT * FROM gold.dq_run_metrics WHERE _batch_id = :b"), {"b": batch_id}).mappings().one()
    falla = run["finished_at"]
    hit = first_alerting_after(alerta, falla)
    if not hit:
        raise RuntimeError(f"No hay una transición de {alerta} a Alerting después de la corrida {batch_id}.")
    disparo, valores = hit
    if rule_state(alerta)["state"] != "firing":
        raise RuntimeError(f"{alerta} ya no está en Firing: no se puede rehacer la captura de la lista.")
    mail = wait_mail(alerta, disparo, timeout_min=0.2)
    previas = [{"archivo": f"{alerta}_{n}.png", "que_muestra": d, "escenario": escenario,
                "tomada": iso(datetime.fromtimestamp((OUT / f"{alerta}_{n}.png").stat().st_mtime, UTC))}
               for n, d in (("detalle_regla", "Detalle de la regla"),
                            ("panel_salud", "Panel de salud del pipeline (dashboard de calidad, STAGING)"),
                            ("notificacion_mailpit", "Notificación recibida en Mailpit"))
               if (OUT / f"{alerta}_{n}.png").exists()]
    nueva = screenshots(alerta, escenario, mail, solo={f"{alerta}_firing.png"})
    base = {"escenario": escenario, "alerta": alerta, "batch_id": batch_id, "hora_falla": iso(falla),
            "hora_disparo": iso(disparo), "valores_regla": valores.get("values"),
            "minutos": round((disparo - falla).total_seconds() / 60, 2),
            "notificacion": {**mail, "recibido": iso(mail["recibido"])} if mail else None,
            "capturas": nueva + previas, "recuperado": True}
    if escenario == "B":
        base.update({"falla": "Corrida del simulador IoT con 50 % de registros con errores inyectados",
                     "como": "docker compose run --rm -e APP_ENV=staging -e PIPELINE_IOT_ERROR_RATE=0.5 pipeline "
                             "python -m src.main --env staging --source iot_simulator",
                     "dq_score": float(run["dq_score"]), "total": run["total"], "valid": run["valid"],
                     "warning": run["warning"], "invalid": run["invalid"]})
    else:
        base.update({"falla": "Corrida del pipeline con PIPELINE_FORCE_FAILURE=true (falla antes de la extracción)",
                     "como": "docker compose run --rm -e APP_ENV=staging -e PIPELINE_FORCE_FAILURE=true pipeline"})
    return base


# --- Resumen -------------------------------------------------------------------------------------

def _t(s: str | None) -> str:
    return fmt(datetime.fromisoformat(s)) if s else "—"


def _n(x: float) -> str:
    return f"{x:.2f}".replace(".", ",")


def write_summary(results: list[dict], restore_notes: list[str]) -> None:
    lines = [
        "# Evidencia de las alertas del pipeline (sección 11.6)",
        "",
        f"Generado por `scripts/simulate_alerts.py` el {fmt(datetime.now(UTC))}, contra el entorno **STAGING**. "
        "Todos los datos salen de la ejecución: la hora de la falla, de `gold.dq_run_metrics`; la hora de disparo "
        "y el estado, de la API de Grafana (`activeAt` de la instancia en Firing o, en un escenario rearmado con "
        "`--recuperar`, la transición a Alerting del historial de estados); la notificación, de Mailpit.",
        "",
        "## Texto para la sección 11.6",
        "",
    ]
    for r in results:
        if r.get("error"):
            lines += [f"**Escenario {r['escenario']}: no se completó.** {r['error']}", ""]
            continue
        cumple = r["minutos"] <= 30
        extra = (f" El DQ Score de esa corrida fue de **{_n(r['dq_score'])} %** ({r['valid']} registros VALID de "
                 f"{r['total']}; {r['warning']} WARNING y {r['invalid']} INVALID)." if r["escenario"] == "B" else "")
        if r["escenario"] == "C":
            cuando = (f"El scheduler se detuvo a las {_t(r['hora_detencion'])}; la última corrida registrada era de las "
                      f"{_t(r['ultima_corrida'])}, así que el umbral de {AL01_MINUTOS:.0f} minutos sin corridas se "
                      f"cruzó a las {_t(r['hora_falla'])}.")
        else:
            cuando = f"La corrida quedó registrada a las {_t(r['hora_falla'])}."
        mail = (f" La notificación llegó por correo (Mailpit) a las {_t(r['notificacion']['recibido'])}, con el asunto "
                f"«{r['notificacion']['asunto']}»." if r.get("notificacion") else
                " No se encontró la notificación en Mailpit dentro del tiempo de espera.")
        lines += [
            f"**Escenario {r['escenario']} – {r['falla']}.** Se provocó con `{r['como']}`. {cuando}{extra} "
            f"Grafana disparó la alerta **{r['alerta']}** a las {_t(r['hora_disparo'])}, "
            f"**{_n(r['minutos'])} minutos** después.{mail} "
            f"RNF11 (alerta en ≤ 30 minutos): **{'se cumple' if cumple else 'NO se cumple'}**.",
            "",
        ]
    lines += ["## Datos", "",
              "| Escenario | Falla provocada | Alerta | Hora de la falla | Hora del disparo | Minutos | DQ Score | RNF11 (≤ 30 min) |",
              "|---|---|---|---|---|---|---|---|"]
    for r in results:
        if r.get("error"):
            lines.append(f"| {r['escenario']} | no se completó | — | — | — | — | — | — |")
            continue
        score = f"{_n(r['dq_score'])} %" if "dq_score" in r else "—"
        lines.append(f"| {r['escenario']} | {r['falla']} | {r['alerta']} | {_t(r['hora_falla'])} | "
                     f"{_t(r['hora_disparo'])} | {_n(r['minutos'])} | {score} | "
                     f"{'Cumple' if r['minutos'] <= 30 else 'No cumple'} |")
    notas = [f"- Escenario {r['escenario']}: rearmado con `--recuperar` (no se repitió la falla). La captura de la lista "
             f"de alertas se tomó después, con {r['alerta']} todavía en Firing desde el disparo original."
             for r in results if r.get("recuperado")]
    if notas:
        lines += ["", "## Notas", "", *notas]
    lines += ["", "## Capturas", "", "En cada captura se ve, abajo a la derecha, la hora en que se tomó.", "",
              "| Archivo | Escenario | Qué muestra | Tomada |", "|---|---|---|---|"]
    for r in results:
        for c in r.get("capturas", []):
            lines.append(f"| [{c['archivo']}]({c['archivo']}) | {c['escenario']} | {c['que_muestra']} | {_t(c.get('tomada'))} |")
    lines += ["", "## Restauración del entorno", ""] + [f"- {n}" for n in restore_notes]
    lines += ["", "Detalle completo: [`resultados.json`](resultados.json) y la salida de cada corrida "
              "(`<escenario>_salida_pipeline.txt`).", ""]
    (OUT / "resumen.md").write_text("\n".join(lines), encoding="utf-8")


# --- Principal -----------------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description="Simulación de alertas AL01 / AL02 en STAGING")
    parser.add_argument("--escenario", choices=["A", "B", "C"], action="append",
                        help="escenario a correr (se puede repetir). Por defecto: A y B. C es opcional.")
    parser.add_argument("--timeout-min", type=float, default=10, help="espera máxima del disparo (A y B)")
    parser.add_argument("--recuperar", metavar="ESCENARIO=BATCH_ID",
                        help="rearma el resultado de un escenario ya corrido (ej. B=<batch_id>) sin repetir la falla")
    args = parser.parse_args()
    if args.recuperar:
        OUT.mkdir(parents=True, exist_ok=True)
        esc, batch = args.recuperar.split("=", 1)
        res = recuperar(esc.upper(), batch)
        previos = OUT / "resultados.json"
        todos = {r["escenario"]: r for r in (json.loads(previos.read_text(encoding="utf-8")) if previos.exists() else [])}
        todos[res["escenario"]] = res
        todos = [todos[k] for k in sorted(todos)]
        previos.write_text(json.dumps(todos, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        write_summary(todos, [f"Escenario {res['escenario']} rearmado con --recuperar a partir de gold.dq_run_metrics, "
                              "el historial de estados de Grafana y Mailpit; no se repitió la falla."])
        log(f"Escenario {res['escenario']}: {res['alerta']} a los {res['minutos']:.2f} min (recuperado).")
        return 0
    escenarios = args.escenario or ["A", "B"]
    if not AUTH[1]:
        sys.exit("Falta GRAFANA_ADMIN_PASSWORD (entorno, .env o .env.example).")
    OUT.mkdir(parents=True, exist_ok=True)

    was_running = scheduler_running()
    log(f"Entorno: {ENV.upper()} · {SERVICE} {'en ejecución' if was_running else 'detenido'} al empezar.")
    results, restore_notes = [], []
    try:
        for esc in escenarios:
            # La alerta tiene que estar en Normal antes de provocar la falla; si no, el disparo no sería de esta falla.
            # Se espera con el scheduler andando: la próxima corrida normal la resuelve (hasta un ciclo de 15 min).
            alerta = "AL02" if esc == "B" else "AL01"
            if rule_state(alerta)["state"] != "inactive":
                log(f"{alerta} todavía está activa por una corrida anterior; espero que vuelva a Normal (hasta 20 min)...")
                if not wait_inactive(alerta, 20):
                    results.append({"escenario": esc, "error": f"{alerta} no volvió a Normal antes del escenario."})
                    continue
            log(f"Deteniendo {SERVICE} para el escenario {esc}...")
            compose("stop", SERVICE)
            try:
                fn = {"A": escenario_a, "B": escenario_b, "C": escenario_c}[esc]
                timeout = args.timeout_min if esc != "C" else AL01_MINUTOS + 20
                results.append(fn(timeout))
                log(f"Escenario {esc}: {results[-1]['alerta']} en Firing a los {results[-1]['minutos']:.2f} min.")
            except Exception as exc:  # se registra y se sigue con el próximo escenario
                log(f"Escenario {esc} falló: {exc}")
                results.append({"escenario": esc, "error": str(exc)})
            finally:
                if was_running:
                    compose("up", "-d", SERVICE)     # corre enseguida y vuelve a dejar una corrida normal
    finally:
        if was_running and not scheduler_running():
            compose("up", "-d", SERVICE, check=False)
        ok = scheduler_running() == was_running
        restore_notes.append(f"{SERVICE}: {'en ejecución' if scheduler_running() else 'detenido'} al terminar "
                             f"({'igual que al empezar' if ok else 'DISTINTO al estado inicial: revisar'}).")
        restore_notes.append("PIPELINE_FORCE_FAILURE y PIPELINE_IOT_ERROR_RATE se pasaron solo a contenedores de un "
                             "solo uso (docker compose run --rm): ningún archivo ni scheduler quedó con esos valores.")
        restore_notes.append("Las corridas de prueba quedan en gold.dq_run_metrics de STAGING (son la evidencia). "
                             "La del escenario B también aportó su lote al Gold de STAGING.")
        # Se combinan con los escenarios de corridas anteriores: cada escenario conserva su última ejecución.
        previos = OUT / "resultados.json"
        anteriores = json.loads(previos.read_text(encoding="utf-8")) if previos.exists() else []
        # Un intento fallido no pisa un resultado exitoso anterior del mismo escenario.
        por_escenario = {r["escenario"]: r for r in anteriores}
        for r in results:
            if not r.get("error") or por_escenario.get(r["escenario"], {}).get("error", True):
                por_escenario[r["escenario"]] = r
        todos = [por_escenario[k] for k in sorted(por_escenario)]
        previos.write_text(json.dumps(todos, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        write_summary(todos, restore_notes)
        for n in restore_notes:
            log(n)
    log(f"Listo: {OUT / 'resumen.md'}")
    return 0 if all(not r.get("error") for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
