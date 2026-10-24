// Prueba de extremo a extremo de la demo, dentro de un iframe con la web real.
//
// Dos personas simuladas se registran tecleando en la caja de la demo (eventos de teclado con
// sus propios tiempos; Chrome sin ventana adelanta el reloj virtual, así que no hay esperas
// reales). Después se comprueba que la demo reconoce a cada una y no acepta a una tercera.
// Con ?stop=print se detiene en la huella de la primera persona (para hacer capturas).

const results = [];
const frame = document.getElementById("site");
const stopAt = new URLSearchParams(location.search).get("stop");

function report(done = true) {
  const out = document.getElementById("results");
  out.textContent = JSON.stringify(results);
  if (done) out.dataset.done = "1";
}

async function step(name, fn) {
  try {
    await fn();
    results.push({ name, ok: true });
    return true;
  } catch (e) {
    results.push({ name, ok: false, error: String((e && e.stack) || e) });
    return false;
  }
}

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function waitFor(fn, what, timeout = 120000) {
  const t0 = performance.now();
  for (;;) {
    const v = fn();
    if (v) return v;
    if (performance.now() - t0 > timeout) throw new Error(`No aparece: ${what}`);
    await sleep(100);
  }
}

// --- mecanógrafo simulado -------------------------------------------------------------------

