import React from "react";

const sel = "w-full rounded-lg px-2.5 py-2 text-sm outline-none";
const selStyle = { background: "var(--c4-surface)", border: "1px solid var(--c4-border)", color: "var(--c4-text)" };
const toVal = (v) => (v === null || v === undefined ? "" : String(v));

const Pick = ({ label, value, onChange, options, testid }) => (
  <label className="block">
    <span className="text-[11px]" style={{ color: "var(--c4-muted)" }}>{label}</span>
    <select data-testid={testid} value={toVal(value)} onChange={(e) => onChange(e.target.value)} className={sel} style={selStyle}>
      <option value="">Leave as is</option>
      {options.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
    </select>
  </label>
);

// One room's part of a shortcut. Every field defaults to "Leave as is".
export const RoomActionRow = ({ room, action = {}, onChange }) => {
  const set = (k, v) => onChange({ ...action, [k]: v });
  const bool = (v) => (v === "" ? null : v === "true");
  return (
    <div className="rounded-xl p-3 space-y-2" style={{ background: "var(--c4-bg)", border: "1px solid var(--c4-border)" }} data-testid={`sc-room-${room.id}`}>
      <p className="text-sm font-semibold">{room.name}</p>
      <div className="grid grid-cols-2 gap-2">
        <Pick label="Speakers" testid={`sc-power-${room.id}`} value={action.power} onChange={(v) => set("power", bool(v))} options={[["true", "On"], ["false", "Off"]]} />
        <Pick label="Source" testid={`sc-input-${room.id}`} value={action.input} onChange={(v) => set("input", v === "" ? null : Number(v))}
          options={room.sources.map((s) => [String(s.input), s.label])} />
        <Pick label="Mute" testid={`sc-mute-${room.id}`} value={action.mute} onChange={(v) => set("mute", bool(v))} options={[["true", "Muted"], ["false", "Unmuted"]]} />
        <label className="block">
          <span className="text-[11px]" style={{ color: "var(--c4-muted)" }}>Volume %</span>
          <input data-testid={`sc-volume-${room.id}`} type="number" min="0" max={room.max_volume} placeholder="Leave as is"
            value={toVal(action.volume)} onChange={(e) => set("volume", e.target.value === "" ? null : Math.max(0, Math.min(room.max_volume, Number(e.target.value))))}
            className={sel} style={selStyle} />
        </label>
      </div>
    </div>
  );
};
