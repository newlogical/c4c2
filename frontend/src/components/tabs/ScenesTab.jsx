import React, { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Power, Moon, Clapperboard, Radio, RotateCcw, Sparkles, Plus, Trash2, X, Film, Coffee, Sun, Pencil, ListPlus, Tv, Star } from "lucide-react";
import { useSystem } from "@/context/SystemContext";
import { Automations } from "@/components/Automations";
import { PresetBuilder } from "@/components/PresetBuilder";
import { toast } from "sonner";

const icons = { all_off: Power, good_night: Moon, movie_night: Clapperboard, whole_home_audio: Radio };
const iconByName = { Sparkles, Moon, Clapperboard, Radio, Film, Coffee, Sun, Power, Tv };
const PICKER = ["Sparkles", "Film", "Coffee", "Sun", "Moon", "Radio"];
const colorFor = (type) => (type === "critical" ? "var(--c4-rose)" : type === "vibrant" ? "var(--c4-indigo)" : "var(--c4-primary)");

const CreateSceneModal = ({ open, onClose, onCreate }) => {
  const [name, setName] = useState("");
  const [icon, setIcon] = useState("Sparkles");
  const [type, setType] = useState("vibrant");

  const save = () => {
    if (!name.trim()) return toast.error("Give your scene a name");
    onCreate({ name: name.trim(), icon, type });
    setName(""); setIcon("Sparkles"); setType("vibrant");
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
            className="fixed inset-x-0 top-0 bottom-0 m-auto h-fit max-h-[90vh] overflow-y-auto z-50 w-[92%] max-w-md"
            data-testid="create-scene-modal"
          >
            <div className="glass-elevated rounded-3xl p-5">
              <div className="flex items-center justify-between mb-2">
                <h3 className="font-head font-bold text-lg">Save current setup</h3>
                <button data-testid="close-scene-modal" onClick={onClose} className="w-8 h-8 rounded-lg glass flex items-center justify-center"><X className="w-4 h-4" /></button>
              </div>
              <p className="text-xs mb-4" style={{ color: "var(--c4-muted)" }}>
                Captures every TV, audio zone and the thermostat exactly as they are right now, saved as a one-tap scene.
              </p>
              <input
                data-testid="scene-name-input"
                value={name} onChange={(e) => setName(e.target.value)}
                placeholder="e.g. Sunday Morning"
                className="w-full mb-4 rounded-xl px-3 py-2.5 text-sm outline-none"
                style={{ background: "var(--c4-surface)", border: "1px solid var(--c4-border)", color: "var(--c4-text)" }}
              />
              <label className="text-xs font-semibold" style={{ color: "var(--c4-muted)" }}>Icon</label>
              <div className="flex flex-wrap gap-2 mt-2 mb-5">
                {PICKER.map((n) => {
                  const I = iconByName[n];
                  const on = icon === n;
                  return (
                    <button key={n} data-testid={`scene-icon-${n}`} onClick={() => setIcon(n)}
                      className="w-11 h-11 rounded-xl flex items-center justify-center transition active:scale-95"
                      style={{ background: on ? "rgba(99,102,241,0.18)" : "rgba(255,255,255,0.05)", border: on ? "1px solid var(--c4-indigo)" : "1px solid transparent" }}>
                      <I className="w-5 h-5" style={{ color: on ? "var(--c4-indigo)" : "var(--c4-muted)" }} />
                    </button>
                  );
                })}
              </div>
              <button data-testid="save-scene-btn" onClick={save}
                className="w-full rounded-xl py-3 text-sm font-bold active:scale-95 transition"
                style={{ background: "var(--c4-primary)", color: "#fff" }}>
                Save scene
              </button>
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
};

export const ScenesTab = () => {
  const { state, act, api } = useSystem();
  const [scenes, setScenes] = useState([]);
  const [modal, setModal] = useState(false);
  const [builder, setBuilder] = useState(null);

  const load = async () => setScenes(await api.getScenes());
  useEffect(() => { load(); }, []);

  const run = async (sc) => {
    await act(api.scene(sc.id));
    toast.success(`Scene: ${sc.name}`, { description: sc.desc });
  };
  const create = async (payload) => {
    await api.createScene(payload);
    await load();
    toast.success("Scene saved");
  };
  const remove = async (sc) => {
    await api.deleteScene(sc.id);
    await load();
    toast(`Removed "${sc.name}"`);
  };
  const pinned = state?.pinned_scenes || [];
  const togglePin = async (sc) => {
    const on = !pinned.includes(sc.id);
    await act(api.pinScene(sc.id, on));
    toast(on ? `Pinned "${sc.name}" to Home` : `Unpinned "${sc.name}"`);
  };
  const reset = async () => {
    await act(api.reset());
    await load();
    toast("System reset to defaults");
  };

  if (!state) return null;

  return (
    <div className="p-4 sm:p-6 space-y-5 pb-8" data-testid="scenes-tab">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Sparkles className="w-5 h-5" style={{ color: "var(--c4-indigo)" }} />
          <h1 className="font-head text-2xl font-extrabold tracking-tight">Scenes</h1>
        </div>
        <div className="flex gap-2">
        <button
          data-testid="new-preset-btn"
          onClick={() => setBuilder({})}
          className="flex items-center gap-1.5 rounded-xl px-3 py-2 text-xs font-semibold active:scale-95 transition"
          style={{ background: "var(--c4-indigo)", color: "#fff" }}
        >
          <ListPlus className="w-4 h-4" /> New preset
        </button>
        <button
          data-testid="new-scene-btn"
          onClick={() => setModal(true)}
          className="flex items-center gap-1.5 rounded-xl px-3 py-2 text-xs font-semibold active:scale-95 transition"
          style={{ background: "rgba(99,102,241,0.15)", color: "var(--c4-indigo)", border: "1px solid rgba(99,102,241,0.3)" }}
        >
          <Plus className="w-4 h-4" /> Save current
        </button>
        </div>
      </div>
      <p className="text-sm" style={{ color: "var(--c4-muted)" }}>
        One tap orchestrates the matrix, amplifier and thermostat together.
      </p>

      <div className="space-y-3">
        {scenes.map((sc, i) => {
          const Icon = icons[sc.id] || iconByName[sc.icon] || Sparkles;
          const color = colorFor(sc.type);
          return (
            <motion.div
              key={sc.id}
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: Math.min(i * 0.05, 0.4) }}
              className="w-full glass rounded-2xl p-5 flex items-center gap-4 hover:border-[var(--c4-border-med)]"
            >
              <button data-testid={`scene-${sc.id}`} onClick={() => run(sc)} className="flex items-center gap-4 flex-1 text-left active:scale-[0.98] transition">
                <div className="w-12 h-12 rounded-2xl flex items-center justify-center shrink-0" style={{ background: `${color}22` }}>
                  <Icon className="w-6 h-6" style={{ color }} />
                </div>
                <div className="flex-1">
                  <p className="font-head font-bold flex items-center gap-2">
                    {sc.name}
                    {sc.custom && <span className="text-[9px] font-bold uppercase px-1.5 py-0.5 rounded" style={{ background: "rgba(99,102,241,0.18)", color: "var(--c4-indigo)" }}>Custom</span>}
                  </p>
                  <p className="text-xs mt-0.5" style={{ color: "var(--c4-muted)" }}>{sc.desc}</p>
                </div>
              </button>
              <button data-testid={`scene-pin-${sc.id}`} onClick={() => togglePin(sc)} aria-label="Pin to Home" className="w-9 h-9 rounded-lg glass-elevated flex items-center justify-center active:scale-90 transition">
                <Star className="w-4 h-4" style={pinned.includes(sc.id) ? { color: "var(--c4-amber)", fill: "var(--c4-amber)" } : { color: "var(--c4-muted)" }} />
              </button>
              {sc.actions && (
                <button data-testid={`scene-edit-${sc.id}`} onClick={() => setBuilder({ preset: sc })} className="w-9 h-9 rounded-lg glass-elevated flex items-center justify-center active:scale-90 transition">
                  <Pencil className="w-4 h-4" style={{ color: "var(--c4-muted)" }} />
                </button>
              )}
              {sc.custom ? (
                <button data-testid={`scene-delete-${sc.id}`} onClick={() => remove(sc)} className="w-9 h-9 rounded-lg glass-elevated flex items-center justify-center active:scale-90 transition">
                  <Trash2 className="w-4 h-4" style={{ color: "var(--c4-muted)" }} />
                </button>
              ) : (
                <div className="text-xs font-semibold px-3 py-1.5 rounded-lg" style={{ background: `${color}18`, color }}>Run</div>
              )}
            </motion.div>
          );
        })}
      </div>

      <Automations scenes={scenes} />

      <button
        data-testid="reset-system-btn"
        onClick={reset}
        className="w-full glass rounded-2xl p-4 flex items-center justify-center gap-2 text-sm font-semibold active:scale-95 transition"
        style={{ color: "var(--c4-muted)" }}
      >
        <RotateCcw className="w-4 h-4" /> Reset system to defaults
      </button>

      <PresetBuilder open={!!builder} preset={builder?.preset} onClose={() => setBuilder(null)} onSaved={() => { setBuilder(null); load(); }} />
      <CreateSceneModal open={modal} onClose={() => setModal(false)} onCreate={create} />
    </div>
  );
};

export default ScenesTab;
