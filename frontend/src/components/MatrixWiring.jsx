import React, { useState } from "react";
import { Cable, Wand2 } from "lucide-react";
import { toast } from "sonner";
import { useSystem } from "@/context/SystemContext";
import { MatrixIdentify } from "@/components/MatrixIdentify";

const NUMS = [1, 2, 3, 4];

const Picker = ({ label, value, onChange, testid }) => (
  <label className="flex items-center justify-between gap-2 text-xs py-1">
    <span>{label}</span>
    <select
      data-testid={testid} value={value} onChange={(e) => onChange(Number(e.target.value))}
      className="rounded-lg px-2 py-1 text-xs font-mono outline-none"
      style={{ background: "var(--c4-bg)", border: "1px solid var(--c4-border)", color: "var(--c4-text)" }}
    >
      {NUMS.map((n) => <option key={n} value={n}>{n}</option>)}
    </select>
  </label>
);

export const MatrixWiring = () => {
  const { state, act, api } = useSystem();
  const [wizard, setWizard] = useState(false);
  if (!state) return null;

  const save = async (body) => {
    try {
      await act(api.matrixMap(body));
      toast.success("Matrix wiring saved");
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Could not save wiring");
    }
  };
  // Swap numbers so each output/input stays unique
  const change = (list, field, key, id, val) => {
    const other = list.find((x) => x[field] === val && x.id !== id);
    const cur = list.find((x) => x.id === id)[field];
    save({ [key]: { [id]: val, ...(other ? { [other.id]: cur } : {}) } });
  };

  return (
    <div className="glass rounded-2xl p-4" data-testid="matrix-wiring-card">
      <div className="flex items-center gap-2 mb-2">
        <Cable className="w-4 h-4" style={{ color: "var(--c4-cyan)" }} />
        <p className="font-semibold text-sm flex-1">Matrix wiring</p>
        <button
          data-testid="matrix-identify-open-btn" onClick={() => setWizard(true)}
          className="text-[11px] font-semibold px-3 py-1.5 rounded-lg flex items-center gap-1 active:scale-95 transition"
          style={{ background: "rgba(34,211,238,0.15)", color: "var(--c4-cyan)" }}
        >
          <Wand2 className="w-3.5 h-3.5" /> Identify outputs
        </button>
      </div>
      <p className="text-[10px] uppercase tracking-widest mt-2" style={{ color: "var(--c4-muted)" }}>Output → TV</p>
      {state.displays.map((d) => (
        <Picker key={d.id} label={d.name} value={d.output} testid={`matrix-output-${d.id}`} onChange={(v) => change(state.displays, "output", "outputs", d.id, v)} />
      ))}
      <p className="text-[10px] uppercase tracking-widest mt-3" style={{ color: "var(--c4-muted)" }}>Input → Apple TV</p>
      {state.sources.map((s) => (
        <Picker key={s.id} label={s.name} value={s.input} testid={`matrix-input-${s.id}`} onChange={(v) => change(state.sources, "input", "inputs", s.id, v)} />
      ))}
      <MatrixIdentify open={wizard} onClose={() => setWizard(false)} onSave={save} />
    </div>
  );
};

export default MatrixWiring;
