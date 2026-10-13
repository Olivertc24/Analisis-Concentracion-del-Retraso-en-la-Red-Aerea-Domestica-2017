#!/usr/bin/env python3
"""
GENERACION DEL LIBRO DE TABLEAU (.twb) POR CODIGO
Escuela de Estadistica y Ciencias Actuariales (EECA-UCV) - Computacion II
================================================================================

Un .twb es XML: describe fuentes, campos calculados, hojas y tableros. Este
script lo construye entero a partir del extracto `.hyper`, de modo que el
tablero es reproducible: si cambian los datos, se vuelven a correr los scripts
en orden y el libro sale igual.

El esquema se lee DEL PROPIO .hyper, no de las consultas que lo generaron: asi
el libro y el extracto no pueden divergir.

REGLAS DEL FORMATO QUE NO SON OBVIAS
------------------------------------
El validador de Tableau es estricto y su mensaje de error queda enmascarado en
la bitacora; solo el dialogo de la aplicacion lo muestra entero. Las reglas que
hubo que respetar, aprendidas a base de que el libro fuera rechazado:

  * `<workbook>` necesita el atributo `source-build`, y
    `<document-format-change-manifest>` es obligatorio.
  * Cada `<worksheet>`, `<dashboard>` y `<window>` necesita su `<simple-id>`, y
    va SIEMPRE al final del elemento.
  * `<aggregation value='true' />` cierra cada `<view>`.
  * Los elementos vacios se rechazan: nada de `<slices></slices>`.
  * El orden dentro de `<view>` es estricto: filter, computed-sort, slices,
    aggregation. Y el elemento de orden se llama `<computed-sort>`.
  * En una zona contenedora de tablero, `<zone-style>` va DESPUES de las zonas
    hijas.
  * La paleta de una dimension discreta se declara en el `<style>` de la FUENTE
    DE DATOS, no en el de la hoja; la referencia al campo va SIN el prefijo de
    la fuente; el campo debe ser una dimension CALCULADA, no una columna del
    archivo; y el hexadecimal debe ir en MINUSCULAS. Si falla cualquiera de las
    cuatro condiciones, Tableau ignora la paleta EN SILENCIO.
  * Un mapa necesita `<lod>` con un identificador de fila, o Tableau colapsa
    todas las marcas en un unico punto promedio.
  * Dos medidas en el mismo estante se separan con ' + ', no con un espacio.
  * Dentro de `<datasource>` y de `<datasource-dependencies>`, TODOS los
    `<column>` van antes que TODOS los `<column-instance>`. Declararlos por
    pares produce:
        element 'column' is not allowed for content model '(...,column,column-instance,...)'
    El fallo solo se manifiesta a partir del SEGUNDO campo calculado, porque
    con uno solo el orden intercalado coincide por casualidad con el correcto.
"""

import uuid
from pathlib import Path
from xml.sax.saxutils import escape, quoteattr

from tableauhyperapi import (Connection, HyperProcess, TableName, Telemetry,
                             TypeTag)

AQUI = Path(__file__).resolve().parent
HYPER = "retraso_red_aerea_2017.hyper"
SALIDA = AQUI / "Retraso_Red_Aerea_2017.twb"
SOURCE_BUILD = "0.0.0 (0000.25.1024.2150)"

# ───────────────────────────────────────────────────────── paleta "Pista" ──
# Los mismos colores del aplicativo: el color codifica el REGIMEN, que es la
# variable que organiza la investigacion, y no es decorativo.
CIAN      = "#2bd4e8"   # demora breve: el modo bajo, la inmensa mayoria
VERDE     = "#3ddc97"   # puntual al minuto
ROJO      = "#f2545b"   # demora prolongada: el modo alto, separado del resto
AZUL_GRIS = "#7fa8bc"
PIZARRA   = "#44606e"

PAPEL      = "#F6F9FA"
SUPERFICIE = "#FFFFFF"
TINTA      = "#12222B"
TINTA_2    = "#35505C"
TINTA_3    = "#6E8894"

