"""Consulta libre sobre el esquema en estrella."""

import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src import query_manager as qm        # noqa: E402
from src import stats_logic as sl          # noqa: E402

st.set_page_config(page_title="Consulta libre", page_icon="✈", layout="wide")
st.title("Consulta libre")
st.caption("El esquema en estrella, abierto. Motor DuckDB sobre la base "
           "analítica cargada en memoria.")

EJEMPLOS = {
    "Las medidas de posición y dispersión, de una vez": """
SELECT COUNT(*)                               AS vuelos,
       ROUND(AVG(demora_salida_min), 2)       AS media,
       median(demora_salida_min)              AS mediana,
       mode(demora_salida_min)                AS moda,
       ROUND(stddev_samp(demora_salida_min), 2) AS desviacion,
       ROUND(skewness(demora_salida_min), 2)  AS asimetria,
       quantile_cont(demora_salida_min, [0.25, 0.5, 0.75, 0.95]) AS cuantiles
FROM h_demoras;""",

    "El hueco: la mayor distancia entre dos demoras consecutivas": """
WITH distintos AS (SELECT DISTINCT demora_salida_min AS m FROM h_demoras),
     saltos AS (SELECT m, LEAD(m) OVER (ORDER BY m) AS siguiente FROM distintos)
SELECT m AS fin_del_modo_bajo, siguiente AS inicio_del_modo_alto,
       siguiente - m AS amplitud
FROM saltos WHERE siguiente IS NOT NULL
ORDER BY amplitud DESC LIMIT 5;""",

    "Índice de concentración por aeropuerto": """
WITH t AS (SELECT (SELECT COUNT(*) FROM h_demoras) tv,
                  (SELECT SUM(demora_salida_min) FROM h_demoras) tm)
SELECT a.codigo, a.ciudad, a.banda_trafico,
       COUNT(*) AS vuelos,
       ROUND(100.0 * COUNT(*) / MAX(t.tv), 2)                 AS pct_vuelos,
       ROUND(100.0 * SUM(d.demora_salida_min) / MAX(t.tm), 2) AS pct_retraso,
       ROUND((1.0 * SUM(d.demora_salida_min) / MAX(t.tm))
             / (1.0 * COUNT(*) / MAX(t.tv)), 3)               AS indice
FROM h_demoras d
JOIN h_vuelos     v ON v.vuelo_id      = d.vuelo_id
JOIN d_aeropuerto a ON a.aeropuerto_id = v.origen_id, t
GROUP BY 1, 2, 3
HAVING COUNT(*) >= 100
ORDER BY indice DESC;""",

    "Cobertura del registro, día a día": """
SELECT t.fecha, t.nombre_dia, t.hay_operados,
       COUNT(*)                    AS programados,
       SUM(v.es_operado::INT)      AS con_hora_real
FROM h_vuelos v JOIN d_tiempo t ON t.fecha_id = v.fecha_id
GROUP BY 1, 2, 3 ORDER BY t.fecha;""",

    "Los ocho vuelos cancelados que sin embargo despegaron": """
SELECT v.numero_vuelo, r.etiqueta AS ruta, v.salida_programada,
       d.demora_salida_min, g.etiqueta AS regimen
FROM h_demoras d
JOIN h_vuelos  v ON v.vuelo_id   = d.vuelo_id
JOIN d_estado  e ON e.estado_id  = v.estado_id
JOIN d_ruta    r ON r.ruta_id    = v.ruta_id
JOIN d_regimen g ON g.regimen_id = d.regimen_id
WHERE e.codigo = 'Cancelled'
ORDER BY d.demora_salida_min DESC;""",
}

with st.sidebar:
    st.subheader("El esquema")
    st.markdown("""
**Hechos**
- `h_vuelos` — 33.121, el vuelo programado
- `h_demoras` — 16.773, en 1:0..1 sobre el anterior

**Dimensiones**
- `d_tiempo` · `d_franja`
- `d_aeropuerto` (rol origen y destino)
- `d_ruta` · `d_aeronave`
- `d_estado` · `d_regimen`
- `parametros`
""")
    st.caption("`h_vuelos` y `h_demoras` se reúnen por `vuelo_id`.")

elegido = st.selectbox("Consulta de ejemplo", list(EJEMPLOS))
sql = st.text_area("SQL", EJEMPLOS[elegido].strip(), height=260)

if st.button("Ejecutar", type="primary"):
    prohibidas = ("insert", "update", "delete", "drop", "alter", "create",
                  "attach", "copy", "install", "load")
    if any(p in sql.lower().split() for p in prohibidas):
        st.error(
            "**Sólo se admiten consultas de lectura.** La base vive en memoria "
            "y se reconstruye en cada sesión, pero permitir escrituras haría "
            "que una pestaña alterase lo que ve otra."
        )
    else:
        datos = qm.consulta(sql)
        st.success(f"{sl.miles(len(datos))} filas · {len(datos.columns)} columnas")
        st.dataframe(datos, width="stretch", height=420)
        st.download_button(
            "Descargar en CSV",
            datos.to_csv(index=False).encode("utf-8"),
            file_name="consulta.csv", mime="text/csv",
        )
