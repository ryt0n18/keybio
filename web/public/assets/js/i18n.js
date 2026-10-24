// Textos de la web en el idioma de la página. web/i18n/build.py los escribe dentro de cada página
// (<script type="application/json" id="i18n">) junto con las frases para teclear de la demo.
// Sin ellos (páginas de prueba) t() devuelve la clave.

const node = typeof document === "undefined" ? null : document.getElementById("i18n");
const data = node ? JSON.parse(node.textContent) : { lang: "es", locale: "es-ES", js: {}, texts: {}, languages: [] };

export const LANG = data.lang;
export const LOCALE = data.locale;
export const TEXTS = data.texts;
/** [{code, name, suggest, switch, dismiss}] de todos los idiomas de la web. */
export const LANGUAGES = data.languages;

const plurals = new Intl.PluralRules(LANG);

/** Texto ``key`` con sus variables {nombre} sustituidas. */
export function t(key, params = {}) {
  const text = data.js[key];
  if (text === undefined) return key;
  return text.replace(/\{(\w+)\}/g, (mark, name) => (name in params ? String(params[name]) : mark));
}

/** Texto con plural: usa ``key_one``, ``key_other``... según el número ``n`` y el idioma. */
export function tn(key, n, params = {}) {
  const form = `${key}_${plurals.select(n)}`;
  return t(form in data.js ? form : `${key}_other`, { n, ...params });
}
