# Arquitectura

> **Nota:** esta rama (`feature/dashboard-html-standalone`) es una **prueba de factibilidad**
> alterna a la rama `main` (Grafana). Reemplaza Grafana por un script que extrae la vista una vez
> al día y un HTML estático que la renderiza. Este documento describe la arquitectura *de esta
> rama*; ver la sección "Por qué esta rama alterna (sin Grafana)" para la comparación con `main`.

## Flujo de datos

```
SQL Server Intelix (WS-OVH-BDD-REPORT\BDD, vista vw_dashboard_usuarios_intelix)
        │  SELECT * de solo lectura (login GenJYudico / MSSQL_INTELIX_*), una vez al día (cron)
        ▼
dashboard-etl (Python + pymssql) → escribe /data/snapshot.json
        │  volumen Docker nombrado compartido (dc_dashboard_data)
        ▼
dashboard-web (nginx + auth básica) → sirve web/index.html + web/app.js
        │  fetch('./data/snapshot.json') desde el navegador
        ▼
Dashboard interactivo (Plotly.js): barras apiladas / líneas / área apilada / barras 100%
```

Igual que en `main`, no hay PostgreSQL analítico ni ETL pesado: el "proceso" es un único script
que hace `SELECT *` sobre una vista ya agregada y vuelca el resultado a JSON — la vista misma es
la única transformación de datos que existe.

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
`docs/RUNBOOK.md`), y cualquier panel nuevo se vuelve código JS a mantener en `web/app.js` en vez
de configuración declarativa.

**Alcance actual (prueba de factibilidad, corta duración):** sin retención de snapshots diarios
para auditoría histórica (un solo `snapshot.json` vigente, sobrescrito cada corrida) y sin
indicador visible de "datos desactualizados" si el cron falla (nginx sigue sirviendo el último
snapshot bueno). Si la prueba resulta exitosa y se decide formalizar esta vía en vez de Grafana,
esos dos puntos son el primer trabajo pendiente a retomar.

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

- **`MSSQL_INTELIX_*`**: credencial de prueba `GenJYudico` (personal, solo lectura, ya validada
  contra `Despliegue_BBDD.dbo.vw_dashboard_usuarios_intelix`), consumida directamente por
  `dashboard-etl` — mismo patrón que ya usa `grafana/provisioning/datasources/mssql-intelix.yaml`
  en `main`.
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
**construyen** (`build:`) a partir de sus Dockerfiles — el HTML/JS/CSS y el script Python quedan
horneados dentro de la imagen (`COPY`), no montados por bind mount en runtime. El único dato que
cambia fuera del build es `snapshot.json`, que vive en el volumen nombrado `dc_dashboard_data`.
Por eso el gotcha de "Preserve Repository During Deployment" documentado para `main` (bind mounts
de `grafana/provisioning`/`grafana/dashboards` quedando vacíos) **no aplica aquí** — el checkout
solo hace falta durante el build, no en cada arranque del contenedor. Sí sigue aplicando el
cuidado general de no destruir `dc_dashboard_data` con `docker compose down -v` (se perdería el
snapshot hasta la próxima corrida del cron).

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
  sin reenvío de puertos en Windows o el modo "mirrored" de WSL2 (no configurado actualmente en
  `.wslconfig`). Si la demo requiere que otras personas la vean desde su propia máquina en la red
  de Concentra, esto se resuelve aparte.

**Plan de migración:** en cuanto se asigne un servidor Linux remoto dedicado, reinstalar Coolify
ahí, reconectar este mismo repositorio de GitHub, y reconfigurar las variables de entorno de
producción en la nueva instancia. Nada del código de este repositorio cambia — es exactamente el
mismo `docker-compose.yml` desplegado desde una ubicación distinta.
