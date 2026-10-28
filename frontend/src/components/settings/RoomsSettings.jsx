import React, { useState, useEffect, useRef } from "react";
import { toast } from "sonner";
import { ChevronUp, ChevronDown, Trash2, Plus, Speaker, Radio } from "lucide-react";
import { api } from "@/lib/api";
import { useListen } from "@/context/ListenContext";
import { Switch } from "@/components/listen/StatusPill";

const inp = "rounded-lg px-2.5 py-2 text-sm outline-none min-w-0";
const inpStyle = { background: "var(--c4-surface)", border: "1px solid var(--c4-border)", color: "var(--c4-text)" };
const move = (arr, i, d) => { const a = [...arr]; const j = i + d; if (j < 0 || j >= a.length) return a; [a[i], a[j]] = [a[j], a[i]]; return a; };
const NUMS = [1, 2, 3, 4, 5, 6];

// Ordered list of {input, label}: the client-facing source buttons.
export const SourceListEditor = ({ items, onChange, testid, wiims = [], modes = {} }) => (
  <div className="space-y-1.5" data-testid={testid}>
    {items.map((s, i) => (
      <div key={i} className="space-y-1">
      <div className="flex items-center gap-1.5">
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
      {wiims.length > 0 && (
        <div className="flex items-center gap-1.5 pl-[70px] text-[11px]" style={{ color: "var(--c4-muted)" }}>
          <span className="shrink-0">Also switch</span>
          <select value={s.wiim || ""} onChange={(e) => onChange(items.map((x, k) => (k === i ? { ...x, wiim: e.target.value || null, wiim_mode: e.target.value ? (x.wiim_mode || "wifi") : null } : x)))}
            className={`${inp} flex-1`} style={inpStyle} data-testid={`${testid}-wiim-${i}`} aria-label="WiiM to switch">
            <option value="">No WiiM</option>
            {wiims.map((w) => <option key={w.id} value={w.id}>{w.name}</option>)}
          </select>
          {s.wiim && (
            <select value={s.wiim_mode || "wifi"} onChange={(e) => onChange(items.map((x, k) => (k === i ? { ...x, wiim_mode: e.target.value } : x)))}
              className={`${inp} flex-1`} style={inpStyle} data-testid={`${testid}-wiim-mode-${i}`} aria-label="WiiM mode">
              {Object.entries(modes).map(([k, l]) => <option key={k} value={k}>to {l}</option>)}
            </select>
          )}
        </div>
      )}
      </div>
    ))}
    <button onClick={() => onChange([...items, { input: 1, label: "New source" }])} data-testid={`${testid}-add`}
      className="text-xs font-semibold flex items-center gap-1 pt-1" style={{ color: "var(--c4-primary)" }}><Plus className="w-3.5 h-3.5" /> Add source</button>
  </div>
);

const WiimEditor = ({ w, onChange }) => {
  const check = () => api.wiimStatus(w.id, w.ip)
    .then((st) => toast.success(`${w.name}: reachable · ${st.mode_label}${st.playing ? " · playing" : ""}${st.demo ? " (demo)" : " — press Save rooms & sources to keep it"}`))
    .catch((e) => toast.error(e?.response?.data?.detail || "Not reachable"));
  return (
    <div className="flex items-center gap-1.5" data-testid={`layout-wiim-${w.id}`}>
      <input value={w.name} onChange={(e) => onChange({ ...w, name: e.target.value })} className={`${inp} w-24`} style={inpStyle} aria-label="WiiM name" data-testid={`layout-wiim-name-${w.id}`} />
      <input value={w.ip} placeholder="192.168.0.x" onChange={(e) => onChange({ ...w, ip: e.target.value.trim() })} className={`${inp} flex-1 font-mono`} style={inpStyle} aria-label="WiiM IP" data-testid={`layout-wiim-ip-${w.id}`} />
      <select value={w.amp_input || ""} onChange={(e) => onChange({ ...w, amp_input: e.target.value ? Number(e.target.value) : null })} className={`${inp} w-20`} style={inpStyle} aria-label="Wired to amp input" data-testid={`layout-wiim-input-${w.id}`}>
        <option value="">In –</option>{NUMS.map((n) => <option key={n} value={n}>In {n}</option>)}
      </select>
      <button onClick={check} className="rounded-md px-2.5 h-8 text-xs font-semibold glass" data-testid={`layout-wiim-check-${w.id}`}>Check</button>
    </div>
  );
};

