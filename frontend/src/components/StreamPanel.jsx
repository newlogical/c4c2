import React, { useCallback, useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { Play, Pause, SkipBack, SkipForward, Star, Music2, X, Speaker, Loader2 } from "lucide-react";
import { toast } from "sonner";
import { useSystem } from "@/context/SystemContext";

const chip = (on) => ({ background: on ? "var(--c4-primary)" : "var(--c4-surface)", color: on ? "#fff" : "var(--c4-text)", border: "1px solid var(--c4-border)" });

// Favourite picker + room chooser for one streaming module
const FavouriteSheet = ({ mod, onClose, onDone }) => {
  const { state, api, act } = useSystem();
  const [presets, setPresets] = useState(null);
  const [pick, setPick] = useState(null);
  const [zones, setZones] = useState(mod.zones);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api.streamPresets(mod.id).then((r) => setPresets(r.presets)).catch((e) => { toast.error(e?.response?.data?.detail || "Could not load favourites"); setPresets([]); });
  }, [api, mod.id]);

  const toggle = (id) => setZones((z) => (z.includes(id) ? z.filter((x) => x !== id) : [...z, id]));
  const play = async () => {
    setBusy(true);
    try {
      await act(api.streamPlay(mod.id, { preset: pick, zones }));
      toast.success(pick ? `Playing favourite ${pick}` : "Rooms updated", { description: `${mod.label} → ${zones.length} room(s)` });
      onDone();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Could not start playback");
    } finally {
      setBusy(false);
    }
  };

  return createPortal(
    <div className="fixed inset-0 z-[80] flex flex-col" style={{ background: "var(--c4-bg)" }} data-testid={`stream-sheet-${mod.id}`}>
      <div className="flex items-center justify-between px-5 py-4">
        <div>
          <p className="text-[10px] uppercase tracking-widest" style={{ color: "var(--c4-amber)" }}>{mod.label} · {mod.source_name} · input {mod.input}</p>
          <h2 className="text-xl font-semibold">Pick a favourite & rooms</h2>
        </div>
        <button data-testid="stream-sheet-close-btn" onClick={onClose} className="w-12 h-12 rounded-2xl glass flex items-center justify-center"><X className="w-6 h-6" /></button>
      </div>
      <div className="flex-1 overflow-y-auto px-5 pb-4 space-y-5">
        <div>
          <p className="text-[10px] uppercase tracking-widest mb-2" style={{ color: "var(--c4-muted)" }}>Favourites (saved in the Soundavo app)</p>
          {!presets ? <Loader2 className="w-5 h-5 animate-spin" /> : presets.length === 0 ? (
            <p className="text-xs" style={{ color: "var(--c4-muted)" }}>No favourites saved on this module yet. Add them in the Soundavo app, or just send rooms below.</p>
          ) : (
            <div className="grid grid-cols-2 gap-2">
              {presets.map((p) => (
                <button key={p.number} data-testid={`stream-fav-${mod.id}-${p.number}`} onClick={() => setPick(pick === p.number ? null : p.number)}
                  className="rounded-xl p-3 text-left flex items-center gap-2 active:scale-95 transition" style={chip(pick === p.number)}>
                  {p.art ? <img src={p.art} alt="" className="w-8 h-8 rounded-md object-cover" /> : <Star className="w-4 h-4 shrink-0" />}
                  <span className="text-xs font-semibold truncate">{p.number}. {p.name}</span>
                </button>
              ))}
            </div>
          )}
        </div>
        <div>
          <p className="text-[10px] uppercase tracking-widest mb-2" style={{ color: "var(--c4-muted)" }}>Play in these rooms</p>
          <div className="grid grid-cols-2 gap-2">
            {state.audio_zones.map((z) => (
              <button key={z.id} data-testid={`stream-zone-${mod.id}-${z.id}`} onClick={() => toggle(z.id)}
                className="rounded-xl p-3 text-xs font-semibold flex items-center gap-2 active:scale-95 transition" style={chip(zones.includes(z.id))}>
                <Speaker className="w-4 h-4" /> {z.name}
              </button>
            ))}
          </div>
        </div>
      </div>
      <div className="px-5 pb-6">
        <button data-testid={`stream-play-btn-${mod.id}`} disabled={busy || (!pick && zones.length === 0)} onClick={play}
          className="w-full rounded-2xl py-4 font-semibold flex items-center justify-center gap-2 disabled:opacity-40 active:scale-[0.98] transition" style={{ background: "var(--c4-amber)", color: "#1a1204" }}>
          {busy ? <Loader2 className="w-5 h-5 animate-spin" /> : <Play className="w-5 h-5" />} {pick ? "Play favourite" : "Send to rooms"}
        </button>
      </div>
    </div>,
    document.body
  );
};

