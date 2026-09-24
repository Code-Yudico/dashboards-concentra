#!/bin/sh
# Genera /etc/nginx/.htpasswd a partir de NGINX_BASIC_AUTH_USER/PASS al
# arrancar el contenedor, ya que la imagen base no trae esas credenciales
# horneadas (se inyectan por .env, igual que el resto de credenciales del
# proyecto).
set -eu

if [ -z "${NGINX_BASIC_AUTH_USER:-}" ] || [ -z "${NGINX_BASIC_AUTH_PASS:-}" ]; then
    echo "ERROR: NGINX_BASIC_AUTH_USER y NGINX_BASIC_AUTH_PASS son obligatorios (ver .env.example)." >&2
    exit 1
fi

htpasswd -bc /etc/nginx/.htpasswd "$NGINX_BASIC_AUTH_USER" "$NGINX_BASIC_AUTH_PASS"

exec "$@"
