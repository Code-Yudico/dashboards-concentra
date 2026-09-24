# Dashboards Concentra — contexto del proyecto

Sistema de tableros de BI con Grafana, alimentado directamente desde SQL Server, desarrollado en
WSL2 con Docker Compose y desplegado (provisionalmente, ver abajo) vía Coolify.

## Arquitectura (ver detalle y justificación en `docs/ARQUITECTURA.md`)

- **Grafana consulta SQL Server directamente** (datasource nativo `mssql`, sin plugins ni
  drivers adicionales). No hay PostgreSQL analítico ni ETL en esta iteración — se descartó
  deliberadamente por sobre-ingeniería: el uso real es de 3-7 directivos consultando de forma
  esporádica KPIs ya agregados desde vistas SQL, tolerando unos segundos de carga.
- Esa decisión es revisable — ver "Criterio de revisión" en `docs/ARQUITECTURA.md` para las
  señales que ameritarían reintroducir una capa analítica intermedia.
- **WSL2 es una unidad de contención desechable.** Todo vive dentro de la distro "dashboards";
  `wsl --unregister dashboards` elimina el sistema completo sin afectar el repositorio remoto.
  **Excepción vigente:** Coolify corre provisionalmente en esta misma distro (ver sección
  Coolify abajo) — desregistrarla también destruiría esa instancia de Coolify, no solo el
  entorno de desarrollo.
- **Grafana como código.** Todo por provisioning versionado (`grafana/provisioning/`); nada se
  configura solo por UI sin reflejarse en el repo. Excepción intencional: cuentas de usuario de
  Grafana (Viewer para directivos) sí se crean por UI, no hay forma razonable de versionarlas.

## Orígenes de datos

Hay **dos datasources SQL Server independientes** en Grafana — servidores distintos, no
confundir:

### 1. SQL Server Concentra (principal) — `grafana/provisioning/datasources/mssql.yaml`
- SQL Server 2019 RTM, instancia nombrada `WS-BDD-CENTRL\DATALAKE`, expuesta en
  `10.80.12.2,54441` (IP+puerto fijo, no por SQL Browser). ~64 ms de latencia estable.
- Login definitivo pendiente: `bi_grafana_ro` (solo lectura, acotado a vistas de KPIs) — **el
  DBA todavía no lo ha creado**. Mientras tanto, `MSSQL_USER_GRAFANA`/`MSSQL_PASS_GRAFANA` usan
  la credencial de prueba `GenReadingServ` (ya validada, solo lectura).
- `MSSQL_DB` sigue vacío — aún no se ha definido qué base/vista usará el primer dashboard sobre
  este origen. Sin dashboard construido todavía.
- MariaDB (`10.70.13.70:3306`) fue una hipótesis de origen descartada. Queda comentada en
  `.env.example` por si el alcance cambiara.

### 2. SQL Server Intelix (DEV) — `grafana/provisioning/datasources/mssql-intelix.yaml`
- Servidor real: `WS-OVH-BDD-REPORT\BDD`, alcanzable en `10.80.11.73,54441` (IP+puerto fijo).
  **Cuidado:** hubo dos intentos previos con datos de conexión incorrectos
  (`10.80.11.70\DEV` y luego `10.80.11.73` sin el nombre de base correcto) que parecían errores
  de permisos pero eran simplemente host/base equivocados — ver "Lecciones" abajo.
- Base de datos: **`Despliegue_BBDD`** (doble B — "Bases de Datos" — no `Despliegue_BDD`, error
  fácil de cometer).
- Login: `GenJYudico` (credencial personal de prueba, solo lectura, validada y funcionando).
- Vista consumida: `dbo.vw_dashboard_usuarios_intelix`. Columnas: `id_ceco, ceco,
  DeptoBiometrico, alias, SITE, locacion, Periodo (texto, nombre de mes), Fecha (tipo `date`,
  sin hora), num_usuarios`.
