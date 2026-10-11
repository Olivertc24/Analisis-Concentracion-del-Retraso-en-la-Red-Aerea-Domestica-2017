"""
Genera el banner de cabecera del repositorio y del aplicativo.

FORMATO. El mismo de la serie de trabajos: lienzo de 1800x460, barra de acento
superior, antetitulo de la Escuela, titulo en dos lineas y las cifras al pie.
Lo propio de cada trabajo es el color y el motivo del fondo.

MOTIVO. La distribucion de la demora de salida, dibujada a escala real. No es
un adorno: es el hallazgo que sostiene toda la investigacion. Hay un modo bajo
enorme que se agota en los 11 minutos, un modo alto pequeno que no empieza
hasta los 124, y entre ambos un hueco donde no cae NI UN SOLO vuelo de los
16.773 operados. La media -12,20 minutos- cae dentro de ese hueco.

ANTIALIASING. Pillow no suaviza los bordes de las primitivas: el fondo y el
motivo se trazan a triple resolucion y se reducen al final.
"""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ANCHO, ALTO = 1800, 460
SUPER = 3

ACENTO = (43, 212, 232)          # cian; sin uso en los demas trabajos
ACENTO_OSCURO = (17, 86, 100)
FONDO_IZQ = (8, 14, 20)
FONDO_DER = (14, 62, 78)
BLANCO = (255, 255, 255)
GRIS_TEXTO = (186, 204, 210)

HELVETICA = "/System/Library/Fonts/HelveticaNeue.ttc"
NEGRITA, REGULAR = 1, 0

ANTETITULO = "ESCUELA DE ESTADISTICA Y CIENCIAS ACTUARIALES   ·   COMPUTACION II"
TITULO = ["Concentracion del retraso", "en la red aerea domestica"]
PIE = "16.773 vuelos operados   ·   104 aeropuertos   ·   julio - agosto 2017"

# Demora de salida en minutos: vuelos observados. Medido sobre la fuente.
MODO_BAJO = {0: 717, 1: 2249, 2: 3645, 3: 3651, 4: 2801, 5: 1653, 6: 784,
             7: 324, 8: 103, 9: 34, 10: 10, 11: 2}
# El modo alto va de 124 a 277 y suma 800 vuelos; se resume por tramos.
MODO_ALTO = {135: 16, 165: 187, 195: 381, 225: 191, 258: 25}
MINUTO_MAXIMO = 285


def degradado(ancho, alto):
    lienzo = Image.new("RGB", (ancho, alto))
    pintor = ImageDraw.Draw(lienzo)
    for x in range(ancho):
        t = (x / (ancho - 1)) ** 0.75
        color = tuple(round(a + (b - a) * t) for a, b in zip(FONDO_IZQ, FONDO_DER))
        pintor.line([(x, 0), (x, alto)], fill=color)
    return lienzo


def motivo(lienzo):
    """La distribucion real de la demora, con su hueco a la vista."""
    capa = Image.new("RGBA", lienzo.size, (0, 0, 0, 0))
    pintor = ImageDraw.Draw(capa)
    s = SUPER
    # El motivo vive en la franja inferior: con mas altura, el modo bajo se
    # metia detras del titulo y dejaba de leerse justo la parte que importa.
    base_y = 456 * s
    alto_max = 118 * s
    margen_x = 46
    pico = max(MODO_BAJO.values())

    def barra(minuto, vuelos, ancho_min, alfa):
        util = (ANCHO - 2 * margen_x) * s
        x = margen_x * s + (minuto / MINUTO_MAXIMO) * util
        w = (ancho_min / MINUTO_MAXIMO) * util
        h = (vuelos / pico) * alto_max
        pintor.rectangle([x, base_y - h, x + w * 0.82, base_y], fill=ACENTO + (alfa,))

    for minuto, vuelos in MODO_BAJO.items():
        barra(minuto, vuelos, 1, 58)
    # El modo alto se amplifica para que sea visible: 381 vuelos frente a 3.651
    # serian tres pixeles. Se declara aqui porque el dibujo deja de ser a escala.
    for minuto, vuelos in MODO_ALTO.items():
        barra(minuto - 14, vuelos * 6, 29, 42)

    # Linea de la media, que cae en el hueco.
    x_media = margen_x * s + (12.20 / MINUTO_MAXIMO) * (ANCHO - 2 * margen_x) * s
    pintor.line([(x_media, base_y - alto_max * 1.25), (x_media, base_y)],
                fill=ACENTO + (95,), width=2 * s)

    return Image.alpha_composite(lienzo.convert("RGBA"), capa).convert("RGB")


def texto_espaciado(pintor, xy, texto, fuente, fill, espaciado):
    x, y = xy
    for caracter in texto:
        pintor.text((x, y), caracter, font=fuente, fill=fill)
        x += pintor.textlength(caracter, font=fuente) + espaciado


def construir():
    lienzo = motivo(degradado(ANCHO * SUPER, ALTO * SUPER))
    lienzo = lienzo.resize((ANCHO, ALTO), Image.LANCZOS)
    pintor = ImageDraw.Draw(lienzo)

    for x in range(ANCHO):
        t = x / (ANCHO - 1)
        color = tuple(round(a + (b - a) * t) for a, b in zip(ACENTO_OSCURO, ACENTO))
        pintor.line([(x, 0), (x, 7)], fill=color)

    f_antetitulo = ImageFont.truetype(HELVETICA, 19, index=REGULAR)
    f_titulo = ImageFont.truetype(HELVETICA, 62, index=NEGRITA)
    f_pie = ImageFont.truetype(HELVETICA, 27, index=REGULAR)

    texto_espaciado(pintor, (74, 82), ANTETITULO, f_antetitulo, ACENTO, 1.6)
    pintor.text((72, 132), TITULO[0], font=f_titulo, fill=BLANCO)
    pintor.text((72, 204), TITULO[1], font=f_titulo, fill=BLANCO)
    pintor.text((74, 292), PIE, font=f_pie, fill=GRIS_TEXTO)

    destino = Path(__file__).with_name("banner_retraso.png")
    lienzo.save(destino, optimize=True)
    print(f"{destino.name}  {lienzo.size[0]}x{lienzo.size[1]}  "
          f"{destino.stat().st_size / 1024:.0f} KB")


if __name__ == "__main__":
    construir()
