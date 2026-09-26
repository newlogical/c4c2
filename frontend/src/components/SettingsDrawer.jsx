import React, { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { X, Cable, Radio, Thermometer, Camera, Tv, Wifi, Loader2, MonitorSpeaker } from "lucide-react";
import { useSystem } from "@/context/SystemContext";
import { toast } from "sonner";

const Toggle = ({ on, onChange, testid }) => (
  <button
    data-testid={testid}
    onClick={onChange}
    className="w-11 h-6 rounded-full relative transition shrink-0"
    style={{ background: on ? "var(--c4-emerald)" : "rgba(255,255,255,0.12)" }}
  >
    <span className="absolute top-0.5 w-5 h-5 rounded-full bg-white transition-all" style={{ left: on ? "22px" : "2px" }} />
  </button>
);

const Field = ({ label, value, onChange, placeholder, type = "text", testid }) => (
  <div className="mt-2">
    <label className="text-[11px] font-semibold" style={{ color: "var(--c4-muted)" }}>{label}</label>
    <input
      type={type} value={value ?? ""} placeholder={placeholder}
      data-testid={testid}
      onChange={(e) => onChange(e.target.value)}
      className="w-full mt-1 rounded-lg px-3 py-2 text-sm outline-none"
      style={{ background: "var(--c4-bg)", border: "1px solid var(--c4-border)", color: "var(--c4-text)" }}
    />
  </div>
);

const DeviceCard = ({ icon: Icon, title, subtitle, device, conn, onField, onToggle, onTest, testing, children }) => (
  <div className="glass rounded-2xl p-4" data-testid={`settings-${device}`}>
    <div className="flex items-center justify-between">
      <div className="flex items-center gap-2.5">
        <div className="w-9 h-9 rounded-xl flex items-center justify-center" style={{ background: conn.live ? "rgba(16,185,129,0.15)" : "rgba(255,255,255,0.05)" }}>
          <Icon className="w-4.5 h-4.5" style={{ color: conn.live ? "var(--c4-emerald)" : "var(--c4-muted)" }} />
        </div>
        <div>
          <p className="font-semibold text-sm">{title}</p>
          <p className="text-[11px]" style={{ color: "var(--c4-muted)" }}>{subtitle}</p>
        </div>
      </div>
      <div className="flex items-center gap-2">
        <span className="text-[10px] font-semibold" style={{ color: conn.live ? "var(--c4-emerald)" : "var(--c4-muted)" }}>
          {conn.live ? "LIVE" : "DEMO"}
        </span>
        <Toggle on={!!conn.live} onChange={() => onToggle(device)} testid={`settings-live-${device}`} />
      </div>
    </div>
    {conn.live && (
      <div className="mt-2">
        {children}
        {onTest && (
          <button
            data-testid={`settings-test-${device}`}
            onClick={() => onTest(device)}
            className="mt-3 w-full rounded-lg py-2 text-xs font-semibold flex items-center justify-center gap-2 active:scale-95 transition glass-elevated"
          >
            {testing === device ? <Loader2 className="w-4 h-4 animate-spin" /> : <Wifi className="w-4 h-4" style={{ color: "var(--c4-cyan)" }} />}
            Test connection
          </button>
        )}
      </div>
    )}
  </div>
);

export const SettingsDrawer = ({ open, onClose }) => {
  const { state, act, api } = useSystem();
  const [config, setConfig] = useState({});
  const [testing, setTesting] = useState(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (open && state?.config) setConfig(JSON.parse(JSON.stringify(state.config)));
  }, [open, state]);

  const setField = (device, field, val) =>
    setConfig((p) => ({ ...p, [device]: { ...p[device], [field]: val } }));
  const setTvField = (displayId, field, val) =>
    setConfig((p) => ({
      ...p,
      tv: { ...p.tv, sets: { ...(p.tv?.sets || {}), [displayId]: { ...((p.tv?.sets || {})[displayId] || {}), [field]: val } } },
    }));
  const toggle = (device) =>
    setConfig((p) => ({ ...p, [device]: { ...p[device], live: !p[device]?.live } }));

  const save = async () => {
    setSaving(true);
    await act(api.updateConfig(config));
    setSaving(false);
    toast.success("Device settings saved");
    onClose();
  };

  const test = async (device) => {
    setTesting(device);
    await act(api.updateConfig(config)); // persist before test
    const res = await api.testConnection(device);
    setTesting(null);
    toast[res.ok ? "success" : "error"](`${device}: ${res.ok ? "reachable" : "failed"}`, { description: res.detail });
  };

  const c = (d) => config[d] || {};

  return (
    <AnimatePresence>
      {open && (
        <>
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} onClick={onClose}
            className="fixed inset-0 z-40" style={{ background: "rgba(10,13,20,0.85)" }} />
          <motion.div
            initial={{ x: "100%" }} animate={{ x: 0 }} exit={{ x: "100%" }}
            transition={{ type: "spring", damping: 30, stiffness: 300 }}
            className="fixed top-0 right-0 bottom-0 z-50 w-full max-w-md flex flex-col"
            style={{ background: "var(--c4-surface)", borderLeft: "1px solid var(--c4-border)" }}
            data-testid="settings-drawer"
          >
            <div className="flex items-center justify-between px-5 py-4" style={{ borderBottom: "1px solid var(--c4-border)" }}>
              <span className="font-head font-bold">Device Settings</span>
              <button data-testid="close-settings-btn" onClick={onClose} className="w-8 h-8 rounded-lg glass flex items-center justify-center"><X className="w-4 h-4" /></button>
            </div>
            <p className="px-5 pt-3 text-xs" style={{ color: "var(--c4-muted)" }}>
              Toggle a device to <b style={{ color: "var(--c4-emerald)" }}>LIVE</b> and enter its LAN address to control real hardware when self-hosted. Left in DEMO, the app simulates responses.
            </p>

            <div className="flex-1 overflow-y-auto no-scrollbar px-5 py-3 space-y-3">
              <DeviceCard icon={Cable} title="JTECH-MXT40 Matrix" subtitle="HDMI video routing" device="matrix" conn={c("matrix")} onToggle={toggle} onTest={test} testing={testing}>
                <Field label="Host / IP" value={c("matrix").host} placeholder="192.168.1.1" onChange={(v) => setField("matrix", "host", v)} testid="matrix-host-input" />
                <Field label="Telnet Port" value={c("matrix").port} placeholder="23" type="number" onChange={(v) => setField("matrix", "port", Number(v))} testid="matrix-port-input" />
              </DeviceCard>

              <DeviceCard icon={Radio} title="WS66i Amplifier" subtitle="6-zone audio" device="amp" conn={c("amp")} onToggle={toggle} onTest={test} testing={testing}>
                <Field label="Host / IP" value={c("amp").host} placeholder="192.168.1.50" onChange={(v) => setField("amp", "host", v)} testid="amp-host-input" />
              </DeviceCard>

              <DeviceCard icon={Thermometer} title="Ecobee Thermostat" subtitle="Climate control" device="ecobee" conn={c("ecobee")} onToggle={toggle} onTest={test} testing={testing}>
                <Field label="API Access Token" value={c("ecobee").token} placeholder="Bearer token" onChange={(v) => setField("ecobee", "token", v)} testid="ecobee-token-input" />
                <Field label="Thermostat ID" value={c("ecobee").thermostat_id} placeholder="optional" onChange={(v) => setField("ecobee", "thermostat_id", v)} testid="ecobee-id-input" />
              </DeviceCard>

              <DeviceCard icon={Camera} title="UniFi Protect Camera" subtitle="Live RTSP → HLS stream" device="camera" conn={c("camera")} onToggle={toggle} onTest={test} testing={testing}>
                <Field label="RTSP URL" value={c("camera").rtsp_url} placeholder="rtsp://NVR_IP:7447/GUID_0" onChange={(v) => setField("camera", "rtsp_url", v)} testid="camera-rtsp-input" />
              </DeviceCard>

              <DeviceCard icon={Tv} title="Apple TVs" subtitle="pyatv remote control" device="appletv" conn={c("appletv")} onToggle={toggle}>
                <p className="text-[11px]" style={{ color: "var(--c4-muted)" }}>
                  Apple TV device IDs & pairing credentials are provisioned on the host via <code>atvremote</code>. Enable LIVE to route remote commands through pyatv.
                </p>
              </DeviceCard>

              <div className="glass rounded-2xl p-4" data-testid="settings-tv">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2.5">
                    <div className="w-9 h-9 rounded-xl flex items-center justify-center" style={{ background: c("tv").live ? "rgba(16,185,129,0.15)" : "rgba(255,255,255,0.05)" }}>
                      <MonitorSpeaker className="w-4.5 h-4.5" style={{ color: c("tv").live ? "var(--c4-emerald)" : "var(--c4-muted)" }} />
                    </div>
                    <div>
                      <p className="font-semibold text-sm">Samsung TVs</p>
                      <p className="text-[11px]" style={{ color: "var(--c4-muted)" }}>Power (Wake-on-LAN) + volume</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-[10px] font-semibold" style={{ color: c("tv").live ? "var(--c4-emerald)" : "var(--c4-muted)" }}>{c("tv").live ? "LIVE" : "DEMO"}</span>
                    <Toggle on={!!c("tv").live} onChange={() => toggle("tv")} testid="settings-live-tv" />
                  </div>
                </div>
                {c("tv").live && (
                  <div className="mt-3 space-y-3">
                    {(state?.displays || []).map((d) => {
                      const set = (c("tv").sets || {})[d.id] || {};
                      const inp = "rounded-lg px-2.5 py-2 text-xs outline-none";
                      const inpStyle = { background: "var(--c4-surface)", border: "1px solid var(--c4-border)", color: "var(--c4-text)" };
                      return (
                        <div key={d.id} className="rounded-xl p-3" style={{ background: "var(--c4-bg)", border: "1px solid var(--c4-border)" }} data-testid={`settings-tv-${d.id}`}>
                          <p className="text-xs font-semibold mb-2">{d.name}</p>
                          <div className="grid grid-cols-2 gap-2">
                            <input placeholder="IP e.g. 192.168.1.60" value={set.ip || ""} data-testid={`tv-ip-${d.id}`} onChange={(e) => setTvField(d.id, "ip", e.target.value)} className={inp} style={inpStyle} />
                            <input placeholder="MAC AA:BB:CC:.." value={set.mac || ""} data-testid={`tv-mac-${d.id}`} onChange={(e) => setTvField(d.id, "mac", e.target.value)} className={inp} style={inpStyle} />
                            <input placeholder="HDMI input #" type="number" value={set.hdmi_input ?? 1} data-testid={`tv-hdmi-${d.id}`} onChange={(e) => setTvField(d.id, "hdmi_input", Number(e.target.value))} className={inp} style={inpStyle} />
                            <input placeholder="Token (optional)" value={set.token || ""} data-testid={`tv-token-${d.id}`} onChange={(e) => setTvField(d.id, "token", e.target.value)} className={inp} style={inpStyle} />
                          </div>
                        </div>
                      );
                    })}
                    <button data-testid="settings-test-tv" onClick={() => test("tv")} className="w-full rounded-lg py-2 text-xs font-semibold flex items-center justify-center gap-2 active:scale-95 transition glass-elevated">
                      {testing === "tv" ? <Loader2 className="w-4 h-4 animate-spin" /> : <Wifi className="w-4 h-4" style={{ color: "var(--c4-cyan)" }} />} Test connection
                    </button>
                    <p className="text-[11px]" style={{ color: "var(--c4-muted)" }}>
                      Each TV stays on its wired HDMI input; power-on uses Wake-on-LAN (needs the MAC and "Network standby" enabled on the TV).
                    </p>
                  </div>
                )}
              </div>
            </div>

            <div className="px-5 py-4" style={{ borderTop: "1px solid var(--c4-border)" }}>
              <button
                data-testid="save-settings-btn"
                onClick={save}
                className="w-full rounded-xl py-3 text-sm font-bold active:scale-95 transition"
                style={{ background: "var(--c4-primary)", color: "#fff" }}
              >
                {saving ? "Saving…" : "Save settings"}
              </button>
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
};

export default SettingsDrawer;
