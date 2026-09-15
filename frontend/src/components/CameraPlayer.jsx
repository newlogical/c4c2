import React, { useEffect, useRef, useState } from "react";
import Hls from "hls.js";
import { Loader2, WifiOff } from "lucide-react";
import { api, BACKEND } from "@/lib/api";

const STILL = "https://images.unsplash.com/photo-1787659601659-399e4ea21429?crop=entropy&cs=srgb&fm=jpg&q=85&w=1200";

export const CameraPlayer = ({ full }) => {
  const videoRef = useRef(null);
  const [status, setStatus] = useState("loading"); // loading | playing | error
  const [demo, setDemo] = useState(false);

  useEffect(() => {
    let hls;
    let cancelled = false;

    const start = async () => {
      try {
        const info = await api.cameraStream();
        if (cancelled) return;
        setDemo(!!info.demo);
        const src = info.demo ? info.hls_url : `${BACKEND}${info.hls_url}`;
        const video = videoRef.current;
        if (!video) return;

        if (Hls.isSupported()) {
          hls = new Hls({ liveSyncDurationCount: 3, enableWorker: true });
          hls.loadSource(src);
          hls.attachMedia(video);
          hls.on(Hls.Events.MANIFEST_PARSED, () => {
            video.play().catch(() => {});
            setStatus("playing");
          });
          hls.on(Hls.Events.ERROR, (_e, data) => {
            if (data.fatal) setStatus("error");
          });
        } else if (video.canPlayType("application/vnd.apple.mpegurl")) {
          video.src = src;
          video.addEventListener("loadedmetadata", () => {
            video.play().catch(() => {});
            setStatus("playing");
          });
        } else {
          setStatus("error");
        }
      } catch (e) {
        setStatus("error");
      }
    };

    start();
    return () => {
      cancelled = true;
      if (hls) hls.destroy();
    };
  }, []);

  return (
    <div className="relative w-full h-full overflow-hidden bg-black" data-testid="camera-player">
      <video
        ref={videoRef}
        muted
        playsInline
        autoPlay
        poster={STILL}
        className="w-full h-full object-cover"
        style={{ filter: "saturate(1.05) contrast(1.05)" }}
      />
      <div className="absolute inset-0 pointer-events-none" style={{ background: "linear-gradient(180deg, rgba(6,182,212,0.05), transparent 30%, transparent 70%, rgba(10,13,20,0.45))" }} />

      <div className="absolute top-3 left-3 flex items-center gap-1.5 px-2 py-1 rounded-md" style={{ background: "rgba(10,13,20,0.7)" }}>
        <span className="w-2 h-2 rounded-full animate-motion" style={{ background: "#EF4444" }} />
        <span className="text-[10px] font-mono font-semibold tracking-wide">LIVE</span>
      </div>
      <div className="absolute top-3 right-3 px-2 py-1 rounded-md font-mono text-[10px]" style={{ background: "rgba(10,13,20,0.7)", color: "var(--c4-cyan)" }}>
        {demo ? "DEMO STREAM" : "UniFi Protect"} · {full ? "FULLSCREEN" : "HLS"}
      </div>

      {status === "loading" && (
        <div className="absolute inset-0 flex items-center justify-center" style={{ background: "rgba(10,13,20,0.6)" }}>
          <Loader2 className="w-6 h-6 animate-spin" style={{ color: "var(--c4-cyan)" }} />
        </div>
      )}
      {status === "error" && demo && (
        <div className="absolute inset-0">
          <img src={STILL} alt="Camera" className="w-full h-full object-cover" style={{ filter: "saturate(1.05) brightness(0.85)" }} />
          <div className="absolute bottom-3 left-3 font-mono text-[10px]" style={{ color: "rgba(255,255,255,0.7)" }}>
            {new Date().toLocaleString()}
          </div>
        </div>
      )}
      {status === "error" && !demo && (
        <div className="absolute inset-0 flex flex-col items-center justify-center gap-2" style={{ background: "rgba(10,13,20,0.85)" }}>
          <WifiOff className="w-6 h-6" style={{ color: "var(--c4-rose)" }} />
          <p className="text-xs" style={{ color: "var(--c4-muted)" }}>Stream unavailable</p>
        </div>
      )}
    </div>
  );
};

export default CameraPlayer;
