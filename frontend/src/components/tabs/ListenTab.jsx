import React, { useState, useEffect } from "react";
import { Volume2, VolumeX, Power, Radio, Speaker, Music, Link2 } from "lucide-react";
import { useSystem } from "@/context/SystemContext";
import { toast } from "sonner";

const ZoneCard = ({ zone, sources, onChange }) => {
  const [vol, setVol] = useState(zone.volume);
  useEffect(() => setVol(zone.volume), [zone.volume]);

  const src = sources.find((s) => s.id === zone.source);

  return (
    <div className="glass rounded-2xl p-4" data-testid={`zone-card-${zone.id}`}>
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2.5">
          <div className="w-9 h-9 rounded-xl flex items-center justify-center" style={{ background: zone.power ? "rgba(245,158,11,0.15)" : "rgba(255,255,255,0.05)" }}>
            <Speaker className="w-4.5 h-4.5" style={{ color: zone.power ? "var(--c4-amber)" : "var(--c4-muted)" }} />
          </div>
          <div>
            <p className="font-semibold text-sm">{zone.name}</p>
            <p className="text-[11px]" style={{ color: "var(--c4-muted)" }}>
              {zone.paired_tv ? "TV + Audio zone" : "Audio only"}
            </p>
          </div>
        </div>
        <button
          data-testid={`zone-power-${zone.id}`}
          onClick={() => onChange({ zone_id: zone.id, power: !zone.power })}
          className="w-9 h-9 rounded-xl flex items-center justify-center active:scale-95 transition"
          style={{ background: zone.power ? "rgba(16,185,129,0.15)" : "rgba(255,255,255,0.05)" }}
        >
          <Power className="w-4 h-4" style={{ color: zone.power ? "var(--c4-emerald)" : "var(--c4-muted)" }} />
        </button>
      </div>

      {/* Volume */}
      <div className="flex items-center gap-3 mb-3">
        <button
          data-testid={`zone-mute-${zone.id}`}
          onClick={() => onChange({ zone_id: zone.id, mute: !zone.mute })}
          className="shrink-0"
        >
          {zone.mute ? (
            <VolumeX className="w-5 h-5" style={{ color: "var(--c4-rose)" }} />
          ) : (
            <Volume2 className="w-5 h-5" style={{ color: "var(--c4-text)" }} />
          )}
        </button>
        <input
          type="range"
          min="0"
          max="100"
          value={zone.mute ? 0 : vol}
          data-testid={`zone-volume-${zone.id}`}
          className="c4-range flex-1"
          onChange={(e) => setVol(Number(e.target.value))}
          onPointerUp={() => onChange({ zone_id: zone.id, volume: vol })}
          onTouchEnd={() => onChange({ zone_id: zone.id, volume: vol })}
        />
        <span className="w-9 text-right text-sm font-mono" style={{ color: "var(--c4-muted)" }}>
          {zone.mute ? "—" : `${vol}%`}
        </span>
      </div>

      {/* Source select */}
      <div className="flex flex-wrap gap-1.5">
        {sources.map((s) => (
          <button
            key={s.id}
            data-testid={`zone-source-${zone.id}-${s.id}`}
            onClick={() => onChange({ zone_id: zone.id, source: s.id })}
            className="rounded-lg px-2.5 py-1.5 text-[11px] font-semibold transition active:scale-95"
            style={{
              background: zone.source === s.id ? "var(--c4-amber)" : "rgba(255,255,255,0.05)",
              color: zone.source === s.id ? "#0A0D14" : "var(--c4-muted)",
            }}
          >
            {s.name}
          </button>
        ))}
      </div>
    </div>
  );
};