# Las claves llevan el prefijo de orden porque la dimension calculada que
# consume la paleta lo antepone. Si no coinciden EXACTAMENTE, Tableau ignora la
# correspondencia sin avisar.
COLOR_REGIMEN = {
    "1. Puntual":           VERDE,
    "2. Demora breve":      CIAN,
    "3. Demora prolongada": ROJO,
}
COLOR_BANDA = {
    "1. Principal":  CIAN,
    "2. Intermedio": AZUL_GRIS,
    "3. Secundario": PIZARRA,
}

TABLAS = {
    "cobertura":    ("federated.cobertura",    "hyper.cobertura",    "Cobertura"),
    "distribucion": ("federated.distribucion", "hyper.distribucion", "Distribucion"),
    "aeropuertos":  ("federated.aeropuertos",  "hyper.aeropuertos",  "Aeropuertos"),
    "tiempo":       ("federated.tiempo",       "hyper.tiempo",       "Tiempo"),
}

# Campos numericos que son codigos, no cantidades: deben ser dimension.
DIMENSIONES_NUMERICAS = {"orden_regimen", "orden_banda", "orden_bloque",
                         "dia_semana", "hora", "minutos"}

TIPO_TABLEAU = {
    TypeTag.INT: "integer", TypeTag.SMALL_INT: "integer",
    TypeTag.BIG_INT: "integer", TypeTag.DOUBLE: "real",
    TypeTag.TEXT: "string", TypeTag.DATE: "date", TypeTag.BOOL: "boolean",
}
TIPO_REMOTO = {"integer": "20", "real": "5", "string": "130",
               "date": "7", "boolean": "11"}
SUFIJO = {"nominal": "nk", "ordinal": "ok", "quantitative": "qk"}

MANIFEST = """  <document-format-change-manifest>
    <_.fcp.AccessibleZoneTabOrder.true...AccessibleZoneTabOrder />
    <_.fcp.AnimationOnByDefault.true...AnimationOnByDefault />
    <AutoCreateAndUpdateDSDPhoneLayouts />
    <_.fcp.MarkAnimation.true...MarkAnimation />
    <_.fcp.ObjectModelEncapsulateLegacy.true...ObjectModelEncapsulateLegacy />
    <_.fcp.ObjectModelTableType.true...ObjectModelTableType />
    <_.fcp.SchemaViewerObjectModel.true...SchemaViewerObjectModel />
    <SetMembershipControl />
    <SheetIdentifierTracking />
    <SortTagCleanup />
    <WindowsPersistSimpleIdentifiers />
  </document-format-change-manifest>"""

CARDS = """      <cards>
        <edge name='left'>
          <strip size='160'>
            <card type='pages' />
            <card type='filters' />
            <card type='marks' />
          </strip>
        </edge>
        <edge name='top'>
          <strip size='2147483647'>
            <card type='columns' />
          </strip>
          <strip size='2147483647'>
            <card type='rows' />
          </strip>
        </edge>
      </cards>"""


def a(v):
    return quoteattr(str(v))


def sid(nombre):
    """<simple-id>, obligatorio. Derivado con UUID v5 para que regenerar el
    libro no cambie los identificadores y el control de versiones muestre solo
    cambios reales."""
    u = uuid.uuid5(uuid.NAMESPACE_URL, "eeca/retraso/" + nombre)
    return f"      <simple-id uuid='{{{str(u).upper()}}}' />"


def esquema_del_hyper():
    """Lee el esquema REAL del extracto, que es lo que Tableau va a abrir."""
    salida = {}
    with HyperProcess(telemetry=Telemetry.DO_NOT_SEND_USAGE_DATA_TO_TABLEAU) as hp:
        with Connection(hp.endpoint, str(AQUI / HYPER)) as con:
            for tabla in TABLAS:
                definicion = con.catalog.get_table_definition(
                    TableName("Extract", tabla))
                cols = []
                for orden, c in enumerate(definicion.columns):
                    nombre = c.name.unescaped
                    tipo = TIPO_TABLEAU[c.type.tag]
                    medida = (tipo in ("integer", "real")
                              and nombre not in DIMENSIONES_NUMERICAS)
                    cols.append({
                        "n": nombre, "t": tipo, "orden": orden,
                        "rol": "measure" if medida else "dimension",
                        "clase": ("quantitative" if medida
                                  else "ordinal" if tipo in ("integer", "real", "date")
                                  else "nominal"),
                    })
                salida[tabla] = cols
    return salida


