"""Vuelca gc_wfm.dbo.tbl_dashboard_users_intelix (servidor 10.80.11.70,1433, instancia DEV) a datos.js
para el dashboard de web/index.html.

Logica de conteo y formato de salida portados del dashboard original
"dash_conexiones_intelix" (ver docs/ARQUITECTURA.md para la referencia) — la unica
diferencia real es de donde salen las credenciales (variables de entorno
MSSQL_INTELIX_1_* de este proyecto, no un alias en C:\\PROYECTOS\\env\\.env) y que
aqui no existe la opcion de "empaquetar" un HTML autocontenido: este script
corre en un contenedor con cron, sirviendo datos.js via nginx en vez de
generar un archivo para enviar por correo.

Formato: cada usuario es un indice entero en "reg" (asi se cuentan distintos
rapido). "uids" traduce ese indice a [id_HR, id] para la pestana de data
bruta del Excel, y "extra" guarda las filas de un id_HR que aparece con un
segundo id (duplicados del JOIN de origen). Con eso el tablero reconstruye
la tabla fila por fila.

Por que .js y no .json: mismo formato que el original por compatibilidad
con index.html tal cual (const D = window.DASH_CONEX), aunque aqui ya no es
estrictamente necesario (se sirve por HTTP, no se abre con file://).
"""

import json
import os
import sys
from collections import defaultdict
from datetime import datetime

import pyodbc

DRIVER = "{ODBC Driver 17 for SQL Server}"
BASE = os.environ.get("MSSQL_INTELIX_1_DB", "gc_wfm")
TABLA = "dbo.tbl_dashboard_users_intelix"
SIN_DATO = "Sin dato"

CONSULTA = f"""
SELECT  CONVERT(varchar(10), FECHA, 23) AS fecha,
        id_ceco, ceco, alias, DeptoBiometrico, locacion, [SITE],
        id_HR, id
FROM    {TABLA}
WHERE   FECHA IS NOT NULL AND id_HR IS NOT NULL
"""


def conectar():
    encrypt = "yes" if os.environ.get("MSSQL_INTELIX_1_ENCRYPT", "no").lower() in ("yes", "true", "1") else "no"
    trust_cert = "yes" if os.environ.get("MSSQL_INTELIX_1_TRUST_CERT", "yes").lower() in ("yes", "true", "1") else "no"
    return pyodbc.connect(
        driver=DRIVER,
        server=os.environ["MSSQL_INTELIX_1_HOST"],
        database=BASE,
        uid=os.environ["MSSQL_INTELIX_1_USER"],
        pwd=os.environ["MSSQL_INTELIX_1_PASS"],
        encrypt=encrypt,
        trustservercertificate=trust_cert,
        timeout=600,
        readonly=True,
    )


def limpio(valor):
    """Quita espacios y saltos de linea colgados (hay 'Movistar Pospago Nat\\r\\n')."""
    if valor is None:
        return SIN_DATO
    texto = " ".join(str(valor).split())
    return texto or SIN_DATO


