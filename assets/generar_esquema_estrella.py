"""
Genera el diagrama del esquema en estrella de la base analitica.

DISPOSICION. Una sola estrella: el grano es el vuelo y la tabla de hechos
central es h_vuelos, con las siete dimensiones alrededor. Colgando de ella,
h_demoras, que no es otra estrella sino una EXTENSION en relacion 1:0..1: solo
recibe fila el vuelo que llego a despegar. Por eso se dibuja debajo y unida por
una linea mas gruesa, y por eso d_regimen cuelga de ella y no del centro.

ANTIALIASING. Pillow no suaviza las primitivas: se traza a triple resolucion y
se reduce al final. El texto se escribe despues, ya en tamano final.
"""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ANCHO, ALTO = 1800, 1180
SUPER = 3

ACENTO = (43, 212, 232)          # cian: los hechos
ACENTO_DIM = (124, 160, 180)     # gris azulado: las dimensiones
FONDO = (8, 14, 20)
CAJA = (16, 32, 40)
CAJA_DIM = (16, 26, 34)
BLANCO = (240, 248, 250)
GRIS = (160, 180, 190)
GRIS_TENUE = (104, 124, 136)
LINEA = (56, 86, 100)

HELVETICA = "/System/Library/Fonts/HelveticaNeue.ttc"
NEGRITA, REGULAR, MEDIA = 1, 0, 10

ALTO_CABECERA, ALTO_CAMPO, ALTO_SEPARADOR, MARGEN_INFERIOR = 98, 23, 18, 18


def alto_de(campos):
    return (ALTO_CABECERA + MARGEN_INFERIOR
            + sum(ALTO_SEPARADOR if c == "" else ALTO_CAMPO for c in campos))


# (titulo, subtitulo, campos, (x0, y0, x1), es_hecho)
TABLAS = {
    "d_franja": ("d_franja", "24 filas", [
        "franja_id       PK  (0 a 23)", "hora", "bloque", "orden"],
        (700, 50, 1100), False),
    "d_tiempo": ("d_tiempo", "61 filas", [
        "fecha_id        PK  (AAAAMMDD)", "fecha", "anio · mes · nombre_mes",
        "dia_semana · nombre_dia", "semana_iso", "es_fin_de_semana",
        "hay_operados"], (120, 50, 470), False),
    "d_aeropuerto": ("d_aeropuerto", "104 filas  ·  rol: origen y destino", [
        "aeropuerto_id   PK", "codigo  (IATA)", "nombre · ciudad",
        "zona_horaria", "longitud · latitud", "vuelos_salida",
        "banda_trafico"], (120, 480, 470), False),
    "d_ruta": ("d_ruta", "710 filas", [
        "ruta_id         PK", "numero_vuelo", "etiqueta  ('DME - LED')",
        "duracion_programada_min"], (1330, 50, 1680), False),
    "d_aeronave": ("d_aeronave", "9 filas", [
        "aeronave_id     PK", "codigo · modelo", "autonomia_km",
        "asientos_total"], (1330, 310, 1680), False),
    "d_estado": ("d_estado", "6 filas", [
        "estado_id       PK", "codigo · descripcion", "es_operado"],
        (1330, 570, 1680), False),
    "d_regimen": ("d_regimen", "3 filas  ·  deducida del dato", [
        "regimen_id      PK", "etiqueta", "desde_min · hasta_min",
        "descripcion", "orden"], (1330, 840, 1680), False),
    "h_vuelos": ("h_vuelos", "33.121 filas  ·  grano: el vuelo programado", [
        "vuelo_id        PK · degenerada", "fecha_id             FK",
        "franja_id            FK", "origen_id            FK",
        "destino_id           FK", "ruta_id              FK",
        "aeronave_id          FK", "estado_id            FK",
        "numero_vuelo         degenerada", "salida_programada    degenerada",
        "", "duracion_programada_min", "es_operado  (0/1)"],
        (700, 330, 1100), True),
    "h_demoras": ("h_demoras", "16.773 filas  ·  1:0..1 sobre h_vuelos", [
        "vuelo_id        PK  y  FK", "regimen_id           FK", "",
        "demora_salida_min", "demora_llegada_min", "minutos_recuperados",
        "duracion_real_min"], (700, 830, 1100), True),
}

# (origen, lado, destino, lado, grueso)
ENLACES = [
    ("d_franja", "S", "h_vuelos", "N", False),
    ("d_tiempo", "E", "h_vuelos", "O", False),
    ("d_aeropuerto", "E", "h_vuelos", "O", False),
    ("d_ruta", "O", "h_vuelos", "E", False),
    ("d_aeronave", "O", "h_vuelos", "E", False),
    ("d_estado", "O", "h_vuelos", "E", False),
    ("h_vuelos", "S", "h_demoras", "N", True),
    ("d_regimen", "O", "h_demoras", "E", False),
]

# Desplazamiento vertical del punto de entrada, para que las lineas que llegan
# al mismo borde no se amontonen sobre un unico pixel.
ALTURAS = {"d_tiempo": -90, "d_aeropuerto": 90,
           "d_ruta": -110, "d_aeronave": 0, "d_estado": 110}


