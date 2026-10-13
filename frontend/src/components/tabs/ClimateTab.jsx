import React, { useEffect } from "react";
import { Flame, Snowflake, RefreshCw, Power, Fan, Minus, Plus, Droplets, Sun } from "lucide-react";
import { useSystem } from "@/context/SystemContext";

const MODES = [
  { id: "heat", label: "Heat", icon: Flame, color: "#F97316" },
  { id: "cool", label: "Cool", icon: Snowflake, color: "#3B82F6" },
  { id: "auto", label: "Auto", icon: RefreshCw, color: "#6366F1" },
  { id: "off", label: "Off", icon: Power, color: "#94A3B8" },
];
const FANS = [
  { id: "auto", label: "Auto" },
  { id: "on", label: "On" },
  { id: "circulate", label: "Circulate" },
];

const RANGE_MIN = 50;
const RANGE_MAX = 90;

const DialArc = ({ current, target, color }) => {
  const r = 120;
  const cx = 140;
  const cy = 140;
  const arcFraction = 0.75; // 270deg
  const circumference = 2 * Math.PI * r;
  const arcLen = circumference * arcFraction;

  const pct = Math.max(0, Math.min(1, (target - RANGE_MIN) / (RANGE_MAX - RANGE_MIN)));

  return (
    <svg width="280" height="280" viewBox="0 0 280 280" className="mx-auto">
      <g transform={`rotate(135 ${cx} ${cy})`}>
        <circle
          cx={cx} cy={cy} r={r} fill="none"
          stroke="rgba(255,255,255,0.07)" strokeWidth="16" strokeLinecap="round"
          strokeDasharray={`${arcLen} ${circumference}`}
        />
        <circle
          cx={cx} cy={cy} r={r} fill="none"
          stroke={color} strokeWidth="16" strokeLinecap="round"
          strokeDasharray={`${arcLen * pct} ${circumference}`}
          style={{ transition: "stroke-dasharray 0.5s ease, stroke 0.4s ease", filter: `drop-shadow(0 0 8px ${color}88)` }}
        />
      </g>
      <text x={cx} y={cy - 6} textAnchor="middle" className="font-head" fill="#E5E9F0" fontSize="56" fontWeight="800">
        {current}°
      </text>
      <text x={cx} y={cy + 28} textAnchor="middle" fill="#94A3B8" fontSize="14" fontWeight="600">
        Current Temp
      </text>
    </svg>
  );
};

const Stepper = ({ label, value, color, onDec, onInc, testid }) => (
  <div className="glass rounded-2xl p-4 flex items-center justify-between" data-testid={testid}>
    <div>
      <p className="text-[11px] uppercase tracking-wide font-semibold" style={{ color: "var(--c4-muted)" }}>{label}</p>
      <p className="font-head text-2xl font-bold" style={{ color }}>{value}°</p>
    </div>
    <div className="flex items-center gap-2">
      <button data-testid={`${testid}-dec`} onClick={onDec} className="w-10 h-10 rounded-xl glass-elevated flex items-center justify-center active:scale-90 transition">
        <Minus className="w-4 h-4" />
      </button>
      <button data-testid={`${testid}-inc`} onClick={onInc} className="w-10 h-10 rounded-xl glass-elevated flex items-center justify-center active:scale-90 transition">
        <Plus className="w-4 h-4" />
      </button>
    </div>
  </div>
);

