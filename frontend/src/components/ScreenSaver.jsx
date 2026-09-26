import React, { useState, useEffect, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { useSystem } from "@/context/SystemContext";
import { CameraPlayer } from "@/components/CameraPlayer";

const PHOTOS = [
  "https://images.unsplash.com/photo-1567316106249-b2ecaeefdade?crop=entropy&cs=srgb&fm=jpg&q=85&w=1600",
  "https://images.unsplash.com/photo-1475070929565-c985b496cb9f?crop=entropy&cs=srgb&fm=jpg&q=85&w=1600",
  "https://images.unsplash.com/photo-1597407068889-782ba11fb621?crop=entropy&cs=srgb&fm=jpg&q=85&w=1600",
  "https://images.unsplash.com/uploads/1413595244012e81f5c69/de0cc225?crop=entropy&cs=srgb&fm=jpg&q=85&w=1600",
];

export const ScreenSaver = ({ enabled = true, timeout = 90000, mode = "clock" }) => {
  const { state } = useSystem();
  const [active, setActive] = useState(false);
  const [now, setNow] = useState(new Date());
  const [photo, setPhoto] = useState(0);
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

  useEffect(() => {
    if (!active || mode !== "photos") return;
    const iv = setInterval(() => setPhoto((p) => (p + 1) % PHOTOS.length), 8000);
    return () => clearInterval(iv);
  }, [active, mode]);

  const wake = () => setActive(false);
  const temp = state?.thermostat?.current_temp;
  const compact = mode !== "clock";

  return (
    <AnimatePresence>
      {active && enabled && (
        <motion.div
          initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
          transition={{ duration: 0.6 }}
          onClick={wake}
          data-testid="screensaver"
          className="fixed inset-0 z-[60] flex flex-col items-center justify-center cursor-pointer select-none overflow-hidden"
          style={{ background: "radial-gradient(120% 80% at 50% 38%, #0e1524, #05070c)" }}
        >
          {mode === "photos" && (
            <>
              <AnimatePresence>
                <motion.img
                  key={photo}
                  src={PHOTOS[photo]}
                  initial={{ opacity: 0, scale: 1.08 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0 }}
                  transition={{ duration: 1.2 }}
                  className="absolute inset-0 w-full h-full object-cover"
                />
              </AnimatePresence>
              <div className="absolute inset-0" style={{ background: "linear-gradient(180deg, rgba(5,7,12,0.35), rgba(5,7,12,0.75))" }} />
            </>
          )}
          {mode === "camera" && (
            <div className="absolute inset-0">
              <CameraPlayer camId="cam_front" full />
              <div className="absolute inset-0" style={{ background: "linear-gradient(180deg, transparent 55%, rgba(5,7,12,0.8))" }} />
            </div>
          )}

          <div className={compact ? "absolute bottom-12 left-8 text-left z-10" : "flex flex-col items-center z-10"}>
            <motion.p
              initial={{ scale: 0.96, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} transition={{ delay: 0.1 }}
              className="font-head font-extrabold tracking-tighter"
              style={{ fontSize: compact ? "clamp(3rem,12vw,6rem)" : "clamp(4rem, 22vw, 10rem)", color: "#fff", lineHeight: 1, textShadow: "0 2px 30px rgba(0,0,0,0.6)" }}
            >
              {now.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
            </motion.p>
            <p className={compact ? "text-base" : "mt-3 text-lg"} style={{ color: "rgba(255,255,255,0.75)" }}>
              {now.toLocaleDateString([], { weekday: "long", month: "long", day: "numeric" })}
            </p>
            {temp != null && !compact && (
              <p className="mt-6 text-sm font-semibold px-4 py-2 rounded-full glass" style={{ color: "var(--c4-cyan)" }}>Indoor {temp}°</p>
            )}
          </div>
          <p className="absolute bottom-6 right-8 text-xs tracking-wide z-10" style={{ color: "rgba(255,255,255,0.6)" }}>Tap to wake</p>
        </motion.div>
      )}
    </AnimatePresence>
  );
};

export default ScreenSaver;
