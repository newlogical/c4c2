import React, { useState } from "react";
import { Tv, Loader2, CheckCircle2, AlertTriangle, Wrench } from "lucide-react";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { errText } from "@/context/ListenContext";

const status = (t) => {
  if (!t.ok) return { Icon: AlertTriangle, color: "var(--c4-red, #F87171)", text: t.expects_arc ? "Couldn't set ARC" : "Not answering" };
  if (t.simulated) return { Icon: CheckCircle2, color: "var(--c4-muted)", text: "Demo — not checked" };
  if (t.fixed) return { Icon: Wrench, color: "var(--c4-amber)", text: "Switched to ARC" };
  return { Icon: CheckCircle2, color: "var(--c4-emerald)", text: t.expects_arc ? "On ARC" : "Checked" };
};

const Result = ({ t }) => {
  const { Icon, color, text } = status(t);
  return (
    <div className="flex items-start gap-3 py-2.5" data-testid={`tv-sound-${t.tv_id}`}>
      <Icon className="w-4 h-4 mt-0.5 shrink-0" style={{ color }} />
      <div className="min-w-0 flex-1">
        <div className="flex items-center justify-between gap-2">
          <span className="text-sm font-semibold truncate">{t.name}</span>
          <span className="text-[11px] font-semibold shrink-0" style={{ color }} data-testid={`tv-sound-${t.tv_id}-status`}>{text}</span>
        </div>
        <p className="text-[11px] mt-0.5" style={{ color: "var(--c4-muted)" }} data-testid={`tv-sound-${t.tv_id}-output`}>
          {t.output_label ? `Sound output: ${t.output_label}` : t.error || "Sound output unknown"}
          {!t.expects_arc && " · left as is"}
        </p>
      </div>
    </div>
  );
};

export const TvSoundCheck = ({ onDone }) => {
  const [busy, setBusy] = useState(false);
  const [res, setRes] = useState(null);
  const run = async () => {
    setBusy(true);
    try {
      setRes(await api.tvSoundCheck());
      onDone?.();
    } catch (e) {
      toast.error(errText(e));
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="glass rounded-2xl p-4" data-testid="tv-sound-check">
      <div className="flex items-center gap-3">
        <Tv className="w-5 h-5 shrink-0" style={{ color: "var(--c4-cyan)" }} />
        <div className="flex-1 min-w-0">
          <p className="font-semibold text-sm">TV sound check</p>
          <p className="text-[11px]" style={{ color: "var(--c4-muted)" }}>Reads every TV's sound output and puts Living Room and Master Bedroom back on ARC.</p>
        </div>
        <button data-testid="tv-sound-check-btn" onClick={run} disabled={busy}
          className="shrink-0 px-4 h-10 rounded-xl text-sm font-semibold flex items-center gap-2 active:scale-95 transition-transform disabled:opacity-60"
          style={{ background: "var(--c4-amber)", color: "#0A0D14" }}>
          {busy && <Loader2 className="w-4 h-4 animate-spin" />}{busy ? "Checking" : "Check"}
        </button>
      </div>
      {res && (
        <div className="mt-3 divide-y divide-white/5" style={{ borderTop: "1px solid var(--c4-border)" }} data-testid="tv-sound-results">
          {res.tvs.map((t) => <Result key={t.tv_id} t={t} />)}
        </div>
      )}
    </div>
  );
};
