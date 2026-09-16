# Dashboards Concentra

Sistema de tableros de BI sobre Grafana, alimentado desde SQL Server y MariaDB.

## Arquitectura

- **Origen**: SQL Server y MariaDB (acceso de solo lectura)
- **Ingesta**: procesos Python containerizados
- **Almacén analítico**: PostgreSQL
- **Visualización**: Grafana, con provisioning versionado
- **Despliegue**: Coolify sobre Linux, desde este repositorio

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
