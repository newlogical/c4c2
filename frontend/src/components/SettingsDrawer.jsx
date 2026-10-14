import React, { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Activity, X, Cable, Radio, Thermometer, Camera, Tv, Wifi, Loader2, MonitorSpeaker, BookOpen, Globe, KeyRound, Sparkles, Moon, Mic, Printer, ExternalLink } from "lucide-react";
import { BACKEND } from "@/lib/api";
import { useSystem } from "@/context/SystemContext";
import { toast } from "sonner";
import { AtvPair } from "@/components/AtvPair";

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

const HomeKitPair = ({ conn, onBeforePair }) => {
  const { act, api } = useSystem();
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);
  const run = async (fn, ok) => {
    setBusy(true);
    try {
      await act(fn());
      toast.success(ok);
      setCode("");
    } catch (e) {
      toast.error(e?.response?.data?.detail || "HomeKit request failed");
    } finally {
      setBusy(false);
    }
  };
  if (conn.paired) {
    return (
      <div className="mt-3 flex items-center justify-between rounded-lg px-3 py-2" style={{ background: "rgba(16,185,129,0.1)" }} data-testid="homekit-paired">
        <span className="text-xs font-semibold" style={{ color: "var(--c4-emerald)" }}>Paired via HomeKit (local)</span>
        <button data-testid="homekit-unpair-btn" disabled={busy} onClick={() => run(api.homekitUnpair, "Thermostat unpaired")} className="text-[11px] font-semibold underline" style={{ color: "var(--c4-muted)" }}>Unpair</button>
      </div>
    );
  }
  return (
    <div className="mt-3">
      <Field label="HomeKit setup code (on thermostat: Menu → Settings → HomeKit)" value={code} placeholder="123-45-678" onChange={setCode} testid="homekit-code-input" />
      <button
        data-testid="homekit-pair-btn" disabled={busy || code.replace(/\D/g, "").length !== 8}
        onClick={() => run(async () => { await onBeforePair(); return api.homekitPair(code); }, "Thermostat paired")}
        className="mt-2 w-full rounded-lg py-2 text-xs font-semibold flex items-center justify-center gap-2 active:scale-95 transition disabled:opacity-40"
        style={{ background: "var(--c4-emerald)", color: "#04120c" }}
      >
        {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <KeyRound className="w-4 h-4" />} Pair thermostat
      </button>
    </div>
  );
};

