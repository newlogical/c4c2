import React, { useEffect, useState } from "react";
import { WifiOff } from "lucide-react";
import { useSystem } from "@/context/SystemContext";

export const OfflineBanner = ({ onOpenHealth }) => {
  const { api } = useSystem();
  const [items, setItems] = useState([]);

  useEffect(() => {
    const poll = () => api.alerts().then((r) => setItems(r.offline_alerts || [])).catch(() => {});
    poll();
    const id = setInterval(poll, 30000);
    return () => clearInterval(id);
  }, [api]);

  if (!items.length) return null;
  const mins = (since) => Math.max(3, Math.round((Date.now() - new Date(since).getTime()) / 60000));
  return (
    <button
      data-testid="offline-banner"
      onClick={onOpenHealth}
      className="w-full rounded-2xl p-4 flex items-start gap-3 text-left active:scale-[0.99] transition"
      style={{ background: "rgba(244,63,94,0.12)", border: "1px solid rgba(244,63,94,0.45)" }}
    >
      <WifiOff className="w-5 h-5 mt-0.5 shrink-0" style={{ color: "var(--c4-rose)" }} />
      <div className="min-w-0">
        <p className="font-semibold text-sm">{items.length === 1 ? `${items[0].name} is offline` : `${items.length} devices are offline`}</p>
        <p className="text-[11px] mt-0.5" style={{ color: "var(--c4-muted)" }}>
          {items.map((d) => `${d.name} (${d.ip}) · ${mins(d.since)} min`).join(" · ")}
        </p>
      </div>
    </button>
  );
};

export default OfflineBanner;
