// Demo en el navegador: registro, huella de tecleo y «adivina quién».
// Las muestras se guardan solo en este navegador (localStorage); no se envían a ningún sitio.

import { LOCALE, t, tn } from "./i18n.js";
import * as kb from "./keybio.js";
import { ENROLL_COUNT, pickEnroll, pickVerify } from "./texts.js";

const STORE_KEY = "keybio-demo-v1";
const MAX_PEOPLE = 12;
const MAX_NAME = 30;
// K del umbral (m + K·s + margen; en el programa «normal» es 2 y «estricto» 1). Con solo 2 frases
// de registro, cada persona se calibra comparando una frase con la otra y el umbral sale holgado:
// en las pruebas, con K = 2 se aceptaba a casi cualquier desconocido. Con K = 0 se rechaza a la
// mayoría, a cambio de que alguna vez no reconozca a quien sí está registrado (web/README.md).
const SENSITIVITY = 0;

// --- utilidades de DOM ----------------------------------------------------------------------

function h(tag, attrs = {}, ...children) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v === null || v === undefined || v === false) continue;
    if (k === "class") el.className = v;
    else if (k === "text") el.textContent = v;
    else if (k.startsWith("on")) el.addEventListener(k.slice(2), v);
    else el.setAttribute(k, v === true ? "" : v);
  }
  for (const c of children.flat()) {
    if (c === null || c === undefined || c === false) continue;
    el.append(c instanceof Node ? c : document.createTextNode(String(c)));
  }
  return el;
}

const SVG_NS = "http://www.w3.org/2000/svg";
function s(tag, attrs = {}, ...children) {
  const el = document.createElementNS(SVG_NS, tag);
  for (const [k, v] of Object.entries(attrs)) el.setAttribute(k, v);
  el.append(...children);
  return el;
}

function icon(name, cls = "icon") {
  return s("svg", { class: cls, "aria-hidden": "true" }, s("use", { href: `#i-${name}` }));
}

function button(text, { kind = "", iconName = null, onclick, type = "button", disabled = false, autofocus = false } = {}) {
  return h("button", { class: `btn ${kind}`.trim(), type, onclick, disabled, "data-autofocus": autofocus },
    iconName ? icon(iconName) : null, text);
}

const newId = () => (crypto.randomUUID ? crypto.randomUUID().replaceAll("-", "") : Math.random().toString(16).slice(2)).slice(0, 12);

const fmt = (v, digits = 0) => v.toLocaleString(LOCALE, { maximumFractionDigits: digits, minimumFractionDigits: digits });
const MESSAGES = Object.fromEntries(Object.keys(kb.MESSAGES).map((k) => [k, t(`demo.check.${k}`)]));

// --- datos -------------------------------------------------------------------------------------

function loadPeople() {
  try {
    const data = JSON.parse(localStorage.getItem(STORE_KEY) || "null");
    if (data && Array.isArray(data.people)) return data.people;
  } catch { /* almacenamiento bloqueado o dañado: se empieza de cero */ }
  return [];
}

function savePeople(people) {
  try {
    localStorage.setItem(STORE_KEY, JSON.stringify({ version: 1, people }));
    return true;
  } catch {
    return false;
  }
}

function compactSample(sample) {
  const r = (x) => (x === null ? null : Math.round(x * 100) / 100);
  return { ...sample, keys: sample.keys.map((k) => ({ ...k, press: r(k.press), release: r(k.release) })) };
}

const featureCache = new WeakMap();
function features(sample) {
  let f = featureCache.get(sample);
  if (!f) featureCache.set(sample, (f = kb.extract(sample)));
  return f;
}

function buildProfiles(people) {
  const profiles = people.filter((p) => p.samples.length >= 2).map((p) =>
    kb.Profile.build(p.id, p.name, p.samples.map(features), { sessions: kb.sessionsOf(p.samples) }));
  kb.shareSpread(profiles);
  return profiles;
}

// --- rasgos de la huella (ksb/traits.py) ---------------------------------------------------------