def instancia(col, derivacion, clase):
    prefijo = "none" if derivacion == "None" else derivacion.lower()
    return f"[{prefijo}:{col}:{SUFIJO[clase]}]"


def ref(inst, ds):
    return f"[{ds}].{inst}"


# ────────────────────────────────────────────────── campos calculados ──
# Todos son COCIENTES DE SUMAS. Ninguno usa AVG() sobre una media ya calculada:
# promediar promedios da una media no ponderada, que es distinta y esta mal.
CALCULADOS = {
    "aeropuertos": [
        ("DemoraMedia", "Demora media de salida (min)",
         "SUM([minutos]) / SUM([vuelos])", "n#,##0.00"),
        # El indice de concentracion: cuota de retraso sobre cuota de vuelos.
        # TOTAL() lo hace robusto a los filtros del tablero.
        ("Indice", "Indice de concentracion",
         "(SUM([minutos]) / TOTAL(SUM([minutos]))) "
         "/ (SUM([vuelos]) / TOTAL(SUM([vuelos])))", "n#,##0.000"),
    ],
    "tiempo": [
        ("DemoraMedia", "Demora media de salida (min)",
         "SUM([minutos]) / SUM([vuelos])", "n#,##0.00"),
    ],
}

# Dimensiones calculadas. Existen por dos motivos concretos: la paleta discreta
# solo se aplica sobre una dimension CALCULADA, y anteponer el numero de orden
# fuerza la secuencia logica, porque Tableau ordena alfabeticamente y
# "Demora prolongada" aparecia antes que "Puntual".
DIMS_CALC = {
    "distribucion": [("RegimenDemora", "Regimen de demora",
                      "STR([orden_regimen]) + '. ' + [regimen]")],
    "aeropuertos":  [("BandaTrafico", "Banda de trafico",
                      "STR([orden_banda]) + '. ' + [banda]")],
    "tiempo":       [("DiaOrdenado", "Dia de la semana",
                      "STR([dia_semana]) + '. ' + [nombre_dia]")],
}
PALETAS = {"distribucion": ("RegimenDemora", COLOR_REGIMEN),
           "aeropuertos": ("BandaTrafico", COLOR_BANDA)}
SEMANTICA = {"aeropuertos": {"longitud": "[Longitude]", "latitud": "[Latitude]"}}


