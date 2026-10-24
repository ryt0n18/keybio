# Cambios

## 2.1.0

**Verificación de acceso al iniciar sesión** (pensada para el RGPD y el ámbito laboral)
- `KeyBio --acceso NOMBRE --sistema SISTEMA` pide una frase corta (unos 100 caracteres) y
  termina con un código de salida: 0 confirmada, 1 no confirmada, 2 no se pudo comprobar.
  Solo al iniciar sesión: no hay captura en segundo plano.
- La muestra se analiza en el equipo y se descarta: no se guarda, no se añade al perfil ni pasa
  al historial. Solo queda la puntuación de coincidencia (y el día y la persona); nunca las
  pulsaciones, el texto, la IP ni el nombre del equipo.
- Si no coincide: verificación adicional con un texto más largo y aviso al administrador
  (sección «Accesos» y panel de control) con la hora, el sistema, la puntuación y cómo terminó
  la verificación adicional. Nada más.
- Los registros se borran solos a los 30 días (configurable), al borrar a la persona, y no
  entran en las copias de seguridad. Se cifran con la contraseña de los datos.
- Longitud de la frase elegida con pruebas: con frases más cortas se rechazaba a bastantes más
  usuarios legítimos; con unas 90–100 pulsaciones el equilibrio es bueno.

**El programa en nueve idiomas**
- Español, inglés, catalán, gallego, euskera, francés, portugués, alemán e italiano. Se elige en
  Ajustes → «Apariencia e idioma» (por defecto, el del sistema) y se aplica al reiniciar.
- Textos para escribir en cada idioma (registro, comprobación y frases de acceso) y teclado en
  pantalla con la distribución de cada país: además de la española y la estadounidense,
  AZERTY, QWERTZ, italiana y portuguesa. Ambas cosas siguen al idioma salvo que se elijan a mano.
- Fechas con el formato de cada idioma y diálogos de Qt traducidos. El instalador de Windows,
  también en catalán, francés, portugués, alemán e italiano.
- Las traducciones están en `ksb/locale/` con el texto en español como clave;
  `tools/i18n.py check` comprueba que no falte ninguna ni cambien sus variables.

**Se instala como un programa más**
- Linux: paquete `.deb` (Ubuntu, Debian, Mint) que se instala con doble clic, y `instalar.sh` en
  el `.tar.gz` para el resto, sin permisos de administrador. Los dos añaden KeyBio al menú y al
  buscador de aplicaciones, con icono y palabras de búsqueda en los nueve idiomas; el `.deb`
  lleva además la ficha para las tiendas de aplicaciones. Desinstalar no borra los perfiles.
- Windows: el acceso del menú Inicio lleva descripción y el mismo identificador que la ventana,
  para que al anclarlo a la barra de tareas no salga un icono repetido.

**Escribir menos y probar el sistema**
- Decisión progresiva: la comprobación termina antes del final del texto si el resultado ya está
  claro (a partir de 60 pulsaciones, con margen frente al segundo perfil). En las pruebas se
  escribe bastante menos texto sin errores nuevos. Opción en Ajustes, activada por defecto. Las
  muestras cortas no entran al perfil.
- Modo desafío: imitar a otra persona para intentar engañar a KeyBio, con pista y marcador.
  Los intentos quedan verificados en el historial y la calibración los usa como impostores.

**Precisión: umbrales más fiables con perfiles pequeños**
- Los perfiles con pocas muestras toman la variación típica del resto del equipo en lugar
  de un valor fijo pesimista. Con 2 muestras el umbral quedaba tan holgado que aceptaba a
  otra persona en sensibilidad «normal».
- Una sola muestra de otro día ya no reduce todo el margen del perfil: el margen se
  reduce en proporción a la parte de la calibración hecha realmente entre sesiones.
- En las pruebas, «estricto» y «normal» dejan de rechazar a usuarios legítimos sin aceptar a
  impostores; con los datos sintéticos el resultado no empeora.

