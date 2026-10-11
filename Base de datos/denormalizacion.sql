-- =============================================================================
-- DENORMALIZACION: ESQUEMA EN ESTRELLA PARA LA EXPLOTACION ANALITICA
-- Escuela de Estadistica y Ciencias Actuariales (EECA-UCV) - Computacion II
-- =============================================================================
--
-- ORIGEN   travel_normalizada.sqlite   12 tablas en 3FN
-- DESTINO  travel_analitica.sqlite     7 dimensiones + 2 hechos + parametros
--
-- EJECUCION (desde esta carpeta, solo con el cliente sqlite3):
--     sqlite3 travel_analitica.sqlite < denormalizacion.sql
--
-- -----------------------------------------------------------------------------
-- POR QUE DESNORMALIZAR LO QUE SE ACABA DE NORMALIZAR
-- -----------------------------------------------------------------------------
-- Son dos objetivos opuestos y cada esquema sirve al suyo. La 3FN optimiza la
-- ESCRITURA: cada hecho vive en un solo sitio y no puede contradecirse. El
-- esquema en estrella optimiza la LECTURA y, sobre todo, la COMPRENSION: separa
-- lo que se mide -la demora- de aquello por lo que se mide -el aeropuerto, la
-- hora, el dia, la aeronave-, que es exactamente como estan formuladas las
-- preguntas de la investigacion.
--
-- -----------------------------------------------------------------------------
-- EL GRANO ES EL VUELO, Y HAY DOS TABLAS DE HECHOS EN RELACION 1:0..1
-- -----------------------------------------------------------------------------
--   h_vuelos    33.121 filas - TODOS los vuelos programados
--   h_demoras   16.773 filas - solo los que llegaron a despegar
--
-- La separacion no es un capricho de diseno: es el instrumento que responde al
-- objetivo 2. De los 33.121 vuelos programados, 16.348 no tienen hora real de
-- salida porque al cerrarse el volcado -el 15 de agosto- todavia no habian
-- ocurrido. Las tres alternativas eran:
--
--   a) Cargar solo los operados. Se perderia de vista que la mitad de la
--      programacion no esta observada, que es en si mismo un resultado.
--   b) Cargar todos con la demora en NULL. Peor: AVG() ignora los nulos en
--      silencio, de modo que un promedio mal planteado parece correcto.
--   c) Cargar todos en h_vuelos y solo los observados en h_demoras.
--
-- Se elige (c). La clave primaria de h_demoras ES su clave foranea, asi que la
-- cardinalidad 0..1 la impone el esquema, y la cobertura queda CONTABLE:
-- COUNT(*) sobre cada tabla la responde sin posibilidad de equivocarse de
-- denominador.
--
-- -----------------------------------------------------------------------------
-- DOS CORTES QUE SE DEDUCEN DEL DATO, NO SE ESCRIBEN A MANO
-- -----------------------------------------------------------------------------
-- EL HUECO.  La demora de salida no se distribuye de forma continua: hay un
-- tramo central donde no cae NI UN SOLO vuelo. El limite no se fija por
-- criterio sino buscando la mayor distancia entre dos valores consecutivos
-- observados. Da 11 -> 124, con 113 minutos de salto; el segundo hueco mayor
-- de toda la distribucion es de 9 minutos, de modo que la deteccion no es
-- ambigua. De ahi salen los tres regimenes de `d_regimen`.
--
-- LAS BANDAS DE TRAFICO.  Los 104 aeropuertos no se pueden graficar de uno en
-- uno. Se agrupan por acumulado de vuelos programados, al modo de Pareto:
-- principales los que suman el primer 50 % de la operacion, intermedios hasta
-- el 80 %, secundarios el resto. Salen 14, 31 y 59 aeropuertos. El corte lo
-- calcula el script; si la fuente cambiara, se recalcularia solo.
--
-- -----------------------------------------------------------------------------
-- LA TRAMPA DE LA FECHA LOCAL
-- -----------------------------------------------------------------------------
-- Las marcas de tiempo llevan desplazamiento '+03:00' y las funciones de fecha
-- de SQLite convierten a UTC antes de operar:
--
--     date('2017-07-30 01:50:00+03:00')  ->  '2017-07-29'
--
-- Usar date() atribuiria 79 vuelos al dia anterior y haria aparecer 62 dias de
-- operacion donde hay 61. Este script toma la fecha local con substr(x, 1, 10)
-- y la hora con substr(x, 12, 2), exactos porque toda la base esta en +03. Las
-- diferencias en minutos si usan julianday() sobre la marca completa: ahi la
-- conversion se cancela entre los dos operandos.
-- =============================================================================

