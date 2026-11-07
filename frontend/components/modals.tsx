"use client";

import { useState, type FormEvent, type ReactNode } from "react";

import { cn, localDateString, splitExecutionOutput } from "@/lib/utils";
import type {
  Commitment,
  DelegateState,
  Goal,
} from "@/lib/types";
import { Button, Modal, Spinner } from "@/components/ui";

const inputClass =
  "mt-1.5 h-11 w-full rounded-field border border-black/10 bg-white px-3.5 text-sm text-ink outline-none transition placeholder:text-muted/55 focus:border-ink/30 focus:ring-2 focus:ring-ink/10";

const textareaClass =
  "mt-1.5 min-h-24 w-full rounded-field border border-black/10 bg-white px-3.5 py-3 text-sm text-ink outline-none transition placeholder:text-muted/55 focus:border-ink/30 focus:ring-2 focus:ring-ink/10";

function Field({
  label,
  children,
  full = false,
}: {
  label: string;
  children: ReactNode;
  full?: boolean;
}) {
  return (
    <label className={cn("block", full && "md:col-span-2")}>
      <span className="text-[9px] font-bold uppercase tracking-[0.16em] text-muted">
        {label}
      </span>
      {children}
    </label>
  );
}

function FormError({ message }: { message: string | null }) {
  if (!message) {
    return null;
  }
  return (
    <p className="rounded-xl border border-coral/20 bg-coral/10 px-3 py-2 text-xs text-coral md:col-span-2">
      {message}
    </p>
  );
}

function FormActions({
  submitting,
  submitLabel,
  onClose,
}: {
  submitting: boolean;
  submitLabel: string;
  onClose: () => void;
}) {
  return (
    <div className="flex flex-col-reverse gap-2 pt-2 sm:flex-row sm:justify-end md:col-span-2">
      <Button type="button" variant="secondary" onClick={onClose}>
        Cancel
      </Button>
      <Button type="submit" variant="primary" disabled={submitting}>
        {submitting ? "Saving…" : submitLabel}
      </Button>
    </div>
  );
}

function errorMessage(reason: unknown, fallback: string): string {
  return reason instanceof Error ? reason.message : fallback;
}

export function GoalModal({
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
      const response = await fetch("/api/dashboard/goals", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title,
          year: Number(year),
          evidence_of_done: evidence,
        }),
      });
      const payload = await response.json().catch(() => null);
      if (!response.ok) {
        throw new Error(payload?.detail ?? "Could not save goal.");
      }
      await onSaved();
    } catch (reason) {
      setFormError(errorMessage(reason, "Could not save goal."));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Modal title="New year goal" subtitle="Planning cascade" onClose={onClose}>
      <form className="grid gap-4 md:grid-cols-2" onSubmit={submit}>
        <Field label="Goal title" full>
          <input
            className={inputClass}
            value={title}
            onChange={(event) => setTitle(event.target.value)}
            placeholder="What should be true this year?"
            maxLength={160}
            required
          />
        </Field>
        <Field label="Year">
          <input
            className={inputClass}
            type="number"
            min={2000}
            max={2200}
            value={year}
            onChange={(event) => setYear(event.target.value)}
            required
          />
        </Field>
        <Field label="Evidence of done" full>
          <textarea
            className={textareaClass}
            value={evidence}
            onChange={(event) => setEvidence(event.target.value)}
            placeholder="What artifact or result proves this is complete?"
            rows={4}
            maxLength={1000}
            required
          />
        </Field>
        <FormError message={formError} />
        <FormActions
          submitting={submitting}
          submitLabel="Create goal"
          onClose={onClose}
        />
      </form>
    </Modal>
  );
}

