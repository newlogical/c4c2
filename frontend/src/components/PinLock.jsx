import React, { useState, useEffect, useRef } from "react";
import { toast } from "sonner";
import { motion } from "framer-motion";
import { Delete, Lock, Home, ShieldAlert } from "lucide-react";
import { QRCodeCanvas } from "qrcode.react";
import { api } from "@/lib/api";

export const PinLock = ({ onUnlock, propertyName }) => {
  const [pin, setPin] = useState("");
  const [error, setError] = useState(false);
  const [retry, setRetry] = useState(0);
  const [attemptsLeft, setAttemptsLeft] = useState(null);
  const [name, setName] = useState(propertyName);
  const [demoMode, setDemoMode] = useState(false);
  const [remote, setRemote] = useState(false);
  const timerRef = useRef(null);

  const locked = retry > 0;

  useEffect(() => {
    api.getBootstrap().then((b) => {
      if (b?.property_name) setName(b.property_name);
      setDemoMode(!!b?.demo_mode);
      setRemote(!!b?.remote);
    }).catch((e) => console.warn("Bootstrap failed", e));
  }, []);

  useEffect(() => {
    if (!locked) return;
    timerRef.current = setInterval(() => setRetry((r) => (r <= 1 ? 0 : r - 1)), 1000);
    return () => clearInterval(timerRef.current);
  }, [locked]);

  const submit = async (value) => {
    const res = await api.verifyPin(value);
    if (res.success) {
      onUnlock();
      return;
    }
    if (res.signed_out) {
      toast.error("Too many wrong PINs — please sign in again");
      setTimeout(() => window.location.reload(), 1200);
      return;
    }
    setError(true);
    if (res.locked) {
      setRetry(res.retry_after || 30);
      setAttemptsLeft(0);
    } else if (typeof res.attempts_left === "number") {
      setAttemptsLeft(res.attempts_left);
    }
    setTimeout(() => {
      setError(false);
      setPin("");
    }, 500);
  };

  const press = (digit) => {
    if (locked || pin.length >= 4) return;
    const next = pin + digit;
    setPin(next);
    if (next.length === 4) setTimeout(() => submit(next), 150);
  };

  const keys = ["1", "2", "3", "4", "5", "6", "7", "8", "9", "", "0", "del"];

  const subtitle = locked
    ? `Too many attempts · retry in ${retry}s`
    : attemptsLeft != null && attemptsLeft < 5
    ? `Incorrect PIN · ${attemptsLeft} attempt${attemptsLeft === 1 ? "" : "s"} left`
    : "Enter your 4-digit PIN";

  return (
    <div className="c4-shell min-h-screen flex flex-col items-center justify-center px-6 safe-top safe-bottom" data-testid="pin-lock-screen">
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
        className="w-full max-w-xs flex flex-col items-center"
      >
        <div className="w-14 h-14 rounded-2xl glass-elevated glow-ring flex items-center justify-center mb-5">
          {locked ? <ShieldAlert className="w-6 h-6" style={{ color: "var(--c4-rose)" }} /> : <Lock className="w-6 h-6" style={{ color: "var(--c4-primary)" }} />}
        </div>
        <h1 className="font-head text-2xl font-bold tracking-tight">{name || "Home Control"}</h1>
        <p data-testid="pin-subtitle" className="text-sm mt-1 text-center" style={{ color: locked || (attemptsLeft != null && attemptsLeft < 5) ? "var(--c4-rose)" : "var(--c4-muted)" }}>
          {subtitle}
        </p>

        <div className={`flex gap-4 my-8 ${error ? "animate-shake" : ""}`}>
          {[0, 1, 2, 3].map((i) => (
            <div
              key={i}
              data-testid={`pin-dot-${i}`}
              className="w-4 h-4 rounded-full transition-all duration-200"
              style={{
                background: error ? "var(--c4-rose)" : pin.length > i ? "var(--c4-primary)" : "rgba(255,255,255,0.12)",
                boxShadow: pin.length > i && !error ? "0 0 12px rgba(59,130,246,0.7)" : "none",
              }}
            />
          ))}
        </div>

        <div className="grid grid-cols-3 gap-4 w-full" style={{ opacity: locked ? 0.4 : 1, pointerEvents: locked ? "none" : "auto" }}>
          {keys.map((k, idx) =>
            k === "" ? (
              <div key={`blank-${idx}`} />
            ) : (
              <button
                key={`key-${k}`}
                disabled={locked}
                data-testid={k === "del" ? "pin-key-del" : `pin-key-${k}`}
                onClick={() => (k === "del" ? setPin(pin.slice(0, -1)) : press(k))}
                className="aspect-square rounded-2xl glass flex items-center justify-center text-2xl font-head font-semibold active:scale-95 transition-all hover:border-[var(--c4-border-med)]"
                style={{ color: "var(--c4-text)" }}
              >
                {k === "del" ? <Delete className="w-6 h-6" /> : k}
              </button>
            )
          )}
        </div>

        {demoMode && (
          <button
            data-testid="pin-demo-bypass"
            onClick={async () => {
              try {
                const res = await api.demoBypass();
                if (res?.success) onUnlock();
              } catch (e) {
                toast.error(e?.response?.data?.detail || "Demo access is not available");
              }
            }}
            className="mt-8 text-xs flex items-center gap-1.5"
            style={{ color: "var(--c4-muted)" }}
          >
            <Home className="w-3.5 h-3.5" /> Demo — tap to skip (PIN 1234)
          </button>
        )}

        {!remote && <div className="mt-7 flex flex-col items-center gap-1.5" data-testid="setup-guide-qr">
          <div className="p-2 rounded-xl" style={{ background: "rgba(255,255,255,0.92)" }}>
            <QRCodeCanvas value={`${window.location.origin}/setup-guide.html`} size={72} bgColor="#ffffff" fgColor="#0a0d14" level="M" />
          </div>
          <span className="text-[10px]" style={{ color: "var(--c4-muted)" }}>Scan for the setup guide</span>
        </div>}
      </motion.div>
    </div>
  );
};

export default PinLock;
