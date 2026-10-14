import React, { useEffect, useRef, useState } from "react";
import { ChevronUp, ChevronDown, ChevronLeft, ChevronRight, ZoomIn, ZoomOut, Home, Play, Square, Crosshair } from "lucide-react";
import { toast } from "sonner";
import { useSystem } from "@/context/SystemContext";

const SPEED = 500;
const btn = "glass-elevated rounded-xl flex items-center justify-center active:scale-95 transition select-none touch-none";

const HoldButton = ({ testid, vec, onMove, children, className = "" }) => {
  const timer = useRef(null);
  const start = (e) => {
    e.preventDefault();
    onMove(vec);
    timer.current = setInterval(() => onMove(vec), 1000);
  };
  const stop = () => {
    if (!timer.current) return;
    clearInterval(timer.current);
    timer.current = null;
    onMove({ pan: 0, tilt: 0, zoom: 0 });
  };
  useEffect(() => () => timer.current && clearInterval(timer.current), []);
  return (
    <button data-testid={testid} onPointerDown={start} onPointerUp={stop} onPointerLeave={stop} onPointerCancel={stop} className={`${btn} ${className}`}>
      {children}
    </button>
  );
};

const DPad = ({ onMove }) => (
  <div className="grid grid-cols-3 gap-1.5 w-[132px]" data-testid="ptz-dpad">
    <span />
    <HoldButton testid="ptz-up" vec={{ pan: 0, tilt: SPEED, zoom: 0 }} onMove={onMove} className="h-10"><ChevronUp className="w-5 h-5" /></HoldButton>
    <span />
    <HoldButton testid="ptz-left" vec={{ pan: -SPEED, tilt: 0, zoom: 0 }} onMove={onMove} className="h-10"><ChevronLeft className="w-5 h-5" /></HoldButton>
    <div className="h-10 rounded-xl flex items-center justify-center" style={{ color: "var(--c4-muted)" }}><Crosshair className="w-4 h-4" /></div>
    <HoldButton testid="ptz-right" vec={{ pan: SPEED, tilt: 0, zoom: 0 }} onMove={onMove} className="h-10"><ChevronRight className="w-5 h-5" /></HoldButton>
    <span />
    <HoldButton testid="ptz-down" vec={{ pan: 0, tilt: -SPEED, zoom: 0 }} onMove={onMove} className="h-10"><ChevronDown className="w-5 h-5" /></HoldButton>
    <span />
  </div>
);

export const PtzControls = () => {
  const { api, refresh } = useSystem();
  const [presets, setPresets] = useState([]);
  const [patrolling, setPatrolling] = useState(false);

  useEffect(() => { api.ptzPresets().then((r) => setPresets(r.presets)).catch(() => {}); }, [api]);

  const run = async (fn, okMsg) => {
    try {
      const r = await fn();
      if (okMsg) toast.success(`${okMsg}${r?.status === "simulated" ? " (demo)" : ""}`);
      refresh?.();
      return true;
    } catch (e) {
      toast.error(e?.response?.data?.detail || "PTZ command failed");
      return false;
    }
  };
  const onMove = (v) => api.ptzMove(v).catch((e) => toast.error(e?.response?.data?.detail || "Move failed"));
  const togglePatrol = async () => {
    if (await run(() => api.ptzPatrol({ start: !patrolling, slot: 0 }), patrolling ? "Patrol stopped" : "Patrol started")) setPatrolling(!patrolling);
  };

  return (
    <div className="glass rounded-2xl p-4 space-y-3" data-testid="ptz-controls">
      <div className="flex items-center justify-between">
        <p className="text-xs font-semibold tracking-wide uppercase" style={{ color: "var(--c4-muted)" }}>Aim camera · G6 PTZ</p>
        <button data-testid="ptz-patrol-btn" onClick={togglePatrol} className="rounded-lg px-3 py-1.5 text-[11px] font-semibold flex items-center gap-1.5 glass-elevated active:scale-95 transition" style={{ color: patrolling ? "var(--c4-rose)" : "var(--c4-emerald)" }}>
          {patrolling ? <Square className="w-3.5 h-3.5" /> : <Play className="w-3.5 h-3.5" />} {patrolling ? "Stop patrol" : "Start patrol"}
        </button>
      </div>
      <div className="flex flex-wrap gap-2" data-testid="ptz-presets">
        {presets.map((p) => (
          <button key={p.slot} data-testid={`ptz-preset-${p.slot}`} onClick={() => run(() => api.ptzGoto(p.slot), `Moving to ${p.name}`)} className="glass-elevated rounded-xl px-3 py-2 text-xs font-semibold flex items-center gap-1.5 active:scale-95 transition">
            {p.slot === -1 && <Home className="w-3.5 h-3.5" />} {p.name}
          </button>
        ))}
      </div>
      <div className="flex items-center gap-4 pt-1">
        <DPad onMove={onMove} />
        <div className="flex flex-col gap-1.5">
          <HoldButton testid="ptz-zoom-in" vec={{ pan: 0, tilt: 0, zoom: SPEED }} onMove={onMove} className="w-11 h-10"><ZoomIn className="w-5 h-5" /></HoldButton>
          <HoldButton testid="ptz-zoom-out" vec={{ pan: 0, tilt: 0, zoom: -SPEED }} onMove={onMove} className="w-11 h-10"><ZoomOut className="w-5 h-5" /></HoldButton>
        </div>
        <p className="text-[10px] leading-snug flex-1" style={{ color: "var(--c4-muted)" }} data-testid="ptz-experimental-note">
          Hold to move. Arrows & zoom are <b>experimental</b> (unofficial Protect API, needs a local Protect user).
        </p>
      </div>
    </div>
  );
};

export default PtzControls;