- Dashboard construido sobre este origen: **"Usuarios Intelix"** (ver sección Dashboards abajo).

## Coolify (provisional, en este mismo equipo)

- Instalado directamente en la distro WSL2 "dashboards" (no en un servidor remoto) para tener un
  MVP de demo mientras se asigna un servidor Linux dedicado. Ver riesgos aceptados y plan de
  migración completo en `docs/ARQUITECTURA.md` ("Coolify provisional en el equipo de desarrollo").
- Dashboard de Coolify: `http://localhost:8000`. Repo conectado vía **Deploy Key** (SSH, solo
  lectura) generada en Coolify y agregada en GitHub → Settings → Deploy keys del repo.
- Recurso/aplicación en Coolify: nombre `thoughtless-trout-wahxe3pgxybee2yx5wa3ksa9`, uuid
  `wahxe3pgxybee2yx5wa3ksa9`. Build pack: Docker Compose, rama `main`, ruta `docker-compose.yml`.
- **Gotcha importante:** por defecto Coolify limpia el checkout de git después de clonarlo,
  dejando vacíos los bind mounts relativos del compose (`./grafana/provisioning`,
  `./grafana/dashboards`). Hay que activar **"Preserve Repository During Deployment"**
  (`settings.is_preserve_repository_enabled = true` en la API) para que el provisioning de
  Grafana realmente cargue. Ya está activado en el recurso actual — si se crea un recurso nuevo
  desde cero (p. ej. al migrar al servidor remoto), hay que volver a activarlo.
- **Gotcha de variables de entorno:** Coolify guarda dos juegos paralelos de env vars por
  aplicación — "Production" (el que de verdad usa el contenedor) y "Preview Deployments" (para
  despliegues por PR, que tenemos desactivados: `is_preview_deployments_enabled: false`). El
  juego "preview" no lo usa nadie; si ves variables duplicadas en la UI de Coolify, es por esto,
  no es un error. El autocompletado del navegador a veces rellena esos campos de "preview" (que
  se renderizan como `type="password"`) con contraseñas guardadas sin relación — inofensivo
  porque esa tabla nunca se lee, pero puede confundir.
- Hay un archivo `api_token-coolify` en la raíz del repo (gitignored, con `*api_token*` en
  `.gitignore`) con un token de API de Coolify de permisos amplios, usado para automatizar
  despliegues/variables durante el desarrollo. **Rotarlo o borrarlo** cuando ya no se necesite
  seguir automatizando cambios — sigue teniendo control total sobre la instancia mientras exista.

## Grafana — dashboards y lección clave sobre "Format: Time series"

- Dashboard construido: **"Usuarios Intelix"**, sobre el datasource "SQL Server Intelix (DEV)".
  Panel tipo **Time series** (Style: Bars, Stacking: Normal) con dos variables de plantilla:
  - `agrupar_por` (Custom): `Centro de costo:ceco, Depto biométrico:DeptoBiometrico,
    Alias:alias, Site:SITE, Locación:locacion` — controla por qué columna se agrupan/apilan
    las barras.
  - `granularidad` (Custom): `Día:dia, Semana:semana, Mes:mes` — controla el truncado de fecha.
  - **Pendiente:** exportar el JSON (Dashboard settings → JSON Model) y guardarlo en
    `grafana/dashboards/` para versionarlo — todavía no se ha hecho.

