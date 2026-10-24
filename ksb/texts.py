"""Textos de registro y de comprobación.

Son distintos entre sí a propósito: la identificación se hace con un texto
que la persona no ha escrito durante el registro (análisis de texto libre).
Todos tienen frases con mayúsculas, comas y puntos para capturar el uso de
shift y de los signos de puntuación.
"""

from __future__ import annotations

import random

from .texts_langs import POOLS as LANG_POOLS

ENROLL_TEXTS: dict[str, str] = {
    "R1": ("El tren de la mañana salió con algo de retraso. Por la ventanilla se veían "
           "campos de trigo, pequeños pueblos y alguna carretera vacía. Marta abrió su "
           "cuaderno y empezó a escribir una lista de cosas pendientes: llamar a su "
           "hermano, revisar el presupuesto y comprar pan antes de volver a casa."),
    "R2": ("Cuando llegamos al puerto, el viento soplaba con fuerza y las gaviotas "
           "volaban bajo. Un pescador nos explicó que el mar estaba demasiado agitado "
           "para salir. Decidimos tomar un café en el bar de la esquina y esperar. A "
           "media tarde el cielo se despejó y por fin pudimos subir al barco."),
    "R3": ("La biblioteca del barrio abre todos los días de nueve a ocho. Tiene una sala "
           "de estudio silenciosa, ordenadores para consultar el catálogo y una sección "
           "infantil muy completa. Los sábados organizan talleres de lectura y, una vez "
           "al mes, invitan a un autor para que hable de su último libro."),
    "R4": ("Para preparar una buena tortilla hacen falta paciencia y fuego lento. Primero "
           "se pelan las patatas y se cortan en láminas finas. Después se fríen con "
           "cebolla hasta que estén tiernas. Por último se mezclan con el huevo batido, "
           "se cuajan en la sartén y se les da la vuelta con un plato."),
    "R5": ("Ayer por la noche hubo una tormenta eléctrica impresionante. Los relámpagos "
           "iluminaban todo el valle y los truenos hacían temblar los cristales. Se fue "
           "la luz durante casi una hora, así que encendimos unas velas y jugamos a las "
           "cartas. Al final, nadie quería que volviera la electricidad."),
    "R6": ("Mi abuelo tenía un taller de relojes en el centro de la ciudad. Pasaba horas "
           "inclinado sobre la mesa, con una lupa en el ojo y unas pinzas diminutas. "
           "Decía que cada reloj tiene su propio carácter y que, si lo escuchas con "
           "atención, te cuenta cuánto lo han cuidado sus dueños."),
    "R7": ("El equipo de baloncesto del instituto ganó el campeonato regional después de "
           "una temporada complicada. En la final iban perdiendo por diez puntos al "
           "descanso, pero en la segunda parte defendieron mejor y acertaron desde "
           "lejos. Toda la grada celebró la victoria cantando hasta el final."),
    "R8": ("Viajar en bicicleta permite descubrir rincones que pasan desapercibidos desde "
           "el coche. Se escuchan los pájaros, se huele la hierba recién cortada y se "
           "nota cada cuesta en las piernas. Lo más importante es llevar agua, una buena "
           "chaqueta y no tener prisa por llegar a ninguna parte."),
}