export const ClimateTab = () => {
  const { state, act, api, setState } = useSystem();
  const hkLive = !!(state?.config?.ecobee?.live && state?.config?.ecobee?.paired);
  useEffect(() => {
    if (!hkLive) return;
    const pull = () => api.climateRefresh().then((r) => r?.ok && setState(r.state)).catch(() => {});
    pull();
    const id = setInterval(pull, 60000);
    return () => clearInterval(id);
  }, [hkLive, api, setState]);
  if (!state) return null;
  const t = state.thermostat;

  const modeMeta = MODES.find((m) => m.id === t.mode) || MODES[3];
  const primaryTarget = t.mode === "heat" ? t.target_heat : t.mode === "cool" ? t.target_cool : Math.round((t.target_heat + t.target_cool) / 2);

  const setMode = (mode) => act(api.climate({ mode }));
  const setFan = (fan) => act(api.climate({ fan }));
  const adjust = (field, delta) => act(api.climate({ [field]: t[field] + delta }));

  return (
    <div className="p-4 sm:p-6 space-y-6 pb-8" data-testid="climate-tab">
      <div>
        <p className="text-[11px] font-semibold uppercase tracking-wider" style={{ color: "var(--c4-emerald)" }}>Ecobee Smart Thermostat</p>
        <h1 className="font-head text-2xl font-extrabold tracking-tight">Climate</h1>
      </div>

      <div className="glass rounded-3xl p-5">
        <DialArc current={t.current_temp} target={primaryTarget} color={modeMeta.color} />
        <div className="flex items-center justify-center gap-6 -mt-2">
          <div className="flex items-center gap-2" data-testid="humidity-readout">
            <Droplets className="w-4 h-4" style={{ color: "var(--c4-cyan)" }} />
            <span className="text-sm font-medium">{t.humidity}%</span>
          </div>
          <div className="flex items-center gap-2" data-testid="outdoor-readout">
            <Sun className="w-4 h-4" style={{ color: "var(--c4-amber)" }} />
            <span className="text-sm font-medium">{t.outdoor_temp}° {t.outdoor_condition}</span>
          </div>
        </div>
      </div>

      {/* Modes */}
      <div className="grid grid-cols-4 gap-2">
        {MODES.map((m) => {
          const on = t.mode === m.id;
          return (
            <button
              key={m.id}
              data-testid={`mode-${m.id}`}
              onClick={() => setMode(m.id)}
              className="glass rounded-2xl py-3 flex flex-col items-center gap-1.5 active:scale-95 transition"
              style={{ background: on ? `${m.color}22` : undefined, border: on ? `1px solid ${m.color}` : undefined }}
            >
              <m.icon className="w-5 h-5" style={{ color: on ? m.color : "var(--c4-muted)" }} />
              <span className="text-[11px] font-semibold" style={{ color: on ? m.color : "var(--c4-muted)" }}>{m.label}</span>
            </button>
          );
        })}
      </div>

      {/* Targets */}
      {t.mode !== "off" && (
        <div className="space-y-3">
          {(t.mode === "heat" || t.mode === "auto") && (
            <Stepper
              label="Heat to" value={t.target_heat} color="#F97316" testid="target-heat"
              onDec={() => adjust("target_heat", -1)} onInc={() => adjust("target_heat", 1)}
            />
          )}
          {(t.mode === "cool" || t.mode === "auto") && (
            <Stepper
              label="Cool to" value={t.target_cool} color="#3B82F6" testid="target-cool"
              onDec={() => adjust("target_cool", -1)} onInc={() => adjust("target_cool", 1)}
            />
          )}
        </div>
      )}

      {/* Fan */}
      <div>
        <div className="flex items-center gap-2 mb-3">
          <Fan className="w-4 h-4" style={{ color: "var(--c4-muted)" }} />
          <p className="font-semibold text-sm">Fan</p>
        </div>
        <div className="grid grid-cols-3 gap-2">
          {FANS.map((f) => {
            const on = t.fan === f.id;
            return (
              <button
                key={f.id}
                data-testid={`fan-${f.id}`}
                onClick={() => setFan(f.id)}
                className="glass rounded-xl py-2.5 text-sm font-semibold active:scale-95 transition"
                style={{ background: on ? "rgba(59,130,246,0.15)" : undefined, color: on ? "var(--c4-primary)" : "var(--c4-muted)" }}
              >
                {f.label}
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
};

export default ClimateTab;
