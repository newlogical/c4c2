import React, { useState, useEffect, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { useSystem } from "@/context/SystemContext";

export const ScreenSaver = ({ enabled = true, timeout = 90000 }) => {
  const { state } = useSystem();
  const [active, setActive] = useState(false);
  const [now, setNow] = useState(new Date());
  const tRef = useRef(null);

  useEffect(() => {
    if (!enabled) {
      setActive(false);
      if (tRef.current) clearTimeout(tRef.current);
      return;
    }
    const arm = () => {
      if (tRef.current) clearTimeout(tRef.current);
      tRef.current = setTimeout(() => setActive(true), timeout);
    };
    const onAct = () => { if (!active) arm(); };
    const evs = ["mousemove", "mousedown", "touchstart", "keydown", "scroll"];
    evs.forEach((e) => window.addEventListener(e, onAct, { passive: true }));
    arm();
    return () => {
      evs.forEach((e) => window.removeEventListener(e, onAct));
      if (tRef.current) clearTimeout(tRef.current);
    };
  }, [enabled, active, timeout]);

  useEffect(() => {
    if (!active) return;
    const iv = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(iv);
  }, [active]);

  const wake = () => setActive(false);
  const temp = state?.thermostat?.current_temp;

  return (
    <AnimatePresence>
      {active && enabled && (
        <motion.div
          initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
          transition={{ duration: 0.6 }}
          onClick={wake}
          data-testid="screensaver"
          className="fixed inset-0 z-[60] flex flex-col items-center justify-center cursor-pointer select-none"
          style={{ background: "radial-gradient(120% 80% at 50% 38%, #0e1524, #05070c)" }}
        >
          <motion.p
            initial={{ scale: 0.96, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} transition={{ delay: 0.1 }}
            className="font-head font-extrabold tracking-tighter"
            style={{ fontSize: "clamp(4rem, 22vw, 10rem)", color: "#fff", lineHeight: 1, textShadow: "0 0 40px rgba(59,130,246,0.25)" }}
          >
            {now.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
          </motion.p>
          <p className="mt-3 text-lg" style={{ color: "var(--c4-muted)" }}>
            {now.toLocaleDateString([], { weekday: "long", month: "long", day: "numeric" })}
          </p>
          {temp != null && (
            <p className="mt-6 text-sm font-semibold px-4 py-2 rounded-full glass" style={{ color: "var(--c4-cyan)" }}>
              Indoor {temp}°
            </p>
          )}
          <p className="absolute bottom-10 text-xs tracking-wide" style={{ color: "var(--c4-muted)" }}>Tap anywhere to wake</p>
        </motion.div>
      )}
    </AnimatePresence>
  );
};

export default ScreenSaver;
