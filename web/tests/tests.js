// Pruebas de la web: algoritmo (paridad con Python) y función de valoraciones.
// Se ejecutan en Chrome sin ventana con:  python web/tests/run.py

import * as kb from "../public/assets/js/keybio.js";
import * as ratings from "../functions/api/ratings.js";

const results = [];

async function test(name, fn) {
  try {
    await fn();
    results.push({ name, ok: true });
  } catch (e) {
    results.push({ name, ok: false, error: String((e && e.stack) || e) });
  }
}

function assert(cond, msg = "comprobación fallida") {
  if (!cond) throw new Error(msg);
}

function close(a, b, msg, tol = 1e-9) {
  if (a === null || b === null || a === undefined || b === undefined) {
    if ((a ?? null) !== (b ?? null)) throw new Error(`${msg}: ${a} != ${b}`);
    return;
  }
  if (Math.abs(a - b) > tol * Math.max(1, Math.abs(b))) throw new Error(`${msg}: ${a} != ${b}`);
}

// --- algoritmo ---------------------------------------------------------------------------

await test("estadística como el módulo statistics de Python", () => {
  close(kb.median([5, 1, 3, 2]), 2.5, "mediana");
  close(kb.iqr([3, 1, 4, 1, 5]), 3.5, "iqr impar");
  close(kb.iqr([1, 2, 3, 4, 5, 6, 7, 8, 9, 10]), 5.5, "iqr par");
  assert(kb.iqr([1, 2, 3]) === null, "iqr con menos de 4 valores");
  const d = [2, 4, 4, 4, 5, 5, 7, 9];
  close(kb.stdev(d), 2.138089935299395, "stdev");
  close(kb.pstdev(d), 2.0, "pstdev");
  close(kb.variance(d), 4.571428571428571, "variance");
});

await test("utilidades de texto", () => {
  assert(kb.fold("Canción ñandú") === "Cancion nandu", "fold");
  assert(kb.normalizeTyped("cancio´n", "canción") === "cancion", "normalizeTyped");
  assert(kb.levenshtein("kitten", "sitting") === 3 && kb.levenshtein("", "abc") === 3, "levenshtein");
  assert(kb.charLabel("É") === "e" && kb.charLabel("Ñ") === "ñ" && kb.charLabel("?") === "?", "charLabel");
});

await test("clasificación de teclas del navegador", () => {
  const c = (key, code) => kb.classifyKey({ key, code }).join(" ");
  assert(c("Shift", "ShiftRight") === "shift_r mod", c("Shift", "ShiftRight"));
  assert(c("AltGraph", "AltRight") === "altgr mod");
  assert(c("Backspace", "Backspace") === "backspace backspace");
  assert(c(" ", "Space") === "space space");
  assert(c("Dead", "Quote") === "dead dead");
  assert(c("Á", "KeyA") === "a char" && c("ñ", "Semicolon") === "ñ char");
  assert(c("ArrowLeft", "ArrowLeft") === "key_arrowleft other");
});

await test("el grabador empareja pulsaciones e ignora la autorrepetición", () => {
  const rec = new kb.Recorder("ab");
  rec.press("KeyA", "a", kb.CHAR, 0);
  rec.press("KeyA", "a", kb.CHAR, 30, true);   // repetición
  rec.press("KeyA", "a", kb.CHAR, 40);         // pulsación sin soltar
  rec.release("KeyA", 95);
  rec.press("ShiftLeft", "shift_l", kb.MOD, 100);
  rec.press("KeyB", "b", kb.CHAR, 180);
  rec.release("KeyB", 260);
  rec.release("ShiftLeft", 270);
  rec.textChanged("a");
  rec.textChanged("ax");
  assert(rec.keys.map((k) => k.label).join() === "a,shift_l,b", "etiquetas");
  assert(rec.keys[0].release - rec.keys[0].press === 95 && rec.keys[2].release - rec.keys[2].press === 80, "dwell");
  assert(rec.autorepeats === 2 && rec.errorsCommitted === 1, "repeticiones y errores");
  const s = rec.sample();
  close(s.accuracy, 0.5, "precisión");
});

const fixture = await (await fetch("fixture.json")).json();
const peopleFeats = fixture.people.map((p) => p.samples.map(kb.extract));
const testFeats = fixture.tests.map(kb.extract);

await test("características idénticas a Python", () => {
  const all = [...peopleFeats, testFeats];
  all.forEach((group, gi) => group.forEach((f, si) => {
    const exp = fixture.expected.globals[gi][si];
    const got = f.globals;
    assert(Object.keys(got).sort().join() === Object.keys(exp).sort().join(),
      `rasgos de ${gi}/${si}: ${Object.keys(got).sort()} != ${Object.keys(exp).sort()}`);
    for (const k of Object.keys(exp)) close(got[k], exp[k], `${k} (${gi}/${si})`);
  }));
});

const profiles = fixture.people.map((p, i) =>
  kb.Profile.build(p.id, p.name, peopleFeats[i], { sessions: kb.sessionsOf(p.samples) }));
