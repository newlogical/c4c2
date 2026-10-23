import React from "react";
import { api } from "@/lib/api";
import { useListen } from "@/context/ListenContext";
import { shortcutIcon } from "@/lib/shortcutIcons";

export const FavoriteShortcuts = () => {
  const { shortcuts, run, busy } = useListen();
  const favs = shortcuts.filter((s) => s.favorite);
  if (!favs.length) return null;
  return (
    <div className="flex sm:grid sm:grid-cols-3 gap-3 overflow-x-auto no-scrollbar -mx-4 px-4 sm:mx-0 sm:px-0" data-testid="favorite-shortcuts">
      {favs.map((s) => {
        const Icon = shortcutIcon(s.icon);
        return (
          <button key={s.id} data-testid={`fav-shortcut-${s.id}`} disabled={busy} onClick={() => run(api.runShortcut(s.id), `${s.name} done`)}
            className="glass rounded-2xl p-3.5 sm:p-4 w-36 sm:w-auto shrink-0 min-h-[76px] sm:min-h-[84px] flex flex-col items-start justify-between text-left active:scale-[0.97] transition-transform disabled:opacity-50">
            <Icon className="w-5 h-5" style={{ color: "var(--c4-cyan)" }} />
            <span className="font-semibold text-sm leading-tight">{s.name}</span>
          </button>
        );
      })}
    </div>
  );
};
