/**
 * FinkiBOT floating chat widget.
 *
 * Self-contained, no dependencies — same pattern as Intercom/Tawk.to/Crisp: a floating
 * bubble button that toggles a small iframe pointing at FinkiBOT's own "/widget" page
 * (see frontend/src/routes/widget.tsx). Because the chat itself lives entirely inside
 * that iframe, on FinkiBOT's own origin, this script never talks to the FinkiBOT API
 * directly — no CORS configuration on the backend is needed for this to work.
 *
 * Usage: include this script on any page (WordPress "Custom HTML"/"Insert Headers and
 * Footers" block, theme footer, or via the finkibot-widget WordPress plugin in this
 * same folder) and set which FinkiBOT deployment it should open, either via a data
 * attribute on the <script> tag itself:
 *
 *   <script src="https://YOUR-FINKIBOT-DOMAIN/finkibot-widget.js"
 *           data-finkibot-url="https://YOUR-FINKIBOT-DOMAIN"></script>
 *
 * or by setting window.FINKIBOT_URL before this script loads. Falls back to the
 * script's own origin (the src of this very file) if neither is set — the common case
 * when this file is served directly by the FinkiBOT frontend itself.
 */
(function () {
  "use strict";

  function resolveFinkiBotUrl() {
    var currentScript = document.currentScript;
    if (currentScript && currentScript.dataset.finkibotUrl) {
      return currentScript.dataset.finkibotUrl.replace(/\/$/, "");
    }
    if (window.FINKIBOT_URL) {
      return String(window.FINKIBOT_URL).replace(/\/$/, "");
    }
    if (currentScript && currentScript.src) {
      try {
        return new URL(currentScript.src).origin;
      } catch (e) {
        /* fall through */
      }
    }
    return null;
  }

  var FINKIBOT_URL = resolveFinkiBotUrl();
  if (!FINKIBOT_URL) {
    console.error(
      "[FinkiBOT widget] Could not determine the FinkiBOT URL — set data-finkibot-url on the <script> tag, or window.FINKIBOT_URL before it loads.",
    );
    return;
  }

  // Avoid injecting twice if the snippet ends up on the page more than once (e.g. a
  // theme footer include plus a manually-added Custom HTML block).
  if (window.__finkibotWidgetLoaded) return;
  window.__finkibotWidgetLoaded = true;

  var OPEN = false;

  var style = document.createElement("style");
  style.textContent = [
    "#finkibot-widget-bubble{position:fixed;bottom:20px;right:20px;width:60px;height:60px;",
    "border-radius:50%;background:#6b21a8;color:#fff;border:none;cursor:pointer;",
    "box-shadow:0 4px 16px rgba(0,0,0,.25);z-index:2147483000;display:flex;",
    "align-items:center;justify-content:center;transition:transform .15s ease;padding:0;}",
    "#finkibot-widget-bubble:hover{transform:scale(1.06);}",
    "#finkibot-widget-bubble svg{width:28px;height:28px;}",
    "#finkibot-widget-panel{position:fixed;bottom:92px;right:20px;width:380px;",
    "max-width:calc(100vw - 32px);height:560px;max-height:calc(100vh - 120px);",
    "border-radius:16px;overflow:hidden;box-shadow:0 12px 40px rgba(0,0,0,.3);",
    "z-index:2147483000;display:none;background:#fff;}",
    "#finkibot-widget-panel.finkibot-open{display:block;}",
    "#finkibot-widget-panel iframe{width:100%;height:100%;border:0;display:block;}",
    "@media (max-width:480px){#finkibot-widget-panel{bottom:0;right:0;width:100vw;",
    "height:100vh;max-height:100vh;border-radius:0;}}",
  ].join("");
  document.head.appendChild(style);

  var bubble = document.createElement("button");
  bubble.id = "finkibot-widget-bubble";
  bubble.type = "button";
  bubble.setAttribute("aria-label", "Отвори чат со FinkiBOT");
  bubble.innerHTML =
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">' +
    '<path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>';

  var panel = document.createElement("div");
  panel.id = "finkibot-widget-panel";

  var iframe = null;

  function ensureIframe() {
    if (iframe) return;
    iframe = document.createElement("iframe");
    iframe.src = FINKIBOT_URL + "/widget";
    iframe.title = "FinkiBOT";
    panel.appendChild(iframe);
  }

  function setOpen(next) {
    OPEN = next;
    ensureIframe(); // lazy: only load the chat once the visitor actually opens it
    panel.classList.toggle("finkibot-open", OPEN);
    bubble.setAttribute("aria-expanded", String(OPEN));
  }

  bubble.addEventListener("click", function () {
    setOpen(!OPEN);
  });

  document.body.appendChild(panel);
  document.body.appendChild(bubble);
})();