"use client";

import { CalendarDays, Check, Clock } from "lucide-react";

import { cn, formatDate, parseTimeLabel } from "@/lib/utils";
import type { FixedEvent, TodayItem, TodayPayload } from "@/lib/types";
import { EmptyState, Spinner } from "@/components/ui";

const DAY_LABELS = ["Mon", "Tue", "Wed", "Thu", "Fri"];
const START_MINUTE = 8 * 60;
const END_MINUTE = 18 * 60;
const GRID_MINUTES = END_MINUTE - START_MINUTE;

function weekDays(date: string): { label: string; day: number; date: string }[] {
  const parsed = new Date(`${date}T12:00:00Z`);
  const weekday = parsed.getUTCDay();
  const mondayOffset = weekday === 0 ? -6 : 1 - weekday;
  return Array.from({ length: 5 }, (_, index) => {
    const current = new Date(parsed);
    current.setUTCDate(parsed.getUTCDate() + mondayOffset + index);
    return {
      label: DAY_LABELS[index],
      day: current.getUTCDate(),
      date: current.toISOString().slice(0, 10),
    };
  });
}

function activeDayIndex(date: string): number {
  const weekday = new Date(`${date}T12:00:00Z`).getUTCDay();
  if (weekday === 0) {
    return 4;
  }
  if (weekday === 6) {
    return 4;
  }
  return weekday - 1;
}

function timePosition(label: string | null): { top: number; height: number } | null {
  const start = parseTimeLabel(label);
  if (start === null) {
    return null;
  }
  const top = Math.max(0, ((start - START_MINUTE) / GRID_MINUTES) * 100);
  return { top, height: 9 };
}

function CalendarLink({ url, title }: { url: string | null; title: string }) {
  if (!url) {
    return null;
  }
  return (
    <a
      href={url}
      target="_blank"
      rel="noreferrer"
      aria-label={`Add ${title} to Google Calendar`}
      title="Add to Google Calendar"
      className="grid h-7 w-7 place-items-center rounded-full border border-black/10 bg-white/45 text-ink/65 transition hover:bg-white/80"
    >
      <CalendarDays size={13} />
    </a>
  );
}

function PlanTaskCard({
  item,
  busy,
  onComplete,
}: {
  item: TodayItem;
  busy: boolean;
  onComplete: (id: string) => void;
}) {
  const completed = item.status === "completed" || item.outcome === "completed";
  const position =
    timePosition(item.planned_start_display) ??
    timePosition(item.planned_end_display);
  const style = position
    ? { top: `${position.top}%`, minHeight: `${position.height}%` }
    : undefined;
  return (
    <article
      className={cn(
        "group absolute inset-x-2 z-10 rounded-[20px] border border-black/10 p-3 text-ink shadow-card transition duration-200 hover:-translate-y-0.5 hover:shadow-[0_24px_42px_-20px_rgba(17,17,17,0.42)]",
        item.disposition === "must" ? "bg-zest" : "bg-mint",
        completed && "bg-white/60 text-ink/45 grayscale-[0.25]",
      )}
      style={style}
    >
      <div className="flex items-start justify-between gap-2">
        <div>
          <p className="text-[8px] font-bold uppercase tracking-[0.16em] text-black/45">
            {item.disposition === "must" ? "Must do" : "Should do"} ·{" "}
            {item.planned_est_min} min
          </p>
          <h3 className="mt-1 text-[13px] font-semibold leading-tight tracking-[-0.02em]">
            {item.title}
          </h3>
        </div>
        <CalendarLink url={item.google_calendar_url} title={item.title} />
      </div>
      <div className="mt-2 flex items-center gap-1.5 text-[9px] font-medium text-black/55">
        <Clock size={11} />
        {item.planned_start_display ?? "—"} –{" "}
        {item.planned_end_display ?? "—"}
      </div>
      <div className="mt-2 flex items-center justify-between gap-2">
        <span className="truncate text-[9px] font-medium text-black/45">
          {item.commitment_title ?? "Ad hoc work"}
        </span>
        <button
          type="button"
          onClick={() => onComplete(item.id)}
          disabled={busy || completed}
          aria-label={
            completed
              ? `${item.title} is complete`
              : `Mark ${item.title} complete`
          }
          className={cn(
            "grid h-6 w-6 shrink-0 place-items-center rounded-lg border border-black/20 bg-white/35 text-ink transition hover:bg-white/65",
            completed && "bg-ink text-white",
          )}
        >
          {busy ? <Spinner /> : completed ? <Check size={12} /> : null}
        </button>
      </div>
    </article>
  );
}

