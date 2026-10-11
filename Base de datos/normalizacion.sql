-- =============================================================================
-- NORMALIZACION DE travel.sqlite HASTA LA TERCERA FORMA NORMAL
-- Escuela de Estadistica y Ciencias Actuariales (EECA-UCV) - Computacion II
-- =============================================================================
--
-- ORIGEN   travel.sqlite               8 tablas, sin claves ni indices, 104 MB
-- DESTINO  travel_normalizada.sqlite  12 tablas en 3FN, con PK, FK y CHECK
--
-- EJECUCION (desde esta carpeta, solo con el cliente sqlite3):
--     sqlite3 travel_normalizada.sqlite < normalizacion.sql
--
-- El script es idempotente: borra lo que haya y lo reconstruye.
--
-- -----------------------------------------------------------------------------
-- SE NORMALIZA LA FUENTE ENTERA, NO SOLO LO QUE ESTE ESTUDIO USA
-- -----------------------------------------------------------------------------
-- La investigacion trata de los retrasos, de modo que su materia prima son las
-- horas reales de los vuelos. Aun asi, aqui se normalizan tambien las reservas,
-- los pasajes, los cupones y las tarjetas de embarque. La razon es que esta
-- etapa produce la base que GUARDA LA VERDAD: recortarla segun la pregunta de
-- hoy obligaria a rehacerla con cada pregunta nueva. La seleccion de lo
-- relevante corresponde al modelo dimensional, que viene despues.
--
-- -----------------------------------------------------------------------------
-- QUE SE CORRIGE Y POR QUE
-- -----------------------------------------------------------------------------
--
-- 1FN - ATRIBUTOS NO ATOMICOS.  Cuatro columnas guardan mas de un valor en una
--       sola celda:
--         airports_data.airport_name   {"en": ..., "ru": ...}
--         airports_data.city           {"en": ..., "ru": ...}
--         aircrafts_data.model         {"en": ..., "ru": ...}
--         airports_data.coordinates    (129.77099,62.09329)
--
-- 2FN - SE CUMPLE EN EL ORIGEN.  Las dos tablas de clave compuesta son
--       ticket_flights -(ticket_no, flight_id) -> clase, monto- y
--       boarding_passes -(ticket_no, flight_id) -> numero, asiento-. En ambas
--       los atributos dependen de la clave COMPLETA. No hay nada que corregir
--       en este nivel y conviene decirlo en vez de inventar una infraccion.
--
-- 3FN - DEPENDENCIAS TRANSITIVAS.  Dos, ambas verificadas sobre los datos:
--         a) flights.flight_no -> (origen, destino, aeronave, duracion).
--            Los 710 numeros de vuelo producen exactamente 710 combinaciones
--            distintas; esos atributos se repetian en 33.121 filas. Nace la
--            tabla `rutas`.
--         b) airports_data.city -> timezone.
--            Las 101 ciudades producen 101 pares (ciudad, zona) pese a haber
--            104 aeropuertos: Moscu tiene tres y Ulianovsk dos. Nace `ciudades`.
--
-- -----------------------------------------------------------------------------
-- DOS PROBLEMAS DE FORMATO QUE, EN ESTE ESTUDIO, SON CRITICOS
-- -----------------------------------------------------------------------------
-- Una investigacion sobre retrasos se calcula restando marcas de tiempo. Los
-- dos defectos que trae la fuente caen justo ahi.
--
-- NULOS DISFRAZADOS.  Las horas reales de los vuelos no operados no son NULL:
--       contienen la cadena literal '\N', marcador de nulo de los volcados de
--       PostgreSQL. Hay 16.348 en actual_departure y 16.406 en actual_arrival,
--       o sea cerca de la mitad de la tabla. Restarlas sin depurarlas no da un
--       error: da un resultado silenciosamente incorrecto. Se convierten con
--       NULLIF.
--
-- FECHAS QUE SQLITE NO SABE LEER.  Las marcas de tiempo vienen como
--       '2017-09-10 09:50:00+03'. El desplazamiento ISO-8601 exige minutos, de
--       modo que julianday() y datetime() devuelven NULL sobre ese texto: la
--       demora, que es una resta de dos marcas, sale NULL en los 33.121 vuelos.
--       Se comprobo que TODAS las marcas de la base llevan el mismo
--       desplazamiento '+03', asi que anadir ':00' es una correccion de formato
--       sin perdida. Tras ella las funciones de fecha de SQLite funcionan.
--
-- -----------------------------------------------------------------------------
-- DECISIONES QUE VAN MAS ALLA DE LA 3FN, DECLARADAS COMO TALES
-- -----------------------------------------------------------------------------
--
-- CATALOGOS DE DOMINIO.  `status` (6 valores repetidos en 33.121 filas) y
--       `fare_conditions` (3 valores repetidos en 1.045.726) pasan a tablas con
--       clave foranea. La 3FN NO lo exige: ambos dependen de la clave de su
--       tabla. Lo exige la integridad de dominio, que hoy no existe: nada
--       impide escribir 'Arrivedd' en el origen.
--
-- ATRIBUTOS DERIVADOS SUPRIMIDOS.  Tampoco lo exige la 3FN. Se suprimen porque
--       guardan por segunda vez un dato que ya esta en otro sitio, y se reponen
--       como vistas para no perder nada:
--         flights.scheduled_arrival  = salida programada + rutas.duracion_min
--                                      (constante en los 710 numeros de vuelo)
--         bookings.total_amount      = suma de los cupones de la reserva
--                                      (coincide en las 262.788 reservas)
--
-- LAS HORAS REALES SI SE CONSERVAN.  No son derivadas de nada: son el dato
--       propio de cada vuelo y la materia prima de esta investigacion. Lo unico
--       que se les hace es convertir su '\N' en NULL de verdad.
--
-- LO QUE NO SE HACE AQUI.  No se calcula ninguna demora, ni distancias, ni
--       clasificaciones. Eso es analisis, no normalizacion.
-- =============================================================================

