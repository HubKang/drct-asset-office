export type ArchitectureFolderStatusItem = {
  path: string;
  exists: boolean;
  category: string;
  policy: string;
  role: string;
  risk_level: string;
  size_bytes: number;
  file_count: number;
  latest_modified_at?: string | null;
  scan_note?: string | null;
};

export type ArchitectureFolderStatusResponse = {
  scanned_at: string;
  total_size_bytes: number;
  operational_data_size_bytes: number;
  cache_and_artifact_size_bytes: number;
  cleanup_candidate_size_bytes: number;
  items: ArchitectureFolderStatusItem[];
};

export type ArchitectureCleanupCandidateItem = {
  path: string;
  candidate_type: string;
  category: string;
  policy: string;
  risk_level: string;
  size_bytes: number;
  file_count: number;
  latest_modified_at?: string | null;
};

export type ArchitectureCleanupCandidatesResponse = {
  scanned_at: string;
  items: ArchitectureCleanupCandidateItem[];
};

export type ArchitectureReferenceMatch = {
  file_path: string;
  line_no: number;
  snippet: string;
};

export type ArchitectureReferenceCheckResponse = {
  path: string;
  reference_count: number;
  matched_files: string[];
  matches: ArchitectureReferenceMatch[];
};

export type ArchitectureCleanupRequest = {
  targets: string[];
  mode: "archive";
  confirm: boolean;
};

export type ArchitectureCleanupResultItem = {
  target: string;
  original_path: string;
  archived_path?: string | null;
  size_bytes: number;
  file_count: number;
  status: string;
  message: string;
};

export type ArchitectureCleanupResponse = {
  run_id: string;
  executed_at: string;
  mode: string;
  results: ArchitectureCleanupResultItem[];
};

export type ArchitectureCleanupHistoryItem = {
  run_id: string;
  executed_at: string;
  mode: string;
  target: string;
  original_path: string;
  archived_path?: string | null;
  size_bytes: number;
  file_count: number;
  status: string;
  message: string;
};

export type ArchitectureCleanupHistoryResponse = {
  items: ArchitectureCleanupHistoryItem[];
};

export type ArchitectureDeleteEligibilityStatus =
  | "protected"
  | "safe_to_delete"
  | "safe_to_delete_after_archive"
  | "review_required"
  | "blocked_by_reference"
  | "archived_delete_candidate"
  | "archive_delete_blocked"
  | "unknown";

export type ArchitectureDeleteEligibilityItem = {
  path: string;
  category: string;
  policy: string;
  deletion_status: ArchitectureDeleteEligibilityStatus;
  deletion_label: string;
  delete_reason: string;
  risk_level: string;
  reference_count?: number | null;
  is_git_tracked?: boolean | null;
  is_archived: boolean;
  cleanup_history_status?: string | null;
  protected_reason?: string | null;
  size_bytes: number;
  file_count: number;
  last_modified_at?: string | null;
};

export type ArchitectureDeleteEligibilityResponse = {
  scanned_at: string;
  items: ArchitectureDeleteEligibilityItem[];
};

export type ArchitectureSafeDeleteRequest = {
  targets: string[];
  confirm_text: string;
};

export type ArchitectureSafeDeleteResultItem = {
  target: string;
  status: string;
  message: string;
  deleted_path?: string | null;
};

export type ArchitectureSafeDeleteResponse = {
  executed_at: string;
  results: ArchitectureSafeDeleteResultItem[];
};
