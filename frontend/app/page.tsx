"use client";

import {
  useCallback,
  useEffect,
  useMemo,
  useState,
} from "react";

import { AnalyticsDock } from "@/components/AnalyticsDock";
import { NavigationRail, MobileNav } from "@/components/NavigationRail";
import { PlanView } from "@/components/PlanView";
import { ReconciliationView } from "@/components/ReconciliationView";
import { TaskQueuePanel } from "@/components/TaskQueuePanel";
import { WorkspaceHeader } from "@/components/WorkspaceHeader";
import {
  CommitmentModal,
  DelegateModal,
  GoalModal,
  TaskModal,
} from "@/components/modals";
import { Button, Spinner } from "@/components/ui";
import { fetchJson, formatDate, sendJson } from "@/lib/utils";
import type {
  CommitmentsPayload,
  DashboardTask,
  DelegateState,
  GoalsPayload,
  ModalKind,
  ReconciliationsPayload,
  Tab,
  TaskFilter,
  TasksPayload,
  TodayPayload,
} from "@/lib/types";

export default function DashboardPage() {
  const [tab, setTab] = useState<Tab>("today");
  const [filter, setFilter] = useState<TaskFilter>("all");
  const [today, setToday] = useState<TodayPayload | null>(null);
  const [tasks, setTasks] = useState<TasksPayload | null>(null);
  const [reconciliations, setReconciliations] =
    useState<ReconciliationsPayload | null>(null);
  const [goals, setGoals] = useState<GoalsPayload["goals"]>([]);
  const [commitments, setCommitments] = useState<
    CommitmentsPayload["commitments"]
  >([]);
  const [modal, setModal] = useState<ModalKind>(null);
  const [delegateState, setDelegateState] = useState<DelegateState>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState<Record<string, boolean>>({});
  const [syncedAt, setSyncedAt] = useState<string | null>(null);

  const loadAll = useCallback(async (signal?: AbortSignal) => {
    const [todayPayload, tasksPayload, reconciliationPayload, goalsPayload, commitmentsPayload] =
      await Promise.all([
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
        await sendJson(`/api/dashboard/tasks/${encodeURIComponent(taskId)}/complete`, {});
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

  const openDelegate = useCallback((task: DashboardTask) => {
    setDelegateState({ task, status: "confirm" });
  }, []);

  const runDelegation = useCallback(async (instruction: string) => {
    if (!delegateState) {
      return;
    }
    const task = delegateState.task;
    setDelegateState({ task, status: "loading" });
    try {
      const payload = await sendJson<{
        output: string;
        execution_code?: string;
        discord_delivered?: boolean;
      }>(`/api/dashboard/delegate/${encodeURIComponent(task.id)}`, {
        instruction: instruction.trim() || null,
      });
      setDelegateState({
        task,
        status: "done",
        output: payload.output,
        executionCode: payload.execution_code,
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
  }, [delegateState]);

  const approveDelegation = useCallback(async () => {
    if (!delegateState?.executionCode) {
      return;
    }
    const state = delegateState;
    const executionCode = delegateState.executionCode;
    setDelegateState({ ...state, status: "approving" });
    try {
      await sendJson(
        `/api/dashboard/executions/${encodeURIComponent(executionCode)}/approve`,
        {},
      );
      await loadAll();
      setDelegateState({ ...state, status: "approved" });
    } catch (reason) {
      setDelegateState({
        ...state,
        status: "error",
        error:
          reason instanceof Error
            ? reason.message
            : "Could not approve the execution.",
      });
    }
  }, [delegateState, loadAll]);

  const filteredTasks = useMemo(() => {
    const items = tasks?.tasks ?? [];
    return filter === "all"
      ? items
      : items.filter((task) => task.status === filter);
  }, [filter, tasks]);

  const activeGoals = useMemo(
    () => goals.filter((goal) => goal.status === "active"),
    [goals],
  );
  const activeCommitments = useMemo(
    () => commitments.filter((item) => item.status === "active"),
    [commitments],
  );
  const counts = tasks?.counts ?? {
    active: 0,
    parked: 0,
    completed: 0,
    total: 0,
  };

  return (
    <div className="min-h-screen overflow-hidden bg-canvas p-3 text-ink sm:p-4 lg:p-5 xl:p-6">
      <div className="pointer-events-none fixed inset-0 -z-10 bg-[radial-gradient(circle_at_12%_18%,rgba(242,239,105,0.35),transparent_36%),radial-gradient(circle_at_88%_12%,rgba(199,163,243,0.28),transparent_36%),radial-gradient(circle_at_52%_100%,rgba(142,215,246,0.2),transparent_45%)]" />

      <div className="mx-auto grid min-h-[calc(100vh-24px)] max-w-[1600px] animate-rise grid-cols-1 gap-3 rounded-shell border border-black/5 bg-surface p-3 shadow-shell md:grid-cols-[64px_minmax(0,1fr)] lg:grid-cols-[64px_minmax(0,1fr)_360px] xl:grid-cols-[64px_minmax(0,1fr)_380px] xl:gap-4 xl:p-4">
        <NavigationRail tab={tab} onTab={setTab} />

        <main className="min-w-0 px-0 pb-24 pt-1 sm:px-1 lg:pb-2">
          <div className="mb-4 flex items-center justify-between gap-2 md:hidden">
            <div className="flex items-center gap-2">
              <span className="grid h-9 w-9 place-items-center rounded-2xl bg-ink text-xs font-bold text-white shadow-card">
                Z
              </span>
              <div>
                <p className="text-[9px] font-bold uppercase tracking-[0.16em] text-muted">
                  Owner dashboard
                </p>
                <p className="text-xs font-semibold">Zasky</p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <span className="h-1.5 w-1.5 rounded-full bg-mint" />
              <span className="text-[10px] font-medium text-muted">
                {syncedAt ? `Synced ${syncedAt}` : "Connecting"}
              </span>
            </div>
          </div>

          <WorkspaceHeader
            dateLabel={
              today ? formatDate(today.date, true) : "Today’s workspace"
            }
            subLabel={
              today
                ? `Owner workspace · ${today.timezone}${syncedAt ? ` · synced ${syncedAt}` : ""}`
                : "Owner workspace"
            }
            tab={tab}
            onTab={setTab}
            onGoal={() => setModal("goal")}
            onCommitment={() => setModal("commitment")}
            onTask={() => setModal("task")}
          />

          {error ? (
            <div className="mb-4 flex items-start justify-between gap-4 rounded-2xl border border-coral/20 bg-coral/10 px-4 py-3 text-coral">
              <div>
                <p className="text-xs font-semibold">Dashboard request failed.</p>
                <p className="mt-0.5 text-[11px] text-coral/80">{error}</p>
              </div>
              <button
                type="button"
                onClick={() => setError(null)}
                className="shrink-0 rounded-full border border-coral/30 px-3 py-1 text-[10px] font-semibold"
              >
                Dismiss
              </button>
            </div>
          ) : null}

          {loading ? (
            <div className="grid gap-3">
              <div className="h-56 animate-pulse rounded-panel bg-black/[0.045]" />
              <div className="grid gap-3 md:grid-cols-3">
                <div className="h-32 animate-pulse rounded-panel bg-black/[0.045]" />
                <div className="h-32 animate-pulse rounded-panel bg-black/[0.045]" />
                <div className="h-32 animate-pulse rounded-panel bg-black/[0.045]" />
              </div>
            </div>
          ) : (
            <>
              {tab === "today" ? (
                <PlanView today={today} pending={pending} onComplete={complete} />
              ) : null}
              {tab === "reconciliation" ? (
                <ReconciliationView
                  reconciliations={reconciliations?.reconciliations ?? []}
                />
              ) : null}
              {tab === "tasks" ? (
                <div className="lg:hidden">
                  <TaskQueuePanel
                    tasks={filteredTasks}
                    counts={counts}
                    filter={filter}
                    onFilter={setFilter}
                    pending={pending}
                    onComplete={complete}
                    onDelegate={openDelegate}
                    onAddTask={() => setModal("task")}
                  />
                </div>
              ) : null}

              <AnalyticsDock
                counts={counts}
                tasks={tasks?.tasks ?? []}
              />
            </>
          )}

          <footer className="mt-5 flex flex-col justify-between gap-1 border-t border-black/5 pt-3 text-[9px] text-muted/70 sm:flex-row">
            <span>Zasky · owner-only dashboard</span>
            <span>Neon Postgres · deterministic planning state</span>
          </footer>
        </main>

        <div className="hidden min-h-0 lg:flex">
          <div className="flex min-h-0 w-full flex-col">
            <TaskQueuePanel
              tasks={filteredTasks}
              counts={counts}
              filter={filter}
              onFilter={setFilter}
              pending={pending}
              onComplete={complete}
              onDelegate={openDelegate}
              onAddTask={() => setModal("task")}
            />
            <div className="mt-3 flex items-center justify-between rounded-2xl border border-black/5 bg-white/55 px-3 py-2 text-[9px] text-muted">
              <span>{refreshing ? "Refreshing…" : "Live from Postgres"}</span>
              <Button
                variant="secondary"
                size="sm"
                onClick={() => void refresh()}
                disabled={refreshing}
              >
                {refreshing ? <Spinner /> : null}
                Refresh
              </Button>
            </div>
          </div>
        </div>
      </div>

      <MobileNav tab={tab} onTab={setTab} />

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
          onConfirm={(instruction) => void runDelegation(instruction)}
          onApprove={() => void approveDelegation()}
        />
      ) : null}
    </div>
  );
}
