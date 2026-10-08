# -*- coding: utf-8 -*-
"""Recolector diario de noticias para el boletín de Turismo de Marbella.

    python scripts/noticias.py        -> datos/noticias.json

Los RSS solo guardan los últimos días (Hosteltur unas 48 horas, marbella.es
sus 8 últimas noticias), así que para un boletín mensual hay que ir
acumulando. Este script se ejecuta cada día (GitHub Actions), añade lo nuevo y
olvida lo que tiene más de DIAS días. Make lee el acumulado al redactar.

Fuentes:
- Ayuntamiento de Marbella: RSS de noticias, paginado, con la delegación de
  cada noticia (se lee de la propia página, igual que Marbella News).
- Prensa especializada: Hosteltur, Preferente, Nexotur, TecnoHotel,
  Smart Travel News y SEGITTUR (solo lo que toca a Marbella, la Costa del Sol,
  Andalucía o temas clave para el destino).
- Prensa general: Diario Sur (sección Marbella) y Google Noticias.
- BOJA: disposiciones de turismo (la API no busca por texto: se filtra aquí).

Solo biblioteca estándar.
"""

import datetime
import email.utils
import html
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SALIDA = os.path.join(RAIZ, "datos", "noticias.json")
DIAS = 40
UA = {"User-Agent": "Mozilla/5.0 (boletin-turismo-marbella; +https://github.com/JoseHino/boletin-turismo-marbella)"}

MARBELLA_RSS = "https://www.marbella.es/actualidad/noticias.feed?type=rss&start={start}"
MARBELLA_TURISMO = "https://www.marbella.es/temas/turismo.feed?type=rss"
# La delegación va en la cabecera de cada noticia: <div class="... uk-heading-bullet ...">
# <a href="/temas/turismo.html">Turismo</a></div> (cambió en 2026; antes era un <span uk-link-muted>)
RE_DELEGACION = re.compile(r'uk-heading-bullet[^"]*"[^>]*>\s*<a[^>]*href="/temas/[^"]+"[^>]*>\s*([\s\S]*?)\s*</a>')
PRENSA_SECTOR = [
    ("Hosteltur", "https://www.hosteltur.com/rss"),
    ("Preferente", "https://www.preferente.com/feed"),
    ("Nexotur", "https://www.nexotur.com/rss"),
    ("TecnoHotel", "https://tecnohotelnews.com/feed/"),
    ("Smart Travel News", "https://www.smarttravel.news/feed/"),
    ("SEGITTUR", "https://www.segittur.es/feed/"),
]
DIARIO_SUR = "https://www.diariosur.es/rss/2.0/?section=marbella"
GOOGLE = "https://news.google.com/rss/search?q={q}&hl=es&gl=ES&ceid=ES:es"
GOOGLE_CONSULTAS = [
    "Marbella turismo when:30d",
    "Marbella hoteles when:30d",
    "Marbella congreso OR feria OR festival when:30d",
    "\"Costa del Sol\" turismo when:30d",
]
BOJA = ("https://datos.juntadeandalucia.es/api/v0/boja/get/search_pagination"
        "?date_from={desde}&date_to={hasta}&size=100&page={pagina}&order_by=date&mode=DESC")

LOCAL = re.compile(r"marbella|puerto ban[uú]s|san pedro (de )?alc[aá]ntara|nueva andaluc[ií]a|costa del sol|"
                   r"m[aá]laga|andaluc[ií]a|benahav[ií]s|estepona|ist[aá]n|oj[eé]n", re.I)
TEMAS = re.compile(r"viviendas? (de uso |con fines )?tur[ií]stic|tasa tur[ií]stica|reino unido|brit[aá]nic|"
                   r"turismo de lujo|golf|congresos|\bmice\b|cruceros|destino tur[ií]stico inteligente|\bdti\b|"
                   r"conectividad a[eé]rea|fitur|\bwtm\b|\bitb\b|ocupaci[oó]n hotelera|exceltur|turespa[ñn]a|"
                   r"sostenibilidad tur[ií]stica|fondos next|kit digital", re.I)
TURISMO = re.compile(r"turis|turíst|hotel|playa|crucero|congreso|feria|festival|evento|golf|restaura|"
                     r"gastronom|ocio|visitante|aeropuerto|vuelo|puerto|ban[uú]s|starlite|conciertos?|"
                     r"exposici[oó]n|museo|semana santa|navidad|promoci[oó]n", re.I)
