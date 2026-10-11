# Denormalización: el esquema en estrella

De doce tablas en tercera forma normal a **una estrella de siete dimensiones**,
con una tabla de hechos central y una extensión en relación 1:0..1. Es el
insumo directo del aplicativo en Streamlit y del tablero.

Todo el proceso está en [`denormalizacion.sql`](denormalizacion.sql):

```bash
cd "Base de datos"
sqlite3 travel_analitica.sqlite < denormalizacion.sql
```

Tarda **1 segundo** y, como el anterior, sólo necesita el cliente `sqlite3`.

---

## 1. El esquema

![Esquema en estrella de la base analítica](../assets/esquema_estrella.png)

---

## 2. Por qué desnormalizar lo que se acaba de normalizar

Son dos objetivos opuestos y cada esquema sirve al suyo.

La **tercera forma normal optimiza la escritura**: cada hecho vive en un solo
sitio y no puede contradecirse. Es lo que se quiere de la base que guarda la
verdad.

El **esquema en estrella optimiza la lectura y, sobre todo, la comprensión**.
Separa lo que se **mide** —la demora— de aquello **por lo que** se mide: el
aeropuerto, la hora, el día, la aeronave. Que es exactamente como están
formuladas las preguntas de esta investigación.

---

## 3. El grano es el vuelo, y hay dos tablas de hechos

| Tabla de hechos | Filas | Qué contiene |
|---|---:|---|
| `h_vuelos` | 33.121 | **Todos** los vuelos programados |
| `h_demoras` | 16.773 | Sólo los que llegaron a despegar |

La separación no es un capricho de diseño: **es el instrumento que responde al
objetivo 2**. De los 33.121 vuelos programados, 16.348 no tienen hora real de
salida porque al cerrarse el volcado —el 15 de agosto— todavía no habían
ocurrido. Había tres caminos:

| Alternativa | Problema |
|---|---|
| Cargar sólo los operados | Se pierde de vista que la mitad de la programación no está observada, que es en sí mismo un resultado |
| Cargar todos con la demora en `NULL` | Peor: `AVG()` ignora los nulos **en silencio**, de modo que un promedio mal planteado parece correcto |
| **Cargar todos en `h_vuelos` y sólo los observados en `h_demoras`** | **Ninguno** |

La clave primaria de `h_demoras` **es** su clave foránea, así que la
cardinalidad 0..1 la impone el esquema. La cobertura queda **contable**:
`COUNT(*)` sobre cada tabla la responde sin posibilidad de equivocarse de
denominador.

| Estado del vuelo | Programados | Con hora real |
|---|---:|---:|
| `Arrived` | 16.707 | 16.707 |
| `Scheduled` | 15.383 | 0 |
| `On Time` | 518 | 0 |
| `Cancelled` | 414 | **8** |
| `Departed` | 58 | 58 |
| `Delayed` | 41 | 0 |

Los ocho `Cancelled` con hora real son la anomalía que la normalización
conservó sin corregir. Entran en `h_demoras` porque despegaron; la
contradicción con su estado queda a la vista, no tapada.

---

## 4. Dos cortes que el script deduce del dato

Ninguno de los dos se escribe a mano. Si la fuente cambiara, se recalcularían
solos.

### El hueco, y con él los tres regímenes

La demora de salida no se distribuye de forma continua. El límite entre sus dos
modos no se fija por criterio sino **buscando la mayor distancia entre dos
valores consecutivos observados**:

```sql
WITH distintos AS (SELECT DISTINCT demora m FROM ...),
     saltos AS (SELECT m, LEAD(m) OVER (ORDER BY m) sig FROM distintos)
SELECT m, sig, sig - m AS amplitud FROM saltos ORDER BY amplitud DESC LIMIT 1;
```

| Salto | Desde | Hasta | Amplitud |
|---|---:|---:|---:|
| **El mayor** | **11** | **124** | **113** |
| El segundo | 268 | 277 | 9 |
| El tercero | 124 | 132 | 8 |

El mayor salto es **doce veces** el siguiente: la detección no es ambigua. De
ahí salen las tres filas de `d_regimen`:

