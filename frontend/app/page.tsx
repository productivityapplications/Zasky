"use client";

import {
  type FormEvent,
  useCallback,
  useEffect,
  useMemo,
  useState,
} from "react";

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

type Goal = {
  id: string;
  title: string;
  year: number;
  evidence_of_done: string;
  status: string;
};

type Commitment = {
  id: string;
  title: string;
  year: number;
  month: number;
  goal_id: string | null;
  goal_title: string | null;
  est_total_min: number;
  deadline_local_date: string | null;
  priority: string;
  status: string;
};

type GoalsPayload = { goals: Goal[] };
type CommitmentsPayload = { commitments: Commitment[] };

type ModalKind = "goal" | "commitment" | "task" | null;

type DelegateState = {
  task: DashboardTask;
  status: "loading" | "done" | "error";
  output?: string;
  error?: string;
  discordDelivered?: boolean;
} | null;

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

async function sendJson<T>(path: string, body: unknown): Promise<T> {
  const response = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
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

function localDateString(): string {
  const now = new Date();
  const month = String(now.getMonth() + 1).padStart(2, "0");
  const day = String(now.getDate()).padStart(2, "0");
  return `${now.getFullYear()}-${month}-${day}`;
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

function Modal({
  title,
  subtitle,
  onClose,
  children,
  wide = false,
}: {
  title: string;
  subtitle?: string;
  onClose: () => void;
  children: React.ReactNode;
  wide?: boolean;
}) {
  return (
    <div
      className="modal-backdrop"
      role="presentation"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) {
          onClose();
        }
      }}
    >
      <div
        className={classNames("modal-card", wide && "is-wide")}
        role="dialog"
        aria-modal="true"
        aria-label={title}
      >
        <div className="modal-head">
          <div>
            <p className="eyebrow">{subtitle ?? "Owner action"}</p>
            <h2>{title}</h2>
          </div>
          <button type="button" className="modal-close" onClick={onClose}>
            Close
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}

function FormError({ message }: { message: string | null }) {
  if (!message) {
    return null;
  }
  return <p className="form-error">{message}</p>;
}

