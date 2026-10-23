import React, { useState } from "react";
import { Plus, Play, Star, ChevronUp, ChevronDown, Pencil, Copy, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { useListen, errText } from "@/context/ListenContext";
import { shortcutIcon, summarize } from "@/lib/shortcutIcons";
import { ShortcutEditor } from "@/components/shortcuts/ShortcutEditor";

const IconBtn = ({ icon: Icon, onClick, testid, label, active, disabled }) => (
  <button data-testid={testid} aria-label={label} title={label} onClick={onClick} disabled={disabled}
    className="w-10 h-10 rounded-lg flex items-center justify-center active:scale-90 transition-transform disabled:opacity-30"
    style={{ background: "rgba(255,255,255,0.05)", color: active ? "var(--c4-amber)" : "var(--c4-muted)" }}>
    <Icon className="w-4 h-4" fill={active ? "currentColor" : "none"} />
  </button>
);

const ShortcutCard = ({ sc, i, count, data, onRun, onEdit, onAction, busy }) => {
  const Icon = shortcutIcon(sc.icon);
  return (
    <div className="glass rounded-2xl p-4 space-y-3" data-testid={`shortcut-${sc.id}`}>
      <div className="flex items-start gap-3">
        <div className="w-11 h-11 rounded-xl flex items-center justify-center shrink-0" style={{ background: "rgba(6,182,212,0.14)" }}>
          <Icon className="w-5 h-5" style={{ color: "var(--c4-cyan)" }} />
        </div>
        <div className="min-w-0 flex-1">
          <p className="font-semibold">{sc.name}</p>
          <p className="text-xs mt-0.5" style={{ color: "var(--c4-muted)" }}>{sc.description || summarize(sc, data.rooms, data.party_sources)}</p>
        </div>
        <button data-testid={`shortcut-run-${sc.id}`} disabled={busy} onClick={onRun}
          className="rounded-xl px-4 h-11 flex items-center gap-1.5 text-sm font-semibold active:scale-95 transition-transform disabled:opacity-50"
          style={{ background: "var(--c4-primary)", color: "#fff" }}><Play className="w-4 h-4" /> Run</button>
      </div>
      <div className="flex gap-1.5 flex-wrap">
        <IconBtn icon={Star} label="Favorite" testid={`shortcut-fav-${sc.id}`} active={sc.favorite} onClick={() => onAction("fav")} />
        <IconBtn icon={ChevronUp} label="Move up" testid={`shortcut-up-${sc.id}`} disabled={i === 0} onClick={() => onAction("up")} />
        <IconBtn icon={ChevronDown} label="Move down" testid={`shortcut-down-${sc.id}`} disabled={i === count - 1} onClick={() => onAction("down")} />
        <IconBtn icon={Pencil} label="Edit" testid={`shortcut-edit-${sc.id}`} onClick={onEdit} />
        <IconBtn icon={Copy} label="Duplicate" testid={`shortcut-dup-${sc.id}`} onClick={() => onAction("dup")} />
        <IconBtn icon={Trash2} label="Delete" testid={`shortcut-del-${sc.id}`} onClick={() => onAction("del")} />
      </div>
    </div>
  );
};

export const ShortcutsTab = () => {
  const { data, shortcuts, setShortcuts, loadShortcuts, run, busy } = useListen();
  const [editing, setEditing] = useState(undefined); // undefined = closed, null = new
  if (!data) return null;

  const action = async (sc, i, kind) => {
    try {
      if (kind === "fav") await api.favoriteShortcut(sc.id, !sc.favorite);
      if (kind === "dup") toast.success("Shortcut duplicated", { description: (await api.duplicateShortcut(sc.id)).name });
      if (kind === "del") {
        if (!window.confirm(`Delete "${sc.name}"?`)) return;
        await api.deleteShortcut(sc.id);
      }
      if (kind === "up" || kind === "down") {
        const ids = shortcuts.map((s) => s.id);
        const j = kind === "up" ? i - 1 : i + 1;
        [ids[i], ids[j]] = [ids[j], ids[i]];
        setShortcuts(await api.reorderShortcuts(ids));
        return;
      }
      await loadShortcuts();
    } catch (e) {
      toast.error(errText(e));
    }
  };

  return (
    <div className="p-4 sm:p-6 space-y-5 pb-8" data-testid="shortcuts-tab">
      <div className="flex items-end justify-between gap-3">
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-wider" style={{ color: "var(--c4-cyan)" }}>One-tap audio</p>
          <h1 className="font-head text-4xl sm:text-5xl font-extrabold tracking-tight">Shortcuts</h1>
        </div>
        <button data-testid="shortcut-new" onClick={() => setEditing(null)} className="rounded-xl px-3.5 py-2.5 text-sm font-semibold flex items-center gap-2 glass-elevated active:scale-95 transition-transform">
          <Plus className="w-4 h-4" /> New
        </button>
      </div>
      <div className="space-y-3">
        {shortcuts.map((sc, i) => (
          <ShortcutCard key={sc.id} sc={sc} i={i} count={shortcuts.length} data={data} busy={busy}
            onRun={() => run(api.runShortcut(sc.id), `${sc.name} done`)} onEdit={() => setEditing(sc)} onAction={(k) => action(sc, i, k)} />
        ))}
        {!shortcuts.length && <p className="text-sm" style={{ color: "var(--c4-muted)" }}>No shortcuts yet. Tap New to make one.</p>}
      </div>
      <ShortcutEditor open={editing !== undefined} shortcut={editing} data={data} onClose={() => setEditing(undefined)}
        onSaved={() => { setEditing(undefined); loadShortcuts(); }} />
    </div>
  );
};

export default ShortcutsTab;
