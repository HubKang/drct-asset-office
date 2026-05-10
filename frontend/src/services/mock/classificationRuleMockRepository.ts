import type {
  ClassificationRule,
  ClassificationRuleCreatePayload,
  ClassificationRuleListParams,
  ClassificationRuleUpdatePayload,
} from "@/types/classificationRule";

const now = "2026-05-09 12:00:00";
let sample: ClassificationRule[] = [
  {
    id: 1,
    rule_group: "tag",
    target_type: "news",
    rule_name: "뉴스_반도체",
    keywords: "반도체,hbm,d램,낸드,파운드리,메모리",
    output_field: "ai_tags",
    output_value: "반도체",
    score_delta: 10,
    priority: 10,
    is_active: true,
    description: "반도체 관련 뉴스 태그",
    created_at: now,
    updated_at: now,
  },
  {
    id: 2,
    rule_group: "disclosure_risk_level",
    target_type: "disclosure",
    rule_name: "공시_고위험",
    keywords: "소송,제재,불성실공시,상장폐지",
    output_field: "ai_risk_level",
    output_value: "high",
    score_delta: 20,
    priority: 10,
    is_active: true,
    description: "고위험 공시 분류",
    created_at: now,
    updated_at: now,
  },
];

export const classificationRuleMockRepository = {
  async listClassificationRules(params?: ClassificationRuleListParams): Promise<ClassificationRule[]> {
    let result = [...sample];
    if (params?.target_type) result = result.filter((row) => row.target_type === params.target_type);
    if (params?.rule_group) result = result.filter((row) => row.rule_group === params.rule_group);
    if (params?.is_active !== undefined) result = result.filter((row) => row.is_active === params.is_active);
    if (params?.keyword) {
      const q = params.keyword.toLowerCase();
      result = result.filter((row) => `${row.rule_name} ${row.keywords} ${row.output_value}`.toLowerCase().includes(q));
    }
    const offset = params?.offset ?? 0;
    const limit = params?.limit ?? 100;
    return result.slice(offset, offset + limit);
  },
  async getClassificationRule(ruleId: number): Promise<ClassificationRule> {
    const found = sample.find((row) => row.id === ruleId);
    if (!found) throw new Error("classification rule not found");
    return found;
  },
  async createClassificationRule(payload: ClassificationRuleCreatePayload): Promise<ClassificationRule> {
    const id = Math.max(0, ...sample.map((row) => row.id)) + 1;
    const row: ClassificationRule = {
      id,
      rule_group: payload.rule_group,
      target_type: payload.target_type,
      rule_name: payload.rule_name,
      keywords: payload.keywords,
      output_field: payload.output_field,
      output_value: payload.output_value,
      score_delta: payload.score_delta ?? 0,
      priority: payload.priority ?? 100,
      is_active: payload.is_active ?? true,
      description: payload.description ?? null,
      created_at: now,
      updated_at: now,
    };
    sample = [row, ...sample];
    return row;
  },
  async updateClassificationRule(ruleId: number, payload: ClassificationRuleUpdatePayload): Promise<ClassificationRule> {
    const idx = sample.findIndex((row) => row.id === ruleId);
    if (idx < 0) throw new Error("classification rule not found");
    sample[idx] = {
      ...sample[idx],
      ...payload,
      updated_at: now,
      description: payload.description !== undefined ? (payload.description ?? null) : sample[idx].description,
    };
    return sample[idx];
  },
  async deactivateClassificationRule(ruleId: number): Promise<ClassificationRule> {
    return this.updateClassificationRule(ruleId, { is_active: false });
  },
};
