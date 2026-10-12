"""
Construye el extracto de Tableau leyendo DIRECTAMENTE de la base DuckDB.

POR QUE NO HAY CSV POR EL CAMINO
--------------------------------
Un CSV intermedio es una copia sin tipos: todo se vuelve texto y Tableau tiene
que adivinar al leerlo. Adivina mal con frecuencia -las fechas, los decimales
segun la configuracion regional, los acentos segun la codificacion- y cada
error aparece en el tablero, no en el script, que es donde se puede corregir.

`.hyper` es el formato NATIVO de extracto de Tableau: columnar, tipado y con
indices. Los datos van de DuckDB a Hyper sin pasar por ningun formato de texto,
de modo que un `SMALLINT` llega como entero y una fecha como fecha.

Tableau Public, ademas, no admite conexiones en vivo: solo publica extractos.
Aunque hubiera un conector DuckDB para Tableau, el tablero publicado acabaria
siendo un extracto igualmente.

POR QUE CUATRO TABLAS Y NO UNA
------------------------------
Cada hoja del tablero tiene su propio GRANO. Con una sola tabla al grano mas
fino, cada hoja tendria que reagregar y bastaria un filtro mal puesto para que
una cifra dejara de cuadrar con el aplicativo. Se entrega a cada hoja la tabla
que necesita, agregada en SQL, donde el resultado se verifica contra la base.

El INDICE DE CONCENTRACION, en particular, es un cociente de cuotas. En Tableau
exigiria una expresion de nivel de detalle que se rompe en cuanto alguien
aplica un filtro. Calculado aqui, es una columna.
"""

from pathlib import Path

import duckdb
from tableauhyperapi import (Connection, CreateMode, HyperProcess, Inserter,
                             NULLABLE, SqlType, TableDefinition, TableName,
                             Telemetry)

AQUI = Path(__file__).resolve().parent
BASE = AQUI.parent / "Base de datos" / "travel_analitica.duckdb"
DESTINO = AQUI / "retraso_red_aerea_2017.hyper"

CONSULTAS = {
    # --- hoja 1: la cobertura del registro, dia a dia --------------------
    "cobertura": """
        SELECT t.fecha, t.nombre_dia, t.es_fin_de_semana, t.hay_operados,
               COUNT(*)::INTEGER              AS programados,
               SUM(v.es_operado::INT)::INTEGER AS operados
        FROM h_vuelos v JOIN d_tiempo t ON t.fecha_id = v.fecha_id
        GROUP BY 1, 2, 3, 4 ORDER BY 1
    """,
    # --- hoja 2: la distribucion, con su hueco ---------------------------
    "distribucion": """
        SELECT d.demora_salida_min::INTEGER AS minutos,
               g.etiqueta                   AS regimen,
               g.orden::INTEGER             AS orden_regimen,
               COUNT(*)::INTEGER            AS vuelos
        FROM h_demoras d JOIN d_regimen g ON g.regimen_id = d.regimen_id
        GROUP BY 1, 2, 3 ORDER BY 1
    """,
    # --- hoja 3: el mapa y la concentracion ------------------------------
    "aeropuertos": """
        WITH t AS (SELECT (SELECT COUNT(*) FROM h_demoras) tv,
                          (SELECT SUM(demora_salida_min) FROM h_demoras) tm)
        SELECT a.codigo, a.nombre, a.ciudad,
               a.banda_trafico                                  AS banda,
               a.orden_banda::INTEGER                           AS orden_banda,
               a.longitud, a.latitud,
               COUNT(*)::INTEGER                                AS vuelos,
               SUM(d.demora_salida_min)::INTEGER                AS minutos,
               (COUNT(*) FILTER (WHERE d.regimen_id = 3))::INTEGER AS prolongadas,
               ROUND(AVG(d.demora_salida_min), 2)               AS demora_media,
               ROUND(100.0 * COUNT(*) / MAX(t.tv), 4)           AS pct_vuelos,
               ROUND(100.0 * SUM(d.demora_salida_min) / MAX(t.tm), 4) AS pct_retraso,
               ROUND((1.0 * SUM(d.demora_salida_min) / MAX(t.tm))
                     / (1.0 * COUNT(*) / MAX(t.tv)), 4)         AS indice
        FROM h_demoras d
        JOIN h_vuelos     v ON v.vuelo_id      = d.vuelo_id
        JOIN d_aeropuerto a ON a.aeropuerto_id = v.origen_id, t
        GROUP BY 1, 2, 3, 4, 5, 6, 7 ORDER BY minutos DESC
    """,
    # --- hoja 4: el reparto temporal -------------------------------------
    "tiempo": """
        SELECT f.franja_id::INTEGER   AS hora,
               f.hora                 AS etiqueta_hora,
               f.bloque,
               f.orden::INTEGER       AS orden_bloque,
               t.nombre_dia,
               t.dia_semana::INTEGER  AS dia_semana,
               COUNT(*)::INTEGER                                AS vuelos,
               ROUND(AVG(d.demora_salida_min), 2)               AS demora_media,
               (COUNT(*) FILTER (WHERE d.regimen_id = 3))::INTEGER AS prolongadas
        FROM h_demoras d
        JOIN h_vuelos v ON v.vuelo_id  = d.vuelo_id
        JOIN d_franja f ON f.franja_id = v.franja_id
        JOIN d_tiempo t ON t.fecha_id  = v.fecha_id
        GROUP BY 1, 2, 3, 4, 5, 6 ORDER BY 6, 1
    """,
}

