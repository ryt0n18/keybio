# Cómo funciona KeyBio

KeyBio no se fija en **qué** escribes, sino en **cómo**: cuánto tiempo mantienes pulsada cada
tecla, cuánto tardas en pasar a la siguiente y qué combinaciones te cuestan más. Con eso crea
un perfil de cada persona y compara con él cada texto nuevo.

- [Qué se mide](#qué-se-mide)
- [Cómo decide quién eres](#cómo-decide-quién-eres)
- [Escribir menos: decisión progresiva](#escribir-menos-decisión-progresiva)
- [Sensibilidad y calibración automática](#sensibilidad-y-calibración-automática)
- [Perfiles que se adaptan](#perfiles-que-se-adaptan)
- [Limitaciones conocidas](#limitaciones-conocidas)

## Qué se mide

Por cada pulsación se registra el instante en que se pulsa y se suelta la tecla, con precisión
de microsegundos. De ahí salen estas medidas:

| Medida | Qué es |
|---|---|
| Tiempo de pulsación (*dwell*) | Cuánto tiempo se mantiene pulsada cada tecla |
| Intervalo DD (*down‑down*) | Tiempo entre pulsar una tecla y pulsar la siguiente |
| Tiempo de vuelo UD (*up‑down*) | Entre soltar una tecla y pulsar la siguiente (negativo si se solapan) |
| Dígrafos y trígrafos | Duración de cada combinación de 2 y 3 teclas (`en`, `de`, `que`…) |
| Solapamiento | Veces que se pulsa la siguiente tecla antes de soltar la anterior |
| Espacio | Pulsación de la barra y tiempos letra→espacio y espacio→letra |
| Mayúsculas | Shift izquierdo o derecho, adelanto del shift y cuánto se mantiene |
| Errores | Caracteres erróneos, corregidos y sin corregir; precisión final |
| Correcciones | Retrocesos, duración del retroceso y tiempo de reacción ante un error |
| Ritmo | Velocidad, pausas largas y regularidad |

## Cómo decide quién eres

La identificación es de **texto libre**: el texto de comprobación no aparece en el registro,
así que las medidas se calculan sobre teclas y combinaciones de teclas, no sobre un texto fijo.

1. **Medidas R y A** (Gunetti y Picardi, *Keystroke analysis of free text*, 2005) entre la
   muestra nueva y cada muestra del perfil, sobre dígrafos, trígrafos, tiempos de pulsación y
   tiempos de vuelo:
   - **R** ordena de más rápida a más lenta cada combinación que ambas muestras tienen en
     común y mide cuánto difieren esas ordenaciones.
   - **A** es la proporción de combinaciones cuya duración difiere más de un 25 % (o 30 ms en
     los tiempos de vuelo).
2. **Distancia estadística** (Manhattan escalada) sobre los rasgos globales y el tiempo de
   pulsación de cada tecla, frente a la media y la dispersión del perfil.
3. **Umbral propio de cada persona.** Con validación deja‑uno‑fuera se mide cuánto se parece
   la persona a sí misma (*m*) y cuánto varía (*s*). Si el perfil tiene **varias sesiones**
   (días distintos), se aparta la sesión entera, que da una estimación más realista. La
   muestra se acepta si `distancia ≤ m + K·s + margen`.
4. Si ningún perfil la acepta, la respuesta es **no registrado**. Si la aceptan varios, gana
   el que tenga menor distancia en proporción a su umbral y se avisa de que el resultado es
   poco concluyente.
5. Si la muestra es **sospechosa** (ritmo robótico, réplica de una muestra guardada…), no se
   acepta.

## Escribir menos: decisión progresiva

Mientras se escribe, la estimación en directo compara la muestra cada 15 pulsaciones. Si a
partir de 60 pulsaciones el resultado ya está claro, la comprobación termina sin acabar el
texto:

- se acepta cuando la distancia queda por debajo del 85 % del umbral y el segundo perfil más
  parecido está al menos 0,2 más lejos (en proporción a su umbral);
- se responde «no registrado» cuando todos los perfiles superan el 140 % de su umbral.

Con poco texto la distancia de una persona a su propio perfil crece, pero la de las demás no
baja; por eso no basta con ampliar el umbral y se exige un margen claro. En las pruebas se
escribe bastante menos texto sin ningún error más que con el texto completo. Las muestras cortas
no se añaden al perfil. Se puede desactivar en Ajustes.

## Sensibilidad y calibración automática

K vale 1, 2 o 3 (sensibilidad estricta, normal o permisiva). En **Ajustes → Calibración
automática** el programa prueba cada muestra guardada contra su perfil (sin ella) y contra los
de los demás, añade las comprobaciones que hayas marcado como correctas o incorrectas y busca
la K y el peso de cada medida que menos errores cometen **con vuestros datos**.

- Necesita al menos 3 personas con 3 muestras.
- Tiene en cuenta que las muestras de una misma sesión son optimistas.
- No baja de la sensibilidad estricta, para no sobreajustarse con pocos datos.
- Los intentos del **modo desafío** (alguien que imita a otra persona) cuentan como impostores
  reales.

## Perfiles que se adaptan

- Lo ideal es registrarse en **dos sesiones** de días distintos; el panel de control lo sugiere.
- Las comprobaciones reconocidas con confianza ≥ 75 %, sin ambigüedad ni sospechas, se añaden
  solas al perfil. Si luego se marca el resultado como incorrecto, la muestra se retira.
- El perfil usa las muestras de registro más recientes (hasta 6, como ancla) más las más
  recientes de comprobaciones, hasta 12 en total.
- Las pulsaciones se guardan en bruto, así que los perfiles se recalculan siempre con el
  algoritmo de la versión instalada.

## Limitaciones conocidas

- Los umbrales se han ajustado con **pocas personas reales** y con mecanógrafos
  simulados. Con un equipo nuevo conviene registrar a varias personas, verificar resultados y
  usar la calibración automática.
- Con una sola sesión de registro, otro día (cansancio, otro teclado) es más fácil que se
  rechace a la persona correcta; por eso se sugiere una segunda sesión y existe la adaptación.
- Cambiar de teclado o de sistema operativo cambia un poco los tiempos de pulsación.
- La detección de suplantaciones cubre ataques sencillos (programas que teclean, réplicas
  exactas), no imitaciones hechas a mano con mucha práctica.
- La biometría de tecleo puede equivocarse: no debe ser el único medio para proteger el acceso
  a sistemas o datos importantes.