- **Lección más cara de esta fase (para no repetirla):** en el editor SQL en modo "Code" con
  **Format: Time series**, Grafana exige que la columna de tiempo se llame **literalmente
  `time`** (minúsculas). Cualquier otro alias (usamos `periodo` un buen rato) hace que falle con
  `"db has no time column"` — un error que aparece igual sin importar el tipo de dato real de la
  columna, sin importar si se usa `CASE`/`CAST`, e incluso con un `SELECT GETDATE() AS x`
  literal sin tabla. No es un problema de tipos ni de permisos: es únicamente el nombre del alias.
  Patrón de query que funciona (agrupando por una columna variable, con granularidad variable):
  ```sql
  SELECT
    CAST(
      CASE '${granularidad}'
        WHEN 'dia'    THEN CAST(Fecha AS date)
        WHEN 'semana' THEN DATEADD(WEEK, DATEDIFF(WEEK, 0, Fecha), 0)
        WHEN 'mes'    THEN DATEFROMPARTS(YEAR(Fecha), MONTH(Fecha), 1)
      END AS datetime2
    ) AS time,
    ${agrupar_por:raw} AS categoria,
    SUM(num_usuarios) AS total_usuarios
  FROM [dbo].[vw_dashboard_usuarios_intelix]
  WHERE $__timeFilter(Fecha)
  GROUP BY CASE '${granularidad}' WHEN 'dia' THEN CAST(Fecha AS date)
    WHEN 'semana' THEN DATEADD(WEEK, DATEDIFF(WEEK,0,Fecha),0)
    WHEN 'mes' THEN DATEFROMPARTS(YEAR(Fecha),MONTH(Fecha),1) END,
    ${agrupar_por:raw}
  ORDER BY time
  ```
  Con esta forma (tiempo, columna de texto, número), Grafana separa automáticamente una serie
  por cada valor distinto de la columna de texto — así se logra el apilado por categoría.

## Lecciones sobre depuración de conectividad SQL Server

- Un login puede autenticar correctamente contra el servidor y aun así no tener **ningún acceso**
  a una base de datos específica si no tiene un **usuario mapeado dentro de esa base** (login ≠
  usuario en SQL Server). Esto se manifiesta como `Cannot open database "X" requested by the
  login` incluso con credenciales válidas.
- Pero antes de asumir que es un problema de permisos, **verificar primero que el host, puerto y
  nombre de la base sean exactamente correctos** — en este proyecto perdimos tiempo pensando que
  era un problema de permisos cuando en realidad eran datos de conexión con errores de tipeo
  (`Despliegue_BDD` vs `Despliegue_BBDD`, y un host/instancia equivocados).
- El error `Invalid object name` (Msg 208) al referenciar una base entre bases de datos también
  puede ser SQL Server ocultando deliberadamente que no tienes permiso (no siempre significa que
  el objeto no existe).

## Entorno de desarrollo

- Equipo HP ProDesk 600 G2 SFF, Windows 10 Pro, hostname `CCN-P1-M01-01`, usuario Windows
  `Sistemas`.
- WSL2, distro "dashboards" (Ubuntu 24.04) en `D:\wsl\distros`, usuario Linux `pepe`, systemd
  activo. Repositorio en `~/proyectos/dashboards-concentra` (dentro de Linux, NO en `/mnt/c`).
- Red WSL2 actualmente en modo NAT clásico (no "mirrored") — por eso Grafana solo es alcanzable
  como `localhost:3000` desde la propia PC, no desde otras computadoras de la red.
  **`networkingMode=mirrored` no es viable en este equipo** (requiere Windows 11 build 22621+;
  este equipo es Windows 10 Pro y no se va a actualizar). La vía real para exponerlo en la red de
  oficina es `netsh interface portproxy` + regla de Firewall (script
  `windows/wsl-portproxy.ps1`, rama `feature/dashboard-html-standalone`), ver "Próximos pasos".
- Docker sin sudo, Compose v2+. `sqlcmd`/`msodbcsql18` instalados en el host WSL para pruebas de
  conectividad manuales (no se usan dentro de ningún contenedor — Grafana no depende de ellos).
- Repo: `github.com:Code-Yudico/dashboards-concentra` (privado), SSH, rama `main`.
- `.gitattributes` fuerza LF en todo el texto del repo; scripts `.bat`/`.ps1` son la única
  excepción (CRLF).
- `.env` nunca se versiona; `.env.example` sí, y debe mantenerse sincronizado con cualquier
  variable nueva que se introduzca.

