"""Objetivo 3: caracterizar la distribución y evaluar si la media es admisible."""

import sys
from pathlib import Path

import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src import query_manager as qm        # noqa: E402
from src import stats_logic as sl          # noqa: E402

st.set_page_config(page_title="La distribución", page_icon="✈", layout="wide")
st.title("La forma de la distribución")
st.caption("Objetivo 3 — evaluar si la media y la desviación típica son "
           "resúmenes admisibles")

p = qm.parametros()
u = qm.universo()

# ------------------------------------------------------------- los estadisticos
st.header("Las medidas, una al lado de la otra")

e = qm.consulta("""
    SELECT COUNT(*)                              AS n,
           AVG(demora_salida_min)                AS media,
           median(demora_salida_min)             AS mediana,
           mode(demora_salida_min)               AS moda,
           stddev_samp(demora_salida_min)        AS desviacion,
           var_samp(demora_salida_min)           AS varianza,
           skewness(demora_salida_min)           AS asimetria,
           kurtosis(demora_salida_min)           AS curtosis,
           mad(demora_salida_min)                AS mad,
           quantile_cont(demora_salida_min, 0.25) AS q1,
           quantile_cont(demora_salida_min, 0.75) AS q3,
           quantile_cont(demora_salida_min, 0.95) AS p95,
           MIN(demora_salida_min)                AS minimo,
           MAX(demora_salida_min)                AS maximo
    FROM h_demoras
""").iloc[0]

c = st.columns(4)
c[0].metric("Media", f"{sl.decimal(e['media'])} min")
c[1].metric("Mediana", f"{sl.decimal(e['mediana'], 0)} min")
c[2].metric("Moda", f"{sl.decimal(e['moda'], 0)} min")
c[3].metric("Desviación típica", sl.decimal(e["desviacion"]))

c = st.columns(4)
c[0].metric("Coeficiente de variación",
            sl.porcentaje(100 * e["desviacion"] / e["media"]))
c[1].metric("Asimetría", sl.decimal(e["asimetria"]))
c[2].metric("Curtosis", sl.decimal(e["curtosis"]))
c[3].metric("Desviación absoluta mediana", sl.decimal(e["mad"], 0))

st.markdown(f"""
**Cuartiles.** Q1 = {sl.decimal(e['q1'], 0)}, mediana = {sl.decimal(e['mediana'], 0)},
Q3 = {sl.decimal(e['q3'], 0)}, percentil 95 = **{sl.decimal(e['p95'], 0)}**.
Rango observado: de {sl.decimal(e['minimo'], 0)} a {sl.decimal(e['maximo'], 0)} minutos.
""")

bajo_media = qm.consulta("""
    SELECT 100.0 * COUNT(*) FILTER (
             WHERE demora_salida_min < (SELECT AVG(demora_salida_min) FROM h_demoras))
           / COUNT(*) AS pct
    FROM h_demoras
""").iloc[0]["pct"]

st.error(f"""
### La media no resume: desplaza

La media es **{sl.decimal(e['media'])} minutos** y el **percentil 95** son
**{sl.decimal(e['p95'], 0)} minutos**. La media es mayor.

De ahí se sigue que el **{sl.decimal(bajo_media)} %** de los vuelos tiene una
demora **inferior** a la media. Un promedio que deja por debajo a diecinueve de
cada veinte observaciones no describe el centro de nada.

El coeficiente de variación, **{sl.porcentaje(100 * e['desviacion'] / e['media'])}**,
lo confirma: la desviación típica triplica a la media. La asimetría de
{sl.decimal(e['asimetria'])} y la curtosis de {sl.decimal(e['curtosis'])}
describen una distribución que no se parece en nada a una campana.
""")

st.divider()

# --------------------------------------------------------- tabla de frecuencias
st.header("La tabla de frecuencias")

# OJO con los nombres: DuckDB no distingue mayusculas en los alias, de modo que
# `fi` y `Fi` -la notacion habitual para la frecuencia absoluta y la acumulada-
# colisionan y una de las dos columnas desaparece. Se nombran sin ambiguedad y
# se rotulan para el lector en la tabla.
frecuencias = qm.consulta("""
    SELECT demora_salida_min AS minutos,
           COUNT(*)                                             AS frec_abs,
           100.0 * COUNT(*) / (SELECT COUNT(*) FROM h_demoras)   AS frec_rel,
           SUM(COUNT(*)) OVER (ORDER BY demora_salida_min
                               ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)
                                                                 AS frec_abs_acum,
           100.0 * SUM(COUNT(*)) OVER (ORDER BY demora_salida_min
                               ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)
             / (SELECT COUNT(*) FROM h_demoras)                  AS frec_rel_acum
    FROM h_demoras GROUP BY demora_salida_min ORDER BY demora_salida_min
""")

izq, der = st.columns([2, 3])
with izq:
    st.markdown("**Los doce primeros valores, que agotan el modo bajo**")
    st.dataframe(
        frecuencias.head(12).assign(
            frec_abs=lambda d: d["frec_abs"].map(sl.miles),
            frec_rel=lambda d: d["frec_rel"].map(lambda v: sl.decimal(v, 2)),
            frec_abs_acum=lambda d: d["frec_abs_acum"].map(sl.miles),
            frec_rel_acum=lambda d: d["frec_rel_acum"].map(lambda v: sl.decimal(v, 2)),
        ).rename(columns={"minutos": "Minutos", "frec_abs": "fi",
                          "frec_rel": "hi %", "frec_abs_acum": "Fi",
                          "frec_rel_acum": "Hi %"}),
        hide_index=True, width="stretch", height=460,
    )