function GoalModal({
  onClose,
  onSaved,
}: {
  onClose: () => void;
  onSaved: () => Promise<void>;
}) {
  const [title, setTitle] = useState("");
  const [year, setYear] = useState(String(new Date().getFullYear()));
  const [evidence, setEvidence] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    setFormError(null);
    try {
      await sendJson("/api/dashboard/goals", {
        title,
        year: Number(year),
        evidence_of_done: evidence,
      });
      await onSaved();
    } catch (reason) {
      setFormError(reason instanceof Error ? reason.message : "Could not save goal.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Modal
      title="New year goal"
      subtitle="Planning cascade"
      onClose={onClose}
    >
      <form className="form-grid" onSubmit={submit}>
        <label className="field field-full">
          <span>Goal title</span>
          <input
            value={title}
            onChange={(event) => setTitle(event.target.value)}
            placeholder="What should be true this year?"
            maxLength={160}
            required
          />
        </label>
        <label className="field">
          <span>Year</span>
          <input
            type="number"
            min={2000}
            max={2200}
            value={year}
            onChange={(event) => setYear(event.target.value)}
            required
          />
        </label>
        <label className="field field-full">
          <span>Evidence of done</span>
          <textarea
            value={evidence}
            onChange={(event) => setEvidence(event.target.value)}
            placeholder="What artifact or result proves this is complete?"
            rows={4}
            maxLength={1000}
            required
          />
        </label>
        <FormError message={formError} />
        <div className="form-actions">
          <button type="button" className="ghost-button" onClick={onClose}>
            Cancel
          </button>
          <button type="submit" className="primary-button" disabled={submitting}>
            {submitting ? "Saving…" : "Create goal"}
          </button>
        </div>
      </form>
    </Modal>
  );
}

function CommitmentModal({
  goals,
  onClose,
  onSaved,
}: {
  goals: Goal[];
  onClose: () => void;
  onSaved: () => Promise<void>;
}) {
  const now = new Date();
  const [title, setTitle] = useState("");
  const [year, setYear] = useState(String(now.getFullYear()));
  const [month, setMonth] = useState(String(now.getMonth() + 1));
  const [goalId, setGoalId] = useState(goals[0]?.id ?? "");
  const [estimate, setEstimate] = useState("120");
  const [deadline, setDeadline] = useState("");
  const [consequence, setConsequence] = useState("");
  const [priority, setPriority] = useState("normal");
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    setFormError(null);
    try {
      await sendJson("/api/dashboard/commitments", {
        title,
        year: Number(year),
        month: Number(month),
        goal_id: goalId || null,
        est_min: Number(estimate),
        deadline_local_date: deadline || null,
        consequence: consequence || null,
        priority,
      });
      await onSaved();
    } catch (reason) {
      setFormError(
        reason instanceof Error ? reason.message : "Could not save commitment.",
      );
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Modal
      title="New month commitment"
      subtitle="Planning cascade"
      onClose={onClose}
      wide
    >
      <form className="form-grid" onSubmit={submit}>
        <label className="field field-full">
          <span>Commitment title</span>
          <input
            value={title}
            onChange={(event) => setTitle(event.target.value)}
            placeholder="What concrete outcome belongs to this month?"
            maxLength={200}
            required
          />
        </label>
        <label className="field">
          <span>Year</span>
          <input
            type="number"
            min={2000}
            max={2200}
            value={year}
            onChange={(event) => setYear(event.target.value)}
            required
          />
        </label>
        <label className="field">
          <span>Month</span>
          <select value={month} onChange={(event) => setMonth(event.target.value)}>
            {Array.from({ length: 12 }, (_, index) => index + 1).map((value) => (
              <option key={value} value={value}>
                {new Intl.DateTimeFormat("en-US", {
                  month: "long",
                  timeZone: "UTC",
                }).format(new Date(Date.UTC(2026, value - 1, 1)))}
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          <span>Linked goal (optional)</span>
          <select value={goalId} onChange={(event) => setGoalId(event.target.value)}>
            <option value="">No linked goal</option>
            {goals.map((goal) => (
              <option key={goal.id} value={goal.id}>
                {goal.title} ({goal.year})
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          <span>Estimate (minutes)</span>
          <input
            type="number"
            min={1}
            value={estimate}
            onChange={(event) => setEstimate(event.target.value)}
            required
          />
        </label>
        <label className="field">
          <span>Deadline (optional)</span>
          <input
            type="date"
            value={deadline}
            onChange={(event) => setDeadline(event.target.value)}
          />
        </label>
        <label className="field">
          <span>Priority</span>
          <select value={priority} onChange={(event) => setPriority(event.target.value)}>
            <option value="high">high</option>
            <option value="normal">normal</option>
            <option value="low">low</option>
          </select>
        </label>
        <label className="field field-full">
          <span>Consequence (optional)</span>
          <textarea
            value={consequence}
            onChange={(event) => setConsequence(event.target.value)}
            placeholder="What happens if this commitment slips?"
            rows={3}
            maxLength={1000}
          />
        </label>
        <FormError message={formError} />
        <div className="form-actions">
          <button type="button" className="ghost-button" onClick={onClose}>
            Cancel
          </button>
          <button type="submit" className="primary-button" disabled={submitting}>
            {submitting ? "Saving…" : "Create commitment"}
          </button>
        </div>
      </form>
    </Modal>
  );
}

function TaskModal({
  commitments,
  onClose,
  onSaved,
}: {
  commitments: Commitment[];
  onClose: () => void;
  onSaved: () => Promise<void>;
}) {
  const [title, setTitle] = useState("");
  const [estimate, setEstimate] = useState("45");
  const [scheduledDate, setScheduledDate] = useState(localDateString());
  const [commitmentId, setCommitmentId] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    setFormError(null);
    try {
      await sendJson("/api/dashboard/tasks", {
        title,
        est_min: Number(estimate),
        scheduled_date: scheduledDate || null,
        commitment_id: commitmentId || null,
      });
      await onSaved();
    } catch (reason) {
      setFormError(reason instanceof Error ? reason.message : "Could not save task.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Modal title="Add task to this week" subtitle="Week pool" onClose={onClose}>
      <form className="form-grid" onSubmit={submit}>
        <label className="field field-full">
          <span>Task title</span>
          <input
            value={title}
            onChange={(event) => setTitle(event.target.value)}
            placeholder="What concrete work should enter the week pool?"
            maxLength={200}
            required
          />
        </label>
        <label className="field">
          <span>Estimate (minutes)</span>
          <input
            type="number"
            min={1}
            value={estimate}
            onChange={(event) => setEstimate(event.target.value)}
            required
          />
        </label>
        <label className="field">
          <span>Scheduled date</span>
          <input
            type="date"
            value={scheduledDate}
            onChange={(event) => setScheduledDate(event.target.value)}
          />
        </label>
        <label className="field field-full">
          <span>Commitment (optional)</span>
          <select
            value={commitmentId}
            onChange={(event) => setCommitmentId(event.target.value)}
          >
            <option value="">Ad hoc task (no commitment)</option>
            {commitments.map((commitment) => (
              <option key={commitment.id} value={commitment.id}>
                {commitment.title}
              </option>
            ))}
          </select>
        </label>
        <FormError message={formError} />
        <div className="form-actions">
          <button type="button" className="ghost-button" onClick={onClose}>
            Cancel
          </button>
          <button type="submit" className="primary-button" disabled={submitting}>
            {submitting ? "Adding…" : "Add to week pool"}
          </button>
        </div>
      </form>
    </Modal>
  );
}

function TaskRow({
  task,
  busy,
  onComplete,
  onDelegate,
  showDate = true,
}: {
  task: DashboardTask;
  busy: boolean;
  onComplete: (id: string) => void;
  onDelegate?: (task: DashboardTask) => void;
  showDate?: boolean;
}) {
  const completed = task.status === "completed";
  const delegatable =
    Boolean(onDelegate) && !completed && task.status !== "cancelled";
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
          <div className="task-side">
            <StatusPill status={task.status} />
            {delegatable ? (
              <button
                type="button"
                className="delegate-button"
                onClick={() => onDelegate?.(task)}
              >
                ⚡ Delegate to AI
              </button>
            ) : null}
          </div>
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

function DelegateModal({
  state,
  onClose,
}: {
  state: NonNullable<DelegateState>;
  onClose: () => void;
}) {
  return (
    <Modal
      title="Execution Sub-Agent"
      subtitle={state.task.title}
      onClose={onClose}
      wide
    >
      <div className="delegate-body">
        {state.status === "loading" ? (
          <div className="delegate-loading">
            <span className="spinner spinner-large" />
            <div>
              <h3>Working on the task…</h3>
              <p>
                The sub-agent is producing a draft from the task and its
                commitment. Planning state will not change.
              </p>
            </div>
          </div>
        ) : null}
        {state.status === "error" ? (
          <div className="delegate-error">
            <h3>Delegation failed</h3>
            <p>{state.error}</p>
          </div>
        ) : null}
        {state.status === "done" ? (
          <>
            <div className="delegate-meta">
              <span className="meta-pill">Draft ready</span>
              <span className="meta-pill">
                {state.discordDelivered
                  ? "Also posted to #ai-workspace"
                  : "Not posted to #ai-workspace"}
              </span>
            </div>
            <pre className="delegate-output">{state.output}</pre>
          </>
        ) : null}
      </div>
      <div className="form-actions">
        <button type="button" className="ghost-button" onClick={onClose}>
          Close
        </button>
      </div>
    </Modal>
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
  const [goals, setGoals] = useState<Goal[]>([]);
  const [commitments, setCommitments] = useState<Commitment[]>([]);
  const [modal, setModal] = useState<ModalKind>(null);
  const [delegateState, setDelegateState] = useState<DelegateState>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState<Record<string, boolean>>({});
  const [syncedAt, setSyncedAt] = useState<string | null>(null);

  const loadAll = useCallback(async (signal?: AbortSignal) => {
    const [
      todayPayload,
      tasksPayload,
      reconciliationPayload,
      goalsPayload,
      commitmentsPayload,
    ] = await Promise.all([
      fetchJson<TodayPayload>("/api/dashboard/today", signal),
      fetchJson<TasksPayload>("/api/dashboard/tasks", signal),
      fetchJson<ReconciliationsPayload>(
        "/api/dashboard/reconciliations",
        signal,
      ),
      fetchJson<GoalsPayload>("/api/dashboard/goals", signal),
      fetchJson<CommitmentsPayload>("/api/dashboard/commitments", signal),
    ]);
    setToday(todayPayload);
    setTasks(tasksPayload);
    setReconciliations(reconciliationPayload);
    setGoals(goalsPayload.goals);
    setCommitments(commitmentsPayload.commitments);
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

  const activeGoals = useMemo(
    () => goals.filter((goal) => goal.status === "active"),
    [goals],
  );
  const activeCommitments = useMemo(
    () => commitments.filter((item) => item.status === "active"),
    [commitments],
  );

  const delegate = useCallback(async (task: DashboardTask) => {
    setDelegateState({ task, status: "loading" });
    try {
      const payload = await sendJson<{
        output: string;
        discord_delivered?: boolean;
      }>(`/api/dashboard/delegate/${encodeURIComponent(task.id)}`, {});
      setDelegateState({
        task,
        status: "done",
        output: payload.output,
        discordDelivered: Boolean(payload.discord_delivered),
      });
    } catch (reason) {
      setDelegateState({
        task,
        status: "error",
        error:
          reason instanceof Error
            ? reason.message
            : "The execution sub-agent failed.",
      });
    }
  }, []);

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

        <section className="action-strip" aria-label="Planning actions">
          <div>
            <p className="eyebrow">Build the cascade</p>
            <span>Name the outcome, then the work. Zasky keeps the arithmetic.</span>
          </div>
          <div className="action-buttons">
            <button
              type="button"
              className="ghost-button"
              onClick={() => setModal("goal")}
            >
              + New Goal
            </button>
            <button
              type="button"
              className="ghost-button"
              onClick={() => setModal("commitment")}
            >
              + New Commitment
            </button>
            <button
              type="button"
              className="primary-button"
              onClick={() => setModal("task")}
            >
              + Add Task
            </button>
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
                  <div className="heading-actions">
                    <span className="meta-pill">
                      {tasks?.counts.total ?? 0} total
                    </span>
                    <button
                      type="button"
                      className="primary-button"
                      onClick={() => setModal("task")}
                    >
                      + Add Task
                    </button>
                  </div>
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
                        onDelegate={(selected) => void delegate(selected)}
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

        {modal === "goal" ? (
          <GoalModal
            onClose={() => setModal(null)}
            onSaved={async () => {
              setModal(null);
              await refresh();
            }}
          />
        ) : null}
        {modal === "commitment" ? (
          <CommitmentModal
            goals={activeGoals}
            onClose={() => setModal(null)}
            onSaved={async () => {
              setModal(null);
              await refresh();
            }}
          />
        ) : null}
        {modal === "task" ? (
          <TaskModal
            commitments={activeCommitments}
            onClose={() => setModal(null)}
            onSaved={async () => {
              setModal(null);
              await refresh();
            }}
          />
        ) : null}
        {delegateState ? (
          <DelegateModal
            state={delegateState}
            onClose={() => setDelegateState(null)}
          />
        ) : null}

        <footer className="footer">
          <span>Zasky · owner-only dashboard</span>
          <span>Neon Postgres · deterministic planning state</span>
        </footer>
      </main>
    </div>
  );
}
