import { apiRequest } from "@/services/api/apiClient";
import type {
  GptPromptTemplate,
  GptPromptTemplateRestoreResponse,
  GptPromptTemplateUpdateInput,
} from "@/types/gptPromptTemplate";

export const gptPromptTemplateApiRepository = {
  list: () => apiRequest<GptPromptTemplate[]>("/settings/gpt-prompts"),
  get: (promptKey: string) => apiRequest<GptPromptTemplate>(`/settings/gpt-prompts/${promptKey}`),
  update: (promptKey: string, payload: GptPromptTemplateUpdateInput) =>
    apiRequest<GptPromptTemplate>(`/settings/gpt-prompts/${promptKey}`, {
      method: "PUT",
      body: JSON.stringify(payload),
    }),
  restoreDefault: (promptKey: string) =>
    apiRequest<GptPromptTemplateRestoreResponse>(`/settings/gpt-prompts/${promptKey}/restore-default`, {
      method: "POST",
    }),
};