const TRAITS = [
  { id: "speed", unit: t("demo.unit.cpm"), low: 100, high: 600, get: (m) => m.cpm },
  { id: "dwell", unit: "ms", low: 50, high: 180, get: (m) => m.dwellMean },
  { id: "flight", unit: "ms", low: -30, high: 250, get: (m) => m.flightMean },
  { id: "overlap", unit: "%", low: 0, high: 50, get: (m) => m.rolloverPct },
  { id: "regularity", unit: "%", low: 0, high: 100, get: (m) => m.consistency },
  { id: "errors", unit: t("demo.unit.per100chars"), low: 0, high: 12,
    get: (m) => (100 * m.errorsCommitted) / Math.max(m.chars, 1) },
].map((tr) => ({ ...tr, name: t(`demo.trait.${tr.id}`), help: t(`demo.trait.${tr.id}.help`) }));

const GLOBAL_UNITS = {
  overlap: [100, "%"], shift_right: [100, "%"], speed_cpm: [1, ` ${t("demo.unit.cpm")}`],
  pause_rate: [1, ` ${t("demo.unit.per100keys")}`], bs_rate: [1, ` ${t("demo.unit.per100keys")}`],
  err_rate: [1, ` ${t("demo.unit.per100chars")}`],
};
function fmtGlobal(key, value) {
  const [mult, unit] = GLOBAL_UNITS[key] || [1, " ms"];
  return `${fmt(value * mult)}${unit}`;
}

// --- teclado del mapa de calor (distribución ISO; las teclas pulsadas muestran lo que escribe cada una) ---

const ROW = (codes, labels) => codes.map((c, i) => [c, labels[i], 1]);
const LETTERS = (s) => [...s].map((ch) => `Key${ch.toUpperCase()}`);
const KEYBOARD = [
  [["Backquote", "º", 1], ...ROW(["Digit1", "Digit2", "Digit3", "Digit4", "Digit5", "Digit6", "Digit7", "Digit8", "Digit9", "Digit0"], [..."1234567890"]),
    ["Minus", "'", 1], ["Equal", "¡", 1], ["Backspace", "⌫", 2]],
  [["Tab", t("demo.key.tab"), 1.5], ...ROW(LETTERS("qwertyuiop"), [..."qwertyuiop"]), ["BracketLeft", "`", 1], ["BracketRight", "+", 1], ["Enter", t("demo.key.enter"), 1.5]],
  [["CapsLock", t("demo.key.caps"), 1.75], ...ROW(LETTERS("asdfghjkl"), [..."asdfghjkl"]), ["Semicolon", "ñ", 1], ["Quote", "´", 1], ["Backslash", "ç", 1], ["", "", 1.25]],
  [["ShiftLeft", t("demo.key.shift"), 1.25], ["IntlBackslash", "<", 1], ...ROW(LETTERS("zxcvbnm"), [..."zxcvbnm"]), ["Comma", ",", 1], ["Period", ".", 1], ["Slash", "-", 1], ["ShiftRight", t("demo.key.shift"), 2.75]],
  [["ControlLeft", t("demo.key.ctrl"), 1.5], ["MetaLeft", "", 1.25], ["AltLeft", "Alt", 1.25], ["Space", "", 6.25], ["AltRight", "AltGr", 1.25], ["ContextMenu", "", 1.25], ["ControlRight", t("demo.key.ctrl"), 2.25]],
];

function heatmap(samples) {
  const stats = kb.dwellByCode(samples);
  const known = [...stats.values()].filter((e) => e.count >= 3).map((e) => e.dwell);
  const lo = Math.min(...known), hi = Math.max(...known);
  const wrap = h("div", { class: "kbd", role: "img", "aria-label": t("demo.heatmap.label") });
  for (const row of KEYBOARD) {
    const r = h("div", { class: "kbd-row" });
    for (const [code, label, width] of row) {
      const e = stats.get(code);
      // lo que escribe la tecla en el teclado de quien escribe (AZERTY, QWERTZ...) si la ha pulsado
      const shown = e && [...e.label].length === 1 && !["Space", "Tab", "Enter"].includes(code) ? e.label : label;
      const key = h("div", { class: code ? "kbd-key" : "kbd-key blank" }, shown);
      key.style.flex = `${width} 1 0`;
      if (e && e.count >= 3 && known.length >= 2) {
        const heat = hi > lo ? (e.dwell - lo) / (hi - lo) : 0.5;
        key.style.setProperty("--heat", heat.toFixed(3));
        key.classList.add("hot");
        if (heat > 0.55) key.classList.add("strong");
        key.title = t("demo.heatmap.key", { key: shown || code, ms: fmt(e.dwell), n: e.count });
      }
      r.append(key);
    }
    wrap.append(r);
  }
  return h("figure", { class: "heatmap" }, wrap,
    h("figcaption", {}, h("span", { class: "legend-scale" }, h("span", {}, t("demo.heatmap.shorter")), h("span", { class: "legend-bar" }), h("span", {}, t("demo.heatmap.longer"))),
      h("span", { class: "muted" }, ` · ${t("demo.heatmap.caption")}`)));
}

