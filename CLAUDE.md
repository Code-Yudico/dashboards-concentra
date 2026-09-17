# Dashboards Concentra — contexto del proyecto

Sistema de tableros de BI con Grafana, alimentado directamente desde SQL Server, desarrollado en
WSL2 con Docker Compose y desplegado en producción vía Coolify sobre un servidor Linux remoto.

## Arquitectura (ver detalle y justificación en `docs/ARQUITECTURA.md`)

- **Grafana consulta SQL Server directamente** (datasource nativo `mssql`, sin plugins ni
  drivers adicionales). No hay PostgreSQL analítico ni ETL en esta iteración — se descartó
  deliberadamente por sobre-ingeniería: el uso real es de 3-7 directivos consultando de forma
  esporádica KPIs ya agregados desde vistas SQL, tolerando unos segundos de carga.
- Esa decisión es revisable — ver "Criterio de revisión" en `docs/ARQUITECTURA.md` para las
  señales que ameritarían reintroducir una capa analítica intermedia.
- **Coolify NO se instala localmente.** Desarrollo con Docker Compose; en producción Coolify
  despliega el mismo `docker-compose.yml` desde GitHub. Las diferencias entre entornos viven
  solo en variables de entorno.
- **WSL2 es una unidad de contención desechable.** Todo vive dentro de la distro "dashboards";
  `wsl --unregister dashboards` elimina el sistema completo sin afectar el repositorio remoto.
  **Excepción temporal:** mientras Coolify corra provisionalmente en esta misma distro (ver
  abajo), desregistrarla también destruiría esa instancia de Coolify — no solo el entorno de
  desarrollo.
- **Grafana como código.** Todo por provisioning versionado (`grafana/provisioning/`); nada se
  configura solo por UI sin reflejarse en el repo.

## Origen de datos

- SQL Server 2019 RTM, instancia nombrada `WS-BDD-CENTRL\DATALAKE`, expuesta en
  `10.80.12.2,54441` (IP+puerto fijo, no por SQL Browser). Developer Edition, ~64 ms de latencia
  estable desde el equipo de desarrollo.
- Login usado por Grafana: `bi_grafana_ro`, solo lectura, acotado a las vistas de KPIs (no a la
  base completa). Es el único login solicitado en esta fase — ver `docs/ARQUITECTURA.md`.
- MariaDB (`10.70.13.70:3306`) fue una hipótesis de origen descartada. Queda comentada en
  `.env.example` por si el alcance cambiara.

## Entorno de desarrollo

- Equipo HP ProDesk 600 G2 SFF, Windows 10 Pro, hostname `CCN-P1-M01-01`, usuario Windows
  `Sistemas`.
- WSL2, distro "dashboards" (Ubuntu 24.04) en `D:\wsl\distros`, usuario Linux `pepe`, systemd
  activo. Repositorio en `~/proyectos/dashboards-concentra` (dentro de Linux, NO en `/mnt/c`).
- Docker sin sudo, Compose v2+. `sqlcmd`/`msodbcsql18` instalados en el host WSL para pruebas de
  conectividad manuales (no se usan dentro de ningún contenedor — Grafana no depende de ellos).
- Repo: `github.com:Code-Yudico/dashboards-concentra` (privado), SSH, rama `main`.
- `.gitattributes` fuerza LF en todo el texto del repo (evita problemas de CRLF en contenedores
  Linux); scripts `.bat`/`.ps1` son la única excepción (CRLF).
- `.env` nunca se versiona; `.env.example` sí, y debe mantenerse sincronizado con cualquier
  variable nueva que se introduzca.

## Estructura del repositorio

```
docker-compose.yml              único servicio activo: grafana
.env.example                    plantilla de variables (MariaDB comentado, sin Postgres/ETL)
grafana/
  provisioning/
    datasources/mssql.yaml      datasource directo a SQL Server
    dashboards/default.yaml     provider de dashboards por archivo (carpeta "Concentra")
    alerting/                   vacía — fuera de alcance por ahora
  dashboards/                   dashboards JSON versionados (fuente de verdad)
docs/
  ARQUITECTURA.md               decisiones de diseño y su justificación
  RUNBOOK.md                    operación, troubleshooting, mantenimiento
db/init/, etl/                  existen localmente pero vacías y sin trackear en git —
                                 reservadas para si se retoma una capa analítica intermedia
                                 (ver criterio de revisión en docs/ARQUITECTURA.md)
```

## Estado actual / próximos pasos

Ver `/home/pepe/.claude/plans/tus-instrucciones-y-contexto-effervescent-harbor.md` para el plan
detallado paso a paso. Resumen:

- [x] Grafana en Docker Compose, con provisioning de dashboards.
- [x] Datasource `mssql` provisionado apuntando a SQL Server.
- [ ] **Pendiente (acción humana, no técnica):** el DBA debe crear el login `bi_grafana_ro` con
  `SELECT` acotado a las vistas de KPIs, y confirmar/crear esas vistas. Sin esto, el datasource
  no puede probarse con datos reales.
- [ ] Primer dashboard versionado (`grafana/dashboards/`) una vez el datasource esté validado.
- [ ] Despliegue en Coolify — **decisión temporal:** se instala Coolify provisionalmente en este
  mismo equipo (WSL2 "dashboards") para tener un MVP de demo, mientras se asigna un servidor Linux
  remoto dedicado. Ver riesgos aceptados y plan de migración en `docs/ARQUITECTURA.md`
  ("Coolify provisional en el equipo de desarrollo"). Cuando se asigne el servidor remoto, se
  reinstala Coolify ahí y se reconecta el mismo repositorio — sin cambios de código.

## Notas operativas

- Arrancar WSL siempre desde la sesión de Windows del usuario `Sistemas` (las distros se
  registran por usuario).
- `docker compose down` conserva volúmenes; `down -v` los destruye.
- El terminal de WSL maltrata los heredocs pegados — usar un editor de archivos para contenido
  multilínea en vez de pegarlo directo en la terminal.
