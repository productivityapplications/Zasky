"use client";

import {
  CalendarDays,
  Check,
  Plus,
  Zap,
} from "lucide-react";

import { cn, formatDate } from "@/lib/utils";
import type { DashboardTask, TaskFilter } from "@/lib/types";
import { EmptyState, Spinner } from "@/components/ui";

const TONES = ["bg-coral", "bg-lavender", "bg-sky", "bg-mint", "bg-zest"];

function TaskCard({
  task,
  index,
  busy,
  onComplete,
  onDelegate,
}: {
  task: DashboardTask;
  index: number;
  busy: boolean;
  onComplete: (id: string) => void;
  onDelegate: (task: DashboardTask) => void;
}) {
  const completed = task.status === "completed";
  const cancelled = task.status === "cancelled";
  const tone = completed || cancelled ? "" : TONES[index % TONES.length];
  return (
    <article
      className={cn(
        "group rounded-[22px] p-4 text-ink shadow-darkcard transition duration-200 hover:-translate-y-0.5 hover:shadow-[0_22px_40px_-20px_rgba(0,0,0,0.75)]",
        tone,
        (completed || cancelled) &&
          "bg-white/[0.08] text-white/55 ring-1 ring-inset ring-white/10",
      )}
    >
      <div className="flex items-center justify-between gap-2 text-[8px] font-bold uppercase tracking-[0.14em]">
        <span className={completed || cancelled ? "text-white/45" : "text-black/50"}>
          {formatDate(task.scheduled_date, false)} · {task.est_min} min
        </span>
        <span
          className={cn(
            "rounded-full px-2 py-0.5",
            completed || cancelled
              ? "bg-white/10 text-white/55"
              : "bg-black/10 text-black/55",
          )}
        >
          {task.status}
        </span>
      </div>

      <h3 className="mt-2 text-[17px] font-semibold leading-tight tracking-[-0.025em]">
        {task.title}
      </h3>
      <div
        className={cn(
          "mt-2 flex flex-wrap items-center gap-1.5 text-[9px] font-medium",
          completed || cancelled ? "text-white/40" : "text-black/55",
        )}
      >
        {task.commitment_title ? <span>{task.commitment_title}</span> : null}
        {task.ad_hoc ? <span>ad hoc</span> : null}
        {task.resume_note_present ? <span>parked note</span> : null}
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-1.5">
        <button
          type="button"
          onClick={() => onComplete(task.id)}
          disabled={busy || completed || cancelled}
          aria-label={completed ? `${task.title} complete` : `Complete ${task.title}`}
          className={cn(
            "grid h-7 w-7 place-items-center rounded-lg border border-black/20 bg-white/35 text-ink transition hover:bg-white/65",
            (completed || cancelled) &&
              "border-white/10 bg-white/10 text-white/60",
          )}
        >
          {busy ? <Spinner /> : completed ? <Check size={12} /> : null}
        </button>
        {task.google_calendar_url ? (
          <a
            href={task.google_calendar_url}
            target="_blank"
            rel="noreferrer"
            aria-label={`Add ${task.title} to Google Calendar`}
            title="Add to Google Calendar"
            className={cn(
              "grid h-7 w-7 place-items-center rounded-full border border-black/10 bg-white/45 text-ink/65 transition hover:bg-white/80",
              (completed || cancelled) &&
                "border-white/10 bg-white/10 text-white/55",
            )}
          >
            <CalendarDays size={12} />
          </a>
        ) : null}
        {!completed && !cancelled ? (
          <button
            type="button"
            onClick={() => onDelegate(task)}
            className="inline-flex items-center gap-1 rounded-full bg-ink px-3 py-1.5 text-[9px] font-bold uppercase tracking-[0.08em] text-white transition hover:bg-ink-soft"
          >
            <Zap size={10} />
            Delegate to AI
          </button>
        ) : null}
      </div>
    </article>
  );
}

export function TaskQueuePanel({
  tasks,
  counts,
  filter,
  onFilter,
  pending,
  onComplete,
  onDelegate,
  onAddTask,
}: {
  tasks: DashboardTask[];
  counts: { active: number; parked: number; completed: number; total: number };
  filter: TaskFilter;
  onFilter: (filter: TaskFilter) => void;
  pending: Record<string, boolean>;
  onComplete: (id: string) => void;
  onDelegate: (task: DashboardTask) => void;
  onAddTask: () => void;
}) {
  const filters: { key: TaskFilter; label: string; count: number }[] = [
    { key: "all", label: "All", count: counts.total },
    { key: "active", label: "Active", count: counts.active },
    { key: "parked", label: "Parked", count: counts.parked },
    { key: "completed", label: "Done", count: counts.completed },
  ];

  return (
    <aside className="flex min-h-0 flex-col rounded-panel bg-ink p-4 text-white shadow-darkcard">
      <div className="flex items-start justify-between gap-3 pb-3">
        <div>
          <p className="text-[9px] font-bold uppercase tracking-[0.16em] text-white/40">
            Owner queue
          </p>
          <h2 className="mt-1 font-display text-2xl font-semibold tracking-[-0.045em]">
            All Tasks
          </h2>
        </div>
        <button
          type="button"
          onClick={onAddTask}
          aria-label="Add task"
          className="grid h-9 w-9 place-items-center rounded-full border border-white/10 bg-white/[0.06] text-white/70 transition hover:bg-white/10 hover:text-white"
        >
          <Plus size={15} />
        </button>
      </div>

      <div className="flex flex-wrap gap-1.5 pb-3">
        {filters.map(({ key, label, count }) => (
          <button
            key={key}
            type="button"
            onClick={() => onFilter(key)}
            className={cn(
              "rounded-full border border-white/10 bg-white/[0.06] px-3 py-1.5 text-[9px] font-semibold text-white/55 transition hover:bg-white/10 hover:text-white",
              filter === key && "border-white bg-white text-ink hover:bg-white hover:text-ink",
            )}
          >
            {label} <span className="opacity-50">{count}</span>
          </button>
        ))}
      </div>

      <div className="min-h-0 flex-1 space-y-2.5 overflow-y-auto pr-1">
        {tasks.length ? (
          tasks.map((task, index) => (
            <TaskCard
              key={task.id}
              task={task}
              index={index}
              busy={Boolean(pending[task.id])}
              onComplete={onComplete}
              onDelegate={onDelegate}
            />
          ))
        ) : (
          <div className="rounded-[20px] border border-white/10 bg-white/[0.04] p-6 text-center">
            <p className="text-sm font-semibold text-white/80">No tasks here.</p>
            <p className="mt-1 text-[11px] leading-relaxed text-white/40">
              Add a task to the week pool or change the filter.
            </p>
          </div>
        )}
      </div>

      <button
        type="button"
        onClick={onAddTask}
        className="mt-3 flex items-center justify-between rounded-2xl border border-white/10 bg-white/[0.04] px-3 py-2.5 text-left transition hover:bg-white/[0.08]"
      >
        <span className="text-[11px] font-semibold text-white/75">
          Add task to this week
        </span>
        <Plus size={14} className="text-white/45" />
      </button>
    </aside>
  );
}
