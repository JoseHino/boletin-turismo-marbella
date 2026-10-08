# -*- coding: utf-8 -*-
"""Cifras del boletín profesional de Turismo de Marbella.

    python scripts/kpis.py            -> datos/kpis.json

Toma las mismas series que el Observatorio Turístico de Marbella y deja en
datos/kpis.json el último mes publicado con su variación interanual, ya
redactado y maquetado. Make lee ese fichero y pega el bloque `html` tal cual en
el boletín: la IA nunca escribe una cifra.

Fuentes:
- INE, Encuesta de Ocupación Hotelera (Marbella punto turístico), IRSH y EOAP.
- Turismo Costa del Sol, Big Data (pernoctaciones por país), vía el observatorio.
- Junta de Andalucía, Registro de Turismo (VUT), vía el observatorio.
- Eurostat avia_paoa (pasajeros del aeropuerto de Málaga).

Solo biblioteca estándar. Si el INE falla, no se sobrescribe el fichero.
"""

import datetime
import html
import json
import os
import sys
import time
import urllib.request

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SALIDA = os.path.join(RAIZ, "datos", "kpis.json")

OBSERVATORIO = "https://josehino.github.io/observatorio-turistico-marbella/"
INE = "https://servicios.ine.es/wstempus/js/ES/DATOS_SERIE/"
EUROSTAT = ("https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/avia_paoa"
            "?format=JSON&lang=en&freq=M&unit=PAS&tra_meas=PAS_CRD&rep_airp=ES_LEMG"
            "&schedule=TOTAL&tra_cov=TOTAL&sinceTimePeriod={desde}")

# Mismos códigos que el observatorio (verificados allí contra el Excel del Ayuntamiento).
SERIES = {
    "viaj_es": "EOT2759", "viaj_ext": "EOT2760",
    "pern_es": "EOT2761", "pern_ext": "EOT2762",
    "ocup_hab": "EOT3224", "estancia": "EOT2936", "personal": "EOT3296",
    "adr": "EOT43542", "revpar": "EOT43946",
    "apt_pern_es": "EOT9425", "apt_pern_ext": "EOT9426",
}

MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
         "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
MESES_CORTO = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]

# Paleta (la misma que plantilla/boletin.html)
AZUL, TURQUESA, CORAL, GRIS, FONDO = "#0B2F4E", "#0E7C86", "#C2502F", "#5B6B7A", "#F3F6F8"
FUENTE = "Arial,Helvetica,sans-serif"


# ── utilidades ────────────────────────────────────────────────────────────
def get_json(url, reintentos=3, timeout=90):
    ultimo = None
    for i in range(reintentos):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "boletin-turismo-marbella/1.0"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception as e:                                    # noqa: BLE001
            ultimo = e
            time.sleep(2 * (i + 1))
    raise ultimo


def mes_texto(p, corto=False):
    y, m = map(int, p.split("-"))
    return f"{(MESES_CORTO if corto else MESES)[m - 1]} {y}" if corto else f"{MESES[m - 1]} de {y}"


def menos_un_anio(p):
    y, m = map(int, p.split("-"))
    return f"{y - 1:04d}-{m:02d}"


def num(v, dec=0):
    """Formato español con separador de millares siempre (5.915, no 5915)."""
    s = f"{v:,.{dec}f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def signo(v, dec=1):
    return ("+" if v > 0 else "−" if v < 0 else "") + num(abs(v), dec)


def ine_mensual(cod, nult=40):
    """{'AAAA-MM': valor}. El periodo sale de Anyo + FK_Periodo, nunca de Fecha
    (Fecha va a medianoche de Madrid y en UTC corre toda la serie un mes)."""
    j = get_json(f"{INE}{cod}?nult={nult}")
    out, prov = {}, {}
    for d in j.get("Data", []):
        p, v = d.get("FK_Periodo"), d.get("Valor")
        if v is None or p is None or not (1 <= int(p) <= 12):
            continue
        clave = f"{int(d['Anyo']):04d}-{int(p):02d}"
        out[clave] = v
        prov[clave] = d.get("FK_TipoDato") in (2, 3)
    return out, prov


