import React, { useState, useEffect } from "react";
import { toast } from "sonner";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { api } from "@/lib/api";
import { errText } from "@/context/ListenContext";
import { SHORTCUT_ICONS } from "@/lib/shortcutIcons";
import { RoomActionRow } from "@/components/shortcuts/RoomActionRow";
import { Switch } from "@/components/listen/StatusPill";

const field = "w-full rounded-lg px-3 py-2.5 text-sm outline-none";
const fieldStyle = { background: "var(--c4-surface)", border: "1px solid var(--c4-border)", color: "var(--c4-text)" };
const BLANK = { name: "", description: "", icon: "Sparkles", favorite: true, restore_defaults: false, rooms: {}, party: null };

const PartyEditor = ({ party, onChange, data }) => {
  const mode = !party ? "none" : party.enabled ? "on" : "off";
  const rooms = data.rooms.filter((r) => r.visible);
  const setMode = (m) => onChange(m === "none" ? null : m === "off" ? { enabled: false } : { enabled: true, input: data.party_sources[0]?.input, rooms: rooms.map((r) => r.id) });
  return (
    <div className="space-y-2" data-testid="sc-party">
      <p className="text-sm font-semibold">Party Mode</p>
      <div className="grid grid-cols-3 gap-2">
        {[["none", "Leave as is"], ["on", "Turn on"], ["off", "Turn off"]].map(([m, l]) => (
          <button key={m} data-testid={`sc-party-${m}`} onClick={() => setMode(m)} className="rounded-lg py-2 text-xs font-semibold"
            style={{ background: mode === m ? "var(--c4-indigo)" : "rgba(255,255,255,0.05)", color: mode === m ? "#fff" : "var(--c4-muted)" }}>{l}</button>
        ))}
      </div>
      {mode === "on" && (
        <>
          <select data-testid="sc-party-input" value={party.input ?? ""} onChange={(e) => onChange({ ...party, input: Number(e.target.value) })} className={field} style={fieldStyle}>
            {data.party_sources.map((s) => <option key={s.input} value={s.input}>{s.label}</option>)}
          </select>
          <div className="flex flex-wrap gap-2">
            {rooms.map((r) => {
              const on = (party.rooms || []).includes(r.id);
              return (
                <button key={r.id} data-testid={`sc-party-room-${r.id}`} onClick={() => onChange({ ...party, rooms: on ? party.rooms.filter((x) => x !== r.id) : [...(party.rooms || []), r.id] })}
                  className="rounded-full px-3 py-1.5 text-xs font-semibold" style={{ background: on ? "rgba(99,102,241,0.25)" : "rgba(255,255,255,0.05)", color: on ? "var(--c4-text)" : "var(--c4-muted)" }}>{r.name}</button>
              );
            })}
          </div>
        </>
      )}
    </div>
  );
};

export const ShortcutEditor = ({ open, shortcut, data, onClose, onSaved }) => {
  const [f, setF] = useState(BLANK);
  const [saving, setSaving] = useState(false);
  useEffect(() => { if (open) setF(shortcut ? JSON.parse(JSON.stringify(shortcut)) : BLANK); }, [open, shortcut]);
  const set = (k, v) => setF((p) => ({ ...p, [k]: v }));

  const save = async () => {
    if (!f.name.trim()) return toast.error("Give the shortcut a name");
    setSaving(true);
    try {
      const body = { name: f.name.trim(), description: f.description, icon: f.icon, favorite: f.favorite, restore_defaults: f.restore_defaults, rooms: f.rooms, party: f.party };
      await (shortcut ? api.updateShortcut(shortcut.id, body) : api.createShortcut(body));
      toast.success("Shortcut saved");
      onSaved();
    } catch (e) {
      toast.error(errText(e));
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-h-[90vh] overflow-y-auto" style={{ background: "var(--c4-surface)", border: "1px solid var(--c4-border)", color: "var(--c4-text)" }} data-testid="shortcut-editor">
        <DialogHeader><DialogTitle>{shortcut ? "Edit shortcut" : "New shortcut"}</DialogTitle></DialogHeader>
        <div className="space-y-4">
          <input data-testid="sc-name" placeholder="Name" value={f.name} onChange={(e) => set("name", e.target.value)} className={field} style={fieldStyle} maxLength={60} />
          <input data-testid="sc-description" placeholder="Description (optional)" value={f.description} onChange={(e) => set("description", e.target.value)} className={field} style={fieldStyle} />
          <div className="flex flex-wrap gap-2" data-testid="sc-icons">
            {Object.entries(SHORTCUT_ICONS).map(([n, Icon]) => (
              <button key={n} data-testid={`sc-icon-${n}`} onClick={() => set("icon", n)} className="w-10 h-10 rounded-lg flex items-center justify-center"
                style={{ background: f.icon === n ? "rgba(6,182,212,0.2)" : "rgba(255,255,255,0.05)", border: f.icon === n ? "1px solid var(--c4-cyan)" : "1px solid transparent" }}>
                <Icon className="w-4 h-4" />
              </button>
            ))}
          </div>
          <div className="flex items-center justify-between"><span className="text-sm">Show on Listen as a favorite</span><Switch on={f.favorite} testid="sc-favorite" label="Favorite" onClick={() => set("favorite", !f.favorite)} /></div>
          <div className="flex items-center justify-between"><span className="text-sm">Start with Restore Default Audio</span><Switch on={f.restore_defaults} testid="sc-restore" label="Restore defaults" onClick={() => set("restore_defaults", !f.restore_defaults)} /></div>
          <PartyEditor party={f.party} data={data} onChange={(v) => set("party", v)} />
          <div className="space-y-2">
            <p className="text-sm font-semibold">Rooms</p>
            {data.rooms.filter((r) => r.visible).map((r) => (
              <RoomActionRow key={r.id} room={r} action={f.rooms[r.id]} onChange={(a) => set("rooms", { ...f.rooms, [r.id]: a })} />
            ))}
          </div>
          <button data-testid="sc-save" onClick={save} disabled={saving} className="w-full rounded-xl py-3 font-semibold active:scale-[0.98] transition-transform disabled:opacity-50"
            style={{ background: "var(--c4-primary)", color: "#fff" }}>{saving ? "Saving…" : "Save shortcut"}</button>
        </div>
      </DialogContent>
    </Dialog>
  );
};
