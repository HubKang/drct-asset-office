export type ClassificationRule = {
  id: number;
  rule_group: string;
  target_type: string;
  rule_name: string;
  keywords: string;
  output_field: string;
  output_value: string;
  score_delta: number;
  priority: number;
  is_active: boolean;
  description: string | null;
  created_at: string;
  updated_at: string;
};

export type ClassificationRuleListParams = {
  target_type?: string;
  rule_group?: string;
  is_active?: boolean;
  keyword?: string;
  limit?: number;
  offset?: number;
};

export type ClassificationRuleCreatePayload = {
  rule_group: string;
  target_type: string;
  rule_name: string;
  keywords: string;
  output_field: string;
  output_value: string;
  score_delta?: number;
  priority?: number;
  is_active?: boolean;
  description?: string | null;
};

export type ClassificationRuleUpdatePayload = Partial<ClassificationRuleCreatePayload>;
