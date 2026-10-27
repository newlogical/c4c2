import React, { useState } from "react";
import { motion } from "framer-motion";
import { ShieldCheck, Loader2 } from "lucide-react";
import { QRCodeSVG } from "qrcode.react";
import { api } from "@/lib/api";

export const apiError = (e) => {
  const d = e?.response?.data?.detail;
  if (typeof d === "string") return d;
  if (Array.isArray(d)) return d.map((x) => x?.msg || "").filter(Boolean).join(" ") || "Check the fields and try again.";
  return e?.message || "Something went wrong. Please try again.";
};

const inputCls = "w-full rounded-xl px-4 py-3 text-base outline-none";
const inputStyle = { background: "var(--c4-surface)", border: "1px solid var(--c4-border)", color: "var(--c4-text)" };

const Enroll = ({ uri, secret }) => (
  <div className="space-y-3" data-testid="remote-enroll">
    <p className="text-sm" style={{ color: "var(--c4-muted)" }}>
      First time from outside: open an authenticator app (Google Authenticator, Microsoft Authenticator or iPhone Passwords), add an account, and scan this code.
    </p>
    <div className="bg-white p-3 rounded-xl w-fit mx-auto" data-testid="remote-enroll-qr"><QRCodeSVG value={uri} size={168} /></div>
    <p className="text-[11px] text-center font-mono break-all" style={{ color: "var(--c4-muted)" }} data-testid="remote-enroll-secret">
      Can't scan? Enter this key: {secret}
    </p>
    <a href={uri} className="block text-center text-xs underline" style={{ color: "var(--c4-cyan)" }} data-testid="remote-enroll-link">Open in authenticator app on this device</a>
  </div>
);

// Shown instead of the PIN screen when connecting from outside the apartment and not signed in yet.
export const RemoteLogin = ({ onSignedIn, propertyName }) => {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [code, setCode] = useState("");
  const [step, setStep] = useState("password");
  const [enroll, setEnroll] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const r = await api.remoteLogin({ username, password, code: step === "password" ? undefined : code });
      if (r.step === "done") return onSignedIn();
      if (r.step === "enroll") setEnroll({ uri: r.otpauth_uri, secret: r.secret });
      setStep(r.step);
      setCode("");
    } catch (err) {
      setError(apiError(err));
      if (err?.response?.status === 401 && step !== "password" && /password/i.test(apiError(err))) setStep("password");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="c4-shell min-h-screen flex items-center justify-center px-6 safe-top safe-bottom" data-testid="remote-login-screen">
      <motion.form onSubmit={submit} initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }}
        className="glass-elevated rounded-3xl p-6 w-full max-w-sm space-y-4" data-testid="remote-login-form">
        <div className="flex items-center gap-3">
          <ShieldCheck className="w-7 h-7" style={{ color: "var(--c4-emerald)" }} />
          <div>
            <p className="font-head font-bold text-lg">{propertyName || "Smith Apartment"}</p>
            <p className="text-xs" style={{ color: "var(--c4-muted)" }}>Secure sign-in for access away from home</p>
          </div>
        </div>
        {step === "password" ? (
          <>
            <input className={inputCls} style={inputStyle} placeholder="Username" autoCapitalize="none" autoComplete="username"
              value={username} onChange={(e) => setUsername(e.target.value)} data-testid="remote-username-input" required />
            <input className={inputCls} style={inputStyle} placeholder="Password" type="password" autoComplete="current-password"
              value={password} onChange={(e) => setPassword(e.target.value)} data-testid="remote-password-input" required />
          </>
        ) : (
          <>
            {step === "enroll" && enroll && <Enroll uri={enroll.uri} secret={enroll.secret} />}
            {step === "code" && <p className="text-sm" style={{ color: "var(--c4-muted)" }}>Enter the 6-digit code from your authenticator app.</p>}
            <input className={`${inputCls} text-center tracking-[0.5em] font-mono`} style={inputStyle} placeholder="000000"
              inputMode="numeric" autoComplete="one-time-code" maxLength={6} value={code}
              onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))} data-testid="remote-code-input" required autoFocus />
          </>
        )}
        {error && <p className="text-sm" style={{ color: "#F87171" }} data-testid="remote-login-error">{error}</p>}
        <button type="submit" disabled={busy} data-testid="remote-login-submit"
          className="w-full rounded-xl py-3 font-semibold flex items-center justify-center gap-2 active:scale-[0.98] transition-transform disabled:opacity-60"
          style={{ background: "var(--c4-amber)", color: "#0A0D14" }}>
          {busy && <Loader2 className="w-4 h-4 animate-spin" />}{step === "password" ? "Continue" : "Verify"}
        </button>
        {step !== "password" && (
          <button type="button" onClick={() => { setStep("password"); setError(""); }} className="w-full text-xs" style={{ color: "var(--c4-muted)" }} data-testid="remote-login-back">
            Use a different account
          </button>
        )}
      </motion.form>
    </div>
  );
};