export const ListenTab = () => {
  const { state, act, api } = useSystem();
  const [groupSource, setGroupSource] = useState("spotify");
  const [groupVol, setGroupVol] = useState(30);
  if (!state) return null;

  const change = async (payload) => {
    await act(api.zone(payload));
  };

  const applyGroup = async () => {
    await act(api.audioGroup(groupSource, groupVol));
    const name = state.audio_sources.find((s) => s.id === groupSource)?.name;
    toast.success(`All zones synced to ${name}`);
  };

  const toggleFollow = async () => {
    await act(api.setAudioFollow(!state.audio_follow_tv));
  };
  const follow = state.audio_follow_tv;

  return (
    <div className="p-4 sm:p-6 space-y-6 pb-8" data-testid="listen-tab">
      <div>
        <p className="text-[11px] font-semibold uppercase tracking-wider" style={{ color: "var(--c4-amber)" }}>WS66i · 6-Zone Amplifier</p>
        <h1 className="font-head text-2xl font-extrabold tracking-tight">Audio Zones</h1>
      </div>

      {/* Sound follows screen */}
      <button
        data-testid="audio-follow-toggle"
        onClick={toggleFollow}
        className="w-full glass rounded-2xl p-3.5 flex items-center justify-between active:scale-[0.99] transition"
      >
        <div className="flex items-center gap-2.5">
          <div className="w-9 h-9 rounded-xl flex items-center justify-center" style={{ background: follow ? "rgba(6,182,212,0.15)" : "rgba(255,255,255,0.05)" }}>
            <Link2 className="w-4.5 h-4.5" style={{ color: follow ? "var(--c4-cyan)" : "var(--c4-muted)" }} />
          </div>
          <div className="text-left">
            <p className="font-semibold text-sm">Sound follows screen</p>
            <p className="text-[11px]" style={{ color: "var(--c4-muted)" }}>A room's audio switches to its TV's source</p>
          </div>
        </div>
        <span className="w-11 h-6 rounded-full relative transition shrink-0" style={{ background: follow ? "var(--c4-emerald)" : "rgba(255,255,255,0.12)" }}>
          <span className="absolute top-0.5 w-5 h-5 rounded-full bg-white transition-all" style={{ left: follow ? "22px" : "2px" }} />
        </span>
      </button>

      {/* Whole home group */}
      <div className="glass rounded-2xl p-4">
        <div className="flex items-center gap-2 mb-3">
          <Radio className="w-4 h-4" style={{ color: "var(--c4-indigo)" }} />
          <p className="font-semibold text-sm">Whole-Home Audio</p>
        </div>
        <div className="flex flex-wrap gap-1.5 mb-3">
          {state.audio_sources.map((s) => (
            <button
              key={s.id}
              data-testid={`group-source-${s.id}`}
              onClick={() => setGroupSource(s.id)}
              className="rounded-lg px-2.5 py-1.5 text-[11px] font-semibold transition active:scale-95"
              style={{
                background: groupSource === s.id ? "var(--c4-indigo)" : "rgba(255,255,255,0.05)",
                color: groupSource === s.id ? "#fff" : "var(--c4-muted)",
              }}
            >
              {s.name}
            </button>
          ))}
        </div>
        <div className="flex items-center gap-3 mb-3">
          <Music className="w-4 h-4 shrink-0" style={{ color: "var(--c4-muted)" }} />
          <input
            type="range" min="0" max="100" value={groupVol}
            data-testid="group-volume"
            className="c4-range flex-1"
            onChange={(e) => setGroupVol(Number(e.target.value))}
          />
          <span className="w-9 text-right text-sm font-mono" style={{ color: "var(--c4-muted)" }}>{groupVol}%</span>
        </div>
        <button
          data-testid="apply-group-btn"
          onClick={applyGroup}
          className="w-full rounded-xl py-2.5 text-sm font-semibold active:scale-95 transition"
          style={{ background: "rgba(99,102,241,0.15)", color: "var(--c4-indigo)", border: "1px solid rgba(99,102,241,0.3)" }}
        >
          Sync all 4 zones
        </button>
      </div>

      <div className="grid sm:grid-cols-2 gap-3">
        {state.audio_zones.map((z) => (
          <ZoneCard key={z.id} zone={z} sources={state.audio_sources} onChange={change} />
        ))}
      </div>
    </div>
  );
};

export default ListenTab;
