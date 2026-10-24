// KeyBio en el navegador: captura de pulsaciones, características y comparación.
//
// Es la traducción de ksb/capture.py, ksb/features.py y ksb/matcher.py, con los mismos
// parámetros y fórmulas. Las pruebas de web/tests comparan los resultados con los de
// Python sobre las mismas pulsaciones. No usa el DOM: la interfaz está en demo.js.

export const CHAR = "char", SPACE = "space", BACKSPACE = "backspace", MOD = "mod", DEAD = "dead", OTHER = "other";
const TYPING = new Set([CHAR, SPACE, DEAD]);
export const PAUSE_MS = 1500;
const SEP = "\u001f";   // separador de n-gramas: menor que cualquier carácter imprimible (ordena como las tuplas de Python)

// --- estadística (equivalente al módulo statistics de Python) -------------------

export function median(values) {
  if (!values.length) return null;
  const s = [...values].sort((a, b) => a - b);
  const h = s.length >> 1;
  return s.length % 2 ? s[h] : (s[h - 1] + s[h]) / 2;
}

export function fmean(values) {
  let sum = 0, comp = 0;   // suma compensada (Neumaier), cercana a math.fsum
  for (const v of values) {
    const t = sum + v;
    comp += Math.abs(sum) >= Math.abs(v) ? (sum - t) + v : (v - t) + sum;
    sum = t;
  }
  return (sum + comp) / values.length;
}

function sumSquares(values) {
  const m = fmean(values);
  return values.reduce((acc, v) => acc + (v - m) ** 2, 0);
}

export const variance = (values) => sumSquares(values) / (values.length - 1);
export const stdev = (values) => Math.sqrt(variance(values));
export const pstdev = (values) => Math.sqrt(sumSquares(values) / values.length);

/** Rango intercuartílico como statistics.quantiles(n=4) (método "exclusive"); null con menos de 4. */
export function iqr(values) {
  if (values.length < 4) return null;
  const d = [...values].sort((a, b) => a - b);
  const ld = d.length, m = ld + 1, n = 4;
  const q = [];
  for (let i = 1; i < n; i++) {
    let j = Math.floor((i * m) / n);
    j = j < 1 ? 1 : j > ld - 1 ? ld - 1 : j;
    const delta = i * m - j * n;
    q.push((d[j - 1] * (n - delta) + d[j] * delta) / n);
  }
  return q[2] - q[0];
}

// --- texto -------------------------------------------------------------------------

const SPACING_DIACRITICS = new Set("´`¨^~˜");

export function fold(text) {
  return text.normalize("NFD").replace(/\p{M}/gu, "");
}

export function normalizeTyped(typed, target) {
  const allowed = new Set(target);
  return fold([...typed].filter((c) => !SPACING_DIACRITICS.has(c) || allowed.has(c)).join(""));
}

export function levenshtein(a, b) {
  if (a.length < b.length) [a, b] = [b, a];
  let prev = Array.from({ length: b.length + 1 }, (_, i) => i);
  for (let i = 1; i <= a.length; i++) {
    const cur = [i];
    for (let j = 1; j <= b.length; j++) {
      cur.push(Math.min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (a[i - 1] !== b[j - 1] ? 1 : 0)));
    }
    prev = cur;
  }
  return prev[b.length];
}

/** Etiqueta de una tecla de carácter: minúscula y sin tilde (la ñ y la ç son teclas propias). */
export function charLabel(text) {
  const low = text.toLowerCase();
  if (low === "ñ" || low === "ç") return low;
  return fold(low) || text;
}

// --- captura -------------------------------------------------------------------------

const MODIFIERS = {
  ShiftLeft: "shift_l", ShiftRight: "shift_r", ControlLeft: "ctrl", ControlRight: "ctrl",
  AltLeft: "alt", AltRight: "altgr", MetaLeft: "meta", MetaRight: "meta", CapsLock: "capslock",
};