PRAGMA foreign_keys = OFF;   -- se activa tras construir, para la carga ordenada
PRAGMA journal_mode = MEMORY;
PRAGMA synchronous  = OFF;

ATTACH DATABASE 'travel.sqlite' AS origen;

DROP VIEW  IF EXISTS v_reserva;
DROP VIEW  IF EXISTS v_vuelo;
DROP TABLE IF EXISTS tarjetas_embarque;
DROP TABLE IF EXISTS cupones;
DROP TABLE IF EXISTS pasajes;
DROP TABLE IF EXISTS reservas;
DROP TABLE IF EXISTS vuelos;
DROP TABLE IF EXISTS rutas;
DROP TABLE IF EXISTS asientos;
DROP TABLE IF EXISTS estados_vuelo;
DROP TABLE IF EXISTS clases_tarifarias;
DROP TABLE IF EXISTS aeronaves;
DROP TABLE IF EXISTS aeropuertos;
DROP TABLE IF EXISTS ciudades;


-- =============================================================================
-- 1. CIUDADES          3FN - resuelve  ciudad -> zona horaria
-- =============================================================================
-- La zona horaria y el nombre en ruso dependen de la CIUDAD, no del aeropuerto.
-- Sin esta tabla, los tres aeropuertos de Moscu repiten la misma zona tres
-- veces: es la dependencia transitiva que rompe la 3FN.

CREATE TABLE ciudades (
    ciudad_id     INTEGER PRIMARY KEY,
    nombre        TEXT NOT NULL UNIQUE,
    nombre_ru     TEXT NOT NULL,
    zona_horaria  TEXT NOT NULL
);

INSERT INTO ciudades (nombre, nombre_ru, zona_horaria)
SELECT json_extract(city, '$.en'),
       MIN(json_extract(city, '$.ru')),
       MIN(timezone)
FROM origen.airports_data
GROUP BY json_extract(city, '$.en')
ORDER BY 1;


-- =============================================================================
-- 2. AEROPUERTOS       1FN - desdobla el JSON bilingue y el par de coordenadas
-- =============================================================================
-- `coordinates` llega como '(129.77099,62.09329)': PRIMERO LA LONGITUD, al
-- reves de lo que asume casi toda biblioteca de mapas. Se parte una sola vez
-- aqui en lugar de interpretar texto en cada consulta.

CREATE TABLE aeropuertos (
    codigo     TEXT    PRIMARY KEY,          -- IATA, tres letras
    nombre     TEXT    NOT NULL,
    nombre_ru  TEXT    NOT NULL,
    ciudad_id  INTEGER NOT NULL REFERENCES ciudades (ciudad_id),
    longitud   REAL    NOT NULL CHECK (longitud BETWEEN -180 AND 180),
    latitud    REAL    NOT NULL CHECK (latitud  BETWEEN  -90 AND  90),
    CHECK (length(codigo) = 3)
);

