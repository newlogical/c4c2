import React, { useEffect, useState } from "react";
import { Lock, Wifi, Cable, Radio, Terminal, Settings } from "lucide-react";
import { useSystem } from "@/context/SystemContext";

const StatusDot = ({ ok, label, icon: Icon }) => (
  <div className="flex items-center gap-1.5" data-testid={`status-${label.toLowerCase()}`}>
    <Icon className="w-3.5 h-3.5" style={{ color: ok ? "var(--c4-emerald)" : "var(--c4-rose)" }} />
    <span className="text-[11px] font-medium hidden sm:inline" style={{ color: "var(--c4-muted)" }}>
      {label}
    </span>
    <span
      className="w-1.5 h-1.5 rounded-full"
      style={{ background: ok ? "var(--c4-emerald)" : "var(--c4-rose)" }}
    />
  </div>
);

export const TopBar = ({ onLock, onOpenDrivers, onOpenSettings }) => {
  const { state } = useSystem();
  const [now, setNow] = useState(new Date());

  useEffect(() => {
    const t = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(t);
  }, []);

  const net = state?.network || {};
  const time = now.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });

  return (
    <header
      className="sticky top-0 z-30 px-4 sm:px-6 py-3 flex items-center justify-between backdrop-blur-xl"
      style={{ background: "rgba(10,13,20,0.75)", borderBottom: "1px solid var(--c4-border)" }}
      data-testid="top-bar"
    >
      <div className="flex flex-col">
        <span className="font-head font-bold text-base leading-tight tracking-tight">
          {state?.property_name || "Home"}
        </span>
        <span className="text-[11px] font-mono" style={{ color: "var(--c4-muted)" }}>
          {time} · Control OS
        </span>
      </div>

      <div className="flex items-center gap-2 sm:gap-4">
        <div className="hidden xs:flex items-center gap-3">
          <StatusDot ok={net.unifi_online} label="UniFi" icon={Wifi} />
          <StatusDot ok={net.matrix_linked} label="Matrix" icon={Cable} />
          <StatusDot ok={net.amp_linked} label="Amp" icon={Radio} />
        </div>
        <button
          data-testid="open-drivers-btn"
          onClick={onOpenDrivers}
          className="w-9 h-9 rounded-xl glass flex items-center justify-center active:scale-95 transition"
          title="Driver command log"
        >
          <Terminal className="w-4 h-4" style={{ color: "var(--c4-cyan)" }} />
        </button>
        <button
          data-testid="open-settings-btn"
          onClick={onOpenSettings}
          className="w-9 h-9 rounded-xl glass flex items-center justify-center active:scale-95 transition"
          title="Device settings"
        >
          <Settings className="w-4 h-4" style={{ color: "var(--c4-text)" }} />
        </button>
        <button
          data-testid="lock-btn"
          onClick={onLock}
          className="w-9 h-9 rounded-xl glass flex items-center justify-center active:scale-95 transition"
          title="Lock"
        >
          <Lock className="w-4 h-4" style={{ color: "var(--c4-text)" }} />
        </button>
      </div>
    </header>
  );
};

export default TopBar;
