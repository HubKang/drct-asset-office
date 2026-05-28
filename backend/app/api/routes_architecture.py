from __future__ import annotations

from fastapi import APIRouter, Query

from backend.app.schemas.architecture_schema import (
    CleanupCandidatesResponse,
    CleanupHistoryResponse,
    CleanupRequest,
    CleanupResponse,
    DeleteEligibilityResponse,
    FolderStatusResponse,
    ReferenceCheckResponse,
    SafeDeleteRequest,
    SafeDeleteResponse,
)
from backend.app.services.architecture_service import ArchitectureService

router = APIRouter(tags=["architecture"])


@router.get("/architecture/folder-status", response_model=FolderStatusResponse)
def get_folder_status():
    return ArchitectureService().get_folder_status()


@router.get("/architecture/cleanup-candidates", response_model=CleanupCandidatesResponse)
def get_cleanup_candidates():
    return ArchitectureService().get_cleanup_candidates()


@router.get("/architecture/reference-check", response_model=ReferenceCheckResponse)
def get_reference_check(path: str = Query(...)):
    return ArchitectureService().reference_check(path=path)


@router.post("/architecture/cleanup", response_model=CleanupResponse)
def run_cleanup(payload: CleanupRequest):
    return ArchitectureService().cleanup(targets=payload.targets, mode=payload.mode, confirm=payload.confirm)


@router.get("/architecture/cleanup-history", response_model=CleanupHistoryResponse)
def get_cleanup_history():
    return ArchitectureService().cleanup_history()


@router.get("/architecture/delete-eligibility", response_model=DeleteEligibilityResponse)
def get_delete_eligibility():
    return ArchitectureService().get_delete_eligibility()


@router.post("/architecture/delete-safe-candidates", response_model=SafeDeleteResponse)
def delete_safe_candidates(payload: SafeDeleteRequest):
    return ArchitectureService().delete_safe_candidates(targets=payload.targets, confirm_text=payload.confirm_text)
