import { apiRequest } from "@/services/api/apiClient";
import type {
  ArchitectureCleanupCandidatesResponse,
  ArchitectureCleanupHistoryResponse,
  ArchitectureCleanupRequest,
  ArchitectureCleanupResponse,
  ArchitectureDeleteEligibilityResponse,
  ArchitectureFolderStatusResponse,
  ArchitectureReferenceCheckResponse,
  ArchitectureSafeDeleteRequest,
  ArchitectureSafeDeleteResponse,
} from "@/types/architecture";

export const architectureApiRepository = {
  fetchFolderStatus: () => apiRequest<ArchitectureFolderStatusResponse>("/architecture/folder-status"),
  fetchCleanupCandidates: () => apiRequest<ArchitectureCleanupCandidatesResponse>("/architecture/cleanup-candidates"),
  referenceCheck: (path: string) =>
    apiRequest<ArchitectureReferenceCheckResponse>(`/architecture/reference-check?path=${encodeURIComponent(path)}`),
  runCleanup: (payload: ArchitectureCleanupRequest) =>
    apiRequest<ArchitectureCleanupResponse>("/architecture/cleanup", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  fetchCleanupHistory: () => apiRequest<ArchitectureCleanupHistoryResponse>("/architecture/cleanup-history"),
  fetchDeleteEligibility: () => apiRequest<ArchitectureDeleteEligibilityResponse>("/architecture/delete-eligibility"),
  deleteSafeCandidates: (payload: ArchitectureSafeDeleteRequest) =>
    apiRequest<ArchitectureSafeDeleteResponse>("/architecture/delete-safe-candidates", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
};
