# Normalización de `travel.sqlite`

De ocho tablas sin una sola clave declarada a doce tablas en tercera forma
normal, con claves primarias, foráneas y restricciones de dominio.

Todo el proceso está en [`normalizacion.sql`](normalizacion.sql) y **no usa nada
más que SQLite**:

```bash
cd "Base de datos"
sqlite3 travel_normalizada.sqlite < normalizacion.sql
```

Tarda **2,3 segundos** y es idempotente: borra lo que haya y lo reconstruye.

---

## 1. Se normaliza la fuente entera, no sólo lo que este estudio usa

La investigación trata de los retrasos, de modo que su materia prima son las
horas reales de los vuelos. Aun así se normalizan también las reservas, los
pasajes, los cupones y las tarjetas de embarque.

La razón es que esta etapa produce **la base que guarda la verdad**. Recortarla
según la pregunta de hoy obligaría a rehacerla con cada pregunta nueva. La
selección de lo relevante corresponde al modelo dimensional, que viene después.

---

## 2. El punto de partida

| Tabla de origen | Filas | Clave real (no declarada) |
|---|---:|---|
| `ticket_flights` | 1.045.726 | (ticket_no, flight_id) |
| `boarding_passes` | 579.686 | (ticket_no, flight_id) |
| `tickets` | 366.733 | ticket_no |
| `bookings` | 262.788 | book_ref |
| `flights` | 33.121 | flight_id |
| `seats` | 1.339 | (aircraft_code, seat_no) |
| `airports_data` | 104 | airport_code |
| `aircrafts_data` | 9 | aircraft_code |

La fuente **no declara ninguna clave primaria, ninguna clave foránea y ningún
índice**. Lo primero fue comprobar si los datos las respetan de todos modos. Sí
lo hacen: las claves candidatas probadas resultaron únicas y las relaciones
evaluadas no tienen huérfanos. Las restricciones del esquema nuevo, por tanto,
no corrigen datos: hacen **exigible** lo que hasta ahora era sólo costumbre.

---

## 3. Análisis forma por forma

### Primera forma normal — cuatro atributos no atómicos

| Columna de origen | Contenido | Queda como |
|---|---|---|
| `airports_data.airport_name` | `{"en": "Yakutsk Airport", "ru": "Якутск"}` | `nombre`, `nombre_ru` |
| `airports_data.city` | `{"en": "Yakutsk", "ru": "Якутск"}` | `ciudades.nombre`, `nombre_ru` |
| `aircrafts_data.model` | `{"en": "Airbus A319-100", …}` | `modelo`, `modelo_ru` |
| `airports_data.coordinates` | `(129.77099,62.09329)` | `longitud`, `latitud` |

El orden de `coordinates` es el de PostgreSQL: **primero la longitud**, al
contrario de lo que asume casi toda biblioteca de mapas.

### Segunda forma normal — ya se cumplía

Conviene decirlo con claridad en vez de inventar una infracción para tener las
tres formas completas: **la fuente ya satisface la 2FN**. Las dos únicas tablas
de clave compuesta son `ticket_flights` —(ticket_no, flight_id) → clase, monto—
y `boarding_passes` —(ticket_no, flight_id) → número de embarque, asiento—, y en
ambas los atributos dependen de la clave **completa**. No hay nada que corregir
en este nivel.

### Tercera forma normal — dos dependencias transitivas

Las dos se verificaron sobre los datos antes de actuar.

**a) El número de vuelo determina la ruta.**

```sql
SELECT COUNT(DISTINCT flight_no) AS numeros, COUNT(*) AS combinaciones
FROM (SELECT DISTINCT flight_no, departure_airport,
                      arrival_airport, aircraft_code FROM flights);
-- 710 numeros  ->  710 combinaciones
```

Esos tres atributos pertenecen a la **ruta**, no al vuelo concreto, y se
repetían a lo largo de 33.121 filas. Nace **`rutas`** (710 filas) y `vuelos`
conserva sólo lo que varía de un día a otro: la fecha, la hora, el estado y las
horas reales.

