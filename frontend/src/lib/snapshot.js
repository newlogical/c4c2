// Grab a still from the live <video>, stamp date/time, then share it (iOS app → native sheet, browser → Web Share, else download).
const loadImg = (src) => new Promise((res, rej) => {
  const img = new Image();
  img.crossOrigin = "anonymous";
  img.onload = () => res(img);
  img.onerror = () => rej(new Error("Couldn't load the camera picture"));
  img.src = src;
});

export const captureStill = async (video, label) => {
  let frame = video;
  let w = video?.videoWidth;
  let h = video?.videoHeight;
  if (!video || video.readyState < 2 || !w) {
    if (video?.dataset.demo !== "true" || !video.poster) throw new Error("The live feed isn't playing yet");
    frame = await loadImg(video.poster);
    w = frame.naturalWidth;
    h = frame.naturalHeight;
  }
  const c = document.createElement("canvas");
  c.width = w;
  c.height = h;
  const ctx = c.getContext("2d");
  ctx.drawImage(frame, 0, 0, w, h);
  const now = new Date();
  const text = `${label} · ${now.toLocaleDateString()} ${now.toLocaleTimeString()}`;
  const fs = Math.max(14, Math.round(h * 0.035));
  ctx.font = `600 ${fs}px ui-monospace, Menlo, monospace`;
  const pad = Math.round(fs * 0.5);
  const tw = ctx.measureText(text).width;
  ctx.fillStyle = "rgba(0,0,0,0.6)";
  ctx.fillRect(pad, h - fs - pad * 3, tw + pad * 2, fs + pad * 2);
  ctx.fillStyle = "#fff";
  ctx.textBaseline = "top";
  ctx.fillText(text, pad * 2, h - fs - pad * 2);
  const dataUrl = c.toDataURL("image/jpeg", 0.9);
  const stamp = now.toISOString().slice(0, 19).replace(/[:T]/g, "-");
  return { dataUrl, name: `camera-${stamp}.jpg` };
};

const nativePlugins = () => {
  const cap = window.Capacitor;
  if (!cap?.isNativePlatform?.() || !cap.isPluginAvailable?.("Share") || !cap.isPluginAvailable?.("Filesystem")) return null;
  window.__capSnap ??= { Share: cap.registerPlugin("Share"), Filesystem: cap.registerPlugin("Filesystem") };
  return window.__capSnap;
};

const withTimeout = (p, ms) => Promise.race([p, new Promise((_, rej) => setTimeout(() => rej(new Error("native-timeout")), ms))]);

// Returns "shared" | "downloaded" | "cancelled"
export const shareStill = async ({ dataUrl, name }) => {
  const native = nativePlugins();
  let uri = null;
  if (native) {
    // Native tools may not answer pages loaded from the mini-PC; fall back to the web share sheet if so.
    uri = await withTimeout(native.Filesystem.writeFile({ path: name, data: dataUrl.split(",")[1], directory: "CACHE" }), 2500)
      .then((r) => r.uri).catch(() => null);
  }
  if (uri) {
    try {
      await native.Share.share({ title: "Camera snapshot", files: [uri] });
      return "shared";
    } catch (e) {
      if (/cancel/i.test(e?.message || "")) return "cancelled";
      throw e;
    }
  }
  const blob = await (await fetch(dataUrl)).blob();
  const file = new File([blob], name, { type: "image/jpeg" });
  if (navigator.canShare?.({ files: [file] })) {
    try {
      await navigator.share({ files: [file], title: "Camera snapshot" });
      return "shared";
    } catch (e) {
      if (e?.name === "AbortError") return "cancelled";
    }
  }
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 2000);
  return "downloaded";
};
