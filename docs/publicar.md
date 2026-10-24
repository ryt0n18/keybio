# Publicar KeyBio

Estado de la preparación y pasos para hacer público el programa (repositorio, ejecutables y
web). **Hasta el día de la publicación todo sigue en privado**: el repositorio es privado, la
versión está en borrador y la web no está desplegada.

## Cómo se prepara una versión

1. Cambia la versión en `ksb/__init__.py` y añade su sección al principio de `CHANGELOG.md`.
   `tests/test_release.py` falla si el instalador (`tools/keybio.iss`), `docs/desarrollo.md` o
   `web/public/assets/js/config.js` no coinciden.
2. Sube los cambios a `main` y crea la etiqueta: `git tag -a vX.Y.Z -m "KeyBio X.Y.Z" && git push
   origin main vX.Y.Z`.
3. La CI pasa las pruebas (Linux, Windows, macOS y web), crea los ejecutables y deja un
   **borrador** de la versión con los ficheros, `SHA256SUMS.txt` y las notas del CHANGELOG.
   Comprueba que la etiqueta coincide con la versión del programa.
4. Prueba los ejecutables del borrador. Si algo falla: corrige, borra el borrador y la etiqueta
   (`gh release delete vX.Y.Z --cleanup-tag`) y vuelve al paso 2.
5. Publica el borrador: `gh release edit vX.Y.Z --draft=false` (solo cuando el repositorio ya sea
   público; ver abajo).

Los nombres de los ficheros que espera la web están en `config.js` y los comprueba
`tests/test_release.py`: `KeyBio-X.Y.Z-setup.exe`, `KeyBio-windows-x64.zip`,
`KeyBio-linux-x64.tar.gz` y `KeyBio-X.Y.Z-macos-arm64.dmg`.

## Versión 2.1.0

- [x] Versión 2.1.0 en el programa, el instalador, la documentación, la web y el CHANGELOG.
- [x] Etiqueta `v2.1.0` y borrador de la versión con los cuatro ejecutables y `SHA256SUMS.txt`
      (CI correcta en Linux, Windows y macOS, el 24 de octubre de 2026).
- [ ] Probar el borrador: instalador y portable en Windows, `.tar.gz` en Linux, `.dmg` en un Mac.
- [ ] Probar la verificación de acceso con el ejecutable de Windows: que `KeyBio.exe --acceso
      "Nombre"` devuelva el código de salida (`Start-Process -Wait -PassThru` en PowerShell).

## Repositorio

- [x] Historial revisado: sin secretos ni claves privadas, sin perfiles, muestras reales,
      `history.jsonl` ni copias de seguridad. Las claves de `config.js` son públicas por diseño.
- [x] Raíz ordenada: documentación en `docs/` (con capturas en `docs/img/`), empaquetado en
      `tools/`, `CONTRIBUTING.md` y `SECURITY.md` en `.github/`.
- [x] README con capturas, descargas, funciones por bloques y enlaces a `docs/`; plantillas de
      *issues* (avisan de no adjuntar datos biométricos) y Dependabot.
- [x] La CI publica las versiones como borrador, con sumas SHA-256 y notas del CHANGELOG.
- [x] Repositorio rehecho el 24-10-2026 con un único commit («KeyBio 2.1.0»): sin el correo
      personal, sin enlaces a sesiones y sin cifras de pruebas con personas reales. El historial
      completo sigue en local (rama `historial-completo`) y en `ryt0n18/keybio-antiguo` (privado;
      se puede borrar desde *Settings → Delete this repository*). Los commits nuevos usan el correo
      privado de GitHub (`git config user.email`).

## Día de la publicación (en este orden)

1. Revisa la lista de «Legal» de abajo.
2. Repositorio público: `gh repo edit ryt0n18/keybio --visibility public
   --accept-visibility-change-consequences`.
3. En GitHub → *Settings*:
   - *Code security*: activar *Private vulnerability reporting* (lo usa `.github/SECURITY.md`),
     *Dependabot alerts* y *Secret scanning*.
   - *Rules*: regla para `main` (sin borrar ni forzar subidas; que pase la CI). En un
     repositorio privado gratuito no está disponible, por eso se hace ahora.
   - *General*: web del proyecto (`https://keybio.pages.dev` o el dominio propio) y temas.
4. Publica la versión: `gh release edit v2.1.0 --draft=false`, y comprueba que
   `https://github.com/ryt0n18/keybio/releases/download/v2.1.0/KeyBio-linux-x64.tar.gz`
   descarga sin iniciar sesión.
5. Activa las descargas en la web: `downloads.enabled: true` en `config.js`, commit y subida.
6. Despliega la web (ver «Web») y borra los despliegues de prueba (`vista-previa.keybio.pages.dev`
   y los de dirección aleatoria) en Cloudflare → *Workers & Pages → keybio → Deployments*, para
   que solo quede `keybio.pages.dev`.
7. Borra las valoraciones de prueba (las de la vista previa van a la misma base de datos):
   `npx wrangler d1 execute keybio --remote --command "DELETE FROM ratings"` desde `web/`.

## Web (`web/`)

- [x] Demo en el navegador, explicación, descargas, valoraciones, contacto y privacidad.
- [x] Pruebas en Chrome sin ventana (paridad con Python, valoraciones, demo completa) y en la CI.
- [x] Cabeceras de seguridad (CSP estricta) comprobadas con la demo funcionando.
- [x] API de valoraciones probada con el servidor de Cloudflare en local (D1 real, Turnstile de prueba).
- [x] Responsable en `config.js`: Álvaro Ruiz (ryt0n18).
- [x] Sesión de Cloudflare; base de datos D1 `keybio` en la jurisdicción de la UE con el esquema;
      proyecto de Pages `keybio` (sin despliegues); widget de Turnstile y secretos `IP_SALT` y
      `TURNSTILE_SECRET` en producción y en vista previa.
