import { apiRequest } from "@/services/api/apiClient";
import type {
  BacktestRule,
  BacktestRuleInput,
  BacktestRuleListResponse,
  BacktestRunCreateResponse,
  BacktestRunDetail,
  BacktestRunListResponse,
  BacktestRunRequest,
  BacktestConditionFieldListResponse,
  BacktestStockListResponse,
} from "@/types/backtest";

export const backtestApiRepository = {
  fetchStocks: (params?: { keyword?: string; limit?: number }) => {
    const search = new URLSearchParams();
    if (params?.keyword?.trim()) search.set("keyword", params.keyword.trim());
    if (params?.limit) search.set("limit", String(params.limit));
    const query = search.toString();
    return apiRequest<BacktestStockListResponse>(`/backtest/stocks${query ? `?${query}` : ""}`);
  },
  fetchConditionFields: () => apiRequest<BacktestConditionFieldListResponse>("/backtest/condition-fields"),
  fetchRules: (params?: { include_inactive?: boolean }) => {
    const search = new URLSearchParams();
    if (params?.include_inactive) search.set("include_inactive", "true");
    const query = search.toString();
    return apiRequest<BacktestRuleListResponse>(`/backtest/rules${query ? `?${query}` : ""}`);
  },
  createRule: (payload: BacktestRuleInput) =>
    apiRequest<BacktestRule>("/backtest/rules", { method: "POST", body: JSON.stringify(payload) }),
  updateRule: (ruleId: number, payload: Partial<BacktestRuleInput> & { is_active?: boolean }) =>
    apiRequest<BacktestRule>(`/backtest/rules/${ruleId}`, { method: "PATCH", body: JSON.stringify(payload) }),
  deleteRule: (ruleId: number) => apiRequest<BacktestRule>(`/backtest/rules/${ruleId}`, { method: "DELETE" }),
  run: (payload: BacktestRunRequest) =>
    apiRequest<BacktestRunCreateResponse>("/backtest/runs", {
      method: "POST",
      body: JSON.stringify(payload),
      timeoutMs: 60_000,
    }),
  fetchRun: (runId: number) => apiRequest<BacktestRunDetail>(`/backtest/runs/${runId}`),
  fetchRuns: (params?: { rule_id?: number; stock_code?: string; limit?: number }) => {
    const search = new URLSearchParams();
    if (params?.rule_id) search.set("rule_id", String(params.rule_id));
    if (params?.stock_code) search.set("stock_code", params.stock_code);
    if (params?.limit) search.set("limit", String(params.limit));
    const query = search.toString();
    return apiRequest<BacktestRunListResponse>(`/backtest/runs${query ? `?${query}` : ""}`);
  },
};
