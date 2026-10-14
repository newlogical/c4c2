import React, { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { X, ChevronRight, ChevronLeft, Wifi, Loader2, Cable, Radio, Thermometer, Camera, MonitorSpeaker, Sparkles, CheckCircle2 } from "lucide-react";
import { useSystem } from "@/context/SystemContext";
import { toast } from "sonner";

const STEPS = [
  { key: "welcome" },
  { key: "matrix", title: "HDMI Matrix", sub: "JTECH-MXT40 video routing", icon: Cable, device: "matrix", fields: [["host", "IP address", "192.168.0.254"], ["port", "Telnet port", "23"]] },
  { key: "amp", title: "WS66i Amplifier", sub: "6-zone audio", icon: Radio, device: "amp", fields: [["host", "IP address", "192.168.0.43"]] },
  { key: "ecobee", title: "Ecobee Thermostat", sub: "Local HomeKit control — pair in Settings", icon: Thermometer, device: "ecobee", fields: [["ip", "Thermostat LAN IP", "192.168.0.222"]] },
  { key: "camera", title: "UniFi Camera", sub: "Live video feed", icon: Camera, device: "camera", fields: [["rtsp_url", "RTSPS link (Protect → G6 PTZ → Settings → Advanced)", "rtsps://192.168.0.166:7441/..."]] },
  { key: "tv", title: "Sony Bravia TVs", sub: "Power, volume & HDMI", icon: MonitorSpeaker, device: "tv", tv: true },
  { key: "done" },
];

const Toggle = ({ on, onChange, testid }) => (
  <button data-testid={testid} onClick={onChange} className="w-11 h-6 rounded-full relative transition shrink-0" style={{ background: on ? "var(--c4-emerald)" : "rgba(255,255,255,0.14)" }}>
    <span className="absolute top-0.5 w-5 h-5 rounded-full bg-white transition-all" style={{ left: on ? "22px" : "2px" }} />
  </button>
);

export const SetupWizard = ({ open, onClose }) => {
  const { state, api, act } = useSystem();
  const [i, setI] = useState(0);
  const [cfg, setCfg] = useState(() => JSON.parse(JSON.stringify(state?.config || {})));
  const [testing, setTesting] = useState(false);
  const [scanning, setScanning] = useState(false);
  const step = STEPS[i];

  useEffect(() => {
    if (open) {
      setI(0);
      setCfg(JSON.parse(JSON.stringify(state?.config || {})));
    }
  }, [open]);

  const c = (d) => cfg[d] || {};
  const setField = (d, k, v) => setCfg((p) => ({ ...p, [d]: { ...p[d], [k]: v } }));
  const setLive = (d, v) => setCfg((p) => ({ ...p, [d]: { ...p[d], live: v } }));
  const setTv = (id, k, v) => setCfg((p) => ({ ...p, tv: { ...p.tv, sets: { ...(p.tv?.sets || {}), [id]: { ...((p.tv?.sets || {})[id] || {}), [k]: v } } } }));
  const setCam = (id, v) => setCfg((p) => ({ ...p, cameras: { ...(p.cameras || {}), [id]: { ...((p.cameras || {})[id] || {}), live: true, rtsp_url: v } } }));

  const persist = async (extra = {}) => { await act(api.updateConfig({ ...cfg, ...extra })); };

  const test = async (d) => {
    setTesting(true);
    try {
      await api.updateConfig(cfg);
      const r = await api.testConnection(d);
      r.ok ? toast.success("Connected") : toast.error(r.detail || "Not reachable");
    } catch (e) {
      toast.error("Not reachable (expected in the cloud demo)");
    } finally { setTesting(false); }
  };

  const next = async () => { if (step.device) await persist(); if (i < STEPS.length - 1) setI(i + 1); };
  const finish = async () => { await persist({ setup_done: true }); toast.success("Setup complete"); onClose(); };

  const scan = async () => {
    setScanning(true);
    try {
      const r = await api.discover(false);
      const d = r.devices || {};
      setCfg((p) => {
        const n = JSON.parse(JSON.stringify(p));
        if (d.matrix) n.matrix = { ...n.matrix, live: true, host: d.matrix.host, port: d.matrix.port };
        if (d.amp) n.amp = { ...n.amp, live: true, host: d.amp.host };
        if (d.camera) n.camera = { ...n.camera, live: true, rtsp_url: d.camera.rtsp_url };
        if (d.tv) {
          const sets = { ...(n.tv?.sets || {}) };
          Object.entries(d.tv).forEach(([k, v]) => { sets[k] = { ...(sets[k] || {}), ...v }; });
          n.tv = { ...n.tv, live: true, sets };
        }
        return n;
      });
      toast.success(r.demo ? "Found devices (demo results)" : "Scan complete — review each step");
    } catch (e) {
      toast.error("Scan failed (only works self-hosted)");
    } finally { setScanning(false); }
  };

  const inputStyle = { background: "var(--c4-surface)", border: "1px solid var(--c4-border)", color: "var(--c4-text)" };
  const progress = ((i) / (STEPS.length - 1)) * 100;

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
          className="fixed inset-0 z-[70] flex items-end sm:items-center justify-center"
          style={{ background: "rgba(5,7,12,0.9)" }}
          data-testid="setup-wizard"
        >
          <motion.div
            initial={{ y: 40, opacity: 0 }} animate={{ y: 0, opacity: 1 }} exit={{ y: 40, opacity: 0 }}
            className="glass-elevated w-full sm:max-w-md sm:rounded-3xl rounded-t-3xl flex flex-col max-h-[92vh]"
          >
            <div className="p-5 pb-3 shrink-0">
              <div className="flex items-center justify-between mb-3">
                <span className="text-[11px] font-bold uppercase tracking-widest" style={{ color: "var(--c4-primary)" }}>Guided Setup</span>
                <button data-testid="wizard-skip" onClick={onClose} className="w-8 h-8 rounded-lg glass flex items-center justify-center"><X className="w-4 h-4" /></button>
              </div>
              <div className="h-1 rounded-full" style={{ background: "var(--c4-border)" }}>
                <div className="h-1 rounded-full transition-all" style={{ width: `${progress}%`, background: "var(--c4-primary)" }} />
              </div>
            </div>

            <div className="px-5 py-2 overflow-y-auto no-scrollbar flex-1">
              {step.key === "welcome" && (
                <div className="py-6 text-center">
                  <div className="w-16 h-16 rounded-2xl glow-ring glass flex items-center justify-center mx-auto mb-4"><Sparkles className="w-7 h-7" style={{ color: "var(--c4-primary)" }} /></div>
                  <h2 className="font-head text-2xl font-extrabold">Let's connect your rack</h2>
                  <p className="text-sm mt-2" style={{ color: "var(--c4-muted)" }}>
                    We'll walk through each device — enter its address and test the connection. You can skip any step and finish later from Settings.
                  </p>
                  <p className="text-[11px] mt-3" style={{ color: "var(--c4-amber)" }}>Note: real devices are only reachable when self-hosted on your LAN.</p>
                  <button data-testid="wizard-scan-btn" onClick={scan} disabled={scanning} className="mt-4 w-full rounded-xl py-2.5 text-sm font-semibold glass flex items-center justify-center gap-2">
                    {scanning ? <Loader2 className="w-4 h-4 animate-spin" /> : <Wifi className="w-4 h-4" style={{ color: "var(--c4-cyan)" }} />} Scan my network
                  </button>
                </div>
              )}

              {step.device && !step.tv && (
                <div className="py-3">
                  <div className="flex items-center gap-3 mb-4">
                    <div className="w-11 h-11 rounded-2xl flex items-center justify-center" style={{ background: "rgba(59,130,246,0.14)" }}><step.icon className="w-5 h-5" style={{ color: "var(--c4-primary)" }} /></div>
                    <div className="flex-1"><h2 className="font-head text-lg font-bold">{step.title}</h2><p className="text-[11px]" style={{ color: "var(--c4-muted)" }}>{step.sub}</p></div>
                    <Toggle on={!!c(step.device).live} onChange={() => setLive(step.device, !c(step.device).live)} testid={`wizard-live-${step.device}`} />
                  </div>
                  {c(step.device).live ? (
                    <div className="space-y-2">
                      {step.fields.map(([k, label, ph]) => (
                        <div key={k}>
                          <label className="text-[11px] font-semibold" style={{ color: "var(--c4-muted)" }}>{label}</label>
                          <input data-testid={`wizard-${step.device}-${k}`} value={c(step.device)[k] ?? ""} placeholder={ph} onChange={(e) => setField(step.device, k, e.target.value)} className="w-full mt-1 rounded-lg px-3 py-2 text-sm outline-none" style={inputStyle} />
                        </div>
                      ))}
                      <button data-testid={`wizard-test-${step.device}`} onClick={() => test(step.device)} className="w-full mt-2 rounded-lg py-2 text-xs font-semibold flex items-center justify-center gap-2 glass">
                        {testing ? <Loader2 className="w-4 h-4 animate-spin" /> : <Wifi className="w-4 h-4" style={{ color: "var(--c4-cyan)" }} />} Test connection
                      </button>
                      {step.device === "camera" && (state?.cameras || []).filter((cm) => cm.id !== "cam_front").map((cm) => (
                        <div key={cm.id} className="pt-1">
                          <label className="text-[11px] font-semibold" style={{ color: "var(--c4-muted)" }}>{cm.name} RTSP URL</label>
                          <input data-testid={`wizard-camera-rtsp-${cm.id}`} value={(cfg.cameras?.[cm.id]?.rtsp_url) ?? ""} placeholder="rtsp://NVR:7447/..." onChange={(e) => setCam(cm.id, e.target.value)} className="w-full mt-1 rounded-lg px-3 py-2 text-sm outline-none" style={inputStyle} />
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="text-xs py-2" style={{ color: "var(--c4-muted)" }}>Leave off to keep this device simulated. Toggle on to enter its connection details.</p>
                  )}
                </div>
              )}

              {step.tv && (
                <div className="py-3">
                  <div className="flex items-center gap-3 mb-4">
                    <div className="w-11 h-11 rounded-2xl flex items-center justify-center" style={{ background: "rgba(59,130,246,0.14)" }}><step.icon className="w-5 h-5" style={{ color: "var(--c4-primary)" }} /></div>
                    <div className="flex-1"><h2 className="font-head text-lg font-bold">{step.title}</h2><p className="text-[11px]" style={{ color: "var(--c4-muted)" }}>{step.sub}</p></div>
                    <Toggle on={!!c("tv").live} onChange={() => setLive("tv", !c("tv").live)} testid="wizard-live-tv" />
                  </div>
                  {c("tv").live ? (
                    <div className="space-y-2">
                      {(state?.displays || []).map((d) => {
                        const s = (c("tv").sets || {})[d.id] || {};
                        return (
                          <div key={d.id} className="rounded-lg p-2.5" style={{ background: "var(--c4-bg)", border: "1px solid var(--c4-border)" }}>
                            <p className="text-[11px] font-semibold mb-1.5">{d.name}</p>
                            <div className="grid grid-cols-2 gap-2">
                              <input data-testid={`wizard-tv-ip-${d.id}`} placeholder="IP" value={s.ip || ""} onChange={(e) => setTv(d.id, "ip", e.target.value)} className="rounded-md px-2 py-1.5 text-xs outline-none" style={inputStyle} />
                              <input data-testid={`wizard-tv-mac-${d.id}`} placeholder="MAC" value={s.mac || ""} onChange={(e) => setTv(d.id, "mac", e.target.value)} className="rounded-md px-2 py-1.5 text-xs outline-none" style={inputStyle} />
                              <input data-testid={`wizard-tv-hdmi-${d.id}`} type="number" placeholder="HDMI #" value={s.hdmi_input ?? 1} onChange={(e) => setTv(d.id, "hdmi_input", Number(e.target.value))} className="rounded-md px-2 py-1.5 text-xs outline-none" style={inputStyle} />
                              <input data-testid={`wizard-tv-psk-${d.id}`} type="password" placeholder="PSK" value={s.psk || ""} onChange={(e) => setTv(d.id, "psk", e.target.value)} className="rounded-md px-2 py-1.5 text-xs outline-none" style={inputStyle} />
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  ) : (
                    <p className="text-xs py-2" style={{ color: "var(--c4-muted)" }}>Toggle on to enter each TV's IP, MAC, HDMI input and Pre-Shared Key.</p>
                  )}
                </div>
              )}

              {step.key === "done" && (
                <div className="py-8 text-center">
                  <div className="w-16 h-16 rounded-2xl flex items-center justify-center mx-auto mb-4" style={{ background: "rgba(16,185,129,0.15)" }}><CheckCircle2 className="w-8 h-8" style={{ color: "var(--c4-emerald)" }} /></div>
                  <h2 className="font-head text-2xl font-extrabold">You're all set</h2>
                  <p className="text-sm mt-2" style={{ color: "var(--c4-muted)" }}>You can revisit any device anytime from Settings. Devices left off stay in demo mode.</p>
                </div>
              )}
            </div>

            <div className="p-4 shrink-0 flex items-center gap-2" style={{ borderTop: "1px solid var(--c4-border)" }}>
              {i > 0 && step.key !== "done" && (
                <button data-testid="wizard-back" onClick={() => setI(i - 1)} className="rounded-xl px-4 py-2.5 text-sm font-semibold glass flex items-center gap-1"><ChevronLeft className="w-4 h-4" /> Back</button>
              )}
              <div className="flex-1" />
              {step.key === "done" ? (
                <button data-testid="wizard-finish" onClick={finish} className="rounded-xl px-6 py-2.5 text-sm font-bold" style={{ background: "var(--c4-primary)", color: "#fff" }}>Finish</button>
              ) : (
                <button data-testid="wizard-next" onClick={next} className="rounded-xl px-6 py-2.5 text-sm font-bold flex items-center gap-1" style={{ background: "var(--c4-primary)", color: "#fff" }}>
                  {step.key === "welcome" ? "Start" : "Next"} <ChevronRight className="w-4 h-4" />
                </button>
              )}
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
};

export default SetupWizard;
