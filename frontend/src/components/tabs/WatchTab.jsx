import React, { useState } from "react";
import { motion } from "framer-motion";
import { Tv, Power, Gamepad2, Tv2, Cast, Check, Volume2, VolumeX, Volume1 } from "lucide-react";
import { useSystem } from "@/context/SystemContext";
import { AppleTVRemote } from "@/components/AppleTVRemote";
import { SonyRemote } from "@/components/SonyRemote";
import { toast } from "sonner";

const MEDIA = "https://images.unsplash.com/photo-1662454420647-3d20ddcdb8f8?crop=entropy&cs=srgb&fm=jpg&q=85&w=1200";

export const WatchTab = () => {
  const { state, act, api } = useSystem();
  const [remoteSource, setRemoteSource] = useState(null);
  const [sonyDisplay, setSonyDisplay] = useState(null);
  if (!state) return null;

  const route = async (displayId, sourceId) => {
    await act(api.route(displayId, sourceId));
  };
  const broadcast = async (sourceId, name) => {
    await act(api.broadcast(sourceId));
    toast.success(`${name} sent to all 4 TVs`);
  };
  const togglePower = async (d) => {
    await act(api.displayPower(d.id, !d.power));
  };
  const tvVol = async (d, key) => {
    await api.tvKey(d.id, key);
  };
  const setTvVolume = async (d, v) => {
    await api.tvVolume(d.id, v);
    toast.success(`${d.name} volume ${v}%`, { description: "Sony Bravia absolute level" });
  };

  return (
    <div className="p-4 sm:p-6 space-y-6 pb-8" data-testid="watch-tab">
      {/* Header */}
      <div className="relative rounded-3xl overflow-hidden h-32">
        <img src={MEDIA} alt="Video" className="w-full h-full object-cover" />
        <div className="absolute inset-0" style={{ background: "linear-gradient(to right, rgba(10,13,20,0.95), rgba(10,13,20,0.4))" }} />
        <div className="absolute inset-0 flex flex-col justify-center px-5">
          <p className="text-[11px] font-semibold uppercase tracking-wider" style={{ color: "var(--c4-primary)" }}>JTECH-MXT40 · 4×4 HDBaseT</p>
          <h1 className="font-head text-2xl font-extrabold tracking-tight">Video Routing</h1>
        </div>
      </div>

      {/* Broadcast bar */}
      <div className="glass rounded-2xl p-4">
        <div className="flex items-center gap-2 mb-3">
          <Cast className="w-4 h-4" style={{ color: "var(--c4-indigo)" }} />
          <p className="font-semibold text-sm">Broadcast a source to all TVs</p>
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
          {state.sources.map((s) => (
            <button
              key={s.id}
              data-testid={`broadcast-${s.id}`}
              onClick={() => broadcast(s.id, s.name)}
              className="rounded-xl py-2.5 text-xs font-semibold active:scale-95 transition"
              style={{ background: "rgba(99,102,241,0.12)", color: "var(--c4-indigo)", border: "1px solid rgba(99,102,241,0.25)" }}
            >
              {s.name}
            </button>
          ))}
        </div>
      </div>

      {/* Matrix grid */}
      <div>
        <h2 className="font-head font-bold text-lg mb-3">Matrix Router</h2>
        <div className="glass rounded-2xl p-3 overflow-x-auto no-scrollbar">
          <table className="w-full border-collapse" data-testid="matrix-grid">
            <thead>
              <tr>
                <th className="text-left p-2 text-[11px] font-semibold uppercase tracking-wide" style={{ color: "var(--c4-muted)" }}>TV \ Source</th>
                {state.sources.map((s) => (
                  <th key={s.id} className="p-2 text-[11px] font-semibold text-center" style={{ color: "var(--c4-muted)" }}>
                    ATV{s.input}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {state.displays.map((d) => (
                <tr key={d.id}>
                  <td className="p-2 text-xs font-medium whitespace-nowrap">{d.name}</td>
                  {state.sources.map((s) => {
                    const active = d.source === s.id;
                    return (
                      <td key={s.id} className="p-1.5">
                        <button
                          data-testid={`matrix-${d.id}-${s.id}`}
                          onClick={() => route(d.id, s.id)}
                          className="w-full aspect-square rounded-lg flex items-center justify-center active:scale-90 transition"
                          style={{
                            background: active ? "var(--c4-primary)" : "rgba(255,255,255,0.05)",
                            border: `1px solid ${active ? "var(--c4-primary)" : "var(--c4-border)"}`,
                            boxShadow: active ? "0 0 14px rgba(59,130,246,0.5)" : "none",
                          }}
                        >
                          {active && <Check className="w-4 h-4 text-white" />}
                        </button>
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="text-[11px] mt-2" style={{ color: "var(--c4-muted)" }}>Tap a cell to route an Apple TV to a display. Highlighted = active route.</p>
      </div>

      {/* Display cards */}
      <div>
        <h2 className="font-head font-bold text-lg mb-3">Displays</h2>
        <div className="grid sm:grid-cols-2 gap-3">
          {state.displays.map((d) => {
            const src = state.sources.find((s) => s.id === d.source);
            return (
              <motion.div key={d.id} layout className="glass rounded-2xl p-4" data-testid={`display-card-${d.id}`}>
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-2.5">
                    <div className="w-9 h-9 rounded-xl flex items-center justify-center" style={{ background: d.power ? "rgba(59,130,246,0.15)" : "rgba(255,255,255,0.05)" }}>
                      <Tv className="w-4.5 h-4.5" style={{ color: d.power ? "var(--c4-primary)" : "var(--c4-muted)" }} />
                    </div>
                    <div>
                      <p className="font-semibold text-sm">{d.name}</p>
                      <p className="text-[11px]" style={{ color: "var(--c4-muted)" }}>{d.power ? src?.name : "Powered off"}</p>
                    </div>
                  </div>
                  <button
                    data-testid={`power-${d.id}`}
                    onClick={() => togglePower(d)}
                    className="w-9 h-9 rounded-xl flex items-center justify-center active:scale-95 transition"
                    style={{ background: d.power ? "rgba(16,185,129,0.15)" : "rgba(255,255,255,0.05)" }}
                  >
                    <Power className="w-4 h-4" style={{ color: d.power ? "var(--c4-emerald)" : "var(--c4-muted)" }} />
                  </button>
                </div>

                <div className="grid grid-cols-4 gap-1.5 mb-3">
                  {state.sources.map((s) => (
                    <button
                      key={s.id}
                      data-testid={`display-source-${d.id}-${s.id}`}
                      onClick={() => route(d.id, s.id)}
                      className="rounded-lg py-2 text-[11px] font-semibold transition active:scale-95"
                      style={{
                        background: d.source === s.id ? "var(--c4-primary)" : "rgba(255,255,255,0.05)",
                        color: d.source === s.id ? "#fff" : "var(--c4-muted)",
                      }}
                    >
                      ATV{s.input}
                    </button>
                  ))}
                </div>

                <div className="grid grid-cols-2 gap-1.5">
                  <button
                    data-testid={`open-remote-${d.id}`}
                    onClick={() => setRemoteSource(src)}
                    className="rounded-xl py-2.5 flex items-center justify-center gap-2 text-xs font-semibold active:scale-95 transition glass-elevated"
                  >
                    <Gamepad2 className="w-4 h-4" style={{ color: "var(--c4-cyan)" }} /> {src?.name}
                  </button>
                  <button
                    data-testid={`open-sony-remote-${d.id}`}
                    onClick={() => setSonyDisplay(d)}
                    className="rounded-xl py-2.5 flex items-center justify-center gap-2 text-xs font-semibold active:scale-95 transition glass-elevated"
                  >
                    <Tv2 className="w-4 h-4" style={{ color: "var(--c4-primary)" }} /> TV Remote
                  </button>
                </div>

                <div className="grid grid-cols-3 gap-1.5 mt-2">
                  <button data-testid={`tv-voldown-${d.id}`} onClick={() => tvVol(d, "KEY_VOLDOWN")} className="glass-elevated rounded-xl py-2 flex items-center justify-center gap-1 text-[11px] font-semibold active:scale-95 transition">
                    <Volume1 className="w-3.5 h-3.5" /> TV Vol−
                  </button>
                  <button data-testid={`tv-mute-${d.id}`} onClick={() => tvVol(d, "KEY_MUTE")} className="glass-elevated rounded-xl py-2 flex items-center justify-center gap-1 text-[11px] font-semibold active:scale-95 transition">
                    <VolumeX className="w-3.5 h-3.5" /> Mute
                  </button>
                  <button data-testid={`tv-volup-${d.id}`} onClick={() => tvVol(d, "KEY_VOLUP")} className="glass-elevated rounded-xl py-2 flex items-center justify-center gap-1 text-[11px] font-semibold active:scale-95 transition">
                    <Volume2 className="w-3.5 h-3.5" /> TV Vol+
                  </button>
                </div>

                <div className="mt-2 flex items-center gap-2.5 px-1">
                  <span className="text-[9px] font-bold uppercase tracking-wider shrink-0" style={{ color: "var(--c4-muted)" }}>TV Vol</span>
                  <input
                    type="range" min="0" max="100"
                    defaultValue={d.tv_volume ?? 30}
                    data-testid={`tv-abs-vol-${d.id}`}
                    onMouseUp={(e) => setTvVolume(d, Number(e.target.value))}
                    onTouchEnd={(e) => setTvVolume(d, Number(e.target.value))}
                    className="flex-1 h-1.5 rounded-full appearance-none cursor-pointer"
                    style={{ accentColor: "var(--c4-cyan)", background: "var(--c4-border)" }}
                  />
                </div>
              </motion.div>
            );
          })}
        </div>
      </div>

      <AppleTVRemote open={!!remoteSource} source={remoteSource} onClose={() => setRemoteSource(null)} />
      <SonyRemote display={sonyDisplay} onClose={() => setSonyDisplay(null)} />
    </div>
  );
};

export default WatchTab;
