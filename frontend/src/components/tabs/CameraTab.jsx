import React, { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Maximize2, X, Film } from "lucide-react";
import { toast } from "sonner";
import { CameraPlayer } from "@/components/CameraPlayer";
import { PtzControls } from "@/components/PtzControls";

// Recordings stay in UniFi Protect; this hands off to its app (iOS/Android register unifi-protect://).
const openProtect = () => {
  const t = setTimeout(() => {
    if (document.visibilityState === "visible") toast.info("Install the UniFi Protect app to view recordings");
  }, 1800);
  document.addEventListener("visibilitychange", () => clearTimeout(t), { once: true });
  window.location.href = "unifi-protect://";
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
        <button onClick={() => setFull(true)} aria-label="Full screen" data-testid="camera-fullscreen-btn"
          className="absolute top-3 right-3 w-10 h-10 rounded-xl flex items-center justify-center active:scale-95 transition-transform"
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
