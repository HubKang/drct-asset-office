export type CollectionRunStatus = "running" | "success" | "failed" | "partial";

export type CollectionRun = {
  id: number;
  collector_name: string;
  target: string | null;
  status: CollectionRunStatus | string;
  started_at: string;
  finished_at: string | null;
  message: string | null;
  created_at: string;
};

export type CollectionRunListParams = {
  collector_name?: string;
  status?: string;
  target?: string;
  limit?: number;
  offset?: number;
};