/** (etiqueta, tipo) de un evento de teclado del navegador, como classify_key en Qt. */
export function classifyKey(event) {
  if (MODIFIERS[event.code] || ["Shift", "Control", "Alt", "AltGraph", "Meta", "CapsLock"].includes(event.key)) {
    return [MODIFIERS[event.code] || event.key.toLowerCase(), MOD];
  }
  if (event.key === "Backspace") return ["backspace", BACKSPACE];
  if (event.key === " " || event.code === "Space") return ["space", SPACE];
  if (event.key === "Dead") return ["dead", DEAD];
  if ([...event.key].length === 1) return [charLabel(event.key), CHAR];
  return [`key_${event.key.toLowerCase()}`, OTHER];
}

/** Graba una muestra sobre un texto objetivo. Los tiempos llegan en milisegundos. */
export class Recorder {
  constructor(target, { free = false, textId = "" } = {}) {
    this.target = target;
    this.free = free;
    this.textId = textId;
    this.targetNorm = normalizeTyped(target, target);
    this.t0 = null;
    this.down = new Map();
    this.keys = [];
    this.autorepeats = 0;
    this.blocked = 0;
    this.errorsCommitted = 0;
    this.prevLen = 0;
    this.typed = "";
  }

  press(code, label, kind, t, repeat = false) {
    if (repeat || this.down.has(code)) { this.autorepeats++; return; }
    if (this.t0 === null) this.t0 = t;
    const ks = { label, kind, press: t - this.t0, release: null, code };
    this.down.set(code, ks);
    this.keys.push(ks);
  }

  release(code, t) {
    if (this.t0 === null) return;
    const ks = this.down.get(code);
    if (ks) { ks.release = t - this.t0; this.down.delete(code); }
  }

  /** Suelta todo lo pulsado (se perdió el foco: esas liberaciones no llegarán). */
  dropPressed() { this.down.clear(); }

  block() { this.blocked++; }

  textChanged(typed) {
    this.typed = typed;
    if (this.free) return;
    const norm = normalizeTyped(typed, this.target);
    for (let pos = this.prevLen; pos < norm.length; pos++) {
      if (pos >= this.targetNorm.length || norm[pos] !== this.targetNorm[pos]) this.errorsCommitted++;
    }
    this.prevLen = norm.length;
  }

  /** Muestra con lo escrito; con ``partial`` el texto objetivo se recorta a lo escrito (decisión progresiva). */
  sample({ partial = false } = {}) {
    const target = this.free ? this.typed : partial ? this.target.slice(0, this.typed.length) : this.target;
    const typedNorm = normalizeTyped(this.typed, target);
    const targetNorm = normalizeTyped(target, target);
    const uncorrected = this.free ? 0 : levenshtein(typedNorm, targetNorm);
    return {
      created: new Date().toISOString(),
      textId: this.textId,
      free: this.free,
      typedLength: typedNorm.length,
      errorsCommitted: this.errorsCommitted,
      uncorrected,
      accuracy: Math.max(0, 1 - uncorrected / Math.max(target.length, 1)),
      autorepeats: this.autorepeats,
      blocked: this.blocked,
      keys: this.keys.map((k) => ({ ...k })),
    };
  }
}

// --- características (ksb/features.py) -------------------------------------------------

const dwellOf = (k) => (k.release === null || k.release === undefined ? null : k.release - k.press);

function push(map, key, value) {
  const list = map.get(key);
  if (list) list.push(value); else map.set(key, [value]);
}

function typingChains(keys) {
  const chains = [[]];
  for (const k of keys) {
    if (TYPING.has(k.kind)) chains[chains.length - 1].push(k);
    else if (k.kind === MOD) continue;
    else if (chains[chains.length - 1].length) chains.push([]);
  }
  return chains.filter((c) => c.length >= 2);
}

export function durationMs(keys) {
  if (!keys.length) return 0;
  return Math.max(...keys.map((k) => k.release || k.press)) - keys[0].press;
}

