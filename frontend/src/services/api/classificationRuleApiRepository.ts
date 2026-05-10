import { apiRequest } from "@/services/api/apiClient";
import type {
  ClassificationRule,
  ClassificationRuleCreatePayload,
  ClassificationRuleListParams,
  ClassificationRuleUpdatePayload,
} from "@/types/classificationRule";

export const classificationRuleApiRepository = {
  listClassificationRules: (params?: ClassificationRuleListParams) => {
    const search = new URLSearchParams();
    if (params?.target_type) search.set("target_type", params.target_type);
    if (params?.rule_group) search.set("rule_group", params.rule_group);
    if (params?.is_active !== undefined) search.set("is_active", String(params.is_active));
    if (params?.keyword) search.set("keyword", params.keyword);
    search.set("limit", String(params?.limit ?? 100));
    search.set("offset", String(params?.offset ?? 0));
    return apiRequest<ClassificationRule[]>(`/classification-rules?${search.toString()}`);
  },
  getClassificationRule: (ruleId: number) => apiRequest<ClassificationRule>(`/classification-rules/${ruleId}`),
  createClassificationRule: (payload: ClassificationRuleCreatePayload) =>
    apiRequest<ClassificationRule>("/classification-rules", { method: "POST", body: JSON.stringify(payload) }),
  updateClassificationRule: (ruleId: number, payload: ClassificationRuleUpdatePayload) =>
    apiRequest<ClassificationRule>(`/classification-rules/${ruleId}`, { method: "PATCH", body: JSON.stringify(payload) }),
  deactivateClassificationRule: (ruleId: number) =>
    apiRequest<ClassificationRule>(`/classification-rules/${ruleId}/deactivate`, { method: "POST" }),
};
