import React, { useCallback, useEffect, useState } from "react";
import { Globe2, Trash2, KeyRound, ShieldOff, LogOut, UserPlus } from "lucide-react";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { apiError } from "@/components/RemoteLogin";

const inp = "rounded-lg px-3 py-2 text-sm outline-none w-full";
const inpStyle = { background: "var(--c4-surface)", border: "1px solid var(--c4-border)", color: "var(--c4-text)" };
const when = (iso) => (iso ? new Date(iso).toLocaleString() : "never");

const IconBtn = ({ icon: Icon, label, onClick, testid }) => (
  <button onClick={onClick} aria-label={label} title={label} data-testid={testid}
    className="w-8 h-8 rounded-lg flex items-center justify-center active:scale-95 transition-transform" style={{ background: "rgba(255,255,255,0.05)" }}>
    <Icon className="w-3.5 h-3.5" />
  </button>
);

const UserRow = ({ u, reload }) => {
  const act = async (fn, msg) => {
    try { await fn(); toast.success(msg); reload(); } catch (e) { toast.error(apiError(e)); }
  };
  const newPassword = () => {
    const pw = window.prompt(`New password for ${u.username} (12+ characters)`);
    if (pw) act(() => api.remoteSetPassword(u.id, pw), "Password changed — signed out everywhere");
  };
  return (
    <div className="flex items-center gap-2 py-2" data-testid={`remote-user-${u.username}`}>
      <div className="min-w-0 flex-1">
        <p className="text-sm font-semibold truncate">{u.name || u.username} <span className="font-mono text-[11px] opacity-60">{u.username}</span></p>
        <p className="text-[11px]" style={{ color: "var(--c4-muted)" }}>
          {u.two_factor ? "Code app set up" : "Sets up code app at first sign-in"} · last sign-in {when(u.last_login_at)}
        </p>
      </div>
      <IconBtn icon={KeyRound} label="Change password" onClick={newPassword} testid={`remote-user-${u.username}-password`} />
      <IconBtn icon={ShieldOff} label="Reset code app" testid={`remote-user-${u.username}-reset-2fa`}
        onClick={() => window.confirm(`Reset ${u.username}'s code app? They'll scan a new QR code at next sign-in.`) && act(() => api.remoteReset2fa(u.id), "Code app reset")} />
      <IconBtn icon={Trash2} label="Remove login" testid={`remote-user-${u.username}-delete`}
        onClick={() => window.confirm(`Remove ${u.username}'s outside access?`) && act(() => api.remoteDeleteUser(u.id), "Login removed")} />
    </div>
  );
};

const AddUser = ({ reload }) => {
  const [f, setF] = useState({ name: "", username: "", password: "" });
  const add = async () => {
    try {
      await api.remoteCreateUser(f);
      toast.success(`Login created for ${f.username}`);
      setF({ name: "", username: "", password: "" });
      reload();
    } catch (e) { toast.error(apiError(e)); }
  };
  return (
    <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 mt-2" data-testid="remote-add-user">
      <input className={inp} style={inpStyle} placeholder="Name" value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} data-testid="remote-new-name" />
      <input className={inp} style={inpStyle} placeholder="Username" autoCapitalize="none" value={f.username} onChange={(e) => setF({ ...f, username: e.target.value })} data-testid="remote-new-username" />
      <input className={inp} style={inpStyle} placeholder="Password (12+)" type="password" value={f.password} onChange={(e) => setF({ ...f, password: e.target.value })} data-testid="remote-new-password" />
      <button onClick={add} disabled={!f.username || !f.password} data-testid="remote-add-user-btn"
        className="sm:col-span-3 rounded-lg py-2 text-sm font-semibold flex items-center justify-center gap-2 disabled:opacity-40 active:scale-[0.98] transition-transform"
        style={{ background: "var(--c4-amber)", color: "#0A0D14" }}>
        <UserPlus className="w-4 h-4" /> Add login
      </button>
    </div>
  );
};

export const RemoteAccessSettings = () => {
  const [users, setUsers] = useState([]);
  const [me, setMe] = useState(null);
  const reload = useCallback(() => api.remoteUsers().then(setUsers).catch(() => {}), []);
  useEffect(() => { reload(); api.remoteMe().then(setMe).catch(() => {}); }, [reload]);
  const signOut = async () => { await api.remoteLogout().catch(() => {}); window.location.reload(); };
  return (
    <div className="glass rounded-2xl p-4" data-testid="settings-remote-access">
      <div className="flex items-center gap-2.5 mb-1">
        <div className="w-9 h-9 rounded-xl flex items-center justify-center" style={{ background: "rgba(16,185,129,0.15)" }}>
          <Globe2 className="w-4.5 h-4.5" style={{ color: "var(--c4-emerald)" }} />
        </div>
        <div>
          <p className="font-semibold text-sm">Outside access</p>
          <p className="text-[11px]" style={{ color: "var(--c4-muted)" }}>Personal logins (password + authenticator code) for use away from the apartment.</p>
        </div>
      </div>
      <div className="divide-y divide-white/5" data-testid="remote-user-list">
        {users.map((u) => <UserRow key={u.id} u={u} reload={reload} />)}
        {!users.length && <p className="text-xs py-2" style={{ color: "var(--c4-muted)" }}>No outside logins yet.</p>}
      </div>
      <AddUser reload={reload} />
      {me?.remote && me?.signed_in && (
        <button onClick={signOut} data-testid="remote-sign-out-btn" className="mt-3 w-full rounded-lg py-2 text-sm flex items-center justify-center gap-2" style={{ background: "rgba(255,255,255,0.05)" }}>
          <LogOut className="w-4 h-4" /> Sign {me.username} out of this device
        </button>
      )}
    </div>
  );
};