PRAGMA journal_mode = MEMORY;
PRAGMA synchronous  = OFF;
PRAGMA temp_store   = MEMORY;
PRAGMA foreign_keys = OFF;   -- se carga en orden; se activa al final

ATTACH DATABASE 'travel_normalizada.sqlite' AS norm;

DROP TABLE IF EXISTS h_demoras;
DROP TABLE IF EXISTS h_vuelos;
DROP TABLE IF EXISTS d_tiempo;
DROP TABLE IF EXISTS d_franja;
DROP TABLE IF EXISTS d_aeropuerto;
DROP TABLE IF EXISTS d_ruta;
DROP TABLE IF EXISTS d_aeronave;
DROP TABLE IF EXISTS d_estado;
DROP TABLE IF EXISTS d_regimen;
DROP TABLE IF EXISTS parametros;


-- =============================================================================
-- PREPARACION - LA DEMORA, CALCULADA UNA SOLA VEZ
-- =============================================================================
-- `demora_llegada` y `duracion_real` quedan en NULL para los 58 vuelos que
-- estaban EN EL AIRE cuando se congelo el volcado: despegaron pero aun no
-- habian aterrizado. No es un fallo de carga, es su situacion real.

CREATE TEMP TABLE demora AS
SELECT v.vuelo_id,
       CAST(ROUND((julianday(v.salida_real) - julianday(v.salida_programada)) * 1440) AS INTEGER) AS dem_salida,
       CAST(ROUND((julianday(v.llegada_real) - julianday(vv.llegada_programada)) * 1440) AS INTEGER) AS dem_llegada,
       CAST(ROUND((julianday(v.llegada_real) - julianday(v.salida_real)) * 1440) AS INTEGER) AS dur_real
FROM norm.vuelos v
JOIN norm.v_vuelo vv ON vv.vuelo_id = v.vuelo_id
WHERE v.salida_real IS NOT NULL;

CREATE INDEX tmp_demora_vuelo ON demora (vuelo_id);


-- =============================================================================
-- DIMENSION  d_tiempo        rol: fecha de salida programada
-- =============================================================================
-- `hay_operados` marca los dias en los que existe al menos una salida real.
-- Son 31 de 61: a partir del 16 de agosto la programacion continua pero el
-- registro se acaba. Dejar esa frontera dentro de la dimension evita que un
-- grafico por fecha insinue una caida de actividad que en realidad es el borde
-- del volcado.

CREATE TABLE d_tiempo (
    fecha_id          INTEGER PRIMARY KEY,   -- AAAAMMDD
    fecha             TEXT    NOT NULL UNIQUE,
    anio              INTEGER NOT NULL,
    mes               INTEGER NOT NULL,
    nombre_mes        TEXT    NOT NULL,
    dia               INTEGER NOT NULL,
    dia_semana        INTEGER NOT NULL,      -- 1 lunes ... 7 domingo (ISO)
    nombre_dia        TEXT    NOT NULL,
    semana_iso        INTEGER NOT NULL,
    es_fin_de_semana  INTEGER NOT NULL,
    hay_operados      INTEGER NOT NULL
);