def bloque_datasource(tabla, cols):
    ds, cx, caption = TABLAS[tabla]
    calculados = CALCULADOS.get(tabla, [])
    dims_calc = DIMS_CALC.get(tabla, [])
    semantica = SEMANTICA.get(tabla, {})
    paleta = PALETAS.get(tabla)

    o = [f"  <datasource caption={a(caption)} inline='true' name='{ds}' version='18.1'>",
         "    <connection class='federated'>",
         "      <named-connections>",
         f"        <named-connection caption={a(caption)} name='{cx}'>",
         f"          <connection class='hyper' dbname='Data/{HYPER}' schema='Extract' "
         "server='' username='tableau_internal_user' />",
         "        </named-connection>",
         "      </named-connections>",
         f"      <relation connection='{cx}' name={a(tabla)} "
         f"table='[Extract].[{tabla}]' type='table'>",
         "        <columns header='yes' outcome='6'>"]
    for c in cols:
        o.append(f"          <column datatype='{c['t']}' name={a(c['n'])} "
                 f"ordinal='{c['orden']}' />")
    o += ["        </columns>", "      </relation>", "      <metadata-records>"]
    for c in cols:
        o += ["        <metadata-record class='column'>",
              f"          <remote-name>{escape(c['n'])}</remote-name>",
              f"          <remote-type>{TIPO_REMOTO[c['t']]}</remote-type>",
              f"          <local-name>[{escape(c['n'])}]</local-name>",
              f"          <parent-name>[{tabla}]</parent-name>",
              f"          <remote-alias>{escape(c['n'])}</remote-alias>",
              f"          <ordinal>{c['orden']}</ordinal>",
              f"          <local-type>{c['t']}</local-type>",
              f"          <aggregation>{'Sum' if c['rol'] == 'measure' else 'Count'}</aggregation>",
              "          <contains-null>true</contains-null>",
              "        </metadata-record>"]
    o += ["      </metadata-records>", "    </connection>", "    <aliases enabled='yes' />"]

    for c in cols:
        # El rol geografico es lo que hace que Tableau dibuje un mapa real y no
        # un diagrama de dispersion.
        geo = f" semantic-role={a(semantica[c['n']])}" if c["n"] in semantica else ""
        o.append(f"    <column datatype='{c['t']}' name={a('[' + c['n'] + ']')} "
                 f"role='{c['rol']}'{geo} type='{c['clase']}' />")
    for clave, cap, formula, fmt in calculados:
        o += [f"    <column caption={a(cap)} datatype='real' default-format={a(fmt)} "
              f"name='[{clave}]' role='measure' type='quantitative'>",
              f"      <calculation class='tableau' formula={a(formula)} "
              "scope-isolation='false' />", "    </column>"]
    for clave, cap, formula in dims_calc:
        o += [f"    <column caption={a(cap)} datatype='string' name='[{clave}]' "
              "role='dimension' type='nominal'>",
              f"      <calculation class='tableau' formula={a(formula)} "
              "scope-isolation='false' />", "    </column>"]
    # TODOS los <column> arriba; TODAS las instancias, aqui.
    for clave, _, _ in dims_calc:
        o.append(f"    <column-instance column='[{clave}]' derivation='None' "
                 f"name={a('[none:' + clave + ':nk]')} pivot='key' type='nominal' />")
    o.append("    <layout dim-ordering='alphabetic' measure-ordering='alphabetic' "
             "show-structure='true' />")
    if paleta:
        campo, mapa = paleta
        o += ["    <style>", "      <style-rule element='mark'>",
              f"        <encoding attr='color' field={a(f'[none:{campo}:nk]')} "
              "type='palette'>"]
        for valor, color in mapa.items():
            o += [f"          <map to='{color.lower()}'>",
                  f"            <bucket>&quot;{escape(valor)}&quot;</bucket>",
                  "          </map>"]
        o += ["        </encoding>", "      </style-rule>", "    </style>"]
    o.append("  </datasource>")
    return o


# ─────────────────────────────────────────────────────────────── hojas ──

