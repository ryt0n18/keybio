# Verificación de acceso al iniciar sesión

Para sistemas sensibles (nóminas, banca, historiales…), KeyBio puede comprobar la identidad
**solo en el momento de iniciar sesión**, con una frase corta. No hay captura en segundo plano
ni durante el resto de la sesión.

![Ventana de verificación de acceso](img/acceso.png)

## Cómo se usa

El sistema sensible, o el guion que lo abre, lanza KeyBio con la persona que inicia sesión:

```sh
KeyBio --acceso "Ana" --sistema "Nóminas"      # desde el código: python main.py --acceso ...
```

1. Se abre una ventana con una frase de unos 100 caracteres, elegida al azar.
2. La muestra se compara en el equipo con el perfil de esa persona (verificación 1:1, con la
   sensibilidad de Ajustes) y se descarta.
3. Si coincide, la ventana se cierra sola.
4. Si no coincide, se crea un **aviso para el administrador** y se pide una **verificación
   adicional**: un texto más largo, con el que el resultado es más fiable.

| Código de salida | Significado |
|---|---|
| **0** | Identidad confirmada, con la frase o con la verificación adicional |
| **1** | No confirmada: no coincide y la verificación adicional no se superó o se abandonó (hay aviso) |
| **2** | No se pudo comprobar: persona sin perfil, contraseña de los datos cancelada o ventana cerrada antes de terminar la frase |

Cualquier valor distinto de 0 debe tratarse como **no confirmado**.

## Qué se guarda

Los registros van en `access.jsonl`, dentro de la carpeta de datos, cifrados si los datos
tienen contraseña.

| Caso | Se guarda |
|---|---|
| Coincide | El **día**, la persona y la **puntuación** de coincidencia (0–100; 50 es el umbral) |
| No coincide (aviso) | Además la **hora** y el **sistema**, para poder revisar el aviso, y cómo terminó la verificación adicional (superada, no superada o abandonada) |
| Nunca | Las pulsaciones, el texto escrito, la dirección IP ni el nombre del equipo. La muestra no se añade al perfil ni pasa al historial |

- Los registros se borran solos pasados 30 días (el plazo se cambia en la sección «Accesos»),
  al borrar a la persona, y no entran en las copias de seguridad.
- El administrador ve los avisos en la sección **Accesos** y en el panel de control. No se
  envían por red.

![Sección «Accesos» con los registros y los avisos](img/accesos.png)

## Por qué una frase de unos 100 caracteres

Con poco texto la distancia de una persona a su propio perfil crece y se rechaza a más
usuarios legítimos, y cada rechazo es un aviso sobre alguien que no ha hecho nada. En las
pruebas, por debajo de unas 90 pulsaciones se rechazaba a bastantes más usuarios legítimos; a
partir de ahí la mejora era pequeña y los impostores aceptados apenas cambiaban.

Aun así, de vez en cuando un inicio de sesión legítimo necesitará la verificación adicional.
Son pocas pruebas: conviene revisarlo con más personas.

## Antes de usarla con trabajadores

Orientación, no asesoramiento legal:

- Los datos de tecleo que sirven para confirmar la identidad son **datos biométricos de
  categoría especial** (art. 9 del RGPD), también en la verificación 1:1.
- Hace falta una **base jurídica** válida: el consentimiento del trabajador no suele serlo.
- Hace falta una **evaluación de impacto** (art. 35 del RGPD).
- Hay que **informar a la plantilla** antes de implantarla y pedir el **informe de la
  representación legal** de los trabajadores (art. 64.5 del Estatuto de los Trabajadores).
- Hay que ofrecer **otro método** a quien no pueda o no quiera usarla.
- La carpeta de datos tiene que estar en un sitio que la persona verificada **no pueda
  modificar**.
