-- =============================================================================
-- CONVERSION DEL ESQUEMA EN ESTRELLA A DUCKDB
-- Escuela de Estadistica y Ciencias Actuariales (EECA-UCV) - Computacion II
-- =============================================================================
--
-- ORIGEN   travel_analitica.sqlite    7 dimensiones + 2 hechos, en SQLite
-- DESTINO  travel_analitica.duckdb    las mismas tablas, con tipos nativos
--
-- EJECUCION (desde esta carpeta):
--     duckdb travel_analitica.duckdb < conversion_duckdb.sql
--
-- -----------------------------------------------------------------------------
-- POR QUE DUCKDB, Y POR QUE NO
-- -----------------------------------------------------------------------------
-- NO es por velocidad. Con 33.121 vuelos y una base de 5 MB, SQLite responde al
-- instante; prometer rendimiento aqui seria vender humo.
--
-- Es por el REPERTORIO ESTADISTICO. Esta investigacion tiene como objetivo 3
-- "evaluar si la media y la desviacion tipica son resumenes admisibles", y
-- SQLite NO TIENE desviacion tipica. Tampoco moda, ni cuantiles, ni asimetria,
-- ni curtosis, ni correlacion. Todo eso habria que escribirlo a mano con
-- funciones de ventana. DuckDB lo trae:
--
--     stddev_samp   var_samp     median       quantile_cont   quantile_disc
--     mode          skewness     kurtosis     mad             entropy
--     histogram     corr         regr_slope   approx_quantile
--
-- Y es por los TIPOS. SQLite no tiene tipo fecha ni booleano: guarda texto y
-- enteros. Aqui las fechas son DATE, las marcas son TIMESTAMPTZ y las banderas
-- son BOOLEAN, de modo que el motor puede validar y comparar de verdad.
--
-- -----------------------------------------------------------------------------
-- LA ZONA HORARIA: LEASE ANTES DE CONSULTAR ESTA BASE
-- -----------------------------------------------------------------------------
-- `salida_programada` se guarda como TIMESTAMP WITH TIME ZONE, que es la
-- representacion fiel: un instante, con su desplazamiento +03. La consecuencia
-- es que DuckDB lo MUESTRA en la zona de la sesion, no en la de la red.
--
-- Ya nos mordio dos veces en este trabajo, una en SQLite y otra en el perfilado
-- previo: proyectar un instante a fecha en la zona equivocada desplaza el dia y
-- hace aparecer 62 dias de operacion donde hay 61.
--
--     SET TimeZone = 'Europe/Moscow';     <- obligatorio antes de consultar
--
-- El analisis no depende de ello, porque la fecha y la hora locales ya estan
-- materializadas en `fecha_id` y `franja_id` desde la etapa anterior. Solo
-- afecta a como se ve esa columna. Aun asi, la conversion comprueba que la
-- fecha derivada del instante coincide con `fecha_id` en los 33.121 vuelos.
--
-- -----------------------------------------------------------------------------
-- POR QUE NO SE DECLARAN CLAVES FORANEAS AQUI
-- -----------------------------------------------------------------------------
-- Se declararon primero, y se midio lo que cuestan. En DuckDB cada restriccion
-- construye un indice ART, y sobre tablas de este tamano eso pesa mas que los
-- propios datos:
--
--     sin ninguna clave .............................  3,01 MB
--     clave primaria solo en las 7 dimensiones ......  4,76 MB
--     clave primaria en dimensiones y hechos ........  5,76 MB
--     ademas con las 9 foraneas declaradas .......... 12,51 MB
--
-- Las foraneas solas cuestan 6,75 MB: mas del doble de los datos. Y no compran
-- nada aqui, por dos razones. La primera es que esta base es una COPIA DE SOLO
-- LECTURA: nadie va a insertar en ella, de modo que no hay nada que la
-- restriccion pueda impedir. La segunda es que la integridad referencial ya
-- esta exigida y verificada aguas arriba, en travel_analitica.sqlite, donde
-- PRAGMA foreign_key_check no devuelve una sola fila.
--
-- Las PRIMARIAS si se conservan: cuestan 2,75 MB, documentan el grano de cada
-- tabla en el propio esquema y garantizan la unicidad.
--
-- Las relaciones del modelo no se pierden: estan declaradas en la base SQLite,
-- dibujadas en assets/esquema_estrella.png y descritas en DENORMALIZACION.md.
--
-- -----------------------------------------------------------------------------
-- LO QUE NO CAMBIA
-- -----------------------------------------------------------------------------
-- El MODELO es exactamente el mismo: las mismas nueve tablas, las mismas claves
-- y las mismas medidas. Esto no es un rediseno, es un cambio de motor. La base
-- en SQLite se conserva y sigue siendo reproducible sin instalar nada.
-- =============================================================================

INSTALL sqlite;
LOAD sqlite;
SET TimeZone = 'Europe/Moscow';

ATTACH 'travel_analitica.sqlite' AS lite (TYPE sqlite, READ_ONLY);

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
-- DIMENSIONES
-- =============================================================================

CREATE TABLE d_tiempo (
    fecha_id          INTEGER PRIMARY KEY,
    fecha             DATE    NOT NULL UNIQUE,   -- en SQLite era texto
    anio              SMALLINT NOT NULL,
    mes               TINYINT  NOT NULL,
    nombre_mes        VARCHAR  NOT NULL,
    dia               TINYINT  NOT NULL,
    dia_semana        TINYINT  NOT NULL,
    nombre_dia        VARCHAR  NOT NULL,
    semana_iso        TINYINT  NOT NULL,
    es_fin_de_semana  BOOLEAN  NOT NULL,         -- en SQLite era 0/1
    hay_operados      BOOLEAN  NOT NULL
);
INSERT INTO d_tiempo SELECT
    fecha_id, CAST(fecha AS DATE), anio, mes, nombre_mes, dia, dia_semana,
    nombre_dia, semana_iso, es_fin_de_semana <> 0, hay_operados <> 0
