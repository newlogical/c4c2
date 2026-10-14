import React from "react";
import { createPortal } from "react-dom";
import { motion, AnimatePresence } from "framer-motion";
import { X, ChevronUp, ChevronDown, ChevronLeft, ChevronRight, Play, Pause, ArrowLeft, Menu, Volume2, VolumeX, Mic } from "lucide-react";
import { useSystem } from "@/context/SystemContext";
import { toast } from "sonner";

export const AppleTVRemote = ({ open, onClose, source }) => {
  const { api } = useSystem();
  if (!source) return null;

  const send = async (key) => {
    await api.remote(source.id, key);
    toast(`${source.name}`, { description: key, duration: 900, position: "bottom-center" });
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
        width: 56,
        height: 56,
      }}
    >
      <Icon className="w-6 h-6" style={{ color: "var(--c4-text)" }} />
    </button>
  );

  return createPortal(
    <AnimatePresence>
      {open && (
        <motion.div
          initial={{ opacity: 0, y: 40 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: 40 }}
          transition={{ duration: 0.22, ease: "easeOut" }}
          className="fixed inset-0 z-[70] flex flex-col"
          style={{ background: "var(--c4-bg)", paddingTop: "env(safe-area-inset-top)", paddingBottom: "env(safe-area-inset-bottom)" }}
          data-testid="apple-tv-remote"
        >
          <div className="flex items-center justify-between px-5 py-4">
            <div>
              <p className="font-head font-bold text-lg">{source.name}</p>
              <p className="text-xs" style={{ color: "var(--c4-muted)" }}>{source.location} · Remote</p>
            </div>
            <button data-testid="close-remote-btn" onClick={onClose} className="w-12 h-12 rounded-2xl glass flex items-center justify-center active:scale-95 transition" aria-label="Close remote">
              <X className="w-6 h-6" />
            </button>
          </div>
          <div className="flex-1 overflow-y-auto flex items-center justify-center px-6 pb-6">
            <div className="w-full max-w-sm">
              {/* Directional ring */}
              <div className="relative mx-auto mb-8" style={{ width: 260, height: 260 }}>
                <div className="absolute inset-0 rounded-full" style={{ background: "var(--c4-surface)", border: "1px solid var(--c4-border-med)" }} />
                <RingBtn dir="up" icon={ChevronUp} testid="remote-up" />
                <RingBtn dir="down" icon={ChevronDown} testid="remote-down" />
                <RingBtn dir="left" icon={ChevronLeft} testid="remote-left" />
                <RingBtn dir="right" icon={ChevronRight} testid="remote-right" />
                <button
                  data-testid="remote-select"
                  onClick={() => send("select")}
                  className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 rounded-full font-head font-semibold text-sm active:scale-95 transition"
                  style={{ width: 120, height: 120, background: "var(--c4-elevated)", border: "1px solid var(--c4-border-med)", color: "var(--c4-text)" }}
                >
                  OK
                </button>
              </div>

              <div className="grid grid-cols-2 gap-3 mb-3">
                <button data-testid="remote-menu" onClick={() => send("menu")} className="glass rounded-xl py-4 flex items-center justify-center gap-2 text-sm active:scale-95 transition">
                  <ArrowLeft className="w-4 h-4" /> Back
                </button>
                <button data-testid="remote-home" onClick={() => send("home")} className="glass rounded-xl py-4 flex items-center justify-center gap-2 text-sm active:scale-95 transition">
                  <Menu className="w-4 h-4" /> Home
                </button>
              </div>

              <div className="grid grid-cols-4 gap-3">
                <button data-testid="remote-playpause" onClick={() => send("play_pause")} className="glass rounded-xl py-4 flex items-center justify-center active:scale-95 transition">
                  <Play className="w-4 h-4" />
                </button>
                <button data-testid="remote-pause" onClick={() => send("pause")} className="glass rounded-xl py-4 flex items-center justify-center active:scale-95 transition">
                  <Pause className="w-4 h-4" />
                </button>
                <button data-testid="remote-volup" onClick={() => send("volume_up")} className="glass rounded-xl py-4 flex items-center justify-center active:scale-95 transition">
                  <Volume2 className="w-4 h-4" />
                </button>
                <button data-testid="remote-voldown" onClick={() => send("volume_down")} className="glass rounded-xl py-4 flex items-center justify-center active:scale-95 transition">
                  <VolumeX className="w-4 h-4" />
                </button>
              </div>

              <button
                data-testid="remote-siri"
                onClick={() => send("siri")}
                className="w-full mt-3 rounded-xl py-4 flex items-center justify-center gap-2 text-sm font-semibold active:scale-95 transition"
                style={{ background: "rgba(99,102,241,0.15)", color: "var(--c4-indigo)", border: "1px solid rgba(99,102,241,0.3)" }}
              >
                <Mic className="w-4 h-4" /> Hold for Siri
              </button>
            </div>
          </div>
        </motion.div>
      )}
    </AnimatePresence>,
    document.body
  );
};

export default AppleTVRemote;
