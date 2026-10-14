import React, { useEffect, useState } from "react";
import { X, RefreshCw } from "lucide-react";
import { toast } from "sonner";
import { useSystem } from "@/context/SystemContext";

const NUMS = [1, 2, 3, 4];
const btn = "rounded-xl px-3 py-2.5 text-xs font-semibold active:scale-95 transition";

// Phase "out": flip output n between input 2 and 1 -> the TV that blinks is output n.
// Phase "in": show input k on a known TV -> user says which Apple TV it is (test key helps).
export const MatrixIdentify = ({ open, onClose, onSave }) => {
  const { state, api } = useSystem();
  const [phase, setPhase] = useState("out");
  const [n, setN] = useState(1);
  const [outs, setOuts] = useState({});
  const [ins, setIns] = useState({});
  const [flip, setFlip] = useState(1);
  const live = !!state?.config?.matrix?.live;

  const viewOut = phase === "in" ? (outs.tv_living || state?.displays?.[0]?.output || 1) : n;
  const route = async (input, output) => {
    const r = await api.matrixIdentify(input, output).catch((e) => ({ ok: false, error: e?.response?.data?.detail }));
    if (!r.ok) toast.error(r.error || "Matrix command failed");
  };
  const show = async (f = flip) => {
    if (phase === "out") await route(f, n);
    else await route(n, viewOut);
  };

  useEffect(() => {
    if (open) show(1);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, phase, n]);

  if (!open || !state) return null;
  const reset = () => { setPhase("out"); setN(1); setOuts({}); setIns({}); setFlip(1); };
  const close = () => { reset(); onClose(); };

  const pickTv = (id) => {
    const next = { ...outs, [id]: n };
    setOuts(next);
    if (n < 4) setN(n + 1);
    else { setPhase("in"); setN(1); }
  };
  const pickAtv = async (id) => {
    const next = { ...ins, [id]: n };
    setIns(next);
    if (n < 4) { setN(n + 1); return; }
    await onSave({ outputs: outs, inputs: next });
    close();
  };
  const usedTv = new Set(Object.keys(outs));
  const usedAtv = new Set(Object.keys(ins));

  return (
    <div className="fixed inset-0 z-[80] flex items-center justify-center p-4" style={{ background: "rgba(5,7,12,0.8)", backdropFilter: "blur(16px)" }} data-testid="matrix-identify-modal">
      <div className="glass rounded-2xl p-5 w-full max-w-md">
        <div className="flex items-center justify-between mb-1">
          <p className="text-[10px] uppercase tracking-widest" style={{ color: "var(--c4-cyan)" }}>
            {phase === "out" ? `Step 1 · Output ${n} of 4` : `Step 2 · Input ${n} of 4`}
          </p>
          <button data-testid="matrix-identify-close-btn" onClick={close}><X className="w-4 h-4" /></button>
        </div>
        {!live && <p className="text-[11px] mb-2" style={{ color: "var(--c4-amber)" }} data-testid="matrix-identify-demo-note">Demo mode: matrix commands are simulated. Run this on the mini-PC with the matrix LIVE.</p>}
        {phase === "out" ? (
          <>
            <p className="font-semibold text-sm mb-1" data-testid="matrix-identify-question">Which TV just went black for a moment?</p>
            <p className="text-[11px] mb-3" style={{ color: "var(--c4-muted)" }}>Turn all four TVs on first. The app switched matrix output {n}; the TV it feeds blanks briefly while the picture reconnects.</p>
            <div className="grid grid-cols-2 gap-2">
              {state.displays.map((d) => (
                <button key={d.id} data-testid={`identify-tv-${d.id}`} disabled={usedTv.has(d.id)} onClick={() => pickTv(d.id)} className={`${btn} disabled:opacity-30`} style={{ background: "var(--c4-bg)" }}>{d.name}</button>
              ))}
            </div>
          </>
        ) : (
          <>
            <p className="font-semibold text-sm mb-1" data-testid="matrix-identify-question">Which Apple TV is on the {state.displays.find((d) => d.id === "tv_living")?.name || "first TV"} now?</p>
            <p className="text-[11px] mb-3" style={{ color: "var(--c4-muted)" }}>Matrix input {n} is shown there. Not sure? Tap “Test” to send Home to that Apple TV and see if the screen reacts.</p>
            <div className="space-y-2">
              {state.sources.map((s) => (
                <div key={s.id} className="flex gap-2">
                  <button data-testid={`identify-atv-${s.id}`} disabled={usedAtv.has(s.id)} onClick={() => pickAtv(s.id)} className={`${btn} flex-1 disabled:opacity-30`} style={{ background: "var(--c4-bg)" }}>{s.name}</button>
                  <button data-testid={`identify-test-${s.id}`} onClick={() => api.remote(s.id, "home").catch(() => {})} className={btn} style={{ background: "rgba(34,211,238,0.12)", color: "var(--c4-cyan)" }}>Test</button>
                </div>
              ))}
            </div>
          </>
        )}
        <div className="flex gap-2 mt-4">
          <button data-testid="matrix-identify-again-btn" onClick={() => { const f = flip === 1 ? 2 : 1; setFlip(f); show(f); }} className={`${btn} flex-1 flex items-center justify-center gap-1`} style={{ background: "var(--c4-bg)" }}>
            <RefreshCw className="w-3.5 h-3.5" /> {phase === "out" ? "Switch again" : "Show again"}
          </button>
          <button data-testid="matrix-identify-restart-btn" onClick={reset} className={btn} style={{ color: "var(--c4-muted)" }}>Restart</button>
        </div>
        <div className="flex gap-1 mt-3 justify-center">
          {NUMS.map((i) => <span key={i} className="w-6 h-1 rounded-full" style={{ background: (phase === "in" || i <= n) ? "var(--c4-cyan)" : "var(--c4-border)" }} />)}
        </div>
      </div>
    </div>
  );
};

export default MatrixIdentify;