const RoomEditor = ({ r, onChange, wiims, modes }) => {
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
      <SourceListEditor items={r.sources} testid={`layout-sources-${r.id}`} wiims={wiims} modes={modes}
        onChange={(v) => onChange({ ...r, sources: v, default_input: v.some((x) => x.input === r.default_input) ? r.default_input : (v[0]?.input ?? r.default_input) })} />
    </div>
  );
};

export const RoomsSettings = () => {
  const { data, run } = useListen();
  const [rooms, setRooms] = useState([]);
  const [party, setParty] = useState([]);
  const [wiims, setWiims] = useState([]);
  const loaded = useRef(false);
  // Load the layout once; the 10 s status refresh must not wipe edits that aren't saved yet.
  useEffect(() => {
    if (data && !loaded.current) {
      loaded.current = true;
      setRooms(data.rooms.map(({ status, in_party, ...r }) => r));
      setParty(data.party_sources);
      setWiims(data.wiims || []);
    }
  }, [data]);
  const save = async () => {
    let fresh;
    const ok = await run(api.listenLayout({ rooms, party_sources: party, wiims }).then((d) => (fresh = d)));
    if (!ok) return;
    setWiims(fresh.wiims || []);
    const lost = wiims.filter((w) => (fresh.wiims || []).find((x) => x.id === w.id)?.ip !== w.ip);
    if (lost.length) toast.error(`Not saved: ${lost.map((w) => w.name).join(", ")} IP — please try again`);
    else toast.success(`Saved · ${(fresh.wiims || []).map((w) => `${w.name} ${w.ip || "(no IP)"}`).join(" · ")}`);
  };
  const modes = data?.wiim_modes || {};
  if (!data) return null;

  return (
    <div className="glass rounded-2xl p-4 space-y-3" data-testid="settings-rooms">
      <div className="flex items-center gap-2.5">
        <div className="w-9 h-9 rounded-xl flex items-center justify-center" style={{ background: "rgba(245,158,11,0.15)" }}><Speaker className="w-4.5 h-4.5" style={{ color: "var(--c4-amber)" }} /></div>
        <div><p className="font-semibold text-sm">Rooms &amp; sources</p><p className="text-[11px]" style={{ color: "var(--c4-muted)" }}>WS66i zone, labels and the amp source number behind each button</p></div>
      </div>
      <div className="rounded-xl p-3 space-y-2" style={{ background: "var(--c4-bg)", border: "1px solid var(--c4-border)" }}>
        <p className="text-sm font-semibold flex items-center gap-1.5"><Radio className="w-4 h-4" style={{ color: "var(--c4-primary)" }} /> WiiM streamers</p>
        <p className="text-[11px]" style={{ color: "var(--c4-muted)" }}>Name, IP and the amp input each WiiM is wired to. A source below can switch a WiiM to Bluetooth (e.g. TV sound) or Wi-Fi/AirPlay before the amp changes.</p>
        {wiims.map((w, i) => <WiimEditor key={w.id} w={w} onChange={(nw) => setWiims(wiims.map((x, k) => (k === i ? nw : x)))} />)}
      </div>
      {rooms.map((r, i) => <RoomEditor key={r.id} r={r} wiims={wiims} modes={modes} onChange={(nr) => setRooms(rooms.map((x, k) => (k === i ? nr : x)))} />)}
      <div className="rounded-xl p-3 space-y-2" style={{ background: "var(--c4-bg)", border: "1px solid var(--c4-border)" }}>
        <p className="text-sm font-semibold">Party Mode sources</p>
        <SourceListEditor items={party} onChange={setParty} testid="layout-party" wiims={wiims} modes={modes} />
      </div>
      <button data-testid="layout-save" onClick={save}
        className="w-full rounded-xl py-2.5 text-sm font-semibold" style={{ background: "var(--c4-primary)", color: "#fff" }}>Save rooms &amp; sources</button>
    </div>
  );
};
