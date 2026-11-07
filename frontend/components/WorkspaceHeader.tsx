"use client";

import { CalendarDays, Plus, Target } from "lucide-react";

import type { Tab } from "@/lib/types";
import { Button, LinkButton } from "@/components/ui";
import { cn } from "@/lib/utils";

export function WorkspaceHeader({
  dateLabel,
  subLabel,
  tab,
  onTab,
  onGoal,
  onCommitment,
  onTask,
}: {
  dateLabel: string;
  subLabel: string;
  tab: Tab;
  onTab: (tab: Tab) => void;
  onGoal: () => void;
  onCommitment: () => void;
  onTask: () => void;
}) {
  return (
    <header className="flex flex-wrap items-start justify-between gap-4 px-1 pb-5">
      <div>
        <h1 className="font-display text-[30px] font-semibold leading-none tracking-[-0.055em] sm:text-[34px]">
          {dateLabel}
        </h1>
        <p className="mt-1 text-[11px] font-medium text-muted">{subLabel}</p>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <div className="inline-flex rounded-full border border-black/5 bg-black/[0.035] p-1">
          <button
            type="button"
            onClick={() => onTab("today")}
            className={cn(
              "rounded-full px-4 py-2 text-[11px] font-semibold text-muted transition hover:text-ink",
              tab === "today" && "bg-ink text-white shadow-sm hover:text-white",
            )}
          >
            Plan
          </button>
          <button
            type="button"
            onClick={() => onTab("reconciliation")}
            className={cn(
              "rounded-full px-4 py-2 text-[11px] font-semibold text-muted transition hover:text-ink",
              tab === "reconciliation" &&
                "bg-ink text-white shadow-sm hover:text-white",
            )}
          >
            Reconcile
          </button>
        </div>

        <Button variant="secondary" onClick={onGoal}>
          <Target size={13} />
          New Goal
        </Button>
        <Button variant="secondary" onClick={onCommitment}>
          <Plus size={13} />
          Commitment
        </Button>
        <Button variant="primary" onClick={onTask}>
          <Plus size={13} />
          Add Task
        </Button>
        <LinkButton
          variant="calendar"
          href="/api/dashboard/calendar.ics"
          target="_blank"
          rel="noreferrer"
        >
          <CalendarDays size={13} />
          Sync to Calendar
        </LinkButton>
      </div>
    </header>
  );
}
