# El tablero

Un extracto `.hyper` con cuatro tablas, construido **directamente desde la base
DuckDB**, y cuatro hojas, una por hallazgo de la investigación.

```bash
python Tableau/construir_hyper.py
```

| Tabla del extracto | Filas | Grano | Alimenta |
|---|---:|---|---|
| `cobertura` | 61 | El día de operación | La frontera del registro |
| `distribucion` | 124 | El valor de demora observado | La forma, con su hueco |
| `aeropuertos` | 104 | El aeropuerto de salida | El mapa y la concentración |
| `tiempo` | 134 | Hora × día de la semana | El reparto temporal |

El archivo entero pesa **64 KB**. No se versiona: se regenera en un segundo, y
cuando el libro esté construido viajará dentro del `.twbx`.

---

## Por qué no hay ningún CSV por el camino

Un CSV intermedio es **una copia sin tipos**: todo se vuelve texto y Tableau
tiene que adivinar al leerlo. Adivina mal con frecuencia —las fechas, los
decimales según la configuración regional, los acentos según la codificación—
y cada error aparece en el tablero, no en el script, que es donde se podría
corregir.

`.hyper` es el **formato nativo de extracto de Tableau**: columnar, tipado y
con índices. Los datos van de DuckDB a Hyper sin pasar por ningún formato de
texto, de modo que un `SMALLINT` llega como entero y una fecha como fecha. El
script lleva una tabla de correspondencia explícita entre los tipos de DuckDB y
los de Hyper, y **se detiene** si encuentra uno que no sabe traducir, en lugar
de degradarlo a texto en silencio.

Tableau Public, además, **no admite conexiones en vivo**: sólo publica
extractos. Aunque existiera un conector DuckDB para Tableau, el tablero
publicado acabaría siendo un extracto igualmente.

## Por qué cuatro tablas y no una

Cada hoja tiene su propio **grano**. Con una sola tabla al grano más fino, cada
hoja tendría que reagregar, y bastaría un filtro mal puesto para que una cifra
dejara de cuadrar con el aplicativo.

El **índice de concentración**, en particular, es un cociente de cuotas: los
minutos del aeropuerto sobre los totales, dividido entre sus vuelos sobre los
totales. En Tableau exigiría una expresión de nivel de detalle que se rompe en
cuanto alguien aplica un filtro. Calculado en SQL, es una columna.

## Los controles

El script termina leyendo **del propio `.hyper`**, no de las consultas que lo
generaron, y comprueba que cada tabla sume **16.773** vuelos y **204.740**
minutos. Si alguno falla, se detiene.

Comprobar las consultas sería comprobar lo que el script creía escribir;
comprobar el extracto es comprobar lo que Tableau va a leer.

---

## Las cuatro hojas previstas

1. **La cobertura del registro.** Barras de programados y operados por fecha,
   con la frontera del 15 de agosto marcada. Sin ella, cualquier serie temporal
   insinúa un desplome que no ocurrió.

2. **La forma de la distribución.** Vuelos por minuto de demora, en escala
   logarítmica, con el tramo vacío sombreado y la media marcada **dentro** de
   él. Es la hoja que sostiene el objetivo 3.

3. **El mapa de la red.** Los 104 aeropuertos por sus coordenadas, el tamaño
   por volumen y el color por índice de concentración, con el punto medio de
   la escala fijado en **1**. La ausencia de patrón es el hallazgo.

4. **El reparto temporal.** Mapa de calor de hora × día de la semana sobre la
   demora media, para mostrar que no hay franja ni jornada peor que otra.

## Lo que falta

Construir el libro en Tableau Desktop sobre este extracto y publicarlo en
Tableau Public. El enlace se añadirá al README principal cuando esté.
