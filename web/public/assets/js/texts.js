// Frases para teclear en la demo, en el idioma de la página (catálogos de web/i18n). Más cortas
// que las del programa (≈140 caracteres) para que la prueba dure un par de minutos; las de
// comprobación no aparecen en el registro (texto libre).

import { TEXTS } from "./i18n.js";

// Con 2 frases el umbral tiene que ser más estricto que en el programa: ver SENSITIVITY en demo.js
export const ENROLL_COUNT = 2;

/** Textos de registro al azar, distintos entre sí. */
export function pickEnroll(n = ENROLL_COUNT) {
  return shuffle(TEXTS.enroll.map((t, i) => [`R${i + 1}`, t])).slice(0, n);
}

/** Un texto de comprobación al azar, evitando el último usado. */
export function pickVerify(lastId = null) {
  const options = TEXTS.verify.map((t, i) => [`V${i + 1}`, t]).filter(([id]) => id !== lastId);
  return options[Math.floor(Math.random() * options.length)];
}

function shuffle(list) {
  const a = [...list];
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
}
