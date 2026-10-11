"""Objetivo 4: medir la concentración del retraso en la red."""

import sys
from pathlib import Path

import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src import query_manager as qm        # noqa: E402
from src import stats_logic as sl          # noqa: E402

st.set_page_config(page_title="La red", page_icon="✈", layout="wide")
st.title("La concentración en la red")
st.caption("Objetivo 4 — contrastar la cuota de retraso frente a la cuota de "
           "vuelos, y determinar qué parte explica el volumen")

st.markdown("""
El **índice de concentración** de un aeropuerto es su cuota de minutos de
retraso dividida entre su cuota de vuelos operados. Un valor de **1** significa
que acumula exactamente el retraso que su volumen explica; por encima, más de
lo que le corresponde; por debajo, menos.
""")

aeropuertos = qm.consulta("""
    WITH t AS (SELECT (SELECT COUNT(*) FROM h_demoras) tv,
                      (SELECT SUM(demora_salida_min) FROM h_demoras) tm)
    SELECT a.codigo, a.ciudad, a.banda_trafico AS banda, a.orden_banda,
           a.longitud, a.latitud,
           COUNT(*)                                        AS vuelos,
           SUM(d.demora_salida_min)                        AS minutos,
           100.0 * COUNT(*) / MAX(t.tv)                    AS pct_vuelos,
           100.0 * SUM(d.demora_salida_min) / MAX(t.tm)    AS pct_retraso,
           (1.0 * SUM(d.demora_salida_min) / MAX(t.tm))
             / (1.0 * COUNT(*) / MAX(t.tv))                AS indice
    FROM h_demoras d
    JOIN h_vuelos     v ON v.vuelo_id      = d.vuelo_id
    JOIN d_aeropuerto a ON a.aeropuerto_id = v.origen_id, t
    GROUP BY 1, 2, 3, 4, 5, 6
""")

# -------------------------------------------------------------------- el mapa
st.header("La red entera, coloreada por su índice")

fig = go.Figure(go.Scattergeo(
    lon=aeropuertos["longitud"], lat=aeropuertos["latitud"],
    text=aeropuertos.apply(
        lambda f: f"{f.codigo} · {f.ciudad}<br>"
                  f"{sl.miles(f.vuelos)} vuelos<br>"
                  f"índice {sl.decimal(f.indice, 2)}", axis=1),
    hoverinfo="text",
    marker=dict(
        size=(aeropuertos["vuelos"] ** 0.5) * 0.9 + 4,
        color=aeropuertos["indice"], colorscale="RdBu_r", cmid=1.0,
        cmin=0.5, cmax=1.5, line=dict(width=0.5, color="#0A1620"),
        colorbar=dict(title="Índice", thickness=12),
    ),
))
# fitbounds encuadra automaticamente sobre los 104 aeropuertos. Fijar los
# rangos a mano dejaba el mapa del mundo entero y la red reducida a un borron.
fig.update_geos(
    projection_type="mercator", fitbounds="locations", visible=True,
    showland=True, landcolor="#13232D", showocean=True, oceancolor="#070E14",
    showcountries=True, countrycolor="#24404F", showcoastlines=True,
    coastlinecolor="#24404F", showlakes=False, bgcolor="rgba(0,0,0,0)",
)
fig.update_layout(height=460, margin=dict(l=0, r=0, t=10, b=0),
                  paper_bgcolor="rgba(0,0,0,0)", font=dict(color=sl.TEXTO))
st.plotly_chart(fig, width="stretch")
st.caption(
    "El tamaño del círculo es el volumen de salidas; el color, el índice. "
    "La red no muestra un patrón geográfico: los tonos se reparten sin "
    "relación con el tamaño ni con la posición."
)

st.divider()

# ------------------------------------------------------------------ los grandes
st.header("Los aeropuertos con más retraso acumulado")

mayores = aeropuertos.nlargest(12, "minutos")
izq, der = st.columns([3, 2])
with izq:
    fig = go.Figure()
    fig.add_bar(y=mayores["codigo"], x=mayores["pct_vuelos"],
                name="Cuota de vuelos", orientation="h", marker_color=sl.TENUE)
    fig.add_bar(y=mayores["codigo"], x=mayores["pct_retraso"],
                name="Cuota de retraso", orientation="h", marker_color=sl.ACENTO)
    fig.update_layout(barmode="group")
    fig.update_yaxes(autorange="reversed")
    st.plotly_chart(sl._base(fig, 460, "", "% del total"), width="stretch")
with der:
    st.dataframe(
        mayores.assign(
            vuelos=lambda d: d["vuelos"].map(sl.miles),
            minutos=lambda d: d["minutos"].map(sl.miles),
            indice=lambda d: d["indice"].map(lambda v: sl.decimal(v, 3)),
        )[["codigo", "ciudad", "vuelos", "minutos", "indice"]]
         .rename(columns={"codigo": "IATA", "ciudad": "Ciudad",
                          "vuelos": "Vuelos", "minutos": "Minutos",
                          "indice": "Índice"}),
        hide_index=True, width="stretch", height=440,
    )

st.success(f"""
**Las dos barras son prácticamente iguales en todos los casos.** Los cuatro
mayores aeropuertos —tres de ellos en Moscú— tienen índices de
{sl.decimal(aeropuertos.set_index('codigo').loc['DME', 'indice'], 3)},
{sl.decimal(aeropuertos.set_index('codigo').loc['SVO', 'indice'], 3)},
{sl.decimal(aeropuertos.set_index('codigo').loc['LED', 'indice'], 3)} y
{sl.decimal(aeropuertos.set_index('codigo').loc['VKO', 'indice'], 3)}.
No hay efecto de concentrador.
""")

