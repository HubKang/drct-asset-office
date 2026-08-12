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
