#!/bin/sh
# Arranque de Grafana: completa los umbrales de las alertas y después inicia Grafana normalmente.
# El provisioning se monta de solo lectura; se copia a /tmp y ahí se escribe la regla ya resuelta
# a partir de la plantilla grafana/alerting/reglas-pipeline.yml.tmpl.
set -eu

: "${ALERT_AL01_MINUTOS_SIN_CORRIDAS:=30}"
: "${ALERT_AL02_DQ_SCORE_MINIMO:=80}"
: "${ALERT_AL02_CAIDA_MAXIMA_PUNTOS:=10}"

for pair in "ALERT_AL01_MINUTOS_SIN_CORRIDAS=$ALERT_AL01_MINUTOS_SIN_CORRIDAS" \
            "ALERT_AL02_DQ_SCORE_MINIMO=$ALERT_AL02_DQ_SCORE_MINIMO" \
            "ALERT_AL02_CAIDA_MAXIMA_PUNTOS=$ALERT_AL02_CAIDA_MAXIMA_PUNTOS"; do
  value="${pair#*=}"
  if ! printf '%s' "$value" | grep -Eq '^[0-9]+([.][0-9]+)?$'; then
    echo "[ALERTAS] ${pair%%=*}='$value' no es un número." >&2
    exit 1
  fi
done

DEST=/tmp/provisioning
rm -rf "$DEST"
cp -r /etc/grafana/provisioning "$DEST"
mkdir -p "$DEST/alerting"
sed -e "s/\${ALERT_AL01_MINUTOS_SIN_CORRIDAS}/$ALERT_AL01_MINUTOS_SIN_CORRIDAS/g" \
    -e "s/\${ALERT_AL02_DQ_SCORE_MINIMO}/$ALERT_AL02_DQ_SCORE_MINIMO/g" \
    -e "s/\${ALERT_AL02_CAIDA_MAXIMA_PUNTOS}/$ALERT_AL02_CAIDA_MAXIMA_PUNTOS/g" \
    /etc/grafana/alerting/reglas-pipeline.yml.tmpl > "$DEST/alerting/reglas-pipeline.yml"
echo "[ALERTAS] Umbrales: AL01 > ${ALERT_AL01_MINUTOS_SIN_CORRIDAS} min sin corridas · AL02 score < ${ALERT_AL02_DQ_SCORE_MINIMO} % o caída > ${ALERT_AL02_CAIDA_MAXIMA_PUNTOS} puntos."

export GF_PATHS_PROVISIONING="$DEST"
exec /run.sh "$@"
