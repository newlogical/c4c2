import { useState, useEffect } from "react";
import "@/App.css";
import { api } from "@/lib/api";
import { SystemProvider, useSystem } from "@/context/SystemContext";
import { Toaster } from "@/components/ui/sonner";
import { PinLock } from "@/components/PinLock";
import { TopBar } from "@/components/TopBar";
import { BottomNav } from "@/components/BottomNav";
import { DriverDrawer } from "@/components/DriverDrawer";
import { SettingsDrawer } from "@/components/SettingsDrawer";
import { SetupWizard } from "@/components/SetupWizard";
import { DeviceHealthPanel } from "@/components/DeviceHealthPanel";
import { PersonAlert } from "@/components/PersonAlert";
import { ScreenSaver } from "@/components/ScreenSaver";
import { HomeTab } from "@/components/tabs/HomeTab";
import { WatchTab } from "@/components/tabs/WatchTab";
import { ListenTab } from "@/components/tabs/ListenTab";
import { ClimateTab } from "@/components/tabs/ClimateTab";
import { SecurityTab } from "@/components/tabs/SecurityTab";
import { ScenesTab } from "@/components/tabs/ScenesTab";
import { AnimatePresence, motion } from "framer-motion";

const Controller = () => {
  const { state, loading, authed, refresh } = useSystem();
  const [unlocked, setUnlocked] = useState(false);
  useEffect(() => {
    if (authed) setUnlocked(true);
  }, [authed]);
  const [tab, setTab] = useState("home");
  const [driversOpen, setDriversOpen] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [wizardOpen, setWizardOpen] = useState(false);
  const [healthOpen, setHealthOpen] = useState(false);
  const [wizardSeen, setWizardSeen] = useState(false);
  const [saverOn, setSaverOn] = useState(() => localStorage.getItem("c4_saver") !== "off");
  const [saverMode, setSaverMode] = useState(() => localStorage.getItem("c4_saver_mode") || "clock");

  const toggleSaver = () => {
    setSaverOn((v) => {
      const nv = !v;
      localStorage.setItem("c4_saver", nv ? "on" : "off");
      return nv;
    });
  };
  const changeSaverMode = (m) => {
    setSaverMode(m);
    localStorage.setItem("c4_saver_mode", m);
  };

  useEffect(() => {
    const onUnauthorized = () => setUnlocked(false);
    window.addEventListener("c4-unauthorized", onUnauthorized);
    return () => window.removeEventListener("c4-unauthorized", onUnauthorized);
  }, []);

  useEffect(() => {
    if (unlocked && !wizardSeen && state && state.config && state.config.setup_done === false) {
      setWizardOpen(true);
      setWizardSeen(true);
    }
  }, [unlocked, state, wizardSeen]);

  if (loading) {
    return (
      <div className="c4-shell min-h-screen flex items-center justify-center">
        <div className="w-10 h-10 rounded-full border-2 border-white/10 border-t-[var(--c4-primary)] animate-spin" />
      </div>
    );
  }

  if (!unlocked) {
    return <PinLock onUnlock={async () => { await refresh(); setUnlocked(true); }} propertyName={state?.property_name} />;
  }

  const tabs = {
    home: <HomeTab onNavigate={setTab} onOpenHealth={() => setHealthOpen(true)} />,
    watch: <WatchTab />,
    listen: <ListenTab />,
    climate: <ClimateTab />,
    security: <SecurityTab />,
    scenes: <ScenesTab />,
  };

  return (
    <div className="c4-shell min-h-screen flex flex-col">
      <TopBar onLock={() => { api.logout().catch((e) => console.warn("Logout failed", e)); setUnlocked(false); }} onOpenDrivers={() => setDriversOpen(true)} onOpenSettings={() => setSettingsOpen(true)} onOpenHealth={() => setHealthOpen(true)} />
      <main className="flex-1 max-w-2xl w-full mx-auto">
        <AnimatePresence mode="wait">
          <motion.div
            key={tab}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            transition={{ duration: 0.25 }}
          >
            {tabs[tab]}
          </motion.div>
        </AnimatePresence>
      </main>
      <BottomNav active={tab} onChange={setTab} />
      <DriverDrawer open={driversOpen} onClose={() => setDriversOpen(false)} />
      <SettingsDrawer
        open={settingsOpen}
        onClose={() => setSettingsOpen(false)}
        onRunWizard={() => { setSettingsOpen(false); setWizardOpen(true); }}
        onOpenHealth={() => { setSettingsOpen(false); setHealthOpen(true); }}
        saverOn={saverOn}
        onToggleSaver={toggleSaver}
        saverMode={saverMode}
        onChangeSaverMode={changeSaverMode}
      />
      <DeviceHealthPanel open={healthOpen} onClose={() => setHealthOpen(false)} />
      <PersonAlert />
      <SetupWizard open={wizardOpen} onClose={() => setWizardOpen(false)} />
      <ScreenSaver enabled={saverOn} mode={saverMode} />
    </div>
  );
};

function App() {
  return (
    <div className="App">
      <SystemProvider>
        <Controller />
        <Toaster position="top-center" theme="dark" />
      </SystemProvider>
    </div>
  );
}

export default App;
