import React from "react";
import { PartyPopper, Minus, Plus } from "lucide-react";
import { api } from "@/lib/api";
import { useListen } from "@/context/ListenContext";
import { VolumeControl } from "@/components/listen/VolumeControl";
import { StatusPill, Switch } from "@/components/listen/StatusPill";

const RoomRow = ({ room, party, busy, run }) => {
  const joined = party.rooms.includes(room.id);
  return (
    <div className="glass rounded-2xl p-4 space-y-3" data-testid={`party-room-${room.id}`}>
      <div className="flex items-center justify-between">
        <span className="font-semibold">{room.name}</span>
        <Switch on={joined} label={`${room.name} joins the party`} testid={`party-join-${room.id}`} disabled={busy}
          onClick={() => run(api.partyRoom(room.id, !joined))} />
      </div>
      {party.active && joined && (
        <VolumeControl id={`party-${room.id}`} status={room.status} max={room.max_volume} disabled={busy}
          onChange={(body) => run(api.listenRoom(room.id, body))} />
      )}
    </div>
  );
};

export const PartyPanel = ({ data }) => {
  const { run, busy } = useListen();
  const p = data.party;
  const rooms = data.rooms.filter((r) => r.visible);

  return (
    <div className="space-y-4" data-testid="party-panel">
      <div className="rounded-2xl p-5 flex items-center justify-between gap-3"
        style={{ background: p.active ? "rgba(99,102,241,0.16)" : "var(--c4-card)", border: `1px solid ${p.active ? "rgba(99,102,241,0.45)" : "var(--c4-border)"}` }}>
        <div>
          <h2 className="font-head text-xl font-bold flex items-center gap-2"><PartyPopper className="w-5 h-5" style={{ color: "var(--c4-indigo)" }} /> Party Mode</h2>
          <p className="text-sm mt-0.5" style={{ color: "var(--c4-muted)" }}>One source in every room you choose</p>
          <div className="mt-2"><StatusPill data={data} /></div>
        </div>
        <Switch on={p.active} label="Party Mode" testid="party-toggle" disabled={busy}
          onClick={() => run(api.party(!p.active), p.active ? "Party Mode off — rooms restored" : "Party Mode on")} />
      </div>

      <div className="grid grid-cols-2 gap-3">
        {data.party_sources.map((s) => {
          const on = p.input === s.input;
          return (
            <button key={s.input} data-testid={`party-source-${s.input}`} disabled={busy} onClick={() => run(api.partySource(s.input))}
              className="rounded-2xl p-4 min-h-[76px] text-left font-semibold active:scale-[0.97] transition-transform disabled:opacity-40"
              style={{ background: on ? "var(--c4-indigo)" : "var(--c4-card)", color: on ? "#fff" : "var(--c4-text)", border: `1px solid ${on ? "var(--c4-indigo)" : "var(--c4-border)"}` }}>
              {s.label}
            </button>
          );
        })}
      </div>

      {p.active && (
        <div className="glass rounded-2xl p-4 flex items-center justify-between" data-testid="party-master">
          <span className="text-sm font-semibold">All party rooms</span>
          <div className="flex gap-2">
            <button data-testid="party-master-down" disabled={busy} onClick={() => run(api.partyMaster(-5))} className="w-12 h-11 rounded-xl glass-elevated flex items-center justify-center active:scale-90 transition-transform"><Minus className="w-4 h-4" /></button>
            <button data-testid="party-master-up" disabled={busy} onClick={() => run(api.partyMaster(5))} className="w-12 h-11 rounded-xl glass-elevated flex items-center justify-center active:scale-90 transition-transform"><Plus className="w-4 h-4" /></button>
          </div>
        </div>
      )}

      <div className="space-y-3">
        {rooms.map((r) => <RoomRow key={r.id} room={r} party={p} busy={busy} run={run} />)}
      </div>
    </div>
  );
};
