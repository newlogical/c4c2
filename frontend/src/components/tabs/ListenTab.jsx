import React, { useState } from "react";
import { RotateCcw, Loader2, MonitorSmartphone } from "lucide-react";
import { api } from "@/lib/api";
import { useListen } from "@/context/ListenContext";
import { useSystem } from "@/context/SystemContext";
import { RoomPanel } from "@/components/listen/RoomPanel";
import { PartyPanel } from "@/components/listen/PartyPanel";
import { FavoriteShortcuts } from "@/components/listen/FavoriteShortcuts";

const RoomTabs = ({ rooms, tab, setTab, partyOn }) => (
  <div className="flex gap-2 overflow-x-auto no-scrollbar -mx-4 px-4 sm:mx-0 sm:px-0" role="tablist" data-testid="room-tabs">
    {[...rooms.map((r) => ({ id: r.id, label: r.name, on: r.status.power })), { id: "party", label: "Party Mode", on: partyOn }].map((t) => {
      const sel = tab === t.id;
      return (
        <button key={t.id} role="tab" aria-selected={sel} data-testid={`room-tab-${t.id}`} onClick={() => setTab(t.id)}
          className="shrink-0 rounded-full px-4 py-2.5 text-sm font-semibold flex items-center gap-2 transition-colors"
          style={{ background: sel ? "var(--c4-text)" : "rgba(255,255,255,0.05)", color: sel ? "#0A0D14" : "var(--c4-muted)" }}>
          {t.label}
          <span className="w-1.5 h-1.5 rounded-full" style={{ background: t.on ? "var(--c4-emerald)" : "rgba(148,163,184,0.4)" }} />
        </button>
      );
    })}
  </div>
);

export const ListenTab = ({ onRemote }) => {
  const { data, run, busy } = useListen();
  const { state } = useSystem();
  const [tab, setTab] = useState("living");
  if (!data) return <div className="p-10 flex justify-center"><Loader2 className="w-6 h-6 animate-spin" /></div>;

  const rooms = data.rooms.filter((r) => r.visible);
  const current = tab === "party" ? null : rooms.find((r) => r.id === tab) || rooms[0];
  const roomTvs = new Set(rooms.map((r) => r.tv_id));
  const otherTvs = (state?.displays || []).filter((d) => !roomTvs.has(d.id));

  return (
    <div className="p-4 sm:p-6 space-y-5 pb-8" data-testid="listen-tab">
      <div className="flex items-end justify-between gap-3">
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-wider" style={{ color: "var(--c4-amber)" }}>Audio · WS66i</p>
          <h1 className="font-head text-4xl sm:text-5xl font-extrabold tracking-tight">Listen</h1>
        </div>
        <button data-testid="restore-default-audio" disabled={busy} onClick={() => run(api.restoreDefaults(), "Default audio restored")}
          className="rounded-xl px-3.5 py-2.5 text-sm font-semibold flex items-center gap-2 active:scale-95 transition-transform disabled:opacity-50"
          style={{ background: "rgba(6,182,212,0.14)", color: "var(--c4-cyan)", border: "1px solid rgba(6,182,212,0.35)" }}>
          <RotateCcw className="w-4 h-4" /> Restore Default Audio
        </button>
      </div>

      <FavoriteShortcuts />
      <RoomTabs rooms={rooms} tab={current ? current.id : "party"} setTab={setTab} partyOn={data.party.active} />
      {current ? <RoomPanel room={current} data={data} onRemote={onRemote} /> : <PartyPanel data={data} />}

      {otherTvs.length > 0 && (
        <div className="pt-2" data-testid="other-tv-controls">
          <p className="text-[11px] font-semibold uppercase tracking-wider mb-2" style={{ color: "var(--c4-muted)" }}>TV Controls</p>
          <div className="flex flex-wrap gap-2">
            {otherTvs.map((d) => (
              <button key={d.id} data-testid={`tv-remote-${d.id}`} onClick={() => onRemote(d.id)}
                className="glass rounded-xl px-3.5 py-2.5 text-sm font-semibold flex items-center gap-2 active:scale-95 transition-transform">
                <MonitorSmartphone className="w-4 h-4" style={{ color: "var(--c4-primary)" }} /> {d.name}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

export default ListenTab;
