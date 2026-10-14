import React, { useEffect, useState } from "react";
import { Music2, LogIn, Unlink } from "lucide-react";
import { toast } from "sonner";
import { useSystem } from "@/context/SystemContext";

const inp = "w-full rounded-lg px-3 py-2 text-sm outline-none";
const inpStyle = { background: "var(--c4-surface)", border: "1px solid var(--c4-border)", color: "var(--c4-text)" };

export const SpotifyCard = ({ config, setField, save }) => {
  const { api } = useSystem();
  const [status, setStatus] = useState(null);
  const sp = config.spotify || {};
  const load = () => api.spotifyStatus().then(setStatus).catch(() => {});
  useEffect(() => { load(); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const connect = async () => {
    try {
      await save();
      const { auth_url } = await api.spotifyLogin();
      window.open(auth_url, "_blank");
      toast("Finish signing in to Spotify in the new tab, then come back");
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Could not start Spotify sign-in");
    }
  };
  const unlink = async () => { await api.spotifyUnlink(); load(); toast("Spotify disconnected"); };

  return (
    <div className="glass rounded-2xl p-4 space-y-2.5" data-testid="settings-spotify">
      <div className="flex items-center gap-3">
        <div className="w-9 h-9 rounded-xl flex items-center justify-center" style={{ background: "rgba(29,185,84,0.15)" }}><Music2 className="w-4.5 h-4.5" style={{ color: "#1DB954" }} /></div>
        <div className="flex-1">
          <p className="font-semibold text-sm">Spotify</p>
          <p className="text-[11px]" style={{ color: "var(--c4-muted)" }} data-testid="spotify-status-text">
            {status?.connected ? `Connected as ${status.user}${status.premium ? " · Premium" : " · Free (needs Premium to play on speakers)"}` : "Not connected"}
          </p>
        </div>
      </div>
      <p className="text-[11px]" style={{ color: "var(--c4-muted)" }}>
        Create an app at developer.spotify.com → Dashboard → Create app. Redirect URI: <code>{sp.redirect_uri}</code> · API: Web API. Then paste its Client ID & Secret.
      </p>
      <input data-testid="spotify-client-id-input" className={inp} style={inpStyle} placeholder="Client ID" value={sp.client_id || ""} onChange={(e) => setField("spotify", "client_id", e.target.value.trim())} />
      <input data-testid="spotify-client-secret-input" type="password" className={inp} style={inpStyle} placeholder="Client Secret" value={sp.client_secret || ""} onChange={(e) => setField("spotify", "client_secret", e.target.value.trim())} />
      <div className="flex gap-2">
        <button data-testid="spotify-connect-btn" onClick={connect} className="flex-1 rounded-lg py-2 text-xs font-semibold flex items-center justify-center gap-1.5" style={{ background: "#1DB954", color: "#04130a" }}>
          <LogIn className="w-4 h-4" /> {status?.connected ? "Reconnect" : "Connect"} (on the mini-PC)
        </button>
        {status?.connected && (
          <button data-testid="spotify-unlink-btn" onClick={unlink} className="rounded-lg px-3 py-2 text-xs font-semibold flex items-center gap-1.5 glass"><Unlink className="w-4 h-4" /> Disconnect</button>
        )}
      </div>
      <p className="text-[10px]" style={{ color: "var(--c4-muted)" }}>Sign-in must happen in a browser on the mini-PC itself (Spotify only allows 127.0.0.1 for local apps).</p>
    </div>
  );
};

export default SpotifyCard;
