export type StockSyncRequest = {
  markets: string[];
  dry_run: boolean;
  deactivate_missing: boolean;
  include_security_types: string[];
  mode?: "upsert" | "rebuild";
};

export type StockSyncResponse = {
  markets: string[];
  dry_run: boolean;
  mode: "upsert" | "rebuild";
  rebuild_strategy?: string | null;
  raw_fetched_count: number;
  eligible_count: number;
  type_counts: Record<string, number>;
  deleted_existing_count: number;
  fetched_count: number;
  inserted_count: number;
  updated_count: number;
  reactivated_count: number;
  deactivated_count: number;
  skipped_count: number;
  error_count: number;
  started_at: string;
  finished_at: string;
  message: string;
};