# Correspondencia de tipos DuckDB -> Hyper. Es lo que el CSV perdia.
TIPOS = {
    "INTEGER": SqlType.int, "BIGINT": SqlType.big_int,
    "SMALLINT": SqlType.small_int, "TINYINT": SqlType.small_int,
    "DOUBLE": SqlType.double, "FLOAT": SqlType.double,
    "BOOLEAN": SqlType.bool, "DATE": SqlType.date,
    "VARCHAR": SqlType.text,
}


def tipo_hyper(tipo_duckdb) -> SqlType:
    # `relacion.types` devuelve objetos DuckDBPyType, no cadenas.
    base = str(tipo_duckdb).split("(")[0].upper()
    if base.startswith("DECIMAL"):
        return SqlType.double()
    if base not in TIPOS:
        raise SystemExit(f"Tipo de DuckDB sin correspondencia en Hyper: {tipo_duckdb}")
    return TIPOS[base]()


def main() -> None:
    if not BASE.exists():
        raise SystemExit(
            f"No se encuentra {BASE.name}. Se construye con "
            f"'duckdb travel_analitica.duckdb < conversion_duckdb.sql'."
        )

    con = duckdb.connect(str(BASE), read_only=True)
    con.execute("SET TimeZone='Europe/Moscow';")
    DESTINO.unlink(missing_ok=True)

    totales = {}
    with HyperProcess(telemetry=Telemetry.DO_NOT_SEND_USAGE_DATA_TO_TABLEAU) as hyper:
        with Connection(hyper.endpoint, str(DESTINO),
                        CreateMode.CREATE_AND_REPLACE) as destino:
            destino.catalog.create_schema("Extract")

            for nombre, sql in CONSULTAS.items():
                relacion = con.sql(sql)
                columnas = [
                    # Todas NULLABLE: DuckDB no expone la nulabilidad en
                    # `types`, y declararlas obligatorias por suposicion haria
                    # fallar la insercion en cuanto una consulta futura
                    # devolviera un nulo legitimo.
                    TableDefinition.Column(c, tipo_hyper(t), NULLABLE)
                    for c, t in zip(relacion.columns, relacion.types)
                ]
                tabla = TableDefinition(TableName("Extract", nombre), columnas)
                destino.catalog.create_table(tabla)

                filas = relacion.fetchall()
                with Inserter(destino, tabla) as inserter:
                    inserter.add_rows(filas)
                    inserter.execute()
                totales[nombre] = len(filas)
                print(f"[OK] {nombre:16s} {len(filas):>6,} filas  "
                      f"{len(columnas):>2} columnas")

    # --- controles --------------------------------------------------------
    # Lo que llega a Tableau tiene que sumar lo mismo que la base. Si no, el
    # tablero mostraria cifras distintas de las del aplicativo, que es peor
    # que no tener tablero. Se leen DEL HYPER, no de las consultas.
    print("\n--- controles, leidos del propio .hyper ---")
    operados = con.execute("SELECT COUNT(*) FROM h_demoras").fetchone()[0]
    minutos = con.execute("SELECT SUM(demora_salida_min) FROM h_demoras").fetchone()[0]
    con.close()

    pruebas = [
        ('SELECT SUM("operados") FROM "Extract"."cobertura"', operados,
         "cobertura: suma de operados"),
        ('SELECT SUM("vuelos") FROM "Extract"."distribucion"', operados,
         "distribucion: suma de vuelos"),
        ('SELECT SUM("vuelos") FROM "Extract"."aeropuertos"', operados,
         "aeropuertos: suma de vuelos"),
        ('SELECT SUM("minutos") FROM "Extract"."aeropuertos"', minutos,
         "aeropuertos: suma de minutos"),
        ('SELECT SUM("vuelos") FROM "Extract"."tiempo"', operados,
         "tiempo: suma de vuelos"),
    ]
    fallos = 0
    with HyperProcess(telemetry=Telemetry.DO_NOT_SEND_USAGE_DATA_TO_TABLEAU) as hyper:
        with Connection(hyper.endpoint, str(DESTINO)) as c:
            for sql, esperado, titulo in pruebas:
                obtenido = c.execute_scalar_query(sql)
                ok = obtenido == esperado
                fallos += 0 if ok else 1
                print(f"  [{'OK  ' if ok else 'FALLA'}] {titulo:34s} "
                      f"{obtenido:>10,}" + ("" if ok else f"  esperado {esperado:,}"))

    if fallos:
        raise SystemExit(f"\n{fallos} control(es) fallaron.")
    print(f"\nLos {len(pruebas)} controles pasaron.")
    print(f"\n{DESTINO.name}  {DESTINO.stat().st_size / 1024:.0f} KB  "
          f"· {len(totales)} tablas · {sum(totales.values()):,} filas")


if __name__ == "__main__":
    main()
