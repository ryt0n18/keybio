# Contribuir

Gracias por el interés. KeyBio se publica con **todos los derechos reservados** (ver
[`LICENSE`](../LICENSE)), así que por ahora:

- **Sí**: avisos de errores y propuestas en las *issues* (hay plantillas), y fallos de seguridad
  por la vía privada de [`SECURITY.md`](SECURITY.md).
- **No por ahora**: *pull requests* con código. Si quieres proponer un cambio grande, abre antes
  una *issue* para hablarlo.

## Al avisar de un error

- Indica la versión (Ajustes → «Cómo funciona», al final), el sistema y cómo reproducirlo.
- El registro de errores está en la carpeta de datos, en `logs/keybio.log` (ver
  [privacidad y datos](../docs/privacidad-y-datos.md)). Solo contiene errores y avisos del programa, pero revísalo antes de pegarlo.
- **No adjuntes perfiles, exportaciones, copias de seguridad ni `history.jsonl`/`access.jsonl`**:
  son datos biométricos de personas reales.

## Desarrollo

Si trabajas con el código (con permiso del titular):

```sh
python -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m pyflakes ksb tests tools main.py web/i18n   # lint
.venv/bin/python -m pytest tests                      # pruebas (Qt sin ventana)
python3 web/tests/run.py                              # web (necesita Chrome)
```

- El código, los comentarios, la interfaz y los mensajes de commit están en español.
- Cualquier cambio en el modelo (`ksb/features.py`, `ksb/matcher.py`) se comprueba con datos
  reales y con `python -m tests.evaluate` y `python -m tests.separation`, y se traslada a la
  demo web (`web/public/assets/js/keybio.js`, ver [`web/README.md`](../web/README.md)).
- Un cambio que altere la longitud de las muestras necesita umbrales que la tengan en cuenta:
  con menos texto la distancia de una persona a su propio perfil crece.
- La versión se cambia solo en `ksb/__init__.py`; `tests/test_release.py` comprueba el resto.
  Cómo publicar una versión: [`docs/publicar.md`](../docs/publicar.md). Guía completa de
  desarrollo: [`docs/desarrollo.md`](../docs/desarrollo.md).
