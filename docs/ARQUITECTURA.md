# Arquitectura

> **Nota:** esta rama (`feature/dashboard-html-standalone`) es una **prueba de factibilidad**
> alterna a la rama `main` (Grafana). Reemplaza Grafana por un script que extrae la vista una vez
> al día y un HTML estático que la renderiza. Este documento describe la arquitectura *de esta
> rama*; ver la sección "Por qué esta rama alterna (sin Grafana)" para la comparación con `main`.

## Flujo de datos

```
SQL Server Intelix 1 (10.80.11.70,1433 — instancia WS-BDD-INTELIX\DEV, gc_wfm.dbo.tbl_dashboard_users_intelix)
        │  SELECT de solo lectura (MSSQL_INTELIX_1_*), una vez al día (cron)
        ▼
dashboard-etl (Python + pyodbc) → limpia/canonicaliza texto, arma catálogo de
        │  cecos, cuenta id_HR distintos por índice → escribe /data/datos.js
        │  volumen Docker nombrado compartido (dc_dashboard_data)
        ▼
dashboard-web (nginx + auth básica) → sirve web/index.html (autocontenido)
        │  <script src="data/datos.js"> — sin fetch, sin librería de gráficos externa
        ▼
Dashboard interactivo: barras por día/semana/mes con id_HR únicos, filtros
por locación/DeptoBiometrico/alias/ceco, top 15 de cecos, descarga a Excel
```

No hay PostgreSQL analítico ni ETL pesado: `exportar.py` hace una sola consulta de solo lectura y
transforma el resultado en memoria (deduplicación, catálogo de cecos, indexado compacto) — no hay
job intermedio, tabla de staging ni motor de transformación separado.

## Origen: dashboard portado de un proyecto existente

El dashboard actual de esta rama (`web/index.html`, la lógica de `etl-diario/exportar.py`) está
**portado casi sin cambios** de un proyecto local de un compañero (`dash_conexiones_intelix`,
carpeta `DashboardsGUs` en su OneDrive, repo git local sin remoto). Es un dashboard ya maduro y
probado, con lógica de conteo cuidadosamente pensada — se prefirió portarlo en vez de rehacerlo.

Qué cambió al portarlo (todo lo demás es igual):
- **Credenciales**: el original lee un archivo `C:\PROYECTOS\env\.env` con alias por servidor
  (`conexion.py`); aquí se leen directo de las variables `MSSQL_INTELIX_1_*` del entorno del
  contenedor — no se replicó su capa de alias porque este proyecto ya tiene su propio patrón
  (`MSSQL_<NOMBRE>_*`, ver `.env.example`) y no hace falta soportar múltiples servidores.
- **Driver**: se mantuvo `pyodbc` + `ODBC Driver 17 for SQL Server` (no `pymssql`, que usa el
  resto de esta rama) porque es el driver ya validado por el original contra este servidor
  específico (`10.80.11.70\DEV`, instancia nombrada sin puerto fijo) — cambiarlo habría sido
  reintroducir un riesgo de conectividad ya resuelto. Esto hace la imagen de `dashboard-etl` más
  pesada (hay que instalar el driver de Microsoft en el `Dockerfile`).
- **Salida**: se quitó la función `empaquetar()` (generaba un HTML con los datos incrustados para
  mandar por correo) — no aplica aquí, el dashboard se sirve por HTTP permanentemente. El formato
  de datos (`datos.js`, variable global `window.DASH_CONEX`) se mantuvo igual aunque ya no hace
  falta el truco de evitar `fetch()` bajo `file://` — cambiar el formato habría significado tocar
  el JS de parseo de `index.html`, que no se quiso modificar.
- `index.html` se copió intacto salvo **una línea**: `<script src="datos.js">` →
  `<script src="data/datos.js">`, para apuntar al subdirectorio donde nginx monta el volumen
  compartido (mismo patrón que ya se usaba para `snapshot.json` en la versión anterior de esta
  rama).

**Cómo cuenta usuarios (importante, distinto de una simple suma):** cuenta `id_HR` (identificador
de empleado) **distintos**, no filas — la tabla de origen trae duplicados reales (mismo `id_HR`
con dos `id` de la tabla de usuarios). Semana (ISO, lunes a domingo) y mes cuentan personas
distintas del periodo completo, no la suma de los días — alguien conectado toda la semana cuenta
una vez, no siete. Los textos (`ceco`, `alias`, `DeptoBiometrico`, `locacion`, `SITE`) se
normalizan sin distinguir mayúsculas/minúsculas (igual que la comparación de SQL Server) y se
unifican a su grafía más frecuente, para que los filtros no se dupliquen por diferencias de
capitalización.

