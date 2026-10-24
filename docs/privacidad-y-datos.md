# Privacidad y datos

La forma de teclear es un **dato biométrico**. KeyBio está pensado para tratarla con el mínimo
de riesgo: todo se queda en el equipo donde se usa.

## Principios

- **Nada sale del equipo.** El programa no envía datos por red.
- **Permiso antes de registrar.** Al registrar a alguien hay que confirmar que esa persona está
  de acuerdo.
- **Protección con contraseña** (Ajustes): los perfiles, el historial y los registros de acceso
  se cifran con Fernet (AES + HMAC), con una clave derivada de la contraseña con scrypt. La
  contraseña no se guarda; si se olvida, los datos cifrados no se pueden recuperar.
- **Las exportaciones y copias de seguridad van sin cifrar**, para poder abrirlas en otro
  equipo. El programa avisa antes de crearlas.
- En Linux y macOS, la carpeta de datos y sus ficheros solo los puede leer el usuario.

## Dónde se guardan los datos

| Sistema | Carpeta |
|---|---|
| Linux | `~/.local/share/keybio/` (o `$XDG_DATA_HOME/keybio`) |
| Windows | `%APPDATA%\KeyBio\` |
| macOS | `~/Library/Application Support/KeyBio/` |

Se puede cambiar con la variable de entorno `KEYBIO_DATA_DIR`.

| Fichero | Contenido |
|---|---|
| `users/<id>.json` | Cada persona con todas sus muestras en bruto |
| `history.jsonl` | Una línea por comprobación |
| `access.jsonl` | Verificaciones de acceso: solo la puntuación (y los avisos). Ver [verificación de acceso](verificacion-acceso.md) |
| `settings.json` | Ajustes (nunca se cifran: hacen falta antes de pedir la contraseña) |
| `keystore.json` | Solo con contraseña: sal y parámetros (nunca la contraseña) |
| `logs/keybio.log` | Registro de errores del programa |

## Borrar datos

- Una muestra o una persona: sección **Usuarios**. Al borrar a una persona se borran también
  sus registros de acceso.
- El historial: sección **Historial** → «Borrar historial».
- Los registros de acceso: sección **Accesos** → «Borrar registros» (además se borran solos
  pasado su plazo de conservación).
- Todo: cerrar KeyBio y borrar la carpeta de datos.

## La web y la demo

La demo de la web también procesa las pulsaciones solo en el navegador. La web tiene su propia
[política de privacidad](../web/public/privacidad.html).
