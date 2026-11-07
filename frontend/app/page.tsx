"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

type Tab = "today" | "tasks" | "reconciliation";
type TaskFilter = "all" | "active" | "parked" | "completed";

type DashboardTask = {
  id: string;
  title: string;
  est_min: number;
  actual_min: number | null;
  scheduled_date: string;
  status: "active" | "parked" | "completed" | "cancelled";
  ad_hoc: boolean;
  resume_note_present: boolean;
  completed_at: string | null;
  week_start: string | null;
  commitment_title: string | null;
};

type TodayItem = DashboardTask & {
  disposition: "must" | "should";
  position: number;
  outcome: string | null;
  planned_est_min: number;
  planned_start_utc: string | null;
  planned_end_utc: string | null;
  planned_start_display: string | null;
  planned_end_display: string | null;
};

type FixedEvent = {
  id: string;
  title: string;
  starts_at_display: string | null;
  ends_at_display: string | null;
};

type TodayPayload = {
  date: string;
  timezone: string;
  has_plan: boolean;
  battery: "low" | "medium" | "high" | null;
  source: string | null;
  latest_wake_display: string | null;
  must: TodayItem[];
  should: TodayItem[];
  fixed_events: FixedEvent[];
};

type TasksPayload = {
  timezone: string;
  counts: {
    active: number;
    parked: number;
    completed: number;
    cancelled: number;
    total: number;
  };
  tasks: DashboardTask[];
};

type Reconciliation = {
  id: string;
  date: string;
  revision: number;
  battery: string;
  approved_at: string | null;
  latest_wake_display: string | null;
  summary: string | null;
  items: Array<
    DashboardTask & {
      disposition: "must" | "should";
      position: number;
      outcome: string | null;
      planned_start_display: string | null;
      planned_end_display: string | null;
    }
  >;
};

type ReconciliationsPayload = {
  timezone: string;
  reconciliations: Reconciliation[];
};

const TAB_LABELS: Record<Tab, string> = {
  today: "Today's Plan",
  tasks: "All Tasks",
  reconciliation: "Reconciliation History",
};

async function fetchJson<T>(path: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(path, { cache: "no-store", signal });
  const payload = await response.json().catch(() => null);
  if (!response.ok) {
    const detail =
      payload && typeof payload.detail === "string"
        ? payload.detail
        : `Request failed (${response.status})`;
    throw new Error(detail);
  }
  return payload as T;
}

function formatDate(value: string, long = true): string {
  const parts = value.split("-").map(Number);
  if (parts.length !== 3 || parts.some(Number.isNaN)) {
    return value;
  }
  const date = new Date(Date.UTC(parts[0], parts[1] - 1, parts[2], 12));
  return new Intl.DateTimeFormat("en-US", {
    weekday: long ? "long" : "short",
    month: long ? "long" : "short",
    day: "numeric",
    timeZone: "UTC",
  }).format(date);
}

function classNames(
  ...values: Array<string | false | null | undefined>
): string {
  return values.filter(Boolean).join(" ");
}