# ── indicadores ───────────────────────────────────────────────────────────
def indicador(id_, nombre, serie, periodo, unidad="", dec=0, modo="pct", fuente="INE", prov=None, nota=""):
    """modo 'pct' = variación interanual en %; 'pp' = diferencia en puntos;
    'abs' = diferencia en la misma unidad (p. ej. días de estancia)."""
    if periodo not in serie:
        return None
    v = serie[periodo]
    previo = serie.get(menos_un_anio(periodo))
    var, var_txt = None, "sin dato del año anterior"
    if previo not in (None, 0):
        if modo == "pct":
            var = (v - previo) / previo * 100
            var_txt = f"{signo(var)} %"
        elif modo == "pp":
            var = v - previo
            var_txt = f"{signo(var)} p. p."
        else:
            var = v - previo
            var_txt = f"{signo(var, dec if dec else 1)}{(' ' + unidad) if unidad else ''}"
    return {
        "id": id_, "nombre": nombre, "valor": round(v, 2),
        "valor_texto": num(v, dec) + (f" {unidad}" if unidad else ""),
        "variacion": None if var is None else round(var, 2),
        "variacion_texto": var_txt,
        "comparado_con": mes_texto(menos_un_anio(periodo), corto=True),
        "tendencia": None if var is None else ("sube" if var > 0.05 else "baja" if var < -0.05 else "igual"),
        "periodo": periodo, "periodo_texto": mes_texto(periodo),
        "provisional": bool(prov and prov.get(periodo)),
        "fuente": fuente, "nota": nota,
    }


def suma(a, b):
    return {k: a[k] + b[k] for k in a if k in b}


def recoger_ine():
    s, prov = {}, {}
    for k, cod in SERIES.items():
        s[k], prov[k] = ine_mensual(cod)
        print(f"  [ok] {k:12s} {cod:9s} último {max(s[k]) if s[k] else '—'}")
    pern = suma(s["pern_es"], s["pern_ext"])
    viaj = suma(s["viaj_es"], s["viaj_ext"])
    periodo = max(pern)
    cuota_ext = {k: s["pern_ext"][k] / pern[k] * 100 for k in pern if pern[k]}
    apt = suma(s["apt_pern_es"], s["apt_pern_ext"])
    p = prov["pern_es"]
    lista = [
        indicador("pernoctaciones_hotel", "Pernoctaciones en hoteles", pern, periodo, prov=p, fuente="INE · EOH"),
        indicador("viajeros_hotel", "Viajeros alojados en hoteles", viaj, periodo, prov=p, fuente="INE · EOH"),
        indicador("ocupacion_hab", "Ocupación hotelera (habitaciones)", s["ocup_hab"], periodo, "%", 1, "pp",
                  "INE · EOH", prov["ocup_hab"]),
        indicador("cuota_extranjero", "Pernoctaciones de extranjeros", cuota_ext, periodo, "%", 1, "pp",
                  "INE · EOH", p, "Peso sobre el total de pernoctaciones hoteleras"),
        indicador("adr", "Tarifa media diaria (ADR)", s["adr"], max(s["adr"]), "€", 2, "pct",
                  "INE · IRSH", prov["adr"]),
        indicador("revpar", "Ingreso por habitación disponible (RevPAR)", s["revpar"], max(s["revpar"]), "€", 2,
                  "pct", "INE · IRSH", prov["revpar"]),
        indicador("estancia", "Estancia media en hoteles", s["estancia"], periodo, "días", 2, "abs",
                  "INE · EOH", prov["estancia"]),
        indicador("empleo_hotel", "Personal empleado en hoteles", s["personal"], periodo, fuente="INE · EOH",
                  prov=prov["personal"]),
        indicador("pernoctaciones_apt", "Pernoctaciones en apartamentos turísticos", apt, max(apt),
                  fuente="INE · EOAP", prov=prov["apt_pern_es"]),
    ]
    return periodo, [x for x in lista if x]


def recoger_mercados():
    """Top 5 países por pernoctaciones (hoteles + apartamentos), Big Data de
    Turismo Costa del Sol, tal como lo publica el observatorio."""
    d = get_json(OBSERVATORIO + "data/paises_marbella.json")
    meses = d["meses"]
    agregados = set(d["meta"].get("agregados", [])) | {"España", "Extranjero", "Total"}
    tot = {}
    for tipo in ("Hoteles", "Apartamentos"):
        for pais, vals in d["datos"].get(tipo, {}).get("Pernoctaciones", {}).items():
            if pais in agregados:
                continue
            acc = tot.setdefault(pais, [0] * len(meses))
            for i, v in enumerate(vals):
                if v is not None:
                    acc[i] += v
    # último mes con datos de verdad (la serie puede venir rellenada con ceros/None)
    i = max(j for j in range(len(meses)) if sum(v[j] for v in tot.values()) > 0)
    periodo = meses[i]
    i12 = meses.index(menos_un_anio(periodo)) if menos_un_anio(periodo) in meses else None
    filas = []
    for pais, vals in tot.items():
        v = vals[i]
        if not v:
            continue
        previo = vals[i12] if i12 is not None else None
        var = (v - previo) / previo * 100 if previo else None
        filas.append({"pais": pais, "pernoctaciones": v, "texto": num(v),
                      "variacion": None if var is None else round(var, 1),
                      "variacion_texto": "—" if var is None else f"{signo(var)} %"})
    filas.sort(key=lambda r: -r["pernoctaciones"])
    return {"periodo": periodo, "periodo_texto": mes_texto(periodo),
            "fuente": "Turismo Costa del Sol · Big Data (microdato EOH)", "lista": filas[:5]}