## Estructura del repositorio

```
docker-compose.yml              único servicio activo: grafana (con env vars de ambos orígenes)
.env.example                    plantilla de variables (MariaDB comentado, sin Postgres/ETL;
                                 bloque MSSQL_INTELIX_* documentado como patrón replicable)
api_token-coolify                token de API de Coolify (gitignored, NO versionado)
grafana/
  provisioning/
    datasources/
      mssql.yaml                 datasource → SQL Server Concentra (principal)
      mssql-intelix.yaml         datasource → SQL Server Intelix (DEV)
    dashboards/default.yaml      provider de dashboards por archivo (carpeta "Concentra")
    alerting/                    vacía — fuera de alcance por ahora
  dashboards/                    dashboards JSON versionados — AÚN VACÍO, falta exportar
                                  "Usuarios Intelix"
docs/
  ARQUITECTURA.md                decisiones de diseño y su justificación
  RUNBOOK.md                     operación, troubleshooting, mantenimiento (incluye el gotcha
                                  de "Preserve Repository During Deployment")
db/init/, etl/                   existen localmente pero vacías y sin trackear en git —
                                  reservadas para si se retoma una capa analítica intermedia
```

## Estado actual / próximos pasos

- [x] Grafana corriendo (vía Coolify, provisional en este equipo).
- [x] Datasource "SQL Server Concentra" (principal) provisionado y probado (con credencial de
  prueba `GenReadingServ`); sin dashboard construido todavía; `bi_grafana_ro` sigue pendiente
  del DBA.
- [x] Datasource "SQL Server Intelix (DEV)" provisionado, probado y funcionando con datos reales.
- [x] Primer dashboard construido ("Usuarios Intelix") con apilado por categoría y granularidad
  de tiempo seleccionables.
- [ ] **Exportar y versionar** el dashboard "Usuarios Intelix" en `grafana/dashboards/`.
- [ ] **Exponer Grafana en la red de la oficina**: activar `networkingMode=mirrored` en
  `.wslconfig`, abrir el puerto 3000 en el Firewall de Windows, actualizar `GF_SERVER_ROOT_URL`
  a la IP real de la PC, redeploy.
- [ ] **Crear cuentas Viewer** en Grafana (Administration → Users and access → Users) para cada
  directivo — self-registration está desactivado (`GF_USERS_ALLOW_SIGN_UP=false`), así que se
  crean manualmente una por una.
- [ ] Acceso desde fuera de la oficina (internet) para Grafana/`main`: sigue **pospuesto** hasta
  que se asigne el servidor remoto dedicado — no se va a exponer este equipo de desarrollo a
  internet directamente (riesgo de seguridad: esta PC también tiene llaves SSH, credenciales de
  git y acceso a SQL Server de producción). **Excepción puntual:** en la rama
  `feature/dashboard-html-standalone` sí se habilitó acceso a internet para ese dashboard
  específico, vía Cloudflare Tunnel (conexión saliente únicamente, sin abrir puertos en el
  router) — decisión explícita del usuario para ese caso, ver `docs/RUNBOOK.md` en esa rama.
- [ ] Despliegue en el servidor remoto definitivo — sigue pendiente de que se asigne esa máquina;
  cuando exista, se reinstala Coolify ahí (recordar activar de nuevo "Preserve Repository During
  Deployment") y se reconecta el mismo repositorio.

## Notas operativas

- Arrancar WSL siempre desde la sesión de Windows del usuario `Sistemas` (las distros se
  registran por usuario).
- `docker compose down` conserva volúmenes; `down -v` los destruye.
- El terminal de WSL maltrata los heredocs pegados — usar un editor de archivos para contenido
  multilínea en vez de pegarlo directo en la terminal.
- Nunca compartir contraseñas reales en comandos pegados directamente en la conversación/terminal
  compartida — quedan visibles en el historial de la sesión. Si esto pasa por accidente, rotar la
  credencial afectada.