// --- caja de escritura ---------------------------------------------------------------------------------

const EARLY_STEP = 15;   // comprobación cada 15 pulsaciones, como la estimación en directo del programa

class TypingBox {
  /** ``earlyCheck(muestraParcial, pulsaciones)`` devuelve una decisión para terminar antes, o null. */
  constructor(target, { textId = "", step = "", onDone, earlyCheck = null }) {
    this.target = target;
    this.targetNorm = kb.normalizeTyped(target, target);
    this.onDone = onDone;
    this.earlyCheck = earlyCheck;
    this.checkedAt = 0;
    this.partial = false;
    this.rec = new kb.Recorder(target, { textId });
    this.typed = "";
    this.shownLen = 0;
    this.finishing = false;
    this.done = false;

    this.chars = [...target].map((c) => h("span", { class: "ch" }, c));
    this.box = h("div", {
      class: "typing", tabindex: "0", role: "textbox", "aria-label": t("demo.typing.label", { text: target }),
      onkeydown: (e) => this.keyDown(e), onkeyup: (e) => this.keyUp(e),
      onblur: () => this.blur(), onfocus: () => this.hint(""),
      onpaste: (e) => { e.preventDefault(); this.rec.block(); }, ondrop: (e) => e.preventDefault(),
      oncontextmenu: (e) => e.preventDefault(),
    }, this.chars);
    this.chars[0]?.classList.add("cursor");
    this.speed = h("span", { class: "muted" }, t("demo.typing.start"));
    this.bar = h("div", { class: "progress-bar" });
    this.msg = h("p", { class: "typing-hint", "aria-live": "polite" });
    this.el = h("div", { class: "typing-wrap" },
      h("div", { class: "typing-head" }, h("strong", {}, step), this.speed),
      h("div", { class: "progress" }, this.bar), this.box, this.msg);
  }

  focus() { this.box.focus(); }

  hint(text, kind = "warn") {
    this.msg.textContent = text;
    this.msg.className = `typing-hint ${text ? kind : ""}`;
  }

  keyDown(e) {
    if (this.done || this.finishing) {
      if (!e.ctrlKey && !e.metaKey) e.preventDefault();
      return;
    }
    let [label, kind] = kb.classifyKey(e);
    const altGr = e.getModifierState && e.getModifierState("AltGraph");
    if ((e.ctrlKey || e.metaKey) && !altGr && kind === kb.CHAR) {   // atajos (pegar, deshacer...)
      [label, kind] = [`key_${label}`, kb.OTHER];
    }
    this.rec.press(e.code || e.key, label, kind, e.timeStamp, e.repeat);
    if (e.repeat && kind !== kb.BACKSPACE) { e.preventDefault(); return; }
    if (e.key.length === 1 && /\p{L}/u.test(e.key) && e.getModifierState) {
      this.hint(e.getModifierState("CapsLock") ? t("demo.typing.caps") : "");
    }
    switch (kind) {
      case kb.MOD:
      case kb.DEAD:
        return;
      case kb.BACKSPACE:
        e.preventDefault();
        this.typed = [...this.typed].slice(0, -1).join("");
        break;
      case kb.SPACE:
        e.preventDefault();
        this.typed += " ";
        break;
      case kb.CHAR:
        e.preventDefault();
        this.typed += e.key;
        break;
      default:
        if (e.key !== "Escape" && !(e.ctrlKey && ["r", "R"].includes(e.key))) e.preventDefault();
        if (!["Shift", "Escape"].includes(e.key)) this.rec.block();
        return;
    }
    this.rec.textChanged(this.typed);
    this.render();
    this.maybeEarly();
  }

