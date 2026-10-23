import React from "react";

// Amp connection: Connected (live, last read OK) · Amp offline (live, last read failed) · Demo (simulated).
export const StatusPill = ({ data }) => {
  const [label, color] = !data.live ? ["Demo", "var(--c4-amber)"] : data.amp_error ? ["Amp offline", "var(--c4-rose)"] : ["Connected", "var(--c4-emerald)"];
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[11px] font-semibold" title={data.amp_error || ""}
      style={{ background: "rgba(255,255,255,0.05)", color }} data-testid="amp-status-pill">
      <span className="w-1.5 h-1.5 rounded-full" style={{ background: color }} />
      {label}
    </span>
  );
};

export const Switch = ({ on, onClick, testid, disabled, label }) => (
  <button role="switch" aria-checked={on} aria-label={label} data-testid={testid} onClick={onClick} disabled={disabled}
    className="w-14 h-8 rounded-full relative transition-colors shrink-0 disabled:opacity-40"
    style={{ background: on ? "var(--c4-emerald)" : "rgba(255,255,255,0.14)" }}>
    <span className="absolute top-1 w-6 h-6 rounded-full bg-white transition-[left] duration-200" style={{ left: on ? "28px" : "4px" }} />
  </button>
);