/** Características de una muestra: {dwell, di, diUd, tri, globals, metrics, rhythm}. */
export function extract(sample) {
  const keys = sample.keys;
  const f = { dwell: new Map(), di: new Map(), diUd: new Map(), tri: new Map(), globals: {}, rhythm: [], cache: {} };

  for (const k of keys) {
    const d = dwellOf(k);
    if (d !== null && d > 0 && d < 1000) push(f.dwell, k.label, d);
  }

  const ddChar = [], udChar = [], ddToSpace = [], ddFromSpace = [];
  let overlaps = 0, pairs = 0, pauses = 0;
  for (const chain of typingChains(keys)) {
    for (let i = 0; i + 1 < chain.length; i++) {
      const a = chain[i], b = chain[i + 1];
      const dd = b.press - a.press;
      if (dd <= 0) continue;
      f.rhythm.push(dd);
      if (dd > PAUSE_MS) { pauses++; continue; }
      const key = a.label + SEP + b.label;
      push(f.di, key, dd);
      if (a.release !== null && a.release !== undefined) {
        const ud = b.press - a.release;
        push(f.diUd, key, ud);
        pairs++;
        if (ud < 0) overlaps++;
        if (a.kind === CHAR && b.kind === CHAR) udChar.push(ud);
      }
      if (a.kind === CHAR && b.kind === CHAR) ddChar.push(dd);
      else if (a.kind === CHAR && b.kind === SPACE) ddToSpace.push(dd);
      else if (a.kind === SPACE && b.kind === CHAR) ddFromSpace.push(dd);
    }
    for (let i = 0; i + 2 < chain.length; i++) {
      const a = chain[i], b = chain[i + 1], c = chain[i + 2];
      const ab = b.press - a.press, bc = c.press - b.press;
      if (ab > 0 && ab <= PAUSE_MS && bc > 0 && bc <= PAUSE_MS) {
        push(f.tri, a.label + SEP + b.label + SEP + c.label, c.press - a.press);
      }
    }
  }

  const charDwell = keys.filter((k) => k.kind === CHAR).map(dwellOf).filter((d) => d !== null && d > 0 && d < 1000);
  const spaceDwell = f.dwell.get("space") || [];

  const shifts = keys.filter((k) => k.label === "shift_l" || k.label === "shift_r");
  const shiftLead = [], shiftHold = [];
  keys.forEach((k, i) => {
    if (k.label !== "shift_l" && k.label !== "shift_r") return;
    const d = dwellOf(k);
    if (d !== null && d > 0 && d < 2000) shiftHold.push(d);
    const next = keys.slice(i + 1).find((x) => x.kind === CHAR);
    if (next && next.press - k.press > 0 && next.press - k.press < 1000) shiftLead.push(next.press - k.press);
  });

  const bsLatency = [];
  for (let i = 1; i < keys.length; i++) {
    const prev = keys[i - 1], k = keys[i];
    const gap = k.press - prev.press;
    if (k.kind === BACKSPACE && prev.kind !== BACKSPACE && gap > 0 && gap < 3000) bsLatency.push(gap);
  }
  const backspaces = keys.filter((k) => k.kind === BACKSPACE).length;
  const typingKeys = keys.filter((k) => TYPING.has(k.kind)).length;

  const duration = durationMs(keys);
  const excess = f.rhythm.filter((dd) => dd > PAUSE_MS).reduce((s, dd) => s + dd - PAUSE_MS, 0);
  const active = Math.max(duration - excess, 1);

  const g = f.globals;
  const put = (name, value) => { if (value !== null && value !== undefined) g[name] = value; };
  put("dwell_med", median(charDwell));
  put("dwell_iqr", iqr(charDwell));
  put("dd_med", median(ddChar));
  put("dd_iqr", iqr(ddChar));
  put("ud_med", median(udChar));
  put("overlap", pairs >= 10 ? overlaps / pairs : null);
  put("space_dwell", median(spaceDwell));
  put("dd_to_space", median(ddToSpace));
  put("dd_from_space", median(ddFromSpace));
  put("speed_cpm", typingKeys >= 20 ? (60000 * typingKeys) / active : null);
  if (typingKeys >= 20) {
    put("pause_rate", (100 * pauses) / typingKeys);
    put("bs_rate", (100 * backspaces) / typingKeys);
    if (!sample.free) put("err_rate", (100 * sample.errorsCommitted) / Math.max(sample.typedLength, 1));
  }
  if (shifts.length >= 2) put("shift_right", shifts.filter((s) => s.label === "shift_r").length / shifts.length);
  put("shift_lead", median(shiftLead));
  put("shift_hold", median(shiftHold));
  put("bs_dwell", median(f.dwell.get("backspace") || []));
  put("bs_latency", median(bsLatency));

  // Métricas para mostrar (huella)
  const minutes = Math.max(duration / 60000, 1e-9);
  const allDd = f.rhythm.filter((dd) => dd <= PAUSE_MS);
  const allIqr = iqr(allDd);
  const diMedians = [...f.di].filter(([k, v]) => v.length >= 2 && k.split(SEP).every((x) => [...x].length === 1))
    .map(([k, v]) => [k.split(SEP).join(""), median(v)]);
  f.metrics = {
    chars: sample.typedLength,
    wpm: sample.typedLength / 5 / minutes,
    cpm: (60000 * typingKeys) / active,
    accuracy: (sample.accuracy ?? 1) * 100,
    errorsCommitted: sample.errorsCommitted,
    backspaces,
    dwellMean: charDwell.length ? fmean(charDwell) : 0,
    flightMean: udChar.length ? fmean(udChar) : 0,
    rolloverPct: pairs ? (100 * overlaps) / pairs : 0,
    consistency: allDd.length >= 4 ? 100 * Math.max(0, 1 - allIqr / median(allDd) / 1.5) : 0,
    slowest: [...diMedians].sort((a, b) => b[1] - a[1]).slice(0, 5),
    fastest: [...diMedians].sort((a, b) => a[1] - b[1]).slice(0, 5),
  };
  return f;
}

