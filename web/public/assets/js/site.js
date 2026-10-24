// Comportamiento general de la web: tema, idioma, configuración, descargas, valoraciones y contacto.

import { CONFIG } from "./config.js";
import { mountDemo } from "./demo.js";
import { LANG, LANGUAGES, LOCALE, t, tn } from "./i18n.js";

const THEME_KEY = "keybio-theme";
const LANG_KEY = "keybio-lang";          // idioma elegido en el menú (no se vuelve a sugerir otro)
const TURNSTILE_SRC = "https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit";
const HCAPTCHA_SRC = "https://js.hcaptcha.com/1/api.js?render=explicit&recaptchacompat=off";
const WEB3FORMS_URL = "https://api.web3forms.com/submit";

const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];

function storageGet(key) {
  try { return localStorage.getItem(key); } catch { return null; }
}
function storageSet(key, value) {
  try { localStorage.setItem(key, value); } catch { /* sin almacenamiento: solo dura esta visita */ }
}

// --- tema ------------------------------------------------------------------------------------

function setupTheme() {
  const root = document.documentElement;
  const saved = storageGet(THEME_KEY);
  if (saved === "light" || saved === "dark") root.dataset.theme = saved;
  const btn = $("#theme-toggle");
  if (!btn) return;
  const current = () => root.dataset.theme || (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
  const label = () => btn.setAttribute("aria-label", t(current() === "dark" ? "theme.toLight" : "theme.toDark"));
  label();
  btn.addEventListener("click", () => {
    const next = current() === "dark" ? "light" : "dark";
    root.dataset.theme = next;
    storageSet(THEME_KEY, next);
    label();
  });
}

// --- idioma -----------------------------------------------------------------------------------

// --- recuento de visitas --------------------------------------------------------------------------

// Cloudflare Web Analytics: sin cookies ni datos que identifiquen a nadie (ver la página de
// privacidad). Solo en la web publicada: ni las copias locales ni las pruebas cuentan como visitas.
function setupAnalytics() {
  const a = CONFIG.analytics;
  if (!a || !a.token || location.hostname !== a.host) return;
  const script = document.createElement("script");
  script.type = "module";   // como lo da Cloudflare
  script.src = "https://static.cloudflareinsights.com/beacon.min.js";
  script.setAttribute("data-cf-beacon", JSON.stringify({ token: a.token }));
  document.body.append(script);
}

// --- enlaces dentro de la página ------------------------------------------------------------------

// #demo, #descargar…: se desplaza a la sección sin escribir el «#…» en la dirección, que queda
// limpia. Si se llega con uno (desde la política de privacidad o un enlace compartido), se va a esa
// sección y se quita de la dirección. Sin JavaScript, los enlaces funcionan como siempre.
function setupCleanAnchors() {
  const reduceMotion = matchMedia("(prefers-reduced-motion: reduce)").matches;
  const go = (id, smooth) => {
    const target = document.getElementById(id);
    if (!target || target.closest("svg")) return false;
    target.scrollIntoView({ behavior: smooth && !reduceMotion ? "smooth" : "auto", block: "start" });
    if (!target.hasAttribute("tabindex")) target.setAttribute("tabindex", "-1");
    target.focus({ preventScroll: true });   // el teclado y los lectores de pantalla siguen ahí
    return true;
  };
  document.addEventListener("click", (e) => {
    const a = e.target.closest('a[href^="#"]');
    if (!a || e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
    const id = decodeURIComponent(a.getAttribute("href").slice(1));
    if (id && go(id, true)) e.preventDefault();
  });
  if (location.hash.length > 1) {
    const id = decodeURIComponent(location.hash.slice(1));
    history.replaceState(history.state, "", location.pathname + location.search);
    go(id, false);
  }
}

function setupLanguage() {
  const menu = $(".lang-menu");
  if (!menu) return;
  for (const a of $$("a[data-lang]", menu)) a.addEventListener("click", () => storageSet(LANG_KEY, a.dataset.lang));
  document.addEventListener("click", (e) => { if (!menu.contains(e.target)) menu.open = false; });
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") menu.open = false; });
  suggestLanguage(menu);
}

/** Si el navegador prefiere otro idioma de la web, lo ofrece (en ese idioma) sin redirigir. */
function suggestLanguage(menu) {
  if (storageGet(LANG_KEY)) return;
  const codes = new Map(LANGUAGES.map((l) => [l.code, l]));
  const wanted = (navigator.languages || [navigator.language]).map((x) => String(x).toLowerCase().split("-")[0]);
  const first = wanted.find((c) => codes.has(c));
  if (!first || first === LANG) return;
  const other = codes.get(first);
  const link = $(`a[data-lang="${first}"]`, menu);
  const bar = document.createElement("div");
  bar.className = "lang-suggest";
  bar.lang = first;
  const text = document.createElement("span");
  text.textContent = other.suggest;
  const go = document.createElement("a");
  go.className = "btn primary";
  go.href = link.getAttribute("href");
  go.hreflang = first;
  go.textContent = other.switch;
  go.addEventListener("click", () => storageSet(LANG_KEY, first));
  const close = document.createElement("button");
  close.type = "button";
  close.className = "btn ghost";
  close.textContent = other.dismiss;
  close.addEventListener("click", () => { storageSet(LANG_KEY, LANG); bar.remove(); });
  bar.append(text, go, close);
  document.body.prepend(bar);
}

// --- textos que dependen de la configuración -------------------------------------------------

function applyConfig() {
  for (const el of $$("[data-config]")) {
    const value = CONFIG[el.dataset.config];
    el.textContent = value === "" || value === undefined ? (el.dataset.fallback || "[pendiente]") : String(value);
  }
}

function setupDownloads() {
  const d = CONFIG.downloads;
  for (const a of $$("[data-download]")) {
    if (d.enabled) {
      a.href = d.base + d[a.dataset.download];
      a.removeAttribute("aria-disabled");
    } else {
      a.removeAttribute("href");
      a.setAttribute("aria-disabled", "true");
    }
  }
  $("#downloads-soon")?.toggleAttribute("hidden", d.enabled);
  const langs = $("#program-languages");
  if (langs) {
    const names = new Map(LANGUAGES.map((l) => [l.code, l.name]));
    langs.textContent = CONFIG.programLanguages.map((c) => names.get(c) || c).join(", ");
  }
}

// --- valoraciones ------------------------------------------------------------------------------

function starRow(n, total = 5) {
  const wrap = document.createElement("span");
  wrap.className = "stars";
  wrap.setAttribute("aria-label", t("ratings.stars", { n: n.toLocaleString(LOCALE), total }));
  for (let i = 1; i <= total; i++) {
    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.setAttribute("class", `icon star${i <= Math.round(n) ? " filled" : ""}`);
    svg.setAttribute("aria-hidden", "true");
    const use = document.createElementNS("http://www.w3.org/2000/svg", "use");
    use.setAttribute("href", "#i-star");
    svg.append(use);
    wrap.append(svg);
  }
  return wrap;
}

function renderRatings(data) {
  const summary = $("#ratings-summary");
  const list = $("#ratings-list");
  summary.replaceChildren();
  if (!data.count) {
    summary.textContent = t("ratings.none");
  } else {
    const avg = document.createElement("div");
    avg.className = "ratings-average";
    const num = document.createElement("strong");
    num.textContent = data.average.toLocaleString(LOCALE, { minimumFractionDigits: 1 });
    const count = document.createElement("span");
    count.className = "muted";
    count.textContent = tn("ratings.count", data.count);
    avg.append(num, starRow(data.average), count);
    const bars = document.createElement("ul");
    bars.className = "ratings-bars";
    for (let s = 5; s >= 1; s--) {
      const n = data.histogram[s - 1];
      const li = document.createElement("li");
      const lab = document.createElement("span");
      lab.textContent = `${s} ★`;
      const bar = document.createElement("span");
      bar.className = "bar";
      const fill = document.createElement("span");
      fill.className = "bar-fill";
      fill.style.width = `${data.count ? (100 * n) / data.count : 0}%`;
      bar.append(fill);
      const val = document.createElement("span");
      val.className = "muted";
      val.textContent = String(n);
      li.append(lab, bar, val);
      bars.append(li);
    }
    summary.append(avg, bars);
  }
  list.replaceChildren(...data.comments.map((c) => {
    const li = document.createElement("li");
    const head = document.createElement("div");
    head.className = "comment-head";
    const who = document.createElement("strong");
    who.textContent = c.name || t("ratings.anonymous");
    const when = document.createElement("span");
    when.className = "muted small";
    when.textContent = new Date(`${c.date}T12:00:00`).toLocaleDateString(LOCALE, { day: "numeric", month: "long", year: "numeric" });
    head.append(who, starRow(c.stars), when);
    const text = document.createElement("p");
    text.textContent = c.comment;   // siempre como texto: nunca se interpreta como HTML
    li.append(head, text);
    return li;
  }));
}

function loadScript(src) {
  return new Promise((resolve, reject) => {
    const el = document.createElement("script");
    el.src = src;
    el.async = true;
    el.onload = resolve;
    el.onerror = reject;
    document.head.append(el);
  });
}

async function setupRatings() {
  const form = $("#rating-form");
  const status = $("#rating-status");
  if (!form) return;
  const disable = (text) => {
    for (const el of form.elements) el.disabled = true;
    status.textContent = text;
    status.className = "form-status muted";
  };

  let data = null;
  try {
    const res = await fetch("/api/ratings", { headers: { Accept: "application/json" } });
    if (res.ok && (res.headers.get("Content-Type") || "").includes("json")) data = await res.json();
  } catch { /* sin servidor (vista previa local) */ }
  if (!data) {
    $("#ratings-summary").textContent = t("ratings.closed");
    disable(t("common.soon"));
    return;
  }
  renderRatings(data);
  if (!CONFIG.turnstileSiteKey) { disable(t("common.soon")); return; }

  let token = "";
  let widget = null;
  const comment = $("#rating-comment");
  const counter = $("#rating-count");
  comment.addEventListener("input", () => { counter.textContent = `${[...comment.value].length}/600`; });

  // Turnstile se carga solo cuando alguien empieza a valorar
  form.addEventListener("focusin", async () => {
    if (widget !== null) return;
    widget = "cargando";
    try {
      await loadScript(TURNSTILE_SRC);
      widget = window.turnstile.render("#rating-captcha", {
        sitekey: CONFIG.turnstileSiteKey, language: "auto", theme: "auto",
        callback: (value) => { token = value; },
        "expired-callback": () => { token = ""; },
      });
    } catch {
      widget = null;
      status.textContent = t("ratings.captchaError");
    }
  });

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const stars = Number(new FormData(form).get("stars"));
    if (!stars) { status.textContent = t("ratings.chooseStars"); status.className = "form-status bad"; return; }
    if (!token) { status.textContent = t("ratings.waitCaptcha"); status.className = "form-status warn"; return; }
    const submit = $("button[type=submit]", form);
    submit.disabled = true;
    status.textContent = t("common.sending");
    status.className = "form-status muted";
    try {
      const res = await fetch("/api/ratings", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ stars, name: $("#rating-name").value, comment: comment.value, token }),
      });
      const out = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(ratingError(out));
      form.reset();
      counter.textContent = "0/600";
      status.textContent = t(out.pending ? "ratings.thanksPending" : "ratings.thanks");
      status.className = "form-status good";
      const fresh = await fetch("/api/ratings").then((r) => r.json()).catch(() => null);
      if (fresh) renderRatings(fresh);
    } catch (err) {
      status.textContent = err.message;
      status.className = "form-status bad";
    } finally {
      submit.disabled = false;
      token = "";
      if (window.turnstile && typeof widget === "string" && widget !== "cargando") window.turnstile.reset(widget);
    }
  });
}