kb.shareSpread(profiles);

await test("perfiles y umbrales idénticos a Python", () => {
  fixture.expected.profiles.forEach((e, i) => {
    const p = profiles[i];
    close(p.m, e.m, `m de ${e.id}`);
    close(p.s, e.s, `s de ${e.id}`);
    close(p.slack(), e.slack, `margen de ${e.id}`);
    close(p.crossFrac, e.crossFrac, `crossFrac de ${e.id}`);
    close(p.threshold("normal"), e.threshold, `umbral de ${e.id}`);
  });
});

await test("identificación idéntica a Python", () => {
  fixture.expected.identify.forEach((e, i) => {
    const res = kb.identify(testFeats[i], profiles, "normal");
    assert((res.best?.userId ?? null) === e.best, `prueba ${i}: ${res.best?.userId} != ${e.best}`);
    assert(res.candidates.map((c) => c.userId).join() === e.candidates.map((c) => c.id).join(), `orden ${i}`);
    res.candidates.forEach((c, j) => {
      const x = e.candidates[j];
      close(c.distance, x.distance, `distancia ${i}/${c.userId}`);
      close(c.ra, x.ra, `R/A ${i}/${c.userId}`);
      close(c.z, x.z, `z ${i}/${c.userId}`);
      close(c.threshold, x.threshold, `umbral ${i}/${c.userId}`);
    });
  });
});

await test("decisión progresiva igual que en Python", () => {
  const res = (...ratios) => ({ candidates: ratios.map((r, i) => ({ userId: `u${i}`, ratio: r })).sort((a, b) => a.ratio - b.ratio) });
  const n = kb.EARLY_MIN_KEYS;
  assert(kb.earlyDecision(res(0.5, 2.0), n - 1) === null, "poco texto");
  assert(kb.earlyDecision(res(0.8, 1.2), n) === "accept", "claro");
  assert(kb.earlyDecision(res(0.8, 0.95), n) === null, "segundo cerca");
  assert(kb.earlyDecision(res(0.9, 2.0), n) === null, "no lo bastante parecido");
  assert(kb.earlyDecision(res(0.8), n) === "accept", "una sola persona");
  assert(kb.earlyDecision(res(1.5, 1.8), n) === "reject", "nadie");
  assert(kb.earlyDecision(res(), n) === null, "sin perfiles");
  assert(kb.earlyDecision(res(0.7, 1.3), n, "u0") === "accept", "verificación aceptada");
  assert(kb.earlyDecision(res(0.7, 1.3), n, "u1") === null, "verificación de otro");
  assert(kb.earlyDecision(res(0.7, 1.5), n, "u1") === "reject", "verificación rechazada");
  const rec = new kb.Recorder("hola mundo");
  rec.textChanged("hola");
  close(rec.sample({ partial: true }).accuracy, 1, "precisión de una muestra parcial");
  close(rec.sample().accuracy, 0.4, "precisión frente al texto entero");
});

await test("detección de escritura automática", () => {
  assert(kb.livenessProblems(fixture.people[0].samples[0]).length === 0, "una persona no es un robot");
  const keys = [];
  for (let i = 0; i < 80; i++) keys.push({ label: "a", kind: kb.CHAR, press: i * 100, release: i * 100 + 50, code: "KeyA" });
  assert(kb.livenessProblems({ keys }).length >= 2, "ritmo constante y duraciones idénticas");
});

await test("control de calidad de las muestras", () => {
  const human = fixture.people[1].samples[0];
  assert(kb.qualityProblem(human) === null, "muestra válida");
  assert(kb.qualityProblem({ ...human, accuracy: 0.5 }).includes("precisión"), "precisión baja");
  assert(kb.qualityProblem({ ...human, keys: human.keys.slice(0, 30) }).includes("pocas"), "pocas teclas");
});

// --- función de valoraciones ---------------------------------------------------------------

function mockDB() {
  const rows = [];
  return {
    rows,
    prepare(sql) {
      let args = [];
      const live = () => rows.filter((r) => r.status !== "rejected");
      const stmt = {
        bind(...a) { args = a; return stmt; },
        async first() {
          if (sql === ratings.SQL.summary) {
            const l = live();
            return { n: l.length, avg: l.length ? l.reduce((s, r) => s + r.stars, 0) / l.length : null };
          }
          if (sql === ratings.SQL.recent) {
            return { n: rows.filter((r) => r.ip_hash === args[0] && Date.now() - r.created < 86400000).length };
          }
          throw new Error(`SQL inesperada: ${sql}`);
        },
        async all() {
          if (sql === ratings.SQL.histogram) {
            const by = {};
            for (const r of live()) by[r.stars] = (by[r.stars] || 0) + 1;
            return { results: Object.entries(by).map(([stars, n]) => ({ stars: Number(stars), n })) };
          }
          if (sql === ratings.SQL.comments) {
            return { results: rows.filter((r) => r.status === "approved" && r.comment)
              .map(({ name, stars, comment }) => ({ name, stars, comment, date: "2026-10-23" })) };
          }
          throw new Error(`SQL inesperada: ${sql}`);
        },
        async run() {
          if (sql !== ratings.SQL.insert) throw new Error(`SQL inesperada: ${sql}`);
          const [stars, name, comment, status, ip_hash] = args;
          rows.push({ stars, name, comment, status, ip_hash, created: Date.now() });
        },
      };
      return stmt;
    },
  };
}

