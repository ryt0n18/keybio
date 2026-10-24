// Configuración pública de la web. Todo lo que hay aquí lo ve cualquiera: no pongas secretos.
// Mientras un valor esté vacío, la sección correspondiente se muestra como «próximamente».

export const CONFIG = {
  version: "2.1.2",

  // Responsable de la web (pie de página y política de privacidad)
  owner: "Álvaro Ruiz (ryt0n18)",
  year: 2026,

  // Descargas: se activan cuando haya una versión pública de los ejecutables
  downloads: {
    enabled: true,
    base: "https://github.com/ryt0n18/keybio/releases/download/v2.1.2/",
    windowsSetup: "KeyBio-2.1.2-setup.exe",
    windowsZip: "KeyBio-windows-x64.zip",
    linuxDeb: "KeyBio-2.1.2-linux-amd64.deb",
    linuxTar: "KeyBio-linux-x64.tar.gz",
    macDmg: "KeyBio-2.1.2-macos-arm64.dmg",
  },

  // Idiomas de la interfaz del programa (códigos de web/i18n/build.py); se muestran en «Descargar»
  programLanguages: ["es", "en", "ca", "gl", "eu", "fr", "pt", "de", "it"],

  // Clave pública (site key) de Cloudflare Turnstile para las valoraciones
  turnstileSiteKey: "0x4AAAAAAFi4gaJF24sdXJTe",   // widget «KeyBio web» (dominio keybio.pages.dev)

  // Clave de acceso de Web3Forms para el formulario de contacto (es pública por diseño)
  web3formsKey: "dcc5a1a1-b921-4cc4-9389-e25fd9a9ef6b",
  // hCaptcha del formulario de contacto: clave compartida del plan gratuito de Web3Forms (se exige
  // activándolo en el panel de Web3Forms: «Spam protection» → hCaptcha)
  hcaptchaSiteKey: "50b2fe65-b00b-4b9e-ad62-3ba471098be2",

  // Recuento de visitas (Cloudflare Web Analytics, sin cookies). El token es público: solo dice a
  // Cloudflare de qué web son las visitas. Solo se carga en la web publicada (host).
  analytics: { token: "2afb8dfc9c934afd9956aa15a8859c5f", host: "keybio.pages.dev" },
};
