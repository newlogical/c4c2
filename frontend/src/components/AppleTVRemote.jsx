import React from "react";
import { motion, AnimatePresence } from "framer-motion";
import { X, ChevronUp, ChevronDown, ChevronLeft, ChevronRight, Play, Pause, ArrowLeft, Menu, Volume2, VolumeX, Mic } from "lucide-react";
import { useSystem } from "@/context/SystemContext";
import { toast } from "sonner";

export const AppleTVRemote = ({ open, onClose, source }) => {
  const { api } = useSystem();
  if (!source) return null;

  const send = async (key) => {
    await api.remote(source.id, key);
    toast(`${source.name}`, { description: key, duration: 900 });
  };

  const RingBtn = ({ dir, icon: Icon, testid }) => (
    <button
      data-testid={testid}
      onClick={() => send(dir)}
      className="absolute flex items-center justify-center active:bg-white/10 rounded-full transition"
      style={{
        ...(dir === "up" && { top: 8, left: "50%", transform: "translateX(-50%)" }),
        ...(dir === "down" && { bottom: 8, left: "50%", transform: "translateX(-50%)" }),
        ...(dir === "left" && { left: 8, top: "50%", transform: "translateY(-50%)" }),
        ...(dir === "right" && { right: 8, top: "50%", transform: "translateY(-50%)" }),
        width: 44,
        height: 44,
      }}
    >
      <Icon className="w-6 h-6" style={{ color: "var(--c4-text)" }} />
    </button>
  );

  return (
    <AnimatePresence>
      {open && (
        <>
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
            className="fixed inset-0 z-40"
            style={{ background: "rgba(10,13,20,0.85)" }}
          />
          <motion.div
            initial={{ opacity: 0, y: 40, scale: 0.96 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 40, scale: 0.96 }}
            className="fixed left-1/2 top-1/2 z-50 -translate-x-1/2 -translate-y-1/2 w-[300px]"
            data-testid="apple-tv-remote"
          >
            <div className="glass-elevated rounded-[32px] p-6 shadow-2xl" style={{ boxShadow: "0 20px 60px rgba(0,0,0,0.6)" }}>
              <div className="flex items-center justify-between mb-5">
                <div>
                  <p className="font-head font-bold text-sm">{source.name}</p>
                  <p className="text-[11px]" style={{ color: "var(--c4-muted)" }}>{source.location} · Remote</p>
                </div>
                <button data-testid="close-remote-btn" onClick={onClose} className="w-8 h-8 rounded-lg glass flex items-center justify-center">
                  <X className="w-4 h-4" />
                </button>
              </div>

              {/* Directional ring */}
              <div className="relative mx-auto mb-5" style={{ width: 200, height: 200 }}>
                <div className="absolute inset-0 rounded-full" style={{ background: "var(--c4-surface)", border: "1px solid var(--c4-border-med)" }} />
                <RingBtn dir="up" icon={ChevronUp} testid="remote-up" />
                <RingBtn dir="down" icon={ChevronDown} testid="remote-down" />
                <RingBtn dir="left" icon={ChevronLeft} testid="remote-left" />
                <RingBtn dir="right" icon={ChevronRight} testid="remote-right" />
                <button
                  data-testid="remote-select"
                  onClick={() => send("select")}
                  className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 rounded-full font-head font-semibold text-sm active:scale-95 transition"
                  style={{ width: 96, height: 96, background: "var(--c4-elevated)", border: "1px solid var(--c4-border-med)", color: "var(--c4-text)" }}
                >
                  OK
                </button>
              </div>

              <div className="grid grid-cols-2 gap-3 mb-3">
                <button data-testid="remote-menu" onClick={() => send("menu")} className="glass rounded-xl py-3 flex items-center justify-center gap-2 text-sm active:scale-95 transition">
                  <ArrowLeft className="w-4 h-4" /> Back
                </button>
                <button data-testid="remote-home" onClick={() => send("home")} className="glass rounded-xl py-3 flex items-center justify-center gap-2 text-sm active:scale-95 transition">
                  <Menu className="w-4 h-4" /> Home
                </button>
              </div>

              <div className="grid grid-cols-4 gap-3">
                <button data-testid="remote-playpause" onClick={() => send("play_pause")} className="glass rounded-xl py-3 flex items-center justify-center active:scale-95 transition">
                  <Play className="w-4 h-4" />
                </button>
                <button data-testid="remote-pause" onClick={() => send("pause")} className="glass rounded-xl py-3 flex items-center justify-center active:scale-95 transition">
                  <Pause className="w-4 h-4" />
                </button>
                <button data-testid="remote-volup" onClick={() => send("volume_up")} className="glass rounded-xl py-3 flex items-center justify-center active:scale-95 transition">
                  <Volume2 className="w-4 h-4" />
                </button>
                <button data-testid="remote-voldown" onClick={() => send("volume_down")} className="glass rounded-xl py-3 flex items-center justify-center active:scale-95 transition">
                  <VolumeX className="w-4 h-4" />
                </button>
              </div>

              <button
                data-testid="remote-siri"
                onClick={() => send("siri")}
                className="w-full mt-3 rounded-xl py-3 flex items-center justify-center gap-2 text-sm font-semibold active:scale-95 transition"
                style={{ background: "rgba(99,102,241,0.15)", color: "var(--c4-indigo)", border: "1px solid rgba(99,102,241,0.3)" }}
              >
                <Mic className="w-4 h-4" /> Hold for Siri
              </button>
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
};

export default AppleTVRemote;
