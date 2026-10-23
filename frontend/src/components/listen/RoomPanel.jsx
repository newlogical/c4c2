import React from "react";
import { MonitorSmartphone, Tv, Smartphone, PartyPopper, Speaker } from "lucide-react";
import { api } from "@/lib/api";
import { useListen } from "@/context/ListenContext";
import { VolumeControl } from "@/components/listen/VolumeControl";
import { StatusPill, Switch } from "@/components/listen/StatusPill";

const srcIcon = (label) => (/tv/i.test(label) ? Tv : /mobile|phone/i.test(label) ? Smartphone : Speaker);

const SourceButton = ({ room, src, on, disabled, onPick }) => {
  const Icon = srcIcon(src.label);
  return (
    <button data-testid={`source-${room.id}-${src.input}`} onClick={() => onPick(src.input)} disabled={disabled}
      className="rounded-2xl p-4 min-h-[88px] flex flex-col items-start justify-between text-left active:scale-[0.97] transition-transform disabled:opacity-40"
      style={{ background: on ? "var(--c4-amber)" : "var(--c4-card)", color: on ? "#0A0D14" : "var(--c4-text)",
        border: on ? "1px solid var(--c4-amber)" : "1px solid var(--c4-border)" }}>
      <Icon className="w-5 h-5" />
      <span className="font-semibold text-base leading-tight">{src.label}</span>
    </button>
  );
};

export const RoomPanel = ({ room, data, onRemote }) => {
  const { run, busy } = useListen();
  const s = room.status;
  const current = room.in_party
    ? { label: `Party Mode · ${data.party_sources.find((x) => x.input === data.party.input)?.label || "Party source"}` }
    : room.sources.find((x) => x.input === s.input);
  const send = (body) => run(api.listenRoom(room.id, body));

  return (
    <div className="space-y-4" data-testid={`room-panel-${room.id}`}>
      <div className="glass rounded-2xl p-4 flex items-center justify-between gap-3">
        <div className="min-w-0">
          <h2 className="font-head text-xl font-bold tracking-tight truncate" data-testid="room-name">{room.name}</h2>
          <p className="text-sm mt-0.5" style={{ color: "var(--c4-muted)" }} data-testid="room-current-source">
            {s.power ? <>Playing <b style={{ color: "var(--c4-text)" }}>{current?.label || "Other source"}</b></> : "Speakers off"}
          </p>
          <div className="mt-2"><StatusPill data={data} /></div>
        </div>
        <Switch on={s.power} label={`${room.name} speakers`} testid={`room-power-${room.id}`} disabled={busy} onClick={() => send({ power: !s.power })} />
      </div>

      {room.in_party && (
        <div className="rounded-2xl p-3.5 flex items-center justify-between gap-3" style={{ background: "rgba(99,102,241,0.12)", border: "1px solid rgba(99,102,241,0.3)" }} data-testid="room-in-party">
          <span className="flex items-center gap-2 text-sm"><PartyPopper className="w-4 h-4" style={{ color: "var(--c4-indigo)" }} /> Playing Party Mode</span>
          <button data-testid="room-leave-party" onClick={() => run(api.partyRoom(room.id, false), `${room.name} left the party`)}
            className="rounded-lg px-3 py-2 text-xs font-semibold glass-elevated">Leave party</button>
        </div>
      )}

      <div className="grid grid-cols-2 gap-3">
        {room.sources.map((src) => (
          <SourceButton key={src.input} room={room} src={src} on={s.power && s.input === src.input} disabled={busy || room.in_party}
            onPick={(input) => send({ input })} />
        ))}
      </div>

      <div className="glass rounded-2xl p-4">
        <p className="text-[11px] font-semibold uppercase tracking-wider mb-3" style={{ color: "var(--c4-muted)" }}>Volume</p>
        <VolumeControl id={room.id} status={s} max={room.max_volume} onChange={send} disabled={busy} />
      </div>

      {room.tv_id && (
        <button data-testid={`tv-remote-${room.id}`} onClick={() => onRemote(room.tv_id)}
          className="w-full glass rounded-2xl p-4 flex items-center gap-3 active:scale-[0.99] transition-transform">
          <div className="w-11 h-11 rounded-xl flex items-center justify-center" style={{ background: "rgba(59,130,246,0.15)" }}>
            <MonitorSmartphone className="w-5 h-5" style={{ color: "var(--c4-primary)" }} />
          </div>
          <div className="text-left">
            <p className="font-semibold">TV Remote</p>
            <p className="text-xs" style={{ color: "var(--c4-muted)" }}>Power, volume, menus and apps on the {room.name} TV</p>
          </div>
        </button>
      )}
    </div>
  );
};