/** Tiempo de pulsación medio por tecla física (para el mapa de calor) y el carácter que produce. */
export function dwellByCode(samples) {
  const out = new Map();
  for (const s of samples) {
    for (const k of s.keys) {
      const d = dwellOf(k);
      if (!k.code || d === null || d <= 0 || d >= 1000) continue;
      const e = out.get(k.code) || { values: [], label: k.label };
      e.values.push(d);
      out.set(k.code, e);
    }
  }
  return new Map([...out].map(([code, e]) => [code, { dwell: median(e.values), count: e.values.length, label: e.label }]));
}

// --- comparación (ksb/matcher.py) -----------------------------------------------------

export const MIN_SHARED = 10;
export const UD_TOLERANCE_MS = 30;
export const A_THRESHOLD = 1.25;
export const W_RA = 0.55;
export const Z_CAP = 6;
export const S_MIN = 0.035;
export const S_FALLBACK = S_MIN * 2;
export const PRIOR_DOF = 2;
export const PRIOR_MIN_DOF = 4;
export const SLACK = 0.06;
export const SLACK_MULTI = 0.03;
export const SENSITIVITY = { estricto: 1, normal: 2, permisivo: 3 };
// Decisión progresiva (matcher.EARLY_*): terminar en cuanto el resultado está claro
export const EARLY_MIN_KEYS = 60;
export const EARLY_ACCEPT = 0.85;
export const EARLY_MARGIN = 0.20;
export const EARLY_REJECT = 1.40;
const DWELL_MIN_TEST = 3, DWELL_MIN_PROFILE = 6, DWELL_SD_FLOOR = 10;

