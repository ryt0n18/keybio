# Web de KeyBio

Página pública del proyecto: demo en el navegador (huella de tecleo y «adivina quién»),
explicación, descargas, valoraciones y contacto, en **nueve idiomas** (español, inglés, catalán,
gallego, euskera, francés, portugués, alemán e italiano). **Todavía no está publicada.**

```
i18n/                       textos de la web en cada idioma
  templates/                páginas con marcas {{clave}} en lugar de los textos
  es.json, en.json…         un catálogo por idioma: páginas, JavaScript y frases de la demo
  guides/                   guías (artículos) en español e inglés: es.json/en.json y una página por guía
  build.py                  genera public/ a partir de las plantillas, los catálogos y las guías
  social.py                 imágenes para redes sociales (public/assets/img/social/)
public/                     lo que se publica (HTML, CSS y JS sin dependencias)
  index.html                página principal (generada; el español en la raíz)
  privacidad.html           privacidad y aviso legal (generada)
  guias/, en/guides/        guías (generadas); son las únicas páginas que pueden llevar anuncios
  en/, ca/, gl/, eu/…       las mismas páginas en cada idioma (generadas)
  sitemap.xml, robots.txt   para los buscadores (generados; ads.txt también, si hay anuncios)
  _headers                  cabeceras de seguridad (Content-Security-Policy...)
  assets/js/keybio.js       algoritmo de la demo: traducción de ksb/features.py y ksb/matcher.py
  assets/js/demo.js         interfaz de la demo
  assets/js/site.js         tema, idioma, descargas, valoraciones y contacto
  assets/js/i18n.js         textos del JavaScript en el idioma de la página
  assets/js/config.js       configuración pública (claves públicas, descargas, responsable)
functions/api/ratings.js    API de valoraciones (Cloudflare Pages Functions + D1)
schema.sql                  tabla de valoraciones
wrangler.toml               configuración de Cloudflare
package.json                wrangler (herramienta de Cloudflare), con la versión fijada
tests/                      pruebas (Chrome sin ventana, sin Node)
```

## Vista previa y pruebas

```sh
python3 -m http.server -d web/public 8000     # http://localhost:8000
python3 web/tests/run.py                       # pruebas: algoritmo, valoraciones y demo de principio a fin
```

En la vista previa, las valoraciones y el contacto aparecen como «próximamente»: necesitan
el servidor de Cloudflare y las claves.

Las pruebas comparan la demo con el programa: `tests/fixture.json` contiene pulsaciones de
mecanógrafos simulados y lo que calcula Python con ellas. **Si cambias `ksb/features.py` o
`ksb/matcher.py`**, traslada el cambio a `keybio.js` y regenera la referencia:

```sh
.venv/bin/python web/tests/make_fixture.py && python3 web/tests/run.py
```

La integración continua regenera la referencia y pasa las pruebas en cada cambio, así que
avisa si la demo deja de calcular lo mismo que el programa.

La demo registra con **2 frases cortas** (`ENROLL_COUNT` en `texts.js`) y por eso usa un umbral
más estricto que el «normal» del programa (`SENSITIVITY` en `demo.js`, K = 0 en lugar de 2):
con 2 frases cada persona se calibra comparando una con la otra y el umbral sale holgado. En
las pruebas, con K = 2 se aceptaba a casi cualquier desconocido; K = 0 rechaza a la mayoría a
cambio de no reconocer, alguna vez, a quien sí está registrado (se vuelve a intentar). Si
cambias el número de frases, vuelve a simularlo antes.

## Idiomas

Las páginas de `public/` **no se editan a mano**: se generan con las plantillas de
`i18n/templates/` y los catálogos `i18n/<idioma>.json`. Para cambiar un texto:

```sh
# 1. edita la clave en i18n/es.json y en los demás catálogos
# 2. regenera las páginas
python3 web/i18n/build.py
```

- Cada catálogo tiene tres partes: `page` (textos de las páginas, pueden llevar HTML), `js`
  (textos que muestra el JavaScript; las variables `{nombre}` tienen que ser las mismas en todos
  los idiomas y los plurales van en `clave_one` / `clave_other`) y `texts` (6 frases de registro y
  4 de comprobación para la demo, de 100 a 170 caracteres).
- `build.py` se niega a generar si a un idioma le falta o le sobra una clave, y las pruebas
  (`tests/test_web.py`) fallan si las páginas no están al día.
- Para añadir un idioma: una línea en `LANGUAGES` de `build.py` y su catálogo.
- No hay redirección automática: si el navegador prefiere otro idioma disponible, aparece un
  aviso para cambiar, en ese idioma. La elección se recuerda en el navegador.
- `config.js` → `programLanguages` dice en qué idiomas está la interfaz del programa (se muestra
  en «Descargar»).

## Guías

Las guías son artículos sobre biometría del comportamiento y dinámica de tecleo para que la web
salga en los buscadores (ver `docs/promocion.md`). Solo existen en los idiomas que tienen
`i18n/guides/<idioma>.json`; ahí están los textos de alrededor (menú, índice, llamada a la demo)
y el orden en que aparecen. Cada guía es un fichero `i18n/guides/<idioma>/<dirección>.html` que
empieza con una cabecera:

```html
<!--
id: keystroke-dynamics          el mismo en todas las traducciones: las enlaza entre sí
slug: dinamica-de-tecleo         la dirección (/guias/dinamica-de-tecleo) y el nombre del fichero
title: …                         título para el buscador (unos 60 caracteres)
heading: …                       título de la página
description: …                   resumen para el buscador (unos 155 caracteres)
published: 2026-11-08
updated: 2026-11-08              cámbialo al revisar la guía (va al sitemap)
-->
<p class="lead">Entradilla…</p>
<h2 id="que-es">…</h2>            los <h2> con id forman el índice de la guía
```

