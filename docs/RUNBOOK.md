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

La instancia es `WS-BDD-INTELIX\DEV`, pero se conecta por **IP+puerto** (`10.80.11.70,1433`,
puerto confirmado vía SQL Browser), igual que el resto del proyecto. **No usar
`10.80.11.70\DEV` en las variables de Coolify**: Coolify guarda la barra invertida duplicada
(`\\DEV`), el driver busca una instancia inexistente y falla con `Login timeout expired` — parece
un problema de red/firewall y no lo es (costó una tarde de diagnóstico). Desde el host (requiere
`sqlcmd`/`msodbcsql17`/`18`, ya instalados en la distro WSL "dashboards"):

```bash
sqlcmd -S "$MSSQL_INTELIX_1_HOST" -d "$MSSQL_INTELIX_1_DB" \
  -U "$MSSQL_INTELIX_1_USER" -P '<password>' -C \
  -Q "SELECT TOP 10 * FROM dbo.tbl_dashboard_users_intelix"
```

`-C` confía en el certificado del servidor (equivalente a `MSSQL_INTELIX_1_TRUST_CERT=yes`). Si
esto falla con error de autenticación, el problema está en la credencial o en los permisos
otorgados — no en el script `exportar.py`.

## Verificar `datos.js` y el cron de `dashboard-etl`

```bash
# Forzar una extracción manual (útil para probar cambios sin esperar al cron)
docker compose exec dashboard-etl python3 exportar.py

# Ver el datos.js generado (formato: window.DASH_CONEX = {...})
docker compose exec dashboard-etl cat /data/datos.js | head -c 500

# Confirmar el horario programado dentro del contenedor
docker compose exec dashboard-etl cat /etc/cron.d/snapshot-cron

# Ver el log de corridas del cron (incluye la extracción inicial al arrancar)
docker compose exec dashboard-etl cat /var/log/snapshot-cron.log
```

Si `datos.js` no existe o está vacío, revisar primero conectividad SQL (sección anterior) — el
mismo error de credencial/base/host se manifiesta igual aquí que en Grafana (ver "Lecciones sobre
depuración de conectividad SQL Server" en `CLAUDE.md`). `exportar.py` también aborta (sin escribir
`datos.js`) si la tabla está vacía, si la reconstrucción de filas no cuadra, o si algún usuario-día
queda sin su id principal — son validaciones de integridad del original, no bugs del puerto.

## Probar el dashboard web

1. Abrir `http://localhost:8081` — debe pedir usuario/contraseña (auth básica de nginx).
2. Si el dashboard queda en blanco o sin datos, confirmar que `dashboard-etl` ya escribió
   `/data/datos.js` (sección anterior) y que el volumen `dc_dashboard_data` está compartido entre
   ambos servicios: `docker compose exec dashboard-web ls -la /usr/share/nginx/html/data`.
3. Si pide usuario/contraseña pero rechaza credenciales correctas, confirmar que
   `NGINX_BASIC_AUTH_USER`/`NGINX_BASIC_AUTH_PASS` están definidas en el `.env` — el contenedor
   se niega a arrancar si faltan (ver `web/docker-entrypoint.sh`).
4. Probar los filtros desplegables (locación, DeptoBiometrico, alias, ceco), el cambio de
   granularidad (día/semana/mes), el top 15 de cecos y la descarga a Excel.

## Actualizar el dashboard (`web/index.html`)

Es un archivo único autocontenido (HTML + CSS + JS inline, sin build step). Editarlo y reconstruir
la imagen:

```bash
docker compose up -d --build dashboard-web
```

No hace falta redeploy de `dashboard-etl` para cambios solo de frontend. Para cambios a la lógica
de extracción/conteo, editar `etl-diario/exportar.py` y reconstruir ese servicio en su lugar.

## Si cambia la IP de origen del equipo de desarrollo

La IP del equipo de desarrollo es asignada por DHCP y ya ha cambiado una vez. Si el DBA autoriza
el acceso por IP de origen (en vez de por credencial/base de datos), un cambio de IP puede romper
la conectividad sin aviso. Ante un fallo repentino de conexión que antes funcionaba:

