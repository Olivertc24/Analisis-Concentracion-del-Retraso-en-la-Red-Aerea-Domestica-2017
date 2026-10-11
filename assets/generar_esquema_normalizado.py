"""
Genera el diagrama del esquema normalizado hasta 3FN.

LECTURA DEL COLOR. No es decorativo: distingue las tablas que NACIERON de la
normalizacion -ciudades y rutas, que resuelven las dos dependencias
transitivas, y los dos catalogos de dominio- de las que ya existian en la
fuente y solo se depuraron. De un vistazo se ve que hizo la normalizacion.

DISPOSICION. De izquierda a derecha, siguiendo la dependencia: la red primero
-ciudad, aeropuerto, aeronave-, despues la ruta y el vuelo, y en la columna
derecha la cadena de la venta -reserva, pasaje, cupon, tarjeta-. Las lineas no
se cruzan en ningun punto.

ANTIALIASING. Pillow no suaviza las primitivas: se traza a triple resolucion y
se reduce al final.
"""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ANCHO, ALTO = 1800, 1160
SUPER = 3

NACE = (43, 212, 232)            # cian: tabla creada por la normalizacion
HEREDA = (124, 160, 180)         # gris azulado: tabla que ya existia
FONDO = (8, 14, 20)
CAJA_NACE = (16, 32, 40)
CAJA_HEREDA = (16, 26, 34)
BLANCO = (240, 248, 250)
GRIS = (160, 180, 190)
GRIS_TENUE = (104, 124, 136)
LINEA = (56, 86, 100)

HELVETICA = "/System/Library/Fonts/HelveticaNeue.ttc"
NEGRITA, REGULAR, MEDIA = 1, 0, 10

ALTO_CABECERA, ALTO_CAMPO, MARGEN_INFERIOR = 98, 23, 18


def alto_de(campos):
    return ALTO_CABECERA + MARGEN_INFERIOR + len(campos) * ALTO_CAMPO


# (titulo, subtitulo, campos, (x0, y0, x1), nace_de_la_normalizacion)
TABLAS = {
    "ciudades": ("ciudades", "101 filas  ·  3FN: ciudad -> zona", [
        "ciudad_id       PK", "nombre", "nombre_ru", "zona_horaria"],
        (70, 60, 390), True),
    "aeropuertos": ("aeropuertos", "104 filas  ·  1FN: JSON y point", [
        "codigo          PK  (IATA)", "nombre · nombre_ru", "ciudad_id        FK",
        "longitud · latitud"], (70, 320, 390), False),
    "aeronaves": ("aeronaves", "9 filas  ·  1FN: JSON", [
        "codigo          PK", "modelo · modelo_ru", "autonomia_km"],
        (70, 610, 390), False),
    "rutas": ("rutas", "710 filas  ·  3FN: n.o vuelo -> ruta", [
        "numero_vuelo    PK", "origen           FK", "destino          FK",
        "aeronave_codigo  FK", "duracion_min"], (480, 320, 800), True),
    "asientos": ("asientos", "1.339 filas", [
        "aeronave_codigo  PK · FK", "numero          PK", "clase_id         FK"],
        (480, 620, 800), False),
    "clases_tarifarias": ("clases_tarifarias", "3 filas  ·  catalogo de dominio", [
        "clase_id        PK", "codigo · nombre", "orden"],
        (480, 880, 800), True),
    "estados_vuelo": ("estados_vuelo", "6 filas  ·  catalogo de dominio", [
        "estado_id       PK", "codigo", "descripcion"],
        (890, 60, 1210), True),
    "vuelos": ("vuelos", "33.121 filas", [
        "vuelo_id        PK", "numero_vuelo     FK", "estado_id        FK",
        "salida_programada", "salida_real", "llegada_real"],
        (890, 320, 1210), False),
    "reservas": ("reservas", "262.788 filas", [
        "localizador     PK", "fecha_reserva"], (1300, 60, 1620), False),
    "pasajes": ("pasajes", "366.733 filas", [
        "numero_pasaje   PK", "localizador      FK", "pasajero_id     UNIQUE"],
        (1300, 290, 1620), False),
    "cupones": ("cupones", "1.045.726 filas", [
        "numero_pasaje   PK · FK", "vuelo_id        PK · FK", "clase_id         FK",
        "monto"], (1300, 545, 1620), False),
    "tarjetas_embarque": ("tarjetas_embarque", "579.686 filas", [
        "numero_pasaje   PK · FK", "vuelo_id        PK · FK", "numero_embarque",
        "asiento"], (1300, 825, 1620), False),
}

# (origen, lado, destino, lado, desplazamiento del punto de llegada)
ENLACES = [
    ("ciudades", "S", "aeropuertos", "N", 0),
    ("aeropuertos", "E", "rutas", "O", -40),   # origen
    ("aeropuertos", "E", "rutas", "O", 40),    # destino
    ("aeronaves", "N", "rutas", "S", 0),
    ("aeronaves", "E", "asientos", "O", 0),
    ("clases_tarifarias", "N", "asientos", "S", 0),
    ("clases_tarifarias", "E", "cupones", "O", 60),
    ("rutas", "E", "vuelos", "O", 0),
    ("estados_vuelo", "S", "vuelos", "N", 0),
    ("vuelos", "E", "cupones", "O", -40),
    ("reservas", "S", "pasajes", "N", 0),
    ("pasajes", "S", "cupones", "N", 0),
    ("cupones", "S", "tarjetas_embarque", "N", 0),
]


