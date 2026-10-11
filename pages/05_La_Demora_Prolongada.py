"""Objetivo 6: caracterizar la población de retraso alto."""

import sys
from pathlib import Path

import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src import query_manager as qm        # noqa: E402
from src import stats_logic as sl          # noqa: E402

st.set_page_config(page_title="La demora prolongada", page_icon="✈", layout="wide")
st.title("La demora prolongada")
st.caption("Objetivo 6 — describir los vuelos del modo superior y contrastar "
           "si se distinguen del resto por algo observable")

p = qm.parametros()
base = qm.consulta("""
    SELECT COUNT(*) AS vuelos, MIN(demora_salida_min) AS minimo,
           MAX(demora_salida_min) AS maximo, AVG(demora_salida_min) AS media,
           median(demora_salida_min) AS mediana,
           stddev_samp(demora_salida_min) AS desviacion
    FROM h_demoras WHERE regimen_id = 3
""").iloc[0]

c = st.columns(4)
c[0].metric("Vuelos", sl.miles(base["vuelos"]))
c[1].metric("Rango", f"{int(base['minimo'])} – {int(base['maximo'])} min")
c[2].metric("Media", f"{sl.decimal(base['media'])} min")
c[3].metric("Desviación típica", sl.decimal(base["desviacion"]))

st.markdown(f"""
Son **{sl.miles(base['vuelos'])}** vuelos, el **4,77 %** de los operados, y
están separados del resto por **{p['minutos_sin_un_solo_vuelo']} minutos en los
que no cae ninguno**. La pregunta de esta página es si tienen algo en común.
""")

st.divider()

# ------------------------------------------------------------ su propia forma
st.header("Vista por dentro, es una distribución ordinaria")

forma = qm.consulta("""
    SELECT demora_salida_min AS minutos, COUNT(*) AS vuelos
    FROM h_demoras WHERE regimen_id = 3 GROUP BY 1 ORDER BY 1
""")
st.plotly_chart(
    sl.barras(forma, "minutos", "vuelos",
              color=sl.REGIMEN["Demora prolongada"], alto=340,
              titulo_y="Vuelos", titulo_x="Demora de salida (minutos)"),
    width="stretch")
st.caption(
    f"Unimodal, con su máximo alrededor de los {int(forma.loc[forma['vuelos'].idxmax(), 'minutos'])} "
    f"minutos y una dispersión moderada. Aislada, no tiene nada de extraña: "
    f"lo extraño es el vacío que la separa de la otra población."
)

st.divider()

# -------------------------------------------------------- ¿se concentra en algo?
st.header("¿Se concentra en algún sitio, en algún momento, en alguna aeronave?")

cobertura = qm.consulta("""
    SELECT (SELECT COUNT(DISTINCT v.origen_id) FROM h_vuelos v WHERE v.es_operado)    AS aeropuertos,
           (SELECT COUNT(DISTINCT v.origen_id) FROM h_demoras d
              JOIN h_vuelos v ON v.vuelo_id = d.vuelo_id WHERE d.regimen_id = 3)      AS aeropuertos_con,
           (SELECT COUNT(DISTINCT v.fecha_id) FROM h_vuelos v WHERE v.es_operado)     AS dias,
           (SELECT COUNT(DISTINCT v.fecha_id) FROM h_demoras d
              JOIN h_vuelos v ON v.vuelo_id = d.vuelo_id WHERE d.regimen_id = 3)      AS dias_con,
           (SELECT COUNT(DISTINCT v.ruta_id) FROM h_vuelos v WHERE v.es_operado)      AS rutas,
           (SELECT COUNT(DISTINCT v.ruta_id) FROM h_demoras d
              JOIN h_vuelos v ON v.vuelo_id = d.vuelo_id WHERE d.regimen_id = 3)      AS rutas_con
""").iloc[0]

c = st.columns(3)
c[0].metric("Aeropuertos con al menos un caso",
            f"{cobertura['aeropuertos_con']} de {cobertura['aeropuertos']}")
c[1].metric("Días con al menos un caso",
            f"{cobertura['dias_con']} de {cobertura['dias']}")
c[2].metric("Rutas con al menos un caso",
            f"{cobertura['rutas_con']} de {cobertura['rutas']}")

st.markdown("**Por modelo de aeronave**")
aeronaves = qm.consulta("""
    SELECT an.codigo, an.modelo, COUNT(*) AS operados,
           COUNT(*) FILTER (WHERE d.regimen_id = 3) AS prolongadas,
           100.0 * COUNT(*) FILTER (WHERE d.regimen_id = 3) / COUNT(*) AS pct
    FROM h_demoras d
    JOIN h_vuelos   v  ON v.vuelo_id    = d.vuelo_id
    JOIN d_aeronave an ON an.aeronave_id = v.aeronave_id
    GROUP BY 1, 2 ORDER BY pct DESC
""")

