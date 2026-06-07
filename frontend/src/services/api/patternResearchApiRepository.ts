import { apiRequest } from "@/services/api/apiClient";
import { appConfig } from "@/services/config/appConfig";
import type {
  PatternGoalParseResponse,
  PatternGptGoalParsePromptResponse,
  PatternGptGoalResultValidateResponse,
  PatternResearchGptPackage,
  PatternResearchRun,
  PatternResearchRunCreateResponse,
  PatternResearchRunRequest,
  PatternResearchRunSimulateResponse,
  PatternResearchSample,
  PatternResearchStockListResponse,
} from "@/types/patternResearch";

export const patternResearchApiRepository = {
  fetchStocks: (params?: { keyword?: string; limit?: number }) => {
    const search = new URLSearchParams();
    if (params?.keyword?.trim()) search.set("keyword", params.keyword.trim());
    if (params?.limit) search.set("limit", String(params.limit));
    const query = search.toString();
    return apiRequest<PatternResearchStockListResponse>(`/pattern-research/stocks${query ? `?${query}` : ""}`);
  },
  fetchIndicators: () => apiRequest<{ items: Array<Record<string, unknown>> }>("/pattern-research/indicators"),
  parseGoal: (goal_text: string, options?: { use_llm?: boolean; llm_mode?: string }) =>
    apiRequest<PatternGoalParseResponse>("/pattern-research/parse-goal", {
      method: "POST",
      body: JSON.stringify({ goal_text, use_llm: Boolean(options?.use_llm), llm_mode: options?.llm_mode || "assist" }),
      timeoutMs: options?.use_llm ? 300_000 : undefined,
    }),
  fetchGptGoalParsePrompt: (goal_text: string, parsed_goal?: Record<string, any> | null) =>
    apiRequest<PatternGptGoalParsePromptResponse>("/pattern-research/gpt-goal-parse-prompt", {
      method: "POST",
      body: JSON.stringify({ goal_text, parsed_goal }),
    }),
  validateGptGoalResult: (payload: { goal_text: string; gpt_result_text: string; parsed_goal?: Record<string, any> | null }) =>
    apiRequest<PatternGptGoalResultValidateResponse>("/pattern-research/validate-gpt-goal-result", {
      method: "POST",
      body: JSON.stringify(payload),
      timeoutMs: 60_000,
    }),
  createRun: (payload: PatternResearchRunRequest) =>
    apiRequest<PatternResearchRunCreateResponse>("/pattern-research/runs", {
      method: "POST",
      body: JSON.stringify(payload),
      timeoutMs: 90_000,
    }),
  simulateRun: (payload: PatternResearchRunRequest) =>
    apiRequest<PatternResearchRunSimulateResponse>("/pattern-research/runs/simulate", {
      method: "POST",
      body: JSON.stringify(payload),
      timeoutMs: 90_000,
    }),
  fetchRuns: (params?: { limit?: number }) => {
    const search = new URLSearchParams();
    if (params?.limit) search.set("limit", String(params.limit));
    const query = search.toString();
    return apiRequest<{ items: PatternResearchRun[] }>(`/pattern-research/runs${query ? `?${query}` : ""}`);
  },
  fetchRun: (runId: number) => apiRequest<PatternResearchRun>(`/pattern-research/runs/${runId}`),
  fetchSamples: (runId: number, label?: string) => {
    const search = new URLSearchParams();
    if (label) search.set("label", label);
    const query = search.toString();
    return apiRequest<{ items: PatternResearchSample[] }>(`/pattern-research/runs/${runId}/samples${query ? `?${query}` : ""}`);
  },
  fetchGptPackage: (runId: number) => apiRequest<PatternResearchGptPackage>(`/pattern-research/runs/${runId}/gpt-package`),
  csvUrl: (runId: number) => `${appConfig.apiBaseUrl}/pattern-research/runs/${runId}/csv`,
};
