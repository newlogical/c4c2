import React, { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { X, UserRound } from "lucide-react";
import { useSystem } from "@/context/SystemContext";
import { CameraPlayer } from "@/components/CameraPlayer";

const SHOW_FOR_MS = 60000;

export const PersonAlert = () => {
  const { api } = useSystem();
  const [alert, setAlert] = useState(null);
  const seen = useRef(localStorage.getItem("c4_person_seen") || "");

  useEffect(() => {
    const poll = () =>
      api.alerts().then((r) => {
        const a = r.person_alert;
        if (a && a.id !== seen.current && Date.now() - new Date(a.at).getTime() < SHOW_FOR_MS) setAlert(a);
      }).catch(() => {});
    poll();
    const id = setInterval(poll, 4000);
    return () => clearInterval(id);
  }, [api]);

  useEffect(() => {
    if (!alert) return;
    const t = setTimeout(() => close(), SHOW_FOR_MS);
    return () => clearTimeout(t);
  }, [alert]); // eslint-disable-line react-hooks/exhaustive-deps

  const close = () => {
    if (alert) {
      seen.current = alert.id;
      localStorage.setItem("c4_person_seen", alert.id);
    }
    setAlert(null);
  };

  if (!alert) return null;
  return createPortal(
    <div className="fixed inset-0 z-[90] flex items-center justify-center p-4" style={{ background: "rgba(5,8,14,0.75)", backdropFilter: "blur(8px)" }} data-testid="person-alert">
      <div className="w-full max-w-2xl glass rounded-3xl overflow-hidden" style={{ border: "1px solid rgba(244,63,94,0.5)" }}>
        <div className="flex items-center justify-between px-5 py-4">
          <div className="flex items-center gap-3">
            <div className="w-11 h-11 rounded-2xl flex items-center justify-center animate-pulse" style={{ background: "rgba(244,63,94,0.2)" }}>
              <UserRound className="w-6 h-6" style={{ color: "var(--c4-rose)" }} />
            </div>
            <div>
              <p className="font-head font-bold text-lg" data-testid="person-alert-title">Person at {alert.camera}</p>
              <p className="text-xs" style={{ color: "var(--c4-muted)" }}>{new Date(alert.at).toLocaleTimeString()} · Security armed</p>
            </div>
          </div>
          <button data-testid="person-alert-close-btn" onClick={close} className="w-12 h-12 rounded-2xl glass-elevated flex items-center justify-center active:scale-95 transition" aria-label="Dismiss">
            <X className="w-6 h-6" />
          </button>
        </div>
        <div className="aspect-video bg-black">
          <CameraPlayer camId="cam_front" />
        </div>
      </div>
    </div>,
    document.body
  );
};

export default PersonAlert;
