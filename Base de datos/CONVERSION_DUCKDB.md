# Conversión a DuckDB

El mismo esquema en estrella, en un motor analítico. No es un rediseño: son las
mismas nueve tablas, las mismas claves y las mismas medidas, con tipos nativos.

```bash
cd "Base de datos"
duckdb travel_analitica.duckdb < conversion_duckdb.sql
```

Tarda **0,2 segundos**. Como las dos etapas anteriores, es un archivo `.sql` que
se ejecuta desde la línea de comandos: todo el proceso de datos del trabajo
—normalizar, desnormalizar, convertir— se reproduce con dos clientes y ningún
lenguaje de programación.

---

## 1. Por qué DuckDB, y por qué no

**No es por velocidad.** Con 33.121 vuelos y una base de 5 MB, SQLite responde
al instante. Decir que DuckDB acelera esto sería vender humo.

**Es por el repertorio estadístico.** El objetivo 3 de esta investigación es
*«evaluar si la media y la desviación típica son resúmenes admisibles»*, y
**SQLite no tiene desviación típica**:

| Función | DuckDB | SQLite |
|---|:---:|:---:|
| `stddev_samp`, `var_samp` | ✓ | **no existe** |
| `mode` | ✓ | **no existe** |
| `skewness`, `kurtosis` | ✓ | **no existe** |
| `mad` | ✓ | **no existe** |
| `corr`, `regr_slope` | ✓ | **no existe** |
| `histogram`, `entropy` | ✓ | **no existe** |
| `quantile_cont`, `quantile_disc` | ✓ | **no existe** |
| `median` | ✓ | sólo en algunas compilaciones |

Sin ellas habría que escribir a mano, con funciones de ventana, lo que el
objetivo central del trabajo necesita medir.

> Sobre `median`: existe en el SQLite de algunas plataformas, pero no es parte
> del lenguaje estándar. Apoyarse en ella haría que el trabajo dejara de
> reproducirse en otra instalación.

---

## 2. Lo que el repertorio deja ver de inmediato

Una sola consulta sobre `h_demoras`:

| Estadístico | Valor |
|---|---:|
| Vuelos | 16.773 |
| **Media** | **12,21 min** |
| **Mediana** | **3 min** |
| **Moda** | **3 min** |
| Desviación típica | 41,41 |
| Varianza | 1.715,18 |
| **Coeficiente de variación** | **339,28 %** |
| Asimetría | 4,34 |
| Curtosis | 17,22 |
| Desviación absoluta mediana (MAD) | 1 |
| Cuartiles (25 / 50 / 75) | 2 / 3 / 4 |
| Percentil 95 | 9 |

La media **cuadruplica** a la mediana. El coeficiente de variación supera el
300 %. Y el dato que lo cierra: **la media, 12,21 minutos, es mayor que el
percentil 95, que son 9 minutos**. Es decir, **el 95,23 % de los vuelos tiene
una demora inferior a la media**.

Un promedio que deja por debajo a diecinueve de cada veinte observaciones no
resume: desplaza. El objetivo 3 queda contestado con números propios y no con
una impresión.

---

## 3. Los tipos, que SQLite no tiene

| Columna | En SQLite | En DuckDB |
|---|---|---|
| `d_tiempo.fecha` | texto | **`DATE`** |
| `h_vuelos.salida_programada` | texto | **`TIMESTAMP WITH TIME ZONE`** |
| `es_operado`, `es_fin_de_semana`, `hay_operados`, `es_operado` | 0 / 1 | **`BOOLEAN`** |
| `duracion_programada_min`, `demora_salida_min` | sin tipo | `SMALLINT` |
| `franja_id`, `mes`, `dia` | sin tipo | `TINYINT` |

SQLite no tiene tipo fecha ni booleano: guarda texto y enteros, y la
correspondencia vive en la cabeza de quien consulta. Aquí el motor la conoce.

---

## 4. La zona horaria: léase antes de consultar esta base

`salida_programada` se guarda como `TIMESTAMP WITH TIME ZONE`, que es la
representación fiel: un instante con su desplazamiento `+03`. La consecuencia
es que **DuckDB lo muestra en la zona de la sesión, no en la de la red**.

```sql
SET TimeZone = 'Europe/Moscow';   -- obligatorio antes de consultar
```

Esto ya nos mordió dos veces en este trabajo. El análisis no depende de ello
—la fecha y la hora locales están materializadas en `fecha_id` y `franja_id`
desde la etapa anterior— pero la conversión lo comprueba de todos modos: la
fecha derivada del instante coincide con `fecha_id` en los **33.121** vuelos,
sin una sola excepción.