- [x] Clave de Web3Forms para el contacto (en `config.js`). Se creó con el dominio «localhost»:
      al publicar, cámbialo por `keybio.pages.dev` en el panel de Web3Forms si los mensajes no llegan.
- [x] Descargas apuntando a la versión 2.1.0 (desactivadas hasta que la versión sea pública: con el
      repositorio privado los enlaces darían error).
- [x] Nueve idiomas, generados desde `web/i18n` (ver `web/README.md`).
- [ ] Que una persona nativa revise las traducciones, sobre todo el euskera y las páginas de
      privacidad (son textos legales; la española es la que vale).
- [ ] Al publicar con otro dominio, cambiar `SITE_URL` en `web/i18n/build.py` (enlaces para los
      buscadores) y regenerar.
- [ ] Desplegar primero en privado (vista previa protegida con Cloudflare Access) y revisarla.
- [x] Dirección: `keybio.pages.dev`, sin dominio propio (decidido el 24-10-2026; keybio.com es de un
      laboratorio francés). Si más adelante se quiere uno, ver «Dominio propio».
- [x] Dirección limpia: los enlaces internos no añaden `#…`, las páginas se sirven sin `.html`
      y los buscadores reciben esa forma (`SITE_URL` en `web/i18n/build.py`).

## Dominio propio

`keybio.com` y `keybio.net` están ocupados (comprobado el 24-10-2026); `keybio.app`, `keybio.dev`,
`keybio.org`, `keybio.eu` y `keybio.io` estaban libres. Pasos con el dominio elegido (aquí, `keybio.app`):

1. Comprarlo en Cloudflare (*Domain Registration → Register Domains*): misma cuenta que la web,
   precio de coste y renovación automática. Cloudflare no vende `.es`: habría que comprarlo en otro
   registrador y pasar sus DNS a Cloudflare.
2. *Workers & Pages → keybio → Custom domains*: añadir `keybio.app` (y `www.keybio.app`). Cloudflare
   crea los DNS y el certificado.
3. `SITE_URL = "https://keybio.app"` en `web/i18n/build.py`, regenerar las páginas
   (`python web/i18n/build.py`), commit y desplegar. El `.deb` también la toma de ahí.
4. Turnstile (*Turnstile → KeyBio web → Hostnames*): añadir `keybio.app`. Web3Forms: el dominio.
5. **Una sola dirección**: *Rules → Bulk Redirects* (o una regla de redirección) de
   `keybio.pages.dev` y `www.keybio.app` a `https://keybio.app`, con código 301 y conservando la
   ruta. Así quien entre por la dirección vieja acaba en la nueva y los buscadores solo ven una.
6. Borrar los despliegues de prueba (`vista-previa.keybio.pages.dev`) en *Deployments*.

## Programa

- [x] Umbrales corregidos con datos reales (perfiles pequeños y muestras de otro día).
- [x] Revisión de seguridad: importación validada y con límite de tamaño, nombres como texto
      llano, CSV sin fórmulas, permisos privados en Linux/macOS, keystore manipulado.
- [x] Licencias de terceros dentro de los ejecutables; fuera Qt Virtual Keyboard (GPL).
- [x] Casilla de permiso al registrar a una persona.
- [x] Verificación de acceso al iniciar sesión: solo la puntuación, avisos locales al administrador.
- [x] Programa en nueve idiomas, con textos para escribir y teclado de cada uno (`tools/i18n.py check`).
- [x] Linux: `.deb` y `instalar.sh` que añaden KeyBio al menú de aplicaciones (comprobado en la CI).
- [ ] Probar el `.deb` con doble clic en un Ubuntu con escritorio y buscar «KeyBio» en el menú.
- [ ] Que personas nativas revisen las traducciones del programa (sobre todo euskera y gallego) y
      prueben los textos para escribir en su idioma.
- [ ] (Opcional, de pago) Firma de código para Windows, para evitar el aviso de SmartScreen.

## macOS

- [x] Captura de teclas con el código de tecla virtual (antes todas las teclas parecían la misma).
- [x] Carpeta de datos, `.app` con icono, `.dmg` y trabajo de CI (solo al etiquetar o a mano).
- [ ] **Probarlo en un Mac real**: registrar a alguien, escribir con mayúsculas (shift izquierdo
      y derecho), tildes con tecla muerta y Cmd+V (no debe escribir nada), e identificar.
- [ ] (Opcional, 99 $/año) Cuenta de desarrollador de Apple para firmar y notarizar la app.

## Legal

- [x] `LICENSE` (todos los derechos reservados, con la salvedad de la LGPL para Qt), dentro de
      los ejecutables y como licencia del instalador de Windows; titular en el programa, el
      `.app` de macOS, el instalador y la web.
- [ ] Revisar `web/public/privacidad.html` (es un punto de partida, no asesoramiento legal).
- [x] La web ya no cita resultados con las muestras de otras personas: da los de la prueba con
      personas simuladas (`python -m tests.evaluate 20 30`, sensibilidad «normal»).
- [ ] La verificación de acceso con trabajadores necesita base jurídica, evaluación de impacto,
      información previa e informe de la representación de los trabajadores (`docs/verificacion-acceso.md`
      → «Antes de usarla con trabajadores»). Revisarlo con alguien de protección de datos antes de
      anunciarla para empresas.