def exportar(destino):
    with conectar() as cn:
        cur = cn.cursor()
        cur.execute(CONSULTA)
        filas = cur.fetchall()

    if not filas:
        raise SystemExit(f"{TABLA} esta vacia; no se genera datos.js.")

    # SQL Server compara sin distinguir mayusculas ('BAIT' = 'Bait'); el navegador no.
    # Cada texto se unifica a su grafia mas frecuente para que los botones no se dupliquen.
    frecuencia = [defaultdict(lambda: defaultdict(int)) for _ in range(5)]
    for fila in filas:
        textos = fila[2:7]  # ceco, alias, DeptoBiometrico, locacion, SITE
        for i, t in enumerate(textos):
            v = limpio(t)
            frecuencia[i][v.casefold()][v] += 1
    canonico = [{k: max(vs, key=vs.get) for k, vs in f.items()} for f in frecuencia]

    # Catalogo de cecos. Si un id_ceco trajera atributos distintos entre filas se
    # conserva el primero y se avisa: el tablero filtra por ceco.
    cecos = {}
    conflictos = set()
    usuarios = {}
    grupos = defaultdict(set)          # (fecha, id_ceco) -> {indice_usuario}
    ids = defaultdict(list)            # (fecha, id_ceco, indice_usuario) -> [id de users]
    frec_id = defaultdict(lambda: defaultdict(int))
    for fecha, id_ceco, ceco, alias, depto, locacion, site, id_hr, id_user in filas:
        atributos = tuple(canonico[i][limpio(t).casefold()]
                          for i, t in enumerate((ceco, alias, depto, locacion, site)))
        previo = cecos.setdefault(id_ceco, atributos)
        if previo != atributos:
            conflictos.add(id_ceco)
        u = usuarios.setdefault(str(id_hr).strip(), len(usuarios))
        grupos[(fecha, id_ceco)].add(u)
        ids[(fecha, id_ceco, u)].append(id_user)
        frec_id[u][id_user] += 1

    if conflictos:
        print(f"AVISO: {len(conflictos)} cecos con atributos distintos entre filas: "
              f"{sorted(conflictos)[:10]}. Se usa la primera combinacion.", file=sys.stderr)

    dias = sorted({f for f, _ in grupos})
    idx_dia = {d: i for i, d in enumerate(dias)}
    ids_ceco = sorted(cecos)
    idx_ceco = {c: i for i, c in enumerate(ids_ceco)}

    registros = []
    for (fecha, id_ceco), miembros in sorted(grupos.items(), key=lambda kv: (kv[0][0], kv[0][1])):
        registros.append([idx_dia[fecha], idx_ceco[id_ceco], *sorted(miembros)])

    # id principal por usuario; cada fila adicional (otro id o fila repetida) va a "extra"
    principal = {u: max(f, key=f.get) for u, f in frec_id.items()}
    extra = []
    for (fecha, id_ceco, u), lista in sorted(ids.items()):
        pendientes = list(lista)
        pendientes.remove(principal[u]) if principal[u] in pendientes else pendientes.pop(0)
        for otro in pendientes:
            extra.append([idx_dia[fecha], idx_ceco[id_ceco], u, otro])
    reconstruidas = sum(len(r) - 2 for r in registros) + len(extra)
    if reconstruidas != len(filas):
        raise SystemExit(f"La data bruta no cuadra: {reconstruidas:,} filas reconstruidas vs {len(filas):,} en la tabla.")
    # si en un usuario-dia no aparece el id principal, la fila base debe usar otro: se marca
    sin_principal = [[idx_dia[f], idx_ceco[c], u, lista[0]] for (f, c, u), lista in ids.items() if principal[u] not in lista]
    if sin_principal:
        raise SystemExit(f"{len(sin_principal)} usuario-dia sin su id principal; revisar antes de exportar.")
    por_indice = sorted(usuarios.items(), key=lambda kv: kv[1])
    uids = [[hr, principal[u]] for hr, u in por_indice]

    datos = {
        "generado": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "fuente": f"{BASE}.{TABLA} @ {os.environ['MSSQL_INTELIX_1_HOST']}",
        "filasTabla": len(filas),
        "usuarios": len(usuarios),
        "dias": dias,
        "cecos": [[c, *cecos[c]] for c in ids_ceco],   # id, ceco, alias, depto, locacion, site
        "reg": registros,                              # [dia, ceco, u1, u2, ...]
        "uids": uids,                                  # indice -> [id_HR, id]
        "extra": extra,                                # filas adicionales [dia, ceco, u, id]
    }
    cuerpo = json.dumps(datos, ensure_ascii=False, separators=(",", ":"))
    contenido = "// Generado por exportar.py - NO editar a mano.\nwindow.DASH_CONEX = " + cuerpo + ";\n"

    ruta_tmp = f"{destino}.tmp"
    with open(ruta_tmp, "w", encoding="utf-8") as f:
        f.write(contenido)
    os.replace(ruta_tmp, destino)  # escritura atomica

    usuario_dia = sum(len(r) - 2 for r in registros)
    print(f"datos.js listo: {len(filas):,} filas leidas, {usuario_dia:,} usuario-dia unicos, "
          f"{len(usuarios):,} usuarios, {len(ids_ceco)} cecos, {dias[0]} a {dias[-1]}, "
          f"{len(extra)} filas extra de id duplicado.", file=sys.stderr)


def main():
    destino = os.environ.get("SNAPSHOT_OUTPUT_PATH", "/data/datos.js")
    exportar(destino)


if __name__ == "__main__":
    main()
