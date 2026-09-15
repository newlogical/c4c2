import React from "react";
import { motion, AnimatePresence } from "framer-motion";
import { X, Terminal } from "lucide-react";
import { useSystem } from "@/context/SystemContext";

export const DriverDrawer = ({ open, onClose }) => {
  const { state } = useSystem();
  const log = state?.command_log || [];

  const colorFor = (driver) => {
    if (driver?.includes("JTECH")) return "var(--c4-primary)";
    if (driver?.includes("WS66i")) return "var(--c4-amber)";
    if (driver?.includes("Ecobee")) return "var(--c4-emerald)";
    if (driver?.includes("AppleTV")) return "var(--c4-indigo)";
    if (driver?.includes("UniFi")) return "var(--c4-cyan)";
    return "var(--c4-muted)";
  };

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
            initial={{ x: "100%" }}
            animate={{ x: 0 }}
            exit={{ x: "100%" }}
            transition={{ type: "spring", damping: 30, stiffness: 300 }}
            className="fixed top-0 right-0 bottom-0 z-50 w-full max-w-md flex flex-col"
            style={{ background: "var(--c4-surface)", borderLeft: "1px solid var(--c4-border)" }}
            data-testid="driver-drawer"
          >
            <div className="flex items-center justify-between px-5 py-4" style={{ borderBottom: "1px solid var(--c4-border)" }}>
              <div className="flex items-center gap-2">
                <Terminal className="w-4 h-4" style={{ color: "var(--c4-cyan)" }} />
                <span className="font-head font-bold">Driver Command Log</span>
              </div>
              <button data-testid="close-drivers-btn" onClick={onClose} className="w-8 h-8 rounded-lg glass flex items-center justify-center">
                <X className="w-4 h-4" />
              </button>
            </div>
            <p className="px-5 pt-3 text-xs" style={{ color: "var(--c4-muted)" }}>
              Live protocol commands dispatched to hardware drivers (demo mode — no device transport).
            </p>
            <div className="flex-1 overflow-y-auto no-scrollbar px-5 py-3 space-y-2">
              {log.length === 0 && (
                <p className="text-sm py-8 text-center" style={{ color: "var(--c4-muted)" }}>
                  No commands yet. Interact with the controller to see driver traffic.
                </p>
              )}
              {log.map((c, i) => (
                <div key={i} className="glass rounded-xl p-3" data-testid={`log-entry-${i}`}>
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-[11px] font-bold font-mono" style={{ color: colorFor(c.driver) }}>
                      {c.driver}
                    </span>
                    <span className="text-[10px]" style={{ color: "var(--c4-muted)" }}>
                      {c.transport}
                    </span>
                  </div>
                  <code className="text-xs block" style={{ color: "var(--c4-text)" }}>{c.command}</code>
                  {c.note && (
                    <p className="text-[11px] mt-1" style={{ color: "var(--c4-muted)" }}>{c.note}</p>
                  )}
                </div>
              ))}
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
};

export default DriverDrawer;