/** Mensaje de error de la API de valoraciones en el idioma de la página. */
function ratingError(out) {
  const key = `ratings.error.${out.code}`;
  const text = t(key, { name: 40, comment: 600 });
  return text !== key ? text : t("ratings.sendError");
}

// --- contacto -----------------------------------------------------------------------------------

function setupContact() {
  const form = $("#contact-form");
  const status = $("#contact-status");
  if (!form) return;
  if (!CONFIG.web3formsKey) {
    for (const el of form.elements) el.disabled = true;
    status.textContent = t("contact.closed");
    status.className = "form-status muted";
    return;
  }
  // Comprobación antispam (hCaptcha): se carga solo cuando alguien empieza a escribir
  let token = "";
  let widget = null;
  if (CONFIG.hcaptchaSiteKey) {
    form.addEventListener("focusin", async () => {
      if (widget !== null) return;
      widget = "cargando";
      try {
        await loadScript(`${HCAPTCHA_SRC}&hl=${LANG}`);
        const dark = document.documentElement.dataset.theme === "dark"
          || (!document.documentElement.dataset.theme && matchMedia("(prefers-color-scheme: dark)").matches);
        widget = window.hcaptcha.render("contact-captcha", {
          sitekey: CONFIG.hcaptchaSiteKey, theme: dark ? "dark" : "light",
          callback: (value) => { token = value; },
          "expired-callback": () => { token = ""; },
        });
      } catch {
        widget = null;
        status.textContent = t("ratings.captchaError");
        status.className = "form-status bad";
      }
    });
  }

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    if (!form.reportValidity()) return;
    if (CONFIG.hcaptchaSiteKey && !token) {
      status.textContent = t("contact.needCaptcha");
      status.className = "form-status warn";
      return;
    }
    const data = new FormData(form);
    const submit = $("button[type=submit]", form);
    submit.disabled = true;
    status.textContent = t("common.sending");
    status.className = "form-status muted";
    try {
      const res = await fetch(WEB3FORMS_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "application/json" },
        body: JSON.stringify({
          access_key: CONFIG.web3formsKey,
          subject: `Mensaje desde la web de KeyBio (${LANG})`,   // para saber en qué idioma responder
          from_name: "Web de KeyBio",
          name: data.get("name"),
          email: data.get("email"),
          message: data.get("message"),
          botcheck: data.get("botcheck") ? true : "",
          ...(token ? { "h-captcha-response": token } : {}),
        }),
      });
      const out = await res.json().catch(() => ({}));
      if (!res.ok || !out.success) throw new Error(t("contact.sendError"));
      form.reset();
      status.textContent = t("contact.sent");
      status.className = "form-status good";
    } catch (err) {
      status.textContent = err.message;
      status.className = "form-status bad";
    } finally {
      submit.disabled = false;
      token = "";
      if (window.hcaptcha && widget !== null && widget !== "cargando") window.hcaptcha.reset(widget);
    }
  });
}

// --- arranque -------------------------------------------------------------------------------------

setupTheme();
setupCleanAnchors();
setupAnalytics();
setupLanguage();
applyConfig();
setupDownloads();
const demo = $("#demo-app");
if (demo) mountDemo(demo);
setupRatings();
setupContact();