def hoja(nombre, titulo, tabla, esquema, dims, medidas, calcs, filas, columnas,
         marca, color=None, tamano=None, detalle=None, medidas_avg=(),
         dims_calc_usadas=(), estilo_extra=()):
    """Construye una hoja completa."""
    ds, _, caption = TABLAS[tabla]
    esq = {c["n"]: c for c in esquema[tabla]}

    o = [f"    <worksheet name={a(nombre)}>",
         "      <layout-options>", "        <title>", "          <formatted-text>",
         f"            <run fontcolor='{TINTA_2}' fontsize='11'>{escape(titulo)}</run>",
         "          </formatted-text>", "        </title>", "      </layout-options>",
         "      <table>", "        <view>", "          <datasources>",
         f"            <datasource caption={a(caption)} name='{ds}' />",
         "          </datasources>",
         f"          <datasource-dependencies datasource='{ds}'>"]

    # --- primero TODOS los <column> -------------------------------------
    for d in dims:
        c = esq[d]
        o.append(f"            <column datatype='{c['t']}' name={a('[' + d + ']')} "
                 f"role='dimension' type='{c['clase']}' />")
    for m in list(medidas) + list(medidas_avg):
        c = esq[m]
        geo = SEMANTICA.get(tabla, {}).get(m)
        extra = f" semantic-role={a(geo)}" if geo else ""
        o.append(f"            <column datatype='{c['t']}' name={a('[' + m + ']')} "
                 f"role='measure'{extra} type='quantitative' />")
    for clave in dims_calc_usadas:
        cap, formula = next((c, f) for k, c, f in DIMS_CALC[tabla] if k == clave)
        o += [f"            <column caption={a(cap)} datatype='string' "
              f"name='[{clave}]' role='dimension' type='nominal'>",
              f"              <calculation class='tableau' formula={a(formula)} "
              "scope-isolation='false' />", "            </column>"]
    for clave in calcs:
        cap, formula, fmt = next((c, f, x) for k, c, f, x in CALCULADOS[tabla]
                                 if k == clave)
        o += [f"            <column caption={a(cap)} datatype='real' "
              f"default-format={a(fmt)} name='[{clave}]' role='measure' "
              "type='quantitative'>",
              f"              <calculation class='tableau' formula={a(formula)} "
              "scope-isolation='false' />", "            </column>"]

    # --- y despues TODAS las <column-instance> ---------------------------
    for d in dims:
        c = esq[d]
        o.append(f"            <column-instance column={a('[' + d + ']')} "
                 f"derivation='None' name={a(instancia(d, 'None', c['clase']))} "
                 f"pivot='key' type='{c['clase']}' />")
    for m in medidas:
        o.append(f"            <column-instance column={a('[' + m + ']')} "
                 f"derivation='Sum' name={a(instancia(m, 'Sum', 'quantitative'))} "
                 "pivot='key' type='quantitative' />")
    for m in medidas_avg:
        o.append(f"            <column-instance column={a('[' + m + ']')} "
                 f"derivation='Avg' name={a(instancia(m, 'Avg', 'quantitative'))} "
                 "pivot='key' type='quantitative' />")
    for clave in dims_calc_usadas:
        o.append(f"            <column-instance column='[{clave}]' derivation='None' "
                 f"name={a('[none:' + clave + ':nk]')} pivot='key' type='nominal' />")
    for clave in calcs:
        o.append(f"            <column-instance column='[{clave}]' derivation='User' "
                 f"name={a('[usr:' + clave + ':qk]')} pivot='key' "
                 "type='quantitative' />")
    o += ["          </datasource-dependencies>",
          "          <aggregation value='true' />", "        </view>",
          "        <style>",
          "          <style-rule element='worksheet'>",
          "            <format attr='display-field-labels' scope='rows' value='false' />",
          "            <format attr='display-field-labels' scope='cols' value='false' />",
          "          </style-rule>",
          "          <style-rule element='pane'>",
          f"            <format attr='background-color' value='{SUPERFICIE}' />",
          "          </style-rule>",
          "          <style-rule element='axis'>",
          f"            <format attr='color' value='{TINTA_3}' />",
          "          </style-rule>",
          "          <style-rule element='header'>",
          f"            <format attr='color' value='{TINTA_2}' />",
          "          </style-rule>"]
    o += ["          " + l for l in estilo_extra]
    o += ["        </style>", "        <panes>",
          "          <pane selection-relaxation-option='selection-relaxation-allow'>",
          "            <view>", "              <breakdown value='auto' />",
          "            </view>", f"            <mark class='{marca}' />"]
    cod = []
    if color:
        cod.append(f"<color column={a(ref(color, ds))} />")
    if tamano:
        cod.append(f"<size column={a(ref(tamano, ds))} />")
    if detalle:
        # <lod> fija una marca por valor del campo. Es lo que convierte el mapa
        # en 104 aeropuertos y no en un unico punto promedio.
        cod.append(f"<lod column={a(ref(detalle, ds))} />")
    if cod:
        o.append("            <encodings>")
        o += ["              " + c for c in cod]
        o.append("            </encodings>")
    o += ["          </pane>", "        </panes>",
          f"        <rows>{escape(filas)}</rows>",
          f"        <cols>{escape(columnas)}</cols>",
          "      </table>", sid(nombre), "    </worksheet>"]
    return o