// nombre -> [suelo absoluto, suelo relativo, peso, descripción]
export const GLOBAL_SPEC = {
  dwell_med: [6, 0.08, 1.5, "Tiempo de pulsación"],
  dwell_iqr: [6, 0.15, 0.7, "Variabilidad de pulsación"],
  dd_med: [10, 0.08, 1.2, "Intervalo entre teclas"],
  dd_iqr: [15, 0.15, 0.7, "Variabilidad del intervalo"],
  ud_med: [12, 0.15, 1.2, "Tiempo de vuelo"],
  overlap: [0.05, 0, 1.2, "Solapamiento de teclas"],
  space_dwell: [8, 0.1, 1.0, "Pulsación de la barra espaciadora"],
  dd_to_space: [12, 0.1, 0.8, "Letra → espacio"],
  dd_from_space: [12, 0.1, 0.8, "Espacio → letra"],
  speed_cpm: [15, 0.06, 1.2, "Velocidad"],
  pause_rate: [1, 0.3, 0.4, "Frecuencia de pausas"],
  bs_rate: [1.5, 0.3, 0.4, "Frecuencia de retrocesos"],
  err_rate: [1.5, 0.3, 0.4, "Frecuencia de errores"],
  shift_right: [0.15, 0, 1.0, "Uso del shift derecho"],
  shift_lead: [15, 0.12, 0.8, "Shift → letra"],
  shift_hold: [15, 0.12, 0.6, "Duración del shift"],
  bs_dwell: [10, 0.12, 0.4, "Pulsación del retroceso"],
  bs_latency: [30, 0.15, 0.4, "Reacción ante un error"],
};

function shared(a, b) {
  const out = [];
  for (const k of a.keys()) if (b.has(k)) out.push(k);
  return out;
}

export function rMeasure(a, b) {
  const keys = shared(a, b);
  const n = keys.length;
  if (n < MIN_SHARED) return null;
  const rank = (m) => {
    const sorted = [...keys].sort((x, y) => m.get(x) - m.get(y) || (x < y ? -1 : x > y ? 1 : 0));
    return new Map(sorted.map((k, i) => [k, i]));
  };
  const ra = rank(a), rb = rank(b);
  let disorder = 0;
  for (const k of keys) disorder += Math.abs(ra.get(k) - rb.get(k));
  const maxDisorder = n % 2 === 0 ? (n * n) / 2 : (n * n - 1) / 2;
  return disorder / maxDisorder;
}

export function aMeasure(a, b, t = A_THRESHOLD) {
  const keys = shared(a, b);
  if (keys.length < MIN_SHARED) return null;
  let similar = 0;
  for (const k of keys) {
    const x = a.get(k), y = b.get(k);
    if (x > 0 && y > 0 && Math.max(x, y) / Math.min(x, y) <= t) similar++;
  }
  return 1 - similar / keys.length;
}

export function aAbsMeasure(a, b, tolMs = UD_TOLERANCE_MS, rel = 0.25) {
  const keys = shared(a, b);
  if (keys.length < MIN_SHARED) return null;
  let similar = 0;
  for (const k of keys) {
    const x = a.get(k), y = b.get(k);
    if (Math.abs(x - y) <= Math.max(tolMs, rel * Math.max(Math.abs(x), Math.abs(y)))) similar++;
  }
  return 1 - similar / keys.length;
}

const medians = (m) => new Map([...m].map(([k, v]) => [k, median(v)]));

function compact(f) {
  if (!f.cache.compact) {
    f.cache.compact = { di: medians(f.di), tri: medians(f.tri), dwell: medians(f.dwell), ud: medians(f.diUd) };
  }
  return f.cache.compact;
}

export function raDistance(x, y) {
  const parts = [
    rMeasure(x.di, y.di), rMeasure(x.tri, y.tri),
    aMeasure(x.di, y.di), aMeasure(x.tri, y.tri), aMeasure(x.dwell, y.dwell),
    rMeasure(x.ud, y.ud), aAbsMeasure(x.ud, y.ud),
  ].filter((p) => p !== null);
  return parts.length ? fmean(parts) : null;
}

