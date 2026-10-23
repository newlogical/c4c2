import React, { useState, useEffect } from "react";
import { Volume2, VolumeX, Minus, Plus } from "lucide-react";

const Step = ({ onClick, icon: Icon, testid, disabled }) => (
  <button data-testid={testid} onClick={onClick} disabled={disabled}
    className="w-11 h-11 shrink-0 rounded-xl flex items-center justify-center glass-elevated active:scale-90 transition-transform disabled:opacity-40">
    <Icon className="w-4 h-4" />
  </button>
);

// Slider + mute + quick steps. Sends one command on release, never while dragging.
export const VolumeControl = ({ id, status, max = 100, onChange, disabled }) => {
  const [v, setV] = useState(status.volume);
  const [drag, setDrag] = useState(false);
  useEffect(() => { if (!drag) setV(status.volume); }, [status.volume, drag]);

  const commit = async (val) => {
    const n = Math.max(0, Math.min(max, Math.round(val)));
    setDrag(false);
    setV(n);
    if ((await onChange({ volume: n })) === false) setV(status.volume); // amp refused: show the real level
  };

  return (
    <div className="flex items-center gap-2" data-testid={`volume-${id}`}>
      <button data-testid={`mute-${id}`} disabled={disabled} onClick={() => onChange({ mute: !status.mute })}
        className="w-11 h-11 shrink-0 rounded-xl flex items-center justify-center active:scale-90 transition-transform disabled:opacity-40"
        style={{ background: status.mute ? "rgba(239,68,68,0.15)" : "rgba(255,255,255,0.05)" }}
        aria-label={status.mute ? "Unmute" : "Mute"}>
        {status.mute ? <VolumeX className="w-5 h-5" style={{ color: "var(--c4-rose)" }} /> : <Volume2 className="w-5 h-5" />}
      </button>
      <Step testid={`vol-down-${id}`} icon={Minus} disabled={disabled} onClick={() => commit(v - 5)} />
      <input type="range" min="0" max={max} value={v} disabled={disabled} data-testid={`vol-slider-${id}`}
        className="c4-range flex-1 min-w-0"
        onChange={(e) => { setDrag(true); setV(Number(e.target.value)); }}
        onPointerUp={(e) => commit(Number(e.currentTarget.value))}
        onKeyUp={(e) => /^(Arrow|Home|End|Page)/.test(e.key) && commit(Number(e.currentTarget.value))} />
      <Step testid={`vol-up-${id}`} icon={Plus} disabled={disabled} onClick={() => commit(v + 5)} />
      <span className="w-14 text-right text-sm font-mono tabular-nums" style={{ color: status.mute ? "var(--c4-rose)" : "var(--c4-muted)" }} data-testid={`vol-readout-${id}`}>
        {status.mute ? "Muted" : `${v}%`}
      </span>
    </div>
  );
};
