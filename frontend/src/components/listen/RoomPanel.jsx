import React from "react";
import { MonitorSmartphone, Tv, Smartphone, PartyPopper, Speaker } from "lucide-react";
import { api } from "@/lib/api";
import { useListen } from "@/context/ListenContext";
import { VolumeControl } from "@/components/listen/VolumeControl";
import { StatusPill, Switch } from "@/components/listen/StatusPill";
import { useWiimNowPlaying, NowPlayingText, PlayPauseButton } from "@/components/listen/WiimNowPlaying";

const srcIcon = (label) => (/tv/i.test(label) ? Tv : /mobile|phone/i.test(label) ? Smartphone : Speaker);

const SourceButton = ({ testid, src, on, disabled, onPick }) => {
  const Icon = srcIcon(src.label);
  const streaming = on && src.wiim && src.wiim_mode === "wifi";
  const [np, setNp] = useWiimNowPlaying(src.wiim, streaming);
  return (
    <div className="relative">
      <button data-testid={testid} onClick={() => onPick(src.label)} disabled={disabled}
        className="w-full h-full rounded-2xl p-4 min-h-[88px] flex flex-col items-start justify-between gap-2 text-left active:scale-[0.97] transition-transform disabled:opacity-40"
        style={{ background: on ? "var(--c4-amber)" : "var(--c4-card)", color: on ? "#0A0D14" : "var(--c4-text)",
          border: on ? "1px solid var(--c4-amber)" : "1px solid var(--c4-border)" }}>
        <Icon className="w-5 h-5" />
        <span className={`font-semibold text-base leading-tight ${streaming && np ? "pr-10" : ""}`}>{src.label}</span>
        {streaming && np && <NowPlayingText np={np} testid={`${testid}-now-playing`} />}
      </button>
      {streaming && np && <PlayPauseButton wid={src.wiim} np={np} onChange={setNp} testid={`${testid}-play-pause`} />}
    </div>
  );
};

export const RoomPanel = ({ room, data, onRemote }) => {
  const { run, busy } = useListen();
  const s = room.status;
  // Two buttons can share one amp input (e.g. a WiiM for TV over Bluetooth and for AirPlay): prefer the one last picked.
  const picked = room.sources.find((x) => x.label === s.source_label && x.input === s.input) || room.sources.find((x) => x.input === s.input);
  const current = room.in_party
    ? { label: `Party Mode · ${data.party_sources.find((x) => x.input === data.party.input)?.label || "Party source"}` }
    : picked;
  const shared = (src) => room.sources.filter((x) => x.input === src.input).length > 1;
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
        {room.sources.map((src, i) => (
          <SourceButton key={src.label} src={src} on={s.power && !room.in_party && src === picked} disabled={busy || room.in_party}
            testid={`source-${room.id}-${src.input}${shared(src) ? `-${i}` : ""}`} onPick={(label) => send({ label })} />
        ))}
      </div>
      {s.power && !room.in_party && picked?.wiim_mode === "bluetooth" && (
        <p className="text-xs px-1" style={{ color: "var(--c4-muted)" }} data-testid="room-bt-hint">
          TV sound comes over Bluetooth. If it's silent, turn the TV off and on so it reconnects to the WiiM.
        </p>
      )}

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