INSERT INTO d_tiempo
WITH RECURSIVE dias(f) AS (
    SELECT (SELECT MIN(substr(salida_programada,1,10)) FROM norm.vuelos)
    UNION ALL
    SELECT date(f, '+1 day') FROM dias
    WHERE f < (SELECT MAX(substr(salida_programada,1,10)) FROM norm.vuelos)
)
SELECT CAST(replace(f,'-','') AS INTEGER), f,
       CAST(strftime('%Y',f) AS INTEGER), CAST(strftime('%m',f) AS INTEGER),
       CASE CAST(strftime('%m',f) AS INTEGER) WHEN 7 THEN 'Julio'
            WHEN 8 THEN 'Agosto' ELSE 'Septiembre' END,
       CAST(strftime('%d',f) AS INTEGER),
       CASE CAST(strftime('%w',f) AS INTEGER) WHEN 0 THEN 7
            ELSE CAST(strftime('%w',f) AS INTEGER) END,
       CASE CAST(strftime('%w',f) AS INTEGER)
            WHEN 0 THEN 'Domingo'   WHEN 1 THEN 'Lunes'  WHEN 2 THEN 'Martes'
            WHEN 3 THEN 'Miercoles' WHEN 4 THEN 'Jueves' WHEN 5 THEN 'Viernes'
            ELSE 'Sabado' END,
       CAST(strftime('%W',f) AS INTEGER),
       CASE WHEN strftime('%w',f) IN ('0','6') THEN 1 ELSE 0 END,
       CASE WHEN EXISTS (SELECT 1 FROM norm.vuelos
                         WHERE substr(salida_programada,1,10) = f
                           AND salida_real IS NOT NULL) THEN 1 ELSE 0 END
FROM dias;


-- =============================================================================
-- DIMENSION  d_franja        hora programada de salida
-- =============================================================================

CREATE TABLE d_franja (
    franja_id  INTEGER PRIMARY KEY,   -- la hora, 0 a 23
    hora       TEXT    NOT NULL,      -- '09:00'
    bloque     TEXT    NOT NULL,      -- Madrugada / Manana / Tarde / Noche
    orden      INTEGER NOT NULL
);

INSERT INTO d_franja
WITH RECURSIVE h(n) AS (SELECT 0 UNION ALL SELECT n+1 FROM h WHERE n < 23)
SELECT n, printf('%02d:00', n),
       CASE WHEN n < 6 THEN 'Madrugada' WHEN n < 12 THEN 'Manana'
            WHEN n < 18 THEN 'Tarde' ELSE 'Noche' END,
       CASE WHEN n < 6 THEN 1 WHEN n < 12 THEN 2 WHEN n < 18 THEN 3 ELSE 4 END
FROM h;


-- =============================================================================
-- DIMENSION  d_aeropuerto    CONFORMADA - rol: origen y destino
-- =============================================================================
-- Dimension PLANA: la ciudad y su zona horaria viajan dentro, aunque en la base
-- normalizada vivan en `ciudades`. Snowflakear la dimension la partiria en dos
-- y obligaria al tablero a una reunion mas.
--
-- `banda_trafico` es el atributo que hace legible el objetivo 4: sin el, toda
-- comparacion entre aeropuertos son 104 barras.

CREATE TABLE d_aeropuerto (
    aeropuerto_id     INTEGER PRIMARY KEY,
    codigo            TEXT    NOT NULL UNIQUE,
    nombre            TEXT    NOT NULL,
    ciudad            TEXT    NOT NULL,
    zona_horaria      TEXT    NOT NULL,
    longitud          REAL    NOT NULL,
    latitud           REAL    NOT NULL,
    vuelos_salida     INTEGER NOT NULL,
    banda_trafico     TEXT    NOT NULL,
    orden_banda       INTEGER NOT NULL
);

INSERT INTO d_aeropuerto (codigo, nombre, ciudad, zona_horaria, longitud, latitud,
                          vuelos_salida, banda_trafico, orden_banda)