with der:
    st.markdown("**La frecuencia acumulada, con el salto a la vista**")
    fig = sl.lineas(frecuencias, "minutos", "frec_rel_acum", alto=440,
                    titulo_y="Frecuencia acumulada (%)",
                    titulo_x="Demora de salida (minutos)", relleno=True)
    sl.franja_vacia(fig, int(p["hueco_desde"]), int(p["hueco_hasta"]),
                    "sin observaciones")
    st.plotly_chart(fig, width="stretch")
    st.caption(
        f"El acumulado llega al "
        f"**{sl.decimal(frecuencias[frecuencias.minutos <= 11].frec_rel_acum.max())} %** "
        f"en el minuto 11 y se queda plano durante "
        f"{p['minutos_sin_un_solo_vuelo']} minutos antes de completar el 100 %."
    )

st.divider()

# ------------------------------------------------------------------ los regimenes
st.header("Dos poblaciones, no una")

regimenes = qm.consulta("""
    SELECT g.etiqueta AS regimen, g.desde_min, g.hasta_min, g.orden,
           COUNT(*) AS vuelos,
           100.0 * COUNT(*) / (SELECT COUNT(*) FROM h_demoras) AS pct,
           AVG(d.demora_salida_min) AS media,
           SUM(d.demora_salida_min) AS minutos
    FROM h_demoras d JOIN d_regimen g ON g.regimen_id = d.regimen_id
    GROUP BY 1, 2, 3, 4 ORDER BY g.orden
""")

izq, der = st.columns([2, 3])
with izq:
    st.dataframe(
        regimenes.assign(
            intervalo=lambda d: d.apply(
                lambda f: f"{int(f.desde_min)} – {int(f.hasta_min)} min", axis=1),
            vuelos=lambda d: d["vuelos"].map(sl.miles),
            pct=lambda d: d["pct"].map(lambda v: sl.porcentaje(v)),
            minutos=lambda d: d["minutos"].map(sl.miles),
        )[["regimen", "intervalo", "vuelos", "pct", "minutos"]]
         .rename(columns={"regimen": "Régimen", "intervalo": "Intervalo",
                          "vuelos": "Vuelos", "pct": "%",
                          "minutos": "Minutos acumulados"}),
        hide_index=True, width="stretch",
    )
    st.info(f"""
**Los límites no se eligieron.** Salen de buscar la mayor distancia entre dos
valores consecutivos observados: **11 → 124**, un salto de 113 minutos, cuando
el segundo hueco mayor de toda la distribución es de **9**.
""")
with der:
    fig = go.Figure()
    for _, fila in regimenes.iterrows():
        fig.add_bar(x=[fila["regimen"]], y=[fila["vuelos"]],
                    name=fila["regimen"],
                    marker_color=sl.REGIMEN.get(fila["regimen"], sl.ACENTO),
                    text=sl.miles(fila["vuelos"]), textposition="outside")
    fig.update_yaxes(type="log")
    st.plotly_chart(sl._base(fig, 420, "Vuelos (escala logarítmica)"),
                    width="stretch")

st.warning(f"""
**La media cae en el vacío.** Entre los **{p['hueco_desde']}** y los
**{p['hueco_hasta']}** minutos no hay ni un solo vuelo de los
{sl.miles(u['operados'])} operados, y la demora media —{sl.decimal(e['media'])}
minutos— cae exactamente dentro de ese tramo.

La respuesta al objetivo 3 es, por tanto, **no**: ni la media ni la desviación
típica son resúmenes admisibles aquí. Lo que describe a esta variable es la
**mezcla de dos poblaciones**, y cada una debe resumirse por separado.
""")

por_regimen = qm.consulta("""
    SELECT g.etiqueta AS regimen, g.orden,
           AVG(d.demora_salida_min) AS media,
           median(d.demora_salida_min) AS mediana,
           stddev_samp(d.demora_salida_min) AS desviacion
    FROM h_demoras d JOIN d_regimen g ON g.regimen_id = d.regimen_id
    GROUP BY 1, 2 ORDER BY g.orden
""")
st.markdown("**Cada población, resumida por separado**")
st.dataframe(
    por_regimen.assign(
        media=lambda d: d["media"].map(lambda v: sl.decimal(v)),
        mediana=lambda d: d["mediana"].map(lambda v: sl.decimal(v, 0)),
        desviacion=lambda d: d["desviacion"].map(lambda v: sl.decimal(v)),
    )[["regimen", "media", "mediana", "desviacion"]]
     .rename(columns={"regimen": "Régimen", "media": "Media",
                      "mediana": "Mediana", "desviacion": "Desviación típica"}),
    hide_index=True, width="stretch",
)
st.caption(
    "Dentro de cada régimen la media y la mediana vuelven a parecerse, y la "
    "desviación típica recupera un tamaño interpretable. El problema nunca "
    "fue la media: era aplicarla a una mezcla."
)
