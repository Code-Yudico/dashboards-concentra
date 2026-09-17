# Dashboards Concentra

Sistema de tableros de BI sobre Grafana, alimentado directamente desde SQL Server.

## Arquitectura

- **Origen**: SQL Server (acceso de solo lectura, vistas con KPIs ya agregados)
- **Visualización**: Grafana, consultando SQL Server directo vía su datasource nativo `mssql`,
  con provisioning versionado (datasources, dashboards)
- **Despliegue**: Coolify sobre Linux, desde este repositorio

MariaDB fue una hipótesis inicial de origen, descartada — el origen confirmado es únicamente
SQL Server (ver `docs/ARQUITECTURA.md`). No hay capa analítica intermedia ni ETL en esta
iteración del proyecto: el volumen y la concurrencia esperados no lo justifican todavía.

## Requisitos

- Docker Engine 24+ y Docker Compose v2
- En Windows: WSL2 con systemd habilitado

## Puesta en marcha

```bash
cp .env.example .env    # rellenar con credenciales reales
docker compose up -d
```

Grafana queda disponible en http://localhost:3000

## Documentación

- `docs/ARQUITECTURA.md` — decisiones de diseño
- `docs/RUNBOOK.md` — operación y mantenimiento
