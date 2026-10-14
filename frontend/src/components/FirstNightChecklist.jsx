import { createPortal } from "react-dom";
import React, { useCallback, useEffect, useState } from "react";
import { X, CheckCircle2, Circle, ArrowRight, Loader2, RefreshCw } from "lucide-react";
import { toast } from "sonner";
import { useSystem } from "@/context/SystemContext";

const Row = ({ item, onTick, onGo }) => (
  <div className="flex items-start gap-3 py-2.5" data-testid={`checklist-item-${item.id}`}>
    <button
      data-testid={`checklist-tick-${item.id}`}
      disabled={!item.manual_allowed || item.auto}
      onClick={() => onTick(item)}
      className="mt-0.5 shrink-0 disabled:cursor-default"
      title={item.auto ? "Detected automatically" : item.manual_allowed ? "Tap to tick" : "Ticks itself when detected"}
    >
      {item.done
        ? <CheckCircle2 className="w-5 h-5" style={{ color: "var(--c4-emerald)" }} />
        : <Circle className="w-5 h-5" style={{ color: "var(--c4-muted)" }} />}
    </button>
    <div className="flex-1 min-w-0">
      <p className={`text-sm font-medium ${item.done ? "line-through opacity-60" : ""}`}>{item.title}</p>
      <p className="text-[11px]" style={{ color: "var(--c4-muted)" }}>
        {item.hint}{item.auto ? " · detected" : item.manual_allowed ? " · tap the circle when done" : ""}
      </p>
    </div>
    {item.target && (
      <button
        data-testid={`checklist-go-${item.id}`} onClick={() => onGo(item.target)}
        className="shrink-0 text-[11px] font-semibold px-2.5 py-1.5 rounded-lg flex items-center gap-1 active:scale-95 transition"
        style={{ background: "rgba(34,211,238,0.12)", color: "var(--c4-cyan)" }}
      >
        Go <ArrowRight className="w-3 h-3" />
      </button>
    )}
  </div>
);

export const FirstNightChecklist = ({ open, onClose, onGo }) => {
  const { api } = useSystem();
  const [data, setData] = useState(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    setBusy(true);
    try { setData(await api.checklist()); } catch { toast.error("Could not load checklist"); } finally { setBusy(false); }
  }, [api]);
  useEffect(() => { if (open) load(); }, [open, load]);

  if (!open) return null;
  const tick = async (item) => {
    const done = !item.done;
    setData((d) => ({ ...d, done: d.done + (done ? 1 : -1), items: d.items.map((i) => (i.id === item.id ? { ...i, done } : i)) }));
    try { setData(await api.checklistTick(item.id, done)); } catch { toast.error("Could not save"); load(); }
  };
  const groups = data ? [...new Set(data.items.map((i) => i.group))] : [];
  const pct = data ? Math.round((data.done / data.total) * 100) : 0;

  return createPortal(
    <div className="fixed inset-0 z-[80] flex flex-col" style={{ background: "var(--c4-bg)" }} data-testid="checklist-panel">
      <div className="px-5 pt-5 pb-3 flex items-start justify-between">
        <div>
          <p className="text-[10px] uppercase tracking-widest" style={{ color: "var(--c4-cyan)" }}>Mini-PC install</p>
          <h2 className="text-2xl font-semibold">First-night checklist</h2>
          <p className="text-xs mt-1" style={{ color: "var(--c4-muted)" }} data-testid="checklist-progress-text">
            {data ? `${data.done} of ${data.total} done` : "Checking…"}
          </p>
        </div>
        <div className="flex gap-2">
          <button data-testid="checklist-refresh-btn" onClick={load} className="w-9 h-9 rounded-xl glass flex items-center justify-center">
            {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <RefreshCw className="w-4 h-4" />}
          </button>
          <button data-testid="checklist-close-btn" onClick={onClose} className="w-9 h-9 rounded-xl glass flex items-center justify-center"><X className="w-4 h-4" /></button>
        </div>
      </div>
      <div className="px-5">
        <div className="h-1.5 rounded-full overflow-hidden" style={{ background: "var(--c4-border)" }}>
          <div data-testid="checklist-progress-bar" className="h-full rounded-full" style={{ width: `${pct}%`, background: "var(--c4-emerald)", transition: "width 400ms ease" }} />
        </div>
      </div>
      <div className="flex-1 overflow-y-auto no-scrollbar px-5 py-4 space-y-4">
        {groups.map((g) => (
          <div key={g} className="glass rounded-2xl px-4 py-2" data-testid={`checklist-group-${g.replace(/\W+/g, "-").toLowerCase()}`}>
            <p className="text-[10px] uppercase tracking-widest pt-2" style={{ color: "var(--c4-muted)" }}>{g}</p>
            <div className="divide-y" style={{ borderColor: "var(--c4-border)" }}>
              {data.items.filter((i) => i.group === g).map((i) => <Row key={i.id} item={i} onTick={tick} onGo={(t) => { onClose(); onGo(t); }} />)}
            </div>
          </div>
        ))}
      </div>
    </div>,
    document.body
  );
};

export default FirstNightChecklist;
