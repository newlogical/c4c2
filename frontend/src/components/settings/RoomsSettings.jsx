import React, { useState, useEffect } from "react";
import { ChevronUp, ChevronDown, Trash2, Plus, Speaker } from "lucide-react";
import { api } from "@/lib/api";
import { useListen } from "@/context/ListenContext";
import { Switch } from "@/components/listen/StatusPill";

const inp = "rounded-lg px-2.5 py-2 text-sm outline-none min-w-0";
const inpStyle = { background: "var(--c4-surface)", border: "1px solid var(--c4-border)", color: "var(--c4-text)" };
const move = (arr, i, d) => { const a = [...arr]; const j = i + d; if (j < 0 || j >= a.length) return a; [a[i], a[j]] = [a[j], a[i]]; return a; };
const NUMS = [1, 2, 3, 4, 5, 6];

// Ordered list of {input, label}: the client-facing source buttons.
export const SourceListEditor = ({ items, onChange, testid }) => (
  <div className="space-y-1.5" data-testid={testid}>
    {items.map((s, i) => (
      <div key={i} className="flex items-center gap-1.5">
        <select value={s.input} onChange={(e) => onChange(items.map((x, k) => (k === i ? { ...x, input: Number(e.target.value) } : x)))}
          className={`${inp} w-16`} style={inpStyle} data-testid={`${testid}-input-${i}`} aria-label="Amp source number">
          {NUMS.map((n) => <option key={n} value={n}>{n}</option>)}
        </select>
        <input value={s.label} onChange={(e) => onChange(items.map((x, k) => (k === i ? { ...x, label: e.target.value } : x)))}
          className={`${inp} flex-1`} style={inpStyle} data-testid={`${testid}-label-${i}`} aria-label="Label" />
        <button onClick={() => onChange(move(items, i, -1))} className="w-8 h-8 rounded-md glass flex items-center justify-center" aria-label="Up"><ChevronUp className="w-3.5 h-3.5" /></button>
        <button onClick={() => onChange(move(items, i, 1))} className="w-8 h-8 rounded-md glass flex items-center justify-center" aria-label="Down"><ChevronDown className="w-3.5 h-3.5" /></button>
        <button onClick={() => onChange(items.filter((_, k) => k !== i))} className="w-8 h-8 rounded-md glass flex items-center justify-center" aria-label="Remove" data-testid={`${testid}-remove-${i}`}><Trash2 className="w-3.5 h-3.5" /></button>
      </div>
    ))}
    <button onClick={() => onChange([...items, { input: 1, label: "New source" }])} data-testid={`${testid}-add`}
      className="text-xs font-semibold flex items-center gap-1 pt-1" style={{ color: "var(--c4-primary)" }}><Plus className="w-3.5 h-3.5" /> Add source</button>
  </div>
);

const RoomEditor = ({ r, onChange }) => {
  const set = (k, v) => onChange({ ...r, [k]: v });
  return (
    <div className="rounded-xl p-3 space-y-2.5" style={{ background: "var(--c4-bg)", border: "1px solid var(--c4-border)" }} data-testid={`layout-room-${r.id}`}>
      <div className="flex items-center gap-2">
        <input value={r.name} onChange={(e) => set("name", e.target.value)} className={`${inp} flex-1 font-semibold`} style={inpStyle} data-testid={`layout-name-${r.id}`} aria-label="Room name" />
        <Switch on={r.visible} label="Visible" testid={`layout-visible-${r.id}`} onClick={() => set("visible", !r.visible)} />
      </div>
      <div className="grid grid-cols-3 gap-2 text-[11px]" style={{ color: "var(--c4-muted)" }}>
        <label>Amp zone<select value={r.amp_zone} onChange={(e) => set("amp_zone", Number(e.target.value))} className={`${inp} w-full`} style={inpStyle} data-testid={`layout-zone-${r.id}`}>{NUMS.map((n) => <option key={n} value={n}>{n}</option>)}</select></label>
        <label>Default<select value={r.default_input} onChange={(e) => set("default_input", Number(e.target.value))} className={`${inp} w-full`} style={inpStyle} data-testid={`layout-default-${r.id}`}>
          {(r.sources.length ? r.sources : [{ input: r.default_input, label: "—" }]).map((s) => <option key={s.input} value={s.input}>{s.label}</option>)}</select></label>
        <label>Max vol %<input type="number" min="5" max="100" value={r.max_volume} onChange={(e) => set("max_volume", Number(e.target.value))} className={`${inp} w-full`} style={inpStyle} data-testid={`layout-max-${r.id}`} /></label>
      </div>
      <SourceListEditor items={r.sources} onChange={(v) => set("sources", v)} testid={`layout-sources-${r.id}`} />
    </div>
  );
};

export const RoomsSettings = () => {
  const { data, run } = useListen();
  const [rooms, setRooms] = useState([]);
  const [party, setParty] = useState([]);
  useEffect(() => {
    if (data) {
      setRooms(data.rooms.map(({ status, in_party, ...r }) => r));
      setParty(data.party_sources);
    }
  }, [data]);
  if (!data) return null;

  return (
    <div className="glass rounded-2xl p-4 space-y-3" data-testid="settings-rooms">
      <div className="flex items-center gap-2.5">
        <div className="w-9 h-9 rounded-xl flex items-center justify-center" style={{ background: "rgba(245,158,11,0.15)" }}><Speaker className="w-4.5 h-4.5" style={{ color: "var(--c4-amber)" }} /></div>
        <div><p className="font-semibold text-sm">Rooms &amp; sources</p><p className="text-[11px]" style={{ color: "var(--c4-muted)" }}>WS66i zone, labels and the amp source number behind each button</p></div>
      </div>
      {rooms.map((r, i) => <RoomEditor key={r.id} r={r} onChange={(nr) => setRooms(rooms.map((x, k) => (k === i ? nr : x)))} />)}
      <div className="rounded-xl p-3 space-y-2" style={{ background: "var(--c4-bg)", border: "1px solid var(--c4-border)" }}>
        <p className="text-sm font-semibold">Party Mode sources</p>
        <SourceListEditor items={party} onChange={setParty} testid="layout-party" />
      </div>
      <button data-testid="layout-save" onClick={() => run(api.listenLayout({ rooms, party_sources: party }), "Rooms saved")}
        className="w-full rounded-xl py-2.5 text-sm font-semibold" style={{ background: "var(--c4-primary)", color: "#fff" }}>Save rooms &amp; sources</button>
    </div>
  );
};
