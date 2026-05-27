import { apiRequest } from "@/services/api/apiClient";
import type {
  GptPromptTemplate,
  GptPromptTemplateRestoreResponse,
  GptPromptTemplateUpdateInput,
} from "@/types/gptPromptTemplate";

export const gptPromptTemplateApiRepository = {
  list: (domain?: string) => apiRequest<GptPromptTemplate[]>(`/gpt-prompt-templates${domain ? `?domain=${encodeURIComponent(domain)}` : ""}`),
  get: (promptKey: string) => apiRequest<GptPromptTemplate>(`/gpt-prompt-templates/${promptKey}`),
  update: (promptKey: string, payload: GptPromptTemplateUpdateInput) =>
    apiRequest<GptPromptTemplate>(`/gpt-prompt-templates/${promptKey}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),
  restoreDefault: (promptKey: string) =>
    apiRequest<GptPromptTemplateRestoreResponse>(`/gpt-prompt-templates/${promptKey}/reset-default`, {
      method: "POST",
    }),
};
