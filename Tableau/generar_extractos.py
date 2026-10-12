"""
Genera los extractos que alimentan el tablero de Tableau Public.

POR QUE CUATRO ARCHIVOS Y NO UNO
--------------------------------
Cada hoja del tablero tiene su propio GRANO. Si se le entregara a Tableau una
sola tabla con el grano mas fino, cada hoja tendria que reagregar, y bastaria
un filtro mal puesto para que una cifra dejara de cuadrar con el aplicativo.
Se entrega a cada hoja exactamente la tabla que necesita, agregada AQUI, en
SQL, donde el resultado se puede verificar contra la base.

POR QUE SE AGREGA EN SQL Y NO EN TABLEAU
----------------------------------------
El indice de concentracion es un cociente de cuotas: minutos del aeropuerto
sobre minutos totales, dividido entre vuelos del aeropuerto sobre vuelos
totales. Calcularlo en Tableau exige expresiones de nivel de detalle que se
rompen en cuanto alguien aplica un filtro. Calculado aqui, es una columna.

Los CSV se escriben en UTF-8 con BOM: sin el, Tableau en Windows interpreta
los acentos como latin-1 y 'San Petersburgo' llega roto.
"""

from pathlib import Path

import duckdb

AQUI = Path(__file__).resolve().parent
BASE = AQUI.parent / "data" / "travel_analitica.sqlite"
DESTINO = AQUI / "extractos"

CONSULTAS = {
    # --- hoja 1: la cobertura del registro, dia a dia --------------------
    "cobertura": """
        SELECT t.fecha,
               t.nombre_dia,
               t.es_fin_de_semana,
               t.hay_operados,
               COUNT(*)                     AS programados,
               SUM(v.es_operado)            AS operados
        FROM h_vuelos v JOIN d_tiempo t ON t.fecha_id = v.fecha_id
        GROUP BY 1, 2, 3, 4 ORDER BY 1
    """,

    # --- hoja 2: la distribucion, con su hueco ---------------------------
    # Un punto por valor observado de demora. Son ~190 filas: el hueco se
    # dibuja solo, porque entre 12 y 123 no hay ninguna.
    "distribucion": """
        SELECT d.demora_salida_min          AS minutos,
               g.etiqueta                   AS regimen,
               g.orden                      AS orden_regimen,
               COUNT(*)                     AS vuelos
        FROM h_demoras d JOIN d_regimen g ON g.regimen_id = d.regimen_id
        GROUP BY 1, 2, 3 ORDER BY 1
    """,

    # --- hoja 3: el mapa y la concentracion ------------------------------
    "aeropuertos": """
        WITH t AS (SELECT (SELECT COUNT(*) FROM h_demoras) tv,
                          (SELECT SUM(demora_salida_min) FROM h_demoras) tm)
        SELECT a.codigo,
               a.nombre,
               a.ciudad,
               a.banda_trafico              AS banda,
               a.orden_banda,
               a.longitud,
               a.latitud,
               COUNT(*)                                        AS vuelos,
               SUM(d.demora_salida_min)                        AS minutos,
               COUNT(*) FILTER (WHERE d.regimen_id = 3)        AS prolongadas,
               ROUND(AVG(d.demora_salida_min), 2)              AS demora_media,
               ROUND(100.0 * COUNT(*) / MAX(t.tv), 4)          AS pct_vuelos,
               ROUND(100.0 * SUM(d.demora_salida_min) / MAX(t.tm), 4) AS pct_retraso,
               ROUND((1.0 * SUM(d.demora_salida_min) / MAX(t.tm))
                     / (1.0 * COUNT(*) / MAX(t.tv)), 4)        AS indice
        FROM h_demoras d
        JOIN h_vuelos     v ON v.vuelo_id      = d.vuelo_id
        JOIN d_aeropuerto a ON a.aeropuerto_id = v.origen_id, t
        GROUP BY 1, 2, 3, 4, 5, 6, 7 ORDER BY minutos DESC
    """,

    # --- hoja 4: el reparto temporal -------------------------------------
    "tiempo": """
        SELECT f.franja_id                  AS hora,
               f.hora                       AS etiqueta_hora,
               f.bloque,
               f.orden                      AS orden_bloque,
               t.nombre_dia,
               t.dia_semana,
               COUNT(*)                                        AS vuelos,
               ROUND(AVG(d.demora_salida_min), 2)              AS demora_media,
               COUNT(*) FILTER (WHERE d.regimen_id = 3)        AS prolongadas
        FROM h_demoras d
        JOIN h_vuelos v ON v.vuelo_id  = d.vuelo_id
        JOIN d_franja f ON f.franja_id = v.franja_id
        JOIN d_tiempo t ON t.fecha_id  = v.fecha_id
        GROUP BY 1, 2, 3, 4, 5, 6 ORDER BY 6, 1
    """,
}


def main() -> None:
    if not BASE.exists():
        raise SystemExit(f"No se encuentra {BASE}.")

    DESTINO.mkdir(exist_ok=True)
    con = duckdb.connect()
    con.execute("INSTALL sqlite; LOAD sqlite;")
    con.execute("SET TimeZone='Europe/Moscow';")
    con.execute(f"ATTACH '{BASE.as_posix()}' AS lite (TYPE sqlite, READ_ONLY);")
    con.execute("USE lite")

    for nombre, sql in CONSULTAS.items():
        datos = con.execute(sql).df()
        ruta = DESTINO / f"{nombre}.csv"
        datos.to_csv(ruta, index=False, encoding="utf-8-sig")
        print(f"[OK] {ruta.name:20s} {len(datos):>6,} filas  "
              f"{len(datos.columns):>2} columnas  "
              f"{ruta.stat().st_size / 1024:>7.1f} KB")

    # --- controles -------------------------------------------------------
    # Los extractos tienen que sumar lo mismo que la base. Si no, el tablero
    # mostraria cifras distintas de las del aplicativo, que es peor que no
    # mostrarlas.
    print("\n--- controles contra la base ---")
    operados = con.execute("SELECT COUNT(*) FROM h_demoras").fetchone()[0]
    minutos = con.execute("SELECT SUM(demora_salida_min) FROM h_demoras").fetchone()[0]

    import pandas as pd
    comprobaciones = [
        ("cobertura: suma de operados",
         int(pd.read_csv(DESTINO / "cobertura.csv")["operados"].sum()), operados),
        ("distribucion: suma de vuelos",
         int(pd.read_csv(DESTINO / "distribucion.csv")["vuelos"].sum()), operados),
        ("aeropuertos: suma de vuelos",
         int(pd.read_csv(DESTINO / "aeropuertos.csv")["vuelos"].sum()), operados),
        ("aeropuertos: suma de minutos",
         int(pd.read_csv(DESTINO / "aeropuertos.csv")["minutos"].sum()), minutos),
        ("tiempo: suma de vuelos",
         int(pd.read_csv(DESTINO / "tiempo.csv")["vuelos"].sum()), operados),
    ]
    fallos = 0
    for titulo, obtenido, esperado in comprobaciones:
        ok = obtenido == esperado
        fallos += 0 if ok else 1
        print(f"  [{'OK  ' if ok else 'FALLA'}] {titulo:34s} "
              f"{obtenido:>10,}" + ("" if ok else f"  esperado {esperado:,}"))
    con.close()
    if fallos:
        raise SystemExit(f"\n{fallos} control(es) fallaron.")
    print(f"\nLos {len(comprobaciones)} controles pasaron.")


if __name__ == "__main__":
    main()
