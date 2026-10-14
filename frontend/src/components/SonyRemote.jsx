import React from "react";
import { createPortal } from "react-dom";
import { motion, AnimatePresence } from "framer-motion";
import { X, Power, Volume1, Volume2, VolumeX, ChevronUp, ChevronDown, ChevronLeft, ChevronRight, Undo2, Home, LogIn, LayoutList, Play, Pause, Settings2 } from "lucide-react";
import { toast } from "sonner";
import { useSystem } from "@/context/SystemContext";

const Key = ({ k, label, icon: Icon, onKey, wide, accent, testid }) => (
  <button
    data-testid={testid || `sony-key-${k}`}
    onClick={() => onKey(k, label)}
    className={`h-14 rounded-2xl flex items-center justify-center gap-1.5 text-sm font-semibold active:scale-95 transition ${wide ? "col-span-2" : ""}`}
    style={{ background: accent || "var(--c4-elevated)", border: "1px solid var(--c4-border)", color: accent ? "#fff" : "var(--c4-text)" }}
  >
    {Icon && <Icon className="w-5 h-5" />} {label}
  </button>
);

const Arrow = ({ k, icon: Icon, style, onKey }) => (
  <button data-testid={`sony-key-${k}`} onClick={() => onKey(k, k)} className="absolute w-14 h-14 flex items-center justify-center rounded-full active:scale-90 transition" style={style}>
    <Icon className="w-7 h-7" />
  </button>
);

export const SonyRemote = ({ display, onClose }) => {
  const { state, api, act } = useSystem();
  const d = display && state?.displays.find((x) => x.id === display.id);
  const onKey = async (k, label) => {
    try {
      await api.tvKey(d.id, k);
      toast(d.name, { description: label, duration: 900, position: "bottom-center" });
    } catch {
      toast.error("Key not sent");
    }
  };
  const power = async () => {
    await act(api.displayPower(d.id, !d.power));
    toast(d.name, { description: d.power ? "Power off" : "Power on", duration: 900, position: "bottom-center" });
  };

  return createPortal(
    <AnimatePresence>
      {d && (
        <motion.div
          initial={{ opacity: 0, y: 40 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: 40 }}
          transition={{ duration: 0.22, ease: "easeOut" }}
          className="fixed inset-0 z-[70] flex flex-col"
          style={{ background: "var(--c4-bg)", paddingTop: "env(safe-area-inset-top)", paddingBottom: "env(safe-area-inset-bottom)" }}
          data-testid="sony-remote"
        >
          <div className="flex items-center justify-between px-5 py-4">
            <div>
              <p className="font-head font-bold text-lg">{d.name}</p>
              <p className="text-xs" style={{ color: "var(--c4-muted)" }}>Sony Bravia · {d.power ? "On" : "Off"}</p>
            </div>
            <div className="flex gap-2">
              <button data-testid="sony-power-btn" onClick={power} className="w-12 h-12 rounded-2xl flex items-center justify-center active:scale-95" style={{ background: d.power ? "var(--c4-rose)" : "var(--c4-emerald)" }} aria-label="Power">
                <Power className="w-6 h-6 text-white" />
              </button>
              <button data-testid="close-sony-remote-btn" onClick={onClose} className="w-12 h-12 rounded-2xl glass flex items-center justify-center active:scale-95" aria-label="Close remote">
                <X className="w-6 h-6" />
              </button>
            </div>
          </div>
          <div className="flex-1 overflow-y-auto px-5 pb-6">
            <div className="w-full max-w-md lg:max-w-5xl mx-auto grid lg:grid-cols-2 gap-5 lg:gap-10 items-start">
              <div className="space-y-5">
              <div className="grid grid-cols-4 gap-2">
                <Key k="KEY_INPUT" label="Input" icon={LogIn} onKey={onKey} />
                <Key k="KEY_GUIDE" label="Guide" icon={LayoutList} onKey={onKey} />
                <Key k="KEY_NETFLIX" label="Netflix" onKey={onKey} accent="#E50914" />
                <Key k="KEY_YOUTUBE" label="YouTube" onKey={onKey} accent="#CC0000" />
              </div>

              <div className="relative mx-auto" style={{ width: 240, height: 240 }}>
                <div className="absolute inset-0 rounded-full" style={{ background: "var(--c4-surface)", border: "1px solid var(--c4-border)" }} />
                <Arrow k="KEY_UP" icon={ChevronUp} onKey={onKey} style={{ top: 6, left: "50%", marginLeft: -28 }} />
                <Arrow k="KEY_DOWN" icon={ChevronDown} onKey={onKey} style={{ bottom: 6, left: "50%", marginLeft: -28 }} />
                <Arrow k="KEY_LEFT" icon={ChevronLeft} onKey={onKey} style={{ left: 6, top: "50%", marginTop: -28 }} />
                <Arrow k="KEY_RIGHT" icon={ChevronRight} onKey={onKey} style={{ right: 6, top: "50%", marginTop: -28 }} />
                <button data-testid="sony-key-KEY_ENTER" onClick={() => onKey("KEY_ENTER", "OK")} className="absolute rounded-full font-bold active:scale-95 transition"
                  style={{ width: 104, height: 104, left: "50%", top: "50%", marginLeft: -52, marginTop: -52, background: "var(--c4-elevated)", border: "1px solid var(--c4-border-med)" }}>
                  OK
                </button>
              </div>
              </div>

              <div className="space-y-5">
              <div className="grid grid-cols-3 gap-2">
                <Key k="KEY_BACK" label="Back" icon={Undo2} onKey={onKey} />
                <Key k="KEY_HOME" label="Home" icon={Home} onKey={onKey} />
                <Key k="KEY_OPTIONS" label="Options" icon={Settings2} onKey={onKey} />
                <Key k="KEY_VOLDOWN" label="Vol" icon={Volume1} onKey={onKey} />
                <Key k="KEY_MUTE" label="Mute" icon={VolumeX} onKey={onKey} />
                <Key k="KEY_VOLUP" label="Vol" icon={Volume2} onKey={onKey} />
                <Key k="KEY_PLAY" label="Play" icon={Play} onKey={onKey} />
                <Key k="KEY_PAUSE" label="Pause" icon={Pause} onKey={onKey} />
                <Key k="KEY_CHUP" label="CH +" onKey={onKey} />
              </div>

              <div className="grid grid-cols-3 gap-2" data-testid="sony-numpad">
                {["1", "2", "3", "4", "5", "6", "7", "8", "9"].map((n) => <Key key={n} k={`KEY_${n}`} label={n} onKey={onKey} />)}
                <Key k="KEY_CHDOWN" label="CH −" onKey={onKey} />
                <Key k="KEY_0" label="0" onKey={onKey} />
                <div />
              </div>
              </div>
            </div>
          </div>
        </motion.div>
      )}
    </AnimatePresence>,
    document.body
  );
};

export default SonyRemote;
