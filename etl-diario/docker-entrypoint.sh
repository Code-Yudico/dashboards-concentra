#!/bin/sh
# Genera el crontab a partir de SNAPSHOT_CRON_SCHEDULE y las credenciales del
# entorno (cron no hereda las env vars del contenedor por defecto: se
# declaran directamente dentro del archivo de /etc/cron.d, formato que cron
# soporta de forma nativa). Luego corre una extracción inicial al arrancar
# (para no esperar hasta el próximo horario) y deja cron corriendo en primer
# plano.
set -eu

CRON_FILE=/etc/cron.d/snapshot-cron
SCHEDULE="${SNAPSHOT_CRON_SCHEDULE:-0 6 * * *}"
OUTPUT_PATH="${SNAPSHOT_OUTPUT_PATH:-/data/datos.js}"

{
    echo "MSSQL_INTELIX_1_HOST=${MSSQL_INTELIX_1_HOST}"
    echo "MSSQL_INTELIX_1_DB=${MSSQL_INTELIX_1_DB}"
    echo "MSSQL_INTELIX_1_USER=${MSSQL_INTELIX_1_USER}"
    echo "MSSQL_INTELIX_1_PASS=${MSSQL_INTELIX_1_PASS}"
    echo "MSSQL_INTELIX_1_ENCRYPT=${MSSQL_INTELIX_1_ENCRYPT}"
    echo "MSSQL_INTELIX_1_TRUST_CERT=${MSSQL_INTELIX_1_TRUST_CERT}"
    echo "SNAPSHOT_OUTPUT_PATH=${OUTPUT_PATH}"
    echo "${SCHEDULE} root cd /app && python3 exportar.py >> /var/log/snapshot-cron.log 2>&1"
} > "$CRON_FILE"
chmod 0644 "$CRON_FILE"

touch /var/log/snapshot-cron.log

echo "Extraccion inicial al arrancar el contenedor..."
python3 exportar.py >> /var/log/snapshot-cron.log 2>&1 || echo "Extraccion inicial fallo, revisa /var/log/snapshot-cron.log" >&2

cron
tail -F /var/log/snapshot-cron.log