def recoger_vut():
    d = get_json(OBSERVATORIO + "data/rta_vut_marbella.json", timeout=180)
    regs = [r.get("registration_date") or "" for r in d.get("records", [])]
    hoy = datetime.date.fromisoformat(d.get("fetched_at", datetime.date.today().isoformat()))
    hace = (hoy - datetime.timedelta(days=365)).isoformat()
    altas_12m = sum(1 for r in regs if r >= hace)
    plazas = sum(int(r.get("tot_gen_places") or 0) for r in d.get("records", []))
    return {"total": d.get("total", len(regs)), "total_texto": num(d.get("total", len(regs))),
            "plazas": plazas, "plazas_texto": num(plazas),
            "altas_12_meses": altas_12m, "altas_12_meses_texto": num(altas_12m),
            "fecha": d.get("fetched_at"), "fuente": "Junta de Andalucía · Registro de Turismo (VUT)"}


def recoger_aeropuerto():
    desde = f"{datetime.date.today().year - 2}-01"
    d = get_json(EUROSTAT.format(desde=desde))
    ti = {v: k for k, v in d["dimension"]["time"]["category"]["index"].items()}
    serie = {ti[int(k)]: v for k, v in d["value"].items() if int(k) in ti}
    periodo = max(serie)
    return indicador("pasajeros_agp", "Pasajeros en el aeropuerto de Málaga", serie, periodo,
                     fuente="Eurostat · avia_paoa")


# ── maquetación (HTML apto para correo: tablas y estilos en línea) ────────
def flecha(t):
    return {"sube": "&#9650;", "baja": "&#9660;"}.get(t, "&#9644;")


def tarjeta(k):
    color = TURQUESA if k["tendencia"] == "sube" else CORAL if k["tendencia"] == "baja" else GRIS
    periodo = "" if k.get("_mismo_periodo") else f" · {mes_texto(k['periodo'], corto=True)}"
    prov = " (prov.)" if k.get("provisional") else ""
    return (
        f'<td width="50%" valign="top" style="padding:5px;">'
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        f'style="background:{FONDO};border-radius:10px;border-collapse:separate;">'
        f'<tr><td style="padding:14px 16px;font-family:{FUENTE};">'
        f'<div style="font-size:11px;line-height:1.35;color:{GRIS};text-transform:uppercase;letter-spacing:.04em;">'
        f'{html.escape(k["nombre"])}{periodo}{prov}</div>'
        f'<div style="font-size:24px;line-height:1.2;font-weight:700;color:{AZUL};margin-top:5px;">'
        f'{html.escape(k["valor_texto"])}</div>'
        f'<div style="font-size:12px;line-height:1.4;color:{color};margin-top:3px;">'
        f'{flecha(k["tendencia"])} {html.escape(k["variacion_texto"])} '
        f'<span style="color:{GRIS};">vs. {html.escape(k["comparado_con"])}</span></div>'
        f'</td></tr></table></td>'
    )


