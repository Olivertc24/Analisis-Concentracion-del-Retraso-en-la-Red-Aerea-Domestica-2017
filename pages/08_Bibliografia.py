"""Fuentes y referencias."""

import streamlit as st

st.set_page_config(page_title="Bibliografía", page_icon="✈", layout="wide")
st.title("Fuentes y referencias")

st.header("La fuente de datos")
st.markdown("""
**Postgres Pro.** *Demo database — Airlines.* Base de demostración de un
sistema de reservas aéreas, volcada a SQLite. 33.121 vuelos programados entre
el 16 de julio y el 14 de septiembre de 2017, 104 aeropuertos y 710 rutas.
<https://postgrespro.com/docs/postgrespro/current/demodb-bookings>

El volcado utilizado contiene `passenger_id` pero no los campos
`passenger_name` ni `contact_data` de la demo original.
""")

st.header("Modelado de datos")
st.markdown("""
**Codd, E. F.** (1970). *A Relational Model of Data for Large Shared Data
Banks.* Communications of the ACM, 13(6), 377–387. — El modelo relacional y las
formas normales.

**Codd, E. F.** (1971). *Further Normalization of the Data Base Relational
Model.* IBM Research Report RJ909. — La tercera forma normal y las
dependencias transitivas.

**Kimball, R. y Ross, M.** (2013). *The Data Warehouse Toolkit: The Definitive
Guide to Dimensional Modeling* (3.ª ed.). Wiley. — Esquema en estrella,
dimensiones conformadas, dimensiones degeneradas y dimensiones con rol
múltiple.
""")

st.header("Estadística descriptiva")
st.markdown("""
**Tukey, J. W.** (1977). *Exploratory Data Analysis.* Addison-Wesley. — El
argumento, central en este trabajo, de mirar la forma de una distribución antes
de resumirla.

**Pearson, K.** (1895). *Contributions to the Mathematical Theory of Evolution
II: Skew Variation in Homogeneous Material.* Philosophical Transactions of the
Royal Society A, 186, 343–414. — Asimetría y curtosis como descriptores de
forma.

**Hyndman, R. J. y Fan, Y.** (1996). *Sample Quantiles in Statistical Packages.*
The American Statistician, 50(4), 361–365. — Las definiciones de cuantil
muestral; relevante porque `quantile_cont` y `quantile_disc` no devuelven lo
mismo.
""")

st.header("Herramientas")
st.markdown("""
**SQLite** — motor de la base normalizada y de la analítica.
<https://sqlite.org>

**DuckDB** — motor analítico del aplicativo. Se usa por su repertorio
estadístico: `stddev_samp`, `median`, `mode`, `quantile_cont`, `skewness`,
`kurtosis` y `mad`, ninguno de los cuales existe en SQLite.
<https://duckdb.org>

**Streamlit** — aplicativo. <https://streamlit.io>

**Plotly** — gráficos. <https://plotly.com/python>
""")

st.header("El repositorio")
st.markdown("""
Todo el proceso —normalización, denormalización, conversión y aplicativo— está
versionado, con la documentación de cada etapa y los scripts que la reproducen:

<https://github.com/Olivertc24/Analisis-Concentracion-del-Retraso-en-la-Red-Aerea-Domestica-2017>

El proceso de datos se reproduce con dos clientes de línea de comandos y
ningún lenguaje de programación.
""")