**b) La ciudad determina la zona horaria.** Las 101 ciudades producen 101 pares
(ciudad, zona horaria) pese a haber 104 aeropuertos, porque Moscú tiene tres y
Ulianovsk dos. Nace **`ciudades`** (101 filas).

---

## 4. Los dos defectos de formato, que aquí son críticos

Una investigación sobre retrasos se calcula **restando marcas de tiempo**. Los
dos defectos que trae la fuente caen justo ahí.

### Nulos disfrazados

Las horas reales de los vuelos no operados **no son `NULL`**: contienen la
cadena literal `\N`, marcador de nulo de los volcados de PostgreSQL. Hay
**16.348** en `actual_departure` y **16.406** en `actual_arrival`, cerca de la
mitad de la tabla. Restarlas sin depurarlas no produce un error: produce un
resultado silenciosamente incorrecto. Se convierten con `NULLIF`.

### Fechas que SQLite no sabe leer

Las marcas vienen como `2017-09-10 09:50:00+03`. El desplazamiento ISO-8601
exige los minutos, así que para SQLite ese texto **no es una fecha**:

```sql
SELECT julianday('2017-09-10 09:50:00+03');     -- NULL
SELECT julianday('2017-09-10 09:50:00+03:00');  -- 2458006.78
```

Es decir: **sobre la fuente original, la demora sale `NULL` en los 33.121
vuelos**, sin un solo aviso. Se comprobó que todas las marcas de la base llevan
el mismo desplazamiento `+03`, de modo que añadir `:00` es una corrección de
formato sin pérdida.

---

## 5. Decisiones que van más allá de la 3FN

Se declaran como tales en lugar de presentarlas como exigencias de la teoría.

**Catálogos de dominio.** `status` (6 valores repetidos en 33.121 filas) y
`fare_conditions` (3 valores en 1.045.726) pasan a tablas con clave foránea.
**La 3FN no lo exige**: ambos dependen de la clave de su tabla. Lo exige la
integridad de dominio, que hoy no existe — nada impide escribir `Arrivedd`.

**Dos atributos derivados suprimidos**, repuestos como vistas:

| Atributo | Se reconstruye como | Verificado en |
|---|---|---|
| `flights.scheduled_arrival` | salida programada + `rutas.duracion_min` | los 710 números de vuelo |
| `bookings.total_amount` | suma de los cupones de la reserva | las 262.788 reservas |

**Las horas reales sí se conservan.** No son derivadas de nada: son el dato
propio de cada vuelo y la materia prima de esta investigación. Lo único que se
les hace es convertir su `\N` en `NULL` de verdad.

**Lo que no se hace aquí.** No se calcula ninguna demora, ni distancias, ni
clasificaciones. Eso es análisis, no normalización.

---

## 6. Una trampa de zona horaria dentro de la propia vista

La vista que repone `scheduled_arrival` sumaba los minutos de la ruta sobre la
marca completa:

```sql
datetime(salida_programada, '+' || duracion_min || ' minutes')
```

Y `datetime()`, al encontrar un desplazamiento, **convierte a UTC**. Para un
vuelo que llega a las `11:30:00+03:00` devolvía `08:30:00`, sin desplazamiento.
La resta seguía saliendo bien —ambos operandos acababan en UTC— pero la columna
quedaba en otro huso que el resto de la tabla, lista para producir una
comparación errónea en cuanto alguien la mezclara con `salida_programada`.

La vista suma ahora sobre la marca **sin** desplazamiento y lo repone después:

```sql
datetime(substr(salida_programada, 1, 19), '+' || duracion_min || ' minutes') || '+03:00'
```

La comprobación 11 contrasta el resultado contra el origen **comparando las
cadenas en hora local**, que es una prueba más exigente que la anterior: 0
discrepancias en los 33.121 vuelos.

---

## 7. El esquema resultante

```
ciudades ──< aeropuertos ──┬──< rutas >── aeronaves ──< asientos
                           │        │                      │
                           └────────┘                      │
                                    │                      │
                     estados_vuelo >┴< vuelos              │
                                          │                │
       reservas ──< pasajes ──< cupones >─┘                │
                                   │  │                    │
                                   │  └──> clases_tarifarias
                                   │
                                   └──< tarjetas_embarque
```

