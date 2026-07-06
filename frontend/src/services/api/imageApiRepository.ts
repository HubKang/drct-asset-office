import type { AppImage, AppImageDeleteResponse, AppImageDomain, AppImageListResponse } from "@/types/image";
import { apiRequest } from "./apiClient";

type UploadImagePayload = {
  domain: AppImageDomain;
  file: File;
  owner_type?: string;
  owner_id?: number;
  description?: string;
  sort_order?: number;
};

type ListImagesParams = {
  domain?: AppImageDomain;
  owner_type?: string;
  owner_id?: number;
};

const buildQuery = (params: ListImagesParams) => {
  const search = new URLSearchParams();
  if (params.domain) search.set("domain", params.domain);
  if (params.owner_type) search.set("owner_type", params.owner_type);
  if (params.owner_id != null) search.set("owner_id", String(params.owner_id));
  const query = search.toString();
  return query ? `?${query}` : "";
};

export const imageApiRepository = {
  uploadImage: (payload: UploadImagePayload) => {
    const formData = new FormData();
    formData.set("domain", payload.domain);
    formData.set("file", payload.file);
    if (payload.owner_type) formData.set("owner_type", payload.owner_type);
    if (payload.owner_id != null) formData.set("owner_id", String(payload.owner_id));
    if (payload.description) formData.set("description", payload.description);
    if (payload.sort_order != null) formData.set("sort_order", String(payload.sort_order));
    return apiRequest<AppImage>("/images/upload", { method: "POST", body: formData });
  },
  listImages: (params: ListImagesParams = {}) => apiRequest<AppImageListResponse>(`/images${buildQuery(params)}`),
  deleteImage: (imageId: number) => apiRequest<AppImageDeleteResponse>(`/images/${imageId}`, { method: "DELETE" }),
};
