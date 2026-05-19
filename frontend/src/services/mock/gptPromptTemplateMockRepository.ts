import type {
  GptPromptTemplate,
  GptPromptTemplateRestoreResponse,
  GptPromptTemplateUpdateInput,
} from "@/types/gptPromptTemplate";

const DEFAULT_TEMPLATE_TEXT = `당신은 보수적인 주식 애널리스트 보조역입니다.
아래 DrCT에셋 근거 패키지를 바탕으로 분석해 주세요.

주의:
- 매수/매도 단정 금지
- 목표가 제시 금지
- 확률 단정 금지
- 과거 유사 패턴은 참고 사례로만 해석
- 데이터 기준일과 품질 상태를 먼저 확인
- 최종 투자 판단은 사용자가 수행

분석 요청:
1. 핵심 요약
2. 가격·기술적 지표 해석
3. 뉴스·공시·Risk 해석
4. 유사 패턴 참고 해석
5. 단기 스윙 관점 시나리오
6. 중장기 관점 시나리오
7. 확인해야 할 리스크
8. 추가로 확인할 데이터
9. 최종 판단 전 체크리스트`;

let row: GptPromptTemplate = {
  id: 1,
  prompt_key: "stock_advisory_analysis",
  prompt_name: "GPT 주식 분석 프롬프트",
  prompt_type: "stock_analysis",
  description: "가격·캔들관리 화면의 GPT 분석 요청문+JSON 복사 기본 프롬프트",
  template_text: DEFAULT_TEMPLATE_TEXT,
  is_active: 1,
  is_default: 1,
  version: 1,
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
      prompt_name: payload.prompt_name,
      description: payload.description,
      template_text: payload.template_text,
      is_active: payload.is_active,
      version: row.version + 1,
      updated_at: "2026-05-19 00:10:00",
    };
    return row;
  },
  async restoreDefault(promptKey: string): Promise<GptPromptTemplateRestoreResponse> {
    if (promptKey !== row.prompt_key) throw new Error("gpt prompt template not found");
    row = {
      ...row,
      prompt_name: "GPT 주식 분석 프롬프트",
      description: "가격·캔들관리 화면의 GPT 분석 요청문+JSON 복사 기본 프롬프트",
      template_text: DEFAULT_TEMPLATE_TEXT,
      is_active: 1,
      version: row.version + 1,
      updated_at: "2026-05-19 00:20:00",
    };
    return { message: "기본 프롬프트로 복원되었습니다.", template: row };
  },
};