**Nota de privacidad:** la pestaña "Data bruta" del Excel exportado incluye `id_HR` e `id` de
**todas** las filas, sin filtrar — es dato de empleado. Antes se distribuía por correo a un grupo
chico; ahora queda detrás de la misma auth básica que el resto del dashboard, accesible a
cualquiera con esa credencial compartida en la red de oficina. Decisión tomada con el usuario:
mantenerlo así porque la audiencia real sigue siendo el mismo grupo de confianza (<10 personas)
que ya lo recibía por correo — revisar si la audiencia cambia.

## Por qué esta rama alterna (sin Grafana)

Objetivo: validar si, para este caso de uso puntual (serie temporal de licencias por cliente,
actualizada una vez al día), una solución sin motor de dashboards es viable y más simple de
operar/desplegar. Los consumidores siguen siendo un grupo pequeño (menos de 10 personas,
consultando ~1 vez al día) — la diferencia frente a Grafana no es el número de usuarios sino el
**alcance de red**: se busca que sea accesible desde prácticamente cualquier nodo de la red de la
empresa (no solo desde este equipo/`localhost`), lo cual es justamente lo que hace más relevante
la auth básica (ver más abajo) — la superficie de red expuesta es mayor aunque el número de
personas no cambie.

Lo que se gana frente a Grafana: cero dependencia de un motor de dashboards completo (una imagen
menos, sin provisioning de datasources/paneles), y control total sobre la interacción del gráfico
(zoom, tipo de gráfico, subdivisión por categoría) sin las limitaciones de las variables de
plantilla de Grafana.

Lo que se pierde: exploración ad-hoc de los datos (editar queries/paneles sin tocar código),
gestión de usuarios individual (aquí es una sola credencial de auth básica compartida — ver
`docs/RUNBOOK.md`), y cualquier cambio al dashboard se vuelve código JS a mantener en
`web/index.html` en vez de configuración declarativa.

**Alcance actual (prueba de factibilidad, corta duración):** sin retención de snapshots diarios
para auditoría histórica (un solo `datos.js` vigente, sobrescrito cada corrida) y sin indicador
visible de "datos desactualizados" si el cron falla (nginx sigue sirviendo el último bueno). Si la
prueba resulta exitosa y se decide formalizar esta vía en vez de Grafana, esos dos puntos son el
primer trabajo pendiente a retomar.

## Por qué no hay capa analítica intermedia (todavía)

La primera versión de este proyecto contemplaba una capa PostgreSQL intermedia obligatoria,
alimentada por un ETL en Python, motivada por una latencia de ~64 ms hacia el SQL Server de
origen. Esa decisión se revisó al aclarar el contexto real de uso:

- El dashboard lo consultan entre 3 y 7 directivos, de forma esporádica.
- Unos segundos de carga son aceptables para ese uso.
- Los paneles consultan KPIs ya agregados desde vistas SQL, no tablas de alto volumen.

Bajo esas condiciones, construir un ETL, una base Postgres y el driver ODBC de Microsoft en un
contenedor Python (la parte de mayor fricción técnica del diseño original) habría sido
sobre-ingeniería para el problema actual. Grafana incluye de forma nativa un datasource tipo
`mssql` (sin plugins ni drivers externos que instalar), así que la ruta directa cubre el
requerimiento con muchísima menos superficie de mantenimiento.

## Criterio de revisión — cuándo reintroducir una capa analítica

Esta decisión no es definitiva. Revisar introducir PostgreSQL + ETL si ocurre alguna de estas
señales:

- La concurrencia de usuarios crece de forma sostenida más allá de un puñado de directivos.
- Las vistas de origen ya no bastan y se necesita cómputo/transformación pesada que no tiene
  sentido resolver en SQL Server bajo demanda.
- El DBA reporta carga notable en SQL Server atribuible a las consultas de los dashboards.
- Se necesita interactividad casi en tiempo real (sub-segundo) que la latencia de origen no
  permite alcanzar consultando en vivo.

Cuando se cumpla alguno de estos puntos, retomar el diseño de `db/init/` (esquema
staging/marts/meta) y `etl/` (extractores/transformadores/cargadores) descrito en el historial
del proyecto — esas carpetas existen localmente pero no están versionadas en git hasta que se
implementen.

## Credenciales

Esta rama solo usa el origen **SQL Server Intelix (DEV)** — no toca el datasource "Concentra"
(principal) ni sus variables `MSSQL_HOST`/`MSSQL_USER_GRAFANA`, que son exclusivas de `main`.

