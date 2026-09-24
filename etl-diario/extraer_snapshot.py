"""Recupera dbo.vw_dashboard_usuarios_intelix y la vuelca a un snapshot JSON.

La vista ya contiene el histórico completo (ver CLAUDE.md), así que cada
corrida trae todos los registros y sobrescribe el snapshot anterior — no hay
acumulación incremental propia.
"""

import json
import os
import sys
from datetime import date, datetime

import pymssql

COLUMNS = [
    "id_ceco",
    "ceco",
    "DeptoBiometrico",
    "alias",
    "SITE",
    "locacion",
    "Periodo",
    "Fecha",
    "num_usuarios",
]


def _json_default(value):
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    raise TypeError(f"Tipo no serializable: {type(value)!r}")


def extraer():
    conn = pymssql.connect(
        server=os.environ["MSSQL_INTELIX_HOST"],
        port=os.environ["MSSQL_INTELIX_PORT"],
        database=os.environ["MSSQL_INTELIX_DB"],
        user=os.environ["MSSQL_INTELIX_USER"],
        password=os.environ["MSSQL_INTELIX_PASS"],
        as_dict=True,
    )
    try:
        cursor = conn.cursor()
        cursor.execute(
            f"SELECT {', '.join(COLUMNS)} FROM dbo.vw_dashboard_usuarios_intelix"
        )
        filas = cursor.fetchall()
    finally:
        conn.close()
    return filas


def escribir_snapshot(filas, ruta_salida):
    payload = {
        "generado_en": datetime.now().isoformat(),
        "total_filas": len(filas),
        "registros": filas,
    }
    ruta_tmp = f"{ruta_salida}.tmp"
    with open(ruta_tmp, "w", encoding="utf-8") as f:
        json.dump(payload, f, default=_json_default, ensure_ascii=False)
    os.replace(ruta_tmp, ruta_salida)  # escritura atómica


def main():
    ruta_salida = os.environ.get("SNAPSHOT_OUTPUT_PATH", "/data/snapshot.json")
    filas = extraer()
    escribir_snapshot(filas, ruta_salida)
    print(f"Snapshot escrito: {ruta_salida} ({len(filas)} filas)", file=sys.stderr)


if __name__ == "__main__":
    main()
