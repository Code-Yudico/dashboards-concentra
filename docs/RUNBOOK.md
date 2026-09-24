# Runbook

> Esta versión del runbook corresponde a la rama `feature/dashboard-html-standalone` (HTML
> estático + cron, sin Grafana). Ver `docs/ARQUITECTURA.md` para el contexto de por qué existe
> esta rama alterna.

## Arranque y apagado

```bash
cp .env.example .env    # solo la primera vez; rellenar con credenciales reales
docker compose up -d --build
```

El dashboard queda disponible en `http://localhost:8081` (pide usuario/contraseña de
`NGINX_BASIC_AUTH_USER`/`NGINX_BASIC_AUTH_PASS`). `dashboard-etl` corre una extracción inicial al
arrancar (no hace falta esperar al horario del cron para ver datos la primera vez).

```bash
docker compose down       # detiene los contenedores, conserva el volumen dc_dashboard_data
docker compose down -v    # además destruye el volumen (se pierde el snapshot) — usar con cuidado
```

## Verificar conectividad a SQL Server

Desde el host (requiere `sqlcmd`/`msodbcsql18`, ya instalados en la distro WSL "dashboards"):

```bash
sqlcmd -S "$MSSQL_INTELIX_HOST,$MSSQL_INTELIX_PORT" -d "$MSSQL_INTELIX_DB" \
  -U "$MSSQL_INTELIX_USER" -P '<password>' -C \
  -Q "SELECT TOP 10 * FROM dbo.vw_dashboard_usuarios_intelix"
```

`-C` confía en el certificado del servidor (equivalente a `MSSQL_INTELIX_TRUST_CERT=yes`). Si
esto falla con error de autenticación, el problema está en la credencial o en los permisos
otorgados — no en el script `extraer_snapshot.py`.

## Verificar el snapshot y el cron de `dashboard-etl`

```bash
# Forzar una extracción manual (útil para probar cambios sin esperar al cron)
docker compose exec dashboard-etl python3 extraer_snapshot.py

# Ver el snapshot generado
docker compose exec dashboard-etl cat /data/snapshot.json | head -c 500

# Confirmar el horario programado dentro del contenedor
docker compose exec dashboard-etl cat /etc/cron.d/snapshot-cron

# Ver el log de corridas del cron (incluye la extracción inicial al arrancar)
docker compose exec dashboard-etl cat /var/log/snapshot-cron.log
```

