"""Conclusiones de la investigación."""

import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src import query_manager as qm        # noqa: E402
from src import stats_logic as sl          # noqa: E402

st.set_page_config(page_title="Conclusiones", page_icon="✈", layout="wide")
st.title("Conclusiones")

u = qm.universo()
p = qm.parametros()

st.header("1. La pregunta de partida tenía respuesta negativa")
st.markdown(f"""
Se buscaba **dónde se concentra el retraso** en la red, con la expectativa de
encontrar unos pocos aeropuertos responsables de buena parte del problema.
**No los hay.**

El índice de concentración —cuota de minutos de retraso dividida entre cuota de
vuelos— vale **1,024** para los catorce aeropuertos principales, **1,004** para
los treinta y uno intermedios y **0,935** para los cincuenta y nueve
secundarios. Los cuatro mayores, tres de ellos en Moscú, están entre 0,99 y
1,10.

La curva de retraso acumulado y la de vuelos acumulados **se superponen**: hay
concentración, pero es exactamente la del tráfico. Descontado el volumen, no
queda nada que explicar.

Un resultado negativo también es un resultado, y en este caso **reorienta la
investigación**: si la estructura no está en la red, hay que buscarla en otro
sitio.
""")

st.header("2. Donde sí hay estructura es en la forma de la distribución")
st.markdown(f"""
La demora de salida no es una variable continua y unimodal. Son **dos
poblaciones separadas por un vacío de {p['minutos_sin_un_solo_vuelo']} minutos**
en el que no cae ni uno de los {sl.miles(u['operados'])} vuelos operados:

- **Demora breve** — de 1 a 11 minutos, el 90,96 % de los vuelos.
- **Demora prolongada** — de 124 a 277 minutos, el 4,77 %.
- Y **puntuales** al minuto, el 4,27 %.

Los límites no se eligieron: salen de buscar la mayor distancia entre dos
valores consecutivos observados, que da **11 → 124**, un salto de 113 minutos
cuando el segundo hueco mayor de toda la distribución es de nueve.
""")

st.header("3. La media no es un resumen admisible, y se puede demostrar")
st.error(f"""
La demora media es de **{sl.decimal(p['demora_media_min'].replace(',', '.'))}
minutos** y el **percentil 95** son **9 minutos**. La media es mayor que el
percentil 95.

De ahí se sigue que el **95,23 %** de los vuelos tiene una demora **inferior**
a la media, y que la media **cae dentro del tramo vacío**: ningún vuelo de la
base tiene la demora media.

El coeficiente de variación, **339,28 %**, la asimetría de **4,34** y la
curtosis de **17,22** describen una distribución que no admite el resumen
habitual. Dentro de cada régimen, en cambio, media y mediana vuelven a
parecerse. **El problema nunca fue la media: era aplicarla a una mezcla.**
""")

st.header("4. La cobertura del registro es un resultado, no un detalle")
st.markdown(f"""
De los **{sl.miles(u['programados'])}** vuelos programados, sólo
**{sl.miles(u['operados'])}** —el 50,64 %— tienen hora real de salida. El resto
no había ocurrido cuando se congeló el volcado.

El modelo lo trata como lo que es: `h_vuelos` carga los 33.121 y `h_demoras`,
en relación 1:0..1, sólo los observados. La alternativa —dejar la demora en
nulo— habría sido peor, porque **`AVG()` ignora los nulos en silencio** y un
promedio mal planteado habría parecido correcto.
""")

st.header("5. El retraso se transporta, no se recupera")
st.markdown("""
De los 16.715 vuelos con hora real de salida y de llegada, **6.978 aterrizan
con exactamente la misma demora** con la que despegaron. El resto se reparte
casi a partes iguales entre los que recuperan algo y los que pierden algo, y el
balance neto de toda la red es de **−105 minutos**: prácticamente cero.
""")

st.divider()

st.header("Lo que esta investigación no puede afirmar")
st.warning("""
**Sobre la naturaleza del fenómeno.** Un vacío perfectamente limpio de 112
minutos en 16.773 observaciones, repartido de forma homogénea por toda la red y
por todos los días, no es un comportamiento operativo plausible. Es casi con
seguridad una huella de cómo se generó esta base de demostración. El estudio
describe lo que el registro dice y lo usa para mostrar por qué una media puede
ser engañosa; **no afirma que el retraso aéreo real se comporte así**.

**Sobre las causas.** Ninguna variable observable de esta base —aeropuerto,
ruta, aeronave, hora, día— distingue a los 800 vuelos de demora prolongada del
resto. El estudio puede decir **dónde están y cuántos son**; no puede decir
**por qué**.

**Sobre el periodo no observado.** Los 16.348 vuelos sin hora real no son una
muestra de nada: son el futuro respecto del corte. Nada de lo concluido aquí se
extiende a ellos.

**Sobre causalidad.** Es un estudio descriptivo sobre un corte de un mes. Las
diferencias descritas son asociaciones observadas, no efectos.
""")

st.divider()
st.caption(
    "Escuela de Estadística y Ciencias Actuariales · Universidad Central de "
    "Venezuela · Computación II"
)
