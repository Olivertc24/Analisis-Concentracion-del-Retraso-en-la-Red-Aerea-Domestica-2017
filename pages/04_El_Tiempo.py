"""Objetivo 5: describir el reparto temporal del retraso."""

import sys
from pathlib import Path

import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src import query_manager as qm        # noqa: E402
from src import stats_logic as sl          # noqa: E402

st.set_page_config(page_title="El tiempo", page_icon="✈", layout="wide")
st.title("El reparto en el tiempo")
st.caption("Objetivo 5 — franja horaria, día de la semana y día de operación")

st.info("""
**Toda esta página se restringe a los 31 días con horas reales registradas.**
La programación llega hasta el 14 de septiembre, pero el volcado se congeló el
15 de agosto. Incluir los días sin registro mostraría un desplome que no
ocurrió.
""")

# ------------------------------------------------------------------ por hora
st.header("Por hora de salida programada")

horas = qm.consulta("""
    SELECT f.franja_id AS hora, f.hora AS etiqueta, f.bloque,
           COUNT(*) AS vuelos,
           AVG(d.demora_salida_min) AS media,
           median(d.demora_salida_min) AS mediana,
           100.0 * COUNT(*) FILTER (WHERE d.regimen_id = 3) / COUNT(*) AS pct_prolongada
    FROM h_demoras d
    JOIN h_vuelos v ON v.vuelo_id  = d.vuelo_id
    JOIN d_franja f ON f.franja_id = v.franja_id
    GROUP BY 1, 2, 3 ORDER BY 1
""")

fig = go.Figure()
fig.add_bar(x=horas["etiqueta"], y=horas["vuelos"], name="Vuelos operados",
            marker_color=sl.TENUE, opacity=0.5, yaxis="y2")
fig.add_scatter(x=horas["etiqueta"], y=horas["media"], name="Demora media",
                mode="lines+markers", line=dict(color=sl.ACENTO, width=3))
fig.update_layout(
    yaxis2=dict(overlaying="y", side="right", showgrid=False,
                title="Vuelos", color=sl.TENUE))
st.plotly_chart(sl._base(fig, 400, "Demora media (minutos)", "Hora programada"),
                width="stretch")

izq, der = st.columns([2, 3])
with izq:
    pico = horas.loc[horas["media"].idxmax()]
    valle = horas.loc[horas["media"].idxmin()]
    st.metric("Hora con mayor demora media",
              f"{pico['etiqueta']} · {sl.decimal(pico['media'])} min",
              f"{sl.miles(pico['vuelos'])} vuelos", delta_color="off")
    st.metric("Hora con menor demora media",
              f"{valle['etiqueta']} · {sl.decimal(valle['media'])} min",
              f"{sl.miles(valle['vuelos'])} vuelos", delta_color="off")
with der:
    st.warning(f"""
**Cuidado con las horas de madrugada.** La hora de mayor demora media reúne
sólo **{sl.miles(pico['vuelos'])}** vuelos. Con tan pocas observaciones, un
puñado de demoras prolongadas desplaza la media entera.

Entre las **06:00 y las 20:00**, que concentran el grueso de la operación, la
demora media apenas se mueve: va de
**{sl.decimal(horas[(horas.hora >= 6) & (horas.hora <= 20)]['media'].min())}**
a **{sl.decimal(horas[(horas.hora >= 6) & (horas.hora <= 20)]['media'].max())}**
minutos.
""")

st.subheader("Agrupado por bloque, que es donde hay observaciones suficientes")
bloques = qm.consulta("""
    SELECT f.bloque, MIN(f.orden) AS orden, COUNT(*) AS vuelos,
           AVG(d.demora_salida_min) AS media,
           100.0 * COUNT(*) FILTER (WHERE d.regimen_id = 3) / COUNT(*) AS pct_prolongada
    FROM h_demoras d
    JOIN h_vuelos v ON v.vuelo_id  = d.vuelo_id
    JOIN d_franja f ON f.franja_id = v.franja_id
    GROUP BY f.bloque ORDER BY orden
""")
st.dataframe(
    bloques.assign(
        vuelos=lambda d: d["vuelos"].map(sl.miles),
        media=lambda d: d["media"].map(lambda v: sl.decimal(v)),
        pct_prolongada=lambda d: d["pct_prolongada"].map(lambda v: sl.porcentaje(v)),
    )[["bloque", "vuelos", "media", "pct_prolongada"]]
     .rename(columns={"bloque": "Bloque", "vuelos": "Vuelos",
                      "media": "Demora media (min)",
                      "pct_prolongada": "% demora prolongada"}),
    hide_index=True, width="stretch")

