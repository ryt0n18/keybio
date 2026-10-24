# Seguridad

KeyBio trata **datos biométricos** (la forma de teclear). Si encuentras un fallo de seguridad,
avísame en privado antes de contarlo en público, para poder corregirlo primero.

## Cómo avisar

- **En GitHub**: pestaña *Security* → *Report a vulnerability* (aviso privado).
- **Desde la web del proyecto**: formulario de contacto.

No abras una incidencia pública para un fallo de seguridad. Cuenta qué versión usas, en qué
sistema, cómo reproducirlo y qué puede conseguir quien lo aproveche. Intentaré responder en
una semana.

## Qué cuenta como fallo de seguridad

- Leer o modificar perfiles, historial o registros de acceso de otra persona, o saltarse el
  cifrado con contraseña.
- Que un fichero importado (exportación o copia de seguridad) ejecute código, agote la memoria o
  escriba fuera de la carpeta de datos.
- Que la verificación de acceso devuelva «confirmada» (código 0) sin haber comparado la
  escritura, o que guarde las pulsaciones, el texto, la IP o el nombre del equipo.
- En la web: que la demo envíe pulsaciones fuera del navegador, inyección en valoraciones o
  contacto, o fallos de la API de valoraciones.

Que la biometría se equivoque a veces (aceptar a un impostor que imita muy bien, o rechazar a
la persona correcta) es una limitación conocida, no un fallo de seguridad: está descrito en
[cómo funciona](../docs/funcionamiento.md#limitaciones-conocidas). Sí interesan los ataques sistemáticos que la engañen con facilidad.

## Versiones con soporte

Solo la última versión publicada recibe correcciones.

## No envíes datos biométricos

No adjuntes la carpeta de datos de KeyBio, exportaciones de usuarios ni copias de seguridad:
contienen pulsaciones en bruto de personas reales. Si hace falta un ejemplo, usa los
mecanógrafos simulados de `tests/simulate.py`.