export function CommitmentModal({
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
      const response = await fetch("/api/dashboard/commitments", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title,
          year: Number(year),
          month: Number(month),
          goal_id: goalId || null,
          est_min: Number(estimate),
          deadline_local_date: deadline || null,
          consequence: consequence || null,
          priority,
        }),
      });
      const payload = await response.json().catch(() => null);
      if (!response.ok) {
        throw new Error(payload?.detail ?? "Could not save commitment.");
      }
      await onSaved();
    } catch (reason) {
      setFormError(errorMessage(reason, "Could not save commitment."));
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
      <form className="grid gap-4 md:grid-cols-2" onSubmit={submit}>
        <Field label="Commitment title" full>
          <input
            className={inputClass}
            value={title}
            onChange={(event) => setTitle(event.target.value)}
            placeholder="What concrete outcome belongs to this month?"
            maxLength={200}
            required
          />
        </Field>
        <Field label="Year">
          <input
            className={inputClass}
            type="number"
            min={2000}
            max={2200}
            value={year}
            onChange={(event) => setYear(event.target.value)}
            required
          />
        </Field>
        <Field label="Month">
          <select
            className={inputClass}
            value={month}
            onChange={(event) => setMonth(event.target.value)}
          >
            {Array.from({ length: 12 }, (_, index) => index + 1).map((value) => (
              <option key={value} value={value}>
                {new Intl.DateTimeFormat("en-US", {
                  month: "long",
                  timeZone: "UTC",
                }).format(new Date(Date.UTC(2026, value - 1, 1)))}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Linked goal (optional)">
          <select
            className={inputClass}
            value={goalId}
            onChange={(event) => setGoalId(event.target.value)}
          >
            <option value="">No linked goal</option>
            {goals.map((goal) => (
              <option key={goal.id} value={goal.id}>
                {goal.title} ({goal.year})
              </option>
            ))}
          </select>
        </Field>
        <Field label="Estimate (minutes)">
          <input
            className={inputClass}
            type="number"
            min={1}
            value={estimate}
            onChange={(event) => setEstimate(event.target.value)}
            required
          />
        </Field>
        <Field label="Deadline (optional)">
          <input
            className={inputClass}
            type="date"
            value={deadline}
            onChange={(event) => setDeadline(event.target.value)}
          />
        </Field>
        <Field label="Priority">
          <select
            className={inputClass}
            value={priority}
            onChange={(event) => setPriority(event.target.value)}
          >
            <option value="high">high</option>
            <option value="normal">normal</option>
            <option value="low">low</option>
          </select>
        </Field>
        <Field label="Consequence (optional)" full>
          <textarea
            className={textareaClass}
            value={consequence}
            onChange={(event) => setConsequence(event.target.value)}
            placeholder="What happens if this commitment slips?"
            rows={3}
            maxLength={1000}
          />
        </Field>
        <FormError message={formError} />
        <FormActions
          submitting={submitting}
          submitLabel="Create commitment"
          onClose={onClose}
        />
      </form>
    </Modal>
  );
}

export function TaskModal({
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
      const response = await fetch("/api/dashboard/tasks", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title,
          est_min: Number(estimate),
          scheduled_date: scheduledDate || null,
          commitment_id: commitmentId || null,
        }),
      });
      const payload = await response.json().catch(() => null);
      if (!response.ok) {
        throw new Error(payload?.detail ?? "Could not save task.");
      }
      await onSaved();
    } catch (reason) {
      setFormError(errorMessage(reason, "Could not save task."));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Modal title="Add task to this week" subtitle="Week pool" onClose={onClose}>
      <form className="grid gap-4 md:grid-cols-2" onSubmit={submit}>
        <Field label="Task title" full>
          <input
            className={inputClass}
            value={title}
            onChange={(event) => setTitle(event.target.value)}
            placeholder="What concrete work should enter the week pool?"
            maxLength={200}
            required
          />
        </Field>
        <Field label="Estimate (minutes)">
          <input
            className={inputClass}
            type="number"
            min={1}
            value={estimate}
            onChange={(event) => setEstimate(event.target.value)}
            required
          />
        </Field>
        <Field label="Scheduled date">
          <input
            className={inputClass}
            type="date"
            value={scheduledDate}
            onChange={(event) => setScheduledDate(event.target.value)}
          />
        </Field>
        <Field label="Commitment (optional)" full>
          <select
            className={inputClass}
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
        </Field>
        <FormError message={formError} />
        <FormActions
          submitting={submitting}
          submitLabel="Add to week pool"
          onClose={onClose}
        />
      </form>
    </Modal>
  );
}