export function fuse(ra, z, w = W_RA) {
  if (ra !== null && z !== null) return w * ra + (1 - w) * z;
  return ra !== null ? ra : z;
}

function robustSd(values) {
  if (values.length < 2) return 0;
  const med = median(values);
  const sd = 1.4826 * median(values.map((v) => Math.abs(v - med)));
  return sd > 0 ? sd : pstdev(values);
}

export class Profile {
  constructor(userId, name, features, sessions = null) {
    this.userId = userId;
    this.name = name;
    this.features = features;
    this.compact = features.map(compact);
    this.sessions = sessions && sessions.length === features.length ? [...sessions] : [];
    this.globalStats = {};
    this.dwellStats = new Map();
    this.m = 0; this.s = 0; this.loo = []; this.looParts = [];
    this.multiSession = false;
    this.crossFrac = 0;
    this.population = [];
  }

  static build(userId, name, features, { calibrate = true, sessions = null } = {}) {
    const p = new Profile(userId, name, features, sessions);
    for (const key of Object.keys(GLOBAL_SPEC)) {
      const vals = features.filter((f) => key in f.globals).map((f) => f.globals[key]);
      if (vals.length) p.globalStats[key] = [fmean(vals), vals.length >= 2 ? stdev(vals) : 0];
    }
    const merged = new Map();
    for (const f of features) {
      for (const [k, v] of f.dwell) {
        if (!merged.has(k)) merged.set(k, []);
        merged.get(k).push(...v);
      }
    }
    for (const [label, vals] of merged) {
      if (vals.length >= DWELL_MIN_PROFILE) p.dwellStats.set(label, [median(vals), robustSd(vals), vals.length]);
    }
    if (calibrate) p.calibrate();
    return p;
  }

  calibrate() {
    const n = this.features.length;
    this.looParts = [];
    this.multiSession = new Set(this.sessions).size >= 2;
    let cross = 0;
    for (let i = 0; i < (n >= 2 ? n : 0); i++) {
      let rest = [];
      if (this.multiSession) rest = this.features.filter((_, j) => this.sessions[j] !== this.sessions[i]);
      const crossed = rest.length >= 2;
      if (!crossed) rest = this.features.filter((_, j) => j !== i);
      const sub = Profile.build(this.userId, this.name, rest, { calibrate: false });
      const d = sub.distance(this.features[i]);
      if (d.total !== null) {
        this.looParts.push([d.ra, d.z]);
        if (crossed) cross++;
      }
    }
    this.crossFrac = this.looParts.length ? cross / this.looParts.length : 0;
    this.updateStats();
  }

  statsFor(w) {
    const loo = this.looParts.map(([ra, z]) => fuse(ra, z, w)).filter((d) => d !== null);
    if (!loo.length) return [0.3, 0.06, []];
    return [fmean(loo), this.spread(loo, w), loo];
  }

  spread(loo, w) {
    const own = loo.length >= 3 ? stdev(loo) : null;
    const prior = pooledSpread(this.population, w, this.userId);
    if (prior === null) return own === null ? S_FALLBACK : own;
    if (own === null) return prior;
    const dof = loo.length - 1;
    return Math.sqrt((dof * own ** 2 + PRIOR_DOF * prior ** 2) / (dof + PRIOR_DOF));
  }

  updateStats() { [this.m, this.s, this.loo] = this.statsFor(W_RA); }

  slack() { return SLACK + (SLACK_MULTI - SLACK) * this.crossFrac; }

  threshold(sensitivity = "normal") {
    const k = typeof sensitivity === "number" ? sensitivity : SENSITIVITY[sensitivity] ?? SENSITIVITY.normal;
    return this.m + k * Math.max(this.s, S_MIN) + this.slack();
  }

