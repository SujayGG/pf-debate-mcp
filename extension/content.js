// Bridge between the hub page and the extension. Only answers the hub's own window, on the hub's origin.
const VERSION = chrome.runtime.getManifest().version;

window.addEventListener("message", (event) => {
  if (event.source !== window || event.origin !== location.origin) return;
  const msg = event.data || {};
  if (msg.type === "pfhub-ping") {
    window.postMessage({ type: "pfhub-ready", version: VERSION }, location.origin);
  } else if (msg.type === "pfhub-req") {
    chrome.runtime.sendMessage({ op: msg.op, args: msg.args }, (resp) => {
      const r = resp || { ok: false, error: chrome.runtime.lastError?.message || "no answer" };
      window.postMessage({ type: "pfhub-res", id: msg.id, ...r }, location.origin);
    });
  }
});
window.postMessage({ type: "pfhub-ready", version: VERSION }, location.origin);