---

## 5. Por qué no se declaran claves foráneas

Se declararon primero, y después se midió lo que cuestan. En DuckDB cada
restricción construye un índice ART, y sobre tablas de este tamaño eso pesa más
que los propios datos:

| Variante | Tamaño |
|---|---:|
| Sin ninguna clave | 3,01 MB |
| Clave primaria sólo en las 7 dimensiones | 4,76 MB |
| Clave primaria en dimensiones y hechos | 5,76 MB |
| **Además con las 9 foráneas declaradas** | **12,51 MB** |

Las foráneas solas cuestan **6,75 MB**, más del doble que los datos. Y aquí no
compran nada, por dos razones:

1. Esta base es una **copia de sólo lectura**. Nadie va a insertar en ella, de
   modo que no hay nada que la restricción pueda impedir.
2. La integridad referencial ya está **exigida y verificada aguas arriba**, en
   `travel_analitica.sqlite`, donde `PRAGMA foreign_key_check` no devuelve una
   sola fila.

Las primarias sí se conservan: documentan el grano de cada tabla en el propio
esquema y garantizan la unicidad.

Las relaciones del modelo no se pierden. Están declaradas en la base SQLite,
dibujadas en [`esquema_estrella.png`](../assets/esquema_estrella.png) y
descritas en [DENORMALIZACION.md](DENORMALIZACION.md).

**Una hipótesis que resultó falsa.** Antes de medir supuse que construir el
índice durante la carga lo dejaría más fragmentado que construirlo después. Se
probaron las dos variantes y dan **exactamente el mismo tamaño**: 6,01 MB. La
suposición no se sostenía y el script conserva la forma más legible, con la
clave declarada en el `CREATE TABLE`.

---

## 6. El tamaño, y por qué no baja

| | Tamaño |
|---|---:|
| `travel_analitica.sqlite` | 5,05 MB |
| `travel_analitica.duckdb` | **7,51 MB** |

DuckDB comprime por columnas y debería ser más pequeño. No lo es, y el motivo
no es desperdicio:

```
database_size  block_size  total_blocks  used_blocks  free_blocks
7.5 MiB        262144      30            30           0
```

**Treinta bloques, cero libres.** El bloque de DuckDB es de 256 KB y cada tabla
y cada índice necesita al menos uno; una base con una sola tabla vacía ya ocupa
0,26 MB. Con diez tablas y sus claves, la granularidad del formato domina sobre
el contenido.

Es el reverso exacto de la ventaja de DuckDB: el formato está pensado para que
la compresión columnar brille con millones de filas, y aquí hay treinta y tres
mil. Se asume el coste porque lo que se compra son las funciones, no los bytes.

---

## 7. Verificación cruzada

Doce consultas —los conteos, las sumas, y una por cada objetivo del
trabajo— ejecutadas contra los dos motores:

| Consulta | SQLite | DuckDB |
|---|---:|---:|
| Vuelos programados | 33.121 | 33.121 |
| Vuelos operados | 16.773 | 16.773 |
| Suma de minutos de demora | 204.740 | 204.740 |
| Demora máxima | 277 | 277 |
| Vuelos en el hueco 12–123 | 0 | 0 |
| Demoras prolongadas | 800 | 800 |
| Retraso de la banda Principal | 103.047 | 103.047 |
| Vuelos del bloque Noche | 1.568 | 1.568 |
| Minutos netos recuperados | −105 | −105 |
| Días con operados | 31 | 31 |
| Rutas | 710 | 710 |
| Cobertura (`SUM(es_operado)`) | 16.773 | 16.773 |

**Las doce coinciden.** El cambio de motor no movió un solo número.

---

## 8. Lo que no cambia, y lo que se descartó

**La base SQLite se conserva** y sigue siendo el origen de ésta. Quien quiera
reproducir el trabajo hasta el esquema en estrella no necesita instalar DuckDB.

**MotherDuck se descartó.** Se evaluó y no resuelve ningún problema de este
trabajo: la base analítica pesa megabytes, cabe en el repositorio y el
aplicativo puede ser autocontenido. Añadiría una dependencia externa, una
credencial que gestionar y un punto de fallo, a cambio de nada que aquí haga
falta.

**Esta base es la que usa el aplicativo.** Se versiona y se abre en sólo
lectura, sin copia ni conversión al arrancar. Todo el trabajo analítico —el
aplicativo y el extracto de Tableau— se consulta sobre ella.
