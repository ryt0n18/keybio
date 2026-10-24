// Valoraciones de la web (Cloudflare Pages Function, base de datos D1 con binding DB).
//
//   GET  /api/ratings  media, reparto por estrellas y últimos comentarios aprobados
//   POST /api/ratings  {stars, name?, comment?, token}  guarda una valoración
//
// Variables secretas: TURNSTILE_SECRET (antispam) e IP_SALT (la IP se guarda solo como
// HMAC con esta sal, para limitar a una valoración al día sin conservar la IP).
// Los comentarios quedan pendientes hasta que se aprueban a mano (ver web/README.md).

export const LIMITS = { name: 40, comment: 600, body: 4096, perDay: 1 };

export const SQL = {
  summary: "SELECT COUNT(*) AS n, AVG(stars) AS avg FROM ratings WHERE status != 'rejected'",
  histogram: "SELECT stars, COUNT(*) AS n FROM ratings WHERE status != 'rejected' GROUP BY stars",
  comments: "SELECT name, stars, comment, substr(created, 1, 10) AS date FROM ratings "
    + "WHERE status = 'approved' AND comment != '' ORDER BY id DESC LIMIT 20",
  recent: "SELECT COUNT(*) AS n FROM ratings WHERE ip_hash = ?1 AND created > datetime('now', '-1 day')",
  insert: "INSERT INTO ratings (stars, name, comment, status, ip_hash) VALUES (?1, ?2, ?3, ?4, ?5)",
};

const TURNSTILE_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify";

function json(data, status = 200, headers = {}) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { "Content-Type": "application/json; charset=utf-8", "X-Content-Type-Options": "nosniff",
               "Cache-Control": "no-store", ...headers },
  });
}

/** Error con un código que la web traduce a su idioma (``error`` queda como texto de respaldo). */
function fail(code, status, error) {
  return json({ error, code }, status);
}

export async function onRequestGet({ env }) {
  if (!env.DB) return fail("not_configured", 503, "Las valoraciones no están configuradas.");
  const summary = await env.DB.prepare(SQL.summary).first();
  const histogram = (await env.DB.prepare(SQL.histogram).all()).results;
  const comments = (await env.DB.prepare(SQL.comments).all()).results;
  return json({
    count: summary.n,
    average: summary.avg === null ? null : Math.round(summary.avg * 10) / 10,
    histogram: [1, 2, 3, 4, 5].map((s) => histogram.find((r) => r.stars === s)?.n || 0),
    comments,
  }, 200, { "Cache-Control": "public, max-age=60" });
}

export async function onRequestPost({ request, env }) {
  if (!env.DB || !env.TURNSTILE_SECRET || !env.IP_SALT) {
    return fail("not_configured", 503, "Las valoraciones no están configuradas.");
  }
  // Solo desde la propia web (evita que otras páginas envíen valoraciones en nombre del visitante)
  if (request.headers.get("Origin") !== new URL(request.url).origin) {
    return fail("origin", 403, "Origen no permitido.");
  }
  if (!(request.headers.get("Content-Type") || "").startsWith("application/json")) {
    return fail("format", 415, "Formato no válido.");
  }
  // Un envío que anuncia ser enorme se rechaza sin leerlo (no se llega a cargar en memoria)
  if (Number(request.headers.get("Content-Length")) > LIMITS.body) {
    return fail("too_long", 413, "La valoración es demasiado larga.");
  }
  const raw = await request.text();
  if (raw.length > LIMITS.body) return fail("too_long", 413, "La valoración es demasiado larga.");
  let data;
  try {
    data = JSON.parse(raw);
  } catch {
    return fail("format", 400, "Formato no válido.");
  }
  if (!data || typeof data !== "object") return fail("format", 400, "Formato no válido.");

  const { stars } = data;
  if (!Number.isInteger(stars) || stars < 1 || stars > 5) {
    return fail("stars", 400, "Elige entre 1 y 5 estrellas.");
  }
  const name = clean(data.name, LIMITS.name, false);
  const comment = clean(data.comment, LIMITS.comment, true);
  if (name === null || comment === null) {
    return fail("lengths", 400, `El nombre admite hasta ${LIMITS.name} caracteres y el comentario hasta ${LIMITS.comment}.`);
  }

  const ip = request.headers.get("CF-Connecting-IP") || "";
  if (!(await turnstileOk(env.TURNSTILE_SECRET, data.token, ip))) {
    return fail("captcha", 403, "No se ha podido comprobar que no eres un robot. Inténtalo de nuevo.");
  }
  const ipHash = await hmacHex(env.IP_SALT, ip);
  const recent = await env.DB.prepare(SQL.recent).bind(ipHash).first();
  if (recent.n >= LIMITS.perDay) {
    return fail("daily_limit", 429, "Ya has enviado una valoración hoy. ¡Gracias!");
  }
  // Solo estrellas: cuenta para la media al momento. Con comentario: espera a la moderación.
  const status = comment ? "pending" : "approved";
  await env.DB.prepare(SQL.insert).bind(stars, name, comment, status, ipHash).run();
  return json({ ok: true, pending: status === "pending" }, 201);
}

/** Texto limpio (sin caracteres de control; saltos de línea solo si ``multiline``) o null si es demasiado largo. */
export function clean(value, max, multiline) {
  if (value === undefined || value === null) return "";
  if (typeof value !== "string") return null;
  let text = value.normalize("NFC").replace(/\r\n?/g, "\n");
  text = multiline
    ? text.replace(/[\u0000-\u0009\u000b-\u001f\u007f-\u009f​-‏‪-‮⁦-⁩]/g, "")
        .replace(/\n{3,}/g, "\n\n")
    : text.replace(/[\u0000-\u001f\u007f-\u009f​-‏‪-‮⁦-⁩]/g, " ").replace(/ {2,}/g, " ");
  text = text.trim();
  return [...text].length <= max ? text : null;
}

async function turnstileOk(secret, token, ip) {
  if (typeof token !== "string" || !token || token.length > 2048) return false;
  const body = new FormData();
  body.append("secret", secret);
  body.append("response", token);
  if (ip) body.append("remoteip", ip);
  try {
    const res = await fetch(TURNSTILE_URL, { method: "POST", body });
    const out = await res.json();
    return out.success === true;
  } catch {
    return false;
  }
}

async function hmacHex(secret, message) {
  const enc = new TextEncoder();
  const key = await crypto.subtle.importKey("raw", enc.encode(secret), { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
  const sig = new Uint8Array(await crypto.subtle.sign("HMAC", key, enc.encode(message)));
  return [...sig].map((b) => b.toString(16).padStart(2, "0")).join("");
}