1. Verificar la IP actual del equipo.
2. Pedir al DBA que actualice la regla de firewall/whitelist con la IP nueva, o —preferible—
   migrar la regla para que filtre por credencial en vez de por IP.

## Si rotan la contraseña del origen Intelix 1

1. Actualizar `MSSQL_INTELIX_1_PASS` en el `.env` real (nunca en `.env.example`).
2. `docker compose up -d --force-recreate dashboard-etl`.
3. Forzar una extracción manual y repetir la verificación de "Verificar `datos.js` y el cron".

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
  red hacia `$MSSQL_INTELIX_1_HOST` (`10.80.11.70,1433`) — es un supuesto externo, coordinado en
  paralelo con el equipo de infraestructura (ver `docs/ARQUITECTURA.md`).
- **El auto-deploy por push no se dispara solo** en esta instancia (el repo está conectado por
  deploy key, sin webhook de GitHub). Tras cada push, desplegar desde la UI de Coolify
  ("Redeploy") o vía API: `POST /api/v1/deploy?uuid=ifgcpozbzayknigv2xjwxt8r`.
- Confirmar que el volumen nombrado `dc_dashboard_data` no se destruye en cada redeploy (ahí vive
  el `datos.js` vigente).
- **Alcance de red actual:** igual que Grafana hoy, el puerto publicado (`8081`) solo es
  alcanzable desde este mismo equipo (`localhost:8081`) mientras WSL2 siga en modo NAT clásico.
  El objetivo real de esta rama (aclarado con el usuario) no es abrirlo a "toda la compañía" como
  usuarios, sino a "casi cualquier nodo de red" de la oficina — ver la sección siguiente para
  cómo lograrlo en este equipo.

### Exponer en la red de oficina — `networkingMode=mirrored` NO es viable en este equipo

`CLAUDE.md` menciona `networkingMode=mirrored` como el plan original para esto, pero ese modo
**requiere Windows 11** (build 22621+). Este equipo es Windows 10 Pro y **no se va a actualizar a
Windows 11** (confirmado con el usuario) — descartar esa vía por completo, no solo posponerla.

**Alternativa que sí funciona en Windows 10: `netsh interface portproxy` + regla de Firewall.**
WSL2 en modo NAT le asigna a la distro una IP interna (`172.x.x.x`) que Windows sí puede
alcanzar; el truco es reenviar el tráfico que llega a la IP real del equipo (la de la red de
oficina) hacia esa IP interna, y abrir el puerto en el Firewall de Windows.

**Problema a tener presente:** esa IP interna de WSL2 **cambia en cada reinicio** de WSL (`wsl
--shutdown` o reinicio de Windows) — a diferencia de `mirrored`, este método no es "configurar
una vez y listo".

Prueba manual rápida (PowerShell **como Administrador**, con WSL corriendo):
```powershell
$wslIp = (wsl -d dashboards -- hostname -I).Trim().Split(" ")[0]
netsh interface portproxy add v4tov4 listenaddress=0.0.0.0 listenport=8081 connectaddress=$wslIp connectport=8081
New-NetFirewallRule -DisplayName "WSL-dashboards-8081" -Direction Inbound -LocalPort 8081 -Protocol TCP -Action Allow
```
Verificar desde otra máquina de la red: `http://<ip-del-equipo-en-la-red-de-oficina>:8081`.

**Para que sobreviva a reinicios:** usar `windows/wsl-portproxy.ps1` (versionado en este repo,
cubre los puertos `8081` de esta rama y `3000` de Grafana) y programarlo como **Tarea Programada
de Windows** (Task Scheduler) con disparador "Al iniciar sesión", ejecutándose como
Administrador, para que se re-ejecute automáticamente y actualice la regla con la IP nueva de
WSL2 cada vez que el equipo arranca.

### Acceso público a internet — Cloudflare Tunnel (decisión revertida sobre no exponer el equipo)