INSERT INTO aeropuertos (codigo, nombre, nombre_ru, ciudad_id, longitud, latitud)
SELECT a.airport_code,
       json_extract(a.airport_name, '$.en'),
       json_extract(a.airport_name, '$.ru'),
       c.ciudad_id,
       CAST(substr(a.coordinates, 2, instr(a.coordinates, ',') - 2) AS REAL),
       CAST(substr(a.coordinates,
                   instr(a.coordinates, ',') + 1,
                   length(a.coordinates) - instr(a.coordinates, ',') - 1) AS REAL)
FROM origen.airports_data a
JOIN ciudades c ON c.nombre = json_extract(a.city, '$.en')
ORDER BY a.airport_code;


-- =============================================================================
-- 3. AERONAVES         1FN - desdobla el JSON bilingue del modelo
-- =============================================================================

CREATE TABLE aeronaves (
    codigo        TEXT PRIMARY KEY,
    modelo        TEXT    NOT NULL,
    modelo_ru     TEXT    NOT NULL,
    autonomia_km  INTEGER NOT NULL CHECK (autonomia_km > 0)
);

INSERT INTO aeronaves (codigo, modelo, modelo_ru, autonomia_km)
SELECT aircraft_code,
       json_extract(model, '$.en'),
       json_extract(model, '$.ru'),
       range
FROM origen.aircrafts_data
ORDER BY aircraft_code;


-- =============================================================================
-- 4. CLASES TARIFARIAS      Integridad de dominio (no lo exige la 3FN)
-- =============================================================================
-- `orden` no es decorativo: sin el, toda agrupacion devuelve Business antes que
-- Economy por razones alfabeticas, invirtiendo la jerarquia real.

CREATE TABLE clases_tarifarias (
    clase_id  INTEGER PRIMARY KEY,
    codigo    TEXT    NOT NULL UNIQUE,
    nombre    TEXT    NOT NULL,
    orden     INTEGER NOT NULL UNIQUE
);

INSERT INTO clases_tarifarias (clase_id, codigo, nombre, orden) VALUES
    (1, 'Economy',  'Economica', 1),
    (2, 'Comfort',  'Confort',   2),
    (3, 'Business', 'Ejecutiva', 3);


-- =============================================================================
-- 5. ESTADOS DEL VUELO      Integridad de dominio (no lo exige la 3FN)
-- =============================================================================

CREATE TABLE estados_vuelo (
    estado_id    INTEGER PRIMARY KEY,
    codigo       TEXT NOT NULL UNIQUE,
    descripcion  TEXT NOT NULL
);

INSERT INTO estados_vuelo (estado_id, codigo, descripcion) VALUES
    (1, 'Scheduled', 'Programado, aun no operado al cierre del volcado'),
    (2, 'On Time',   'En horario, aun no operado'),
    (3, 'Delayed',   'Con demora anunciada, aun no operado'),
    (4, 'Departed',  'En vuelo al cierre del volcado'),
    (5, 'Arrived',   'Completado'),
    (6, 'Cancelled', 'Cancelado');


-- =============================================================================
-- 6. ASIENTOS          Configuracion de cabina por modelo
-- =============================================================================
-- Se conserva el grano del origen -(aeronave, asiento)- y solo se sustituye el
-- texto de la clase por su clave foranea. El numero de asiento NO se descompone
-- en fila y letra: eso seria enriquecimiento, no normalizacion.

CREATE TABLE asientos (
    aeronave_codigo  TEXT    NOT NULL REFERENCES aeronaves (codigo),
    numero           TEXT    NOT NULL,
    clase_id         INTEGER NOT NULL REFERENCES clases_tarifarias (clase_id),
    PRIMARY KEY (aeronave_codigo, numero)
);

INSERT INTO asientos (aeronave_codigo, numero, clase_id)
SELECT s.aircraft_code, s.seat_no, c.clase_id
FROM origen.seats s
JOIN clases_tarifarias c ON c.codigo = s.fare_conditions;


-- =============================================================================
-- 7. RUTAS             3FN - resuelve  flight_no -> (origen, destino, aeronave)
-- =============================================================================
-- Los 710 numeros de vuelo determinan siempre el mismo origen, destino,
-- aeronave y duracion. Esos atributos pertenecen a la RUTA y se repetian en las
-- 33.121 filas de `flights`.
--
-- `duracion_min` se calcula de la diferencia entre las horas programadas, que
-- es constante dentro de cada numero de vuelo. Al extraerla aqui, la columna
-- scheduled_arrival deja de ser necesaria en `vuelos`.

