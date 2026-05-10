import { apiRequest } from "@/services/api/apiClient";
import type { AdvisoryPackageGenerateRequest, AdvisoryPackageGenerateResponse } from "@/types/advisoryPackage";

export const advisoryPackageApiRepository = {
  generate: (payload: AdvisoryPackageGenerateRequest) =>
    apiRequest<AdvisoryPackageGenerateResponse>("/advisory-packages/generate", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
};
