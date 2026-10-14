import React, { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Camera, Circle, Maximize2, X, Wifi, Aperture, Move, Activity, Shield, ShieldOff, Film, Trash2 } from "lucide-react";
import { useSystem } from "@/context/SystemContext";
import { PtzControls } from "@/components/PtzControls";
import { CameraPlayer } from "@/components/CameraPlayer";
import { toast } from "sonner";

const STILL = "https://images.unsplash.com/photo-1787659601659-399e4ea21429?crop=entropy&cs=srgb&fm=jpg&q=85&w=800";

export const SecurityTab = () => {
  const { state, api, act } = useSystem();
  const [full, setFull] = useState(false);
  const [selected, setSelected] = useState("cam_front");
  const [clips, setClips] = useState([]);
  const loadClips = async () => { try { setClips(await api.getClips()); } catch (e) {} };
  useEffect(() => { loadClips(); }, []);
  if (!state) return null;
  const cam = state.camera;
  const cameras = state.cameras || [];
  const primary = cameras.find((c) => c.id === selected) || cameras[0] || cam;

  const snapshot = async () => {
    await api.cameraSnapshot();
    toast.success("Snapshot captured", { description: `${primary.name} · saved to UniFi Protect` });
  };

  const motionOn = async (camId) => {
    const res = await api.cameraMotion(camId);
    if (res.state) act(Promise.resolve(res.state));
    setSelected(camId);
    loadClips();
    const fired = res.fired || [];
    toast(fired.length ? `Motion → ran: ${fired.join(", ")}` : "Motion detected", {
      description: `${cameras.find((c) => c.id === camId)?.name || camId}${fired.length ? " · automation triggered" : ""}`,
    });
  };
  const simulateMotion = () => motionOn(selected);

  const playClip = (clip) => {
    setSelected(clip.camera_id);
    setFull(true);
    toast(`Playing ${clip.camera_name}`, { description: new Date(clip.ts).toLocaleString() });
  };
  const clearClips = async () => { await api.clearClips(); loadClips(); };

  const toggleArm = async () => {
    await act(api.setArm(!cam.armed));
    toast(!cam.armed ? "Cameras armed" : "Cameras disarmed");
  };

  return (
    <div className="p-4 sm:p-6 space-y-5 pb-8" data-testid="security-tab">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-wider" style={{ color: "var(--c4-cyan)" }}>Ubiquiti UniFi Protect</p>
          <h1 className="font-head text-2xl font-extrabold tracking-tight">Cameras</h1>
        </div>
        <button data-testid="camera-fullscreen-btn" onClick={() => setFull(true)} className="w-9 h-9 rounded-xl glass-elevated flex items-center justify-center active:scale-95 transition">
          <Maximize2 className="w-4 h-4" />
        </button>
      </div>

      <div className="glass rounded-2xl p-4">
        <div className="flex items-center gap-2.5 mb-3">
          <div className="w-9 h-9 rounded-xl flex items-center justify-center" style={{ background: "rgba(6,182,212,0.15)" }}>
            <Camera className="w-4.5 h-4.5" style={{ color: "var(--c4-cyan)" }} />
          </div>
          <div>
            <p className="font-semibold text-sm" data-testid="primary-camera-name">{primary.name}</p>
            <p className="text-[11px] flex items-center gap-1" style={{ color: primary.motion ? "var(--c4-rose)" : "var(--c4-emerald)" }}>
              <Wifi className="w-3 h-3" /> {primary.motion ? "Motion now" : "Online"}
            </p>
          </div>
        </div>

        <div className="rounded-xl overflow-hidden aspect-video" data-testid="camera-feed">
          <CameraPlayer camId={selected} />
        </div>

        <div className="grid grid-cols-4 gap-2 mt-3" data-testid="camera-grid">
          {cameras.map((cm) => (
            <div key={cm.id} className="relative">
              <button
                data-testid={`camera-thumb-${cm.id}`}
                onClick={() => setSelected(cm.id)}
                className="w-full rounded-lg overflow-hidden aspect-video relative block"
                style={{ outline: selected === cm.id ? "2px solid var(--c4-cyan)" : cm.motion ? "2px solid var(--c4-rose)" : "1px solid var(--c4-border)" }}
              >
                <img src={STILL} alt={cm.name} className="w-full h-full object-cover" style={{ filter: "brightness(0.65)" }} />
                {cm.motion && <span className="absolute inset-0 animate-motion" style={{ boxShadow: "inset 0 0 0 2px var(--c4-rose)" }} />}
                <span className="absolute bottom-0.5 left-1 text-[8px] font-semibold truncate max-w-[90%]" style={{ color: "#fff", textShadow: "0 1px 2px #000" }}>{cm.name}</span>
              </button>
              <button data-testid={`camera-motion-${cm.id}`} onClick={() => motionOn(cm.id)} className="absolute top-0.5 right-0.5 w-5 h-5 rounded-md flex items-center justify-center" style={{ background: "rgba(10,13,20,0.7)" }} title="Simulate motion">
                <Activity className="w-3 h-3" style={{ color: "var(--c4-rose)" }} />
              </button>
            </div>
          ))}
        </div>

        <div className="grid grid-cols-2 gap-2 mt-3">
          <button data-testid="camera-snapshot-btn" onClick={snapshot} className="glass-elevated rounded-xl py-2.5 flex items-center justify-center gap-2 text-sm font-semibold active:scale-95 transition">
            <Aperture className="w-4 h-4" style={{ color: "var(--c4-cyan)" }} /> Snapshot
          </button>
          <button data-testid="simulate-motion-btn" onClick={simulateMotion} className="glass-elevated rounded-xl py-2.5 flex items-center justify-center gap-2 text-sm font-semibold active:scale-95 transition" style={{ color: "var(--c4-rose)" }}>
            <Activity className="w-4 h-4" /> Simulate motion
          </button>
        </div>
      </div>

      {selected === "cam_front" && <PtzControls />}

      <div className="glass rounded-2xl p-4" data-testid="clips-timeline">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <Film className="w-4 h-4" style={{ color: "var(--c4-indigo)" }} />
            <p className="font-semibold text-sm">Recent clips</p>
          </div>
          {clips.length > 0 && (
            <button data-testid="clear-clips-btn" onClick={clearClips} className="text-[11px] flex items-center gap-1" style={{ color: "var(--c4-muted)" }}>
              <Trash2 className="w-3.5 h-3.5" /> Clear
            </button>
          )}
        </div>
        {clips.length === 0 ? (
          <p className="text-xs" style={{ color: "var(--c4-muted)" }}>No motion clips yet. Trigger motion on a camera to capture one.</p>
        ) : (
          <div className="space-y-2">
            {clips.map((clip) => (
              <button
                key={clip.id}
                data-testid={`clip-${clip.id}`}
                onClick={() => playClip(clip)}
                className="w-full flex items-center gap-3 rounded-xl p-2 active:scale-[0.99] transition"
                style={{ background: "var(--c4-bg)", border: "1px solid var(--c4-border)" }}
              >
                <div className="w-16 h-10 rounded-lg overflow-hidden shrink-0 relative">
                  <img src={STILL} alt="" className="w-full h-full object-cover" style={{ filter: "brightness(0.6)" }} />
                  <span className="absolute inset-0 flex items-center justify-center"><Film className="w-4 h-4" style={{ color: "#fff" }} /></span>
                </div>
                <div className="flex-1 text-left min-w-0">
                  <p className="text-xs font-semibold truncate">{clip.camera_name}</p>
                  <p className="text-[10px]" style={{ color: "var(--c4-muted)" }}>{new Date(clip.ts).toLocaleString()}</p>
                </div>
                <span className="text-[11px] font-semibold shrink-0" style={{ color: "var(--c4-cyan)" }}>Play</span>
              </button>
            ))}
          </div>
        )}
      </div>

      <div className="glass rounded-2xl p-4 flex items-center justify-between" data-testid="arm-card">
        <div className="flex items-center gap-2.5">
          <div className="w-9 h-9 rounded-xl flex items-center justify-center" style={{ background: cam.armed ? "rgba(239,68,68,0.15)" : "rgba(16,185,129,0.12)" }}>
            {cam.armed ? <Shield className="w-4.5 h-4.5" style={{ color: "var(--c4-rose)" }} /> : <ShieldOff className="w-4.5 h-4.5" style={{ color: "var(--c4-emerald)" }} />}
          </div>
          <div>
            <p className="font-semibold text-sm">{cam.armed ? "Armed" : "Disarmed"}{state.away ? " · Away" : ""}</p>
            <p className="text-[11px]" style={{ color: "var(--c4-muted)" }}>{cam.armed ? "Recording motion on all cameras" : "Not monitoring"}</p>
          </div>
        </div>
        <button
          data-testid="arm-toggle"
          onClick={toggleArm}
          className="w-11 h-6 rounded-full relative transition shrink-0"
          style={{ background: cam.armed ? "var(--c4-rose)" : "rgba(255,255,255,0.12)" }}
        >
          <span className="absolute top-0.5 w-5 h-5 rounded-full bg-white transition-all" style={{ left: cam.armed ? "22px" : "2px" }} />
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
              <CameraPlayer full camId={selected} />
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
};

export default SecurityTab;
