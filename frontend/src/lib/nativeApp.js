// Inside the Casa Vestry iOS app the panel is loaded from the mini-PC, so native tools are reached by handing
// off to the app's built-in page (capacitor://localhost), which then returns to the panel.
const FLAG = "casa_app";

if (new URLSearchParams(window.location.search).get("casaapp") === "1") {
  try { sessionStorage.setItem(FLAG, "1"); } catch { /* private mode */ }
}

export const isInApp = () => {
  try {
    if (sessionStorage.getItem(FLAG) === "1") return true;
  } catch { /* ignore */ }
  return !!window.Capacitor?.isNativePlatform?.();
};

export const openViaApp = (action) => {
  window.location.href = `capacitor://localhost/?${action}`;
};