def caja(clave):
    _, _, campos, (x0, y0, x1), _ = TABLAS[clave]
    return (x0, y0, x1, y0 + alto_de(campos))


def ancla(c, lado, desp=0):
    x0, y0, x1, y1 = c
    cx, cy = (x0 + x1) // 2, (y0 + y1) // 2
    return {"N": (cx, y0), "S": (cx, y1),
            "O": (x0, cy + desp), "E": (x1, cy + desp)}[lado]


def construir():
    s = SUPER
    lienzo = Image.new("RGB", (ANCHO * s, ALTO * s), FONDO)
    pintor = ImageDraw.Draw(lienzo)

    for origen, lo, destino, ld, desp in ENLACES:
        p1 = ancla(caja(origen), lo, desp if lo in "OE" else 0)
        p2 = ancla(caja(destino), ld, desp if ld in "OE" else 0)
        pintor.line([(p1[0] * s, p1[1] * s), (p2[0] * s, p2[1] * s)],
                    fill=LINEA, width=2 * s)
        r = 7 * s
        pintor.ellipse([p2[0] * s - r, p2[1] * s - r, p2[0] * s + r, p2[1] * s + r],
                       fill=HEREDA)

    for clave in TABLAS:
        *_, nace = TABLAS[clave]
        x0, y0, x1, y1 = [v * s for v in caja(clave)]
        borde = NACE if nace else HEREDA
        pintor.rounded_rectangle([x0, y0, x1, y1], radius=10 * s,
                                 fill=CAJA_NACE if nace else CAJA_HEREDA,
                                 outline=borde, width=2 * s)
        pintor.rounded_rectangle([x0, y0, x1, y0 + 62 * s], radius=10 * s, fill=borde)
        pintor.rectangle([x0, y0 + 40 * s, x1, y0 + 62 * s], fill=borde)

    lienzo = lienzo.resize((ANCHO, ALTO), Image.LANCZOS)
    pintor = ImageDraw.Draw(lienzo)

    f_titulo = ImageFont.truetype(HELVETICA, 22, index=NEGRITA)
    f_sub = ImageFont.truetype(HELVETICA, 14, index=REGULAR)
    f_campo = ImageFont.truetype(HELVETICA, 15, index=REGULAR)
    f_campo_k = ImageFont.truetype(HELVETICA, 15, index=MEDIA)
    f_leyenda = ImageFont.truetype(HELVETICA, 16, index=REGULAR)
    f_cab = ImageFont.truetype(HELVETICA, 17, index=NEGRITA)

    for clave in TABLAS:
        titulo, subtitulo, campos, _, nace = TABLAS[clave]
        x0, y0, x1, y1 = caja(clave)
        pintor.text((x0 + 16, y0 + 11), titulo, font=f_titulo, fill=(10, 24, 30))
        pintor.text((x0 + 16, y0 + 72), subtitulo, font=f_sub, fill=GRIS_TENUE)
        y = y0 + 98
        for campo in campos:
            es_clave = "PK" in campo or "FK" in campo or "UNIQUE" in campo
            pintor.text((x0 + 16, y), campo,
                        font=f_campo_k if es_clave else f_campo,
                        fill=BLANCO if es_clave else GRIS)
            y += ALTO_CAMPO

    # El bloque se mantiene a la izquierda de x=460: mas ancho se monta sobre
    # la caja de clases_tarifarias, que empieza en 480.
    pintor.text((70, 842), "DOCE TABLAS EN 3FN", font=f_cab, fill=NACE)
    for i, linea in enumerate([
            "Las cuatro en cian NACIERON de la",
            "normalizacion: ciudades y rutas resuelven",
            "las dos dependencias transitivas, y los dos",
            "catalogos imponen la integridad de dominio",
            "que la fuente no tenia.",
            "",
            "Las ocho restantes ya existian en la fuente;",
            "aqui se depuraron y recibieron las claves",
            "que el origen no declaraba.",
            "",
            "Dos vistas reponen lo suprimido por",
            "derivable: v_vuelo y v_reserva."]):
        pintor.text((70, 868 + i * 20), linea, font=f_sub, fill=GRIS_TENUE)

    ly = ALTO - 44
    pintor.rounded_rectangle([890, ly, 920, ly + 18], radius=4, fill=NACE)
    pintor.text((930, ly), "Nace de la normalizacion", font=f_leyenda, fill=GRIS)
    pintor.rounded_rectangle([1200, ly, 1230, ly + 18], radius=4, fill=HEREDA)
    pintor.text((1240, ly), "Ya existia en la fuente", font=f_leyenda, fill=GRIS)

    destino = Path(__file__).with_name("esquema_normalizado.png")
    lienzo.save(destino, optimize=True)
    print(f"{destino.name}  {ANCHO}x{ALTO}  {destino.stat().st_size/1024:.0f} KB")


if __name__ == "__main__":
    construir()
