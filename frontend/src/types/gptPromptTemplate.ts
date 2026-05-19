export type GptPromptTemplate = {
  id: number;
  prompt_key: string;
  prompt_name: string;
  prompt_type: string;
  description: string | null;
  template_text: string;
  is_active: number;
  is_default: number;
  version: number;
  created_at: string;
  updated_at: string;
};

export type GptPromptTemplateUpdateInput = {
  prompt_name: string;
  description: string | null;
  template_text: string;
  is_active: number;
};

export type GptPromptTemplateRestoreResponse = {
  message: string;
  template: GptPromptTemplate;
};
