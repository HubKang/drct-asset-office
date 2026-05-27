import type {
  GptPromptTemplate,
  GptPromptTemplateRestoreResponse,
  GptPromptTemplateUpdateInput,
} from "@/types/gptPromptTemplate";

const DEFAULT_TEMPLATE_TEXT = "입력된 종목 근거 데이터를 기반으로 리스크를 포함한 분석 요약을 작성하세요.";

let row: GptPromptTemplate = {
  id: 1,
  domain: "investment_advisory",
  prompt_key: "stock_advisory_analysis",
  prompt_name: "종목 분석 프롬프트",
  description: "기본 종목 분석 프롬프트",
  prompt_text: DEFAULT_TEMPLATE_TEXT,
  default_prompt_text: DEFAULT_TEMPLATE_TEXT,
  is_active: 1,
  sort_order: 10,
  created_at: "2026-05-19 00:00:00",
  updated_at: "2026-05-19 00:00:00",
};

export const gptPromptTemplateMockRepository = {
  async list(): Promise<GptPromptTemplate[]> {
    return [row];
  },
  async get(promptKey: string): Promise<GptPromptTemplate> {
    if (promptKey !== row.prompt_key) throw new Error("gpt prompt template not found");
    return row;
  },
  async update(promptKey: string, payload: GptPromptTemplateUpdateInput): Promise<GptPromptTemplate> {
    if (promptKey !== row.prompt_key) throw new Error("gpt prompt template not found");
    row = {
      ...row,
      prompt_name: payload.prompt_name ?? row.prompt_name,
      description: payload.description ?? row.description,
      prompt_text: payload.prompt_text ?? row.prompt_text,
      is_active: payload.is_active ?? row.is_active,
      sort_order: payload.sort_order ?? row.sort_order,
      updated_at: "2026-05-19 00:10:00",
    };
    return row;
  },
  async restoreDefault(promptKey: string): Promise<GptPromptTemplateRestoreResponse> {
    if (promptKey !== row.prompt_key) throw new Error("gpt prompt template not found");
    row = {
      ...row,
      prompt_text: DEFAULT_TEMPLATE_TEXT,
      updated_at: "2026-05-19 00:20:00",
    };
    return { message: "기본 프롬프트로 복원되었습니다.", template: row };
  },
};
