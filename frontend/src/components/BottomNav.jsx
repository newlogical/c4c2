import React from "react";
import { LayoutDashboard, Tv, Volume2, Thermometer, Camera, Sparkles } from "lucide-react";

const TABS = [
  { id: "home", label: "Home", icon: LayoutDashboard },
  { id: "watch", label: "Watch", icon: Tv },
  { id: "listen", label: "Listen", icon: Volume2 },
  { id: "climate", label: "Climate", icon: Thermometer },
  { id: "security", label: "Camera", icon: Camera },
  { id: "scenes", label: "Scenes", icon: Sparkles },
];

export const BottomNav = ({ active, onChange }) => (
  <nav
    className="sticky bottom-0 z-30 backdrop-blur-xl px-1.5 py-2"
    style={{ background: "rgba(10,13,20,0.85)", borderTop: "1px solid var(--c4-border)" }}
    data-testid="bottom-nav"
  >
    <div className="max-w-2xl mx-auto grid grid-cols-6 gap-1">
      {TABS.map(({ id, label, icon: Icon }) => {
        const on = active === id;
        return (
          <button
            key={id}
            data-testid={`nav-${id}`}
            onClick={() => onChange(id)}
            className="flex flex-col items-center gap-1 py-1.5 rounded-xl transition-all active:scale-95"
            style={{ color: on ? "var(--c4-primary)" : "var(--c4-muted)" }}
          >
            <div
              className="w-full flex justify-center py-1 rounded-lg transition-all"
              style={{ background: on ? "rgba(59,130,246,0.14)" : "transparent" }}
            >
              <Icon className="w-5 h-5" strokeWidth={on ? 2.4 : 1.8} />
            </div>
            <span className="text-[10px] font-semibold tracking-tight">{label}</span>
          </button>
        );
      })}
    </div>
  </nav>
);

export default BottomNav;