def bloque_html(periodo, kpis, mercados, vut):
    for k in kpis:
        k["_mismo_periodo"] = k["periodo"] == periodo
    filas = []
    for i in range(0, len(kpis), 2):
        par = kpis[i:i + 2]
        celdas = "".join(tarjeta(k) for k in par)
        if len(par) == 1:
            celdas += '<td width="50%" style="padding:5px;"></td>'
        filas.append(f"<tr>{celdas}</tr>")
    for k in kpis:
        k.pop("_mismo_periodo", None)

    partes = [
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0">{"".join(filas)}</table>'
    ]
    if mercados and mercados["lista"]:
        tr = "".join(
            f'<tr><td style="padding:7px 10px;border-bottom:1px solid #E3E8EC;font:14px/1.4 {FUENTE};color:{AZUL};">'
            f'{n}. {html.escape(m["pais"])}</td>'
            f'<td align="right" style="padding:7px 10px;border-bottom:1px solid #E3E8EC;font:14px/1.4 {FUENTE};color:{AZUL};">'
            f'{m["texto"]}</td>'
            f'<td align="right" style="padding:7px 10px;border-bottom:1px solid #E3E8EC;font:13px/1.4 {FUENTE};'
            f'color:{TURQUESA if (m["variacion"] or 0) >= 0 else CORAL};">{m["variacion_texto"]}</td></tr>'
            for n, m in enumerate(mercados["lista"], 1)
        )
        partes.append(
            f'<div style="font:700 14px/1.4 {FUENTE};color:{AZUL};margin:18px 5px 6px;">'
            f'Principales mercados internacionales · {mercados["periodo_texto"]}</div>'
            f'<div style="font:12px/1.4 {FUENTE};color:{GRIS};margin:0 5px 6px;">'
            f'Pernoctaciones en hoteles y apartamentos y variación interanual</div>'
            f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
            f'style="border-collapse:collapse;margin:0 0 4px;">{tr}</table>'
        )
    if vut:
        partes.append(
            f'<div style="font:14px/1.55 {FUENTE};color:#24323F;margin:16px 5px 0;">'
            f'<strong style="color:{AZUL};">Viviendas turísticas:</strong> {vut["total_texto"]} inscritas en el '
            f'Registro de Turismo de Andalucía ({vut["plazas_texto"]} plazas); {vut["altas_12_meses_texto"]} altas '
            f'en los últimos doce meses.</div>'
        )
    partes.append(
        f'<div style="font:12px/1.5 {FUENTE};color:{GRIS};margin:14px 5px 0;">'
        f'Fuentes: INE (EOH, IRSH, EOAP), Turismo Costa del Sol, Junta de Andalucía y Eurostat. '
        f'Datos de {mes_texto(periodo)} salvo que se indique otro mes. '
        f'<a href="{OBSERVATORIO}" style="color:{TURQUESA};font-weight:600;">Ver el Observatorio Turístico</a></div>'
    )
    return "".join(partes)


def resumen_texto(periodo, kpis, mercados, vut):
    """Lo mismo en texto plano, para que la IA tenga contexto (no para copiarlo)."""
    lineas = [f"Último mes del INE para Marbella: {mes_texto(periodo)}."]
    for k in kpis:
        lineas.append(f"- {k['nombre']} ({k['periodo_texto']}): {k['valor_texto']} ({k['variacion_texto']} "
                      f"vs. {k['comparado_con']}){' [provisional]' if k['provisional'] else ''}")
    if mercados:
        lineas.append(f"Mercados internacionales ({mercados['periodo_texto']}): " + "; ".join(
            f"{m['pais']} {m['texto']} ({m['variacion_texto']})" for m in mercados["lista"]))
    if vut:
        lineas.append(f"Viviendas turísticas inscritas: {vut['total_texto']} ({vut['altas_12_meses_texto']} altas en 12 meses).")
    return "\n".join(lineas)


def main():
    try:  # la consola de Windows no es UTF-8 y el signo menos (−) la tumba
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:                                             # noqa: BLE001
        pass
    print("== Cifras del boletín de Turismo de Marbella ==")
    try:
        periodo, kpis = recoger_ine()
    except Exception as e:                                        # noqa: BLE001
        print(f"  [!] INE no responde ({e}). No se toca datos/kpis.json.")
        return 1
    extras = {}
    for nombre, f in (("aeropuerto", recoger_aeropuerto), ("mercados", recoger_mercados), ("vut", recoger_vut)):
        try:
            extras[nombre] = f()
            print(f"  [ok] {nombre}")
        except Exception as e:                                    # noqa: BLE001
            print(f"  [!] {nombre}: {e}")
            extras[nombre] = None
    if extras.get("aeropuerto"):
        kpis.append(extras["aeropuerto"])
    datos = {
        "generado": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "periodo": periodo, "periodo_texto": mes_texto(periodo),
        "indicadores": kpis,
        "mercados": extras.get("mercados"),
        "vut": extras.get("vut"),
        "observatorio": OBSERVATORIO,
    }
    datos["texto"] = resumen_texto(periodo, kpis, datos["mercados"], datos["vut"])
    datos["html"] = bloque_html(periodo, kpis, datos["mercados"], datos["vut"])
    os.makedirs(os.path.dirname(SALIDA), exist_ok=True)
    with open(SALIDA, "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False, indent=1)
    print(f"\nListo: {SALIDA} · periodo {periodo} · {len(kpis)} indicadores")
    print(datos["texto"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