WITH salidas AS (
    SELECT r.origen AS codigo, COUNT(*) AS n
    FROM norm.vuelos v JOIN norm.rutas r ON r.numero_vuelo = v.numero_vuelo
    GROUP BY r.origen
),
bandas AS (
    SELECT codigo, n,
           SUM(n) OVER (ORDER BY n DESC, codigo ROWS UNBOUNDED PRECEDING) AS acumulado,
           (SELECT SUM(n) FROM salidas) AS total
    FROM salidas
)
SELECT a.codigo, a.nombre, c.nombre, c.zona_horaria, a.longitud, a.latitud,
       COALESCE(b.n, 0),
       CASE WHEN b.n IS NULL                     THEN 'Sin salidas'
            WHEN b.acumulado <= 0.5 * b.total    THEN 'Principal'
            WHEN b.acumulado <= 0.8 * b.total    THEN 'Intermedio'
            ELSE                                      'Secundario' END,
       CASE WHEN b.n IS NULL                     THEN 4
            WHEN b.acumulado <= 0.5 * b.total    THEN 1
            WHEN b.acumulado <= 0.8 * b.total    THEN 2
            ELSE                                      3 END
FROM norm.aeropuertos a
JOIN norm.ciudades    c ON c.ciudad_id = a.ciudad_id
LEFT JOIN bandas      b ON b.codigo    = a.codigo
ORDER BY a.codigo;


-- =============================================================================
-- DIMENSION  d_ruta
-- =============================================================================
-- Guarda solo lo que pertenece a la RUTA y no es ya una dimension propia: su
-- numero, una etiqueta legible y la duracion programada. El origen y el destino
-- NO se duplican aqui: viajan como claves foraneas de la tabla de hechos, que
-- es donde el modelo en estrella los coloca.

CREATE TABLE d_ruta (
    ruta_id                 INTEGER PRIMARY KEY,
    numero_vuelo            TEXT    NOT NULL UNIQUE,
    etiqueta                TEXT    NOT NULL,     -- 'DME - LED'
    duracion_programada_min INTEGER NOT NULL
);

INSERT INTO d_ruta (numero_vuelo, etiqueta, duracion_programada_min)
SELECT numero_vuelo, origen || ' - ' || destino, duracion_min
FROM norm.rutas ORDER BY numero_vuelo;


-- =============================================================================
-- DIMENSION  d_aeronave
-- =============================================================================

CREATE TABLE d_aeronave (
    aeronave_id     INTEGER PRIMARY KEY,
    codigo          TEXT    NOT NULL UNIQUE,
    modelo          TEXT    NOT NULL,
    autonomia_km    INTEGER NOT NULL,
    asientos_total  INTEGER NOT NULL
);

INSERT INTO d_aeronave (codigo, modelo, autonomia_km, asientos_total)
SELECT a.codigo, a.modelo, a.autonomia_km, COUNT(s.numero)
FROM norm.aeronaves a JOIN norm.asientos s ON s.aeronave_codigo = a.codigo
GROUP BY a.codigo, a.modelo, a.autonomia_km
ORDER BY a.codigo;


-- =============================================================================
-- DIMENSION  d_estado
-- =============================================================================

CREATE TABLE d_estado (
    estado_id    INTEGER PRIMARY KEY,
    codigo       TEXT    NOT NULL UNIQUE,
    descripcion  TEXT    NOT NULL,
    es_operado   INTEGER NOT NULL
);

INSERT INTO d_estado
SELECT estado_id, codigo, descripcion,
       CASE WHEN codigo IN ('Departed','Arrived') THEN 1 ELSE 0 END
FROM norm.estados_vuelo;


-- =============================================================================
-- DIMENSION  d_regimen       la dimension propia de esta investigacion
-- =============================================================================
-- Sus tres filas NO se escriben a mano: los limites salen de buscar la mayor
-- distancia entre dos valores consecutivos de la demora observada.

CREATE TABLE d_regimen (
    regimen_id  INTEGER PRIMARY KEY,
    etiqueta    TEXT    NOT NULL UNIQUE,
    desde_min   INTEGER NOT NULL,
    hasta_min   INTEGER NOT NULL,
    descripcion TEXT    NOT NULL,
    orden       INTEGER NOT NULL UNIQUE
);

