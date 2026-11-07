"use client";

import {
  CalendarDays,
  ListChecks,
  RotateCcw,
  Sun,
} from "lucide-react";

import type { Tab } from "@/lib/types";
import { cn } from "@/lib/utils";

const NAV = [
  { key: "today" as const, label: "Today", icon: Sun },
  { key: "reconciliation" as const, label: "Reconciliation", icon: RotateCcw },
];

const MOBILE_NAV = [
  { key: "today" as const, label: "Today", icon: Sun },
  { key: "tasks" as const, label: "Tasks", icon: ListChecks },
  { key: "reconciliation" as const, label: "Reconciliation", icon: RotateCcw },
];

export function NavigationRail({
  tab,
  onTab,
}: {
  tab: Tab;
  onTab: (tab: Tab) => void;
}) {
  return (
    <aside className="hidden h-full flex-col items-center gap-4 rounded-panel bg-rail px-2 py-4 md:flex">
      <div className="grid h-10 w-10 place-items-center rounded-2xl bg-ink text-sm font-bold text-white shadow-card">
        Z
      </div>

      <div className="h-px w-6 bg-black/15" />

      <nav className="flex flex-col items-center gap-2" aria-label="Dashboard">
        {NAV.map(({ key, label, icon: Icon }) => (
          <button
            key={key}
            type="button"
            aria-label={label}
            title={label}
            onClick={() => onTab(key)}
            className={cn(
              "grid h-11 w-11 place-items-center rounded-2xl text-ink/65 transition hover:bg-black/10 hover:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ink/30",
              tab === key &&
                "bg-ink text-white shadow-[0_10px_20px_-10px_rgba(0,0,0,0.7)] hover:bg-ink hover:text-white",
            )}
          >
            <Icon size={18} strokeWidth={2} />
          </button>
        ))}
      </nav>

      <div className="my-1 h-px w-6 bg-black/15" />

      <a
        href="/api/dashboard/calendar.ics"
        target="_blank"
        rel="noreferrer"
        aria-label="Sync to calendar"
        title="Sync to calendar"
        className="grid h-11 w-11 place-items-center rounded-2xl text-ink/65 transition hover:bg-black/10 hover:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ink/30"
      >
        <CalendarDays size={18} strokeWidth={2} />
      </a>

      <div className="mt-auto grid h-10 w-10 place-items-center rounded-full bg-ink text-[11px] font-bold text-white ring-4 ring-white/60">
        OW
      </div>
    </aside>
  );
}

export function MobileNav({
  tab,
  onTab,
}: {
  tab: Tab;
  onTab: (tab: Tab) => void;
}) {
  return (
    <nav
      className="fixed inset-x-3 bottom-3 z-30 flex items-center justify-around rounded-full border border-black/10 bg-rail px-2 py-2 shadow-shell lg:hidden"
      aria-label="Dashboard"
    >
      {MOBILE_NAV.map(({ key, label, icon: Icon }) => (
        <button
          key={key}
          type="button"
          onClick={() => onTab(key)}
          className={cn(
            "flex flex-1 flex-col items-center gap-1 rounded-full px-2 py-1.5 text-[9px] font-semibold text-ink/60",
            tab === key && "bg-ink text-white",
          )}
        >
          <Icon size={16} />
          {label}
        </button>
      ))}
      <a
        href="/api/dashboard/calendar.ics"
        target="_blank"
        rel="noreferrer"
        className="flex flex-1 flex-col items-center gap-1 rounded-full px-2 py-1.5 text-[9px] font-semibold text-ink/60"
      >
        <CalendarDays size={16} />
        Calendar
      </a>
    </nav>
  );
}
