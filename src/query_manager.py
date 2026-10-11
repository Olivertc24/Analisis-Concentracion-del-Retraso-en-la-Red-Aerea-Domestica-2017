"""
Acceso a datos del aplicativo.

POR QUE DUCKDB SOBRE UN ARCHIVO SQLITE
--------------------------------------
El repositorio versiona `data/travel_analitica.sqlite`, de 5 MB, y no el
archivo `.duckdb` equivalente. La razon no es el tamano sino la estabilidad del
formato: SQLite garantiza compatibilidad hacia adelante desde hace dos decadas,
mientras que el formato de almacenamiento de DuckDB puede cambiar entre
versiones, y un artefacto versionado que una version futura no sepa leer deja
de ser reproducible.

Al arrancar, el aplicativo copia esas diez tablas a un DuckDB EN MEMORIA. Se
midieron las dos alternativas:

    copiar a memoria al arrancar ... 65 ms de arranque,  1 ms por consulta
    consultar el SQLite adjunto .... 14 ms de arranque,  4 ms por consulta

Se elige la primera: el arranque ocurre una vez por sesion y queda en cache,
mientras que las consultas ocurren en cada interaccion.

Asi el aplicativo es autocontenido -no necesita ningun servicio externo- y
dispone del repertorio estadistico completo de DuckDB, que es lo que el
objetivo 3 de la investigacion necesita y SQLite no tiene.

LA ZONA HORARIA
---------------
Se fija a 'Europe/Moscow', la de la red estudiada. Sin ella, proyectar un
instante a fecha desplazaria el dia y harian aparecer 62 dias de operacion
donde hay 61. El analisis no depende de ello -la fecha local ya esta
materializada en `fecha_id`- pero la columna `salida_programada` si se mostraria
en otro huso.
"""

from pathlib import Path

import duckdb
import pandas as pd
import streamlit as st

RAIZ = Path(__file__).resolve().parent.parent
BASE = RAIZ / "data" / "travel_analitica.sqlite"
ZONA = "Europe/Moscow"

TABLAS = ["d_tiempo", "d_franja", "d_aeropuerto", "d_ruta", "d_aeronave",
          "d_estado", "d_regimen", "h_vuelos", "h_demoras", "parametros"]


@st.cache_resource(show_spinner="Cargando la base analitica...")
def conexion() -> duckdb.DuckDBPyConnection:
    """DuckDB en memoria con las diez tablas del esquema en estrella."""
    if not BASE.exists():
        st.error(
            f"**No se encuentra la base analitica.**\n\n"
            f"Se esperaba en `{BASE.relative_to(RAIZ)}`. Se reconstruye "
            f"ejecutando los scripts de `Base de datos/` y copiando el "
            f"resultado a `data/`; el README lo explica paso a paso."
        )
        st.stop()

    con = duckdb.connect()
    con.execute("INSTALL sqlite; LOAD sqlite;")
    con.execute(f"SET TimeZone='{ZONA}';")
    con.execute(f"ATTACH '{BASE.as_posix()}' AS lite (TYPE sqlite, READ_ONLY);")
    for tabla in TABLAS:
        con.execute(f"CREATE TABLE {tabla} AS SELECT * FROM lite.{tabla}")
    con.execute("DETACH lite")
    return con


@st.cache_data(show_spinner=False)
def consulta(sql: str) -> pd.DataFrame:
    """
    Ejecuta y devuelve un DataFrame.

    El resultado se cachea por el TEXTO de la consulta, de modo que las paginas
    pueden repetir la misma sin coste. Un error no revienta la pagina: se
    muestra con su SQL a la vista, porque un aplicativo de investigacion debe
    poder enseñar lo que intento hacer.
    """
    try:
        return conexion().execute(sql).df()
    except Exception as error:                       # noqa: BLE001
        st.error(f"**La consulta no pudo ejecutarse.**\n\n```\n{error}\n```")
        st.code(sql, language="sql")
        st.stop()


@st.cache_data(show_spinner=False)
def parametros() -> dict[str, str]:
    """Los valores que la etapa de denormalizacion dedujo del propio dato."""
    filas = consulta("SELECT clave, valor FROM parametros")
    return dict(zip(filas["clave"], filas["valor"]))


@st.cache_data(show_spinner=False)
def universo() -> dict[str, int]:
    """Conteos de cabecera, usados en varias paginas."""
    fila = consulta("""
        SELECT (SELECT COUNT(*) FROM h_vuelos)                    AS programados,
               (SELECT COUNT(*) FROM h_demoras)                   AS operados,
               (SELECT COUNT(*) FROM d_aeropuerto)                AS aeropuertos,
               (SELECT COUNT(*) FROM d_ruta)                      AS rutas,
               (SELECT COUNT(*) FROM d_tiempo)                    AS dias,
               (SELECT SUM(hay_operados) FROM d_tiempo)           AS dias_operados,
               (SELECT SUM(demora_salida_min) FROM h_demoras)     AS minutos
    """).iloc[0]
    return {clave: int(valor) for clave, valor in fila.items()}