export function DelegateModal({
  state,
  onClose,
  onConfirm,
  onApprove,
}: {
  state: NonNullable<DelegateState>;
  onClose: () => void;
  onConfirm: () => void;
  onApprove: () => void;
}) {
  const sections = splitExecutionOutput(state.output ?? "");
  return (
    <Modal
      title="Execution Agent"
      subtitle={state.task.title}
      onClose={onClose}
      wide
    >
      <div className="space-y-4">
        {state.status === "confirm" ? (
          <div className="flex gap-4 rounded-[18px] border border-sky/30 bg-sky/15 p-5">
            <div className="grid h-12 w-12 shrink-0 place-items-center rounded-2xl bg-zest text-xl">
              ⚡
            </div>
            <div>
              <h3 className="font-display text-lg font-semibold tracking-[-0.02em]">
                Confirm delegation
              </h3>
              <p className="mt-1 text-xs leading-relaxed text-muted">
                The Execution Agent can draft copy, write code snippets, outline
                plans and format documents. It cannot browse the web or modify
                the database.
              </p>
              <p className="mt-2 text-[11px] font-medium text-ink/60">
                The output will be posted to <strong>#ai-workspace</strong>.
                Nothing is marked complete until you approve the execution.
              </p>
            </div>
          </div>
        ) : null}

        {state.status === "loading" || state.status === "approving" ? (
          <div className="flex items-center gap-4 rounded-[18px] border border-lavender/30 bg-lavender/15 p-5">
            <Spinner large />
            <div>
              <h3 className="font-display text-lg font-semibold">
                {state.status === "approving"
                  ? "Approving execution…"
                  : "Working on the task…"}
              </h3>
              <p className="mt-1 text-xs text-muted">
                {state.status === "approving"
                  ? "Marking the task complete in Postgres."
                  : "Producing the three-section deliverable. Planning state will not change."}
              </p>
            </div>
          </div>
        ) : null}

        {state.status === "error" ? (
          <div className="rounded-[18px] border border-coral/20 bg-coral/10 p-5">
            <h3 className="font-display text-lg font-semibold text-coral">
              Delegation failed
            </h3>
            <p className="mt-1 text-xs text-ink/70">{state.error}</p>
          </div>
        ) : null}

        {state.status === "approved" ? (
          <div className="rounded-[18px] border border-mint/40 bg-mint/20 p-6 text-center">
            <div className="mx-auto mb-3 grid h-10 w-10 place-items-center rounded-full bg-ink text-white">
              ✓
            </div>
            <h3 className="font-display text-xl font-semibold tracking-[-0.03em]">
              Execution approved
            </h3>
            <p className="mt-1 text-xs text-ink/65">
              <strong>{state.task.title}</strong> is marked complete in
              Postgres.
            </p>
          </div>
        ) : null}

        {state.output ? (
          <div className="space-y-2.5">
            {[
              ["01 · Deliverable", sections.deliverable || "No deliverable returned."],
              ["02 · What I Did", sections.whatIDid || "No activity summary returned."],
              ["03 · Verification Checklist", sections.checklist || "No checklist returned."],
            ].map(([label, value]) => (
              <section
                key={label}
                className="rounded-[18px] border border-black/10 bg-white/75 p-4"
              >
                <p className="text-[9px] font-bold uppercase tracking-[0.16em] text-muted">
                  {label}
                </p>
                <div className="mt-2 whitespace-pre-wrap text-[12px] leading-relaxed text-ink/80">
                  {value}
                </div>
              </section>
            ))}
          </div>
        ) : null}

        {state.status === "done" ? (
          <div className="flex flex-wrap gap-1.5">
            <span className="rounded-full bg-ink/5 px-2.5 py-1 text-[9px] font-bold uppercase tracking-[0.1em] text-ink/55">
              Draft ready
            </span>
            <span className="rounded-full bg-ink/5 px-2.5 py-1 text-[9px] font-bold uppercase tracking-[0.1em] text-ink/55">
              {state.discordDelivered
                ? "Posted to #ai-workspace"
                : "Not posted to #ai-workspace"}
            </span>
            {state.executionCode ? (
              <span className="rounded-full bg-ink/5 px-2.5 py-1 text-[9px] font-bold uppercase tracking-[0.1em] text-ink/55">
                {state.executionCode}
              </span>
            ) : null}
          </div>
        ) : null}
      </div>

      <div className="mt-4 flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
        <Button type="button" variant="secondary" onClick={onClose}>
          Close
        </Button>
        {state.status === "confirm" ? (
          <Button type="button" variant="primary" onClick={onConfirm}>
            Confirm Delegation
          </Button>
        ) : null}
        {state.status === "done" ? (
          <Button
            type="button"
            variant="primary"
            onClick={onApprove}
            className="h-12 px-6 text-[13px]"
          >
            ✅ Approve Execution &amp; Complete Task
          </Button>
        ) : null}
      </div>
    </Modal>
  );
}
