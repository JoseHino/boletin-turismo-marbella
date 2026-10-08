# Boletín profesional · Turismo de Marbella

Boletín mensual para empresas y profesionales del turismo de Marbella (idea de
[Visita Gijón Profesional](https://gijonturismoprofesional.es/es/newsletter)).
Lo redacta una IA con los datos del Observatorio Turístico y las noticias del
mes, lo aprueba por correo la directora general de Turismo y, con su OK, se
publica en esta web y se envía a los suscritos con Brevo.

Web: https://josehino.github.io/boletin-turismo-marbella/
(`?embed=1` la deja sin cabecera ni pie para meterla en la web de Turismo
con un iframe; la página avisa de su altura con `postMessage({boletinAltura})`).

## Cómo funciona

```
GitHub Actions (cada día)          Make (un único escenario, buzón de correo)
  scripts/noticias.py  ─┐
  scripts/kpis.py      ─┼─> datos/*.json ─> «GENERAR» ─> borrador v1 ─> Gmail ─> directora
                        │                                     ▲                  │
                        │                         correcciones │  responde OK o   │
                        │                         (nueva versión)  correcciones   │
                        │                                     └──── IA ◄──────────┘
                        │                                            │ OK
numeros/index.json <────┴── indice.yml <── numeros/AAAA-MM.html <────┤
                                                    Brevo: campaña ◄─┘ a los suscritos
```

| Pieza | Qué hace |
|---|---|
| `scripts/kpis.py` → `datos/kpis.json` | Último mes del INE (EOH, IRSH, EOAP), mercados (Turismo Costa del Sol), VUT (RTA) y aeropuerto (Eurostat), con la variación interanual. Incluye el bloque `html` ya maquetado: **la IA no escribe ninguna cifra**. |
| `scripts/noticias.py` → `datos/noticias.json` | Acumula a diario (ventana de 40 días) las noticias del Ayuntamiento (con su delegación), la prensa especializada, Diario Sur, Google Noticias y el BOJA de turismo. Los RSS solo guardan unos días, por eso se acumula. |
| `plantilla/boletin.html` | Diseño del correo (tablas y estilos en línea). Make rellena los `%%MARCADORES%%`. Colores y textos del pie se cambian aquí. |
| `index.html` | Portada: archivo de números y suscripción (formulario de Brevo). |
| `scripts/indice.py` | Rehace `numeros/index.json` cuando Make sube un número. |
| `make/escenario.json` | Copia del escenario de Make, para importarlo en otra cuenta. |

Actions: `noticias.yml` (cada día, 05:15 UTC), `cifras.yml` (día 9; si se
configuran `MAILHOOK`, `REMITENTE` y el secreto `BREVO_API_KEY`, pide además el
borrador a Make) e `indice.yml` (al publicar un número).

## El circuito de aprobación

1. Llega un correo con «GENERAR» en el asunto al buzón de Make (lo manda la
   Action el día 9 o cualquier editor autorizado; el cuerpo del correo sirve
   para dar indicaciones: «incluid la feria X», «el tema del mes es…»).
2. Make lee cifras y noticias, la IA redacta, y la directora recibe el
   borrador «Nº AAAA-MM · v1» con un recuadro de instrucciones. Su respuesta va
   directa al buzón de Make (cabecera Reply-To).
3. La IA clasifica la respuesta:
   - **OK sin cambios** y sobre la última versión → se publica y se envía.
   - **Correcciones** (aunque diga OK) → se aplican y le llega la versión siguiente.
   - **Ambigua**, de otra persona o sobre una versión antigua → no se publica
     nada y se avisa al equipo técnico.