SUCESOS = re.compile(r"detenid|polic[ií]a|guardia civil|asesin|homicid|muert[eo]|fallec|juzgado|juicio|"
                     r"investigad|droga|narco|tiroteo|robo|apuñal|agresi[oó]n|accidente|incendio", re.I)
BOJA_TURISMO = re.compile(r"turism|tur[ií]stic|campings?|guías? de turismo", re.I)
BOJA_RUIDO = re.compile(r"registro de fundaciones|publicidad institucional|adjudicaci[oó]n|formalizaci[oó]n|"
                        r"contrato|arrendamiento|plazas?\b|selecci[oó]n|puestos? de trabajo|estatutos|s[ií]mbolos|"
                        r"nombra|oposici[oó]n|funcionari|autorizaci[oó]n ambiental|l[ií]nea delimitadora|"
                        r"emplazamiento|recurso contencioso", re.I)
OTRA_PROVINCIA = re.compile(r"(Delegaci[oó]n Territorial[^,.]* en|Ayuntamiento de) "
                            r"(?!Marbella|M[aá]laga)[A-ZÁÉÍÓÚ][\wáéíóúñ]+", re.I)

# Delegaciones municipales que no suelen interesar al sector (se guardan igual,
# pero van al final para que la IA las mire con menos prioridad)
DELEGACIONES_SECTOR = re.compile(r"turismo|congresos|playas|fiestas|cultura|deportes|comercio|promoci[oó]n|"
                                 r"movilidad|transporte|puertos|innovaci[oó]n|alcald[ií]a|distrito|nextgeneration|"
                                 r"medio ambiente|extranjeros|obras", re.I)


def get(url, timeout=60, reintentos=3):
    ultimo = None
    for i in range(reintentos):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
                return r.read()
        except Exception as e:                                    # noqa: BLE001
            ultimo = e
            time.sleep(2 * (i + 1))
    raise ultimo


def limpiar(texto, n=None):
    t = re.sub(r"<[^>]+>", " ", html.unescape(texto or ""))
    t = re.sub(r"\s+", " ", t).strip()
    return (t[:n].rsplit(" ", 1)[0] + "…") if n and len(t) > n else t


def fecha_rss(texto):
    try:
        d = email.utils.parsedate_to_datetime(texto)
        if d.tzinfo is None:
            d = d.replace(tzinfo=datetime.timezone.utc)
        return d.astimezone(datetime.timezone.utc)
    except Exception:                                             # noqa: BLE001
        return None


def items_rss(xml_bytes):
    """(titulo, enlace, fecha, resumen, fuente_google) de un RSS 2.0."""
    raiz = ET.fromstring(xml_bytes)
    for it in raiz.iter("item"):
        fuente = it.find("source")
        yield (
            limpiar(it.findtext("title")),
            (it.findtext("link") or "").strip(),
            fecha_rss(it.findtext("pubDate") or ""),
            it.findtext("description") or "",
            fuente.text.strip() if fuente is not None and fuente.text else "",
        )


def clave_titulo(t):
    return re.sub(r"[^a-z0-9áéíóúñü]+", " ", t.lower()).strip()[:90]


# ── fuentes ───────────────────────────────────────────────────────────────
def marbella(corte, conocidas):
    nuevas, start = [], 0
    while start <= 400:
        lote = list(items_rss(get(MARBELLA_RSS.format(start=start))))
        if not lote:
            break
        for titulo, enlace, fecha, desc, _ in lote:
            if not fecha or fecha < corte or enlace in conocidas:
                continue
            delegacion = ""
            try:
                pagina = get(enlace, timeout=40).decode("utf-8", "replace")
                m = RE_DELEGACION.search(pagina)
                delegacion = limpiar(m.group(1)) if m else ""
                time.sleep(0.4)
            except Exception as e:                                # noqa: BLE001
                print(f"  [!] delegación de {enlace[:70]}…: {e}")
            nuevas.append({"fuente": "Ayuntamiento de Marbella", "tipo": "ayuntamiento", "titulo": titulo,
                           "url": enlace, "fecha": fecha.isoformat(), "delegacion": delegacion,
                           "resumen": limpiar(desc, 220)})
        if min((f for _, _, f, _, _ in lote if f), default=corte) < corte:
            break
        start += 8
    # El canal del tema Turismo no va por fecha y a veces trae noticias que ya
    # no salen en el general: se añade lo que cae dentro del periodo
    try:
        for titulo, enlace, fecha, desc, _ in items_rss(get(MARBELLA_TURISMO)):
            if fecha and fecha >= corte and enlace not in conocidas:
                nuevas.append({"fuente": "Ayuntamiento de Marbella", "tipo": "ayuntamiento", "titulo": titulo,
                               "url": enlace, "fecha": fecha.isoformat(), "delegacion": "Turismo",
                               "resumen": limpiar(desc, 220)})
    except Exception as e:                                        # noqa: BLE001
        print(f"  [!] canal de Turismo: {e}")
    return nuevas


