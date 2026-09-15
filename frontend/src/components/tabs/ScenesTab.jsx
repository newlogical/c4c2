import React from "react";
import { motion } from "framer-motion";
import { Power, Moon, Clapperboard, Radio, RotateCcw, Sparkles } from "lucide-react";
import { useSystem } from "@/context/SystemContext";
import { Automations } from "@/components/Automations";
import { toast } from "sonner";

const icons = { all_off: Power, good_night: Moon, movie_night: Clapperboard, whole_home_audio: Radio };
const colorFor = (type) => (type === "critical" ? "var(--c4-rose)" : type === "vibrant" ? "var(--c4-indigo)" : "var(--c4-primary)");

export const ScenesTab = () => {
  const { state, act, api } = useSystem();
  if (!state) return null;

  const run = async (sc) => {
    await act(api.scene(sc.id));
    toast.success(`Scene: ${sc.name}`, { description: sc.desc });
  };

  const reset = async () => {
    await act(api.reset());
    toast("System reset to defaults");
  };

  return (
    <div className="p-4 sm:p-6 space-y-5 pb-8" data-testid="scenes-tab">
      <div className="flex items-center gap-2">
        <Sparkles className="w-5 h-5" style={{ color: "var(--c4-indigo)" }} />
        <h1 className="font-head text-2xl font-extrabold tracking-tight">Scenes</h1>
      </div>
      <p className="text-sm" style={{ color: "var(--c4-muted)" }}>
        One tap orchestrates the matrix, amplifier and thermostat together.
      </p>

      <div className="space-y-3">
        {state.scenes.map((sc, i) => {
          const Icon = icons[sc.id] || Radio;
          const color = colorFor(sc.type);
          return (
            <motion.button
              key={sc.id}
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.06 }}
              data-testid={`scene-${sc.id}`}
              onClick={() => run(sc)}
              className="w-full glass rounded-2xl p-5 flex items-center gap-4 text-left active:scale-[0.98] transition hover:border-[var(--c4-border-med)]"
            >
              <div className="w-12 h-12 rounded-2xl flex items-center justify-center shrink-0" style={{ background: `${color}22` }}>
                <Icon className="w-6 h-6" style={{ color }} />
              </div>
              <div className="flex-1">
                <p className="font-head font-bold">{sc.name}</p>
                <p className="text-xs mt-0.5" style={{ color: "var(--c4-muted)" }}>{sc.desc}</p>
              </div>
              <div className="text-xs font-semibold px-3 py-1.5 rounded-lg" style={{ background: `${color}18`, color }}>
                Run
              </div>
            </motion.button>
          );
        })}
      </div>

      <Automations />

      <button
        data-testid="reset-system-btn"
        onClick={reset}
        className="w-full glass rounded-2xl p-4 flex items-center justify-center gap-2 text-sm font-semibold active:scale-95 transition"
        style={{ color: "var(--c4-muted)" }}
      >
        <RotateCcw className="w-4 h-4" /> Reset system to defaults
      </button>
    </div>
  );
};

export default ScenesTab;