`CLAUDE.md` documentaba explícitamente posponer el acceso desde internet — este mismo equipo
tiene llaves SSH, credenciales de git y acceso a SQL Server de producción, y no se quería exponer
directamente. El usuario dio luz verde a habilitarlo para este dashboard específico, con la
condición explícita de **no** hacerlo vía port-forward directo en el router de oficina (eso sí
expondría la IP pública real del equipo — confirmada `200.188.112.154` — a cualquiera que la
escanee). En su lugar se usa **Cloudflare Tunnel**: el contenedor `cloudflared` solo abre una
conexión *saliente* hacia el borde de Cloudflare, sin abrir ningún puerto entrante en el
router/firewall de oficina. Cloudflare termina el HTTPS público con su propio certificado — por
eso el Traefik/Let's Encrypt automático de Coolify **no se usa aquí** (su challenge HTTP-01
necesita que el puerto 80 sea alcanzable desde internet, justo lo que el túnel evita); el
`docker_compose_domains` del recurso Coolify se deja vacío a propósito, igual que antes.

**MVP actual: "Quick Tunnel" (sin cuenta ni dominio).** `cloudflared` corre con
`tunnel --url http://dashboard-web:80` y Cloudflare le asigna una URL pública aleatoria
`https://<palabras>.trycloudflare.com`, con HTTPS. Para obtenerla:

```bash
docker logs $(docker ps -q -f name=cloudflared) 2>&1 | grep -o 'https://[a-z0-9-]*\.trycloudflare\.com'
```

Limitaciones aceptadas para el MVP:
- **La URL cambia cada vez que el contenedor `cloudflared` se reinicia** (redeploy, reinicio de
  WSL/Windows). Hay que volver a sacarla de los logs y re-compartirla.
- Cloudflare los ofrece "para pruebas", sin garantía de disponibilidad.

**Siguiente paso para fortalecer (cuando haga falta una URL fija):** un túnel "nombrado" en
Cloudflare Zero Trust, que sí requiere un dominio en la cuenta de Cloudflare (se compra en el
propio Cloudflare, ~10 USD/año, o se usa un subdominio de uno que la empresa ya tenga). Con eso
el comando pasa a `tunnel run --token ${CLOUDFLARE_TUNNEL_TOKEN}` y el hostname público se
apunta a `dashboard-web:80` desde el dashboard de Cloudflare. Alternativa: esperar al servidor
remoto dedicado.

**Mitigaciones aplicadas por la exposición a internet** (más allá de lo que ya bastaba para la
red de oficina):
- Contraseña de auth básica regenerada, más larga (ver `NGINX_BASIC_AUTH_PASS` en Coolify).
- `limit_req` en `web/nginx.conf`: limita a ~5 requests/min por IP tras un burst inicial de 10 —
  no afecta el uso normal (cargar la página + `datos.js`), sí frena scripts de fuerza bruta contra
  la auth básica. La IP real del visitante se toma de `CF-Connecting-IP` (si no, todo el tráfico
  del túnel compartiría un solo cupo).
- La pestaña "Data bruta" del Excel (expone `id_HR` de empleado sin filtrar) se deja **igual**
  por decisión explícita del usuario, pese a la audiencia ahora potencialmente de internet.

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
# debe listar index.html (no un directorio vacío)
docker exec <contenedor-dashboard-etl> cat /etc/cron.d/snapshot-cron
# debe mostrar el horario y las variables MSSQL_INTELIX_1_*, no un archivo vacío/inexistente
```

### Coolify local (provisional) — acceso y notas

- Dashboard de Coolify: `http://localhost:8000` (en este equipo, mientras dure la instancia
  provisional — ver `docs/ARQUITECTURA.md`).
- Un token de API con permisos de escritura sobre esta instancia es equivalente a tener acceso
  de administrador — no lo dejes en archivos versionados ni sin usar por más tiempo del
  necesario. Revócalo desde **Keys & Tokens → API tokens** cuando ya no lo necesites.
