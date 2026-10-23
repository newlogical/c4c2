import React, { createContext, useContext, useState, useEffect, useCallback } from "react";
import { toast } from "sonner";
import { api } from "@/lib/api";

const ListenContext = createContext(null);
export const errText = (e) => e?.response?.data?.detail || e?.message || "Command failed";

export const ListenProvider = ({ children }) => {
  const [data, setData] = useState(null);
  const [shortcuts, setShortcuts] = useState([]);
  const [busy, setBusy] = useState(false);

  const refresh = useCallback(async () => {
    try {
      setData(await api.listen());
    } catch (e) {
      if (e?.response?.status !== 401) console.warn("Listen refresh failed", e);
    }
  }, []);

  const loadShortcuts = useCallback(async () => {
    try {
      setShortcuts(await api.shortcuts());
    } catch (e) {
      console.warn("Shortcuts load failed", e);
    }
  }, []);

  useEffect(() => {
    refresh();
    loadShortcuts();
    const t = setInterval(refresh, 10000); // amp status feedback
    return () => clearInterval(t);
  }, [refresh, loadShortcuts]);

  // Amp actions return the fresh room view. On failure show the amp's error and re-read the real state.
  const run = useCallback(async (promise, okMsg) => {
    setBusy(true);
    try {
      setData(await promise);
      if (okMsg) toast.success(okMsg);
      return true;
    } catch (e) {
      toast.error(errText(e));
      await refresh();
      return false;
    } finally {
      setBusy(false);
    }
  }, [refresh]);

  const value = { data, refresh, run, busy, shortcuts, setShortcuts, loadShortcuts };
  return <ListenContext.Provider value={value}>{children}</ListenContext.Provider>;
};

export const useListen = () => useContext(ListenContext);
