#!/usr/bin/env python3
"""
Empaqueta el libro y su extracto en un unico .twbx.

Un .twbx es un ZIP con el .twb en la raiz y los datos en una carpeta `Data/`.
La ruta que el .twb declara -`Data/retraso_red_aerea_2017.hyper`- tiene que
coincidir EXACTAMENTE con la del ZIP, incluida la mayuscula de `Data`: si no
coincide, Tableau abre el libro y lo muestra vacio, sin dar ningun error.

Se empaqueta porque Tableau Public SOLO publica libros cuyos datos viajan
dentro: una conexion a un archivo local se abre en Tableau Desktop pero es
rechazada al publicar.
"""

import zipfile
from pathlib import Path

AQUI = Path(__file__).resolve().parent
LIBRO = AQUI / "Retraso_Red_Aerea_2017.twb"
EXTRACTO = AQUI / "retraso_red_aerea_2017.hyper"
SALIDA = AQUI / "Retraso_Red_Aerea_2017.twbx"


def main() -> None:
    for archivo in (LIBRO, EXTRACTO):
        if not archivo.exists():
            raise SystemExit(f"Falta {archivo.name}.")

    SALIDA.unlink(missing_ok=True)
    with zipfile.ZipFile(SALIDA, "w", zipfile.ZIP_DEFLATED) as z:
        z.write(LIBRO, LIBRO.name)
        z.write(EXTRACTO, f"Data/{EXTRACTO.name}")

    with zipfile.ZipFile(SALIDA) as z:
        contenido = z.namelist()
        print(f"{SALIDA.name}  {SALIDA.stat().st_size / 1024:.0f} KB")
        for nombre in contenido:
            print(f"  {nombre}")
        esperado = {LIBRO.name, f"Data/{EXTRACTO.name}"}
        if set(contenido) != esperado:
            raise SystemExit("El contenido del paquete no es el esperado.")
    print("\nPaquete correcto.")


if __name__ == "__main__":
    main()