function CheckIcon() {
  return (
    <svg viewBox="0 0 16 16" aria-hidden="true">
      <path
        d="M3.2 8.5 6.4 11.7 12.9 4.6"
        fill="none"
        stroke="currentColor"
        strokeWidth="2.2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function BoltIcon() {
  return (
    <svg viewBox="0 0 20 20" aria-hidden="true">
      <path
        d="M11.2 1.8 4.4 11h4.4l-.9 7.2L15.6 9h-4.4l.9-7.2Z"
        fill="currentColor"
      />
    </svg>
  );
}

function ClockIcon() {
  return (
    <svg viewBox="0 0 20 20" aria-hidden="true">
      <circle
        cx="10"
        cy="10"
        r="7.2"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.6"
      />
      <path
        d="M10 5.8V10l2.8 1.7"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinecap="round"
      />
    </svg>
  );
}

function TaskCheck({
  checked,
  busy,
  disabled,
  onClick,
  label,
}: {
  checked: boolean;
  busy: boolean;
  disabled: boolean;
  onClick: () => void;
  label: string;
}) {
  return (
    <button
      type="button"
      className={classNames("task-check", checked && "is-checked")}
      aria-label={label}
      aria-pressed={checked}
      disabled={disabled || busy}
      onClick={onClick}
    >
      {busy ? <span className="spinner" /> : checked ? <CheckIcon /> : null}
    </button>
  );
}

function StatusPill({ status }: { status: string }) {
  return <span className={`status status-${status}`}>{status}</span>;
}

function TaskRow({
  task,
  busy,
  onComplete,
  showDate = true,
}: {
  task: DashboardTask;
  busy: boolean;
  onComplete: (id: string) => void;
  showDate?: boolean;
}) {
  const completed = task.status === "completed";
  return (
    <article className={classNames("task-row", completed && "is-completed")}>
      <TaskCheck
        checked={completed}
        busy={busy}
        disabled={completed || task.status === "cancelled"}
        label={
          completed
            ? `${task.title} is already complete`
            : `Mark ${task.title} complete`
        }
        onClick={() => onComplete(task.id)}
      />
      <div className="task-main">
        <div className="task-title-line">
          <h3>{task.title}</h3>
          <StatusPill status={task.status} />
        </div>
        <div className="task-meta">
          {showDate ? <span>{formatDate(task.scheduled_date, false)}</span> : null}
          <span>{task.est_min} min</span>
          {task.commitment_title ? (
            <span className="task-commitment">{task.commitment_title}</span>
          ) : null}
          {task.ad_hoc ? <span>ad hoc</span> : null}
          {task.resume_note_present ? <span>parked note</span> : null}
        </div>
      </div>
    </article>
  );
}

function PlanItem({
  item,
  busy,
  onComplete,
}: {
  item: TodayItem;
  busy: boolean;
  onComplete: (id: string) => void;
}) {
  const completed = item.status === "completed" || item.outcome === "completed";
  return (
    <article className={classNames("plan-item", completed && "is-completed")}>
      <div className="plan-index">{item.position}</div>
      <div className="plan-body">
        <div className="task-title-line">
          <h3>{item.title}</h3>
          <StatusPill status={completed ? "completed" : item.status} />
        </div>
        <div className="plan-time">
          <ClockIcon />
          <span>
            {item.planned_start_display ?? "—"} –{" "}
            {item.planned_end_display ?? "—"}
          </span>
          <span className="dot-divider" />
          <span>{item.planned_est_min} min</span>
          {item.commitment_title ? (
            <>
              <span className="dot-divider" />
              <span>{item.commitment_title}</span>
            </>
          ) : null}
        </div>
      </div>
      <TaskCheck
        checked={completed}
        busy={busy}
        disabled={completed}
        label={
          completed ? `${item.title} is already complete` : `Mark ${item.title} complete`
        }
        onClick={() => onComplete(item.id)}
      />
    </article>
  );
}

function EmptyState({
  title,
  body,
}: {
  title: string;
  body: string;
}) {
  return (
    <div className="empty-state">
      <div className="empty-orbit" aria-hidden="true">
        <span />
      </div>
      <h3>{title}</h3>
      <p>{body}</p>
    </div>
  );
}

function LoadingState() {
  return (
    <div className="loading-grid" aria-label="Loading dashboard">
      <div className="skeleton skeleton-hero" />
      <div className="skeleton" />
      <div className="skeleton" />
      <div className="skeleton" />
    </div>
  );
}

export default function DashboardPage() {
  const [tab, setTab] = useState<Tab>("today");
  const [filter, setFilter] = useState<TaskFilter>("all");
  const [today, setToday] = useState<TodayPayload | null>(null);
  const [tasks, setTasks] = useState<TasksPayload | null>(null);
  const [reconciliations, setReconciliations] =
    useState<ReconciliationsPayload | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState<Record<string, boolean>>({});
  const [syncedAt, setSyncedAt] = useState<string | null>(null);

  const loadAll = useCallback(async (signal?: AbortSignal) => {
    const [todayPayload, tasksPayload, reconciliationPayload] = await Promise.all([
      fetchJson<TodayPayload>("/api/dashboard/today", signal),
      fetchJson<TasksPayload>("/api/dashboard/tasks", signal),
      fetchJson<ReconciliationsPayload>(
        "/api/dashboard/reconciliations",
        signal,
      ),
    ]);
    setToday(todayPayload);
    setTasks(tasksPayload);
    setReconciliations(reconciliationPayload);
    setSyncedAt(
      new Intl.DateTimeFormat("en-US", {
        hour: "numeric",
        minute: "2-digit",
      }).format(new Date()),
    );
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    loadAll(controller.signal)
      .catch((reason: unknown) => {
        if (reason instanceof DOMException && reason.name === "AbortError") {
          return;
        }
        setError(reason instanceof Error ? reason.message : "Could not load data.");
      })
      .finally(() => setLoading(false));
    return () => controller.abort();
  }, [loadAll]);

  const refresh = useCallback(async () => {
    setRefreshing(true);
    try {
      await loadAll();
      setError(null);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not refresh.");
    } finally {
      setRefreshing(false);
    }
  }, [loadAll]);

  const complete = useCallback(
    async (taskId: string) => {
      setPending((current) => ({ ...current, [taskId]: true }));
      try {
        const response = await fetch(
          `/api/dashboard/tasks/${encodeURIComponent(taskId)}/complete`,
          {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: "{}",
          },
        );
        const payload = await response.json().catch(() => null);
        if (!response.ok) {
          throw new Error(
            payload && typeof payload.detail === "string"
              ? payload.detail
              : `Could not complete task (${response.status})`,
          );
        }
        await loadAll();
        setError(null);
      } catch (reason) {
        setError(
          reason instanceof Error ? reason.message : "Could not complete task.",
        );
      } finally {
        setPending((current) => {
          const next = { ...current };
          delete next[taskId];
          return next;
        });
      }
    },
    [loadAll],
  );

  const filteredTasks = useMemo(() => {
    const items = tasks?.tasks ?? [];
    if (filter === "all") {
      return items;
    }
    return items.filter((task) => task.status === filter);
  }, [filter, tasks]);

  const planCount = (today?.must.length ?? 0) + (today?.should.length ?? 0);

  return (
    <div className="page">
      <div className="ambient ambient-one" aria-hidden="true" />
      <div className="ambient ambient-two" aria-hidden="true" />
      <main className="shell">
        <header className="topbar">
          <div className="brand">
            <div className="brand-mark">
              <BoltIcon />
            </div>
            <div>
              <p className="eyebrow">Owner dashboard</p>
              <h1>Zasky</h1>
            </div>
          </div>
          <div className="topbar-right">
            <div className="sync-pill">
              <span className="live-dot" />
              {loading ? "Connecting" : syncedAt ? `Synced ${syncedAt}` : "Connected"}
            </div>
            <button
              type="button"
              className="refresh-button"
              onClick={() => void refresh()}
              disabled={refreshing}
            >
              {refreshing ? "Refreshing…" : "Refresh"}
            </button>
          </div>
        </header>

        <section className="hero">
          <div className="hero-copy">
            <p className="eyebrow">Live from Postgres</p>
            <h2>A calm view of what matters next.</h2>
            <p>
              Today&apos;s plan, the full task pool and every recovery decision in
              one place. No streaks, no noise.
            </p>
          </div>
          <div className="hero-stats">
            <div>
              <span className="stat-value">{tasks?.counts.active ?? "—"}</span>
              <span className="stat-label">active</span>
            </div>
            <div>
              <span className="stat-value">{tasks?.counts.completed ?? "—"}</span>
              <span className="stat-label">completed</span>
            </div>
            <div>
              <span className="stat-value">
                {reconciliations?.reconciliations.length ?? "—"}
              </span>
              <span className="stat-label">recoveries</span>
            </div>
          </div>
        </section>

        <nav className="tabs" aria-label="Dashboard views">
          {(Object.keys(TAB_LABELS) as Tab[]).map((key) => (
            <button
              key={key}
              type="button"
              className={classNames("tab", tab === key && "is-active")}
              onClick={() => setTab(key)}
            >
              {TAB_LABELS[key]}
              {key === "today" && planCount > 0 ? (
                <span className="tab-count">{planCount}</span>
              ) : null}
              {key === "tasks" && tasks ? (
                <span className="tab-count">{tasks.counts.active}</span>
              ) : null}
            </button>
          ))}
        </nav>

        {error ? (
          <div className="error-banner" role="alert">
            <div>
              <strong>Dashboard request failed.</strong>
              <span>{error}</span>
            </div>
            <button type="button" onClick={() => setError(null)}>
              Dismiss
            </button>
          </div>
        ) : null}

        {loading ? (
          <LoadingState />
        ) : (
          <>
            {tab === "today" ? (
              <section className="view" aria-label="Today's plan">
                <div className="view-heading">
                  <div>
                    <p className="eyebrow">Today&apos;s Plan</p>
                    <h2>{today ? formatDate(today.date) : "Today"}</h2>
                  </div>
                  {today ? (
                    <div className="heading-badges">
                      {today.battery ? (
                        <span className={`battery battery-${today.battery}`}>
                          <BoltIcon />
                          {today.battery} battery
                        </span>
                      ) : null}
                      {today.latest_wake_display ? (
                        <span className="meta-pill">
                          Latest wake {today.latest_wake_display}
                        </span>
                      ) : null}
                      {today.source ? (
                        <span className="meta-pill">{today.source}</span>
                      ) : null}
                    </div>
                  ) : null}
                </div>

                {!today?.has_plan ? (
                  <EmptyState
                    title="No approved plan for today."
                    body="Ask Zasky in Discord to plan the day. Approved MUST and SHOULD items will appear here automatically."
                  />
                ) : (
                  <div className="today-grid">
                    <div className="plan-column">
                      <section className="panel">
                        <div className="panel-heading">
                          <span className="section-kicker must-kicker">Must do</span>
                          <span className="section-rule" />
                          <span className="section-count">1 protected</span>
                        </div>
                        {today.must.length ? (
                          <div className="plan-list">
                            {today.must.map((item) => (
                              <PlanItem
                                key={item.id}
                                item={item}
                                busy={Boolean(pending[item.id])}
                                onComplete={(id) => void complete(id)}
                              />
                            ))}
                          </div>
                        ) : (
                          <p className="panel-empty">No must item selected.</p>
                        )}
                      </section>

                      <section className="panel">
                        <div className="panel-heading">
                          <span className="section-kicker">Should do</span>
                          <span className="section-rule" />
                          <span className="section-count">
                            {today.should.length} optional
                          </span>
                        </div>
                        {today.should.length ? (
                          <div className="plan-list">
                            {today.should.map((item) => (
                              <PlanItem
                                key={item.id}
                                item={item}
                                busy={Boolean(pending[item.id])}
                                onComplete={(id) => void complete(id)}
                              />
                            ))}
                          </div>
                        ) : (
                          <p className="panel-empty">
                            Nothing else placed. Slack is protected.
                          </p>
                        )}
                      </section>
                    </div>

                    <aside className="side-column">
                      <section className="panel fixed-panel">
                        <div className="panel-heading">
                          <span className="section-kicker">Fixed events</span>
                        </div>
                        {today.fixed_events.length ? (
                          <div className="fixed-list">
                            {today.fixed_events.map((event) => (
                              <div key={event.id} className="fixed-event">
                                <span className="fixed-dot" />
                                <div>
                                  <h3>{event.title}</h3>
                                  <p>
                                    {event.starts_at_display ?? "—"} –{" "}
                                    {event.ends_at_display ?? "—"}
                                  </p>
                                </div>
                              </div>
                            ))}
                          </div>
                        ) : (
                          <p className="panel-empty">No fixed events today.</p>
                        )}
                      </section>
                      <section className="panel note-panel">
                        <p className="eyebrow">Planning rule</p>
                        <h3>One must. Three max. Slack protected.</h3>
                        <p>
                          Completing a task here writes the same owner-approved
                          state change to Postgres that Zasky uses in Discord.
                        </p>
                      </section>
                    </aside>
                  </div>
                )}
              </section>
            ) : null}

            {tab === "tasks" ? (
              <section className="view" aria-label="All tasks">
                <div className="view-heading">
                  <div>
                    <p className="eyebrow">Task pool</p>
                    <h2>All Tasks</h2>
                  </div>
                  <span className="meta-pill">
                    {tasks?.counts.total ?? 0} total
                  </span>
                </div>

                <div className="filter-row" role="group" aria-label="Filter tasks">
                  {(["all", "active", "parked", "completed"] as TaskFilter[]).map(
                    (key) => (
                      <button
                        key={key}
                        type="button"
                        className={classNames(
                          "filter-chip",
                          filter === key && "is-active",
                        )}
                        onClick={() => setFilter(key)}
                      >
                        {key === "all" ? "All" : key}
                        {tasks ? (
                          <span>
                            {key === "all"
                              ? tasks.counts.total
                              : tasks.counts[key]}
                          </span>
                        ) : null}
                      </button>
                    ),
                  )}
                </div>

                {filteredTasks.length ? (
                  <div className="task-list">
                    {filteredTasks.map((task) => (
                      <TaskRow
                        key={task.id}
                        task={task}
                        busy={Boolean(pending[task.id])}
                        onComplete={(id) => void complete(id)}
                      />
                    ))}
                  </div>
                ) : (
                  <EmptyState
                    title="No tasks in this view."
                    body="Tasks placed in the week pool will show up here with their commitment and estimate."
                  />
                )}
              </section>
            ) : null}

            {tab === "reconciliation" ? (
              <section className="view" aria-label="Reconciliation history">
                <div className="view-heading">
                  <div>
                    <p className="eyebrow">Recovery trail</p>
                    <h2>Reconciliation History</h2>
                  </div>
                  <span className="meta-pill">
                    {reconciliations?.reconciliations.length ?? 0} plans
                  </span>
                </div>

                {reconciliations?.reconciliations.length ? (
                  <div className="timeline">
                    {reconciliations.reconciliations.map((entry) => (
                      <article key={entry.id} className="timeline-card">
                        <div className="timeline-marker" aria-hidden="true" />
                        <div className="timeline-head">
                          <div>
                            <p className="timeline-date">
                              {formatDate(entry.date)}
                            </p>
                            <h3>
                              Recovery plan · revision {entry.revision}
                            </h3>
                          </div>
                          <span className={`battery battery-${entry.battery}`}>
                            <BoltIcon />
                            {entry.battery}
                          </span>
                        </div>
                        <p className="timeline-summary">
                          {entry.summary ??
                            "Recovery plan approved. Kept work today and moved or dropped what no longer fit."}
                        </p>
                        {entry.latest_wake_display ? (
                          <p className="timeline-wake">
                            Latest wake {entry.latest_wake_display}
                          </p>
                        ) : null}
                        <div className="timeline-items">
                          {entry.items.map((item) => (
                            <div key={item.id} className="timeline-item">
                              <span
                                className={classNames(
                                  "mini-badge",
                                  item.disposition === "must"
                                    ? "mini-must"
                                    : "mini-should",
                                )}
                              >
                                {item.disposition}
                              </span>
                              <span className="timeline-item-title">
                                {item.title}
                              </span>
                              <span className="timeline-item-time">
                                {item.planned_start_display ?? "—"} –{" "}
                                {item.planned_end_display ?? "—"}
                              </span>
                            </div>
                          ))}
                        </div>
                      </article>
                    ))}
                  </div>
                ) : (
                  <EmptyState
                    title="No reconciliation history yet."
                    body="When a disrupted day is recovered, Zasky records the approved recovery plan here."
                  />
                )}
              </section>
            ) : null}
          </>
        )}

        <footer className="footer">
          <span>Zasky · owner-only dashboard</span>
          <span>Neon Postgres · deterministic planning state</span>
        </footer>
      </main>
    </div>
  );
}