CREATE TABLE rutas (
    numero_vuelo     TEXT    PRIMARY KEY,
    origen           TEXT    NOT NULL REFERENCES aeropuertos (codigo),
    destino          TEXT    NOT NULL REFERENCES aeropuertos (codigo),
    aeronave_codigo  TEXT    NOT NULL REFERENCES aeronaves   (codigo),
    duracion_min     INTEGER NOT NULL CHECK (duracion_min > 0),
    CHECK (origen <> destino)
);

INSERT INTO rutas (numero_vuelo, origen, destino, aeronave_codigo, duracion_min)
SELECT flight_no,
       MIN(departure_airport),
       MIN(arrival_airport),
       MIN(aircraft_code),
       CAST(ROUND(MIN((julianday(scheduled_arrival   || ':00')
                     - julianday(scheduled_departure || ':00')) * 1440)) AS INTEGER)
FROM origen.flights
GROUP BY flight_no
ORDER BY flight_no;


-- =============================================================================
-- 8. VUELOS
-- =============================================================================
-- Queda solo lo que varia de un vuelo a otro. Se van el origen, el destino y la
-- aeronave (ahora en `rutas`) y la llegada programada (derivable).
--
-- Las horas REALES si se conservan: son datos propios del vuelo, no derivados.
-- El '\N' del volcado se convierte en NULL de verdad.

CREATE TABLE vuelos (
    vuelo_id           INTEGER PRIMARY KEY,
    numero_vuelo       TEXT    NOT NULL REFERENCES rutas         (numero_vuelo),
    estado_id          INTEGER NOT NULL REFERENCES estados_vuelo (estado_id),
    salida_programada  TEXT    NOT NULL,   -- ISO-8601 con desplazamiento +03:00
    salida_real        TEXT,               -- NULL si aun no habia ocurrido
    llegada_real       TEXT,
    CHECK (llegada_real IS NULL OR salida_real IS NULL OR llegada_real > salida_real)
);

INSERT INTO vuelos (vuelo_id, numero_vuelo, estado_id, salida_programada,
                    salida_real, llegada_real)
SELECT f.flight_id,
       f.flight_no,
       e.estado_id,
       f.scheduled_departure || ':00',
       NULLIF(f.actual_departure, '\N') || ':00',
       NULLIF(f.actual_arrival,   '\N') || ':00'
FROM origen.flights f
JOIN estados_vuelo e ON e.codigo = f.status
ORDER BY f.flight_id;


-- =============================================================================
-- 9. RESERVAS
-- =============================================================================
-- Se suprime `total_amount`: es la suma de los cupones de la reserva, que ya
-- estan en `cupones`. Se repone en la vista v_reserva.

CREATE TABLE reservas (
    localizador     TEXT PRIMARY KEY,
    fecha_reserva   TEXT NOT NULL,          -- ISO-8601 con desplazamiento +03:00
    CHECK (length(localizador) = 6)
);

INSERT INTO reservas (localizador, fecha_reserva)
SELECT book_ref, book_date || ':00'
FROM origen.bookings
ORDER BY book_ref;


-- =============================================================================
-- 10. PASAJES
-- =============================================================================
-- `passenger_id` resulto UNICO en las 366.733 filas: no identifica a una
-- persona que vuelve, sino a un viajero por pasaje. La restriccion UNIQUE deja
-- constancia del hallazgo en el propio esquema.

CREATE TABLE pasajes (
    numero_pasaje  TEXT NOT NULL PRIMARY KEY,
    localizador    TEXT NOT NULL REFERENCES reservas (localizador),
    pasajero_id    TEXT NOT NULL UNIQUE
);

INSERT INTO pasajes (numero_pasaje, localizador, pasajero_id)
SELECT ticket_no, book_ref, passenger_id
FROM origen.tickets
ORDER BY ticket_no;


-- =============================================================================
-- 11. CUPONES          Un tramo de un pasaje
-- =============================================================================
-- Clave compuesta (pasaje, vuelo), como en el origen. El monto se queda aqui:
-- se comprobo que (vuelo, clase) NO lo determina -34.494 pares producen 50.606
-- combinaciones al anadirlo-, de modo que es un atributo propio del cupon y no
-- de una tarifa, y no procede llevarlo a otra tabla.

CREATE TABLE cupones (
    numero_pasaje  TEXT    NOT NULL REFERENCES pasajes           (numero_pasaje),
    vuelo_id       INTEGER NOT NULL REFERENCES vuelos            (vuelo_id),
    clase_id       INTEGER NOT NULL REFERENCES clases_tarifarias (clase_id),
    monto          REAL    NOT NULL CHECK (monto > 0),
    PRIMARY KEY (numero_pasaje, vuelo_id)
);