  /** Decisión progresiva: con lo escrito hasta ahora, ¿está ya claro el resultado? */
  maybeEarly() {
    if (!this.earlyCheck || this.finishing) return;
    const keys = this.rec.keys.filter((k) => [kb.CHAR, kb.SPACE, kb.DEAD].includes(k.kind)).length;
    if (keys < kb.EARLY_MIN_KEYS || keys - this.checkedAt < EARLY_STEP) return;
    this.checkedAt = keys;
    setTimeout(() => {   // fuera del evento de teclado, para no retrasar los siguientes
      if (this.finishing || !this.earlyCheck(this.rec.sample({ partial: true }), keys)) return;
      this.finishing = this.partial = true;
      this.box.classList.add("finished");
      this.hint(t("demo.typing.early"), "good");
      if (this.rec.down.size === 0) this.finish();
      else setTimeout(() => this.finish(), 700);
    }, 0);
  }

  keyUp(e) {
    this.rec.release(e.code || e.key, e.timeStamp);
    if (this.finishing && this.rec.down.size === 0) this.finish();
  }

  blur() {
    if (this.done) return;
    this.rec.dropPressed();
    if (this.rec.keys.length) this.hint(t("demo.typing.blur"));
  }

  render() {
    const norm = kb.normalizeTyped(this.typed, this.target);
    const from = Math.max(0, Math.min(this.shownLen, norm.length) - 1);
    const to = Math.min(Math.max(this.shownLen, norm.length) + 1, this.chars.length);
    for (let i = from; i < to; i++) {
      const c = this.chars[i];
      c.classList.toggle("ok", i < norm.length && norm[i] === this.targetNorm[i]);
      c.classList.toggle("bad", i < norm.length && norm[i] !== this.targetNorm[i]);
      c.classList.toggle("cursor", i === norm.length);
    }
    this.shownLen = norm.length;
    this.bar.style.width = `${Math.min(100, (100 * norm.length) / this.targetNorm.length)}%`;
    const typing = this.rec.keys.filter((k) => k.kind === kb.CHAR || k.kind === kb.SPACE);
    if (typing.length >= 10) {
      const minutes = (typing[typing.length - 1].press - typing[0].press) / 60000;
      this.speed.textContent = t("demo.typing.speed", { n: fmt((typing.length - 1) / Math.max(minutes, 1e-6)) });
    }
    if (norm.length >= this.targetNorm.length) {
      this.finishing = true;
      setTimeout(() => this.finish(), 700);   // por si alguna tecla no llega a soltarse
    }
  }

  finish() {
    if (this.done) return;
    this.done = true;
    this.box.classList.add("finished");
    this.onDone(compactSample(this.rec.sample({ partial: this.partial })), this.partial);
  }
}

// --- aplicación ----------------------------------------------------------------------------------------