function rng(seed) {   // mulberry32
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function hash(...parts) {
  let h = 2166136261;
  for (const ch of parts.join("|")) h = Math.imul(h ^ ch.codePointAt(0), 16777619);
  return (h >>> 0) / 4294967296;
}

const ACCENTS = { á: "a", é: "e", í: "i", ó: "o", ú: "u" };
const PUNCT = { ",": "Comma", ".": "Period", "-": "Slash" };

function keyInfo(ch) {
  if (ch === " ") return { code: "Space", key: " " };
  if (ch.toLowerCase() === "ñ") return { code: "Semicolon", key: ch };
  if (PUNCT[ch]) return { code: PUNCT[ch], key: ch };
  const base = ACCENTS[ch.toLowerCase()] || ch.toLowerCase();
  return { code: `Key${base.toUpperCase()}`, key: ch, dead: Boolean(ACCENTS[ch.toLowerCase()]) };
}

class Typist {
  constructor(seed, { dd, dwell, overlap }) {
    this.seed = seed;
    this.dd = dd;
    this.dwell = dwell;
    this.overlap = overlap;
    this.rand = rng(seed);
  }

  noise(x, amount = 0.15) {   // aproximadamente lognormal
    const g = (this.rand() + this.rand() + this.rand() - 1.5) * 2;
    return Math.max(12, x * Math.exp(g * amount));
  }

  keyDwell(code) { return this.dwell * (0.75 + 0.5 * hash(this.seed, "dwell", code)); }

  digraph(a, b) { return this.dd * (0.55 + 0.9 * hash(this.seed, "dd", a, b)) * (0.8 + 0.4 * hash(0, a, b)); }

  /** Eventos [{at, type, key, code, shift}] para escribir ``text`` (con algún error corregido). */
  events(text) {
    const ev = [];
    let t = 300, prev = "Space";
    const stroke = (key, code, at, dwell, shift = false) => {
      ev.push({ at, type: "keydown", key, code, shift });
      ev.push({ at: at + dwell, type: "keyup", key, code, shift });
    };
    for (const ch of text) {
      const info = keyInfo(ch);
      t += this.noise(this.digraph(prev, info.code));
      if (this.rand() < 0.03 && /\p{L}/u.test(ch)) {   // error y corrección
        stroke("x", "KeyX", t, this.noise(this.keyDwell("KeyX")));
        t += this.noise(this.dd * 2.5);
        stroke("Backspace", "Backspace", t, this.noise(85));
        t += this.noise(this.dd * 1.2);
      }
      if (info.dead) {
        stroke("Dead", "Quote", t, this.noise(this.keyDwell("Quote")));
        t += this.noise(this.dd * 0.9);
      }
      const upper = ch !== ch.toLowerCase();
      const dwell = this.noise(this.keyDwell(info.code));
      if (upper) {
        const lead = this.noise(this.dd * 0.6);
        ev.push({ at: t - lead, type: "keydown", key: "Shift", code: "ShiftLeft", shift: true });
        ev.push({ at: t + dwell + 15, type: "keyup", key: "Shift", code: "ShiftLeft", shift: false });
      }
      stroke(info.key, info.code, t, dwell, upper);
      // solapamiento: a veces la siguiente tecla llega antes de soltar esta
      if (this.rand() < this.overlap) t -= dwell * 0.4;
      t += dwell * 0.3;
      prev = info.code;
    }
    return ev.sort((a, b) => a.at - b.at);
  }
}

async function typeInto(win, typist) {
  const box = await waitFor(() => win.document.querySelector(".typing:not(.finished)"), "caja de escritura");
  box.focus();
  const text = [...box.querySelectorAll(".ch")].map((s) => s.textContent).join("");
  const events = typist.events(text);
  const t0 = performance.now();
  for (const e of events) {
    const wait = t0 + e.at - performance.now();
    if (wait > 0) await sleep(wait);
    box.dispatchEvent(new win.KeyboardEvent(e.type, { key: e.key, code: e.code, shiftKey: e.shift, bubbles: true, cancelable: true }));
  }
  await waitFor(() => box.classList.contains("finished") || !box.isConnected, "fin de la frase", 5000);
  await sleep(50);
}

function click(win, text) {
  const btn = [...win.document.querySelectorAll("#demo-app button")].find((b) => b.textContent.includes(text));
  if (!btn) throw new Error(`No hay botón «${text}»`);
  btn.click();
}

async function enroll(win, name, typist) {
  const input = await waitFor(() => win.document.getElementById("demo-name"), "campo de nombre");
  input.value = name;
  input.form.requestSubmit();
  for (let i = 0; i < 2; i++) await typeInto(win, typist);   // ENROLL_COUNT (texts.js)
  const title = await waitFor(() => win.document.querySelector(".demo-print h3"), "huella");
  if (!title.textContent.includes(name)) throw new Error(`Huella inesperada: ${title.textContent}`);
  if (win.document.querySelectorAll(".kbd-key.hot").length < 10) throw new Error("El mapa de calor casi no tiene teclas");
  if (win.document.querySelectorAll(".tile").length !== 6) throw new Error("Faltan rasgos en la huella");
}

async function identify(win, typist) {
  await typeInto(win, typist);
  const verdict = await waitFor(() => win.document.querySelector(".verdict h3"), "resultado");
  return verdict.textContent;
}

// --- escenario ----------------------------------------------------------------------------------

const ana = new Typist(11, { dd: 165, dwell: 85, overlap: 0.25 });
const beto = new Typist(22, { dd: 240, dwell: 125, overlap: 0.05 });
const carla = new Typist(33, { dd: 330, dwell: 70, overlap: 0.0 });

await new Promise((r) => { frame.addEventListener("load", r, { once: true }); frame.src = "../public/index.html"; });
const win = frame.contentWindow;
win.localStorage.clear();
win.location.reload();
await new Promise((r) => frame.addEventListener("load", r, { once: true }));

let ok = await step("registro de la primera persona (escribiendo en la caja)", async () => {
  click(win, "Crear mi huella");
  await enroll(win, "Ana", ana);
});
if (ok && stopAt !== "print") {
  ok = await step("registro de la segunda persona", async () => {
    click(win, "Añadir otra persona");   // desde la huella recién creada
    await enroll(win, "Beto", beto);
  }) && await step("las huellas se guardan en el navegador", () => {
    const saved = JSON.parse(win.localStorage.getItem("keybio-demo-v1"));
    if (saved.people.length !== 2 || saved.people.some((p) => p.samples.length !== 2)) throw new Error(JSON.stringify(saved.people.map((p) => p.samples.length)));
    if (!saved.people[0].samples[0].keys.some((k) => k.kind === "dead")) throw new Error("No se registran las teclas muertas");
  });
  if (ok) {
    // Con 2 frases de registro el umbral es estricto (demo.js) y a veces no reconoce a quien sí está
    // registrado: hasta 3 intentos. Confundirlo con otra persona, nunca.
    const UNKNOWN = "No te reconozco";
    async function recognises(typist, expected, { early = false } = {}) {
      for (let attempt = 1; ; attempt++) {
        const v = await identify(win, typist);
        if (v !== expected && v !== UNKNOWN) throw new Error(`Resultado: ${v}`);
        // quien sigue escribiendo tras la decisión no debe pulsar «Probar otra vez» con un espacio
        await new Promise((r) => setTimeout(r, 100));
        const focused = win.document.activeElement;
        if (!focused || !focused.classList.contains("demo-result")) throw new Error(`Foco en ${focused && focused.outerHTML.slice(0, 60)}`);
        if (v === expected && (!early || win.document.querySelector(".early-note"))) return;
        if (attempt === 3) throw new Error(early ? "No ha decidido antes de terminar en 3 intentos" : `Resultado: ${v}`);
        click(win, "Probar otra vez");
      }
    }
    await step("reconoce a Ana sin terminar la frase", async () => {
      click(win, "¿Quién escribe?");
      await recognises(ana, "Eres Ana", { early: true });
      if (win.document.querySelectorAll(".ranking li").length !== 2) throw new Error("La clasificación no tiene 2 personas");
    });
    await step("reconoce a Beto", async () => {
      click(win, "Probar otra vez");
      await recognises(beto, "Eres Beto");
    });
    await step("no acepta a una persona sin registrar", async () => {
      click(win, "Probar otra vez");
      const v = await identify(win, carla);
      if (v !== "No te reconozco") throw new Error(`Resultado: ${v}`);
    });
  }
}

// --- idiomas ------------------------------------------------------------------------------------

async function load(path) {
  await new Promise((r) => { frame.addEventListener("load", r, { once: true }); frame.src = path; });
  return frame.contentWindow;
}

/** Textos del catálogo que la página lleva dentro (los escribe web/i18n/build.py). */
const strings = (w) => JSON.parse(w.document.getElementById("i18n").textContent);

if (stopAt !== "print") {
  const codes = ["es", "en", "ca", "gl", "eu", "fr", "pt", "de", "it"];
  await step("las 9 versiones cargan sin textos sin traducir", async () => {
    frame.contentWindow.localStorage.clear();   // sin las personas del escenario anterior
    for (const code of codes) {
      const w = await load(code === "es" ? "../public/index.html" : `../public/${code}/index.html`);
      const data = strings(w);
      if (w.document.documentElement.lang !== code || data.lang !== code) throw new Error(`${code}: idioma ${data.lang}`);
      await waitFor(() => w.document.querySelector("#demo-app button"), `${code}: botón de la demo`);
      const start = w.document.querySelector("#demo-app button").textContent;
      if (start !== data.js["demo.create"]) throw new Error(`${code}: botón «${start}»`);
      const text = w.document.body.innerText;
      const key = text.match(/\b(?:demo|ratings|common|contact|theme|lang|index|privacy)\.[a-zA-Z]+/);
      if (key) throw new Error(`${code}: clave sin traducir ${key[0]}`);
      const links = [...w.document.querySelectorAll(".lang-menu a")];
      if (links.length !== codes.length || links.filter((a) => a.getAttribute("aria-current") === "page").map((a) => a.lang).join() !== code) {
        throw new Error(`${code}: menú de idiomas incorrecto`);
      }
      const priv = await load(code === "es" ? "../public/privacidad.html" : `../public/${code}/privacidad.html`);
      if (priv.document.documentElement.lang !== code || !priv.document.querySelector(".lang-menu")) throw new Error(`${code}: privacidad`);
    }
  });

  await step("los enlaces internos no ponen «#…» en la dirección", async () => {
    let w = await load("../public/index.html#descargar");
    await new Promise((r) => setTimeout(r, 200));
    if (w.location.hash) throw new Error(`Al entrar queda ${w.location.hash}`);
    if (w.document.activeElement.id !== "descargar") throw new Error("No ha ido a «Descargar»");
    w = await load("../public/index.html");
    w.document.querySelector('.nav a[href="#opiniones"]').click();
    await new Promise((r) => setTimeout(r, 200));
    if (w.location.hash) throw new Error(`El menú deja ${w.location.hash}`);
    if (w.document.activeElement.id !== "opiniones") throw new Error("No ha ido a «Opiniones»");
  });

  await step("demo completa en inglés", async () => {
    const w = await load("../public/en/index.html");
    w.localStorage.clear();
    w.location.reload();
    await new Promise((r) => frame.addEventListener("load", r, { once: true }));
    const en = strings(w).js;
    click(w, en["demo.create"]);
    await enroll(w, "Ana", ana);
    const tiles = [...w.document.querySelectorAll(".tile-label")].map((x) => x.textContent);
    if (!tiles.includes(en["demo.trait.speed"])) throw new Error(`Rasgos: ${tiles.join(", ")}`);
    click(w, en["demo.recognizeMe"]);
    const v = await identify(w, ana);
    if (v !== "You are Ana") throw new Error(`Resultado: ${v}`);
  });
}
report();
