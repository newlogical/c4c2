import React, { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Camera, Circle, Maximize2, X, Wifi, Aperture, Move } from "lucide-react";
import { useSystem } from "@/context/SystemContext";
import { toast } from "sonner";

const CAM = "https://images.unsplash.com/photo-1787659601659-399e4ea21429?crop=entropy&cs=srgb&fm=jpg&q=85&w=1200";

const Feed = ({ full }) => (
  <div className="relative w-full h-full overflow-hidden">
    <img src={CAM} alt="Camera feed" className="w-full h-full object-cover" style={{ filter: "saturate(1.1) brightness(0.9)" }} />
    {/* scanline / live overlay */}
    <div className="absolute inset-0 pointer-events-none" style={{ background: "linear-gradient(180deg, rgba(6,182,212,0.06), transparent 30%, transparent 70%, rgba(10,13,20,0.4))" }} />
    <div className="absolute top-3 left-3 flex items-center gap-1.5 px-2 py-1 rounded-md" style={{ background: "rgba(10,13,20,0.7)" }}>
      <Circle className="w-2.5 h-2.5 animate-motion" fill="#EF4444" color="#EF4444" />
      <span className="text-[10px] font-mono font-semibold tracking-wide">LIVE</span>
    </div>
    <div className="absolute top-3 right-3 px-2 py-1 rounded-md font-mono text-[10px]" style={{ background: "rgba(10,13,20,0.7)", color: "var(--c4-cyan)" }}>
      UniFi Protect · {full ? "FULLSCREEN" : "4K"}
    </div>
    <div className="absolute bottom-3 left-3 font-mono text-[10px]" style={{ color: "rgba(255,255,255,0.7)" }}>
      {new Date().toLocaleString()}
    </div>
  </div>
);

export const SecurityTab = () => {
  const { state, api } = useSystem();
  const [full, setFull] = useState(false);
  if (!state) return null;
  const cam = state.camera;

  const snapshot = async () => {
    await api.cameraSnapshot();
    toast.success("Snapshot captured", { description: `${cam.name} · saved to UniFi Protect` });
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
          <Feed />
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
        <span className="text-[11px] font-semibold" style={{ color: "var(--c4-emerald)" }}>Armed</span>
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
              <Feed full />
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
};

export default SecurityTab;
