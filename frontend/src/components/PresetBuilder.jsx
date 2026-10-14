import React, { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { X, Plus, Trash2, ChevronUp, ChevronDown, Loader2 } from "lucide-react";
import { toast } from "sonner";
import { useSystem } from "@/context/SystemContext";

const STEP_TYPES = [
  ["tv_power", "TV power"], ["tv_route", "TV input (Apple TV)"], ["tv_volume", "TV volume"],
  ["amp_source", "Speaker source"], ["amp_volume", "Speaker volume"], ["amp_power", "Speakers on/off"],
  ["stream_preset", "Play streaming favourite"], ["tunein_station", "Play TuneIn station"], ["spotify_play", "Play Spotify playlist"],
];
const sel = "rounded-lg px-2 py-2 text-xs outline-none w-full";
const selStyle = { background: "var(--c4-surface)", border: "1px solid var(--c4-border)", color: "var(--c4-text)" };

const targetsFor = (type, state) => {
  if (type.startsWith("tv_")) return state.displays.map((d) => [d.id, d.name]);
  if (["stream_preset", "tunein_station", "spotify_play"].includes(type)) return Object.keys(state.config?.amp?.streamers || {}).map((k, i) => [k, `Stream ${i + 1}`]);
  return state.audio_zones.map((z) => [z.id, z.name]);
};
const defaultValue = (type, state) => ({
  tv_power: true, amp_power: true, tv_volume: 20, amp_volume: 30, stream_preset: 1,
  tunein_station: state.tunein_saved?.[0]?.id, spotify_play: "",
  tv_route: state.sources[0]?.id, amp_source: state.audio_sources[0]?.id,
}[type]);

const FavouriteSelect = ({ sid, value, onChange, tid }) => {
  const { api } = useSystem();
  const [favs, setFavs] = useState(null);
  useEffect(() => {
    api.streamPresets(sid).then((r) => setFavs(r.presets)).catch(() => setFavs([]));
  }, [api, sid]);
  const list = favs && favs.length ? favs : Array.from({ length: 10 }, (_, i) => ({ number: i + 1, name: "" }));
  return (
    <select data-testid={tid} className={sel} style={selStyle} value={value} onChange={(e) => onChange(Number(e.target.value))}>
      {list.map((f) => <option key={f.number} value={f.number}>{f.number}. {f.name || `Favourite ${f.number}`}</option>)}
    </select>
  );
};

const SpotifySelect = ({ value, onChange, tid }) => {
  const { api } = useSystem();
  const [items, setItems] = useState(null);
  useEffect(() => {
    api.spotifyLibrary().then((l) => setItems([...l.recent, ...l.playlists])).catch(() => setItems([]));
  }, [api]);
  if (items && items.length)
    return (
      <select data-testid={tid} className={sel} style={selStyle} value={value} onChange={(e) => onChange(e.target.value, items.find((x) => x.uri === e.target.value)?.name)}>
        <option value="">Choose…</option>
        {items.map((x) => <option key={x.uri} value={x.uri}>{x.name}</option>)}
      </select>
    );
  return <input data-testid={tid} className={sel} style={selStyle} value={value} placeholder="spotify:playlist:… (connect Spotify to pick)" onChange={(e) => onChange(e.target.value.trim())} />;
};

const ValueInput = ({ step, state, onChange, idx }) => {
  const t = step.type;
  const tid = `preset-step-value-${idx}`;
  if (t === "tv_power" || t === "amp_power")
    return <select data-testid={tid} className={sel} style={selStyle} value={step.value ? "on" : "off"} onChange={(e) => onChange(e.target.value === "on")}><option value="on">On</option><option value="off">Off</option></select>;
  if (t === "tv_volume" || t === "amp_volume")
    return <input data-testid={tid} type="number" min={0} max={100} className={sel} style={selStyle} value={step.value} onChange={(e) => onChange(Math.max(0, Math.min(100, Number(e.target.value))))} />;
  if (t === "stream_preset") return <FavouriteSelect sid={step.target} value={step.value} onChange={onChange} tid={tid} />;
  if (t === "spotify_play") return <SpotifySelect value={step.value} onChange={onChange} tid={tid} />;
  if (t === "tunein_station")
    return <select data-testid={tid} className={sel} style={selStyle} value={step.value} onChange={(e) => onChange(e.target.value)}>{(state.tunein_saved || []).map((o) => <option key={o.id} value={o.id}>{o.name}</option>)}</select>;
  const opts = t === "tv_route" ? state.sources : state.audio_sources;
  return <select data-testid={tid} className={sel} style={selStyle} value={step.value} onChange={(e) => onChange(e.target.value)}>{opts.map((o) => <option key={o.id} value={o.id}>{o.name}</option>)}</select>;
};

export const PresetBuilder = ({ open, preset, onClose, onSaved }) => {
  const { state, api } = useSystem();
  const [name, setName] = useState("");
  const [steps, setSteps] = useState([]);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!open) return;
    setName(preset?.name || "");
    setSteps(preset?.actions ? preset.actions.map((a) => ({ ...a })) : []);
  }, [open, preset]);

  if (!open || !state) return null;
  const update = (i, patch) => setSteps((s) => s.map((x, j) => (j === i ? { ...x, ...patch } : x)));
  const add = () => setSteps((s) => [...s, { type: "tv_power", target: state.displays[0].id, value: true }]);
  const move = (i, d) => setSteps((s) => { const n = [...s]; const j = i + d; if (j < 0 || j >= n.length) return s; [n[i], n[j]] = [n[j], n[i]]; return n; });
  const changeType = (i, type) => update(i, { type, target: targetsFor(type, state)[0]?.[0], value: defaultValue(type, state) });

  const save = async () => {
    if (!name.trim()) return toast.error("Give the preset a name");
    if (!steps.length) return toast.error("Add at least one step");
    setBusy(true);
    try {
      const body = { name: name.trim(), icon: "Sparkles", actions: steps };
      if (preset) await api.updatePreset(preset.id, body); else await api.createPreset(body);
      toast.success(preset ? "Preset updated" : "Preset saved");
      onSaved();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Could not save preset");
    } finally {
      setBusy(false);
    }
  };

  return createPortal(
    <div className="fixed inset-0 z-[80] flex flex-col" style={{ background: "var(--c4-bg)" }} data-testid="preset-builder">
      <div className="flex items-center justify-between px-5 py-4">
        <h2 className="text-xl font-semibold">{preset ? "Edit preset" : "New preset"}</h2>
        <button data-testid="preset-builder-close-btn" onClick={onClose} className="w-12 h-12 rounded-2xl glass flex items-center justify-center"><X className="w-6 h-6" /></button>
      </div>
      <div className="flex-1 overflow-y-auto px-5 pb-4 space-y-3 max-w-2xl w-full mx-auto">
        <input data-testid="preset-name-input" value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Watch TV in Office with Sound"
          className="w-full rounded-xl px-4 py-3 text-sm outline-none" style={selStyle} />
        <p className="text-[11px]" style={{ color: "var(--c4-muted)" }}>Steps run top to bottom. Put “TV power on” before other TV steps.</p>
        {steps.map((st, i) => (
          <div key={i} className="glass rounded-2xl p-3 space-y-2" data-testid={`preset-step-${i}`}>
            <div className="flex items-center gap-2">
              <span className="text-[11px] font-mono w-5" style={{ color: "var(--c4-muted)" }}>{i + 1}</span>
              <select data-testid={`preset-step-type-${i}`} className={sel} style={selStyle} value={st.type} onChange={(e) => changeType(i, e.target.value)}>
                {STEP_TYPES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
              </select>
              <button data-testid={`preset-step-up-${i}`} onClick={() => move(i, -1)} className="w-8 h-8 rounded-lg glass flex items-center justify-center shrink-0"><ChevronUp className="w-4 h-4" /></button>
              <button data-testid={`preset-step-down-${i}`} onClick={() => move(i, 1)} className="w-8 h-8 rounded-lg glass flex items-center justify-center shrink-0"><ChevronDown className="w-4 h-4" /></button>
              <button data-testid={`preset-step-remove-${i}`} onClick={() => setSteps((s) => s.filter((_, j) => j !== i))} className="w-8 h-8 rounded-lg glass flex items-center justify-center shrink-0"><Trash2 className="w-4 h-4" style={{ color: "var(--c4-rose)" }} /></button>
            </div>
            <div className="grid grid-cols-2 gap-2 pl-7">
              <select data-testid={`preset-step-target-${i}`} className={sel} style={selStyle} value={st.target} onChange={(e) => update(i, { target: e.target.value })}>
                {targetsFor(st.type, state).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
              </select>
              <ValueInput step={st} state={state} idx={i} onChange={(v, label) => update(i, label ? { value: v, label } : { value: v })} />
            </div>
          </div>
        ))}
        <button data-testid="preset-add-step-btn" onClick={add} className="w-full rounded-2xl py-3 text-sm font-semibold flex items-center justify-center gap-2 glass active:scale-[0.98]">
          <Plus className="w-4 h-4" /> Add step
        </button>
      </div>
      <div className="px-5 pb-6 max-w-2xl w-full mx-auto">
        <button data-testid="preset-save-btn" disabled={busy} onClick={save} className="w-full rounded-2xl py-4 font-semibold flex items-center justify-center gap-2 disabled:opacity-50" style={{ background: "var(--c4-indigo)", color: "#fff" }}>
          {busy && <Loader2 className="w-5 h-5 animate-spin" />} Save preset
        </button>
      </div>
    </div>,
    document.body
  );
};

export default PresetBuilder;