VERIFY_TEXTS: dict[str, str] = {
    "V1": ("Esta mañana el parque estaba lleno de gente paseando a sus perros. Un niño "
           "intentaba volar una cometa roja, pero el viento cambiaba de dirección cada "
           "pocos segundos. Al final la cometa quedó enganchada en un árbol y su padre "
           "tuvo que subir a buscarla."),
    "V2": ("La reunión empezó puntual, aunque faltaban dos personas del departamento. "
           "Repasamos las cifras del trimestre, comentamos los problemas con el "
           "proveedor y acordamos una nueva fecha de entrega. Antes de terminar, Laura "
           "propuso celebrar el aniversario de la empresa."),
    "V3": ("En el mercado de los domingos se pueden encontrar frutas de temporada, quesos "
           "artesanos y libros antiguos. Siempre compro tomates en el mismo puesto, "
           "porque la dueña me guarda los más maduros. Después me siento en una terraza "
           "a leer el periódico con calma."),
    "V4": ("Hace unos años decidí aprender a tocar la guitarra. Al principio me dolían los "
           "dedos y los acordes sonaban fatal, pero practicaba un poco cada noche. Ahora "
           "puedo tocar varias canciones completas y, de vez en cuando, me animo a "
           "cantar con mis amigos."),
    "V5": ("El museo inauguró una exposición dedicada a la historia de la navegación. Hay "
           "mapas antiguos, brújulas, maquetas de barcos y diarios de capitanes que "
           "cruzaron el océano. La parte favorita de los visitantes es una sala que "
           "simula el interior de un galeón."),
    "V6": ("Nuestro vecino del quinto cultiva tomates, pimientos y fresas en la terraza. "
           "Cada verano nos regala una caja llena de verduras y nos explica cómo las "
           "riega. Dice que el secreto es hablarles un poco cada día, aunque nadie en el "
           "edificio sabe si lo dice en serio."),
}


ENROLL_TEXTS_EN: dict[str, str] = {
    "EN-R1": ("The morning train left a little late. Through the window we could see wheat fields, small "
              "villages and a few empty roads. Martha opened her notebook and wrote a list of things to do: "
              "call her brother, check the budget and buy bread before going home."),
    "EN-R2": ("When we reached the harbour, the wind was blowing hard and the seagulls were flying low. A "
              "fisherman told us the sea was too rough to go out. We decided to have a coffee in the corner "
              "bar and wait. By the afternoon the sky had cleared and we finally boarded the boat."),
    "EN-R3": ("The local library is open every day from nine to eight. It has a quiet study room, computers "
              "to search the catalogue and a very complete section for children. On Saturdays there are "
              "reading workshops and, once a month, an author comes to talk about a new book."),
    "EN-R4": ("My grandfather had a small watch repair shop in the city centre. He spent hours bent over the "
              "table with a magnifying glass and tiny tweezers. He used to say that every watch has its own "
              "character and that, if you listen carefully, it tells you how well it was looked after."),
    "EN-R5": ("Travelling by bicycle lets you discover places that go unnoticed from a car. You hear the "
              "birds, you smell freshly cut grass and you feel every hill in your legs. The most important "
              "things are to carry water, wear a good jacket and never be in a hurry to arrive."),
}

VERIFY_TEXTS_EN: dict[str, str] = {
    "EN-V1": ("This morning the park was full of people walking their dogs. A boy was trying to fly a red "
              "kite, but the wind kept changing direction every few seconds. In the end the kite got stuck "
              "in a tree and his father had to climb up to get it back."),
    "EN-V2": ("The meeting started on time, although two people from the department were missing. We "
              "reviewed the quarterly figures, discussed the problems with the supplier and agreed on a new "
              "delivery date. Before finishing, Laura suggested celebrating the company anniversary."),
    "EN-V3": ("A few years ago I decided to learn to play the guitar. At first my fingers hurt and the chords "
              "sounded awful, but I practised a little every night. Now I can play several complete songs "
              "and, from time to time, I even sing with my friends."),
}

