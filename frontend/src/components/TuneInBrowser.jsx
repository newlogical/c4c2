import React, { useEffect, useState } from "react";
import { Search, Radio, Star, ChevronLeft, Loader2, Trash2, Bookmark } from "lucide-react";
import { toast } from "sonner";
import { useSystem } from "@/context/SystemContext";

const chip = (on) => ({ background: on ? "var(--c4-primary)" : "var(--c4-surface)", color: on ? "#fff" : "var(--c4-text)", border: "1px solid var(--c4-border)" });
const CATS = [["saved", "Saved"], ["local", "Local"], ["sports", "Sports"], ["news", "News"], ["talk", "Talk"], ["music", "Music"]];

const StationRow = ({ st, picked, onPick, saved, onSave, onRemove }) => (
  <div className="rounded-xl p-2.5 flex items-center gap-2.5" style={chip(picked)} data-testid={`tunein-station-${st.id || st.guide_id}`}>
    <button onClick={() => onPick(st)} className="flex items-center gap-2.5 flex-1 min-w-0 text-left">
      {st.image ? <img src={st.image} alt="" className="w-9 h-9 rounded-md object-cover shrink-0" /> : <Radio className="w-5 h-5 shrink-0" />}
      <span className="min-w-0">
        <span className="block text-xs font-semibold truncate">{st.name}</span>
        <span className="block text-[10px] truncate opacity-70">{st.category || st.subtext}</span>
      </span>
    </button>
    {onRemove ? (
      <button data-testid={`tunein-remove-${st.id}`} onClick={() => onRemove(st)} className="w-8 h-8 flex items-center justify-center opacity-70"><Trash2 className="w-4 h-4" /></button>
    ) : (
      <button data-testid={`tunein-save-${st.guide_id}`} onClick={() => onSave(st)} className="w-8 h-8 flex items-center justify-center">
        <Bookmark className="w-4 h-4" style={saved ? { fill: "currentColor" } : {}} />
      </button>
    )}
  </div>
);

export const TuneInBrowser = ({ pick, onPick }) => {
  const { api } = useSystem();
  const [cat, setCat] = useState("saved");
  const [trail, setTrail] = useState([]);
  const [data, setData] = useState(null);
  const [saved, setSaved] = useState([]);
  const [q, setQ] = useState("");

  const loadSaved = () => api.tuneinSaved().then((r) => setSaved(r.stations)).catch(() => {});
  useEffect(() => { loadSaved(); }, []); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    if (cat === "saved" || cat === "search") return;
    setData(null);
    api.tuneinBrowse(trail.length ? trail[trail.length - 1].id : cat).then(setData).catch((e) => { toast.error(e?.response?.data?.detail || "TuneIn unavailable"); setData({ stations: [], categories: [] }); });
  }, [api, cat, trail]);

  const doSearch = async () => {
    if (!q.trim()) return;
    setCat("search"); setTrail([]); setData(null);
    try { setData(await api.tuneinSearch(q)); } catch { toast.error("TuneIn search failed"); setData({ stations: [] }); }
  };
  const save = async (st) => {
    const r = await api.tuneinSave({ guide_id: st.guide_id, name: st.name, image: st.image, category: "Saved" });
    setSaved(r.stations);
    toast.success(`Saved ${st.name}`);
  };
  const remove = async (st) => setSaved((await api.tuneinUnsave(st.id)).stations);
  const isSaved = (st) => saved.some((x) => x.id === st.guide_id);
  const pickStation = (st) => onPick({ kind: "station", id: st.id || st.guide_id, saved: !!st.id, guide_id: st.guide_id, name: st.name });
  const pickedId = pick?.kind === "station" ? pick.id : null;

  return (
    <div className="space-y-3" data-testid="tunein-browser">
      <div className="flex gap-2">
        <input data-testid="tunein-search-input" value={q} onChange={(e) => setQ(e.target.value)} onKeyDown={(e) => e.key === "Enter" && doSearch()}
          placeholder="Search stations (e.g. WFAN, jazz, Bloomberg)" className="flex-1 rounded-xl px-3 py-2.5 text-sm outline-none"
          style={{ background: "var(--c4-surface)", border: "1px solid var(--c4-border)", color: "var(--c4-text)" }} />
        <button data-testid="tunein-search-btn" onClick={doSearch} className="w-11 rounded-xl flex items-center justify-center" style={{ background: "var(--c4-primary)" }}><Search className="w-4 h-4 text-white" /></button>
      </div>
      <div className="flex gap-1.5 overflow-x-auto no-scrollbar">
        {CATS.map(([k, label]) => (
          <button key={k} data-testid={`tunein-cat-${k}`} onClick={() => { setCat(k); setTrail([]); }} className="px-3 py-1.5 rounded-full text-[11px] font-semibold shrink-0" style={chip(cat === k)}>{label}</button>
        ))}
      </div>
      {trail.length > 0 && (
        <button data-testid="tunein-back-btn" onClick={() => setTrail((t) => t.slice(0, -1))} className="text-xs flex items-center gap-1" style={{ color: "var(--c4-muted)" }}>
          <ChevronLeft className="w-4 h-4" /> {trail[trail.length - 1].name}
        </button>
      )}
      {cat === "saved" ? (
        <div className="grid sm:grid-cols-2 gap-2">
          {saved.map((st) => <StationRow key={st.id} st={st} picked={pickedId === st.id} onPick={pickStation} onRemove={remove} />)}
        </div>
      ) : !data ? <Loader2 className="w-5 h-5 animate-spin" /> : (
        <div className="space-y-3">
          {(data.categories || []).length > 0 && (
            <div className="flex flex-wrap gap-1.5">
              {data.categories.map((c) => (
                <button key={c.id} data-testid={`tunein-sub-${c.id}`} onClick={() => setTrail((t) => [...t, c])} className="px-3 py-1.5 rounded-full text-[11px]" style={chip(false)}>{c.name}</button>
              ))}
            </div>
          )}
          <div className="grid sm:grid-cols-2 gap-2">
            {data.stations.map((st) => <StationRow key={st.guide_id} st={st} picked={pickedId === st.guide_id} onPick={pickStation} saved={isSaved(st)} onSave={save} />)}
          </div>
          {data.stations.length === 0 && (data.categories || []).length === 0 && <p className="text-xs" style={{ color: "var(--c4-muted)" }}>Nothing here.</p>}
        </div>
      )}
      <p className="text-[10px]" style={{ color: "var(--c4-muted)" }}><Star className="inline w-3 h-3" /> Live game broadcasts can be blacked out on internet streams by league rights.</p>
    </div>
  );
};

export default TuneInBrowser;
