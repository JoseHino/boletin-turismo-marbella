# -*- coding: utf-8 -*-
"""Rehace numeros/index.json a partir de los boletines publicados.

    python scripts/indice.py

Make solo sube el fichero del número (numeros/AAAA-MM.html); este script lee
sus <meta name="boletin:..."> y deja la lista que pinta la portada. Los
ficheros con "prueba" en el nombre salen marcados y la portada los oculta
(se ven con ?pruebas=1).
"""

import glob
import html
import json
import os
import re
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CARPETA = os.path.join(RAIZ, "numeros")


def meta(texto, nombre):
    m = re.search(rf'<meta\s+name="boletin:{nombre}"\s+content="([^"]*)"', texto)
    return html.unescape(m.group(1)).strip() if m else ""


def main():
    numeros = []
    for ruta in glob.glob(os.path.join(CARPETA, "*.html")):
        with open(ruta, encoding="utf-8") as f:
            texto = f.read()
        archivo = os.path.basename(ruta)
        numeros.append({
            "numero": meta(texto, "numero") or archivo[:-5],
            "fecha": meta(texto, "fecha"),
            "asunto": meta(texto, "asunto"),
            "resumen": meta(texto, "resumen"),
            "archivo": archivo,
            "prueba": "prueba" in archivo,
        })
    numeros.sort(key=lambda n: (n["numero"], n["archivo"]), reverse=True)
    with open(os.path.join(CARPETA, "index.json"), "w", encoding="utf-8") as f:
        json.dump(numeros, f, ensure_ascii=False, indent=1)
    print(f"{len(numeros)} números en numeros/index.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
