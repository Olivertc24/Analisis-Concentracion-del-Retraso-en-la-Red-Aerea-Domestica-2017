# El tablero

Cuatro extractos y cuatro hojas, una por hallazgo de la investigación.

```bash
python Tableau/generar_extractos.py
```

| Extracto | Filas | Grano | Alimenta |
|---|---:|---|---|
| `cobertura.csv` | 61 | El día de operación | La frontera del registro |
| `distribucion.csv` | 124 | El valor de demora observado | La forma, con su hueco |
| `aeropuertos.csv` | 104 | El aeropuerto de salida | El mapa y la concentración |
| `tiempo.csv` | 134 | Hora × día de la semana | El reparto temporal |

Los cuatro juntos pesan **22 KB**. Se versionan.

---

## Por qué cuatro archivos y no uno

Cada hoja tiene su propio **grano**. Con una sola tabla al grano más fino, cada
hoja tendría que reagregar, y bastaría un filtro mal puesto para que una cifra
dejara de cuadrar con el aplicativo.

## Por qué se agrega en SQL y no en Tableau

El **índice de concentración** es un cociente de cuotas: los minutos del
aeropuerto sobre los minutos totales, dividido entre sus vuelos sobre los
vuelos totales. Calcularlo en Tableau exige expresiones de nivel de detalle
que se rompen en cuanto alguien aplica un filtro. Calculado en SQL, es una
columna, y además se puede verificar contra la base.

El script ejecuta cinco controles al terminar: la suma de vuelos de cada
extracto tiene que dar **16.773** y la de minutos **204.740**. Si alguno falla,
se detiene. Un tablero que muestre cifras distintas de las del aplicativo es
peor que no tener tablero.

## Un detalle de codificación

Los CSV se escriben en **UTF-8 con BOM**. Sin él, Tableau en Windows los lee
como latin-1 y «San Petersburgo» llega roto.

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

Construir el libro en Tableau Desktop con estos cuatro extractos y publicarlo
en Tableau Public. El enlace se añadirá al README principal cuando esté.