function FixedEventCard({ event }: { event: FixedEvent }) {
  const position =
    timePosition(event.starts_at_display) ??
    timePosition(event.ends_at_display);
  const style = position
    ? { top: `${position.top}%`, minHeight: `${position.height}%` }
    : undefined;
  return (
    <article
      className="absolute inset-x-2 z-[9] rounded-[20px] border border-black/10 bg-sky/90 p-3 text-ink shadow-card"
      style={style}
    >
      <p className="text-[8px] font-bold uppercase tracking-[0.16em] text-black/45">
        Fixed event
      </p>
      <h3 className="mt-1 text-[13px] font-semibold leading-tight tracking-[-0.02em]">
        {event.title}
      </h3>
      <p className="mt-2 flex items-center gap-1.5 text-[9px] font-medium text-black/55">
        <Clock size={11} />
        {event.starts_at_display ?? "—"} – {event.ends_at_display ?? "—"}
      </p>
    </article>
  );
}

export function PlanView({
  today,
  pending,
  onComplete,
}: {
  today: TodayPayload | null;
  pending: Record<string, boolean>;
  onComplete: (id: string) => void;
}) {
  if (!today?.has_plan) {
    return (
      <EmptyState
        title="No approved plan yet."
        body="Ask Zasky in Discord to plan the day. Approved MUST and SHOULD items will appear here automatically."
        icon="☀️"
      />
    );
  }

  const days = weekDays(today.date);
  const active = activeDayIndex(today.date);
  const planItems = [...today.must, ...today.should];

  return (
    <section className="pb-5" aria-label="Today's plan">
      <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="text-[9px] font-bold uppercase tracking-[0.18em] text-muted">
            Today’s plan
          </p>
          <h2 className="mt-1 font-display text-3xl font-semibold tracking-[-0.05em]">
            {formatDate(today.date, true)}
          </h2>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {today.battery ? (
            <span className="rounded-full bg-zest px-3 py-1.5 text-[10px] font-bold uppercase tracking-[0.1em]">
              {today.battery} battery
            </span>
          ) : null}
          {today.latest_wake_display ? (
            <span className="rounded-full border border-black/10 bg-white/70 px-3 py-1.5 text-[10px] font-medium text-muted">
              Wake {today.latest_wake_display}
            </span>
          ) : null}
          {today.source ? (
            <span className="rounded-full border border-black/10 bg-white/70 px-3 py-1.5 text-[10px] font-medium text-muted">
              {today.source}
            </span>
          ) : null}
        </div>
      </div>

      <div className="space-y-2.5 md:hidden">
        {[
          ...today.fixed_events.map((event) => ({
            kind: "fixed" as const,
            start: event.starts_at_display ?? "",
            event,
          })),
          ...planItems.map((item) => ({
            kind: "task" as const,
            start: item.planned_start_display ?? "",
            item,
          })),
        ]
          .sort((a, b) => (a.start > b.start ? 1 : -1))
          .map((entry) =>
            entry.kind === "fixed" ? (
              <article
                key={entry.event.id}
                className="rounded-[20px] border border-black/10 bg-sky/90 p-4 text-ink shadow-card"
              >
                <p className="text-[8px] font-bold uppercase tracking-[0.16em] text-black/45">
                  Fixed event
                </p>
                <h3 className="mt-1 text-sm font-semibold">{entry.event.title}</h3>
                <p className="mt-1 text-[10px] text-black/55">
                  {entry.event.starts_at_display ?? "—"} –{" "}
                  {entry.event.ends_at_display ?? "—"}
                </p>
              </article>
            ) : (
              <article
                key={entry.item.id}
                className={cn(
                  "rounded-[20px] border border-black/10 p-4 text-ink shadow-card",
                  entry.item.disposition === "must" ? "bg-zest" : "bg-mint",
                )}
              >
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="text-[8px] font-bold uppercase tracking-[0.16em] text-black/45">
                      {entry.item.disposition} · {entry.item.planned_est_min} min
                    </p>
                    <h3 className="mt-1 text-sm font-semibold">
                      {entry.item.title}
                    </h3>
                    <p className="mt-1 text-[10px] text-black/55">
                      {entry.item.planned_start_display ?? "—"} –{" "}
                      {entry.item.planned_end_display ?? "—"}
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={() => onComplete(entry.item.id)}
                    disabled={
                      Boolean(pending[entry.item.id]) ||
                      entry.item.status === "completed"
                    }
                    className="grid h-8 w-8 place-items-center rounded-lg border border-black/20 bg-white/35"
                    aria-label={`Complete ${entry.item.title}`}
                  >
                    {pending[entry.item.id] ? (
                      <Spinner />
                    ) : entry.item.status === "completed" ? (
                      <Check size={13} />
                    ) : null}
                  </button>
                </div>
              </article>
            ),
          )}
      </div>

      <div className="hidden rounded-panel border border-black/[0.05] bg-white/55 p-3 shadow-card backdrop-blur-sm md:block md:p-4">
        <div className="grid grid-cols-[52px_repeat(5,minmax(0,1fr))] gap-1.5 pb-2">
          <div />
          {days.map((day, index) => (
            <div key={day.date} className="flex flex-col items-center gap-1">
              <span className="text-[9px] font-semibold uppercase tracking-[0.14em] text-muted/70">
                {day.label}
              </span>
              <span
                className={cn(
                  "grid h-9 w-9 place-items-center rounded-xl text-sm font-semibold",
                  index === active
                    ? "bg-ink text-white shadow-card"
                    : "text-ink/30",
                )}
              >
                {day.day}
              </span>
            </div>
          ))}
        </div>

        <div className="relative grid grid-cols-[52px_repeat(5,minmax(0,1fr))] gap-1.5">
          <div className="relative h-[590px]">
            {Array.from({ length: 6 }, (_, index) => {
              const hour = 8 + index * 2;
              return (
                <span
                  key={hour}
                  className="absolute right-1 -translate-y-1/2 text-[9px] font-medium text-muted/60"
                  style={{ top: `${(index / 5) * 100}%` }}
                >
                  {hour}:00
                </span>
              );
            })}
          </div>
          {days.map((day, index) => (
            <div
              key={day.date}
              className={cn(
                "relative h-[590px] overflow-hidden rounded-[16px] bg-white/35 ring-1 ring-inset ring-black/[0.035]",
                index === active && "bg-white/65",
              )}
            >
              {Array.from({ length: 6 }, (_, line) => (
                <div
                  key={line}
                  className="absolute inset-x-0 border-t border-black/[0.055]"
                  style={{ top: `${(line / 5) * 100}%` }}
                />
              ))}
              {index === active ? (
                <>
                  {today.fixed_events.map((event) => (
                    <FixedEventCard key={event.id} event={event} />
                  ))}
                  {planItems.map((item) => (
                    <PlanTaskCard
                      key={item.id}
                      item={item}
                      busy={Boolean(pending[item.id])}
                      onComplete={onComplete}
                    />
                  ))}
                </>
              ) : null}
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