def caja(clave):
    _, _, campos, (x0, y0, x1), _ = TABLAS[clave]
    return (x0, y0, x1, y0 + alto_de(campos))


def ancla(c, lado, desplazamiento=0):
    x0, y0, x1, y1 = c
    cx, cy = (x0 + x1) // 2, (y0 + y1) // 2
    return {"N": (cx, y0), "S": (cx, y1),
            "O": (x0, cy + desplazamiento), "E": (x1, cy + desplazamiento)}[lado]


def construir():
    s = SUPER
    lienzo = Image.new("RGB", (ANCHO * s, ALTO * s), FONDO)
    pintor = ImageDraw.Draw(lienzo)

    for origen, lo, destino, ld, grueso in ENLACES:
        p1 = ancla(caja(origen), lo)
        p2 = ancla(caja(destino), ld, ALTURAS.get(origen, 0))
        pintor.line([(p1[0] * s, p1[1] * s), (p2[0] * s, p2[1] * s)],
                    fill=ACENTO if grueso else LINEA, width=(4 if grueso else 2) * s)
        r = (9 if grueso else 7) * s
        pintor.ellipse([p2[0] * s - r, p2[1] * s - r, p2[0] * s + r, p2[1] * s + r],
                       fill=ACENTO if grueso else ACENTO_DIM)

    for clave in TABLAS:
        _, _, _, _, es_hecho = TABLAS[clave]
        x0, y0, x1, y1 = [v * s for v in caja(clave)]
        borde = ACENTO if es_hecho else ACENTO_DIM
        pintor.rounded_rectangle([x0, y0, x1, y1], radius=10 * s,
                                 fill=CAJA if es_hecho else CAJA_DIM,
                                 outline=borde, width=2 * s)
        pintor.rounded_rectangle([x0, y0, x1, y0 + 62 * s], radius=10 * s, fill=borde)
        pintor.rectangle([x0, y0 + 40 * s, x1, y0 + 62 * s], fill=borde)

    lienzo = lienzo.resize((ANCHO, ALTO), Image.LANCZOS)
    pintor = ImageDraw.Draw(lienzo)

    f_titulo = ImageFont.truetype(HELVETICA, 23, index=NEGRITA)
    f_sub = ImageFont.truetype(HELVETICA, 14, index=REGULAR)
    f_campo = ImageFont.truetype(HELVETICA, 15, index=REGULAR)
    f_campo_k = ImageFont.truetype(HELVETICA, 15, index=MEDIA)
    f_leyenda = ImageFont.truetype(HELVETICA, 16, index=REGULAR)
    f_cab = ImageFont.truetype(HELVETICA, 17, index=NEGRITA)

    for clave in TABLAS:
        titulo, subtitulo, campos, _, es_hecho = TABLAS[clave]
        x0, y0, x1, y1 = caja(clave)
        pintor.text((x0 + 16, y0 + 10), titulo, font=f_titulo, fill=(10, 24, 30))
        pintor.text((x0 + 16, y0 + 72), subtitulo, font=f_sub, fill=GRIS_TENUE)
        y = y0 + 98
        for campo in campos:
            if campo == "":
                pintor.line([(x0 + 16, y + 8), (x1 - 16, y + 8)], fill=LINEA, width=1)
                y += ALTO_SEPARADOR
                continue
            clave_campo = campo.rstrip().endswith(("PK", "FK")) or "degen" in campo or "y  FK" in campo
            pintor.text((x0 + 16, y), campo,
                        font=f_campo_k if clave_campo else f_campo,
                        fill=BLANCO if clave_campo else GRIS)
            y += ALTO_CAMPO

    pintor.text((120, 900), "UNA ESTRELLA Y UNA EXTENSION 1:0..1", font=f_cab, fill=ACENTO)
    for i, linea in enumerate([
            "El grano es el vuelo. De los 33.121 programados, solo 16.773",
            "llegaron a despegar antes de que se cerrara el volcado.",
            "Separarlos hace la cobertura contable en vez de esconderla",
            "entre nulos que AVG() ignoraria en silencio."]):
        pintor.text((120, 926 + i * 20), linea, font=f_sub, fill=GRIS_TENUE)

    ly = ALTO - 48
    pintor.rounded_rectangle([120, ly, 150, ly + 18], radius=4, fill=ACENTO)
    pintor.text((160, ly), "Tabla de hechos", font=f_leyenda, fill=GRIS)
    pintor.rounded_rectangle([330, ly, 360, ly + 18], radius=4, fill=ACENTO_DIM)
    pintor.text((370, ly), "Dimension", font=f_leyenda, fill=GRIS)
    pintor.text((530, ly), "PK clave primaria   ·   FK clave foranea   ·   "
                           "degen. dimension degenerada", font=f_leyenda, fill=GRIS_TENUE)

    destino = Path(__file__).with_name("esquema_estrella.png")
    lienzo.save(destino, optimize=True)
    print(f"{destino.name}  {ANCHO}x{ALTO}  {destino.stat().st_size/1024:.0f} KB")


if __name__ == "__main__":
    construir()
