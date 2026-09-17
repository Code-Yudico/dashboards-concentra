# Arquitectura

## Flujo de datos

```
SQL Server (WS-BDD-CENTRL\DATALAKE, vistas con KPIs agregados)
        │  SELECT de solo lectura (login bi_grafana_ro)
        ▼
Grafana (datasource nativo "mssql", conexión directa)
        │  provisioning versionado
        ▼
Dashboards (grafana/dashboards/*.json)
```

Grafana consulta SQL Server **directamente**, sin ninguna capa intermedia. No hay PostgreSQL
analítico ni proceso ETL en esta iteración del proyecto.

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

- **`bi_grafana_ro`** (SQL Server): único login que se solicitará al DBA. Solo lectura
  (`SELECT`), acotado a las vistas necesarias para los dashboards — no a la base completa. Será
  la credencial definitiva que use Grafana para conectarse directamente.
- **Provisional:** mientras el DBA crea `bi_grafana_ro` y confirma la base/vistas, el datasource
  usa la credencial de prueba `GenReadingServ` (solo lectura, ya validada), colocada en las
  variables `MSSQL_USER_GRAFANA`/`MSSQL_PASS_GRAFANA`. Sustituir por `bi_grafana_ro` en cuanto
  esté disponible.
- **`bi_etl_ro`**: no se solicita en esta fase. Se pedirá si se retoma la capa analítica
  intermedia (ver criterio de revisión arriba).

## Orígenes descartados

- **MariaDB** (`10.70.13.70:3306`): hipótesis inicial de origen, descartada tras confirmar que
  el origen real es SQL Server. Las variables correspondientes quedan comentadas (no eliminadas)
  en `.env.example` por si el alcance cambiara.

## Despliegue

Coolify despliega el mismo `docker-compose.yml` de este repositorio; las diferencias entre
desarrollo y producción viven únicamente en variables de entorno. La ruta de red entre el
servidor de Coolify y SQL Server es un supuesto externo que se resuelve junto con el equipo de
infraestructura — se valida antes de dar por cerrado el despliegue (ver `docs/RUNBOOK.md`).

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