| Tabla | Filas | Por qué existe |
|---|---:|---|
| `ciudades` | 101 | 3FN: ciudad → zona horaria |
| `aeropuertos` | 104 | 1FN: JSON y coordenadas desdoblados |
| `aeronaves` | 9 | 1FN: JSON del modelo desdoblado |
| `clases_tarifarias` | 3 | Integridad de dominio |
| `estados_vuelo` | 6 | Integridad de dominio |
| `asientos` | 1.339 | Configuración de cabina, con la clase como FK |
| `rutas` | 710 | 3FN: número de vuelo → ruta |
| `vuelos` | 33.121 | Lo que varía de un vuelo a otro, horas reales incluidas |
| `reservas` | 262.788 | Sin el total derivado |
| `pasajes` | 366.733 | `pasajero_id` con `UNIQUE` |
| `cupones` | 1.045.726 | Un tramo de un pasaje |
| `tarjetas_embarque` | 579.686 | Depende del cupón, no del pasaje |

---

## 8. Verificación

Dieciséis comprobaciones contra la fuente, todas en **OK**:

| Qué | Resultado |
|---|---|
| Conservación de filas, tabla por tabla | Las diez coinciden con su origen |
| Reconstrucción de `scheduled_arrival` en hora local | 0 discrepancias de 33.121 |
| Reconstrucción de `total_amount` | 0 discrepancias de 262.788 |
| `\N` convertidos a `NULL` en la salida real | 16.348 |
| `\N` convertidos a `NULL` en la llegada real | 16.406 |
| Horas reales legibles por `julianday()` | Todas |
| Vuelos con salida real: el universo del estudio | **16.773** |
| `PRAGMA foreign_key_check` | Sin una sola fila |
| `PRAGMA integrity_check` | `ok` |
| Las dos dependencias transitivas, recontadas | 710 → 710 y 101 → 101 |

Y la que de verdad importa para esta investigación: **la demora calculada sobre
la base normalizada reproduce exactamente la de la fuente.**

| Medida | Normalizada | Fuente |
|---|---:|---:|
| Vuelos con demora calculable | 16.773 | 16.773 |
| Suma de minutos de demora | 204.740 | 204.740 |
| Demora máxima | 277 | 277 |
| Vuelos en el hueco de 12 a 123 minutos | **0** | **0** |

---

## 9. Una anomalía que se conserva

De los 16.773 vuelos con hora real de salida, **ocho están marcados como
`Cancelled`**:

| Estado | Vuelos con hora real de salida |
|---|---:|
| `Arrived` | 16.707 |
| `Departed` | 58 |
| **`Cancelled`** | **8** |

Un vuelo cancelado que despegó y aterrizó es una contradicción, y la fuente no
da forma de saber cuál de los dos datos es el correcto. **Se conservan tal
cual**, sin corregir ni descartar: inventar una respuesta sería peor que dejar
la contradicción a la vista. El estudio declarará, al fijar su universo, qué
hace con ellos.

El esquema sí rechaza lo que es imposible sin ambigüedad: la restricción
`CHECK (llegada_real > salida_real)` se cumple en los 16.715 vuelos que tienen
ambas horas. Ninguno aterriza antes de despegar.

---

## 10. El tamaño, que sorprende al revés

| | Tamaño |
|---|---:|
| `travel.sqlite` (origen) | 104 MB |
| `travel_normalizada.sqlite` | **186 MB** |

La base normalizada es **más grande**, y el motivo no es la normalización sino
lo contrario. Midiendo con `dbstat`:

| Componente | Tamaño |
|---|---:|
| Datos | **71,8 MB** |
| Índices y claves | **114,5 MB** |

Los datos **bajaron** de 104 a 71,8 MB: desaparecieron los dos atributos
derivados, el texto repetido de `status` y `fare_conditions` pasó a enteros, y
la ruta dejó de repetirse 33.121 veces. El crecimiento son los **114,5 MB de
índices y claves primarias que la fuente no tenía en absoluto**. Es el precio de
poder exigir la integridad y de poder consultar la base sin recorrerla entera.
