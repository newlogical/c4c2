import { Tv, PartyPopper, Bath, Moon, RotateCcw, Sparkles, Music, Volume2, Sun, Coffee, Film, Speaker, Headphones, Sofa } from "lucide-react";

export const SHORTCUT_ICONS = { Tv, PartyPopper, Bath, Moon, RotateCcw, Sparkles, Music, Volume2, Sun, Coffee, Film, Speaker, Headphones, Sofa };
export const shortcutIcon = (name) => SHORTCUT_ICONS[name] || Sparkles;

// Plain-language summary of what a shortcut does, using the client-facing source labels.
export const summarize = (sc, rooms, partySources) => {
  const parts = [];
  if (sc.restore_defaults) parts.push("Default sources everywhere");
  if (sc.party) {
    if (!sc.party.enabled) parts.push("Party Mode off");
    else {
      const src = partySources?.find((s) => s.input === sc.party.input)?.label;
      parts.push(`Party Mode${src ? `: ${src}` : ""}`);
    }
  }
  Object.entries(sc.rooms || {}).forEach(([rid, a]) => {
    const r = rooms?.find((x) => x.id === rid);
    if (!r) return;
    const bits = [];
    if (a.power === false) bits.push("off");
    if (a.power === true) bits.push("on");
    if (a.input != null) bits.push(r.sources.find((s) => s.input === a.input)?.label || "other source");
    if (a.volume != null) bits.push(`${a.volume}%`);
    if (a.mute != null) bits.push(a.mute ? "muted" : "unmuted");
    parts.push(`${r.name} ${bits.join(", ")}`);
  });
  return parts.join(" · ") || "No changes yet";
};