def prensa_sector(corte):
    out = []
    for nombre, url in PRENSA_SECTOR:
        try:
            for titulo, enlace, fecha, desc, _ in items_rss(get(url)):
                if not fecha or fecha < corte:
                    continue
                texto = f"{titulo} {limpiar(desc, 600)}"
                if LOCAL.search(texto) or TEMAS.search(texto):
                    out.append({"fuente": nombre, "tipo": "sector", "titulo": titulo, "url": enlace,
                                "fecha": fecha.isoformat(), "resumen": limpiar(desc, 220)})
        except Exception as e:                                    # noqa: BLE001
            print(f"  [!] {nombre}: {e}")
    return out


def prensa_general(corte):
    out = []
    try:
        for titulo, enlace, fecha, desc, _ in items_rss(get(DIARIO_SUR)):
            texto = f"{titulo} {limpiar(desc, 400)}"
            if fecha and fecha >= corte and TURISMO.search(texto) and not SUCESOS.search(texto):
                out.append({"fuente": "Diario Sur", "tipo": "prensa", "titulo": titulo, "url": enlace,
                            "fecha": fecha.isoformat(), "resumen": limpiar(desc, 220)})
    except Exception as e:                                        # noqa: BLE001
        print(f"  [!] Diario Sur: {e}")
    for q in GOOGLE_CONSULTAS:
        try:
            for titulo, enlace, fecha, _, fuente in items_rss(get(GOOGLE.format(q=urllib.parse.quote(q)))):
                if not fecha or fecha < corte or SUCESOS.search(titulo):
                    continue
                if "marbella.es" in fuente.lower() or fuente == "Ayuntamiento de Marbella":
                    continue   # ya viene directamente del Ayuntamiento
                if fuente and titulo.endswith(f" - {fuente}"):
                    titulo = titulo[: -len(fuente) - 3]
                out.append({"fuente": fuente or "Google Noticias", "tipo": "prensa", "titulo": titulo,
                            "url": enlace, "fecha": fecha.isoformat(), "resumen": ""})
        except Exception as e:                                    # noqa: BLE001
            print(f"  [!] Google Noticias «{q}»: {e}")
    return out


def boja(corte, hoy):
    out, pagina = [], 1
    desde = corte.date().isoformat()
    while pagina <= 40:
        d = json.loads(get(BOJA.format(desde=desde, hasta=hoy.isoformat(), pagina=pagina), timeout=90).decode("utf-8"))
        res = d.get("results") or []
        for r in res:
            resumen = limpiar(r.get("summary"))
            seccion = r.get("titleSec") or ""
            # La consejería es «de Turismo, Justicia, Desregulación y Administración
            # Local»: el organismo no sirve de filtro, hay que mirar el texto
            if seccion.startswith("2."):          # nombramientos y personal
                continue
            if not BOJA_TURISMO.search(resumen) or BOJA_RUIDO.search(resumen) or OTRA_PROVINCIA.search(resumen):
                continue
            partes = (r.get("id") or "").split(".")   # disposition.AAAA.NNN.X
            url = (f"https://www.juntadeandalucia.es/boja/{partes[1]}/{partes[2]}/{partes[3]}"
                   if len(partes) == 4 else "https://www.juntadeandalucia.es/boja/")
            try:
                f = datetime.datetime.strptime(r.get("date", ""), "%d/%m/%Y").replace(tzinfo=datetime.timezone.utc)
            except ValueError:
                f = hoy_dt()
            out.append({"fuente": "BOJA", "tipo": "boja", "titulo": limpiar(resumen, 300), "url": url,
                        "fecha": f.isoformat(), "seccion": seccion, "organismo": r.get("organisation") or "",
                        "resumen": ""})
        if len(res) < 100:
            break
        pagina += 1
    return out


