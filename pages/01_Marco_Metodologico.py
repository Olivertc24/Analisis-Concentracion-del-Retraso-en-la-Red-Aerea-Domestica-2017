"""Objetivos 1 y 2: el modelo de datos y el universo observable."""

import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src import query_manager as qm        # noqa: E402
from src import stats_logic as sl          # noqa: E402

st.set_page_config(page_title="Marco metodológico", page_icon="✈", layout="wide")
st.title("Marco metodológico")
st.caption("Objetivo 1 — reconstruir el modelo de datos · "
           "Objetivo 2 — delimitar el universo observable")

u = qm.universo()

# ---------------------------------------------------------------- la fuente
st.header("La fuente, y por qué no se puede usar tal cual")

st.markdown("""
`travel.sqlite` es el volcado a SQLite de una base PostgreSQL de operación:
ocho tablas, **sin claves primarias, sin claves foráneas y sin índices**.
Antes de describir nada hubo que reconstruir el modelo.
""")

izq, der = st.columns(2)
izq.markdown("""
**Lo que impedía consultarla**

| Problema | Alcance |
|---|---:|
| Nulos escritos como la cadena `\\N` | 16.348 |
| Desplazamiento horario sin minutos | 33.121 |
| Campos bilingües en `jsonb` | 3 columnas |
| Coordenadas en un tipo `point` | 104 filas |
| Texto repetido sin catálogo | 1.078.847 filas |
""")
der.info("""
**El defecto más peligroso no daba error.**

Las marcas de tiempo venían como `2017-09-10 09:50:00+03`. El desplazamiento
ISO-8601 exige los minutos, así que `julianday()` devuelve `NULL` sobre ese
texto.

Sobre la fuente original, **la demora sale `NULL` en los 33.121 vuelos**, sin
un solo aviso. Una investigación sobre retrasos se calcula restando marcas de
tiempo: el defecto caía justo en el centro.
""")

st.subheader("De ocho tablas a doce, en tercera forma normal")
st.image("assets/esquema_normalizado.png", width="stretch")
st.caption(
    "En cian, las cuatro tablas que **nacieron** de la normalización: "
    "`ciudades` y `rutas` resuelven las dos dependencias transitivas "
    "verificadas sobre los datos; `clases_tarifarias` y `estados_vuelo` "
    "imponen la integridad de dominio que el origen no tenía."
)

st.subheader("Y de ahí al esquema en estrella")
st.image("assets/esquema_estrella.png", width="stretch")

st.divider()

# ------------------------------------------------------------ obj 2: cobertura
st.header("El universo observable")
st.markdown(f"""
De los **{sl.miles(u['programados'])}** vuelos programados, sólo
**{sl.miles(u['operados'])}** tienen hora real de salida. Los demás no son un
dato perdido: **todavía no habían ocurrido** cuando se congeló el volcado, el
15 de agosto de 2017.
""")

estados = qm.consulta("""
    SELECT e.codigo AS estado, e.descripcion, COUNT(*) AS programados,
           SUM(v.es_operado::INT) AS con_hora_real,
           100.0 * SUM(v.es_operado::INT) / COUNT(*) AS pct
    FROM h_vuelos v JOIN d_estado e ON e.estado_id = v.estado_id
    GROUP BY 1, 2 ORDER BY programados DESC
""")

izq, der = st.columns([3, 2])
with izq:
    st.dataframe(
        estados.assign(
            programados=lambda d: d["programados"].map(sl.miles),
            con_hora_real=lambda d: d["con_hora_real"].map(sl.miles),
            pct=lambda d: d["pct"].map(lambda v: sl.porcentaje(v, 1)),
        ).rename(columns={"estado": "Estado", "descripcion": "Descripción",
                          "programados": "Programados",
                          "con_hora_real": "Con hora real", "pct": "%"}),
        hide_index=True, width="stretch",
    )
with der:
    st.error("""
**Ocho vuelos `Cancelled` tienen hora real de despegue y aterrizaje.**

Es una contradicción, y la fuente no permite saber cuál de los dos datos es el
correcto. **Ninguno vendió un solo cupón.**

Se conservan tal cual, sin corregir ni descartar: inventar una respuesta sería
peor que dejar la contradicción a la vista. Su efecto sobre la demora media es
de ocho milésimas de minuto.
""")

st.subheader("La frontera del registro, día a día")
cobertura = qm.consulta("""
    SELECT t.fecha, COUNT(*) AS programados, SUM(v.es_operado::INT) AS operados
    FROM h_vuelos v JOIN d_tiempo t ON t.fecha_id = v.fecha_id
    GROUP BY t.fecha ORDER BY t.fecha
""")

import plotly.graph_objects as go          # noqa: E402
fig = go.Figure()
fig.add_bar(x=cobertura["fecha"], y=cobertura["programados"],
            name="Programados", marker_color=sl.TENUE)
fig.add_bar(x=cobertura["fecha"], y=cobertura["operados"],
            name="Con hora real", marker_color=sl.ACENTO)
fig.update_layout(barmode="overlay")
st.plotly_chart(sl._base(fig, 360, "Vuelos"), width="stretch")

st.warning(f"""
**El corte no es una caída de actividad.** La programación continúa durante los
{u['dias']} días, pero el registro de horas reales se detiene el **15 de agosto**:
sólo **{u['dias_operados']} de {u['dias']} días** tienen vuelos observados.

Cualquier serie temporal que ignore esta frontera mostrará un desplome que no
ocurrió. Por eso la dimensión `d_tiempo` lleva una bandera `hay_operados`, y
por eso el modelo separa `h_vuelos` de `h_demoras` en lugar de dejar la demora
en nulo: **`AVG()` ignora los nulos en silencio**, y un promedio mal planteado
habría parecido correcto.
""")
