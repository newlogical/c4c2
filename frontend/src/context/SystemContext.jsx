import React, { createContext, useContext, useEffect, useState, useCallback } from "react";
import { api } from "@/lib/api";

const SystemContext = createContext(null);

export const SystemProvider = ({ children }) => {
  const [state, setState] = useState(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    const data = await api.getState();
    setState(data);
    setLoading(false);
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  // Run any api action that returns the full state, then commit it.
  const act = useCallback(async (promise) => {
    const data = await promise;
    if (data && data.command_log !== undefined && data.displays) {
      setState(data);
    }
    return data;
  }, []);

  const value = { state, setState, loading, refresh, act, api };
  return <SystemContext.Provider value={value}>{children}</SystemContext.Provider>;
};

export const useSystem = () => {
  const ctx = useContext(SystemContext);
  if (!ctx) throw new Error("useSystem must be used within SystemProvider");
  return ctx;
};