- **`MSSQL_INTELIX_1_*`**: credencial contra `10.80.11.70,1433` (instancia `DEV`) / `gc_wfm`, consumida directamente
  por `dashboard-etl` (pyodbc). Servidor y base distintos de los que usa `main` para Grafana — ver
  "Origen: dashboard portado de un proyecto existente" arriba.
- **`NGINX_BASIC_AUTH_USER`/`NGINX_BASIC_AUTH_PASS`**: credencial compartida (no individual) para
  la auth básica del dashboard web — ver "Por qué esta rama alterna" arriba sobre esta limitación
  frente a las cuentas Viewer de Grafana.

## Orígenes descartados

- **MariaDB** (`10.70.13.70:3306`): hipótesis inicial de origen, descartada tras confirmar que
  el origen real es SQL Server. Las variables correspondientes quedan comentadas (no eliminadas)
  en `.env.example` por si el alcance cambiara.

## Despliegue

Coolify despliega el mismo `docker-compose.yml` de este repositorio; las diferencias entre
desarrollo y producción viven únicamente en variables de entorno. La ruta de red entre el
servidor de Coolify y SQL Server es un supuesto externo que se resuelve junto con el equipo de
infraestructura — se valida antes de dar por cerrado el despliegue (ver `docs/RUNBOOK.md`).

**Diferencia clave frente a `main`:** en esta rama `dashboard-etl` y `dashboard-web` se
**construyen** (`build:`) a partir de sus Dockerfiles — el HTML y el script Python quedan
horneados dentro de la imagen (`COPY`), no montados por bind mount en runtime. El único dato que
cambia fuera del build es `datos.js`, que vive en el volumen nombrado `dc_dashboard_data`. Por eso
el gotcha de "Preserve Repository During Deployment" documentado para `main` (bind mounts de
`grafana/provisioning`/`grafana/dashboards` quedando vacíos) **no aplica aquí** — el checkout solo
hace falta durante el build, no en cada arranque del contenedor. Sí sigue aplicando el cuidado
general de no destruir `dc_dashboard_data` con `docker compose down -v` (se perdería el dato hasta
la próxima corrida del cron).

### Coolify provisional en el equipo de desarrollo (decisión temporal)

La intención original era instalar Coolify en un servidor Linux remoto dedicado, separado del
equipo de desarrollo (ver "WSL2 como unidad de contención desechable" en `CLAUDE.md`). Se decidió
instalar Coolify **provisionalmente en este mismo equipo** (WSL2, distro "dashboards") para tener
un MVP funcional con el que hacer una demo, antes de que se asigne el servidor remoto definitivo.

Esto es una excepción temporal, no un cambio de la arquitectura objetivo. Riesgos aceptados
conscientemente mientras dure:

- **Se rompe la disposabilidad de WSL2**: si se ejecuta `wsl --unregister dashboards`, se pierde
  también esta instancia de Coolify (no solo el entorno de desarrollo). Evitar desregistrar la
  distro mientras esta sea la única instancia de Coolify.
- **Confiabilidad**: es un escritorio Windows 10 Pro de uso diario, no un servidor dedicado —
  reinicios, actualizaciones de Windows o que el equipo se apague tumban la demo.
- **Alcance de red**: WSL2 usa NAT por defecto; el equipo no es visible desde el resto de la red
  sin reenvío de puertos en Windows. El modo "mirrored" de WSL2 **no es viable en este equipo**
  (requiere Windows 11, este es Windows 10 y no se va a actualizar) — la vía real es
  `netsh interface portproxy` + regla de Firewall, ver `docs/RUNBOOK.md`.
- **Acceso desde internet — decisión revertida para este dashboard.** `CLAUDE.md` posponía
  explícitamente exponer este equipo a internet, precisamente por los riesgos de esta sección
  (llaves SSH, credenciales de git, acceso a SQL Server de producción, todo en la misma máquina).
  El usuario autorizó habilitarlo específicamente para este dashboard, con Cloudflare Tunnel (sin
  abrir puertos entrantes en el router — ver `docs/RUNBOOK.md`) en vez de port-forward directo,
  para no reintroducir el riesgo original de exponer la IP pública del equipo. Sigue siendo un
  riesgo mayor que antes (ahora hay una vía de entrada pública, aunque acotada); revisar si en
  algún momento se prefiere esperar al servidor remoto dedicado en vez de mantenerla aquí.

**Plan de migración:** en cuanto se asigne un servidor Linux remoto dedicado, reinstalar Coolify
ahí, reconectar este mismo repositorio de GitHub, y reconfigurar las variables de entorno de
producción en la nueva instancia. Nada del código de este repositorio cambia — es exactamente el
mismo `docker-compose.yml` desplegado desde una ubicación distinta.