const ModuleCard = ({ mod, zoneNames, onCmd, onOpen }) => {
  const playing = mod.status === "play";
  return (
    <div className="glass rounded-2xl p-4" data-testid={`stream-module-${mod.id}`}>
      <div className="flex items-center gap-3">
        <div className="w-14 h-14 rounded-xl overflow-hidden flex items-center justify-center shrink-0" style={{ background: "var(--c4-surface)" }}>
          {mod.art ? <img src={mod.art} alt="" className="w-full h-full object-cover" /> : <Music2 className="w-6 h-6" style={{ color: "var(--c4-amber)" }} />}
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-[10px] uppercase tracking-widest" style={{ color: "var(--c4-amber)" }}>{mod.label} · input {mod.input}</p>
          <p className="font-semibold text-sm truncate" data-testid={`stream-title-${mod.id}`}>{!mod.online ? "Offline" : mod.title || (playing ? "Playing" : "Nothing playing")}</p>
          <p className="text-[11px] truncate" style={{ color: "var(--c4-muted)" }}>{mod.artist || mod.source_name}</p>
        </div>
      </div>
      <p className="text-[11px] mt-2" style={{ color: "var(--c4-muted)" }} data-testid={`stream-rooms-${mod.id}`}>
        Rooms: {mod.zones.length ? mod.zones.map((z) => zoneNames[z]).join(", ") : "none"}
      </p>
      <div className="flex items-center gap-2 mt-3">
        <button data-testid={`stream-prev-${mod.id}`} onClick={() => onCmd(mod, "prev")} className="w-11 h-11 rounded-xl glass flex items-center justify-center active:scale-95"><SkipBack className="w-4 h-4" /></button>
        <button data-testid={`stream-playpause-${mod.id}`} onClick={() => onCmd(mod, "play_pause")} className="w-11 h-11 rounded-xl flex items-center justify-center active:scale-95" style={{ background: "var(--c4-amber)", color: "#1a1204" }}>
          {playing ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4" />}
        </button>
        <button data-testid={`stream-next-${mod.id}`} onClick={() => onCmd(mod, "next")} className="w-11 h-11 rounded-xl glass flex items-center justify-center active:scale-95"><SkipForward className="w-4 h-4" /></button>
        <button data-testid={`stream-open-${mod.id}`} onClick={() => onOpen(mod)} className="flex-1 h-11 rounded-xl text-xs font-semibold flex items-center justify-center gap-1.5 active:scale-95" style={{ background: "rgba(245,158,11,0.15)", color: "var(--c4-amber)" }}>
          <Star className="w-4 h-4" /> Favourites & rooms
        </button>
      </div>
    </div>
  );
};

export const StreamPanel = () => {
  const { state, api } = useSystem();
  const [mods, setMods] = useState([]);
  const [open, setOpen] = useState(null);
  const load = useCallback(() => api.streamStatus().then((r) => setMods(r.modules)).catch(() => {}), [api]);
  useEffect(() => { load(); const id = setInterval(load, 10000); return () => clearInterval(id); }, [load]);

  const cmd = async (mod, c) => {
    try { await api.streamCmd(mod.id, c); load(); } catch (e) { toast.error(e?.response?.data?.detail || "Command failed"); }
  };
  const zoneNames = Object.fromEntries((state?.audio_zones || []).map((z) => [z.id, z.name]));

  return (
    <div className="space-y-3" data-testid="stream-panel">
      <div className="flex items-center gap-2">
        <Music2 className="w-4 h-4" style={{ color: "var(--c4-amber)" }} />
        <p className="font-semibold text-sm">Streaming</p>
        <span className="text-[11px]" style={{ color: "var(--c4-muted)" }}>· built-in modules, no phone needed</span>
      </div>
      <div className="grid sm:grid-cols-2 gap-3">
        {mods.map((m) => <ModuleCard key={m.id} mod={m} zoneNames={zoneNames} onCmd={cmd} onOpen={setOpen} />)}
      </div>
      {open && <FavouriteSheet mod={open} onClose={() => setOpen(null)} onDone={() => { setOpen(null); load(); }} />}
    </div>
  );
};

export default StreamPanel;