def construir_hojas(esquema):
    """Las cuatro hojas, una por hallazgo de la investigacion."""
    d_cob = TABLAS["cobertura"][0]
    d_dis = TABLAS["distribucion"][0]
    d_aer = TABLAS["aeropuertos"][0]
    d_tie = TABLAS["tiempo"][0]
    h = []

    # --- 1. la frontera del registro -------------------------------------
    # Dos medidas en el mismo estante se separan con ' + ', no con un espacio.
    h += hoja("Cobertura del registro",
              "Vuelos programados y vuelos con hora real, por fecha",
              "cobertura", esquema,
              dims=["fecha"], medidas=["programados", "operados"], calcs=[],
              filas=f"{ref(instancia('programados', 'Sum', 'quantitative'), d_cob)} + "
                    f"{ref(instancia('operados', 'Sum', 'quantitative'), d_cob)}",
              columnas=ref(instancia("fecha", "None", "ordinal"), d_cob),
              marca="Bar")

    # --- 2. la forma de la distribucion ----------------------------------
    h += hoja("La forma de la distribucion",
              "Vuelos por minuto de demora de salida. Entre 12 y 123 no hay ninguno",
              "distribucion", esquema,
              dims=["minutos"], medidas=["vuelos"], calcs=[],
              dims_calc_usadas=["RegimenDemora"],
              filas=ref(instancia("vuelos", "Sum", "quantitative"), d_dis),
              columnas=ref(instancia("minutos", "None", "ordinal"), d_dis),
              marca="Bar", color=ref("[none:RegimenDemora:nk]", d_dis))

    # --- 3. el mapa de la red --------------------------------------------
    h += hoja("El mapa de la red",
              "Tamano por volumen, color por indice de concentracion",
              "aeropuertos", esquema,
              dims=["codigo"], medidas=["vuelos"], calcs=["Indice"],
              medidas_avg=["longitud", "latitud"],
              filas=ref(instancia("latitud", "Avg", "quantitative"), d_aer),
              columnas=ref(instancia("longitud", "Avg", "quantitative"), d_aer),
              marca="Circle",
              color=ref("[usr:Indice:qk]", d_aer),
              tamano=ref(instancia("vuelos", "Sum", "quantitative"), d_aer),
              detalle=ref(instancia("codigo", "None", "nominal"), d_aer))

    # --- 4. el reparto temporal ------------------------------------------
    h += hoja("El reparto temporal",
              "Demora media por hora y dia de la semana",
              "tiempo", esquema,
              dims=["etiqueta_hora"], medidas=["vuelos", "minutos"],
              calcs=["DemoraMedia"], dims_calc_usadas=["DiaOrdenado"],
              filas=ref(instancia("etiqueta_hora", "None", "nominal"), d_tie),
              columnas=ref("[none:DiaOrdenado:nk]", d_tie),
              marca="Square", color=ref("[usr:DemoraMedia:qk]", d_tie))
    return h


# ───────────────────────────────────────────────────────────── tablero ──

def zona_hoja(zid, nombre, x, y, w, h):
    return [f"        <zone h='{h}' id='{zid}' name={a(nombre)} w='{w}' x='{x}' y='{y}'>",
            "          <zone-style>",
            f"            <format attr='border-color' value='{PAPEL}' />",
            "            <format attr='border-style' value='none' />",
            "            <format attr='border-width' value='0' />",
            "            <format attr='margin' value='4' />",
            "          </zone-style>", "        </zone>"]


def zona_texto(zid, texto, tam, color, negrita, x, y, w, h):
    return [f"        <zone h='{h}' id='{zid}' type-v2='text' w='{w}' x='{x}' y='{y}'>",
            "          <formatted-text>",
            f"            <run bold='{str(negrita).lower()}' fontcolor='{color}' "
            f"fontsize='{tam}'>{escape(texto)}</run>",
            "          </formatted-text>", "          <zone-style>",
            f"            <format attr='border-color' value='{PAPEL}' />",
            "            <format attr='border-style' value='none' />",
            "            <format attr='border-width' value='0' />",
            "            <format attr='margin' value='4' />",
            "          </zone-style>", "        </zone>"]


