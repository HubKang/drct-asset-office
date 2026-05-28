from __future__ import annotations

from pydantic import BaseModel


class FolderStatusItem(BaseModel):
    path: str
    exists: bool
    category: str
    policy: str
    role: str
    risk_level: str
    size_bytes: int
    file_count: int
    latest_modified_at: str | None
    scan_note: str | None = None


class FolderStatusResponse(BaseModel):
    scanned_at: str
    total_size_bytes: int
    operational_data_size_bytes: int
    cache_and_artifact_size_bytes: int
    cleanup_candidate_size_bytes: int
    items: list[FolderStatusItem]


class ReferenceMatchItem(BaseModel):
    file_path: str
    line_no: int
    snippet: str


class ReferenceCheckResponse(BaseModel):
    path: str
    reference_count: int
    matched_files: list[str]
    matches: list[ReferenceMatchItem]


class CleanupCandidateItem(BaseModel):
    path: str
    candidate_type: str
    category: str
    policy: str
    risk_level: str
    size_bytes: int
    file_count: int
    latest_modified_at: str | None


class CleanupCandidatesResponse(BaseModel):
    scanned_at: str
    items: list[CleanupCandidateItem]


class CleanupRequest(BaseModel):
    targets: list[str]
    mode: str = "archive"
    confirm: bool = False


class CleanupResultItem(BaseModel):
    target: str
    original_path: str
    archived_path: str | None = None
    size_bytes: int = 0
    file_count: int = 0
    status: str
    message: str


class CleanupResponse(BaseModel):
    run_id: str
    executed_at: str
    mode: str
    results: list[CleanupResultItem]


class CleanupHistoryItem(BaseModel):
    run_id: str
    executed_at: str
    mode: str
    target: str
    original_path: str
    archived_path: str | None = None
    size_bytes: int
    file_count: int
    status: str
    message: str


class CleanupHistoryResponse(BaseModel):
    items: list[CleanupHistoryItem]


class DeleteEligibilityItem(BaseModel):
    path: str
    category: str
    policy: str
    deletion_status: str
    deletion_label: str
    delete_reason: str
    risk_level: str
    reference_count: int | None = None
    is_git_tracked: bool | None = None
    is_archived: bool = False
    cleanup_history_status: str | None = None
    protected_reason: str | None = None
    size_bytes: int
    file_count: int
    last_modified_at: str | None = None


class DeleteEligibilityResponse(BaseModel):
    scanned_at: str
    items: list[DeleteEligibilityItem]


class SafeDeleteRequest(BaseModel):
    targets: list[str]
    confirm_text: str


class SafeDeleteResultItem(BaseModel):
    target: str
    status: str
    message: str
    deleted_path: str | None = None


class SafeDeleteResponse(BaseModel):
    executed_at: str
    results: list[SafeDeleteResultItem]
