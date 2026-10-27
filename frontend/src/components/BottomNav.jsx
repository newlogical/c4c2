import React from "react";
import { Volume2, Sparkles, Thermometer, Settings, Cctv } from "lucide-react";

const TABS = [
  { id: "listen", label: "Listen", icon: Volume2 },
  { id: "shortcuts", label: "Shortcuts", icon: Sparkles },
  { id: "camera", label: "Camera", icon: Cctv },
  { id: "climate", label: "Thermostat", icon: Thermometer },
  { id: "settings", label: "Settings", icon: Settings },
];

export const BottomNav = ({ active, onChange }) => (
  <nav
    className="sticky bottom-0 z-30 backdrop-blur-xl px-1.5 py-2"
    style={{ background: "rgba(10,13,20,0.85)", borderTop: "1px solid var(--c4-border)", paddingBottom: "max(0px, env(safe-area-inset-bottom))" }}
    data-testid="bottom-nav"
  >
    <div className="max-w-2xl mx-auto grid grid-cols-5 gap-1">
      {TABS.map(({ id, label, icon: Icon }) => {
        const on = active === id;
        return (
          <button
            key={id}
            data-testid={`nav-${id}`}
            onClick={() => onChange(id)}
            className="flex flex-col items-center gap-1 py-1.5 rounded-xl transition-transform active:scale-95"
            style={{ color: on ? "var(--c4-primary)" : "var(--c4-muted)" }}
          >
            <div className="w-full flex justify-center py-1 rounded-lg transition-colors" style={{ background: on ? "rgba(59,130,246,0.14)" : "transparent" }}>
              <Icon className="w-5 h-5" strokeWidth={on ? 2.4 : 1.8} />
            </div>
            <span className="text-[11px] font-semibold tracking-tight">{label}</span>
          </button>
        );
      })}
    </div>
  </nav>
);

export default BottomNav;
