export type GptPromptTemplate = {
  id: number;
  domain: string;
  prompt_key: string;
  prompt_name: string;
  description: string | null;
  prompt_text: string;
  default_prompt_text: string;
  is_active: number;
  sort_order: number;
  created_at: string;
  updated_at: string;
};

export type GptPromptTemplateUpdateInput = {
  prompt_name?: string;
  description?: string | null;
  prompt_text?: string;
  is_active?: number;
  sort_order?: number;
};

export type GptPromptTemplateRestoreResponse = {
  message: string;
  template: GptPromptTemplate;
};