INSERT INTO d_regimen
WITH distintos AS (SELECT DISTINCT dem_salida m FROM demora),
     saltos AS (SELECT m, LEAD(m) OVER (ORDER BY m) sig FROM distintos),
     hueco AS (SELECT m AS fin_bajo, sig AS inicio_alto FROM saltos
               WHERE sig IS NOT NULL ORDER BY sig - m DESC LIMIT 1)
SELECT 1, 'Puntual', 0, 0,
       'Sale a la hora programada, al minuto.', 1 FROM hueco
UNION ALL
SELECT 2, 'Demora breve', 1, fin_bajo,
       'Modo bajo de la distribucion: se agota en los ' || fin_bajo || ' minutos.', 2 FROM hueco
UNION ALL
SELECT 3, 'Demora prolongada', inicio_alto, (SELECT MAX(dem_salida) FROM demora),
       'Modo alto: no empieza hasta los ' || inicio_alto || ' minutos.', 3 FROM hueco;


-- =============================================================================
-- HECHO  h_vuelos            GRANO: EL VUELO PROGRAMADO
-- =============================================================================
-- Carga los 33.121. Su medida principal es `es_operado`: sumada da la cobertura
-- del registro, que es el objetivo 2.

CREATE TABLE h_vuelos (
    vuelo_id                 INTEGER NOT NULL PRIMARY KEY,
    fecha_id                 INTEGER NOT NULL REFERENCES d_tiempo     (fecha_id),
    franja_id                INTEGER NOT NULL REFERENCES d_franja     (franja_id),
    origen_id                INTEGER NOT NULL REFERENCES d_aeropuerto (aeropuerto_id),
    destino_id               INTEGER NOT NULL REFERENCES d_aeropuerto (aeropuerto_id),
    ruta_id                  INTEGER NOT NULL REFERENCES d_ruta       (ruta_id),
    aeronave_id              INTEGER NOT NULL REFERENCES d_aeronave   (aeronave_id),
    estado_id                INTEGER NOT NULL REFERENCES d_estado     (estado_id),
    numero_vuelo             TEXT    NOT NULL,          -- degenerada
    salida_programada        TEXT    NOT NULL,
    duracion_programada_min  INTEGER NOT NULL,
    es_operado               INTEGER NOT NULL
);

INSERT INTO h_vuelos
SELECT v.vuelo_id,
       CAST(replace(substr(v.salida_programada,1,10),'-','') AS INTEGER),
       CAST(substr(v.salida_programada,12,2) AS INTEGER),
       ao.aeropuerto_id, ad.aeropuerto_id, ru.ruta_id, an.aeronave_id, v.estado_id,
       v.numero_vuelo, v.salida_programada, r.duracion_min,
       CASE WHEN v.salida_real IS NULL THEN 0 ELSE 1 END
FROM norm.vuelos v
JOIN norm.rutas     r  ON r.numero_vuelo = v.numero_vuelo
JOIN d_aeropuerto   ao ON ao.codigo      = r.origen
JOIN d_aeropuerto   ad ON ad.codigo      = r.destino
JOIN d_ruta         ru ON ru.numero_vuelo = v.numero_vuelo
JOIN d_aeronave     an ON an.codigo      = r.aeronave_codigo;


-- =============================================================================
-- HECHO  h_demoras           GRANO: EL VUELO OPERADO   (1:0..1 sobre h_vuelos)
-- =============================================================================
-- La clave primaria ES la foranea: eso impone la cardinalidad 0..1 y hace
-- imposible que un vuelo aparezca dos veces o que uno no observado aparezca.
--
-- `minutos_recuperados` es la demora de salida menos la de llegada: positivo si
-- el vuelo recorto tiempo en el aire, negativo si lo perdio.

