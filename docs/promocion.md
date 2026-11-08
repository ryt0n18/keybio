# Promoción, anuncios y seguimiento

Objetivo: que la web salga en Google cuando alguien busque información sobre biometría del
comportamiento o dinámica de tecleo, sacar algo con anuncios en las guías y verlo todo desde un
mismo sitio. Sin pagar publicidad.

- [Qué está hecho en la web](#qué-está-hecho-en-la-web)
- [1. Google Search Console](#1-google-search-console)
- [2. Bing Webmaster Tools](#2-bing-webmaster-tools)
- [3. Dominio propio](#3-dominio-propio)
- [4. Anuncios con AdSense](#4-anuncios-con-adsense)
- [5. Verlo todo en un sitio: Looker Studio](#5-verlo-todo-en-un-sitio-looker-studio)
- [6. Conseguir enlaces y visitas](#6-conseguir-enlaces-y-visitas)
- [7. Seguir escribiendo guías](#7-seguir-escribiendo-guías)
- [Qué esperar](#qué-esperar)

## Qué está hecho en la web

- [x] **Guías** en español (`/guias/`) e inglés (`/en/guides/`): dinámica de tecleo, biometría del
      comportamiento y algoritmos. Enlazadas desde la portada (menú y sección «Guías») y entre sí,
      cada una con su traducción (hreflang). Se escriben en `web/i18n/guides/` (ver `web/README.md`).
- [x] **Títulos de la portada** con las palabras que se buscan («Dinámica de tecleo», «Keystroke
      dynamics»…) en los nueve idiomas.
- [x] **Para los buscadores**: dirección canónica en cada página, `sitemap.xml`, `robots.txt` y
      datos estructurados (programa, artículos y migas de pan), generados por `web/i18n/build.py`.
- [x] **Imagen al compartir** en redes y mensajería (`web/i18n/social.py`), una por idioma.
- [x] **Anuncios preparados, pero apagados**: con `ADSENSE_CLIENT` en `web/i18n/build.py`, las guías
      cargan AdSense, se genera `ads.txt` y la política de privacidad añade el apartado de anuncios en
      los nueve idiomas. **La portada nunca lleva anuncios**: ahí se teclea en la demo y ningún código
      de terceros debe poder leer esas pulsaciones (son datos biométricos). Por eso las guías tienen
      su propia política de seguridad en `web/public/_headers` y la portada mantiene la estricta.
      `tests/test_web.py` comprueba las dos cosas.

Tras cualquier cambio: `python web/i18n/build.py`, commit, subida y despliegue
(`npx wrangler pages deploy` desde `web/`).

## 1. Google Search Console

Es gratis y es lo primero: le dice a Google que la web existe y muestra con qué búsquedas sale,
en qué posición y cuántos clics recibe.

1. Entra en [search.google.com/search-console](https://search.google.com/search-console) con tu
   cuenta de Google → *Añadir propiedad* → **Prefijo de la URL** → `https://keybio.pages.dev/`.
   (La opción «Dominio» no sirve con `pages.dev`: pide tocar unos DNS que no son tuyos).
2. Método **Etiqueta HTML**: copia solo el valor de `content="…"` y ponlo en
   `GOOGLE_SITE_VERIFICATION` de `web/i18n/build.py`. Regenera, despliega y pulsa *Verificar*.
3. *Sitemaps* → envía `sitemap.xml`.
4. *Inspección de URLs* → pega la portada y cada guía → *Solicitar indexación*. Acelera la primera
   vez; después Google las encuentra solo con el sitemap.

Qué mirar cada semana: *Rendimiento* → *Consultas* (qué busca la gente para llegar), *Páginas* y la
posición media. Una búsqueda con muchas impresiones y pocos clics es una pista: mejora el título y
la descripción de esa página o escribe una guía sobre ella.

## 2. Bing Webmaster Tools

Bing también alimenta DuckDuckGo, Ecosia, Yahoo y las búsquedas de Copilot y ChatGPT.

1. [bing.com/webmasters](https://www.bing.com/webmasters) → **Importar desde Google Search
   Console** (copia el sitio y el sitemap de un clic).

## 3. Dominio propio

**Hace falta para AdSense.** AdSense comprueba `ads.txt` en la raíz del dominio y con una dirección
de `pages.dev` (que es de Cloudflare) la aprobación no es fiable. Para el posicionamiento ayuda
algo, pero no es imprescindible.

- `keybio.app` estaba libre (24-10-2026). En Cloudflare cuesta lo mismo que al registrador, unos
  12–15 € al año. Los pasos están en [publicar.md → Dominio propio](publicar.md#dominio-propio).
- Al cambiar `SITE_URL` en `web/i18n/build.py` se actualizan solos los enlaces canónicos, el
  sitemap, `robots.txt` y los datos estructurados. Cambia también `analytics.host` en
  `web/public/assets/js/config.js` (las pruebas lo exigen).
- En Search Console: añade la propiedad nueva, verifícala y usa *Configuración* → **Cambio de
  dirección** desde `keybio.pages.dev`. Con la redirección 301 de `publicar.md`, Google pasa la
  posición a la dirección nueva.

## 4. Anuncios con AdSense

1. **Alta** en [adsense.google.com](https://adsense.google.com) con tu cuenta de Google: datos de
   pago (titular, dirección) y el sitio (`keybio.app`).
2. **Conectar el sitio**: copia tu identificador de editor (`ca-pub-…`, en *Cuenta* → *Información
   de la cuenta*) en `ADSENSE_CLIENT` de `web/i18n/build.py`. Regenera y despliega: así se publican
   la etiqueta `google-adsense-account`, `ads.txt` y los anuncios en las guías. En AdSense elige
   el método «Metaetiqueta» y pulsa *Verificar*, luego *Solicitar revisión*.
3. **Revisión**: tarda de unos días a unas semanas. Si la rechazan por «contenido de poco valor»,
   escribe más guías y vuelve a pedirla.
4. **Aviso de cookies (obligatorio en Europa)**: *Privacidad y mensajes* → *Normativas europeas* →
   crear mensaje con los botones *Consentir*, *No consentir* y *Gestionar opciones*, y publicarlo para
   el sitio. Es la plataforma de consentimiento de Google, gratuita y certificada; no hay que poner
   ningún código más. Solo aparece en las guías, que es donde se carga AdSense.
5. **Anuncios automáticos**: *Anuncios* → *Por sitio* → activar. Para no estropear la lectura,
   densidad baja y sin anuncios de pantalla completa (*viñeta*) si molestan.
6. **Privacidad**: al activar los anuncios, la política añade sola el apartado y el proveedor.
   Cambia la fecha de «Última actualización» (`privacy.updatedDate` en los catálogos y `datetime`
   en `web/i18n/templates/privacidad.html`).
7. **Cobrar**: al llegar a 10 € te envían por correo postal un PIN para confirmar la dirección y
   hacen un pequeño depósito de prueba en tu cuenta para confirmarla. El pago llega cada mes en que
   el saldo supera **70 €**; si no, se acumula. Lo que se cobra hay que declararlo en la renta.

## 5. Verlo todo en un sitio: Looker Studio

[Looker Studio](https://lookerstudio.google.com) es gratis y junta Search Console y AdSense en un
único panel que se actualiza solo.

1. *Crear* → *Informe* → fuente **Search Console** → el sitio → *Impresiones de URL* (trae las
   búsquedas y las páginas).
2. *Añadir datos* → fuente **AdSense** → tu cuenta.
3. Gráficos que merecen la pena:
   - Serie temporal: clics, impresiones y posición media (Search Console).
   - Tabla de **consultas** con clics, impresiones, CTR y posición: qué busca la gente.
   - Tabla de **páginas de destino**: qué guías funcionan.
   - Serie temporal: **ganancias estimadas**, páginas vistas y RPM (AdSense).
4. *Compartir* → **Programar envío por correo**: un resumen semanal en PDF a tu correo.

El total de visitas (incluidas las que no vienen de Google) sigue en Cloudflare → *Web Analytics*,
que no tiene conector con Looker Studio.

## 6. Conseguir enlaces y visitas

Google posiciona mejor lo que otros enlazan. Por orden de lo que más rinde para el esfuerzo:

- [ ] **Lista «awesome-keystroke-dynamics» en GitHub.** No existe ninguna lista de recursos sobre
      dinámica de tecleo. Crearla (conjuntos de datos, artículos, librerías, programas, con KeyBio
      entre ellos) atrae estrellas, enlaces y visitas de quien investiga el tema.
- [ ] **DOI en Zenodo** (integración con GitHub, *Settings* → *GitHub* en zenodo.org): cada versión
      queda archivada con un DOI que se puede citar, y Zenodo aparece en Google Académico.
- [ ] **Webs de descargas**: Softonic, Uptodown y Malavida (mucho tráfico en España),
      [AlternativeTo](https://alternativeto.net) (como alternativa a TypingDNA y similares) y
      SourceForge (puede reflejar las versiones de GitHub).
- [ ] **Comunidades** (con un texto propio para cada una, diciendo que eres el autor y sin repetirlo):
      Menéame, Reddit (r/Python en *showcase*, r/privacy, r/linux, r/software), *Show HN* en Hacker
      News, Product Hunt y una publicación en LinkedIn.
- [ ] **Un artículo en inglés** en dev.to o Medium que resuma la guía de algoritmos y enlace a ella
      (con la dirección canónica apuntando a la guía, para que no compita con ella).
- [ ] **Docentes**: la demo sirve como material de clase en asignaturas de biometría y seguridad.
      Un correo breve a profesores de esas asignaturas puede traer enlaces desde webs de universidad.
- [ ] **Responder preguntas** sobre el tema (Reddit, Quora, Stack Exchange) enlazando a la guía
      cuando aporte de verdad.
- **Wikipedia, no**: añadir enlaces al proyecto propio es conflicto de intereses y los quitan.

## 7. Seguir escribiendo guías

Lo que más hace subir en Google es tener **más páginas útiles sobre el tema**. Una guía nueva al
mes es un buen ritmo. Ideas con búsquedas reales:

- FAR, FRR y EER explicados con ejemplos.
- Conjuntos de datos de dinámica de tecleo (*keystroke dynamics dataset*).
- Dinámica del ratón.
- Autenticación continua.
- Biometría en el trabajo: qué permite el RGPD.
- Dinámica de tecleo con Python (*keystroke dynamics python*).

Cómo añadir una: `web/README.md` → «Guías». Mira antes en Search Console qué consultas ya te dan
impresiones: son las guías que más pronto subirán.

## Qué esperar

- **Indexación**: de unos días a dos semanas después de enviar el sitemap.
- **Posición**: en español hay poca competencia (blogs de empresas y algunas tesis), así que las
  guías pueden llegar a la primera página de búsquedas concretas como «dinámica de tecleo» en uno a
  tres meses. En inglés hay mucha más competencia y tardará más.
- **Ingresos**: en temas técnicos en español, AdSense suele pagar del orden de 1 a 3 € por cada
  1.000 páginas vistas. Con 1.000 visitas al mes a las guías serían 1–3 € al mes, así que llegar al
  primer pago de 70 € puede llevar más de un año. Las donaciones (GitHub Sponsors, Ko‑fi) no
  necesitan dominio ni aviso de cookies y, en proyectos de nicho, a menudo dan más que los anuncios.
