"""
Portada del aplicativo.

Presenta el hallazgo que ordena toda la investigacion antes que cualquier otra
cosa: el retraso NO se concentra en la red, y la estructura que si existe esta
en la forma de la distribucion.
"""

import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent))
from src import query_manager as qm        # noqa: E402
from src import stats_logic as sl          # noqa: E402

st.set_page_config(
    page_title="Concentracion del retraso en la red aerea",
    page_icon="✈",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.image("assets/banner_retraso.png", width="stretch")

u = qm.universo()
p = qm.parametros()

st.markdown(
    "### ¿Dónde se concentra el retraso en una red aérea?\n"
    "La pregunta parece geográfica: unos pocos aeropuertos que lo generan y lo "
    "propagan al resto. **Los datos dicen que no.**"
)

# Sin `delta`: Streamlit le pone siempre una flecha de direccion, y aqui no hay
# ninguna variacion que senalar, solo una proporcion.
c1, c2, c3, c4 = st.columns(4)
c1.metric("Vuelos programados", sl.miles(u["programados"]))
c2.metric(f"Operados · {sl.decimal(100 * u['operados'] / u['programados'])} %",
          sl.miles(u["operados"]))
c3.metric("Aeropuertos", sl.miles(u["aeropuertos"]))
c4.metric("Minutos de demora", sl.miles(u["minutos"]))

st.divider()

# ---------------------------------------------------------------- el no-hallazgo
st.subheader("1. El retraso se reparte en proporción al volumen")

concentracion = qm.consulta("""
    WITH t AS (SELECT (SELECT COUNT(*) FROM h_demoras) tv,
                      (SELECT SUM(demora_salida_min) FROM h_demoras) tm)
    SELECT a.banda_trafico                                           AS banda,
           a.orden_banda                                             AS orden,
           100.0 * COUNT(*) / MAX(t.tv)                              AS pct_vuelos,
           100.0 * SUM(d.demora_salida_min) / MAX(t.tm)              AS pct_retraso,
           (1.0 * SUM(d.demora_salida_min) / MAX(t.tm))
             / (1.0 * COUNT(*) / MAX(t.tv))                          AS indice
    FROM h_demoras d
    JOIN h_vuelos     v ON v.vuelo_id      = d.vuelo_id
    JOIN d_aeropuerto a ON a.aeropuerto_id = v.origen_id, t
    GROUP BY a.banda_trafico, a.orden_banda
    ORDER BY a.orden_banda
""")

izq, der = st.columns([3, 2])
with izq:
    import plotly.graph_objects as go
    fig = go.Figure()
    fig.add_bar(x=concentracion["banda"], y=concentracion["pct_vuelos"],
                name="Cuota de vuelos", marker_color=sl.TENUE)
    fig.add_bar(x=concentracion["banda"], y=concentracion["pct_retraso"],
                name="Cuota de retraso", marker_color=sl.ACENTO)
    fig.update_layout(barmode="group")
    st.plotly_chart(sl._base(fig, 340, "% del total"), width="stretch")
with der:
    st.markdown(
        "Un **índice de 1** significa que el grupo acumula exactamente el "
        "retraso que explica su volumen de operación."
    )
    st.dataframe(
        concentracion[["banda", "indice"]].assign(
            indice=lambda d: d["indice"].map(lambda v: sl.decimal(v, 3))
        ).rename(columns={"banda": "Banda de tráfico", "indice": "Índice"}),
        hide_index=True, width="stretch",
    )
    st.markdown(
        "Los catorce aeropuertos principales concentran el **49,1 %** de los "
        "vuelos y el **50,3 %** del retraso. No hay nodos culpables."
    )

st.divider()

# ------------------------------------------------------------------- el hallazgo
st.subheader("2. La estructura está en la forma de la distribución")

distribucion = qm.consulta("""
    SELECT demora_salida_min AS minutos, COUNT(*) AS vuelos
    FROM h_demoras GROUP BY 1 ORDER BY 1
""")

# El modo alto son 800 vuelos frente a los 3.651 del pico: a escala lineal es
# invisible. La escala logaritmica no es un adorno, es la unica forma de ver
# las dos poblaciones a la vez.
logaritmica = st.toggle(
    "Escala logarítmica en el eje vertical",
    value=True,
    help="El modo alto reúne 800 vuelos frente a los 3.651 del pico. "
         "En escala lineal desaparece.",
)

fig = sl.barras(distribucion, "minutos", "vuelos", color=sl.ACENTO, alto=420,
                titulo_y="Vuelos", titulo_x="Demora de salida (minutos)")
sl.franja_vacia(fig, int(p["hueco_desde"]), int(p["hueco_hasta"]),
                f"{p['minutos_sin_un_solo_vuelo']} minutos sin un solo vuelo")
sl.linea_de_referencia(fig, float(p["demora_media_min"].replace(",", ".")),
                       f"media = {sl.decimal(p['demora_media_min'].replace(',', '.'))} min")
if logaritmica:
    fig.update_yaxes(type="log", title="Vuelos (escala logarítmica)")
st.plotly_chart(fig, width="stretch")

a, b, c = st.columns(3)
a.metric("Media", f"{sl.decimal(p['demora_media_min'].replace(',', '.'))} min")
b.metric("Mediana", "3 min")
c.metric("Vuelos por debajo de la media", "95,23 %")

st.warning(
    f"**La media cae dentro del hueco.** Entre los {p['hueco_desde']} y los "
    f"{p['hueco_hasta']} minutos no hay **ni un solo vuelo** de los "
    f"{sl.miles(u['operados'])} operados, y la demora media —"
    f"{sl.decimal(p['demora_media_min'].replace(',', '.'))} minutos— cae justo "
    f"ahí. **Ningún vuelo de la base tiene la demora media.**"
)

st.divider()
st.caption(
    "Escuela de Estadística y Ciencias Actuariales · Universidad Central de "
    "Venezuela · Computación II  ·  Las páginas del menú lateral recorren los "
    "siete objetivos de la investigación."
)