st.divider()

# --------------------------------------------------------------- curva de Lorenz
st.header("¿Cuánta desigualdad hay, descontando el volumen?")

lorenz = qm.consulta("""
    WITH ap AS (
        SELECT a.aeropuerto_id, COUNT(*) AS vuelos,
               SUM(d.demora_salida_min) AS minutos
        FROM h_demoras d
        JOIN h_vuelos     v ON v.vuelo_id      = d.vuelo_id
        JOIN d_aeropuerto a ON a.aeropuerto_id = v.origen_id
        GROUP BY 1),
    orden AS (
        SELECT minutos, vuelos,
               ROW_NUMBER() OVER (ORDER BY minutos DESC) AS pos,
               SUM(minutos) OVER (ORDER BY minutos DESC
                   ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS acum_min,
               SUM(vuelos)  OVER (ORDER BY minutos DESC
                   ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS acum_vue,
               (SELECT SUM(minutos) FROM ap) AS tot_min,
               (SELECT SUM(vuelos)  FROM ap) AS tot_vue,
               (SELECT COUNT(*)     FROM ap) AS n
        FROM ap)
    SELECT 100.0 * pos / n              AS pct_aeropuertos,
           100.0 * acum_min / tot_min   AS pct_retraso,
           100.0 * acum_vue / tot_vue   AS pct_vuelos
    FROM orden ORDER BY pos
""")

izq, der = st.columns([3, 2])
with izq:
    fig = go.Figure()
    fig.add_scatter(x=lorenz["pct_aeropuertos"], y=lorenz["pct_retraso"],
                    mode="lines", name="Retraso acumulado",
                    line=dict(color=sl.ACENTO, width=3))
    fig.add_scatter(x=lorenz["pct_aeropuertos"], y=lorenz["pct_vuelos"],
                    mode="lines", name="Vuelos acumulados",
                    line=dict(color="#F2C14E", width=2, dash="dot"))
    fig.add_scatter(x=[0, 100], y=[0, 100], mode="lines",
                    name="Reparto uniforme",
                    line=dict(color=sl.TENUE, width=1, dash="dash"))
    st.plotly_chart(
        sl._base(fig, 420, "% acumulado", "% de aeropuertos, de mayor a menor"),
        width="stretch")
with der:
    st.markdown("""
Las dos curvas **se superponen**. La del retraso y la de los vuelos describen
casi la misma desigualdad.

Hay concentración, sí: unos pocos aeropuertos acumulan la mayor parte del
retraso. Pero es **exactamente la misma concentración que tiene el tráfico**.
Descontado el volumen, no queda nada que explicar.
""")
    mitad = lorenz[lorenz["pct_retraso"] >= 50].iloc[0]
    ochenta = lorenz[lorenz["pct_retraso"] >= 80].iloc[0]
    st.metric("Aeropuertos que acumulan el 50 % del retraso",
              f"{sl.decimal(mitad['pct_aeropuertos'], 1)} % de la red")
    st.metric("Y el 80 %", f"{sl.decimal(ochenta['pct_aeropuertos'], 1)} % de la red")

st.divider()

# -------------------------------------------------------------------- las rutas
st.header("El mismo resultado, por ruta")

rutas = qm.consulta("""
    WITH t AS (SELECT (SELECT COUNT(*) FROM h_demoras) tv,
                      (SELECT SUM(demora_salida_min) FROM h_demoras) tm)
    SELECT r.etiqueta AS ruta, COUNT(*) AS vuelos,
           SUM(d.demora_salida_min) AS minutos,
           (1.0 * SUM(d.demora_salida_min) / MAX(t.tm))
             / (1.0 * COUNT(*) / MAX(t.tv)) AS indice
    FROM h_demoras d JOIN h_vuelos v ON v.vuelo_id = d.vuelo_id
    JOIN d_ruta r ON r.ruta_id = v.ruta_id, t
    GROUP BY 1 HAVING COUNT(*) >= 30 ORDER BY minutos DESC
""")

izq, der = st.columns(2)
izq.markdown("**Las que más retraso acumulan para su volumen**")
izq.dataframe(
    rutas.nlargest(8, "indice").assign(
        vuelos=lambda d: d["vuelos"].map(sl.miles),
        indice=lambda d: d["indice"].map(lambda v: sl.decimal(v, 3)),
    )[["ruta", "vuelos", "indice"]]
     .rename(columns={"ruta": "Ruta", "vuelos": "Vuelos", "indice": "Índice"}),
    hide_index=True, width="stretch")
der.markdown("**Las que menos**")
der.dataframe(
    rutas.nsmallest(8, "indice").assign(
        vuelos=lambda d: d["vuelos"].map(sl.miles),
        indice=lambda d: d["indice"].map(lambda v: sl.decimal(v, 3)),
    )[["ruta", "vuelos", "indice"]]
     .rename(columns={"ruta": "Ruta", "vuelos": "Vuelos", "indice": "Índice"}),
    hide_index=True, width="stretch")

st.info(f"""
Sobre las **{sl.miles(len(rutas))}** rutas con al menos treinta vuelos
operados, el índice va de **{sl.decimal(rutas['indice'].min(), 2)}** a
**{sl.decimal(rutas['indice'].max(), 2)}**. Hay dispersión, pero no un grupo de
rutas problemáticas: la distribución del índice es continua y está centrada
en 1.
""")