# Frases cortas para la verificación de acceso (al iniciar sesión en un sistema sensible).
# Rondan los 100 caracteres: en las pruebas, por debajo de unas 90 pulsaciones se rechazaba a
# bastantes más usuarios legítimos con los umbrales normales (docs/verificacion-acceso.md).
ACCESS_PHRASES: dict[str, str] = {
    "A1": "Antes de salir, Lucía cerró las ventanas, apagó la radio y dejó una nota en la mesa de la cocina.",
    "A2": "El autobús de las ocho llegó tarde, así que fuimos andando hasta la plaza mientras empezaba a llover.",
    "A3": "Por la tarde revisamos el inventario del almacén, ordenamos las cajas y anotamos todo lo que faltaba.",
    "A4": "Mi hermana compró un mapa antiguo en el rastro y lo colgó en el salón, justo al lado de la estantería.",
    "A5": "Cada domingo, el panadero del barrio prepara una tarta de manzana que se agota antes del mediodía.",
    "A6": "La profesora explicó el ejercicio dos veces, puso un ejemplo en la pizarra y nos dio diez minutos.",
    "A7": "En verano el río baja con poca agua, pero los vecinos siguen bañándose en la poza del viejo molino.",
    "A8": "Javier encontró las llaves debajo del sofá justo cuando ya había llamado al cerrajero de guardia.",
    "A9": "Durante la excursión vimos un ciervo, cruzamos un puente de madera y comimos junto a la cascada.",
    "A10": "El nuevo horario de la piscina empieza en octubre, con clases por la mañana y también los sábados.",
    "A11": "Si el tren vuelve a retrasarse, tomaremos un taxi hasta el hotel y cenaremos algo rápido allí.",
    "A12": "La tienda de la esquina vende fruta fresca, periódicos del día y unas galletas de chocolate caseras.",
}

ACCESS_PHRASES_EN: dict[str, str] = {
    "EN-A1": "Before leaving, Lucy closed the windows, turned off the radio and left a note on the kitchen table.",
    "EN-A2": "The eight o'clock bus was late, so we walked to the main square while it was starting to rain.",
    "EN-A3": "Every Sunday the local baker makes an apple pie that is usually sold out well before midday.",
    "EN-A4": "During the hike we saw a deer, crossed a wooden bridge and had lunch next to the waterfall.",
    "EN-A5": "If the train is late again, we will take a taxi to the hotel and have a quick dinner there.",
    "EN-A6": "The corner shop sells fresh fruit, daily newspapers and some really good homemade biscuits.",
}

# Textos de cada idioma: registro, comprobación y frases de acceso. Los de los demás idiomas están
# en texts_langs.py. «mixed» mezcla los de español e inglés.
POOLS: dict[str, dict[str, dict[str, str]]] = {
    "es": {"enroll": ENROLL_TEXTS, "verify": VERIFY_TEXTS, "access": ACCESS_PHRASES},
    "en": {"enroll": ENROLL_TEXTS_EN, "verify": VERIFY_TEXTS_EN, "access": ACCESS_PHRASES_EN},
    **LANG_POOLS,
}
MIXED = "mixed"


def text_languages() -> list[str]:
    """Idiomas con textos para escribir (códigos de ksb/i18n.py), más «mixed»."""
    return list(POOLS) + [MIXED]


def _pool(kind: str, language: str) -> dict[str, str]:
    if language == MIXED:
        return {**POOLS["es"][kind], **POOLS["en"][kind]}
    return dict(POOLS.get(language, POOLS["en"])[kind])


def text_by_id(text_id: str) -> str | None:
    for kinds in POOLS.values():
        for pool in kinds.values():
            if text_id in pool:
                return pool[text_id]
    return None


def pick_enroll_texts(n: int, exclude: set[str] | None = None, language: str = "es") -> list[tuple[str, str]]:
    """Elige n textos de registro distintos, priorizando los que el usuario no ha escrito."""
    pool = _pool("enroll", language)
    exclude = exclude or set()
    fresh = [k for k in pool if k not in exclude]
    used = [k for k in pool if k in exclude]
    random.shuffle(fresh)
    random.shuffle(used)
    keys = (fresh + used)[:n]
    return [(k, pool[k]) for k in keys]


def pick_verify_text(avoid: str | None = None, language: str = "es") -> tuple[str, str]:
    pool = _pool("verify", language)
    keys = [k for k in pool if k != avoid] or list(pool)
    k = random.choice(keys)
    return k, pool[k]


def pick_access_phrase(avoid: str | None = None, language: str = "es") -> tuple[str, str]:
    """Frase corta al azar para la verificación de acceso."""
    pool = _pool("access", language)
    keys = [k for k in pool if k != avoid] or list(pool)
    k = random.choice(keys)
    return k, pool[k]