Para añadir una: crea el fichero, añade su `id` a `order` en `i18n/guides/<idioma>.json` y
ejecuta `python3 web/i18n/build.py`. Las tablas van dentro de `<div class="table-wrap">`. Para
añadir guías a otro idioma: su `<idioma>.json` (con `folder`, la carpeta de su dirección), sus
guías y una regla para esa carpeta en `public/_headers` (las pruebas avisan si falta).

## Anuncios

Están preparados pero apagados: se activan poniendo el identificador de editor de AdSense en
`ADSENSE_CLIENT` (`i18n/build.py`). Entonces las guías cargan AdSense desde `site.js`, se genera
`ads.txt` y la política de privacidad añade el apartado de anuncios. La portada nunca los lleva:
ahí está la demo, y ningún código de terceros debe poder leer las pulsaciones. Las guías tienen por
eso su propia política de seguridad en `public/_headers`. Pasos completos en `docs/promocion.md`.

## Privacidad y seguridad

- **La demo no envía pulsaciones**: se procesan y guardan solo en el navegador
  (`localStorage`). La forma de teclear es un dato biométrico (art. 9 del RGPD); así la web
  no lo trata.
- **Valoraciones**: antispam con Turnstile, una al día por IP (la IP se guarda como HMAC con
  una sal secreta, nunca en claro), comprobación de origen, límites de tamaño, consultas con
  parámetros y comentarios que solo se publican tras aprobarlos. Se muestran siempre como
  texto, nunca como HTML.
- **Cabeceras**: `public/_headers` aplica una Content-Security-Policy estricta (solo scripts
  propios y de Turnstile, ningún estilo en línea), sin marcos externos, HSTS, etc.
- `config.js` es público: ahí solo van claves públicas (site key de Turnstile, access key de
  Web3Forms). Los secretos van en variables de Cloudflare.

## Probar con el servidor de Cloudflare en local

Sin cuenta ni conexión con Cloudflare: la base de datos es local (`.wrangler/`, fuera del
repositorio). Hace falta Node.js (en este equipo está en `~/.local/opt/node`).

```sh
export PATH=~/.local/opt/node/bin:$PATH
cd web
npm install                                    # instala wrangler (versión fijada en package.json)
npx wrangler d1 execute keybio --local --file=schema.sql
npm run dev                                    # http://localhost:8788 con la API de valoraciones
```

Crea antes `web/.dev.vars` (no se sube al repositorio) con las claves de prueba de Turnstile,
que siempre aceptan:

```
TURNSTILE_SECRET=1x0000000000000000000000000000000AA
IP_SALT=cualquier-cadena-de-prueba
```

Para probar también el formulario en local, pon temporalmente `turnstileSiteKey:
"1x00000000000000000000AA"` en `config.js`: la clave real solo funciona en `keybio.pages.dev`.

## Publicar en Cloudflare Pages (cuando se decida)

Hace falta una cuenta de Cloudflare y haber hecho `npx wrangler login`.

1. **Responsable**: en `public/assets/js/config.js`, rellena `owner` con tu nombre (aparece en
   el pie y en la política de privacidad). Revisa `privacidad.html`.
2. **Base de datos**:
   ```sh
   cd web
   npx wrangler login
   npx wrangler d1 create keybio          # copia el database_id en wrangler.toml
   npx wrangler d1 execute keybio --remote --file=schema.sql
   ```
3. **Proyecto y secretos**:
   ```sh
   npx wrangler pages project create keybio --production-branch main
   python3 -c "import secrets; print(secrets.token_hex(32))"   # valor para IP_SALT
   npx wrangler pages secret put IP_SALT --project-name keybio
   npx wrangler pages secret put TURNSTILE_SECRET --project-name keybio
   ```
4. **Turnstile** (panel de Cloudflare → Turnstile → añadir sitio con el dominio
   `keybio.pages.dev` o el tuyo): la *secret key* va en `TURNSTILE_SECRET` y la *site key* en
   `turnstileSiteKey` de `config.js`.
5. **Contacto**: crea una *access key* en web3forms.com con el correo donde quieras recibir
   los mensajes y ponla en `web3formsKey` de `config.js`.
6. **Publicar**: `npx wrangler pages deploy` (desde `web/`). La web queda en
   `https://keybio.pages.dev`. También se puede conectar el repositorio en el panel (directorio
   raíz `web`, salida `public`) para que se publique con cada push.
7. **Descargas**: cuando haya ejecutables públicos, ajusta `downloads` en `config.js`
   (`enabled: true`, la URL base y los nombres de los ficheros).

**Publicar en privado primero**: si se despliega solo como *preview* (`npx wrangler pages deploy
--branch privado`) y en el panel (Pages → keybio → Settings → General) se activa la política de
acceso de Cloudflare Access para las *previews*, la web queda en
`https://privado.keybio.pages.dev` y solo entra quien tú autorices (por ejemplo, tu correo).
Mientras no haya un despliegue en la rama de producción (`main`), `keybio.pages.dev` no muestra
nada.

## Moderar comentarios

Desde el panel de Cloudflare (D1 → keybio → Console) o con `wrangler`:

```sh
npx wrangler d1 execute keybio --remote --command "SELECT id, created, stars, name, comment FROM ratings WHERE status = 'pending'"
npx wrangler d1 execute keybio --remote --command "UPDATE ratings SET status = 'approved' WHERE id = 12"
npx wrangler d1 execute keybio --remote --command "UPDATE ratings SET status = 'rejected' WHERE id = 13"
```

Una valoración rechazada deja de contar en la media. Para atender una petición de borrado:
`DELETE FROM ratings WHERE id = …`.