def hoy_dt():
    return datetime.datetime.now(datetime.timezone.utc)


# ── texto para la IA ──────────────────────────────────────────────────────
def texto_ia(items):
    """Lista compacta para la IA. Con tope por grupo para que el contexto no se
    dispare (los enlaces de Google Noticias son muy largos)."""
    grupos = [
        ("AYUNTAMIENTO DE MARBELLA (noticias municipales; entre corchetes, la delegación)", "ayuntamiento", 120),
        ("PRENSA ESPECIALIZADA EN TURISMO", "sector", 60),
        ("PRENSA GENERAL (Diario Sur y medios recogidos por Google Noticias)", "prensa", 90),
        ("BOJA (disposiciones de turismo)", "boja", 30),
    ]
    partes = []
    for cabecera, tipo, tope in grupos:
        lista = sorted((i for i in items if i["tipo"] == tipo), key=lambda i: i["fecha"], reverse=True)
        if tipo == "ayuntamiento":   # primero las delegaciones que interesan al sector (orden estable)
            lista.sort(key=lambda i: not DELEGACIONES_SECTOR.search(i.get("delegacion", "")))
        lista = lista[:tope]
        lineas = []
        for i in lista:
            f = i["fecha"][:10]
            f = f"{f[8:10]}/{f[5:7]}/{f[0:4]}"
            extra = f" [{i['delegacion']}]" if i.get("delegacion") else ""
            res = f" — {i['resumen']}" if i.get("resumen") else ""
            lineas.append(f"- {f} · {i['fuente']}{extra} · {i['titulo']}{res} · {i['url']}")
        partes.append(f"### {cabecera} ({len(lista)})\n" + ("\n".join(lineas) if lineas else "(nada)"))
    return "\n\n".join(partes)


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:                                             # noqa: BLE001
        pass
    ahora = hoy_dt()
    corte = ahora - datetime.timedelta(days=DIAS)
    previas = []
    if os.path.exists(SALIDA):
        with open(SALIDA, encoding="utf-8") as f:
            previas = json.load(f).get("items", [])
    previas = [i for i in previas if i["fecha"] >= corte.isoformat()]
    # Las del Ayuntamiento sin delegación se vuelven a leer (fallo puntual de la web)
    conocidas = {i["url"] for i in previas if i["tipo"] != "ayuntamiento" or i.get("delegacion")}

    print("== Noticias para el boletín de Turismo de Marbella ==")
    nuevas, fallos = [], []
    for nombre, f in (("Ayuntamiento", lambda: marbella(corte, conocidas)),
                      ("Prensa del sector", lambda: prensa_sector(corte)),
                      ("Prensa general", lambda: prensa_general(corte)),
                      # El BOJA se repasa entero solo la primera vez; luego, los últimos días
                      ("BOJA", lambda: boja(corte if not previas else max(corte, ahora - datetime.timedelta(days=5)),
                                            ahora.date()))):
        try:
            lote = f()
            nuevas += lote
            print(f"  [ok] {nombre}: {len(lote)}")
        except Exception as e:                                    # noqa: BLE001
            fallos.append(nombre)
            print(f"  [!] {nombre}: {e}")

    # Fusión: por URL y por titular (la misma noticia sale en varias consultas)
    por_url, vistos, items = {}, set(), []
    for i in nuevas + previas:          # lo recién leído manda sobre lo guardado
        por_url.setdefault(i["url"], i)
    for i in sorted(por_url.values(), key=lambda x: x["fecha"], reverse=True):
        k = clave_titulo(i["titulo"])
        if k in vistos:
            continue
        vistos.add(k)
        items.append(i)

    datos = {
        "generado": ahora.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "desde": corte.date().isoformat(), "hasta": ahora.date().isoformat(),
        "fallos": fallos,
        "recuento": {t: sum(1 for i in items if i["tipo"] == t) for t in ("ayuntamiento", "sector", "prensa", "boja")},
        "items": items,
    }
    datos["texto"] = texto_ia(items)
    os.makedirs(os.path.dirname(SALIDA), exist_ok=True)
    with open(SALIDA, "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False, indent=1)
    print(f"\nListo: {len(items)} noticias ({datos['recuento']}) · texto para la IA: {len(datos['texto'])} caracteres")
    return 0


if __name__ == "__main__":
    sys.exit(main())