Si `snapshot.json` no existe o está vacío, revisar primero conectividad SQL (sección anterior) —
el mismo error de credencial/base/host se manifiesta igual aquí que en Grafana (ver "Lecciones
sobre depuración de conectividad SQL Server" en `CLAUDE.md`).

## Probar el dashboard web

1. Abrir `http://localhost:8081` — debe pedir usuario/contraseña (auth básica de nginx).
2. Si no carga datos ("snapshot no tiene registros"), confirmar que `dashboard-etl` ya escribió
   `/data/snapshot.json` (sección anterior) y que el volumen `dc_dashboard_data` está compartido
   entre ambos servicios: `docker compose exec dashboard-web ls -la /usr/share/nginx/html/data`.
3. Si pide usuario/contraseña pero rechaza credenciales correctas, confirmar que
   `NGINX_BASIC_AUTH_USER`/`NGINX_BASIC_AUTH_PASS` están definidas en el `.env` — el contenedor
   se niega a arrancar si faltan (ver `web/docker-entrypoint.sh`).
4. Probar los tres selectores (agrupar por, granularidad, tipo de gráfico) y el rangeslider/zoom
   temporal del gráfico.

## Actualizar el HTML/JS del dashboard

Editar `web/index.html`, `web/app.js` o `web/style.css` y reconstruir la imagen:

```bash
docker compose up -d --build dashboard-web
```

No hace falta redeploy de `dashboard-etl` para cambios solo de frontend.

## Si cambia la IP de origen del equipo de desarrollo

La IP del equipo de desarrollo es asignada por DHCP y ya ha cambiado una vez. Si el DBA autoriza
el acceso por IP de origen (en vez de por credencial/base de datos), un cambio de IP puede romper
la conectividad sin aviso. Ante un fallo repentino de conexión que antes funcionaba:

1. Verificar la IP actual del equipo.
2. Pedir al DBA que actualice la regla de firewall/whitelist con la IP nueva, o —preferible—
   migrar la regla para que filtre por credencial en vez de por IP.

## Si rotan la contraseña de `GenJYudico` (credencial Intelix)

1. Actualizar `MSSQL_INTELIX_PASS` en el `.env` real (nunca en `.env.example`).
2. `docker compose up -d --force-recreate dashboard-etl`.
3. Forzar una extracción manual y repetir la verificación de "Verificar el snapshot y el cron".

## Desinstalación limpia (WSL2 como unidad desechable)

Desde PowerShell en Windows, con la sesión del usuario `Sistemas`:

```powershell
wsl --unregister dashboards
```

Esto elimina toda la distro (incluyendo Docker, volúmenes y el repositorio clonado dentro de
ella). El repositorio en GitHub no se ve afectado; para reconstruir el entorno, volver a crear la
distro y clonar el repo.

## Despliegue en Coolify

- Recurso Coolify de esta rama: nombre `dashboard-html-standalone`, uuid
  `ifgcpozbzayknigv2xjwxt8r` (recurso **separado** del de Grafana —
  `thoughtless-trout-wahxe3pgxybee2yx5wa3ksa9` — así que ambas ramas pueden convivir desplegadas
  al mismo tiempo en este equipo, en puertos distintos). Build pack `dockercompose`, rama
  `feature/dashboard-html-standalone`, ruta `/docker-compose.yml`, deploy key SSH compartida con
  el otro recurso (mismo repo). `is_auto_deploy_enabled` está activo: cualquier push a esta rama
  redespliega solo.
- Coolify despliega el mismo `docker-compose.yml` de este repositorio; las variables de entorno de
  producción se configuran en la UI de Coolify (pestaña **Environment Variables** del recurso),
  replicando `.env.example` — no olvidar `NGINX_BASIC_AUTH_USER`/`NGINX_BASIC_AUTH_PASS` y
  `SNAPSHOT_CRON_SCHEDULE`. Ya configuradas en este recurso.
- **Importante — no asignar dominio a este recurso.** Coolify sugiere por defecto un dominio
  público `http://<uuid>.<ip-publica-del-server>.sslip.io` para cualquier app nueva (visible en el
  campo `fqdn` de la API), pero para build pack `dockercompose` ese campo es solo informativo —
  **no se activa ningún ruteo real hasta que se llena `docker_compose_domains`** (verificado: quedó
  en `None` tras desplegar). Si en algún momento se edita este recurso desde la UI de Coolify y se
  le asigna un dominio ahí, eso expondría el dashboard a internet a través del proxy Traefik —
  contradice la decisión explícita de no exponer este equipo a internet (ver `CLAUDE.md`, sección
  "Próximos pasos"). Dejar esos campos vacíos.
- **Antes de dar por cerrado el despliegue**, validar que el servidor de Coolify tiene ruta de
  red hacia SQL Server Intelix (`$MSSQL_INTELIX_HOST:$MSSQL_INTELIX_PORT`) — es un supuesto
  externo, coordinado en paralelo con el equipo de infraestructura (ver `docs/ARQUITECTURA.md`).
- Confirmar que el volumen nombrado `dc_dashboard_data` no se destruye en cada redeploy (ahí vive
  el `snapshot.json` vigente).
- **Alcance de red actual:** igual que Grafana hoy, el puerto publicado (`8081`) solo es
  alcanzable desde este mismo equipo (`localhost:8081`) mientras WSL2 siga en modo NAT clásico.
  Para que sea alcanzable desde otros nodos de la red de oficina (el objetivo real de esta rama,
  aclarado con el usuario: no es abrirlo a "toda la compañía" como usuarios, sino a "casi
  cualquier nodo de red"), aplica el mismo pendiente ya documentado: activar
  `networkingMode=mirrored` en `.wslconfig` y abrir el puerto en el Firewall de Windows (ver
  "Próximos pasos" en `CLAUDE.md`). No se ha hecho todavía para ninguna de las dos ramas.

### Nota: el gotcha de "Preserve Repository During Deployment" de `main` no aplica igual aquí

En `main` (Grafana), Coolify limpiaba el checkout tras clonar y dejaba vacíos los bind mounts de
`grafana/provisioning`/`grafana/dashboards`, por lo que había que activar **"Preserve Repository
During Deployment"**. En esta rama, `dashboard-etl` y `dashboard-web` se **construyen** desde sus
Dockerfiles (`COPY` del HTML/JS/script dentro de la imagen), no dependen de bind mounts del
checkout en tiempo de ejecución — así que ese gotcha específico no debería reproducirse. Aun así,
**verificar tras el primer deploy** que ambas imágenes se construyeron con el contenido esperado
(ver comando abajo) antes de asumirlo — si la instancia de Coolify tiene alguna otra limpieza que
afecte el build en sí (no solo el post-deploy), sí sería un problema.

Verificación tras cada deploy nuevo:
```bash
docker exec <contenedor-dashboard-web> ls /usr/share/nginx/html
# debe listar index.html, app.js, style.css (no un directorio vacío)
docker exec <contenedor-dashboard-etl> cat /etc/cron.d/snapshot-cron
# debe mostrar el horario y las variables MSSQL_INTELIX_*, no un archivo vacío/inexistente
```

### Coolify local (provisional) — acceso y notas

- Dashboard de Coolify: `http://localhost:8000` (en este equipo, mientras dure la instancia
  provisional — ver `docs/ARQUITECTURA.md`).
- Un token de API con permisos de escritura sobre esta instancia es equivalente a tener acceso
  de administrador — no lo dejes en archivos versionados ni sin usar por más tiempo del
  necesario. Revócalo desde **Keys & Tokens → API tokens** cuando ya no lo necesites.
