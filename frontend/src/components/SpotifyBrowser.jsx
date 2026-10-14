import React, { useEffect, useState } from "react";
import { Loader2, Music2, ExternalLink } from "lucide-react";
import { useSystem } from "@/context/SystemContext";

const chip = (on) => ({ background: on ? "#1DB954" : "var(--c4-surface)", color: on ? "#04130a" : "var(--c4-text)", border: "1px solid var(--c4-border)" });

const Item = ({ it, picked, onPick }) => (
  <button data-testid={`spotify-item-${it.uri}`} onClick={() => onPick({ kind: "spotify", uri: it.uri, name: it.name })}
    className="rounded-xl p-2.5 flex items-center gap-2.5 text-left active:scale-95 transition" style={chip(picked)}>
    {it.image ? <img src={it.image} alt="" className="w-10 h-10 rounded-md object-cover shrink-0" /> : <Music2 className="w-5 h-5 shrink-0" />}
    <span className="min-w-0">
      <span className="block text-xs font-semibold truncate">{it.name}</span>
      <span className="block text-[10px] capitalize opacity-70">{it.kind}</span>
    </span>
  </button>
);

export const SpotifyBrowser = ({ pick, onPick }) => {
  const { api } = useSystem();
  const [status, setStatus] = useState(null);
  const [lib, setLib] = useState(null);
  const [err, setErr] = useState("");

  useEffect(() => {
    api.spotifyStatus().then((s) => {
      setStatus(s);
      if (s.connected) api.spotifyLibrary().then(setLib).catch((e) => setErr(e?.response?.data?.detail || "Could not load Spotify"));
    }).catch(() => setStatus({ configured: false, connected: false }));
  }, [api]);

  if (!status) return <Loader2 className="w-5 h-5 animate-spin" />;
  if (!status.connected)
    return (
      <div className="rounded-xl p-4 text-xs space-y-2" style={{ background: "var(--c4-surface)" }} data-testid="spotify-not-connected">
        <p className="font-semibold text-sm">Spotify isn't connected yet</p>
        <p style={{ color: "var(--c4-muted)" }}>
          {status.configured ? "Sign in once from a browser on the mini-PC: Settings → Spotify → Connect." : "Add your Spotify app's Client ID and Secret in Settings → Spotify, then sign in once on the mini-PC."}
        </p>
        <p style={{ color: "var(--c4-muted)" }}>Starting music on a speaker needs Spotify Premium. Without it, use the Spotify app on a phone and pick the module as the speaker.</p>
      </div>
    );
  if (err) return <p className="text-xs" style={{ color: "var(--c4-rose)" }}>{err}</p>;
  if (!lib) return <Loader2 className="w-5 h-5 animate-spin" />;
  const pickedUri = pick?.kind === "spotify" ? pick.uri : null;
  return (
    <div className="space-y-4" data-testid="spotify-browser">
      <p className="text-[11px]" style={{ color: "var(--c4-muted)" }}>
        Signed in as {lib.user}{!lib.premium && <span style={{ color: "var(--c4-amber)" }}> · Free account: playback on speakers needs Premium</span>}
      </p>
      {lib.recent.length > 0 && (
        <div>
          <p className="text-[10px] uppercase tracking-widest mb-2" style={{ color: "var(--c4-muted)" }}>Recently played</p>
          <div className="grid sm:grid-cols-2 gap-2">{lib.recent.map((it) => <Item key={it.uri} it={it} picked={pickedUri === it.uri} onPick={onPick} />)}</div>
        </div>
      )}
      <div>
        <p className="text-[10px] uppercase tracking-widest mb-2" style={{ color: "var(--c4-muted)" }}>Playlists</p>
        <div className="grid sm:grid-cols-2 gap-2">{lib.playlists.map((it) => <Item key={it.uri} it={it} picked={pickedUri === it.uri} onPick={onPick} />)}</div>
      </div>
      <a href="https://open.spotify.com" target="_blank" rel="noreferrer" className="text-[11px] flex items-center gap-1" style={{ color: "var(--c4-muted)" }}>
        <ExternalLink className="w-3 h-3" /> Manage playlists in Spotify
      </a>
    </div>
  );
};

export default SpotifyBrowser;
