import React, { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { Tv, Volume2, Thermometer, Camera, Power, Moon, Clapperboard, Radio, ChevronRight, Shield, Home, Star, Tv2 } from "lucide-react";
import { SonyRemote } from "@/components/SonyRemote";
import { useSystem } from "@/context/SystemContext";
import { toast } from "sonner";

const HERO = "https://images.unsplash.com/photo-1780257563050-0ee78acfeee8?crop=entropy&cs=srgb&fm=jpg&q=85&w=1200";

const sceneIcons = { all_off: Power, good_night: Moon, movie_night: Clapperboard, whole_home_audio: Radio };

const container = { animate: { transition: { staggerChildren: 0.05 } } };
const item = { initial: { opacity: 0, y: 12 }, animate: { opacity: 1, y: 0 } };

export const HomeTab = ({ onNavigate }) => {
  const { state, act, api } = useSystem();
  const [allScenes, setAllScenes] = useState([]);
  const [sonyDisplay, setSonyDisplay] = useState(null);
  const pinKey = (state?.pinned_scenes || []).join(",");
  useEffect(() => { api.getScenes().then(setAllScenes).catch(() => {}); }, [api, pinKey]);
  if (!state) return null;
  const pinnedScenes = (state.pinned_scenes || []).map((id) => allScenes.find((s) => s.id === id)).filter(Boolean);

  const activeTVs = state.displays.filter((d) => d.power).length;
  const activeZones = state.audio_zones.filter((z) => z.power && !z.mute).length;
  const t = state.thermostat;

  const runScene = async (id, name) => {
    await act(api.scene(id));
    toast.success(`Scene: ${name}`);
  };

  const toggleAway = async () => {
    const goingAway = !state.away;
    await act(api.setAway(goingAway));
    toast[goingAway ? "success" : "success"](goingAway ? "Away — everything off, camera armed" : "Welcome home");
  };

  const stats = [
    { icon: Tv, label: "TVs On", value: `${activeTVs}/4`, color: "var(--c4-primary)", tab: "watch" },
    { icon: Volume2, label: "Audio Zones", value: `${activeZones}/4`, color: "var(--c4-amber)", tab: "listen" },
    { icon: Thermometer, label: "Indoor", value: `${t.current_temp}°`, color: "var(--c4-emerald)", tab: "climate" },
    { icon: Camera, label: "Camera", value: state.camera.online ? "Live" : "Off", color: "var(--c4-cyan)", tab: "security" },
  ];

  return (
    <motion.div variants={container} initial="initial" animate="animate" className="p-4 sm:p-6 space-y-5 pb-8" data-testid="home-tab">
      {/* Hero */}
      <motion.div variants={item} className="relative rounded-3xl overflow-hidden h-44 sm:h-56" data-testid="home-hero">
        <img src={HERO} alt="Home" className="w-full h-full object-cover" />
        <div className="absolute inset-0" style={{ background: "linear-gradient(to top, rgba(10,13,20,0.95) 0%, rgba(10,13,20,0.2) 60%, transparent 100%)" }} />
        <div className="absolute bottom-0 left-0 p-5">
          <p className="text-xs font-semibold uppercase tracking-wider" style={{ color: "var(--c4-cyan)" }}>Welcome home</p>
          <h1 className="font-head text-2xl sm:text-3xl font-extrabold tracking-tight mt-1">{state.property_name}</h1>
          <p className="text-sm" style={{ color: "var(--c4-muted)" }}>{state.outdoor_condition || t.outdoor_condition} · {t.outdoor_temp}° outside</p>
        </div>
      </motion.div>

      {/* Pinned presets */}
      {pinnedScenes.length > 0 && (
        <motion.div variants={item} className="grid grid-cols-1 sm:grid-cols-2 gap-3" data-testid="pinned-presets">
          {pinnedScenes.map((sc) => (
            <button
              key={sc.id}
              data-testid={`pinned-${sc.id}`}
              onClick={() => runScene(sc.id, sc.name)}
              className="rounded-3xl p-5 min-h-[96px] text-left flex items-center gap-4 active:scale-[0.98] transition"
              style={{ background: "linear-gradient(135deg, rgba(99,102,241,0.28), rgba(59,130,246,0.14))", border: "1px solid rgba(99,102,241,0.4)" }}
            >
              <div className="w-14 h-14 rounded-2xl flex items-center justify-center shrink-0" style={{ background: "rgba(255,255,255,0.08)" }}>
                <Star className="w-7 h-7" style={{ color: "var(--c4-amber)", fill: "var(--c4-amber)" }} />
              </div>
              <div className="min-w-0">
                <p className="font-head font-bold text-lg leading-tight">{sc.name}</p>
                <p className="text-[11px] mt-1 truncate" style={{ color: "var(--c4-muted)" }}>{sc.desc}</p>
              </div>
            </button>
          ))}
        </motion.div>
      )}

      {/* Stat grid */}
      <div className="grid grid-cols-2 gap-3">
        {stats.map((s) => (
          <motion.button
            key={s.label}
            variants={item}
            data-testid={`stat-${s.tab}`}
            onClick={() => onNavigate(s.tab)}
            className="glass rounded-2xl p-4 text-left active:scale-[0.98] transition hover:border-[var(--c4-border-med)]"
          >
            <div className="flex items-center justify-between mb-3">
              <div className="w-9 h-9 rounded-xl flex items-center justify-center" style={{ background: `${s.color}22` }}>
                <s.icon className="w-4.5 h-4.5" style={{ color: s.color }} />
              </div>
              <ChevronRight className="w-4 h-4" style={{ color: "var(--c4-muted)" }} />
            </div>
            <p className="font-head text-2xl font-bold">{s.value}</p>
            <p className="text-xs" style={{ color: "var(--c4-muted)" }}>{s.label}</p>
          </motion.button>
        ))}
      </div>

      {/* Away / Home */}
      <motion.button
        variants={item}
        data-testid="away-toggle"
        onClick={toggleAway}
        className="w-full glass rounded-2xl p-4 flex items-center justify-between active:scale-[0.99] transition"
        style={{ border: state.away ? "1px solid var(--c4-rose)" : "1px solid var(--c4-border)" }}
      >
        <div className="flex items-center gap-3">
          <div className="w-11 h-11 rounded-2xl flex items-center justify-center" style={{ background: state.away ? "rgba(239,68,68,0.15)" : "rgba(16,185,129,0.12)" }}>
            {state.away ? <Shield className="w-5 h-5" style={{ color: "var(--c4-rose)" }} /> : <Home className="w-5 h-5" style={{ color: "var(--c4-emerald)" }} />}
          </div>
          <div className="text-left">
            <p className="font-head font-bold">{state.away ? "Away · Armed" : "Home"}</p>
            <p className="text-[11px]" style={{ color: "var(--c4-muted)" }}>
              {state.away ? "Everything off · camera armed" : "Tap when leaving: power down & arm camera"}
            </p>
          </div>
        </div>
        <span className="text-xs font-semibold px-3 py-1.5 rounded-lg" style={{ background: state.away ? "rgba(16,185,129,0.15)" : "rgba(239,68,68,0.15)", color: state.away ? "var(--c4-emerald)" : "var(--c4-rose)" }}>
          {state.away ? "I'm home" : "Leaving"}
        </span>
      </motion.button>

      {/* Quick scenes */}
      <motion.div variants={item}>
        <div className="flex items-center justify-between mb-3">
          <h2 className="font-head font-bold text-lg">Quick Scenes</h2>
          <button data-testid="all-scenes-link" onClick={() => onNavigate("scenes")} className="text-xs" style={{ color: "var(--c4-primary)" }}>
            View all
          </button>
        </div>
        <div className="grid grid-cols-2 gap-3">
          {state.scenes.map((sc) => {
            const Icon = sceneIcons[sc.id] || Radio;
            const color = sc.type === "critical" ? "var(--c4-rose)" : sc.type === "vibrant" ? "var(--c4-indigo)" : "var(--c4-primary)";
            return (
              <button
                key={sc.id}
                data-testid={`quick-scene-${sc.id}`}
                onClick={() => runScene(sc.id, sc.name)}
                className="glass rounded-2xl p-4 text-left active:scale-[0.98] transition hover:border-[var(--c4-border-med)]"
              >
                <div className="w-9 h-9 rounded-xl flex items-center justify-center mb-3" style={{ background: `${color}22` }}>
                  <Icon className="w-4.5 h-4.5" style={{ color }} />
                </div>
                <p className="font-semibold text-sm">{sc.name}</p>
                <p className="text-[11px] mt-0.5 leading-snug" style={{ color: "var(--c4-muted)" }}>{sc.desc}</p>
              </button>
            );
          })}
        </div>
      </motion.div>

      {/* Rooms */}
      <motion.div variants={item}>
        <h2 className="font-head font-bold text-lg mb-3">Rooms</h2>
        <div className="space-y-2.5">
          {state.displays.map((d) => {
            const src = state.sources.find((s) => s.id === d.source);
            const zone = state.audio_zones.find((z) => z.paired_tv === d.id);
            return (
              <div key={d.id} data-testid={`room-row-${d.id}`} className="glass rounded-2xl p-4 flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-xl flex items-center justify-center" style={{ background: d.power ? "rgba(59,130,246,0.15)" : "rgba(255,255,255,0.05)" }}>
                    <Tv className="w-5 h-5" style={{ color: d.power ? "var(--c4-primary)" : "var(--c4-muted)" }} />
                  </div>
                  <div>
                    <p className="font-semibold text-sm">{d.name}</p>
                    <p className="text-[11px]" style={{ color: "var(--c4-muted)" }}>
                      {d.power ? `${src?.name || "—"}` : "Off"}{zone ? ` · Audio ${zone.power && !zone.mute ? "on" : "off"}` : ""}
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  <span className="w-2 h-2 rounded-full" style={{ background: d.power ? "var(--c4-emerald)" : "rgba(255,255,255,0.15)" }} />
                  <button data-testid={`room-remote-${d.id}`} onClick={() => setSonyDisplay(d)} aria-label={`${d.name} remote`}
                    className="w-11 h-11 rounded-xl glass-elevated flex items-center justify-center active:scale-90 transition">
                    <Tv2 className="w-5 h-5" style={{ color: "var(--c4-primary)" }} />
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      </motion.div>
      <SonyRemote display={sonyDisplay} onClose={() => setSonyDisplay(null)} />
    </motion.div>
  );
};

export default HomeTab;