**macOS** (en pruebas: falta probarlo en un Mac real)
- Captura por tecla virtual (en macOS todas las teclas parecían la misma), carpeta de datos
  propia, aplicación `.app` con icono e imagen `.dmg` para Apple Silicon.

**Seguridad y privacidad**
- Ficheros importados validados y con límite de tamaño (también dentro de un `.zip`), nombres
  tratados como texto llano, CSV sin fórmulas, carpeta de datos y ficheros solo legibles por el
  usuario en Linux y macOS, parámetros del almacén de claves comprobados.
- Casilla de permiso de la persona antes de registrarla.

**Proyecto**
- Dependencia: PySide6-Essentials en lugar de PySide6 completo (entorno de 740 a 310 MB).
- Los ejecutables incluyen las licencias de terceros y dejan fuera Qt Virtual Keyboard (GPL).
- Licencia: todos los derechos reservados (con la salvedad de la LGPL de Qt).
- La versión se define solo en `ksb/__init__.py`; una prueba comprueba que el resto coincide.
- La prueba de cifrado ya no falla por azar (≈3 % de las veces).

**Web del proyecto** (`web/`, preparada pero sin publicar)
- Demo en el navegador: huella de tecleo con mapa de calor y modo «adivina quién», con el mismo
  algoritmo que el programa (comprobado contra Python) y decisión progresiva; las pulsaciones no
  salen del navegador.
- Funcionamiento, descargas, valoraciones (Cloudflare Pages + D1, con antispam y moderación),
  contacto, política de privacidad y cabeceras de seguridad. Pruebas en Chrome sin ventana.
- En nueve idiomas (español, inglés, catalán, gallego, euskera, francés, portugués, alemán e
  italiano), con selector de idioma, aviso del idioma del navegador sin redirigir y la demo con
  frases para teclear en cada idioma. Las páginas se generan desde catálogos (`web/i18n`).

## 2.0.0

**Precisión y modelo**
- Los tiempos de vuelo por dígrafo (soltar → pulsar) entran en las medidas R/A.
- Calibración por sesiones: con muestras de varios días se aparta la sesión entera
  (deja‑una‑sesión‑fuera) y el margen se ajusta.
- Calibración automática de la sensibilidad y del peso de cada medida con los datos del
  equipo y las comprobaciones verificadas (nueva sensibilidad «automática»).
- Adaptación automática del perfil con comprobaciones muy seguras, con deshacer.
- El perfil conserva siempre las muestras de registro como ancla.
- Regularidad calculada de forma robusta (IQR/mediana) para que las pausas no la hundan.

**Seguridad**
- Protección opcional con contraseña (scrypt + Fernet) de perfiles e historial.
- Detección de suplantaciones: ritmo robótico, tiempos repetidos, pulsaciones instantáneas
  y réplicas de muestras guardadas.

**Funciones**
- Identificación en directo mientras se escribe.
- Identificación y verificación con texto libre.
- Textos en inglés (o mezclados con los de español).
- Informes PDF de usuarios y de comprobaciones.
- Evolución de velocidad y regularidad por usuario, con las sesiones marcadas.
- Sugerencias en el panel de control; notas y filtro de sospechosas en el historial.
- Registro de errores en fichero y aviso en pantalla en lugar de cierres silenciosos.

**Proyecto**
- `pyproject.toml`, integración continua en Linux y Windows, ejecutables e instalador de
  Windows automáticos, publicación de versiones por etiqueta.

## 1.1.0

- Panel de control con widgets, tema claro/oscuro, iconos, tamaño de letra.
- Teclado en pantalla y mapas de calor, huella de tecleo (radar), medidor de confianza y
  explicación del resultado.
- Verificación 1:1, exportar/importar usuarios, copias de seguridad, historial con filtros y CSV.

## 1.0.0

- Primera versión: registro, identificación, usuarios, historial y ajustes.
