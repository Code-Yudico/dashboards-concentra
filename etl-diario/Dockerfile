FROM python:3.12-slim

# pyodbc necesita el driver ODBC de Microsoft (msodbcsql17) instalado en la
# imagen -- a diferencia de pymssql, no hay wheel autocontenido. Repo oficial
# de Microsoft para Debian 12 (base de python:3.12-slim).
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        cron curl ca-certificates gnupg unixodbc-dev \
    && curl -sSL https://packages.microsoft.com/config/debian/12/prod.list \
        > /etc/apt/sources.list.d/mssql-release.list \
    && mkdir -p /usr/share/keyrings \
    && curl -sSL https://packages.microsoft.com/keys/microsoft.asc \
        | gpg --dearmor -o /usr/share/keyrings/microsoft-prod.gpg \
    && apt-get update \
    && ACCEPT_EULA=Y apt-get install -y --no-install-recommends msodbcsql17 \
    && apt-get purge -y gnupg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY exportar.py .
COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

ENTRYPOINT ["docker-entrypoint.sh"]
