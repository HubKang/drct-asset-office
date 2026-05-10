import { apiRequest } from "@/services/api/apiClient";
import type { SchemaComment } from "@/types/schemaComment";

export const schemaCommentApiRepository = {
  list: (tableName?: string) =>
    apiRequest<SchemaComment[]>(`/schema-comments${tableName ? `?table_name=${encodeURIComponent(tableName)}` : ""}`),
};