const SITE = "https://keybio.example";
const env = () => ({ DB: mockDB(), TURNSTILE_SECRET: "secreto", IP_SALT: "sal" });

// Request de prueba: los navegadores no dejan fijar Origin en un Request real
function post(body, { origin = SITE, ip = "203.0.113.7", type = "application/json" } = {}) {
  const text = typeof body === "string" ? body : JSON.stringify(body);
  return { url: `${SITE}/api/ratings`, headers: new Headers({ Origin: origin, "Content-Type": type, "CF-Connecting-IP": ip }),
           text: async () => text };
}

const realFetch = globalThis.fetch;
globalThis.fetch = async (url, init) => {
  if (String(url).startsWith("https://challenges.cloudflare.com/")) {
    const ok = init.body.get("secret") === "secreto" && init.body.get("response") === "token-bueno";
    return new Response(JSON.stringify({ success: ok }));
  }
  return realFetch(url, init);
};

await test("valoraciones: validación de la entrada", async () => {
  const e = env();
  const call = async (body, opts) => (await ratings.onRequestPost({ request: post(body, opts), env: e })).status;
  assert(await call({ stars: 5, token: "token-bueno" }, { origin: "https://otra.web" }) === 403, "otro origen");
  assert(await call({ stars: 5, token: "token-bueno" }, { type: "text/plain" }) === 415, "tipo de contenido");
  assert(await call("{no es json", {}) === 400, "JSON roto");
  assert(await call({ stars: 6, token: "token-bueno" }) === 400, "6 estrellas");
  assert(await call({ stars: 2.5, token: "token-bueno" }) === 400, "estrellas no enteras");
  assert(await call({ stars: 4, comment: "x".repeat(601), token: "token-bueno" }) === 400, "comentario largo");
  assert(await call({ stars: 4, name: ["x"], token: "token-bueno" }) === 400, "nombre que no es texto");
  assert(await call({ stars: 4, comment: "y".repeat(5000), token: "token-bueno" }) === 413, "cuerpo enorme");
  const huge = post({ stars: 4, token: "token-bueno" });
  huge.headers.set("Content-Length", "100000000");
  huge.text = async () => { throw new Error("no debería leer el cuerpo"); };
  assert((await ratings.onRequestPost({ request: huge, env: e })).status === 413, "tamaño anunciado enorme, sin leerlo");
  assert(await call({ stars: 4, token: "token-malo" }) === 403, "antispam fallido");
  assert(await call({ stars: 4 }) === 403, "sin token");
  assert(e.DB.rows.length === 0, "no se guarda nada inválido");
  const noConfig = await ratings.onRequestPost({ request: post({ stars: 4, token: "token-bueno" }), env: {} });
  assert(noConfig.status === 503, "sin configurar");
});

await test("valoraciones: guardar, limitar y resumir", async () => {
  const e = env();
  const send = async (body, ip) => ratings.onRequestPost({ request: post({ token: "token-bueno", ...body }, { ip }), env: e });
  let r = await send({ stars: 5 }, "198.51.100.1");
  assert(r.status === 201 && (await r.json()).pending === false, "solo estrellas: aprobada");
  r = await send({ stars: 3, name: " Ana\u0000 ", comment: "Muy  curioso\r\n\r\n\r\n\r\n¡Me gusta!" }, "198.51.100.2");
  assert(r.status === 201 && (await r.json()).pending === true, "con comentario: pendiente");
  r = await send({ stars: 1 }, "198.51.100.2");
  assert(r.status === 429, "una al día por IP");
  const row = e.DB.rows[1];
  assert(row.name === "Ana" && row.comment === "Muy  curioso\n\n¡Me gusta!", `limpieza: ${JSON.stringify(row)}`);
  assert(!e.DB.rows.some((x) => x.ip_hash.includes("198.51")) && row.ip_hash.length === 64, "la IP no se guarda");
  e.DB.rows[1].status = "approved";
  const g = await (await ratings.onRequestGet({ env: e })).json();
  assert(g.count === 2 && g.average === 4 && g.histogram.join() === "0,0,1,0,1", JSON.stringify(g));
  assert(g.comments.length === 1 && g.comments[0].name === "Ana", "comentarios aprobados");
});

await test("valoraciones: limpieza de texto", () => {
  assert(ratings.clean("a‮b​", 10, false) === "a b", "caracteres invisibles");
  assert(ratings.clean(undefined, 10, false) === "", "vacío");
  assert(ratings.clean("ñ".repeat(41), 40, false) === null, "límite");
});

globalThis.fetch = realFetch;

// --- resultado ------------------------------------------------------------------------------

const out = document.getElementById("results");
out.textContent = JSON.stringify(results);
out.dataset.done = "1";