  zScores(f) {
    const zg = {};
    for (const [key, [mu, sd]] of Object.entries(this.globalStats)) {
      if (!(key in f.globals)) continue;
      const [absFloor, relFloor] = GLOBAL_SPEC[key];
      const sdEff = Math.sqrt(sd ** 2 + absFloor ** 2 + (relFloor * Math.abs(mu)) ** 2);
      zg[key] = Math.min(Math.abs(f.globals[key] - mu) / sdEff, Z_CAP);
    }
    const zd = new Map();
    for (const [label, vals] of f.dwell) {
      if (vals.length < DWELL_MIN_TEST || !this.dwellStats.has(label)) continue;
      const [medP, sdP] = this.dwellStats.get(label);
      zd.set(label, Math.min(Math.abs(median(vals) - medP) / Math.max(sdP, DWELL_SD_FLOOR), Z_CAP));
    }
    return [zg, zd];
  }

  zDistance(f) {
    const [zg, zd] = this.zScores(f);
    const parts = [], weights = [];
    const gk = Object.keys(zg);
    if (gk.length) {
      const w = gk.map((k) => GLOBAL_SPEC[k][2]);
      parts.push(gk.reduce((s, k, i) => s + zg[k] * w[i], 0) / w.reduce((a, b) => a + b, 0));
      weights.push(0.6);
    }
    if (zd.size) {
      const entries = [...zd];
      const w = entries.map(([k]) => Math.min(f.dwell.get(k).length, 10));
      parts.push(entries.reduce((s, [, z], i) => s + z * w[i], 0) / w.reduce((a, b) => a + b, 0));
      weights.push(0.4);
    }
    if (!parts.length) return null;
    const z = parts.reduce((s, p, i) => s + p * weights[i], 0) / weights.reduce((a, b) => a + b, 0);
    return z / (1 + z);
  }

  distance(f) {
    const cx = compact(f);
    const ras = this.compact.map((c) => raDistance(cx, c)).filter((d) => d !== null);
    const ra = ras.length ? fmean(ras) : null;
    const z = this.zDistance(f);
    return { total: fuse(ra, z), ra, z };
  }
}

export function pooledSpread(profiles, w, exclude = null) {
  let num = 0, dof = 0;
  for (const p of profiles) {
    if (p.userId === exclude) continue;
    const loo = p.looParts.map(([ra, z]) => fuse(ra, z, w)).filter((d) => d !== null);
    if (loo.length >= 3) {
      num += (loo.length - 1) * variance(loo);
      dof += loo.length - 1;
    }
  }
  return dof >= PRIOR_MIN_DOF ? Math.sqrt(num / dof) : null;
}

export function shareSpread(population, targets = null) {
  for (const p of targets || population) {
    p.population = population;
    p.updateStats();
  }
}

export function confidence(c) {
  const span = Math.max(c.threshold - c.m, 1e-6);
  return Math.max(0, Math.min(1, 0.5 + (c.threshold - c.distance) / (2 * span))) * 100;
}

export function identify(f, profiles, sensitivity = "normal") {
  const candidates = [];
  for (const p of profiles) {
    const d = p.distance(f);
    if (d.total === null) continue;
    const threshold = p.threshold(sensitivity);
    const c = { userId: p.userId, name: p.name, distance: d.total, threshold, m: p.m, ra: d.ra, z: d.z };
    c.ratio = threshold > 0 ? d.total / threshold : Infinity;
    c.accepted = d.total <= threshold;
    c.confidence = confidence(c);
    candidates.push(c);
  }
  candidates.sort((a, b) => a.ratio - b.ratio);
  const accepted = candidates.filter((c) => c.accepted);
  return {
    candidates,
    best: accepted[0] || null,
    ambiguous: accepted.length >= 2 && accepted[1].ratio - accepted[0].ratio < 0.08,
  };
}