FROM lite.d_tiempo;

CREATE TABLE d_franja (
    franja_id  TINYINT PRIMARY KEY,
    hora       VARCHAR NOT NULL,
    bloque     VARCHAR NOT NULL,
    orden      TINYINT NOT NULL
);
INSERT INTO d_franja SELECT franja_id, hora, bloque, orden FROM lite.d_franja;

CREATE TABLE d_aeropuerto (
    aeropuerto_id  INTEGER PRIMARY KEY,
    codigo         VARCHAR NOT NULL UNIQUE,
    nombre         VARCHAR NOT NULL,
    ciudad         VARCHAR NOT NULL,
    zona_horaria   VARCHAR NOT NULL,
    longitud       DOUBLE  NOT NULL,
    latitud        DOUBLE  NOT NULL,
    vuelos_salida  INTEGER NOT NULL,
    banda_trafico  VARCHAR NOT NULL,
    orden_banda    TINYINT NOT NULL
);
INSERT INTO d_aeropuerto SELECT * FROM lite.d_aeropuerto;

CREATE TABLE d_ruta (
    ruta_id                 INTEGER PRIMARY KEY,
    numero_vuelo            VARCHAR  NOT NULL UNIQUE,
    etiqueta                VARCHAR  NOT NULL,
    duracion_programada_min SMALLINT NOT NULL
);
INSERT INTO d_ruta SELECT * FROM lite.d_ruta;

CREATE TABLE d_aeronave (
    aeronave_id     INTEGER  PRIMARY KEY,
    codigo          VARCHAR  NOT NULL UNIQUE,
    modelo          VARCHAR  NOT NULL,
    autonomia_km    INTEGER  NOT NULL,
    asientos_total  SMALLINT NOT NULL
);
INSERT INTO d_aeronave SELECT * FROM lite.d_aeronave;

CREATE TABLE d_estado (
    estado_id    INTEGER PRIMARY KEY,
    codigo       VARCHAR NOT NULL UNIQUE,
    descripcion  VARCHAR NOT NULL,
    es_operado   BOOLEAN NOT NULL
);
INSERT INTO d_estado SELECT estado_id, codigo, descripcion, es_operado <> 0
FROM lite.d_estado;

CREATE TABLE d_regimen (
    regimen_id   INTEGER  PRIMARY KEY,
    etiqueta     VARCHAR  NOT NULL UNIQUE,
    desde_min    SMALLINT NOT NULL,
    hasta_min    SMALLINT NOT NULL,
    descripcion  VARCHAR  NOT NULL,
    orden        TINYINT  NOT NULL
);
INSERT INTO d_regimen SELECT * FROM lite.d_regimen;


-- =============================================================================
-- HECHOS
-- =============================================================================

CREATE TABLE h_vuelos (
    vuelo_id                 INTEGER PRIMARY KEY,
    fecha_id                 INTEGER  NOT NULL,
    franja_id                TINYINT  NOT NULL,
    origen_id                INTEGER  NOT NULL,
    destino_id               INTEGER  NOT NULL,
    ruta_id                  INTEGER  NOT NULL,
    aeronave_id              INTEGER  NOT NULL,
    estado_id                INTEGER  NOT NULL,
    numero_vuelo             VARCHAR  NOT NULL,
    salida_programada        TIMESTAMP WITH TIME ZONE NOT NULL,   -- era texto
    duracion_programada_min  SMALLINT NOT NULL,
    es_operado               BOOLEAN  NOT NULL                    -- era 0/1
);
INSERT INTO h_vuelos SELECT
    vuelo_id, fecha_id, franja_id, origen_id, destino_id, ruta_id, aeronave_id,
    estado_id, numero_vuelo,
    strptime(salida_programada, '%Y-%m-%d %H:%M:%S%z'),
    duracion_programada_min, es_operado <> 0
FROM lite.h_vuelos;

CREATE TABLE h_demoras (
    vuelo_id             INTEGER PRIMARY KEY,
    regimen_id           INTEGER NOT NULL,
    demora_salida_min    SMALLINT NOT NULL,
    demora_llegada_min   SMALLINT,
    minutos_recuperados  SMALLINT,
    duracion_real_min    SMALLINT
);
INSERT INTO h_demoras SELECT * FROM lite.h_demoras;

CREATE TABLE parametros (
    clave  VARCHAR PRIMARY KEY,
    valor  VARCHAR NOT NULL,
    nota   VARCHAR NOT NULL
);
INSERT INTO parametros SELECT * FROM lite.parametros;

DETACH lite;

-- Escribe a disco y compacta. Sin esto el archivo queda con las paginas que la
-- carga fue reservando y pesa un tercio mas de lo necesario.
CHECKPOINT;

-- =============================================================================
-- COMPROBACION DE LA ZONA: la fecha derivada del instante tiene que coincidir
-- con la que la etapa anterior materializo en `fecha_id`.
-- =============================================================================
SELECT 'vuelos cuya fecha derivada del instante NO coincide con fecha_id'
           AS comprobacion,
       COUNT(*) AS casos
FROM h_vuelos v JOIN d_tiempo t ON t.fecha_id = v.fecha_id
WHERE CAST(v.salida_programada AS DATE) <> t.fecha;