st.divider()

# ---------------------------------------------------------- dia de la semana
st.header("Por día de la semana")

semana = qm.consulta("""
    SELECT t.nombre_dia AS dia, MIN(t.dia_semana) AS orden, COUNT(*) AS vuelos,
           AVG(d.demora_salida_min) AS media,
           100.0 * COUNT(*) FILTER (WHERE d.regimen_id = 3) / COUNT(*) AS pct_prolongada
    FROM h_demoras d
    JOIN h_vuelos v ON v.vuelo_id = d.vuelo_id
    JOIN d_tiempo t ON t.fecha_id = v.fecha_id
    GROUP BY t.nombre_dia ORDER BY orden
""")

izq, der = st.columns(2)
izq.plotly_chart(
    sl.barras(semana, "dia", "media", color=sl.ACENTO, alto=340,
              titulo_y="Demora media (minutos)"), width="stretch")
der.plotly_chart(
    sl.barras(semana, "dia", "pct_prolongada", color=sl.REGIMEN["Demora prolongada"],
              alto=340, titulo_y="% de vuelos con demora prolongada"),
    width="stretch")

st.caption(
    f"La demora media por día va de **{sl.decimal(semana['media'].min())}** a "
    f"**{sl.decimal(semana['media'].max())}** minutos, y la proporción de "
    f"demoras prolongadas de **{sl.porcentaje(semana['pct_prolongada'].min())}** a "
    f"**{sl.porcentaje(semana['pct_prolongada'].max())}**. "
    "No hay un día peor que los demás."
)

st.divider()

# ----------------------------------------------------------------- dia a dia
st.header("Día a día, durante la ventana observada")

dias = qm.consulta("""
    SELECT t.fecha, COUNT(*) AS vuelos,
           AVG(d.demora_salida_min) AS media,
           COUNT(*) FILTER (WHERE d.regimen_id = 3) AS prolongadas
    FROM h_demoras d
    JOIN h_vuelos v ON v.vuelo_id = d.vuelo_id
    JOIN d_tiempo t ON t.fecha_id = v.fecha_id
    GROUP BY t.fecha ORDER BY t.fecha
""")

fig = go.Figure()
fig.add_bar(x=dias["fecha"], y=dias["prolongadas"],
            name="Vuelos con demora prolongada",
            marker_color=sl.REGIMEN["Demora prolongada"])
fig.add_scatter(x=dias["fecha"], y=dias["media"], name="Demora media",
                mode="lines", line=dict(color=sl.ACENTO, width=2), yaxis="y2")
fig.update_layout(yaxis2=dict(overlaying="y", side="right", showgrid=False,
                              title="Demora media (min)", color=sl.ACENTO))
st.plotly_chart(sl._base(fig, 400, "Vuelos con demora prolongada"), width="stretch")

st.success(f"""
**No hay jornadas de colapso.** Los vuelos con demora prolongada aparecen en
**los {len(dias)} días sin excepción**, entre
**{sl.miles(dias['prolongadas'].min())}** y **{sl.miles(dias['prolongadas'].max())}**
cada día. La demora media diaria se mueve entre
**{sl.decimal(dias['media'].min())}** y **{sl.decimal(dias['media'].max())}**
minutos.

Si existiera un fenómeno operativo detrás —una tormenta, un cierre de espacio
aéreo, una huelga— se vería como un pico en uno o dos días. No lo hay: el
fenómeno es **constante**.
""")
