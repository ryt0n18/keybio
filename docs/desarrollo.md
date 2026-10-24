# Desarrollo

## Ejecutar desde el código

Requisitos: Python 3.10 o superior.

| Sistema | Arrancar | Crear el ejecutable |
|---|---|---|
| Linux | `./run.sh` | `tools/build.sh` → `dist/KeyBio/KeyBio` |
| Windows | `run.bat` | `tools\build.bat` → `dist\KeyBio\KeyBio.exe` |
| macOS | `./run.sh` | `tools/build.sh` → `dist/KeyBio.app` |

La primera vez se crea un entorno virtual `.venv` y se instalan las dependencias
(`PySide6-Essentials`, la parte de Qt for Python que usa KeyBio, y `cryptography`). A mano:

```sh
python -m venv .venv
.venv/bin/pip install -r requirements.txt       # Windows: .venv\Scripts\pip ...
.venv/bin/python main.py                        # Windows: .venv\Scripts\python main.py
```

## Ejecutables e instalador

**Instalador de Windows**: después de `tools\build.bat`, con [Inno Setup 6](https://jrsoftware.org/isinfo.php):

```bat
"C:\Program Files (x86)\Inno Setup 6\ISCC.exe" /DAppVersion=2.1.0 tools\keybio.iss
```

- La integración continua genera el instalador `KeyBio-x.y.z-setup.exe`, el `.zip` portable de
  Windows, el `.deb` y el `.tar.gz` de Linux y el `.dmg` de macOS (Apple Silicon). Cómo se
  publica una versión: [`publicar.md`](publicar.md).
- **Linux**: en Linux, `tools/build.py` añade a `dist/KeyBio` el instalador por usuario
  `instalar.sh` (en `~/.local/opt/keybio`, sin permisos de administrador), la entrada del menú y
  los iconos; `python tools/linux.py deb` crea el `.deb` (en `/opt/keybio`, con la ficha AppStream
  para las tiendas de aplicaciones). La CI instala los dos y comprueba que KeyBio sale en el menú
  y arranca. El identificador `io.github.ryt0n18.keybio` está en `tools/linux.py`,
  `tools/linux/instalar.sh` y `ksb/gui/app.py`: no se cambia, o las entradas instaladas se rompen.
- **macOS** (en pruebas): el `.app` no está firmado ni notarizado por Apple, así que la primera
  vez hay que abrirlo con clic derecho → Abrir (o en Ajustes del Sistema → Privacidad y
  seguridad → «Abrir igualmente»). Falta probarlo en un Mac real.
- Los ejecutables incluyen las licencias de terceros (carpeta `licenses`, que completa
  `tools/notices.py`). Qt for Python y Qt se distribuyen bajo la LGPL-3.0; `tools/keybio.spec`
  deja fuera las partes de Qt que el programa no usa, entre ellas Qt Virtual Keyboard, que es GPL.

## Estructura del proyecto

```
main.py                 punto de entrada (python main.py, o --acceso para la verificación de acceso)
run.sh, run.bat         arrancar desde el código
ksb/                    el programa
  capture.py            grabación de pulsaciones (independiente de la interfaz)
  features.py           extracción de características
  matcher.py            medidas R/A, distancia estadística, umbral de cada persona e identificación
  evaluation.py         evaluación cruzada y calibración automática
  liveness.py           detección de suplantaciones
  service.py            lógica de aplicación: perfiles, sesiones, adaptación, historial, accesos, panel
  storage.py            almacenamiento JSON, cifrado, exportación e importación
  crypto.py             cifrado con contraseña
  texts.py              textos para escribir (registro, comprobación y frases de acceso)
  texts_langs.py        los mismos textos en los demás idiomas
  i18n.py               traducción de la interfaz; catálogos en ksb/locale/<idioma>.json
  traits.py             rasgos normalizados para la huella de tecleo
  textutil.py, logutil.py
  gui/                  interfaz Qt (PySide6): ventana, pantallas, gráficos, teclado, informes PDF
    access.py           ventana de verificación de acceso (--acceso)
tests/                  pruebas, mecanógrafos simulados y bancos de prueba
tools/                  empaquetado: build.py, build.sh, build.bat, keybio.spec (PyInstaller),
                        keybio.iss (instalador de Windows), linux.py y linux/instalar.sh (menú de
                        aplicaciones y .deb), notices.py (licencias de terceros) e i18n.py
                        (comprobar las traducciones)
licenses/               licencias de terceros que acompañan a los ejecutables
web/                    web pública con la demo en el navegador (ver web/README.md)
docs/                   documentación
.github/                integración continua, plantillas de issues, Dependabot, CONTRIBUTING y SECURITY
```

## Pruebas

```sh
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m pyflakes ksb tests tools main.py web/i18n   # lint
.venv/bin/python -m pytest tests                      # núcleo + interfaz (Qt en modo offscreen)
.venv/bin/python -m tests.evaluate 20 30              # 20 usuarios y 30 desconocidos sintéticos
.venv/bin/python -m tests.separation 0.5 0.1          # banco de prueba con personas parecidas entre sí
python3 web/tests/run.py                              # web: demo, paridad con Python y valoraciones (Chrome)
```

- Los cambios en el modelo (`ksb/features.py`, `ksb/matcher.py`) se comprueban con datos reales
  además de con los mecanógrafos simulados, y se trasladan a la demo web
  (`web/public/assets/js/keybio.js`; ver [`web/README.md`](../web/README.md)).
- Un cambio que altere la longitud de las muestras necesita umbrales que la tengan en cuenta:
  con menos texto, la distancia de una persona a su propio perfil crece.
- La versión se cambia solo en `ksb/__init__.py`; `tests/test_release.py` comprueba que el
  instalador, esta guía, la web y el CHANGELOG coinciden.

## Traducciones

El texto original, en español, es la clave: se marca en el código con `_()` (o `_n()` si
depende de un número, y `N_()` si se define al importar el módulo) y cada idioma lo traduce en
`ksb/locale/<idioma>.json`.

```sh
.venv/bin/python tools/i18n.py sync    # añade a los catálogos los textos nuevos y quita los que sobran
.venv/bin/python tools/i18n.py check   # falla si falta alguno o si cambian sus {variables}
.venv/bin/python tools/i18n.py stats   # cuántos hay traducidos en cada idioma
KEYBIO_LANGUAGE=fr ./run.sh            # probar el programa en un idioma
```

- Un texto que no está en el catálogo sale en español, así que el programa nunca se rompe por
  una traducción pendiente; `tests/test_i18n.py` (y la CI) sí fallan.
- Para añadir un idioma: su código y nombre en `LANGUAGES` y su teclado en `KEYBOARDS`
  (`ksb/i18n.py`), el catálogo, los textos para escribir en `ksb/texts_langs.py` y el idioma
  del instalador en `tools/keybio.iss`. La web tiene sus propios catálogos (`web/i18n`).
- Las pruebas usan siempre el español (`tests/conftest.py`), sea cual sea el idioma del sistema.

## Integración continua

`.github/workflows/ci.yml` ejecuta el lint y las pruebas en Ubuntu y Windows con Python 3.11 y
3.13, las pruebas de la web en Chrome, empaqueta la aplicación, comprueba que el `.exe` arranca
y genera el instalador. macOS (pruebas, `.app` y `.dmg`) solo se ejecuta al subir una etiqueta
o al lanzarlo a mano, porque sus minutos cuestan diez veces más en un repositorio privado. Al
subir una etiqueta `vX.Y.Z` se crea un **borrador** de la versión con los ejecutables,
`SHA256SUMS.txt` y las notas del CHANGELOG.
