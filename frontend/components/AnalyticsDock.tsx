"use client";

import { useMemo } from "react";

import { cn, formatDate } from "@/lib/utils";
import type { DashboardTask } from "@/lib/types";

function Donut({
  percentage,
  label,
  tone = "#F6EA74",
}: {
  percentage: number;
  label: string;
  tone?: string;
}) {
  const value = Math.max(0, Math.min(100, Math.round(percentage)));
  return (
    <div
      className="relative grid h-24 w-24 place-items-center rounded-full"
      style={{
        background: `conic-gradient(${tone} ${value * 3.6}deg, rgba(255,255,255,0.13) 0)`,
      }}
    >
      <div className="grid h-[74px] w-[74px] place-items-center rounded-full bg-ink text-center">
        <div>
          <p className="font-display text-2xl font-semibold tracking-[-0.06em]">
            {value}%
          </p>
          <p className="text-[7px] font-bold uppercase tracking-[0.14em] text-white/40">
            {label}
          </p>
        </div>
      </div>
    </div>
  );
}

export function AnalyticsDock({
  counts,
  tasks,
}: {
  counts: { active: number; parked: number; completed: number; total: number };
  tasks: DashboardTask[];
}) {
  const completion = counts.total ? (counts.completed / counts.total) * 100 : 0;
  const week = useMemo(() => {
    const today = new Date();
    const weekday = today.getDay();
    const mondayOffset = weekday === 0 ? -6 : 1 - weekday;
    const monday = new Date(today);
    monday.setDate(today.getDate() + mondayOffset);
    return Array.from({ length: 5 }, (_, index) => {
      const current = new Date(monday);
      current.setDate(monday.getDate() + index);
      const key = current.toISOString().slice(0, 10);
      return {
        key,
        label: new Intl.DateTimeFormat("en-US", {
          weekday: "short",
          timeZone: "UTC",
        }).format(new Date(`${key}T12:00:00Z`)),
        count: tasks.filter(
          (task) =>
            task.scheduled_date === key &&
            task.status !== "cancelled",
        ).length,
      };
    });
  }, [tasks]);
  const maxCount = Math.max(1, ...week.map((day) => day.count));

  const mix = [
    { label: "Active", value: counts.active, tone: "bg-coral" },
    { label: "Parked", value: counts.parked, tone: "bg-lavender" },
    { label: "Done", value: counts.completed, tone: "bg-mint" },
  ];
  const mixTotal = Math.max(1, counts.active + counts.parked + counts.completed);

  return (
    <section className="mt-4 grid grid-cols-1 gap-3 md:grid-cols-3">
      <article className="flex items-center gap-5 rounded-[24px] bg-ink p-5 text-white shadow-darkcard">
        <Donut percentage={completion} label="complete" />
        <div>
          <p className="text-[9px] font-bold uppercase tracking-[0.16em] text-white/40">
            Plan health
          </p>
          <p className="mt-2 font-display text-3xl font-semibold tracking-[-0.06em]">
            {counts.completed}/{counts.total}
          </p>
          <p className="mt-1 text-[11px] text-white/45">
            {counts.active} still active
          </p>
        </div>
      </article>

      <article className="rounded-[24px] border border-black/[0.06] bg-white/85 p-5 shadow-card backdrop-blur-xl">
        <p className="text-[9px] font-bold uppercase tracking-[0.16em] text-muted">
          Task mix
        </p>
        <div className="mt-3 flex items-center gap-5">
          <div
            className="relative h-20 w-20 rounded-full"
            style={{
              background: `conic-gradient(#FF6B5E 0 ${(counts.active / mixTotal) * 360}deg, #C7A3F3 ${(counts.active / mixTotal) * 360}deg ${((counts.active + counts.parked) / mixTotal) * 360}deg, #9DEBB5 ${((counts.active + counts.parked) / mixTotal) * 360}deg 360deg)`,
            }}
          >
            <div className="absolute inset-[18px] rounded-full bg-white" />
          </div>
          <div className="space-y-1.5">
            {mix.map((item) => (
              <div key={item.label} className="flex items-center gap-2">
                <span className={cn("h-2 w-2 rounded-full", item.tone)} />
                <span className="text-[10px] font-medium text-ink/65">
                  {item.value} {item.label.toLowerCase()}
                </span>
              </div>
            ))}
          </div>
        </div>
      </article>

      <article className="rounded-[24px] border border-black/[0.06] bg-white/85 p-5 shadow-card backdrop-blur-xl">
        <div className="flex items-center justify-between">
          <p className="text-[9px] font-bold uppercase tracking-[0.16em] text-muted">
            Weekly activity
          </p>
          <span className="rounded-full bg-coral/15 px-2 py-0.5 text-[9px] font-bold text-coral">
            {tasks.length} tasks
          </span>
        </div>
        <div className="mt-4 flex h-20 items-end gap-2">
          {week.map((day) => (
            <div key={day.key} className="flex flex-1 flex-col items-center gap-1.5">
              <div className="flex h-16 w-full items-end">
                <div
                  className={cn(
                    "w-full rounded-t-full bg-lavender/70 transition-all duration-500",
                    day.count === maxCount && "bg-coral",
                  )}
                  style={{
                    height: `${Math.max(8, (day.count / maxCount) * 100)}%`,
                  }}
                />
              </div>
              <span className="text-[8px] font-semibold uppercase tracking-[0.08em] text-muted/70">
                {day.label}
              </span>
            </div>
          ))}
        </div>
        <p className="mt-1 text-[9px] text-muted/60">
          {formatDate(week[0]?.key ?? "", false)} –{" "}
          {formatDate(week[week.length - 1]?.key ?? "", false)}
        </p>
      </article>
    </section>
  );
}
