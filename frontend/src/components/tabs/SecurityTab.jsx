import React, { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Camera, Circle, Maximize2, X, Wifi, Aperture, Move, Activity } from "lucide-react";
import { useSystem } from "@/context/SystemContext";
import { CameraPlayer } from "@/components/CameraPlayer";
import { toast } from "sonner";

export const SecurityTab = () => {
  const { state, api, act } = useSystem();
  const [full, setFull] = useState(false);
  if (!state) return null;
  const cam = state.camera;

  const snapshot = async () => {
    await api.cameraSnapshot();
    toast.success("Snapshot captured", { description: `${cam.name} · saved to UniFi Protect` });
  };

  const simulateMotion = async () => {
    const res = await api.triggerEvent("motion");
    if (res.state) act(Promise.resolve(res.state));
    const fired = res.fired || [];
    toast(fired.length ? `Motion → ran: ${fired.join(", ")}` : "Motion detected", {
      description: fired.length ? "Event automation triggered" : "No motion automations set",
    });
  };

  return (
    <div className="p-4 sm:p-6 space-y-5 pb-8" data-testid="security-tab">
      <div>
        <p className="text-[11px] font-semibold uppercase tracking-wider" style={{ color: "var(--c4-cyan)" }}>Ubiquiti UniFi Protect</p>
        <h1 className="font-head text-2xl font-extrabold tracking-tight">Security Camera</h1>
      </div>

      <div className="glass rounded-2xl p-4">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2.5">
            <div className="w-9 h-9 rounded-xl flex items-center justify-center" style={{ background: "rgba(6,182,212,0.15)" }}>
              <Camera className="w-4.5 h-4.5" style={{ color: "var(--c4-cyan)" }} />
            </div>
            <div>
              <p className="font-semibold text-sm">{cam.name}</p>
              <p className="text-[11px] flex items-center gap-1" style={{ color: cam.online ? "var(--c4-emerald)" : "var(--c4-rose)" }}>
                <Wifi className="w-3 h-3" /> {cam.online ? "Online" : "Offline"} · {cam.resolution}
              </p>
            </div>
          </div>
          <button data-testid="camera-fullscreen-btn" onClick={() => setFull(true)} className="w-9 h-9 rounded-xl glass-elevated flex items-center justify-center active:scale-95 transition">
            <Maximize2 className="w-4 h-4" />
          </button>
        </div>

        <div className="rounded-xl overflow-hidden aspect-video" data-testid="camera-feed">
          <CameraPlayer />
        </div>

        <div className="grid grid-cols-2 gap-2 mt-3">
          <button data-testid="camera-snapshot-btn" onClick={snapshot} className="glass-elevated rounded-xl py-2.5 flex items-center justify-center gap-2 text-sm font-semibold active:scale-95 transition">
            <Aperture className="w-4 h-4" style={{ color: "var(--c4-cyan)" }} /> Snapshot
          </button>
          <button data-testid="camera-pantilt-btn" onClick={() => toast("Pan / Tilt", { description: "Repositioning camera…" })} className="glass-elevated rounded-xl py-2.5 flex items-center justify-center gap-2 text-sm font-semibold active:scale-95 transition">
            <Move className="w-4 h-4" style={{ color: "var(--c4-indigo)" }} /> Pan / Tilt
          </button>
        </div>
      </div>

      <div className="glass rounded-2xl p-4 flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <div className="w-9 h-9 rounded-xl flex items-center justify-center" style={{ background: cam.motion ? "rgba(239,68,68,0.15)" : "rgba(255,255,255,0.05)" }}>
            <Circle className="w-4 h-4" style={{ color: cam.motion ? "var(--c4-rose)" : "var(--c4-muted)" }} />
          </div>
          <div>
            <p className="font-semibold text-sm">Motion Detection</p>
            <p className="text-[11px]" style={{ color: "var(--c4-muted)" }}>{cam.motion ? "Motion detected now" : "No recent motion"}</p>
          </div>
        </div>
        <button
          data-testid="simulate-motion-btn"
          onClick={simulateMotion}
          className="rounded-xl px-3 py-2 flex items-center gap-2 text-xs font-semibold active:scale-95 transition"
          style={{ background: "rgba(239,68,68,0.14)", color: "var(--c4-rose)", border: "1px solid rgba(239,68,68,0.3)" }}
        >
          <Activity className="w-4 h-4" /> Simulate motion
        </button>
      </div>

      <AnimatePresence>
        {full && (
          <motion.div
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            className="fixed inset-0 z-50 flex items-center justify-center p-4"
            style={{ background: "rgba(10,13,20,0.95)" }}
            data-testid="camera-fullscreen-modal"
          >
            <button data-testid="close-fullscreen-btn" onClick={() => setFull(false)} className="absolute top-5 right-5 w-10 h-10 rounded-xl glass flex items-center justify-center z-10">
              <X className="w-5 h-5" />
            </button>
            <div className="w-full max-w-4xl aspect-video rounded-2xl overflow-hidden glow-ring">
              <CameraPlayer full />
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
};

export default SecurityTab;
