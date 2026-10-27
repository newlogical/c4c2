import React, { useCallback, useEffect, useState } from "react";
import { Play, Pause, Loader2 } from "lucide-react";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { errText } from "@/context/ListenContext";

export const useWiimNowPlaying = (wid, active) => {
  const [np, setNp] = useState(null);
  const load = useCallback(() => api.wiimStatus(wid).then(setNp).catch(() => setNp(null)), [wid]);
  useEffect(() => {
    if (!active) { setNp(null); return undefined; }
    load();
    const t = setInterval(load, 5000);
    return () => clearInterval(t);
  }, [active, load]);
  return [np, setNp];
};

export const NowPlayingText = ({ np, testid }) => (
  <span className="block min-w-0 w-full" data-testid={testid}>
    <span className="block text-xs font-semibold truncate" data-testid={`${testid}-title`}>{np?.title || "Nothing playing"}</span>
    {np?.artist && <span className="block text-[11px] truncate opacity-75" data-testid={`${testid}-artist`}>{np.artist}</span>}
  </span>
);

export const PlayPauseButton = ({ wid, np, onChange, testid }) => {
  const [busy, setBusy] = useState(false);
  const toggle = async () => {
    setBusy(true);
    try { onChange(await api.wiimPlayPause(wid)); } catch (e) { toast.error(errText(e)); } finally { setBusy(false); }
  };
  const Icon = busy ? Loader2 : np?.playing ? Pause : Play;
  return (
    <button data-testid={testid} onClick={toggle} disabled={busy} aria-label={np?.playing ? "Pause" : "Play"}
      className="absolute top-3 right-3 w-10 h-10 rounded-full flex items-center justify-center active:scale-90 transition-transform"
      style={{ background: "#0A0D14", color: "var(--c4-amber)" }}>
      <Icon className={`w-4 h-4 ${busy ? "animate-spin" : ""}`} />
    </button>
  );
};