export const SettingsDrawer = ({ open, onClose, onRunWizard, onOpenHealth, saverOn, onToggleSaver, saverMode, onChangeSaverMode }) => {
  const { state, act, api } = useSystem();
  const [config, setConfig] = useState({});
  const [testing, setTesting] = useState(null);
  const [saving, setSaving] = useState(false);
  const [pinCur, setPinCur] = useState("");
  const [pinNew, setPinNew] = useState("");
  const [pinConf, setPinConf] = useState("");
  const [pinBusy, setPinBusy] = useState(false);
  const [voiceScenes, setVoiceScenes] = useState([]);
  const [phrases, setPhrases] = useState({});

  useEffect(() => {
    if (open) {
      api.getScenes().then(setVoiceScenes).catch(() => {});
      api.getVoicePhrases().then((p) => setPhrases(p || {})).catch(() => {});
    }
  }, [open]);
  const setPhrase = (id, v) => setPhrases((p) => ({ ...p, [id]: v }));
  const savePhrases = () => api.setVoicePhrases(phrases).catch(() => {});

  const changePin = async () => {
    if (!/^\d{4}$/.test(pinNew)) return toast.error("New PIN must be 4 digits");
    if (pinNew !== pinConf) return toast.error("New PINs do not match");
    setPinBusy(true);
    try {
      await api.changePin(pinCur, pinNew);
      toast.success("PIN updated");
      setPinCur(""); setPinNew(""); setPinConf("");
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Could not change PIN");
    } finally {
      setPinBusy(false);
    }
  };

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
  const setAmpInput = (sourceId, val) =>
    setConfig((p) => ({ ...p, amp: { ...p.amp, input_map: { ...(p.amp?.input_map || {}), [sourceId]: val } } }));
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

            <details className="mx-5 mt-3 rounded-xl glass" data-testid="commissioning-guide">
              <summary className="px-4 py-3 text-xs font-semibold cursor-pointer flex items-center gap-2" style={{ color: "var(--c4-text)" }}>
                <BookOpen className="w-4 h-4" style={{ color: "var(--c4-primary)" }} /> On-site commissioning guide
              </summary>
              <div className="px-4 pb-4 text-[11px] space-y-1.5" style={{ color: "var(--c4-muted)" }}>
                <p>1. Self-host on a Pi/mini-PC on the apartment LAN (full steps in <code>SELF_HOST.md</code>).</p>
                <p>2. <b>Matrix</b>: enable Telnet, enter its IP (port 23).</p>
                <p>3. <b>WS66i</b>: set the rear switch to ETHERNET, enter IP, map each source to its wired input.</p>
                <p>4. <b>Ecobee</b>: enter the HomeKit setup code from the thermostat (Menu → Settings → HomeKit) and tap Pair.</p>
                <p>5. <b>UniFi</b>: paste the camera's RTSP URL.</p>
                <p>6. <b>Apple TVs</b>: IPs are pre-mapped; pair each with <code>atvremote</code> (companion + airplay) and paste the credentials.</p>
                <p>7. <b>Sony Bravia TVs</b>: enter IP + MAC + PSK + HDMI input. On each TV set a Pre-Shared Key (Network → IP control) and enable "Remote start" for Wake-on-LAN.</p>
                <p className="pt-1">Flip each device to LIVE → Test connection → Save.</p>
              </div>
            </details>

            <details className="mx-5 mt-2 rounded-xl glass" data-testid="remote-access-guide">
              <summary className="px-4 py-3 text-xs font-semibold cursor-pointer flex items-center gap-2" style={{ color: "var(--c4-text)" }}>
                <Globe className="w-4 h-4" style={{ color: "var(--c4-cyan)" }} /> Remote access (outside the apartment)
              </summary>
              <div className="px-4 pb-4 text-[11px] space-y-1.5" style={{ color: "var(--c4-muted)" }}>
                <p><b>Recommended — Tailscale (free):</b> install Tailscale on the host and on your phone/tablet; both join your private tailnet. Then open the app at <code>http://&lt;host-tailscale-ip&gt;:3000</code> from anywhere — no ports opened.</p>
                <p>1. On the host: <code>curl -fsSL https://tailscale.com/install.sh | sh</code> then <code>tailscale up</code>.</p>
                <p>2. Install the Tailscale app on your phone, sign in with the same account.</p>
                <p>3. Use the host's <code>100.x.y.z</code> address in the browser.</p>
                <p><b>Alternative:</b> WireGuard on the UniFi Dream Machine (Settings → VPN). Connect the VPN, then use the host's LAN IP.</p>
                <p style={{ color: "var(--c4-rose)" }}>Do NOT port-forward 3000/8001 to the internet — always tunnel via VPN.</p>
              </div>
            </details>

            <div className="flex-1 overflow-y-auto no-scrollbar px-5 py-3 space-y-3">
              <button
                data-testid="settings-health-card"
                onClick={onOpenHealth}
                className="w-full glass rounded-2xl p-4 flex items-center gap-3 active:scale-[0.99] transition text-left"
              >
                <div className="w-9 h-9 rounded-xl flex items-center justify-center" style={{ background: "rgba(16,185,129,0.15)" }}>
                  <Activity className="w-4.5 h-4.5" style={{ color: "var(--c4-emerald)" }} />
                </div>
                <div className="flex-1">
                  <p className="font-semibold text-sm">Device health</p>
                  <p className="text-[11px]" style={{ color: "var(--c4-muted)" }}>Every mapped device with IP and online status</p>
                </div>
              </button>
              <a
                data-testid="setup-guide-link"
                href="/setup-guide.html"
                target="_blank"
                rel="noopener noreferrer"
                className="w-full glass rounded-2xl p-4 flex items-center gap-3 active:scale-[0.99] transition"
              >
                <div className="w-9 h-9 rounded-xl flex items-center justify-center" style={{ background: "rgba(6,182,212,0.15)" }}>
                  <Printer className="w-4.5 h-4.5" style={{ color: "var(--c4-cyan)" }} />
                </div>
                <div className="text-left flex-1">
                  <p className="font-semibold text-sm">Setup &amp; install guide</p>
                  <p className="text-[11px]" style={{ color: "var(--c4-muted)" }}>Full printable step-by-step walkthrough</p>
                </div>
                <ExternalLink className="w-4 h-4" style={{ color: "var(--c4-cyan)" }} />
              </a>

              <button
                data-testid="run-wizard-btn"
                onClick={onRunWizard}
                className="w-full glass rounded-2xl p-4 flex items-center gap-3 active:scale-[0.99] transition"
              >
                <div className="w-9 h-9 rounded-xl flex items-center justify-center" style={{ background: "rgba(99,102,241,0.15)" }}>
                  <Sparkles className="w-4.5 h-4.5" style={{ color: "var(--c4-indigo)" }} />
                </div>
                <div className="text-left flex-1">
                  <p className="font-semibold text-sm">Guided setup wizard</p>
                  <p className="text-[11px]" style={{ color: "var(--c4-muted)" }}>Walk through each device & test it</p>
                </div>
                <span className="text-xs font-semibold" style={{ color: "var(--c4-indigo)" }}>Open</span>
              </button>

              <div className="glass rounded-2xl p-4" data-testid="settings-screensaver">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2.5">
                    <div className="w-9 h-9 rounded-xl flex items-center justify-center" style={{ background: saverOn ? "rgba(6,182,212,0.15)" : "rgba(255,255,255,0.05)" }}>
                      <Moon className="w-4.5 h-4.5" style={{ color: saverOn ? "var(--c4-cyan)" : "var(--c4-muted)" }} />
                    </div>
                    <div>
                      <p className="font-semibold text-sm">Screen saver</p>
                      <p className="text-[11px]" style={{ color: "var(--c4-muted)" }}>After 90s idle · tap to wake</p>
                    </div>
                  </div>
                  <button data-testid="screensaver-toggle" onClick={onToggleSaver} className="w-11 h-6 rounded-full relative transition shrink-0" style={{ background: saverOn ? "var(--c4-emerald)" : "rgba(255,255,255,0.14)" }}>
                    <span className="absolute top-0.5 w-5 h-5 rounded-full bg-white transition-all" style={{ left: saverOn ? "22px" : "2px" }} />
                  </button>
                </div>
                {saverOn && (
                  <div className="grid grid-cols-3 gap-2 mt-3">
                    {[["clock", "Clock"], ["photos", "Photos"], ["camera", "Front Door"]].map(([m, label]) => (
                      <button key={m} data-testid={`saver-mode-${m}`} onClick={() => onChangeSaverMode(m)}
                        className="rounded-lg py-2 text-xs font-semibold transition active:scale-95"
                        style={{ background: saverMode === m ? "rgba(6,182,212,0.18)" : "rgba(255,255,255,0.05)", color: saverMode === m ? "var(--c4-cyan)" : "var(--c4-muted)", border: saverMode === m ? "1px solid var(--c4-cyan)" : "1px solid transparent" }}>
                        {label}
                      </button>
                    ))}
                  </div>
                )}
              </div>

              <div className="glass rounded-2xl p-4" data-testid="settings-voice">
                <div className="flex items-center gap-2.5 mb-2">
                  <div className="w-9 h-9 rounded-xl flex items-center justify-center" style={{ background: "rgba(99,102,241,0.15)" }}>
                    <Mic className="w-4.5 h-4.5" style={{ color: "var(--c4-indigo)" }} />
                  </div>
                  <div>
                    <p className="font-semibold text-sm">Voice control</p>
                    <p className="text-[11px]" style={{ color: "var(--c4-muted)" }}>Run scenes with "Hey Siri / Google"</p>
                  </div>
                </div>
                <p className="text-[11px] mb-2" style={{ color: "var(--c4-muted)" }}>
                  Create an iOS Shortcut or Google routine that opens the scene's URL, then say your phrase.
                </p>
                <div className="space-y-2.5">
                  {voiceScenes.map((s) => (
                    <div key={s.id} className="rounded-lg p-2.5" style={{ background: "var(--c4-bg)", border: "1px solid var(--c4-border)" }}>
                      <p className="text-xs font-semibold truncate mb-1.5">{s.name}</p>
                      <input
                        data-testid={`voice-phrase-${s.id}`}
                        value={phrases[s.id] ?? ""}
                        onChange={(e) => setPhrase(s.id, e.target.value)}
                        onBlur={savePhrases}
                        placeholder={`e.g. "Hey Siri, ${s.name}"`}
                        className="w-full rounded-md px-2.5 py-1.5 text-xs outline-none mb-1.5"
                        style={{ background: "var(--c4-surface)", border: "1px solid var(--c4-border)", color: "var(--c4-text)" }}
                      />
                      <div className="flex items-center gap-2">
                        <p className="text-[10px] font-mono truncate flex-1" style={{ color: "var(--c4-muted)" }}>/api/voice/scene/{s.id}</p>
                        <button
                          data-testid={`voice-copy-${s.id}`}
                          onClick={() => {
                            const url = `${BACKEND}/api/voice/scene/${s.id}`;
                            const phrase = phrases[s.id] || s.name;
                            const recipe = `iOS Shortcut / Google routine — run scene "${s.name}"\nPhrase: "${phrase}"\n1. New Shortcut/Routine → trigger phrase: ${phrase}\n2. Action: Get Contents of URL → ${url}\n3. Save. Now say: "Hey Siri, ${phrase}" or "Hey Google, ${phrase}".`;
                            navigator.clipboard?.writeText(recipe);
                            toast.success("Shortcut recipe copied", { description: "Paste into iOS Shortcuts / Google" });
                          }}
                          className="shrink-0 rounded-md px-2.5 py-1.5 text-[11px] font-semibold glass-elevated"
                        >Copy shortcut</button>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              <div className="glass rounded-2xl p-4" data-testid="settings-pin">
                <div className="flex items-center gap-2.5 mb-3">
                  <div className="w-9 h-9 rounded-xl flex items-center justify-center" style={{ background: "rgba(59,130,246,0.15)" }}>
                    <KeyRound className="w-4.5 h-4.5" style={{ color: "var(--c4-primary)" }} />
                  </div>
                  <div>
                    <p className="font-semibold text-sm">Unlock PIN</p>
                    <p className="text-[11px]" style={{ color: "var(--c4-muted)" }}>Change the 4-digit lock code</p>
                  </div>
                </div>
                <div className="grid grid-cols-1 gap-2">
                  <input type="password" inputMode="numeric" maxLength={4} placeholder="Current PIN" value={pinCur} data-testid="pin-current-input" onChange={(e) => setPinCur(e.target.value.replace(/\D/g, ""))} className="rounded-lg px-3 py-2 text-sm outline-none" style={{ background: "var(--c4-surface)", border: "1px solid var(--c4-border)", color: "var(--c4-text)" }} />
                  <div className="grid grid-cols-2 gap-2">
                    <input type="password" inputMode="numeric" maxLength={4} placeholder="New PIN" value={pinNew} data-testid="pin-new-input" onChange={(e) => setPinNew(e.target.value.replace(/\D/g, ""))} className="rounded-lg px-3 py-2 text-sm outline-none" style={{ background: "var(--c4-surface)", border: "1px solid var(--c4-border)", color: "var(--c4-text)" }} />
                    <input type="password" inputMode="numeric" maxLength={4} placeholder="Confirm" value={pinConf} data-testid="pin-confirm-input" onChange={(e) => setPinConf(e.target.value.replace(/\D/g, ""))} className="rounded-lg px-3 py-2 text-sm outline-none" style={{ background: "var(--c4-surface)", border: "1px solid var(--c4-border)", color: "var(--c4-text)" }} />
                  </div>
                  <button data-testid="change-pin-btn" onClick={changePin} disabled={pinBusy} className="rounded-lg py-2 text-xs font-bold active:scale-95 transition flex items-center justify-center gap-2" style={{ background: "var(--c4-primary)", color: "#fff", opacity: pinBusy ? 0.6 : 1 }}>
                    {pinBusy ? <Loader2 className="w-4 h-4 animate-spin" /> : <KeyRound className="w-4 h-4" />} Update PIN
                  </button>
                </div>
              </div>

              <DeviceCard icon={Cable} title="JTECH-MXT40 Matrix" subtitle="HDMI video routing" device="matrix" conn={c("matrix")} onToggle={toggle} onTest={test} testing={testing}>
                <Field label="Host / IP" value={c("matrix").host} placeholder="192.168.0.254" onChange={(v) => setField("matrix", "host", v)} testid="matrix-host-input" />
                <Field label="Telnet Port" value={c("matrix").port} placeholder="23" type="number" onChange={(v) => setField("matrix", "port", Number(v))} testid="matrix-port-input" />
                <Field label="Username" value={c("matrix").username} placeholder="admin" onChange={(v) => setField("matrix", "username", v)} testid="matrix-username-input" />
                <Field label="Password" value={c("matrix").password} placeholder="admin" type="password" onChange={(v) => setField("matrix", "password", v)} testid="matrix-password-input" />
              </DeviceCard>

              <DeviceCard icon={Radio} title="WS66i Amplifier" subtitle="6-zone audio" device="amp" conn={c("amp")} onToggle={toggle} onTest={test} testing={testing}>
                <Field label="Host / IP" value={c("amp").host} placeholder="192.168.0.43" onChange={(v) => setField("amp", "host", v)} testid="amp-host-input" />
                {Object.entries(c("amp").streamers || {}).map(([sid, st]) => (
                  <p key={sid} className="text-[11px] font-mono mt-1.5" style={{ color: "var(--c4-muted)" }} data-testid={`amp-streamer-${sid}`}>
                    Streaming module · {st.name}: {st.ip} · {st.mac}
                  </p>
                ))}
                <div className="mt-3">
                  <p className="text-[11px] font-semibold mb-1.5" style={{ color: "var(--c4-muted)" }}>Source → WS66i physical input (1–6)</p>
                  <div className="grid grid-cols-2 gap-2">
                    {(state?.audio_sources || []).map((s) => (
                      <div key={s.id} className="flex items-center justify-between gap-2 rounded-lg px-2.5 py-1.5" style={{ background: "var(--c4-bg)", border: "1px solid var(--c4-border)" }}>
                        <span className="text-[11px] truncate">{s.name}</span>
                        <input
                          type="number" min="1" max="6"
                          value={(c("amp").input_map || {})[s.id] ?? 1}
                          data-testid={`amp-input-${s.id}`}
                          onChange={(e) => setAmpInput(s.id, Number(e.target.value))}
                          className="w-12 rounded-md px-2 py-1 text-xs outline-none text-center"
                          style={{ background: "var(--c4-surface)", border: "1px solid var(--c4-border)", color: "var(--c4-text)" }}
                        />
                      </div>
                    ))}
                  </div>
                </div>
              </DeviceCard>

              <DeviceCard icon={Thermometer} title="Ecobee Thermostat" subtitle="Local HomeKit control (no cloud)" device="ecobee" conn={c("ecobee")} onToggle={toggle} onTest={test} testing={testing}>
                <Field label="LAN IP (from UniFi)" value={c("ecobee").ip} placeholder="192.168.0.222" onChange={(v) => setField("ecobee", "ip", v)} testid="ecobee-ip-input" />
                <Field label="MAC Address" value={c("ecobee").mac} placeholder="44:61:32:DF:C2:A9" onChange={(v) => setField("ecobee", "mac", v)} testid="ecobee-mac-input" />
                <HomeKitPair conn={c("ecobee")} onBeforePair={() => api.updateConfig(config)} />
              </DeviceCard>

              <DeviceCard icon={Camera} title="UniFi Protect Camera" subtitle="Live RTSP → HLS stream" device="camera" conn={c("camera")} onToggle={toggle} onTest={test} testing={testing}>
                <p className="text-[11px] font-mono" style={{ color: "var(--c4-muted)" }} data-testid="camera-device-info">
                  G6 PTZ · {c("camera").ip} · NVR {c("nvr").ip}
                </p>
                <Field label="RTSPS stream link (from UniFi Protect)" type="password" value={c("camera").rtsp_url} placeholder="rtsps://192.168.0.166:7441/xxxx?enableSrtp" onChange={(v) => setField("camera", "rtsp_url", v)} testid="camera-rtsp-input" />
                <Field label="Protect API key (presets & patrol)" type="password" value={c("camera").protect_api_key} placeholder="Protect → Settings → Control Plane → Integrations" onChange={(v) => setField("camera", "protect_api_key", v)} testid="camera-apikey-input" />
                <Field label="Preset names (slot order, comma-separated)" value={c("camera").ptz_presets} placeholder="Door, Hallway, Wide" onChange={(v) => setField("camera", "ptz_presets", v)} testid="camera-presets-input" />
                <Field label="Local Protect user (experimental arrows/zoom)" value={c("camera").protect_user} placeholder="local-only user" onChange={(v) => setField("camera", "protect_user", v)} testid="camera-protect-user-input" />
                <Field label="Local Protect password" type="password" value={c("camera").protect_password} placeholder="••••" onChange={(v) => setField("camera", "protect_password", v)} testid="camera-protect-pass-input" />
              </DeviceCard>

              <DeviceCard icon={Tv} title="Apple TVs" subtitle="pyatv remote control" device="appletv" conn={c("appletv")} onToggle={toggle}>
                <p className="text-[11px]" style={{ color: "var(--c4-muted)" }}>
                  Turn on LIVE, then tap <b>Pair this Apple TV</b> on each one and type the PIN that appears on its screen (twice: Companion, then AirPlay). Credentials save automatically.
                </p>
                {(state?.sources || []).map((src) => {
                  const dv = (c("appletv").devices || {})[src.id] || {};
                  const setAtv = (k, v) => setConfig((p) => ({ ...p, appletv: { ...p.appletv, devices: { ...(p.appletv?.devices || {}), [src.id]: { ...dv, [k]: v } } } }));
                  return (
                    <div key={src.id} className="mt-3 rounded-xl p-3" style={{ background: "var(--c4-bg)" }} data-testid={`atv-card-${src.id}`}>
                      <p className="text-xs font-semibold">{src.name} <span style={{ color: "var(--c4-muted)" }}>· {src.location}</span></p>
                      <Field label="IP" value={dv.ip} placeholder="192.168.0.x" onChange={(v) => setAtv("ip", v)} testid={`atv-ip-${src.id}`} />
                      <Field label="MAC" value={dv.mac} placeholder="F0:B3:EC:..." onChange={(v) => setAtv("mac", v)} testid={`atv-mac-${src.id}`} />
                      <Field label="Companion credentials" type="password" value={dv.credentials} placeholder="from atvremote pair" onChange={(v) => setAtv("credentials", v)} testid={`atv-cred-${src.id}`} />
                      <Field label="AirPlay credentials" type="password" value={dv.airplay_credentials} placeholder="from atvremote pair" onChange={(v) => setAtv("airplay_credentials", v)} testid={`atv-apcred-${src.id}`} />
                      <AtvPair aid={src.id} dev={dv} />
                    </div>
                  );
                })}
              </DeviceCard>

              <div className="glass rounded-2xl p-4" data-testid="settings-tv">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2.5">
                    <div className="w-9 h-9 rounded-xl flex items-center justify-center" style={{ background: c("tv").live ? "rgba(16,185,129,0.15)" : "rgba(255,255,255,0.05)" }}>
                      <MonitorSpeaker className="w-4.5 h-4.5" style={{ color: c("tv").live ? "var(--c4-emerald)" : "var(--c4-muted)" }} />
                    </div>
                    <div>
                      <p className="font-semibold text-sm">Sony Bravia TVs</p>
                      <p className="text-[11px]" style={{ color: "var(--c4-muted)" }}>Power (Wake-on-LAN) + volume + HDMI</p>
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
                            <input placeholder="IP e.g. 192.168.0.165" value={set.ip || ""} data-testid={`tv-ip-${d.id}`} onChange={(e) => setTvField(d.id, "ip", e.target.value)} className={inp} style={inpStyle} />
                            <input placeholder="MAC AA:BB:CC:.." value={set.mac || ""} data-testid={`tv-mac-${d.id}`} onChange={(e) => setTvField(d.id, "mac", e.target.value)} className={inp} style={inpStyle} />
                            <input placeholder="HDMI input #" type="number" value={set.hdmi_input ?? 1} data-testid={`tv-hdmi-${d.id}`} onChange={(e) => setTvField(d.id, "hdmi_input", Number(e.target.value))} className={inp} style={inpStyle} />
                            <input placeholder="Pre-Shared Key (PSK)" type="password" value={set.psk || ""} data-testid={`tv-psk-${d.id}`} onChange={(e) => setTvField(d.id, "psk", e.target.value)} className={inp} style={inpStyle} />
                          </div>
                        </div>
                      );
                    })}
                    <button data-testid="settings-test-tv" onClick={() => test("tv")} className="w-full rounded-lg py-2 text-xs font-semibold flex items-center justify-center gap-2 active:scale-95 transition glass-elevated">
                      {testing === "tv" ? <Loader2 className="w-4 h-4 animate-spin" /> : <Wifi className="w-4 h-4" style={{ color: "var(--c4-cyan)" }} />} Test connection
                    </button>
                    <p className="text-[11px]" style={{ color: "var(--c4-muted)" }}>
                      Set a Pre-Shared Key on each TV (Settings → Network → Home network → IP control), and enable "Remote start" for Wake-on-LAN. The HDMI input is selected over the Bravia REST API.
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
