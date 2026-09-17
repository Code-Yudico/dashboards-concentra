# Runbook

## Arranque y apagado

```bash
cp .env.example .env    # solo la primera vez; rellenar con credenciales reales
docker compose up -d
```

Grafana queda disponible en `http://localhost:3000`.

```bash
docker compose down       # detiene los contenedores, conserva volúmenes (dashboards/config)
docker compose down -v    # además destruye los volúmenes — usar con cuidado
```

## Verificar conectividad a SQL Server

Desde el host (requiere `sqlcmd`/`msodbcsql18`, ya instalados en la distro WSL "dashboards"):

```bash
sqlcmd -S "$MSSQL_HOST,$MSSQL_PORT" -U "$MSSQL_USER_GRAFANA" -P '<password>' -C \
  -Q "SELECT TOP 10 * FROM <vista_kpi>"
```

`-C` confía en el certificado del servidor (equivalente a `MSSQL_TRUST_CERT=yes`). Si esto falla
con error de autenticación, el problema está en la credencial o en los permisos otorgados por el
DBA — no en la configuración de Grafana.

## Probar el datasource de Grafana

1. Entrar a `http://localhost:3000` con las credenciales de `GF_SECURITY_ADMIN_USER`/
   `GF_SECURITY_ADMIN_PASSWORD`.
2. **Configuration → Data Sources → SQL Server Concentra → Test**.
3. Si falla pero el `sqlcmd` de la sección anterior funcionó, revisar:
   - Que las variables `MSSQL_*` estén presentes dentro del contenedor:
     `docker compose exec grafana printenv | grep MSSQL`.
   - El mapeo de `encrypt`/`tlsSkipVerify` en
     `grafana/provisioning/datasources/mssql.yaml` contra la documentación oficial del
     datasource `mssql` de la versión de Grafana en uso — no es necesariamente un mapeo 1:1
     con `MSSQL_ENCRYPT`/`MSSQL_TRUST_CERT`.

## Agregar o actualizar un dashboard

1. Editar/crear el dashboard en la UI local de Grafana.
2. **Dashboard settings → JSON Model**, copiar el JSON.
3. Poner `"id": null` y fijar un `"uid"` estable (no dejar que Grafana lo regenere).
4. Guardar el archivo en `grafana/dashboards/<carpeta>/<nombre>.json` y commitear.
5. El provider de `grafana/provisioning/dashboards/default.yaml` lo recoge solo, cada 30 s.

**Importante:** cualquier edición hecha desde la UI después de este punto vive solo en el volumen
`dc_grafana_data`. Si no se reexporta a JSON y el volumen se destruye (`down -v`), el cambio se
pierde. El JSON versionado en git es la fuente de verdad.

## Si cambia la IP de origen del equipo de desarrollo

La IP del equipo de desarrollo es asignada por DHCP y ya ha cambiado una vez. Si el DBA autoriza
el acceso por IP de origen (en vez de por credencial/base de datos), un cambio de IP puede romper
la conectividad sin aviso. Ante un fallo repentino de conexión que antes funcionaba:

1. Verificar la IP actual del equipo.
2. Pedir al DBA que actualice la regla de firewall/whitelist con la IP nueva, o —preferible—
   migrar la regla para que filtre por credencial en vez de por IP.

## Si el DBA rota la contraseña de `bi_grafana_ro`

1. Actualizar `MSSQL_PASS_GRAFANA` en el `.env` real (nunca en `.env.example`).
2. `docker compose up -d --force-recreate grafana`.
3. Repetir la verificación de la sección "Probar el datasource de Grafana".

## Desinstalación limpia (WSL2 como unidad desechable)

Desde PowerShell en Windows, con la sesión del usuario `Sistemas`:

```powershell
wsl --unregister dashboards
```

Esto elimina toda la distro (incluyendo Docker, volúmenes y el repositorio clonado dentro de
ella). El repositorio en GitHub no se ve afectado; para reconstruir el entorno, volver a crear la
distro y clonar el repo.

## Despliegue en Coolify

- Coolify despliega el mismo `docker-compose.yml` de este repositorio; las variables de entorno
  de producción se configuran en la UI de Coolify (pestaña **Environment Variables** del
  recurso), replicando `.env.example`.
- **Antes de dar por cerrado el despliegue**, validar que el servidor de Coolify tiene ruta de
  red hacia SQL Server (`$MSSQL_HOST:$MSSQL_PORT`) — es un supuesto externo, coordinado en
  paralelo con el equipo de infraestructura (ver `docs/ARQUITECTURA.md`).
- Confirmar que el volumen nombrado `dc_grafana_data` no se destruye en cada redeploy.

### Gotcha: bind mounts de config quedan vacíos ("Preserve Repository During Deployment")

Por defecto, Coolify limpia el checkout del repositorio después de clonarlo, dejando **vacíos**
los bind mounts relativos definidos en el compose (en nuestro caso,
`./grafana/provisioning:...` y `./grafana/dashboards:...`). El síntoma es que el contenedor
levanta sano, pero Grafana no tiene ningún datasource ni dashboard cargado.

**Fix:** en la configuración de la aplicación en Coolify (Configuration → Advanced, o vía API
como campo `settings.is_preserve_repository_enabled`), activar **"Preserve Repository During
Deployment"**, y volver a desplegar. Esto aplica también al servidor remoto definitivo — no es
algo exclusivo de esta instancia provisional.

Verificación tras cada deploy nuevo:
```bash
docker exec <contenedor-grafana> find /etc/grafana/provisioning -maxdepth 3
# debe listar datasources/mssql.yaml y dashboards/default.yaml, no solo las carpetas vacías
```

### Coolify local (provisional) — acceso y notas

- Dashboard de Coolify: `http://localhost:8000` (en este equipo, mientras dure la instancia
  provisional — ver `docs/ARQUITECTURA.md`).
- Un token de API con permisos de escritura sobre esta instancia es equivalente a tener acceso
  de administrador — no lo dejes en archivos versionados ni sin usar por más tiempo del
  necesario. Revócalo desde **Keys & Tokens → API tokens** cuando ya no lo necesites.