| id | Etiqueta | Desde | Hasta | Vuelos | % |
|---:|---|---:|---:|---:|---:|
| 1 | Puntual | 0 | 0 | 717 | 4,27 % |
| 2 | Demora breve | 1 | 11 | 15.256 | 90,96 % |
| 3 | Demora prolongada | 124 | 277 | 800 | 4,77 % |

### Las bandas de tráfico

Los 104 aeropuertos no se pueden graficar de uno en uno. Se agrupan por
acumulado de vuelos programados, al modo de Pareto: **principales** los que
suman el primer 50 % de la operación, **intermedios** hasta el 80 %,
**secundarios** el resto.

| Banda | Aeropuertos | Vuelos | % |
|---|---:|---:|---:|
| Principal | 14 | 16.293 | 49,2 % |
| Intermedio | 31 | 10.078 | 30,4 % |
| Secundario | 59 | 6.750 | 20,4 % |

---

## 5. Las siete dimensiones

| Dimensión | Filas | Atributos de corte |
|---|---:|---|
| `d_tiempo` | 61 | `fecha`, `nombre_mes`, `nombre_dia`, `semana_iso`, `es_fin_de_semana`, `hay_operados` |
| `d_franja` | 24 | `hora`, `bloque` (Madrugada / Mañana / Tarde / Noche) |
| `d_aeropuerto` | 104 | `codigo`, `nombre`, `ciudad`, `zona_horaria`, coordenadas, `vuelos_salida`, `banda_trafico` |
| `d_ruta` | 710 | `numero_vuelo`, `etiqueta`, `duracion_programada_min` |
| `d_aeronave` | 9 | `codigo`, `modelo`, `autonomia_km`, `asientos_total` |
| `d_estado` | 6 | `codigo`, `descripcion`, `es_operado` |
| `d_regimen` | 3 | `etiqueta`, `desde_min`, `hasta_min` |

**`d_aeropuerto` se usa con rol doble**: `origen_id` y `destino_id` apuntan a la
misma tabla. Es *role-playing*; evita mantener dos catálogos que tendrían que
decir lo mismo y que antes o después dejarían de decirlo.

**`d_aeropuerto` es plana a propósito.** La ciudad y su zona horaria viajan
dentro, aunque en la base normalizada vivan en `ciudades`. Snowflakear la
dimensión la partiría en dos y obligaría al tablero a una reunión más.

**`d_ruta` no duplica el origen ni el destino.** Guarda sólo lo que pertenece a
la ruta y no es ya una dimensión propia: su número, una etiqueta legible y la
duración programada. El origen y el destino viajan como claves foráneas de la
tabla de hechos, que es donde el modelo en estrella los coloca.

**`d_regimen` es la dimensión propia de esta investigación.** Es a este trabajo
lo que la tipología del viaje sería a uno de conducta de compra: la variable
que organiza todo lo demás.

---

## 6. Las medidas

### En `h_vuelos`

`duracion_programada_min` y **`es_operado`** (0/1). Esta última es la medida del
objetivo 2: sumada da la cobertura del registro.

### En `h_demoras`

| Medida | Qué es |
|---|---|
| `demora_salida_min` | Hora real de salida menos hora programada |
| `demora_llegada_min` | Lo mismo en el aterrizaje |
| `minutos_recuperados` | La diferencia entre ambas: positivo si el vuelo recortó tiempo en el aire |
| `duracion_real_min` | Hora real de llegada menos hora real de salida |

**Tres de ellas quedan en `NULL` para 58 vuelos.** No es un fallo de carga: son
los que estaban **en el aire** cuando se congeló el volcado. Despegaron, pero
aún no habían aterrizado. La demora de salida sí existe para los 16.773.

---

## 7. La trampa de la fecha local

Las marcas de tiempo llevan desplazamiento `+03:00`, y las funciones de fecha
de SQLite **convierten a UTC antes de operar**:

```sql
SELECT date('2017-07-30 01:50:00+03:00');   -- '2017-07-29'
```