/** "accept", "reject" o null (seguir escribiendo) para una muestra a medio escribir (matcher.early_decision). */
export function earlyDecision(result, typedKeys, claimedId = null) {
  if (typedKeys < EARLY_MIN_KEYS || !result.candidates.length) return null;
  const [best] = result.candidates;
  const second = result.candidates.length > 1 ? result.candidates[1].ratio : Infinity;
  const clear = best.ratio <= EARLY_ACCEPT && second - best.ratio >= EARLY_MARGIN;
  if (claimedId !== null) {
    const claimed = result.candidates.find((c) => c.userId === claimedId);
    if (!claimed) return null;
    if (clear && best === claimed) return "accept";
    return claimed.ratio >= EARLY_REJECT ? "reject" : null;
  }
  if (clear) return "accept";
  return best.ratio >= EARLY_REJECT ? "reject" : null;
}

/** Sesiones: una pausa de más de 2 horas entre muestras abre una nueva (service.sessions_of). */
export function sessionsOf(samples) {
  const order = samples.map((_, i) => i).sort((a, b) => (samples[a].created || "").localeCompare(samples[b].created || ""));
  const labels = new Array(samples.length).fill("");
  let current = 0, last = null;
  for (const i of order) {
    const t = Date.parse(samples[i].created);
    if (last !== null && (Number.isNaN(t) || t - last > 2 * 3600 * 1000)) current++;
    labels[i] = `s${current}`;
    if (!Number.isNaN(t)) last = t;
  }
  return labels;
}

// --- suplantaciones (ksb/liveness.py, sin réplicas) ----------------------------------------

/** Avisos de las muestras no válidas o sospechosas, en español; la demo pasa los de su idioma. */
export const MESSAGES = {
  robotic: "Ritmo demasiado regular para una persona.",
  repeated: "Muchas pulsaciones duran exactamente lo mismo.",
  instant: "Teclas que se sueltan instantáneamente.",
  accuracy: "La precisión ha sido del {accuracy} % (mínimo {min} %).",
  fewKeys: "Se han registrado muy pocas pulsaciones.",
  focus: "No se han podido medir los tiempos de pulsación (¿se perdió el foco?).",
};

/** Motivos por los que la muestra parece escrita por un programa ([] si parece humana). */
export function livenessProblems(sample, msg = MESSAGES) {
  const out = [];
  const typing = sample.keys.filter((k) => k.kind === CHAR || k.kind === SPACE);
  const dd = [];
  for (let i = 1; i < typing.length; i++) {
    const gap = typing[i].press - typing[i - 1].press;
    if (gap > 0 && gap < 1500) dd.push(gap);
  }
  if (dd.length >= 40 && pstdev(dd) / fmean(dd) < 0.12) out.push(msg.robotic);
  const dwell = sample.keys.filter((k) => TYPING.has(k.kind)).map(dwellOf).filter((d) => d !== null);
  if (dwell.length >= 40) {
    const counts = new Map();
    for (const d of dwell) counts.set(Math.round(d), (counts.get(Math.round(d)) || 0) + 1);
    if (Math.max(...counts.values()) / dwell.length > 0.35) out.push(msg.repeated);
    if (dwell.filter((d) => d < 8).length / dwell.length > 0.25) out.push(msg.instant);
  }
  return out;
}

/** Motivo para rechazar una muestra (precisión, pocas teclas, foco perdido) o null. */
export function qualityProblem(sample, minAccuracy = 80, msg = MESSAGES) {
  if (!sample.free && sample.accuracy * 100 < minAccuracy) {
    return msg.accuracy.replace("{accuracy}", Math.round(sample.accuracy * 100)).replace("{min}", minAccuracy);
  }
  if (sample.keys.filter((k) => TYPING.has(k.kind)).length < 60) return msg.fewKeys;
  if (sample.keys.filter((k) => k.release !== null).length < 0.8 * sample.keys.length) {
    return msg.focus;
  }
  return null;
}
