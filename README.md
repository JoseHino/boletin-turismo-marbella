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

## Make

Un único escenario («Boletín Turismo Marbella») con un buzón de correo
(mailhook) como disparador: así ocupa un solo hueco de escenario activo y solo
gasta operaciones cuando llega un correo (≈16 por borrador, ≈10 por respuesta).

- **Módulo 2, CONFIGURACIÓN**: `modo` (`prueba` sube los números como
  `AAAA-MM-prueba-….html`, que la portada oculta, y avisa en el pie), `directora`,
  `editores` (quién puede pedir GENERAR), `avisos` (equipo técnico), `buzon`,
  `web`, `repo`, `remitente`, `remitente_nombre` y `lista_brevo`.
- **Almacén de datos** «Boletín Turismo Marbella»: un registro por número con la
  versión, el estado (`pendiente` / `publicado`), el Markdown, el HTML y el historial.
- **Conexiones**: OpenAI (modelo `gpt-5.6-terra`), Gmail (envía los borradores;
  con Gmail personal hay que reautorizar cada 6 meses), Brevo y una clave de
  GitHub (token de grano fino con *Contents: read and write* solo en este
  repositorio, guardada como «API Key Auth»: clave `Bearer <token>`, cabecera
  `Authorization`).
- Lecciones: en las fórmulas de Make las expresiones regulares van **entre
  comillas** (`"/<h2/g"`); sin comillas no hacen nada y no dan error. El
  procesamiento secuencial está desactivado a propósito: con él, un fallo
  dejaba el escenario en espera hasta borrar la ejecución incompleta.

### Probarlo

1. Manda un correo al buzón con el asunto `[Boletín Turismo Marbella] GENERAR 2026-10`
   (el cuerpo son las notas para la IA).
2. Llega el borrador a la dirección de `directora`. Responde con correcciones
   y después con «OK».
3. La dirección de `directora` debe ser un buzón distinto del Gmail que envía:
   Gmail, al responder a un correo propio, contesta a los destinatarios y no
   al Reply-To.

## Pasar a la cuenta de Make de Turismo

1. La Delegación abre su cuenta de Make (zona UE) e invita como administrador
   a quien lo mantenga.
2. Importar el escenario (Make → Escenarios → Importar blueprint) y crear:
   buzón nuevo, almacén de datos con la misma estructura y las conexiones.
3. Cambiar el módulo 2: `modo` = `produccion`, correo real de la directora,
   buzón nuevo, remitente @marbella.es y lista real de Brevo.
4. Brevo de la Delegación: verificar el remitente y pedir a Informática los
   registros DNS de Brevo (DKIM y código de verificación). marbella.es tiene
   DMARC `p=quarantine` con alineación estricta: sin ellos, los envíos
   acabarían en spam.
5. Formulario de suscripción de Brevo con doble confirmación → su enlace en
   `BREVO_FORM` de `index.html`; la página de privacidad del Ayuntamiento en
   `PRIVACIDAD`. Que lo revise el Delegado de Protección de Datos (alta de la
   actividad de tratamiento).
6. GitHub: variables `MAILHOOK` y `REMITENTE` y secreto `BREVO_API_KEY` en el
   repositorio para que la Action del día 9 pida el borrador sola.
