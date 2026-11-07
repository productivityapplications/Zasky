export type Tab = "today" | "tasks" | "reconciliation";
export type TaskFilter = "all" | "active" | "parked" | "completed";

export type DashboardTask = {
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
  google_calendar_url: string | null;
};

export type TodayItem = DashboardTask & {
  disposition: "must" | "should";
  position: number;
  outcome: string | null;
  planned_est_min: number;
  planned_start_utc: string | null;
  planned_end_utc: string | null;
  planned_start_display: string | null;
  planned_end_display: string | null;
};

export type FixedEvent = {
  id: string;
  title: string;
  starts_at_display: string | null;
  ends_at_display: string | null;
};

export type TodayPayload = {
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

export type TasksPayload = {
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

export type Reconciliation = {
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

export type ReconciliationsPayload = {
  timezone: string;
  reconciliations: Reconciliation[];
};

export type Goal = {
  id: string;
  title: string;
  year: number;
  evidence_of_done: string;
  status: string;
};

export type Commitment = {
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

export type GoalsPayload = { goals: Goal[] };
export type CommitmentsPayload = { commitments: Commitment[] };

export type ModalKind = "goal" | "commitment" | "task" | null;

export type DelegateState = {
  task: DashboardTask;
  status: "confirm" | "loading" | "done" | "approving" | "approved" | "error";
  output?: string;
  executionCode?: string;
  error?: string;
  discordDelivered?: boolean;
} | null;

export type ExecutionSections = {
  deliverable: string;
  whatIDid: string;
  checklist: string;
};