Usar `date()` atribuiría **79 vuelos al día anterior** y haría aparecer 62 días
de operación donde hay 61. El script toma la fecha local con
`substr(x, 1, 10)` y la hora con `substr(x, 12, 2)`, exactos porque toda la base
está en `+03`. Las diferencias en minutos sí usan `julianday()` sobre la marca
completa: ahí la conversión se cancela entre los dos operandos.

---

## 8. Lo que la estrella contesta

| Objetivo | Hechos | Dimensiones |
|---|---|---|
| 2 — Universo observable | `h_vuelos` | `d_estado`, `d_tiempo` |
| 3 — Forma de la distribución | `h_demoras` | `d_regimen` |
| 4 — Concentración en la red | ambos | `d_aeropuerto`, `d_ruta` |
| 5 — Reparto temporal | ambos | `d_tiempo`, `d_franja` |
| 6 — La demora prolongada | ambos | `d_regimen`, `d_aeronave`, `d_aeropuerto` |

La consulta del objetivo 4, que es el eje del trabajo:

```sql
SELECT a.banda_trafico,
       ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM h_demoras), 2)            AS pct_vuelos,
       ROUND(100.0 * SUM(d.demora_salida_min)
             / (SELECT SUM(demora_salida_min) FROM h_demoras), 2)              AS pct_retraso
FROM h_demoras d
JOIN h_vuelos     v ON v.vuelo_id      = d.vuelo_id
JOIN d_aeropuerto a ON a.aeropuerto_id = v.origen_id
GROUP BY a.banda_trafico;
```

| Banda | % de vuelos | % del retraso | Índice |
|---|---:|---:|---:|
| Principal | 49,14 % | 50,33 % | **1,024** |
| Intermedio | 30,44 % | 30,57 % | **1,004** |
| Secundario | 20,42 % | 19,10 % | **0,935** |

El resultado negativo del planteamiento se sostiene también agregado: el
retraso se reparte en proporción al volumen en los tres niveles de la red.

---

## 9. La tabla `parametros`

Recoge lo que el script dedujo, para que no haya que creérselo:

| Clave | Valor |
|---|---|
| `hueco_desde` | 12 |
| `hueco_hasta` | 123 |
| `minutos_sin_un_solo_vuelo` | **112** |
| `demora_media_min` | **12,21** |
| `media_cae_en_el_hueco` | **sí** |
| `cobertura_operada` | 16.773 de 33.121 |

La penúltima fila es una comprobación, no una afirmación: el script contrasta
la media contra los límites del hueco y escribe el resultado. **Ningún vuelo de
la base tiene la demora media.**

---

## 10. El tamaño, que esta vez baja

| | Tamaño |
|---|---:|
| `travel.sqlite` (origen) | 104 MB |
| `travel_normalizada.sqlite` | 186 MB |
| `travel_analitica.sqlite` | **5,0 MB** |

| Componente | Tamaño |
|---|---:|
| Tablas de hechos | 2.772 KB |
| Índices | 2.332 KB |
| **Las siete dimensiones juntas** | **64 KB** |

Treinta y siete veces menor que la base normalizada, y el motivo es que **el
modelo dimensional selecciona**. La base en 3FN guarda 1.045.726 cupones y
579.686 tarjetas de embarque porque es la que guarda la verdad; esta
investigación no los usa, y aquí no están. Lo que queda son 33.121 vuelos
descritos por 64 KB de dimensiones.

Que la base analítica quepa en cinco megabytes tiene una consecuencia práctica:
el aplicativo puede ser autocontenido sin pedirle nada a ningún servicio
externo.

---

## 11. Lo que no se hace aquí

- **No se agrega nada.** Los dos hechos conservan el grano completo; los
  resúmenes los calcula el aplicativo.
- **No se enriquece con datos nuevos.** No hay distancias entre aeropuertos ni
  variables externas: sólo se resuelven las reuniones y se clasifica lo que ya
  estaba.
- **No se descarta ninguna fila.** Los 33.121 vuelos programados están en
  `h_vuelos`, incluidos los 16.348 que nunca llegaron a ocurrir.
