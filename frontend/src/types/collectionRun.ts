export type CollectionRunStatus = "running" | "success" | "failed" | "partial";

export type CollectionRun = {
  id: number;
  collector_name: string;
  collector_display_name?: string | null;
  run_type?: string | null;
  run_type_label?: string | null;
  collector_group?: string | null;
  collector_group_label?: string | null;
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

export type CollectionRunListResponse = {
  items: CollectionRun[];
  total_count: number;
  limit: number;
  offset: number;
};

export type CollectionRunCleanupPreviewResponse = {
  success: boolean;
  cutoff_date: string;
  target_count: number;
  message: string;
};

export type CollectionRunCleanupResponse = {
  success: boolean;
  cutoff_date: string;
  deleted_count: number;
  message: string;
};
