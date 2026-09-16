export type DashboardActivityType =
  | "TRAINING_COMPLETED"
  | "TRADE_JOURNAL"
  | "CHART_MARKER"
  | "OBSERVATION_CALCULATION"
  | "OBSERVATION_VALIDATION";

export type DashboardActivity = {
  type: DashboardActivityType;
  event_at: string;
  title: string;
  summary: string;
  route: string;
};

export type DashboardRecentActivitiesResponse = {
  period_start: string;
  period_end: string;
  items: DashboardActivity[];
};

export type DashboardReadinessResponse = {
  theme: {
    data_date: string | null;
    last_success_at: string | null;
    linked_stock_count: number;
    run_status: string | null;
  };
  market: {
    data_date: string | null;
    last_run_at: string | null;
    active_indicator_count: number;
    run_status: string | null;
  };
};