izq, der = st.columns([3, 2])
izq.plotly_chart(
    sl.barras(aeronaves, "modelo", "pct",
              color=sl.REGIMEN["Demora prolongada"], alto=360,
              titulo_y="% de vuelos con demora prolongada", horizontal=True),
    width="stretch")
der.dataframe(
    aeronaves.assign(
        operados=lambda d: d["operados"].map(sl.miles),
        prolongadas=lambda d: d["prolongadas"].map(sl.miles),
        pct=lambda d: d["pct"].map(lambda v: sl.porcentaje(v)),
    )[["codigo", "operados", "prolongadas", "pct"]]
     .rename(columns={"codigo": "Modelo", "operados": "Operados",
                      "prolongadas": "Prolongadas", "pct": "%"}),
    hide_index=True, width="stretch", height=340)

st.markdown("**Por banda de tráfico del aeropuerto de salida**")
bandas = qm.consulta("""
    SELECT a.banda_trafico AS banda, MIN(a.orden_banda) AS orden,
           COUNT(*) AS operados,
           COUNT(*) FILTER (WHERE d.regimen_id = 3) AS prolongadas,
           100.0 * COUNT(*) FILTER (WHERE d.regimen_id = 3) / COUNT(*) AS pct
    FROM h_demoras d
    JOIN h_vuelos     v ON v.vuelo_id      = d.vuelo_id
    JOIN d_aeropuerto a ON a.aeropuerto_id = v.origen_id
    GROUP BY a.banda_trafico ORDER BY orden
""")
st.dataframe(
    bandas.assign(
        operados=lambda d: d["operados"].map(sl.miles),
        prolongadas=lambda d: d["prolongadas"].map(sl.miles),
        pct=lambda d: d["pct"].map(lambda v: sl.porcentaje(v)),
    )[["banda", "operados", "prolongadas", "pct"]]
     .rename(columns={"banda": "Banda", "operados": "Operados",
                      "prolongadas": "Prolongadas", "pct": "%"}),
    hide_index=True, width="stretch")

st.error(f"""
### Está en todas partes, y en proporción casi constante

Aparece en **{cobertura['aeropuertos_con']} de los {cobertura['aeropuertos']}
aeropuertos** que operaron, en **los {cobertura['dias_con']} días sin
excepción** y en **{cobertura['rutas_con']} de las {cobertura['rutas']} rutas**.

Por modelo de aeronave la proporción va del
**{sl.porcentaje(aeronaves['pct'].min())}** al
**{sl.porcentaje(aeronaves['pct'].max())}**; por banda de tráfico, del
**{sl.porcentaje(bandas['pct'].min())}** al **{sl.porcentaje(bandas['pct'].max())}**.

**Ninguna variable observable de esta base distingue a esos 800 vuelos del
resto**, más allá de su propia demora.
""")

st.divider()

# ------------------------------------------------------------ se recupera algo?
st.header("¿Se recupera tiempo en el aire?")

recuperacion = qm.consulta("""
    SELECT COUNT(*) AS evaluados,
           COUNT(*) FILTER (WHERE minutos_recuperados > 0) AS recuperan,
           COUNT(*) FILTER (WHERE minutos_recuperados < 0) AS pierden,
           COUNT(*) FILTER (WHERE minutos_recuperados = 0) AS igual,
           SUM(minutos_recuperados) AS neto
    FROM h_demoras WHERE minutos_recuperados IS NOT NULL
""").iloc[0]

c = st.columns(4)
c[0].metric("Vuelos con ambas horas", sl.miles(recuperacion["evaluados"]))
c[1].metric("Llegan con menos demora", sl.miles(recuperacion["recuperan"]))
c[2].metric("Llegan con más", sl.miles(recuperacion["pierden"]))
c[3].metric("Minutos netos recuperados", sl.miles(recuperacion["neto"]))

st.markdown(f"""
De los **{sl.miles(recuperacion['evaluados'])}** vuelos con hora real de salida
y de llegada, **{sl.miles(recuperacion['igual'])}** aterrizan con **exactamente
la misma demora** con la que despegaron. El resto se reparte casi a partes
iguales entre los que recuperan algo y los que pierden algo, y el balance neto
de toda la red es de **{sl.miles(recuperacion['neto'])} minutos**.

Es decir: **la demora no se recupera ni se agrava en vuelo. Se transporta
intacta.**
""")

st.warning("""
**Hasta dónde llega lo que esta base permite afirmar.**

Que 800 vuelos se separen del resto por un vacío de dos horas, repartidos de
forma homogénea por toda la red y por todos los días, no es un comportamiento
operativo plausible: es casi con seguridad una huella de cómo se generó esta
base de demostración.

El estudio **describe lo que el registro dice** y lo usa para mostrar por qué
una media puede ser engañosa. **No afirma** que el retraso aéreo real se
comporte así, y **no puede explicar** por qué estos vuelos están donde están.
Decir lo contrario sería ir más allá de lo que el dato sostiene.
""")
