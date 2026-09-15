import React, { useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Plus, Clock, Activity, Trash2, Play, X, CalendarClock } from "lucide-react";
import { useSystem } from "@/context/SystemContext";
import { toast } from "sonner";

const DAYS = ["S", "M", "T", "W", "T", "F", "S"];

const triggerText = (a) => {
  const t = a.trigger || {};
  if (t.type === "event") return `When ${t.event} detected`;
  const days = t.days || [];
  const dayLabel = days.length === 7 || days.length === 0 ? "Every day" : days.map((d) => DAYS[d]).join(" ");
  return `${t.time} · ${dayLabel}`;
};

const CreateModal = ({ open, onClose, scenes, onCreate }) => {
  const [name, setName] = useState("");
  const [type, setType] = useState("schedule");
  const [time, setTime] = useState("22:00");
  const [days, setDays] = useState([0, 1, 2, 3, 4, 5, 6]);
  const [sceneId, setSceneId] = useState(scenes[0]?.id || "");

  const toggleDay = (d) => setDays((p) => (p.includes(d) ? p.filter((x) => x !== d) : [...p, d].sort()));

  const save = () => {
    if (!name.trim() || !sceneId) return toast.error("Name and scene are required");
    const trigger = type === "schedule" ? { type, time, days } : { type: "event", event: "motion" };
    onCreate({ name: name.trim(), enabled: true, trigger, action: { scene_id: sceneId } });
    setName(""); setType("schedule"); setTime("22:00"); setDays([0, 1, 2, 3, 4, 5, 6]);
    onClose();
  };

  return (
    <AnimatePresence>
      {open && (
        <>
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} onClick={onClose}
            className="fixed inset-0 z-40" style={{ background: "rgba(10,13,20,0.85)" }} />
          <motion.div
            initial={{ opacity: 0, y: 40 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: 40 }}
            className="fixed left-1/2 top-1/2 z-50 -translate-x-1/2 -translate-y-1/2 w-[92%] max-w-md"
            data-testid="automation-modal"
          >
            <div className="glass-elevated rounded-3xl flex flex-col max-h-[85vh] overflow-hidden">
              <div className="p-5 overflow-y-auto no-scrollbar flex-1">
              <div className="flex items-center justify-between mb-4">
                <h3 className="font-head font-bold text-lg">New Automation</h3>
                <button data-testid="close-automation-modal" onClick={onClose} className="w-8 h-8 rounded-lg glass flex items-center justify-center"><X className="w-4 h-4" /></button>
              </div>

              <label className="text-xs font-semibold" style={{ color: "var(--c4-muted)" }}>Name</label>
              <input
                data-testid="automation-name-input"
                value={name} onChange={(e) => setName(e.target.value)}
                placeholder="e.g. Good Night at bedtime"
                className="w-full mt-1 mb-4 rounded-xl px-3 py-2.5 text-sm outline-none"
                style={{ background: "var(--c4-surface)", border: "1px solid var(--c4-border)", color: "var(--c4-text)" }}
              />

              <label className="text-xs font-semibold" style={{ color: "var(--c4-muted)" }}>Trigger</label>
              <div className="grid grid-cols-2 gap-2 mt-1 mb-4">
                {[{ id: "schedule", label: "Schedule", icon: Clock }, { id: "event", label: "Motion", icon: Activity }].map((o) => (
                  <button
                    key={o.id}
                    data-testid={`trigger-type-${o.id}`}
                    onClick={() => setType(o.id)}
                    className="rounded-xl py-2.5 flex items-center justify-center gap-2 text-sm font-semibold transition"
                    style={{ background: type === o.id ? "rgba(59,130,246,0.15)" : "rgba(255,255,255,0.05)", color: type === o.id ? "var(--c4-primary)" : "var(--c4-muted)", border: type === o.id ? "1px solid var(--c4-primary)" : "1px solid transparent" }}
                  >
                    <o.icon className="w-4 h-4" /> {o.label}
                  </button>
                ))}
              </div>

              {type === "schedule" && (
                <div className="mb-4">
                  <input
                    type="time" value={time} onChange={(e) => setTime(e.target.value)}
                    data-testid="automation-time-input"
                    className="w-full rounded-xl px-3 py-2.5 text-sm outline-none mb-3"
                    style={{ background: "var(--c4-surface)", border: "1px solid var(--c4-border)", color: "var(--c4-text)" }}
                  />
                  <div className="flex justify-between gap-1.5">
                    {DAYS.map((d, i) => (
                      <button
                        key={i}
                        data-testid={`automation-day-${i}`}
                        onClick={() => toggleDay(i)}
                        className="flex-1 aspect-square rounded-lg text-xs font-bold transition"
                        style={{ background: days.includes(i) ? "var(--c4-primary)" : "rgba(255,255,255,0.05)", color: days.includes(i) ? "#fff" : "var(--c4-muted)" }}
                      >
                        {d}
                      </button>
                    ))}
                  </div>
                </div>
              )}

              <label className="text-xs font-semibold" style={{ color: "var(--c4-muted)" }}>Run scene</label>
              <div className="grid grid-cols-2 gap-2 mt-1 mb-5">
                {scenes.map((s) => (
                  <button
                    key={s.id}
                    data-testid={`automation-scene-${s.id}`}
                    onClick={() => setSceneId(s.id)}
                    className="rounded-xl py-2.5 text-sm font-semibold transition"
                    style={{ background: sceneId === s.id ? "rgba(99,102,241,0.15)" : "rgba(255,255,255,0.05)", color: sceneId === s.id ? "var(--c4-indigo)" : "var(--c4-muted)", border: sceneId === s.id ? "1px solid var(--c4-indigo)" : "1px solid transparent" }}
                  >
                    {s.name}
                  </button>
                ))}
              </div>

              </div>
              <div className="p-4 shrink-0" style={{ borderTop: "1px solid var(--c4-border)" }}>
                <button
                  data-testid="save-automation-btn"
                  onClick={save}
                  className="w-full rounded-xl py-3 text-sm font-bold active:scale-95 transition"
                  style={{ background: "var(--c4-primary)", color: "#fff" }}
                >
                  Create Automation
                </button>
              </div>
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
};

export const Automations = () => {
  const { state, api } = useSystem();
  const [autos, setAutos] = useState([]);
  const [open, setOpen] = useState(false);

  const load = async () => setAutos(await api.getAutomations());
  useEffect(() => { load(); }, []);

  const create = async (payload) => {
    await api.createAutomation(payload);
    await load();
    toast.success("Automation created");
  };
  const toggle = async (a) => {
    await api.updateAutomation(a.id, { ...a, enabled: !a.enabled });
    await load();
  };
  const runNow = async (a) => {
    await api.runAutomation(a.id);
    toast.success(`Ran "${a.name}"`);
  };
  const remove = async (a) => {
    await api.deleteAutomation(a.id);
    await load();
  };

  const sceneName = (id) => state?.scenes.find((s) => s.id === id)?.name || id;

  return (
    <div data-testid="automations-section">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <CalendarClock className="w-5 h-5" style={{ color: "var(--c4-cyan)" }} />
          <h2 className="font-head font-bold text-lg">Automations</h2>
        </div>
        <button
          data-testid="new-automation-btn"
          onClick={() => setOpen(true)}
          className="flex items-center gap-1.5 rounded-xl px-3 py-2 text-xs font-semibold active:scale-95 transition"
          style={{ background: "rgba(59,130,246,0.15)", color: "var(--c4-primary)", border: "1px solid rgba(59,130,246,0.3)" }}
        >
          <Plus className="w-4 h-4" /> New
        </button>
      </div>

      {autos.length === 0 && (
        <div className="glass rounded-2xl p-6 text-center">
          <p className="text-sm" style={{ color: "var(--c4-muted)" }}>No automations yet. Create one to run a scene on a schedule or when motion is detected.</p>
        </div>
      )}

      <div className="space-y-2.5">
        {autos.map((a) => (
          <div key={a.id} data-testid={`automation-row-${a.id}`} className="glass rounded-2xl p-4 flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl flex items-center justify-center shrink-0" style={{ background: a.trigger.type === "event" ? "rgba(239,68,68,0.15)" : "rgba(6,182,212,0.15)" }}>
              {a.trigger.type === "event" ? <Activity className="w-5 h-5" style={{ color: "var(--c4-rose)" }} /> : <Clock className="w-5 h-5" style={{ color: "var(--c4-cyan)" }} />}
            </div>
            <div className="flex-1 min-w-0">
              <p className="font-semibold text-sm truncate">{a.name}</p>
              <p className="text-[11px]" style={{ color: "var(--c4-muted)" }}>{triggerText(a)} → {sceneName(a.action.scene_id)}</p>
            </div>
            <button data-testid={`automation-run-${a.id}`} onClick={() => runNow(a)} className="w-8 h-8 rounded-lg glass-elevated flex items-center justify-center active:scale-90 transition" title="Run now">
              <Play className="w-3.5 h-3.5" style={{ color: "var(--c4-emerald)" }} />
            </button>
            <button
              data-testid={`automation-toggle-${a.id}`}
              onClick={() => toggle(a)}
              className="w-11 h-6 rounded-full relative transition shrink-0"
              style={{ background: a.enabled ? "var(--c4-primary)" : "rgba(255,255,255,0.12)" }}
            >
              <span className="absolute top-0.5 w-5 h-5 rounded-full bg-white transition-all" style={{ left: a.enabled ? "22px" : "2px" }} />
            </button>
            <button data-testid={`automation-delete-${a.id}`} onClick={() => remove(a)} className="w-8 h-8 rounded-lg glass-elevated flex items-center justify-center active:scale-90 transition">
              <Trash2 className="w-3.5 h-3.5" style={{ color: "var(--c4-muted)" }} />
            </button>
          </div>
        ))}
      </div>

      <CreateModal open={open} onClose={() => setOpen(false)} scenes={state?.scenes || []} onCreate={create} />
    </div>
  );
};

export default Automations;