INSERT INTO cupones (numero_pasaje, vuelo_id, clase_id, monto)
SELECT tf.ticket_no, tf.flight_id, c.clase_id, tf.amount
FROM origen.ticket_flights tf
JOIN clases_tarifarias c ON c.codigo = tf.fare_conditions;


-- =============================================================================
-- 12. TARJETAS DE EMBARQUE
-- =============================================================================
-- Depende del CUPON, no del pasaje: solo se emite tarjeta para un tramo que se
-- vendio. La clave foranea compuesta lo hace exigible.
--
-- Las dos restricciones UNIQUE -un numero de embarque y un asiento no pueden
-- repetirse dentro del mismo vuelo- se verificaron en la fuente antes de
-- declararlas.

CREATE TABLE tarjetas_embarque (
    numero_pasaje     TEXT    NOT NULL,
    vuelo_id          INTEGER NOT NULL,
    numero_embarque   INTEGER NOT NULL CHECK (numero_embarque > 0),
    asiento           TEXT    NOT NULL,
    PRIMARY KEY (numero_pasaje, vuelo_id),
    FOREIGN KEY (numero_pasaje, vuelo_id)
        REFERENCES cupones (numero_pasaje, vuelo_id),
    UNIQUE (vuelo_id, numero_embarque),
    UNIQUE (vuelo_id, asiento)
);

INSERT INTO tarjetas_embarque (numero_pasaje, vuelo_id, numero_embarque, asiento)
SELECT ticket_no, flight_id, boarding_no, seat_no
FROM origen.boarding_passes;


-- =============================================================================
-- 13. VISTAS - reponen los dos atributos derivados que se suprimieron
-- =============================================================================

CREATE VIEW v_vuelo AS
SELECT v.vuelo_id,
       v.numero_vuelo,
       r.origen,
       r.destino,
       r.aeronave_codigo,
       e.codigo AS estado,
       v.salida_programada,
       -- EL ATRIBUTO DERIVADO, RECALCULADO. Ojo con la zona: datetime() sobre
       -- una marca con desplazamiento convierte a UTC, de modo que la version
       -- ingenua devolvia '2017-09-10 08:30:00' donde la hora local es
       -- '2017-09-10 11:30:00+03:00'. La resta seguia saliendo bien, pero la
       -- columna quedaba en otro huso que el resto de la tabla. Se suma sobre
       -- la marca SIN desplazamiento y se le repone despues.
       datetime(substr(v.salida_programada, 1, 19),
                '+' || r.duracion_min || ' minutes') || '+03:00'
           AS llegada_programada,
       v.salida_real,
       v.llegada_real
FROM vuelos v
JOIN rutas         r ON r.numero_vuelo = v.numero_vuelo
JOIN estados_vuelo e ON e.estado_id    = v.estado_id;

CREATE VIEW v_reserva AS
SELECT r.localizador,
       r.fecha_reserva,
       COUNT(DISTINCT p.numero_pasaje) AS pasajes,
       SUM(c.monto)                    AS monto_total   -- el atributo derivado
FROM reservas r
JOIN pasajes  p ON p.localizador   = r.localizador
JOIN cupones  c ON c.numero_pasaje = p.numero_pasaje
GROUP BY r.localizador, r.fecha_reserva;


-- =============================================================================
-- 14. INDICES
-- =============================================================================
-- La fuente no traia NI UNO. Se crean los de las columnas por las que se filtra
-- o se reune, no uno por columna.

CREATE INDEX ix_aeropuertos_ciudad  ON aeropuertos       (ciudad_id);
CREATE INDEX ix_rutas_origen        ON rutas             (origen);
CREATE INDEX ix_rutas_destino       ON rutas             (destino);
CREATE INDEX ix_vuelos_ruta         ON vuelos            (numero_vuelo);
CREATE INDEX ix_vuelos_estado       ON vuelos            (estado_id);
CREATE INDEX ix_pasajes_reserva     ON pasajes           (localizador);
CREATE INDEX ix_cupones_vuelo       ON cupones           (vuelo_id);
CREATE INDEX ix_cupones_clase       ON cupones           (clase_id);
CREATE INDEX ix_tarjetas_vuelo      ON tarjetas_embarque (vuelo_id);

ANALYZE;
DETACH DATABASE origen;
PRAGMA foreign_keys = ON;
