import React, { useState } from "react";
import { Loader2, Link2, CheckCircle2 } from "lucide-react";
import { toast } from "sonner";
import { useSystem } from "@/context/SystemContext";

const STEPS = [["companion", "Companion (remote keys)"], ["airplay", "AirPlay (control channel)"]];

export const AtvPair = ({ aid, dev }) => {
  const { api, setState } = useSystem();
  const [step, setStep] = useState(null);
  const [pin, setPin] = useState("");
  const [busy, setBusy] = useState(false);
  const paired = !!(dev.credentials && dev.airplay_credentials);
  const err = (e) => toast.error(e?.response?.data?.detail || "Pairing failed");

  const begin = async (idx) => {
    setBusy(true);
    try {
      await api.atvPairStart(aid, STEPS[idx][0]);
      setStep(idx);
      setPin("");
      toast.message(`Enter the PIN shown on the Apple TV (${STEPS[idx][1]})`);
    } catch (e) { err(e); setStep(null); } finally { setBusy(false); }
  };
  const submit = async () => {
    setBusy(true);
    try {
      const st = await api.atvPairFinish(aid, STEPS[step][0], pin);
      setState(st);
      if (step + 1 < STEPS.length) { setBusy(false); return begin(step + 1); }
      toast.success("Apple TV paired");
      setStep(null);
    } catch (e) { err(e); } finally { setBusy(false); }
  };

  if (step === null) {
    return (
      <button data-testid={`atv-pair-btn-${aid}`} disabled={busy} onClick={() => begin(0)} className="mt-2 w-full rounded-lg py-2 text-xs font-semibold flex items-center justify-center gap-2 glass-elevated active:scale-95 transition">
        {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : paired ? <CheckCircle2 className="w-4 h-4" style={{ color: "var(--c4-emerald)" }} /> : <Link2 className="w-4 h-4" style={{ color: "var(--c4-cyan)" }} />}
        {paired ? "Paired · pair again" : "Pair this Apple TV"}
      </button>
    );
  }
  return (
    <div className="mt-2 space-y-2" data-testid={`atv-pair-step-${aid}`}>
      <p className="text-[11px]" style={{ color: "var(--c4-muted)" }}>Step {step + 1}/2 · {STEPS[step][1]}: type the 4-digit PIN on the TV screen.</p>
      <div className="flex gap-2">
        <input data-testid={`atv-pin-input-${aid}`} inputMode="numeric" maxLength={4} value={pin} onChange={(e) => setPin(e.target.value.replace(/\D/g, ""))} placeholder="PIN" className="flex-1 rounded-lg px-3 py-2 text-sm font-mono outline-none" style={{ background: "var(--c4-surface)", border: "1px solid var(--c4-border)" }} />
        <button data-testid={`atv-pin-submit-${aid}`} disabled={busy || pin.length !== 4} onClick={submit} className="rounded-lg px-4 text-xs font-semibold disabled:opacity-40" style={{ background: "var(--c4-cyan)", color: "#04121a" }}>
          {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : "Pair"}
        </button>
        <button data-testid={`atv-pair-cancel-${aid}`} onClick={() => setStep(null)} className="text-[11px] underline" style={{ color: "var(--c4-muted)" }}>Cancel</button>
      </div>
    </div>
  );
};

export default AtvPair;
