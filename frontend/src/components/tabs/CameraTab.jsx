import React, { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Maximize2, X, Film, Camera, Loader2 } from "lucide-react";
import { captureStill, shareStill } from "@/lib/snapshot";
import { toast } from "sonner";
import { CameraPlayer } from "@/components/CameraPlayer";
import { PtzControls } from "@/components/PtzControls";

// Recordings stay in UniFi Protect; hand off to its app, or its App Store page if it isn't installed.
const PROTECT_URL = "unifi-protect://";
const STORE_URL = "https://apps.apple.com/app/id1392492235";
let launcher;
const nativeLauncher = () => {
  const cap = window.Capacitor;
  if (!cap?.isNativePlatform?.() || !cap.isPluginAvailable?.("AppLauncher")) return null;
  return (launcher ??= cap.registerPlugin("AppLauncher"));
};

const openProtect = async () => {
  const native = nativeLauncher();
  if (native) {
    try {
      const { value } = await native.canOpenUrl({ url: PROTECT_URL });
      await native.openUrl({ url: value ? PROTECT_URL : STORE_URL });
    } catch {
      toast.error("Couldn't open UniFi Protect");
    }
    return;
  }
  const t = setTimeout(() => {
    if (document.visibilityState === "visible") window.location.href = STORE_URL;
  }, 1800);
  document.addEventListener("visibilitychange", () => clearTimeout(t), { once: true });
  window.location.href = PROTECT_URL;
};

const SnapshotButton = () => {
  const [busy, setBusy] = useState(false);
  const snap = async () => {
    setBusy(true);
    try {
      const still = await captureStill(document.querySelector("[data-testid='camera-live'] video"), "Front Entry");
      const how = await shareStill(still);
      if (how === "downloaded") toast.success("Snapshot saved");
    } catch (e) {
      toast.error(e?.message || "Couldn't take a snapshot");
    } finally {
      setBusy(false);
    }
  };
  return (
    <button onClick={snap} disabled={busy} aria-label="Snapshot" data-testid="camera-snapshot-btn"
      className="absolute bottom-3 right-[3.75rem] w-10 h-10 rounded-xl flex items-center justify-center active:scale-95 transition-transform disabled:opacity-60"
      style={{ background: "rgba(5,7,12,0.65)", backdropFilter: "blur(12px)" }}>
      {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <Camera className="w-4 h-4" />}
    </button>
  );
};

export const CameraTab = () => {
  const [full, setFull] = useState(false);
  return (
    <div className="p-4 sm:p-6 space-y-5 pb-8 max-w-3xl mx-auto" data-testid="camera-tab">
      <div>
        <p className="text-[11px] font-semibold uppercase tracking-[0.2em]" style={{ color: "var(--c4-amber)" }}>Camera · G6 PTZ</p>
        <h1 className="font-head text-3xl sm:text-4xl font-bold tracking-tight">Front Entry</h1>
      </div>

      <div className="relative rounded-2xl overflow-hidden aspect-video glass" data-testid="camera-live">
        <CameraPlayer camId="cam_front" />
        <SnapshotButton />
        <button onClick={() => setFull(true)} aria-label="Full screen" data-testid="camera-fullscreen-btn"
          className="absolute bottom-3 right-3 w-10 h-10 rounded-xl flex items-center justify-center active:scale-95 transition-transform"
          style={{ background: "rgba(5,7,12,0.65)", backdropFilter: "blur(12px)" }}>
          <Maximize2 className="w-4 h-4" />
        </button>
      </div>

      <button onClick={openProtect} data-testid="camera-recordings-btn"
        className="w-full glass rounded-2xl p-4 flex items-center gap-4 text-left active:scale-[0.98] transition-transform">
        <span className="w-12 h-12 rounded-xl flex items-center justify-center shrink-0" style={{ background: "var(--c4-primary)", color: "#fff" }}>
          <Film className="w-6 h-6" />
        </span>
        <div>
          <p className="font-semibold">View recordings</p>
          <p className="text-xs" style={{ color: "var(--c4-muted)" }}>Opens the UniFi Protect app for playback and events</p>
        </div>
      </button>

      <PtzControls />

      <AnimatePresence>
        {full && (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            className="fixed inset-0 z-[70] bg-black" data-testid="camera-fullscreen">
            <CameraPlayer full camId="cam_front" />
            <button onClick={() => setFull(false)} aria-label="Close" data-testid="camera-fullscreen-close"
              className="absolute top-4 right-4 w-11 h-11 rounded-xl flex items-center justify-center"
              style={{ background: "rgba(5,7,12,0.7)" }}>
              <X className="w-5 h-5" />
            </button>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
};

export default CameraTab;
