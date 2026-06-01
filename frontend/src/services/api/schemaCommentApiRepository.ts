import { apiRequest } from "@/services/api/apiClient";
import type { SchemaComment, SchemaCommentColumn, SchemaCommentTable } from "@/types/schemaComment";

export const schemaCommentApiRepository = {
  list: (tableName?: string) =>
    apiRequest<SchemaComment[]>(`/schema-comments${tableName ? `?table_name=${encodeURIComponent(tableName)}` : ""}`),
  listTables: (tableName?: string) =>
    apiRequest<SchemaCommentTable[]>(`/schema-comments/tables${tableName ? `?table_name=${encodeURIComponent(tableName)}` : ""}`),
  listColumns: (tableName: string) => apiRequest<SchemaCommentColumn[]>(`/schema-comments/tables/${encodeURIComponent(tableName)}/columns`),
};
