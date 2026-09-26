import { useState, useEffect } from "react";
import "@/App.css";
import { SystemProvider, useSystem } from "@/context/SystemContext";
import { Toaster } from "@/components/ui/sonner";
import { PinLock } from "@/components/PinLock";
import { TopBar } from "@/components/TopBar";
import { BottomNav } from "@/components/BottomNav";
import { DriverDrawer } from "@/components/DriverDrawer";
import { SettingsDrawer } from "@/components/SettingsDrawer";
import { SetupWizard } from "@/components/SetupWizard";
import { ScreenSaver } from "@/components/ScreenSaver";
import { HomeTab } from "@/components/tabs/HomeTab";
import { WatchTab } from "@/components/tabs/WatchTab";
import { ListenTab } from "@/components/tabs/ListenTab";
import { ClimateTab } from "@/components/tabs/ClimateTab";
import { SecurityTab } from "@/components/tabs/SecurityTab";
import { ScenesTab } from "@/components/tabs/ScenesTab";
import { AnimatePresence, motion } from "framer-motion";

const Controller = () => {
  const { state, loading } = useSystem();
  const [unlocked, setUnlocked] = useState(false);
  const [tab, setTab] = useState("home");
  const [driversOpen, setDriversOpen] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [wizardOpen, setWizardOpen] = useState(false);
  const [wizardSeen, setWizardSeen] = useState(false);
  const [saverOn, setSaverOn] = useState(() => localStorage.getItem("c4_saver") !== "off");

  const toggleSaver = () => {
    setSaverOn((v) => {
      const nv = !v;
      localStorage.setItem("c4_saver", nv ? "on" : "off");
      return nv;
    });
  };

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
    return <PinLock onUnlock={() => setUnlocked(true)} propertyName={state?.property_name} />;
  }

  const tabs = {
    home: <HomeTab onNavigate={setTab} />,
    watch: <WatchTab />,
    listen: <ListenTab />,
    climate: <ClimateTab />,
    security: <SecurityTab />,
    scenes: <ScenesTab />,
  };

  return (
    <div className="c4-shell min-h-screen flex flex-col">
      <TopBar onLock={() => setUnlocked(false)} onOpenDrivers={() => setDriversOpen(true)} onOpenSettings={() => setSettingsOpen(true)} />
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
        saverOn={saverOn}
        onToggleSaver={toggleSaver}
      />
      <SetupWizard open={wizardOpen} onClose={() => setWizardOpen(false)} />
      <ScreenSaver enabled={saverOn} />
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