def tablero(nombre, titulo, subtitulo, hojas):
    o = [f"    <dashboard name={a(nombre)}>",
         "      <style />" if False else "",
         "      <size maxheight='1500' maxwidth='1200' minheight='1500' "
         "minwidth='1200' />",
         "      <zones>",
         "      <zone h='100000' id='1' type-v2='layout-basic' w='100000' x='0' y='0'>"]
    o += zona_texto(90, titulo, 20, TINTA, True, 0, 0, 100000, 4000)
    o += zona_texto(91, subtitulo, 11, TINTA_3, False, 0, 4000, 100000, 3200)
    rejilla = [(0, 7200, 100000, 23000), (0, 30200, 100000, 23000),
               (0, 53200, 50000, 23000), (50000, 53200, 50000, 23000)]
    for i, (hoja_nombre, (x, y, w, hh)) in enumerate(zip(hojas, rejilla)):
        o += zona_hoja(10 + i, hoja_nombre, x, y, w, hh)
    o += zona_texto(
        95,
        "Escuela de Estadistica y Ciencias Actuariales - Universidad Central de "
        "Venezuela - Computacion II", 9, TINTA_3, False, 0, 76200, 100000, 2300)
    # En una zona contenedora, <zone-style> va DESPUES de las zonas hijas.
    o += ["        <zone-style>",
          f"          <format attr='background-color' value='{PAPEL}' />",
          "          <format attr='background-image' value='' />",
          "          <format attr='border-color' value='#000000' />",
          "          <format attr='border-style' value='none' />",
          "          <format attr='border-width' value='0' />",
          "          <format attr='margin' value='8' />",
          "        </zone-style>", "      </zone>", "      </zones>",
          sid(nombre), "    </dashboard>"]
    return [l for l in o if l != ""]


def ventanas(hojas, tablero_nombre):
    o = ["  <windows source-height='30'>"]
    for n in hojas:
        o += [f"    <window class='worksheet' hidden='true' name={a(n)}>",
              "      <viewpoint />", CARDS, sid("w:" + n), "    </window>"]
    o += [f"    <window class='dashboard' maximized='true' name={a(tablero_nombre)}>",
          "      <viewpoints>"]
    for n in hojas:
        o.append(f"        <viewpoint name={a(n)}><zoom type='entire-view' /></viewpoint>")
    o += ["      </viewpoints>", "      <active id='-1' />", sid("w:" + tablero_nombre),
          "    </window>", "  </windows>"]
    return o


def main():
    if not (AQUI / HYPER).exists():
        raise SystemExit(f"Falta {HYPER}. Ejecute antes construir_hyper.py.")

    esquema = esquema_del_hyper()
    o = ["<?xml version='1.0' encoding='utf-8' ?>",
         f"<workbook source-build={a(SOURCE_BUILD)} source-platform='mac' "
         "version='18.1' xmlns:user='http://www.tableausoftware.com/xml/user'>",
         MANIFEST,
         "  <preferences>",
         "    <preference name='ui.encoding.shelf.height' value='24' />",
         "    <preference name='ui.shelf.height' value='26' />",
         "  </preferences>", "  <datasources>"]
    for tabla, cols in esquema.items():
        o += bloque_datasource(tabla, cols)
    o += ["  </datasources>", "  <worksheets>"]
    o += construir_hojas(esquema)
    o += ["  </worksheets>", "  <dashboards>"]
    nombres = ["Cobertura del registro", "La forma de la distribucion",
               "El mapa de la red", "El reparto temporal"]
    o += tablero(
        "Concentracion del retraso",
        "Concentracion del retraso en la red aerea domestica, 2017",
        "El retraso se reparte en proporcion al volumen: el indice de los catorce "
        "aeropuertos principales es 1,02. La estructura no esta en la red, esta "
        "en la forma de la distribucion.",
        nombres)
    o += ["  </dashboards>"]
    o += ventanas(nombres, "Concentracion del retraso")
    o.append("</workbook>")

    SALIDA.write_text("\n".join(o) + "\n", encoding="utf-8")
    print(f"{SALIDA.name}  {SALIDA.stat().st_size / 1024:.0f} KB  "
          f"· {len(esquema)} fuentes · {len(nombres)} hojas · 1 tablero")


if __name__ == "__main__":
    main()