CREATE TABLE h_demoras (
    vuelo_id             INTEGER NOT NULL PRIMARY KEY REFERENCES h_vuelos  (vuelo_id),
    regimen_id           INTEGER NOT NULL             REFERENCES d_regimen (regimen_id),
    demora_salida_min    INTEGER NOT NULL,
    demora_llegada_min   INTEGER,          -- NULL en los 58 vuelos en el aire
    minutos_recuperados  INTEGER,          -- NULL por la misma razon
    duracion_real_min    INTEGER           -- NULL por la misma razon
);

INSERT INTO h_demoras
SELECT d.vuelo_id,
       (SELECT regimen_id FROM d_regimen g
        WHERE d.dem_salida BETWEEN g.desde_min AND g.hasta_min),
       d.dem_salida, d.dem_llegada,
       CASE WHEN d.dem_llegada IS NULL THEN NULL ELSE d.dem_salida - d.dem_llegada END,
       d.dur_real
FROM demora d;


-- =============================================================================
-- PARAMETROS - lo que el script dedujo, a la vista
-- =============================================================================

CREATE TABLE parametros (
    clave  TEXT PRIMARY KEY,
    valor  TEXT NOT NULL,
    nota   TEXT NOT NULL
);

-- El tramo vacio es, por definicion, lo que queda entre los dos regimenes: del
-- minuto siguiente al final del modo bajo al anterior al inicio del alto.
INSERT INTO parametros
SELECT 'hueco_desde',
       CAST((SELECT hasta_min + 1 FROM d_regimen WHERE regimen_id = 2) AS TEXT),
       'Primer minuto del tramo en el que no cae ningun vuelo.';

INSERT INTO parametros
SELECT 'hueco_hasta',
       CAST((SELECT desde_min - 1 FROM d_regimen WHERE regimen_id = 3) AS TEXT),
       'Ultimo minuto del tramo vacio.';

INSERT INTO parametros
SELECT 'minutos_sin_un_solo_vuelo',
       CAST((SELECT desde_min FROM d_regimen WHERE regimen_id = 3)
          - (SELECT hasta_min FROM d_regimen WHERE regimen_id = 2) - 1 AS TEXT),
       'Amplitud del tramo vacio, en minutos.';

INSERT INTO parametros
SELECT 'demora_media_min', CAST(ROUND(AVG(demora_salida_min), 2) AS TEXT),
       'Demora media de salida de los vuelos operados.'
FROM h_demoras;

INSERT INTO parametros
SELECT 'media_cae_en_el_hueco',
       CASE WHEN (SELECT AVG(demora_salida_min) FROM h_demoras)
                 BETWEEN (SELECT CAST(valor AS INTEGER) FROM parametros WHERE clave='hueco_desde')
                     AND (SELECT CAST(valor AS INTEGER) FROM parametros WHERE clave='hueco_hasta')
            THEN 'si' ELSE 'no' END,
       'Si la media cae en el tramo vacio, ningun vuelo tiene la demora media.';

INSERT INTO parametros
SELECT 'cobertura_operada',
       (SELECT CAST(COUNT(*) AS TEXT) FROM h_demoras) || ' de '
       || (SELECT CAST(COUNT(*) AS TEXT) FROM h_vuelos),
       'Vuelos con hora real de salida sobre el total programado.';


-- =============================================================================
-- INDICES DE LECTURA
-- =============================================================================

CREATE INDEX ix_vue_fecha     ON h_vuelos  (fecha_id);
CREATE INDEX ix_vue_franja    ON h_vuelos  (franja_id);
CREATE INDEX ix_vue_origen    ON h_vuelos  (origen_id);
CREATE INDEX ix_vue_destino   ON h_vuelos  (destino_id);
CREATE INDEX ix_vue_ruta      ON h_vuelos  (ruta_id);
CREATE INDEX ix_vue_aeronave  ON h_vuelos  (aeronave_id);
CREATE INDEX ix_vue_operado   ON h_vuelos  (es_operado);
CREATE INDEX ix_dem_regimen   ON h_demoras (regimen_id);

ANALYZE;
DETACH DATABASE norm;
PRAGMA foreign_keys = ON;
