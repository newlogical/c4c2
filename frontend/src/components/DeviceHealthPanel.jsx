import React, { useCallback, useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { X, RefreshCw, Activity, AlertTriangle } from "lucide-react";
import { TvSoundCheck } from "@/components/TvSoundCheck";
import { useSystem } from "@/context/SystemContext";

const Row = ({ d }) => (
  <div className="glass rounded-2xl p-4 flex items-center gap-3" data-testid={`health-row-${d.id}`}>
    <span className="relative flex w-3 h-3 shrink-0">
      {d.online && <span className="absolute inset-0 rounded-full animate-ping opacity-50" style={{ background: "var(--c4-emerald)" }} />}
      <span className="relative w-3 h-3 rounded-full" data-testid={`health-dot-${d.id}`} style={{ background: d.online ? "var(--c4-emerald)" : "var(--c4-rose)" }} />
    </span>
    <div className="flex-1 min-w-0">
      <div className="flex items-center gap-2">
        <p className="font-semibold text-sm truncate">{d.name}</p>
        <span className="text-[9px] font-bold px-1.5 py-0.5 rounded" style={{ background: d.live ? "rgba(16,185,129,0.15)" : "rgba(255,255,255,0.06)", color: d.live ? "var(--c4-emerald)" : "var(--c4-muted)" }}>
          {d.live ? "LIVE" : "DEMO"}
        </span>
      </div>
      <p className="text-[11px] truncate" style={{ color: "var(--c4-muted)" }}>{d.kind}</p>
      <p className="text-[11px] font-mono truncate" style={{ color: "var(--c4-muted)" }} data-testid={`health-ip-${d.id}`}>
        {d.ip}{d.mac ? ` · ${d.mac}` : ""}
      </p>
    </div>
    <div className="text-right shrink-0">
      <p className="text-xs font-semibold" style={{ color: d.online ? "var(--c4-emerald)" : "var(--c4-rose)" }} data-testid={`health-status-${d.id}`}>
        {d.online ? "Online" : "Offline"}
      </p>
      <p className="text-[10px] font-mono" style={{ color: "var(--c4-muted)" }}>{d.online ? `${d.latency_ms} ms` : d.check}</p>
    </div>
  </div>
);

const ArcWarning = ({ w }) => (
  <div className="rounded-2xl p-4 flex items-start gap-3" data-testid={`arc-warning-${w.tv_id}`}
    style={{ background: "rgba(245,158,11,0.12)", border: "1px solid rgba(245,158,11,0.45)" }}>
    <AlertTriangle className="w-5 h-5 mt-0.5 shrink-0" style={{ color: "var(--c4-amber)" }} />
    <div className="min-w-0">
      <p className="font-semibold text-sm">{w.name} isn't on ARC</p>
      <p className="text-[11px] mt-0.5" style={{ color: "var(--c4-muted)" }}>
        Couldn't set its sound output to Audio System at {new Date(w.at).toLocaleTimeString()}. On the TV: Settings → Sound → Sound output → Audio System.
      </p>
      {w.error && <p className="text-[10px] font-mono mt-1 break-words" style={{ color: "var(--c4-muted)" }}>{w.error}</p>}
    </div>
  </div>
);

export const useDeviceHealth = (active) => {
  const { api } = useSystem();
  const [data, setData] = useState(null);
  const [busy, setBusy] = useState(false);
  const load = useCallback(() => {
    setBusy(true);
    return api.deviceHealth().then(setData).catch(() => {}).finally(() => setBusy(false));
  }, [api]);
  useEffect(() => {
    if (!active) return;
    load();
    const id = setInterval(load, 30000);
    return () => clearInterval(id);
  }, [active, load]);
  return { data, busy, load };
};

export const DeviceHealthPanel = ({ open, onClose }) => {
  const { data, busy, load } = useDeviceHealth(open);
  const devices = data?.devices || [];
  return (
    <AnimatePresence>
      {open && (
        <motion.div
          initial={{ opacity: 0, y: 24 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: 24 }}
          transition={{ duration: 0.25 }}
          className="fixed inset-0 z-[60] flex flex-col safe-all" style={{ background: "var(--c4-bg)" }}
          data-testid="device-health-panel"
        >
          <div className="flex items-center justify-between px-5 py-4" style={{ borderBottom: "1px solid var(--c4-border)" }}>
            <div className="flex items-center gap-2.5">
              <Activity className="w-5 h-5" style={{ color: "var(--c4-emerald)" }} />
              <div>
                <p className="font-head font-bold">Device Health</p>
                <p className="text-[11px]" style={{ color: "var(--c4-muted)" }} data-testid="health-summary">
                  {data ? `${data.online} of ${data.total} online · checked ${new Date(data.checked_at).toLocaleTimeString()}` : "Checking…"}
                </p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <button data-testid="health-refresh-btn" onClick={load} disabled={busy} className="w-9 h-9 rounded-xl glass flex items-center justify-center active:scale-95 transition">
                <RefreshCw className={`w-4 h-4 ${busy ? "animate-spin" : ""}`} style={{ color: "var(--c4-cyan)" }} />
              </button>
              <button data-testid="health-close-btn" onClick={onClose} className="w-9 h-9 rounded-xl glass flex items-center justify-center active:scale-95 transition">
                <X className="w-4 h-4" />
              </button>
            </div>
          </div>
          <div className="flex-1 overflow-y-auto no-scrollbar">
            <div className="max-w-2xl mx-auto p-5 space-y-3">
              <p className="text-[11px]" style={{ color: "var(--c4-muted)" }}>
                Checks each device from the controller every 30 s. Devices only show online when the app runs on your home network (mini-PC).
              </p>
              <TvSoundCheck onDone={load} />
              {(data?.arc_warnings || []).map((w) => <ArcWarning key={w.tv_id} w={w} />)}
              {devices.map((d) => <Row key={d.id} d={d} />)}
              {data && devices.length === 0 && <p className="text-sm" style={{ color: "var(--c4-muted)" }}>No devices mapped yet.</p>}
            </div>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
};

export default DeviceHealthPanel;
