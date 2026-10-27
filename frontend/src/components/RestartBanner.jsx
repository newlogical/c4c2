import React, { useEffect, useState } from "react";
import { Power } from "lucide-react";
import { api } from "@/lib/api";

const DAY_MS = 24 * 3600 * 1000;
const fmt = (iso) => new Date(iso).toLocaleString([], { weekday: "short", month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });

// Shown for 24 h after the mini-PC itself restarts (power cut, Windows update); hides on its own.
export const RestartBanner = () => {
  const [reboot, setReboot] = useState(null);

  useEffect(() => {
    const poll = () => api.alerts().then((r) => setReboot(r.reboot || null)).catch(() => {});
    poll();
    const id = setInterval(poll, 60000);
    return () => clearInterval(id);
  }, []);

  if (!reboot || Date.now() - new Date(reboot.back_online_at).getTime() > DAY_MS) return null;
  return (
    <div data-testid="restart-banner" className="mx-4 sm:mx-6 mt-4 rounded-2xl p-4 flex items-start gap-3"
      style={{ background: "rgba(245,158,11,0.12)", border: "1px solid rgba(245,158,11,0.45)" }}>
      <Power className="w-5 h-5 mt-0.5 shrink-0" style={{ color: "var(--c4-amber)" }} />
      <div className="min-w-0">
        <p className="font-semibold text-sm" data-testid="restart-banner-title">
          Back online since {fmt(reboot.back_online_at)}
        </p>
        <p className="text-xs mt-0.5" style={{ color: "var(--c4-muted)" }} data-testid="restart-banner-detail">
          The controller restarted on its own (power cut or Windows update). Everything reconnected automatically.
        </p>
      </div>
    </div>
  );
};

export default RestartBanner;
