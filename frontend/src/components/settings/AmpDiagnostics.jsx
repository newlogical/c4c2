import React, { useEffect } from "react";
import { RefreshCw } from "lucide-react";
import { api } from "@/lib/api";
import { useListen } from "@/context/ListenContext";
import { useSystem } from "@/context/SystemContext";
import { StatusPill } from "@/components/listen/StatusPill";

const COLORS = { confirmed: "var(--c4-emerald)", sent: "var(--c4-emerald)", simulated: "var(--c4-amber)", error: "var(--c4-rose)" };

// Admin view: amp link state, a manual status read, and the last WS66i commands with their outcome.
export const AmpDiagnostics = () => {
  const { data, run, busy } = useListen();
  const { state, refresh } = useSystem();
  useEffect(() => { refresh(); }, [refresh, data?.synced_at]);
  if (!data) return null;
  const log = (state?.command_log || []).filter((e) => e.driver === "WS66i").slice(0, 8);

  return (
    <div className="glass rounded-2xl p-4 space-y-3" data-testid="amp-diagnostics">
      <div className="flex items-center justify-between">
        <p className="font-semibold text-sm">Amplifier diagnostics</p>
        <StatusPill data={data} />
      </div>
      <p className="text-[11px]" style={{ color: "var(--c4-muted)" }} data-testid="amp-diag-detail">
        {data.amp_error || (data.synced_at ? `Last status read ${new Date(data.synced_at).toLocaleTimeString()}` : data.live ? "Not read yet" : "Demo mode: commands are simulated, not sent")}
      </p>
      <div className="grid grid-cols-2 gap-1.5 text-[11px] font-mono" data-testid="amp-diag-zones">
        {data.rooms.filter((r) => r.visible).map((r) => (
          <span key={r.id} style={{ color: "var(--c4-muted)" }}>Z{r.amp_zone} {r.name.split(" ")[0]}: {r.status.power ? "on" : "off"} · src {r.status.input} · {r.status.volume}%{r.status.mute ? " · muted" : ""}</span>
        ))}
      </div>
      <button data-testid="amp-diag-read" disabled={busy || !data.live} onClick={async () => { await run(api.listenSync(), "Amp status read"); refresh(); }}
        className="w-full rounded-lg py-2 text-xs font-semibold glass-elevated flex items-center justify-center gap-2 disabled:opacity-40">
        <RefreshCw className="w-3.5 h-3.5" /> Read status from amp
      </button>
      <div className="space-y-1" data-testid="amp-diag-log">
        {log.map((e, i) => (
          <div key={`${e.timestamp}-${i}`} className="text-[10px] font-mono flex gap-2">
            <span style={{ color: COLORS[e.status] || "var(--c4-muted)" }}>{e.status}</span>
            <span className="truncate" style={{ color: "var(--c4-muted)" }} title={e.error || e.command}>{e.note}{e.error ? ` — ${e.error}` : ""}</span>
          </div>
        ))}
      </div>
    </div>
  );
};
