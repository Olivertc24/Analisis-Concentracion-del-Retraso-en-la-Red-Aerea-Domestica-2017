"""
Acceso a datos del aplicativo.

TODO EL TRABAJO SE CONSULTA SOBRE LA BASE DUCKDB
------------------------------------------------
El aplicativo abre `Base de datos/travel_analitica.duckdb` en modo de SOLO
LECTURA. No hay copia intermedia, ni conversion al arrancar, ni formato de
texto por el camino: la misma base que construyo `conversion_duckdb.sql` es la
que responde a cada consulta.

Eso trae dos cosas que el estudio necesita:

  EL REPERTORIO ESTADISTICO. El objetivo 3 pide evaluar si la media y la
  desviacion tipica son resumenes admisibles, y SQLite no tiene desviacion
  tipica, ni moda, ni cuantiles, ni asimetria, ni curtosis. DuckDB si.

  LOS TIPOS. Las fechas son DATE, las marcas son TIMESTAMPTZ y las banderas
  son BOOLEAN, de modo que el motor valida y compara de verdad en lugar de
  interpretar texto.

LA ZONA HORARIA
---------------
Se fija a 'Europe/Moscow', la de la red estudiada. `salida_programada` es un
TIMESTAMP WITH TIME ZONE, y DuckDB lo MUESTRA en la zona de la sesion: sin
fijarla, proyectar un instante a fecha desplazaria el dia y harian aparecer 62
dias de operacion donde hay 61. El analisis no depende de ello -la fecha local
ya esta materializada en `fecha_id`- pero la columna si.

SOLO LECTURA
------------
`read_only=True` no es una precaucion formal. Permite que varias sesiones del
aplicativo compartan el mismo archivo sin bloquearse, y hace imposible que una
consulta de la pagina de consulta libre altere lo que ve otra pestaña.
"""

from pathlib import Path

import duckdb
import pandas as pd
import streamlit as st

RAIZ = Path(__file__).resolve().parent.parent
BASE = RAIZ / "Base de datos" / "travel_analitica.duckdb"
ZONA = "Europe/Moscow"


@st.cache_resource(show_spinner="Abriendo la base analitica...")
def conexion() -> duckdb.DuckDBPyConnection:
    """La base DuckDB del esquema en estrella, en solo lectura."""
    if not BASE.exists():
        st.error(
            f"**No se encuentra la base analitica.**\n\n"
            f"Se esperaba en `{BASE.relative_to(RAIZ)}`. Se reconstruye con "
            f"los tres scripts de `Base de datos/`; el README lo explica paso "
            f"a paso."
        )
        st.stop()

    con = duckdb.connect(str(BASE), read_only=True)
    con.execute(f"SET TimeZone='{ZONA}';")
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