export function mountDemo(root) {
  let people = loadPeople();
  let lastVerify = null;
  let storageOk = savePeople(people);

  const setView = (...nodes) => {
    const warning = storageOk ? null
      : notice(t("demo.noStorage"), "warn");
    root.replaceChildren(...[warning, ...nodes].filter(Boolean));
    root.querySelector("[data-autofocus]")?.focus();
  };

  const persist = () => { storageOk = savePeople(people); };

  function notice(text, kind = "info") {
    const name = { bad: "x", warn: "alert", good: "check" }[kind] || "info";
    return h("p", { class: `notice ${kind}` }, icon(name), h("span", {}, text));
  }

  function personChip(p, i) {
    return h("span", { class: `avatar p${i % 8}`, "aria-hidden": "true" }, [...p.name][0].toUpperCase());
  }

  // -- inicio
  function home() {
    const touch = matchMedia("(pointer: coarse)").matches && !matchMedia("(any-pointer: fine)").matches;
    const tips = [
      touch ? notice(t("demo.touch"), "warn") : null,
    ];
    if (!people.length) {
      setView(
        h("div", { class: "demo-intro" },
          h("ol", { class: "steps" },
            h("li", {}, h("strong", {}, t("demo.intro.step1")), ` ${t("demo.intro.step1.text", { n: ENROLL_COUNT })}`),
            h("li", {}, h("strong", {}, t("demo.intro.step2")), ` ${t("demo.intro.step2.text")}`),
            h("li", {}, h("strong", {}, t("demo.intro.step3")), ` ${t("demo.intro.step3.text")}`)),
          ...tips,
          h("div", { class: "actions" }, button(t("demo.create"), { kind: "primary", iconName: "fingerprint", onclick: enrollName })),
          h("p", { class: "muted small" }, t("demo.local"))));
      return;
    }
    const list = h("ul", { class: "people" }, people.map((p, i) =>
      h("li", {},
        personChip(p, i),
        h("button", { class: "person-name", type: "button", onclick: () => fingerprint(p) }, p.name),
        h("span", { class: "muted small" }, tn("demo.samples", p.samples.length)),
        h("button", { class: "icon-btn", type: "button", "aria-label": t("demo.deletePerson", { name: p.name }), title: t("demo.delete"),
                      onclick: () => removePerson(p) }, icon("trash")))));
    setView(
      h("div", { class: "demo-home" },
        h("div", { class: "demo-home-head" },
          h("div", {}, h("h3", {}, t("demo.home.title")),
            h("p", { class: "muted" }, t(people.length === 1 ? "demo.home.one" : "demo.home.many"))),
          button(t(people.length === 1 ? "demo.recognizeMe" : "demo.whoTypes"), { kind: "primary", iconName: "scan", onclick: identifyView })),
        list,
        ...tips,
        h("div", { class: "actions" },
          button(t("demo.addPerson"), { iconName: "user-plus", onclick: enrollName, disabled: people.length >= MAX_PEOPLE }),
          button(t("demo.clearAll"), { kind: "ghost", iconName: "trash", onclick: clearAll }))));
  }

  function removePerson(p) {
    if (!confirm(t("demo.confirmDelete", { name: p.name }))) return;
    people = people.filter((x) => x !== p);
    persist();
    home();
  }

  function clearAll() {
    if (!confirm(t("demo.confirmClear"))) return;
    people = [];
    try { localStorage.removeItem(STORE_KEY); } catch { /* nada que borrar */ }
    home();
  }

  // -- registro
  function enrollName() {
    const input = h("input", { id: "demo-name", type: "text", maxlength: String(MAX_NAME), autocomplete: "off",
                               required: true, "data-autofocus": true, placeholder: t("demo.name.placeholder") });
    const error = h("p", { class: "field-error", "aria-live": "polite" });
    const form = h("form", { class: "demo-form", onsubmit: (e) => {
      e.preventDefault();
      const name = input.value.trim().replace(/\s+/g, " ");
      if (!name) { error.textContent = t("demo.name.empty"); return; }
      if (people.some((p) => p.name.toLowerCase() === name.toLowerCase())) {
        error.textContent = t("demo.name.taken"); return;
      }
      enrollStep({ name, texts: pickEnroll(), samples: [] });
    } },
    h("label", { for: "demo-name" }, t("demo.name.label")), input, error,
    h("p", { class: "muted small" }, t("demo.name.help")),
    h("div", { class: "actions" }, button(t("demo.start"), { kind: "primary", type: "submit" }),
      people.length ? button(t("demo.cancel"), { kind: "ghost", onclick: home }) : null));
    setView(form);
  }

  function enrollStep(state, problem = null) {
    const i = state.samples.length;
    const [textId, text] = state.texts[i];
    const box = new TypingBox(text, {
      textId, step: t("demo.enroll.step", { i: i + 1, n: ENROLL_COUNT }),
      onDone: (sample) => {
        const issue = kb.qualityProblem(sample, 80, MESSAGES) || kb.livenessProblems(sample, MESSAGES)[0];
        if (issue) { enrollStep(state, issue); return; }
        state.samples.push(sample);
        if (state.samples.length < ENROLL_COUNT) { enrollStep(state); return; }
        const person = { id: newId(), name: state.name, created: new Date().toISOString(),
                         samples: state.samples };
        people.push(person);
        persist();
        fingerprint(person, true);
      },
    });
    setView(
      h("div", { class: "demo-typing" },
        h("p", { class: "muted" }, t("demo.enroll.intro", { name: state.name })),
        problem ? notice(`${problem} ${t("demo.enroll.retry")}`, "warn") : null,
        box.el,
        h("div", { class: "actions" }, button(t("demo.cancel"), { kind: "ghost", onclick: home }))));
    box.focus();
  }

  // -- huella
  function fingerprint(person, fresh = false) {
    const feats = person.samples.map(features);
    const avg = (get) => kb.fmean(feats.map((f) => get(f.metrics)));
    const tiles = h("div", { class: "tiles" }, TRAITS.map((tr) => {
      const v = avg(tr.get);
      const pos = Math.max(0, Math.min(1, (v - tr.low) / (tr.high - tr.low)));
      const meter = h("div", { class: "trait-meter" }, h("span", {}));
      meter.firstChild.style.left = `${pos * 100}%`;
      return h("div", { class: "tile", title: tr.help },
        h("span", { class: "tile-label" }, tr.name),
        h("span", { class: "tile-value" }, fmt(v), h("small", {}, ` ${tr.unit}`)),
        meter, h("span", { class: "tile-help" }, tr.help));
    }));
    const pairs = (list) => h("ul", { class: "digraphs" }, list.map(([k, v]) =>
      h("li", {}, h("kbd", {}, k.replaceAll(" ", "␣")), h("span", { class: "muted" }, ` ${fmt(v)} ms`))));
    const all = new Map();
    for (const f of feats) for (const [k, v] of [...f.metrics.fastest, ...f.metrics.slowest]) all.set(k, v);
    const sorted = [...all].sort((a, b) => a[1] - b[1]);
    setView(
      h("div", { class: "demo-print" },
        fresh ? notice(t("demo.print.ready", { name: person.name }), "good") : null,
        h("h3", {}, t("demo.print.title", { name: person.name })),
        tiles,
        heatmap(person.samples),
        sorted.length >= 4 ? h("div", { class: "digraph-cols" },
          h("div", {}, h("h4", {}, t("demo.print.fastest")), pairs(sorted.slice(0, 4))),
          h("div", {}, h("h4", {}, t("demo.print.slowest")), pairs(sorted.slice(-4).reverse()))) : null,
        canAdd() ? h("p", { class: "muted add-hint" }, t("demo.print.addHint")) : null,
        h("div", { class: "actions" },
          button(t(people.length === 1 ? "demo.recognizeMe" : "demo.whoTypes"), { kind: "primary", iconName: "scan", onclick: identifyView }),
          addAnotherButton(),
          button(t("demo.back"), { kind: "ghost", onclick: home }))));
  }

  // Más personas = el juego de «¿quién escribe?»: el botón se ve al terminar la huella y el resultado
  function canAdd() { return people.length < MAX_PEOPLE; }

  function addAnotherButton() {
    return canAdd() ? button(t("demo.addAnother"), { iconName: "user-plus", onclick: enrollName }) : null;
  }

  // -- identificación
  function identifyView(problem = null) {
    const [textId, text] = pickVerify(lastVerify);
    lastVerify = textId;
    const profiles = buildProfiles(people);
    const box = new TypingBox(text, {
      textId, step: t("demo.identify.step"),
      earlyCheck: (partial, keys) => kb.earlyDecision(kb.identify(kb.extract(partial), profiles, SENSITIVITY), keys),
      onDone: (sample, early) => {
        const issue = kb.qualityProblem(sample, 80, MESSAGES);
        if (issue) { identifyView(issue); return; }
        result(sample, early);
      },
    });
    setView(
      h("div", { class: "demo-typing" },
        h("p", { class: "muted" }, t(people.length === 1 ? "demo.identify.one" : "demo.identify.many")),
        typeof problem === "string" ? notice(`${problem} ${t("demo.identify.retry")}`, "warn") : null,
        box.el,
        h("div", { class: "actions" }, button(t("demo.cancel"), { kind: "ghost", onclick: home }))));
    box.focus();
  }

  function result(sample, early = false) {
    const f = kb.extract(sample);
    const profiles = buildProfiles(people);
    const res = kb.identify(f, profiles, SENSITIVITY);
    const robot = kb.livenessProblems(sample, MESSAGES);
    const best = robot.length ? null : res.best;
    const closest = res.candidates[0];
    const index = new Map(people.map((p, i) => [p.id, i]));

    let verdict;
    if (robot.length) {
      verdict = h("div", { class: "verdict bad" }, icon("alert", "icon big"),
        h("div", {}, h("h3", {}, t("demo.result.robot")), h("p", {}, robot.join(" "))));
    } else if (best) {
      verdict = h("div", { class: "verdict good" }, ring(best.confidence),
        h("div", {}, h("h3", {}, t("demo.result.youAre", { name: best.name })),
          h("p", {}, t("demo.result.confidence", { n: fmt(best.confidence) })),
          res.ambiguous ? h("p", { class: "muted" }, t("demo.result.ambiguous")) : null));
    } else {
      verdict = h("div", { class: "verdict warn" }, icon("help", "icon big"),
        h("div", {}, h("h3", {}, people.length === 1 ? t("demo.result.notYou", { name: people[0].name }) : t("demo.result.unknown")),
          h("p", {}, closest ? t("demo.result.closest", { name: closest.name }) : t("demo.result.noData"))));
    }

    const ranking = h("ul", { class: "ranking" }, res.candidates.map((c) => {
      const value = resemblance(c);
      const fill = h("span", { class: "bar-fill" });
      fill.style.width = `${Math.max(2, value)}%`;
      return h("li", { class: c.accepted && !robot.length ? "accepted" : "" },
        personChip({ name: c.name }, index.get(c.userId) ?? 0),
        h("span", { class: "rank-name" }, c.name),
        h("span", { class: "bar", title: t("demo.result.threshold") }, fill, h("span", { class: "bar-threshold" })),
        h("span", { class: "rank-value" }, `${fmt(value)} %`));
    }));

    const target = best || closest;
    let why = null;
    if (target) {
      const profile = profiles.find((p) => p.userId === target.userId);
      const [zg] = profile.zScores(f);
      const rows = Object.entries(zg).sort((a, b) => a[1] - b[1]);
      const line = ([key, z]) => h("li", {}, h("span", {}, t(`demo.feature.${key}`)),
        h("span", { class: "muted" }, t("demo.why.values", { now: fmtGlobal(key, f.globals[key]), print: fmtGlobal(key, profile.globalStats[key][0]) })),
        h("span", { class: `z ${z < 1 ? "good" : z < 2 ? "warn" : "bad"}` }));
      why = h("details", { class: "why" }, h("summary", {}, t("demo.why.title", { name: target.name })),
        h("div", { class: "why-cols" },
          h("div", {}, h("h4", {}, t("demo.why.similar")), h("ul", {}, rows.slice(0, 4).map(line))),
          h("div", {}, h("h4", {}, t("demo.why.different")), h("ul", {}, rows.slice(-4).reverse().map(line)))),
        h("p", { class: "muted small" }, t("demo.why.note")));
    }

    // El foco va al resultado, no a un botón: si decide antes de terminar la frase, la persona sigue
    // escribiendo unos instantes y un espacio o un Intro pulsaría «Probar otra vez» y lo borraría.
    // Lo que se teclee encima del resultado se ignora (tampoco desplaza la página).
    const view = h("div", { class: "demo-result", "aria-live": "polite", tabindex: "-1", "data-autofocus": true },
      verdict,
      early ? h("p", { class: "early-note" }, icon("bolt"),
        ` ${t("demo.result.early", { n: sample.keys.filter((k) => [kb.CHAR, kb.SPACE, kb.DEAD].includes(k.kind)).length })}`) : null,
      res.candidates.length ? h("h4", {}, t("demo.result.ranking")) : null,
      ranking,
      why,
      h("p", { class: "muted small" }, t("demo.result.disclaimer")),
      h("div", { class: "actions" },
        button(t("demo.again"), { kind: "primary", iconName: "refresh", onclick: identifyView }),
        addAnotherButton(),
        button(t("demo.back"), { kind: "ghost", onclick: home })));
    view.addEventListener("keydown", (e) => {
      if (e.target === view && !e.ctrlKey && !e.metaKey && !e.altKey && e.key !== "Tab") e.preventDefault();
    });
    setView(view);
  }

  /** Parecido para la clasificación: la confianza por debajo del umbral; por encima baja más
   *  despacio (50 % en el umbral, 0 % al 160 % de él) para que se vea quién se acerca más. */
  function resemblance(c) {
    if (c.accepted) return c.confidence;
    return 50 * Math.max(0, 1 - (c.distance - c.threshold) / (0.6 * c.threshold));
  }

  function ring(value) {
    const r = 26, c = 2 * Math.PI * r;
    return s("svg", { class: "ring", viewBox: "0 0 64 64", "aria-hidden": "true" },
      s("circle", { cx: "32", cy: "32", r: String(r), class: "ring-track" }),
      s("circle", { cx: "32", cy: "32", r: String(r), class: "ring-value",
                    "stroke-dasharray": `${(c * value) / 100} ${c}`, transform: "rotate(-90 32 32)" }),
      s("text", { x: "32", y: "37", "text-anchor": "middle", class: "ring-text" }, `${Math.round(value)}%`));
  }

  home();
}
