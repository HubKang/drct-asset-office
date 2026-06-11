import { useEffect, useMemo, useRef, useState } from "react";
import { Clipboard, Download, Search } from "lucide-react";
import EmptyState from "@/components/common/EmptyState";
import PageHeader from "@/components/common/PageHeader";
import SectionCard from "@/components/common/SectionCard";
import { repositories } from "@/services";
import type {
  PatternGoalParseResponse,
  PatternGptGoalResultValidateResponse,
  PatternResearchGptPackage,
  PatternResearchRun,
  PatternResearchSample,
  PatternResearchStock,
  ScenarioSimulationResponse,
  ScenarioSimulationResult,
  ScenarioValidationResponse,
  ScenarioValidationSummary,
  ValidatedScenarioCandidate,
} from "@/types/patternResearch";

type TabKey = "setup" | "gptValidation" | "confirm" | "samples" | "package" | "settings" | "analysis" | "gpt";
type SampleTab = "SUCCESS" | "FAILURE" | "NEUTRAL";
type GptValidationStatus = "idle" | "validating" | "success" | "failed";
type ConditionUsage = "include" | "exclude" | "reference" | "off";
type FinalUsageMap = Record<string, ConditionUsage>;
type ResearchMode = "rule_validation" | "ai_scenario_search";
type ScenarioSearchStep = "setup" | "gpt_candidates" | "validation" | "results" | "training_guide";
type ScenarioCandidateStatus = "included" | "excluded";
type ScenarioGoalState = {
  tradeType: "short" | "swing" | "mid" | "long";
  targetReturnPct: number;
  holdingDays: number;
  stopLossPct: number;
  minSampleCount: number;
};
type ScenarioRiskPlanState = {
  addBuyEnabled: boolean;
  maxAddBuyCount: number;
  initialAmount: number;
  addBuyAmountType: "same";
  addBuyTriggerLossPct: number;
  finalStopLossBasis: "initial_price" | "average_price";
  finalStopLossPct: number;
};
type ScenarioCandidate = {
  id: string;
  name: string;
  summary: string;
  entryConditions: string[];
  addBuyStrategy: string;
  stopLossRule: string;
  fundingNote: string;
  status: ScenarioCandidateStatus;
  raw: Record<string, any>;
  stringConditionCount: number;
  invalidStructureCount: number;
  schemaWarnings: string[];
};
type NewIndicatorUsageStatus = "filter_supported" | "not_blocking" | "filter_engine_required";
type SampleBlocker = {
  rowId: string;
  indicatorKey: string;
  label: string;
  sourceText: string;
  expression: string;
  finalUsage: ConditionUsage;
  calculationType: string;
  requiredIndicators: string[];
  currentStatus: string;
  message: string;
};
type AutoParamCandidate = {
  id: string;
  label: string;
  description: string;
  parsedGoal: Record<string, any>;
  changedCondition: Record<string, any>;
  hash: string;
};
type AutoParamResult = AutoParamCandidate & {
  seq: number;
  status: "success" | "error";
  summary?: Record<string, any>;
  samples?: PatternResearchSample[];
  gptPackage?: PatternResearchGptPackage;
  error?: string;
};
type ResearchStepStatus = "complete" | "active" | "pending" | "attention";
type ResearchStepperItem = {
  key: string;
  label: string;
  description: string;
  status: ResearchStepStatus;
  statusLabel: string;
};

const SCENARIO_SEARCH_STEPS: Array<{ key: ScenarioSearchStep; label: string }> = [
  { key: "setup", label: "1. 탐색 설정" },
  { key: "gpt_candidates", label: "2. GPT 후보" },
  { key: "validation", label: "3. 검증/실행" },
  { key: "results", label: "4. 결과 분석" },
  { key: "training_guide", label: "5. 훈련가이드" },
];

const SCENARIO_STEP_DESCRIPTIONS: Record<ScenarioSearchStep, string> = {
  setup: "목표 수익률, 대상 종목, 하락 대응전략을 정리해 GPT 후보 생성을 준비합니다.",
  gpt_candidates: "DrCT 데이터 프로파일을 바탕으로 GPT 시나리오 후보를 생성하고 후보 포함 여부를 정합니다.",
  validation: "GPT 후보 조건이 실제 지표와 연산자로 계산 가능한지 검증하고 시뮬레이션 대상을 확정합니다.",
  results: "실제 가격 데이터 기반 결과를 비교해 성공률, 실패율, 추가매수 효과를 분석합니다.",
  training_guide: "선택한 시나리오를 GPT 훈련가이드 요청문으로 정리하고 응답을 미리봅니다.",
};

const SCENARIO_AVAILABLE_INDICATORS = [
  "ma20_slope_5d",
  "ma60_slope_5d",
  "close_vs_ma20_pct",
  "close_vs_ma60_pct",
  "ma5_vs_ma10_pct",
  "recent_3d_return",
  "recent_5d_return",
  "recent_10d_return",
  "max_return_1d_30d",
  "trading_value_ratio_20",
];

const SCENARIO_INDICATOR_GROUPS = [
  { title: "추세", indicators: ["ma20_slope_5d", "ma60_slope_5d"] },
  { title: "눌림/이격", indicators: ["close_vs_ma20_pct", "close_vs_ma60_pct", "ma5_vs_ma10_pct"] },
  { title: "단기 과열", indicators: ["recent_3d_return", "recent_5d_return", "recent_10d_return", "max_return_1d_30d"] },
  { title: "거래대금", indicators: ["trading_value_ratio_20"] },
];

const TRADE_TYPE_LABELS: Record<ScenarioGoalState["tradeType"], string> = {
  short: "단기",
  swing: "스윙",
  mid: "중기",
  long: "장기",
};

const DRCT_SCENARIO_JSON_EXAMPLE = {
  scenario_candidates: [
    {
      scenario_name: "상승추세 눌림 후 과열 해소 반등",
      scenario_type: "swing_pullback",
      intent: "60일선 상승 추세를 유지하면서 20일선 근처로 눌린 뒤 단기 과열이 해소된 구간을 찾습니다.",
      entry_conditions: [
        {
          indicator_key: "ma60_slope_5d",
          operator: ">",
          value: 0,
          role: "trend_filter",
          description: "60일선 상승 추세",
        },
        {
          indicator_key: "close_vs_ma20_pct",
          operator: "between",
          value: [-5, 5],
          role: "pullback",
          description: "20일선 근처 눌림",
        },
        {
          indicator_key: "recent_5d_return",
          operator: "<=",
          value: 12,
          role: "overheat_filter",
          description: "최근 5거래일 단기 과열 제한",
        },
      ],
      add_buy_plan: {
        enabled: true,
        max_count: 1,
        trigger_basis: "entry_price",
        trigger_loss_pct: -5,
        amount_ratio: 1.0,
        stop_loss_basis: "average_price",
        final_stop_loss_pct: -5,
      },
      risk_filters: [
        {
          indicator_key: "close_vs_ma60_pct",
          operator: "<",
          value: 0,
          action: "block_add_buy",
          reason: "60일선 이탈 시 추가매수 차단",
        },
      ],
      expected_risk: "추가매수 후에도 추세가 회복되지 않으면 총 투입금액 증가로 실제 손실금액이 커질 수 있습니다.",
      simulation_priority: "high",
    },
  ],
};

const DRCT_SCENARIO_BAD_JSON_EXAMPLE = {
  entry_conditions: [
    "ma60_slope_5d > 0",
    "close_vs_ma20_pct between -5 and 5",
  ],
};

const DEFAULT_GOAL =
  "20일선 근처에서 눌림을 받고 거래대금이 다시 유입되며, 5거래일 안에 5% 이상 상승할 가능성이 높은 패턴을 찾고 싶다. 손절은 -5% 이내로 제한하고, 급등 직후 추격매수는 제외하고 싶다.";

function fmtNumber(value: number | null | undefined, digits = 2): string {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "-";
  return Number(value).toLocaleString("ko-KR", { maximumFractionDigits: digits });
}

function fmtWon(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "-";
  return `${fmtNumber(value, 0)}원`;
}

function fmtPercent(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "-";
  const sign = Number(value) > 0 ? "+" : "";
  return `${sign}${Number(value).toFixed(2)}%`;
}

function twoYearsBefore(dateText: string): string {
  const date = new Date(`${dateText}T00:00:00`);
  date.setFullYear(date.getFullYear() - 2);
  return date.toISOString().slice(0, 10);
}

function maxDate(left: string, right: string): string {
  return left > right ? left : right;
}

function statusLabel(status: string): string {
  if (status === "applied" || status === "confirmed" || status === "sample_applied") return "확정";
  if (status === "calculated" || status === "calculable" || status === "calculatable" || status === "available") return "계산 가능";
  if (status === "needs_review") return "확인 필요";
  if (status === "unsupported") return "미지원";
  if (status === "disabled") return "사용안함";
  if (status === "error") return "오류";
  if (status === "catalog_missing") return "catalog 필요";
  return status || "-";
}

function statusClass(status: string): string {
  if (status === "applied" || status === "confirmed" || status === "sample_applied") return "confirmed";
  if (status === "calculated" || status === "calculable" || status === "calculatable" || status === "available") return "calculable";
  if (status === "needs_review") return "needs_review";
  if (status === "unsupported" || status === "catalog_missing") return "unsupported";
  if (status === "disabled") return "unsupported";
  if (status === "error") return "error";
  return "unknown";
}

function applyModeLabel(condition: Record<string, any>): string {
  if (condition.apply_mode_label) return String(condition.apply_mode_label);
  if (condition.status === "unsupported") return "미적용";
  if (condition.exclude_when_true) return condition.apply_to_samples ? "제외 조건으로 사용" : "비교용으로만 사용";
  return condition.apply_to_samples ? "포함 조건으로 사용" : "비교용으로만 사용";
}

function expressionForCondition(condition: Record<string, any>): string {
  const indicator = condition.indicator_key || condition.indicator || "-";
  const operator = condition.operator || "-";
  const value = condition.value;
  if (operator === "between" && Array.isArray(value)) {
    return `${value[0]} <= ${indicator} <= ${value[1]}`;
  }
  if (Array.isArray(indicator)) {
    return `${indicator.join(", ")} ${operator} ${value ?? ""}`.trim();
  }
  return `${indicator} ${operator} ${value ?? ""}`.trim();
}

function gptValidationStatusLabel(status: GptValidationStatus): string {
  const labels: Record<GptValidationStatus, string> = {
    idle: "대기",
    validating: "검증 중",
    success: "검증 완료",
    failed: "검증 실패",
  };
  return labels[status];
}

function gptValidationErrorMessage(validation: PatternGptGoalResultValidateResponse | null, fallback = ""): string {
  if (!validation) return fallback;
  if (validation.status === "invalid_json") return validation.raw_error ? `JSON 형식 오류: ${validation.raw_error}` : "JSON 형식 오류";
  if (validation.status === "validation_failed") {
    return validation.validation_message || validation.raw_error || "필수 필드 또는 indicator_key 검증 실패";
  }
  if (validation.validation_message) return validation.validation_message;
  if (validation.raw_error) return validation.raw_error;
  if (validation.status && validation.status !== "success") return validation.status;
  return fallback;
}

function itemText(item: unknown, primaryKey = "source_text", secondaryKey = "reason"): string {
  if (typeof item === "string") return item;
  if (item && typeof item === "object") {
    const row = item as Record<string, any>;
    return String(row[primaryKey] || row.natural_text || row.message || row[secondaryKey] || "-");
  }
  return "-";
}

function friendlyStatusLabel(status: string | undefined): string {
  const labels: Record<string, string> = {
    valid: "사용 가능",
    needs_review: "확인 필요",
    new_indicator_required: "신규 지표 필요",
    calculatable: "계산 가능",
    needs_engine: "계산 엔진 필요",
    rejected: "사용 불가",
    success_criteria: "성공 기준",
    failure_criteria: "실패 기준",
    entry_filter: "진입 조건",
    exclude_filter: "제외 조건",
    reference_condition: "참고 조건",
    reference: "참고 조건",
  };
  return {
    ...labels,
    missing_required_indicator: "필요 지표 없음",
    lookahead_risk: "미래정보 위험",
    invalid_parameters: "파라미터 오류",
    reference_only: "관찰 전용",
    applied: "적용됨",
    confirmed: "확정",
  }[status || ""] || status || "-";
}

function friendlyApplyModeLabel(value: unknown): string {
  if (value === true) return "포함 조건으로 사용";
  if (value === false) return "비교용으로만 사용";
  return "항상 적용";
}

function usageForCondition(condition: Record<string, any>, kind?: "entry_filters" | "exclude_filters"): ConditionUsage {
  if (condition.status === "disabled" || condition.apply_mode === "off") return "off";
  if (kind === "exclude_filters" || condition.exclude_when_true) return condition.apply_to_samples === false ? "reference" : "exclude";
  return condition.apply_to_samples ? "include" : "reference";
}

function usageLabel(usage: ConditionUsage): string {
  const labels: Record<ConditionUsage, string> = {
    include: "포함 조건으로 사용",
    exclude: "제외 조건으로 사용",
    reference: "비교용으로만 사용",
    off: "사용안함",
  };
  return labels[usage];
}

function conditionRowId(kind: string, condition: Record<string, any>, index = 0): string {
  const key = condition.indicator_key || condition.indicator || condition.suggested_indicator_key || "";
  const source = condition.source_text || condition.natural_text || condition.label || "";
  const expression = condition.expression || expressionForCondition(condition);
  const stableParts = key || source || expression
    ? [kind, key, source || expression]
    : [kind, index];
  return stableParts.map((part) => String(part || "").replace(/\s+/g, " ").trim()).join("|");
}

function formatConditionExpression(condition: Record<string, any>, usage: ConditionUsage | "always" = "reference"): string {
  const expression = String(condition.expression || "").trim();
  if (expression && !/(=\s*(none|null|undefined)\b|\bundefined\b|\bNaN\b)/i.test(expression)) return expression;
  const indicator = String(condition.indicator_key || condition.indicator || condition.suggested_indicator_key || "").trim();
  const operator = String(condition.operator || "").trim();
  const value = condition.value;
  if (!indicator) return String(condition.label || condition.natural_text || condition.source_text || (usage === "include" || usage === "exclude" ? "기준값 확인 필요" : "관찰 지표"));
  if (operator === "between" && Array.isArray(value)) return `${value[0]} <= ${indicator} <= ${value[1]}`;
  if (value !== null && value !== undefined && value !== "") return `${indicator} ${operator || "="} ${value}`.trim();
  if (usage === "include" || usage === "exclude") return `${indicator} 기준값 확인 필요`;
  return `${indicator} 관찰`;
}

function conditionIdentity(condition: Record<string, any>): string {
  const indicator = condition.indicator_key || condition.indicator || "";
  const operator = condition.operator || "";
  const value = JSON.stringify(condition.value ?? null);
  const category = condition.category || condition.group || "";
  const expression = condition.expression || expressionForCondition(condition);
  return [indicator, operator, value, category, expression].join("|");
}

function cloneGoal(goal: Record<string, any>): Record<string, any> {
  return JSON.parse(JSON.stringify(goal || {}));
}

function autoConditionHash(goal: Record<string, any>): string {
  const slim = {
    entry_filters: (goal.entry_filters || []).map((item: Record<string, any>) => ({
      indicator_key: item.indicator_key || item.indicator,
      operator: item.operator,
      value: item.value,
      exclude_when_true: Boolean(item.exclude_when_true),
    })),
    exclude_filters: (goal.exclude_filters || []).map((item: Record<string, any>) => ({
      indicator_key: item.indicator_key || item.indicator,
      operator: item.operator,
      value: item.value,
      exclude_when_true: Boolean(item.exclude_when_true),
    })),
    reference_conditions: (goal.reference_conditions || []).map((item: Record<string, any>) => ({
      indicator_key: item.indicator_key || item.indicator,
      operator: item.operator,
      value: item.value,
    })),
  };
  return JSON.stringify(slim);
}

function resultSamplesForTab(samples: PatternResearchSample[], tab: SampleTab): PatternResearchSample[] {
  return samples.filter((sample) => sample.result_label === tab);
}

function autoResultVerdict(result: AutoParamResult, baselineSummary: Record<string, any> | null | undefined): string {
  if (result.status === "error") return "오류";
  const summary = result.summary || {};
  const total = Number(summary.total_samples || 0);
  const success = Number(summary.success_count || 0);
  const failure = Number(summary.failure_count || 0);
  const delta = Number(summary.success_rate || 0) - Number(baselineSummary?.success_rate || 0);
  if (total < 30 || success < 10 || failure < 10) return "샘플 부족";
  if (delta >= 5) return "우수";
  if (delta >= 2) return "검토";
  if (delta <= -2) return "악화";
  return "효과 약함";
}

function autoResultMetrics(result: AutoParamResult, baselineSummary: Record<string, any> | null | undefined) {
  const summary = result.summary || {};
  const baselineTotal = Number(baselineSummary?.total_samples || 0);
  const total = Number(summary.total_samples || 0);
  return {
    baselineTotal,
    total,
    success: Number(summary.success_count || 0),
    failure: Number(summary.failure_count || 0),
    neutral: Number(summary.neutral_count || 0),
    successRate: Number(summary.success_rate || 0),
    baselineRate: Number(baselineSummary?.success_rate || 0),
    rateDelta: Number(summary.success_rate || 0) - Number(baselineSummary?.success_rate || 0),
    sampleDelta: total - baselineTotal,
    successDelta: Number(summary.success_count || 0) - Number(baselineSummary?.success_count || 0),
    failureDelta: Number(summary.failure_count || 0) - Number(baselineSummary?.failure_count || 0),
  };
}

function autoResultVerdictV2(result: AutoParamResult, baselineSummary: Record<string, any> | null | undefined): string {
  if (result.status === "error") return "오류";
  const metrics = autoResultMetrics(result, baselineSummary);
  if (metrics.total < 30 || metrics.success < 10 || metrics.failure < 10) return "샘플 부족";
  if (metrics.baselineTotal > 0 && metrics.total <= metrics.baselineTotal * 0.3) return "과최적화 주의";
  if (metrics.rateDelta >= 5) return "유망";
  if (metrics.rateDelta >= 2) return "검토";
  if (metrics.rateDelta <= -2) return "악화";
  return "효과 약함";
}

function autoResultInterpretation(result: AutoParamResult, baselineSummary: Record<string, any> | null | undefined): string {
  if (result.status === "error") return "이 조건 세트는 계산 중 오류가 발생했습니다. 조건식이나 지표 지원 여부를 확인해야 합니다.";
  const metrics = autoResultMetrics(result, baselineSummary);
  const verdict = autoResultVerdictV2(result, baselineSummary);
  if (verdict === "유망") return `성공률이 기준 대비 ${fmtPercent(metrics.rateDelta)} 개선됐고 후보 ${fmtNumber(metrics.total, 0)}개가 유지되어 다음 테스트 후보로 검토할 만합니다.`;
  if (verdict === "검토") return "성공률은 소폭 개선됐지만 변화 폭이 제한적입니다. 다른 조건과 조합해 추가 검토하는 편이 좋습니다.";
  if (verdict === "샘플 부족") return `성공률은 좋아 보일 수 있지만 후보 수가 ${fmtNumber(metrics.total, 0)}개로 줄었습니다. 과최적화 가능성이 있어 추가 검증이 필요합니다.`;
  if (verdict === "과최적화 주의") return "성공률 변화만 보면 좋아도 후보 수가 기준 대비 크게 감소했습니다. 한 종목/기간에 과하게 맞춰졌을 수 있습니다.";
  if (verdict === "악화") return `성공률이 기준보다 ${fmtPercent(Math.abs(metrics.rateDelta))} 낮아졌습니다. 현재 조건 조합에서는 개선 효과가 약합니다.`;
  return "기준 결과와 성공률 차이가 작습니다. 이 조건 하나만으로는 성공/실패 구분력이 충분하지 않을 수 있습니다.";
}

function autoResultShortInterpretation(result: AutoParamResult, baselineSummary: Record<string, any> | null | undefined): string {
  const verdict = autoResultVerdictV2(result, baselineSummary);
  if (verdict === "유망") return "성공률 개선 + 샘플 유지";
  if (verdict === "검토") return "소폭 개선, 추가 조합 필요";
  if (verdict === "샘플 부족") return "개선처럼 보이나 샘플 부족";
  if (verdict === "과최적화 주의") return "샘플 급감 주의";
  if (verdict === "악화") return "성공률 악화";
  if (verdict === "오류") return "계산 오류";
  return "차이 작음";
}

function autoResultVerdictRank(verdict: string): number {
  const ranks: Record<string, number> = {
    유망: 0,
    검토: 1,
    "효과 약함": 2,
    "샘플 부족": 3,
    "과최적화 주의": 3,
    악화: 4,
    오류: 5,
  };
  return ranks[verdict] ?? 9;
}

function sortAutoResultsByPromise(results: AutoParamResult[], baselineSummary: Record<string, any> | null | undefined): AutoParamResult[] {
  return [...results]
    .filter((result) => result.status === "success")
    .sort((left, right) => {
      const leftMetrics = autoResultMetrics(left, baselineSummary);
      const rightMetrics = autoResultMetrics(right, baselineSummary);
      const verdictDiff = autoResultVerdictRank(autoResultVerdictV2(left, baselineSummary)) - autoResultVerdictRank(autoResultVerdictV2(right, baselineSummary));
      if (verdictDiff !== 0) return verdictDiff;
      if (rightMetrics.rateDelta !== leftMetrics.rateDelta) return rightMetrics.rateDelta - leftMetrics.rateDelta;
      if (rightMetrics.total !== leftMetrics.total) return rightMetrics.total - leftMetrics.total;
      return leftMetrics.failure - rightMetrics.failure;
    });
}

function autoValueKey(value: any): string {
  return Array.isArray(value) ? value.join("~") : String(value ?? "");
}

function autoConditionRowKey(condition: Record<string, any>, usage: ConditionUsage): string {
  const indicator = String(condition.indicator_key || condition.indicator || "");
  const operator = String(condition.operator || "");
  return `auto:${indicator}:${operator}:${autoValueKey(condition.value)}:${usage}`;
}

function buildConditionFromAutoResult(result: AutoParamResult): { condition: Record<string, any>; usage: ConditionUsage; targetKey: "entry_filters" | "exclude_filters"; rowKey: string } {
  const source = result.changedCondition || {};
  const usage: ConditionUsage = source.exclude_when_true ? "exclude" : "include";
  const indicator = String(source.indicator_key || source.indicator || "");
  const condition = {
    ...source,
    indicator_key: indicator,
    label: result.label || source.label || indicator,
    natural_text: result.label || source.natural_text || source.source_text || indicator,
    source_text: `자동 수치변경 테스트 #${result.seq}: ${result.label}`,
    expression: source.expression || expressionForCondition(source),
    apply_to_samples: true,
    exclude_when_true: usage === "exclude",
    apply_mode_label: usageLabel(usage),
    status: "needs_review",
    source: "auto_param_test",
    auto_test_result_id: result.id,
    auto_test_seq: result.seq,
  };
  return {
    condition,
    usage,
    targetKey: usage === "exclude" ? "exclude_filters" : "entry_filters",
    rowKey: autoConditionRowKey(condition, usage),
  };
}

function autoDynamicIndicatorDefinition(indicatorKey: string): Record<string, any> | null {
  if (indicatorKey === "ma5_vs_ma10_pct") {
    return {
      indicator_key: "ma5_vs_ma10_pct",
      indicator_name: "5일선-10일선 이격률",
      calculation_type: "distance_pct",
      parameters: { target_indicator: "ma5", base_indicator: "ma10", unit: "%" },
      required_indicators: ["ma5", "ma10"],
      execution_supported: true,
      execution_status: "supported",
      execution_message: "distance_pct 계산 유형은 샘플 엔진에서 실행 가능합니다.",
      scope: "run_only",
    };
  }
  const maxReturnMatch = indicatorKey.match(/^max_return_1d_(\d+)d$/);
  if (maxReturnMatch) {
    const windowSize = Number(maxReturnMatch[1] || 30);
    return {
      indicator_key: indicatorKey,
      indicator_name: `최근 ${windowSize}일 최대 1일 수익률`,
      calculation_type: "rolling_high",
      parameters: { target_indicator: "return_1d", window: windowSize, unit: "%", include_current_day: true },
      required_indicators: ["return_1d"],
      execution_supported: true,
      execution_status: "supported",
      execution_message: "rolling_high 계산 유형은 샘플 엔진에서 실행 가능합니다.",
      scope: "run_only",
    };
  }
  return null;
}

function ensureAutoDynamicIndicator(goal: Record<string, any>, indicatorKey: string): Record<string, any> {
  const definition = autoDynamicIndicatorDefinition(indicatorKey);
  if (!definition) return goal;
  const existing = [...(goal.temporary_indicators || []), ...(goal.dynamic_indicators || [])].some((item: Record<string, any>) => String(item.indicator_key || item.suggested_indicator_key || "") === indicatorKey);
  if (existing) return goal;
  return {
    ...goal,
    temporary_indicators: [...(goal.temporary_indicators || []), definition],
  };
}

function isNewIndicatorCondition(condition: Record<string, any>, candidate?: Record<string, any>): boolean {
  return Boolean(
    candidate ||
    condition.validation_status === "new_indicator_required" ||
    condition.display_group === "formula_required" ||
    condition.source === "rule_base_candidate" ||
    condition.calculation_type ||
    condition.execution_status,
  );
}

function isSampleFilterExecutable(condition: Record<string, any>, candidate?: Record<string, any>): boolean {
  if (condition.execution_supported === true || candidate?.execution_supported === true) return true;
  const calculationType = String(condition.calculation_type || candidate?.calculation_type || "");
  return ["distance_pct", "rolling_high"].includes(calculationType);
}

function getNewIndicatorUsageStatus(condition: Record<string, any>, finalUsage: ConditionUsage, candidate?: Record<string, any>): NewIndicatorUsageStatus | null {
  if (!isNewIndicatorCondition(condition, candidate)) return null;
  if (isSampleFilterExecutable(condition, candidate)) return "filter_supported";
  if (finalUsage === "reference" || finalUsage === "off") return "not_blocking";
  return "filter_engine_required";
}

function newIndicatorStatusLabels(status: NewIndicatorUsageStatus | null): string[] {
  if (status === "filter_supported") return ["새 지표 필요", "계산 가능"];
  if (status === "not_blocking") return ["새 지표 필요", "비교 가능", "엔진 보완 필요"];
  if (status === "filter_engine_required") return ["새 지표 필요", "엔진 보완 필요"];
  return [];
}

function collectSampleBlockers(goal: Record<string, any> | null | undefined, finalUsageByRowId: FinalUsageMap): SampleBlocker[] {
  if (!goal) return [];
  const candidateByKey = new Map<string, Record<string, any>>();
  ([...(goal.temporary_indicators || []), ...(goal.unsupported_items || []), ...(goal.new_indicator_candidates || [])] as Array<Record<string, any>>).forEach((item) => {
    const key = String(item.indicator_key || item.suggested_indicator_key || "");
    if (key && !candidateByKey.has(key)) candidateByKey.set(key, item);
  });
  const rows = [
    ...((goal.entry_filters || []) as Array<Record<string, any>>).filter((condition) => condition.gpt_verify_selected !== false).map((condition, index) => ({ kind: "parsed_entry", condition, index, fallbackUsage: usageForCondition(condition, "entry_filters") })),
    ...((goal.reference_conditions || []) as Array<Record<string, any>>).map((condition, index) => ({ kind: "reference_condition", condition, index, fallbackUsage: "reference" as ConditionUsage })),
    ...((goal.exclude_filters || []) as Array<Record<string, any>>).filter((condition) => condition.gpt_verify_selected !== false).map((condition, index) => ({ kind: "parsed_exclude", condition, index, fallbackUsage: usageForCondition(condition, "exclude_filters") })),
  ];
  return rows.flatMap(({ kind, condition, index, fallbackUsage }) => {
    const rowId = conditionRowId(kind, condition, index);
    const finalUsage = finalUsageByRowId[rowId] || fallbackUsage;
    const indicatorKey = String(condition.indicator_key || condition.indicator || "");
    const candidate = candidateByKey.get(indicatorKey);
    const status = getNewIndicatorUsageStatus(condition, finalUsage, candidate);
    if (status !== "filter_engine_required") return [];
    const calculationType = String(condition.calculation_type || candidate?.calculation_type || "-");
    return [{
      rowId,
      indicatorKey,
      label: String(condition.label || candidate?.indicator_name || condition.source_text || indicatorKey || "신규 지표"),
      sourceText: String(condition.source_text || condition.natural_text || candidate?.source_text || "-"),
      expression: formatConditionExpression(condition, finalUsage),
      finalUsage,
      calculationType,
      requiredIndicators: (condition.required_indicators || candidate?.required_indicators || []) as string[],
      currentStatus: status,
      message: `${calculationType} 계산은 아직 샘플 필터 실행 엔진에서 지원되지 않습니다.`,
    }];
  });
}

function scrollToIndicatorCandidate(indicatorKey: string) {
  const target = document.getElementById(`gpt-candidate-${indicatorKey}`);
  target?.scrollIntoView({ behavior: "smooth", block: "center" });
  target?.classList.add("pattern-highlight-pulse");
  window.setTimeout(() => target?.classList.remove("pattern-highlight-pulse"), 1400);
}

function normalizeScenarioCandidates(payload: Record<string, any>): ScenarioCandidate[] {
  const source = Array.isArray(payload.scenario_candidates)
    ? payload.scenario_candidates
    : Array.isArray(payload.scenarios)
      ? payload.scenarios
      : [];

  return source.map((item: Record<string, any>, index: number) => {
    const entryConditions = item.entry_conditions || item.conditions || item.core_conditions || [];
    const riskFilters = item.risk_filters || [];
    const schemaCheck = inspectScenarioCandidateSchema(item);
    return {
      id: String(item.id || item.scenario_id || `scenario-${index + 1}`),
      name: String(item.scenario_name || item.name || item.title || `시나리오 후보 ${index + 1}`),
      summary: String(item.summary || item.intent || item.core || item.description || "핵심 조건 설명이 필요합니다."),
      entryConditions: Array.isArray(entryConditions) ? entryConditions.map(formatScenarioCondition) : [String(entryConditions)],
      addBuyStrategy: item.add_buy_plan ? formatAddBuyPlan(item.add_buy_plan) : String(item.add_buy_strategy || item.add_buy || item.scale_in_strategy || "추가매수 전략 검토 필요"),
      stopLossRule: String(item.stop_loss_rule || item.stop_loss || item.risk_control || "손절 기준 검토 필요"),
      fundingNote: String(item.funding_note || item.capital_efficiency || item.money_management || "자금 효율 관점 검토 필요"),
      status: "included" as ScenarioCandidateStatus,
      raw: {
        ...item,
        entry_conditions: Array.isArray(entryConditions) ? entryConditions : [],
        risk_filters: Array.isArray(riskFilters) ? riskFilters : [],
      },
      stringConditionCount: schemaCheck.stringConditionCount,
      invalidStructureCount: schemaCheck.invalidStructureCount,
      schemaWarnings: schemaCheck.warnings,
    };
  });
}

function inspectScenarioCandidateSchema(candidate: Record<string, any>) {
  const warnings: string[] = [];
  const entryConditions = candidate.entry_conditions || candidate.conditions || candidate.core_conditions;
  const riskFilters = candidate.risk_filters || [];
  let stringConditionCount = 0;
  let invalidStructureCount = 0;

  if (!Array.isArray(entryConditions)) {
    warnings.push("entry_conditions 배열이 필요합니다.");
    invalidStructureCount += 1;
  } else {
    stringConditionCount += entryConditions.filter((condition) => typeof condition === "string").length;
    invalidStructureCount += entryConditions.filter((condition) => typeof condition !== "string" && (typeof condition !== "object" || condition === null || Array.isArray(condition))).length;
  }

  if (Array.isArray(riskFilters)) {
    stringConditionCount += riskFilters.filter((condition) => typeof condition === "string").length;
    invalidStructureCount += riskFilters.filter((condition) => typeof condition !== "string" && (typeof condition !== "object" || condition === null || Array.isArray(condition))).length;
  } else if (riskFilters) {
    warnings.push("risk_filters는 배열이어야 합니다.");
    invalidStructureCount += 1;
  }

  if (stringConditionCount > 0) {
    warnings.push("GPT 응답에 문자열 조건이 포함되어 있습니다. DrCT는 객체형 조건을 권장하며, 지원 패턴은 자동 변환을 시도합니다.");
  }
  return { stringConditionCount, invalidStructureCount, warnings };
}

function scenarioJsonExampleText() {
  return JSON.stringify(DRCT_SCENARIO_JSON_EXAMPLE, null, 2);
}

function formatScenarioCondition(condition: unknown): string {
  if (typeof condition === "string") return condition;
  if (!condition || typeof condition !== "object" || Array.isArray(condition)) return "-";
  const item = condition as Record<string, any>;
  const indicatorKey = item.indicator_key ?? item.indicatorKey ?? "-";
  const operator = item.operator ?? "";
  const value = Array.isArray(item.value) ? `[${item.value.join(", ")}]` : item.value ?? "";
  const description = item.description ? ` · ${item.description}` : item.reason ? ` · ${item.reason}` : "";
  const action = item.action ? ` → ${item.action}` : "";
  return `${indicatorKey} ${operator} ${value}${action}${description}`.trim();
}

function formatScenarioConditionParts(condition: unknown): { expression: string; description: string } {
  if (typeof condition === "string") return { expression: condition, description: "" };
  if (!condition || typeof condition !== "object" || Array.isArray(condition)) return { expression: "-", description: "" };
  const item = condition as Record<string, any>;
  const indicatorKey = item.indicator_key ?? item.indicatorKey ?? "-";
  const operator = item.operator ?? "";
  const value = Array.isArray(item.value) ? `[${item.value.join(", ")}]` : item.value ?? "";
  return {
    expression: `${indicatorKey} ${operator} ${value}`.trim(),
    description: String(item.description || item.reason || item.role || ""),
  };
}

function formatAddBuyPlan(plan: unknown): string {
  if (!plan || typeof plan !== "object" || Array.isArray(plan)) return "추가매수 전략 없음";
  const item = plan as Record<string, any>;
  if (item.enabled === false) return "추가매수 사용 안함";
  const maxCount = item.max_count ?? item.maxCount ?? 0;
  const triggerBasis = item.trigger_basis ?? item.triggerBasis ?? "entry_price";
  const triggerLossPct = item.trigger_loss_pct ?? item.triggerLossPct ?? "-";
  const amountRatio = item.amount_ratio ?? item.amountRatio ?? 1;
  const stopLossBasis = item.stop_loss_basis ?? item.stopLossBasis ?? "average_price";
  const finalStopLossPct = item.final_stop_loss_pct ?? item.finalStopLossPct ?? "-";
  return `${triggerBasis === "average_price" ? "평균단가" : "최초 진입가"} 대비 ${triggerLossPct}% 하락 시 최대 ${maxCount}회, 1차 금액의 ${amountRatio}배 추가매수 · ${stopLossBasis === "average_price" ? "평균단가" : "진입가"} 기준 ${finalStopLossPct}% 손절`;
}

function scenarioPriorityLabel(priority: unknown): string {
  const value = String(priority || "medium").toLowerCase();
  if (value === "high") return "우선순위 높음";
  if (value === "low") return "낮음";
  return "보통";
}

function scenarioActionLabel(action: unknown): string {
  return {
    block_add_buy: "추가매수 차단",
    force_stop: "강제 손절 후보",
    exclude_entry: "진입 제외",
    warning_only: "경고만 표시",
  }[String(action || "")] || String(action || "경고만 표시");
}

function formatScenarioRiskFilter(filter: unknown): string {
  if (!filter || typeof filter !== "object" || Array.isArray(filter)) return formatScenarioCondition(filter);
  const item = filter as Record<string, any>;
  const base = formatScenarioCondition({ ...item, action: undefined });
  const reason = item.reason ? ` · ${item.reason}` : "";
  return `${base} → ${scenarioActionLabel(item.action)}${reason}`;
}

function scenarioCandidateStateLabel(candidate: ScenarioCandidate): string {
  if (candidate.status === "excluded") return "제외됨";
  if (candidate.stringConditionCount) return "형식 보정 필요";
  return "시뮬레이션 포함";
}

function ResearchStepper({
  title,
  steps,
  currentStep,
  onChangeStep,
}: {
  title: string;
  steps: ResearchStepperItem[];
  currentStep: string;
  onChangeStep: (step: string) => void;
}) {
  const activeStep = steps.find((step) => step.key === currentStep) || steps.find((step) => step.status === "active") || steps[0];
  return (
    <section className="pattern-research-common-stepper" aria-label={title}>
      <div className="pattern-research-stepper-head">
        <strong>{title}</strong>
        {activeStep ? <span>{activeStep.statusLabel}</span> : null}
      </div>
      <div className="pattern-research-stepper-track">
        {steps.map((step, index) => (
          <button
            key={step.key}
            className={`pattern-research-step-card pattern-research-step-card-${step.status}`}
            type="button"
            onClick={() => onChangeStep(step.key)}
          >
            <span className="pattern-research-step-number">{step.status === "complete" ? "✓" : index + 1}</span>
            <span className="pattern-research-step-title">{step.label.replace(/^\d+\.\s*/, "")}</span>
            <span className="pattern-research-step-status">{step.statusLabel}</span>
          </button>
        ))}
      </div>
      {activeStep ? <p className="pattern-research-step-description">{activeStep.description}</p> : null}
    </section>
  );
}

function PatternResearchPage() {
  const [researchMode, setResearchMode] = useState<ResearchMode>("rule_validation");
  const [scenarioStep, setScenarioStep] = useState<ScenarioSearchStep>("setup");
  const [scenarioGoal, setScenarioGoal] = useState<ScenarioGoalState>({
    tradeType: "swing",
    targetReturnPct: 5,
    holdingDays: 5,
    stopLossPct: -5,
    minSampleCount: 50,
  });
  const [scenarioRiskPlan, setScenarioRiskPlan] = useState<ScenarioRiskPlanState>({
    addBuyEnabled: true,
    maxAddBuyCount: 1,
    initialAmount: 1000000,
    addBuyAmountType: "same",
    addBuyTriggerLossPct: -5,
    finalStopLossBasis: "average_price",
    finalStopLossPct: -5,
  });
  const [scenarioGptPrompt, setScenarioGptPrompt] = useState("");
  const [showScenarioGptPrompt, setShowScenarioGptPrompt] = useState(false);
  const [scenarioGptResponseText, setScenarioGptResponseText] = useState("");
  const [scenarioCandidates, setScenarioCandidates] = useState<ScenarioCandidate[]>([]);
  const [scenarioCandidateParseError, setScenarioCandidateParseError] = useState("");
  const [scenarioParseMessage, setScenarioParseMessage] = useState("");
  const [scenarioValidationResult, setScenarioValidationResult] = useState<ScenarioValidationResponse | null>(null);
  const [scenarioValidationError, setScenarioValidationError] = useState("");
  const [scenarioValidationLoading, setScenarioValidationLoading] = useState(false);
  const [scenarioSimulationResult, setScenarioSimulationResult] = useState<ScenarioSimulationResponse | null>(null);
  const [scenarioSimulationError, setScenarioSimulationError] = useState("");
  const [scenarioSimulationLoading, setScenarioSimulationLoading] = useState(false);
  const [selectedScenarioSimulationResult, setSelectedScenarioSimulationResult] = useState<ScenarioSimulationResult | null>(null);
  const [activeTab, setActiveTab] = useState<TabKey>("setup");
  const [targetModalOpen, setTargetModalOpen] = useState(false);
  const [sampleTab, setSampleTab] = useState<SampleTab>("SUCCESS");
  const [stocks, setStocks] = useState<PatternResearchStock[]>([]);
  const [stockKeyword, setStockKeyword] = useState("");
  const [selectedStock, setSelectedStock] = useState<PatternResearchStock | null>(null);
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [goalText, setGoalText] = useState(DEFAULT_GOAL);
  const [useLlmAssist, setUseLlmAssist] = useState(false);
  const [parsed, setParsed] = useState<PatternGoalParseResponse | null>(null);
  const [gptGoalPrompt, setGptGoalPrompt] = useState("");
  const [showGptGoalPrompt, setShowGptGoalPrompt] = useState(false);
  const [showGptResultInput, setShowGptResultInput] = useState(true);
  const [showGptPackagePrompt, setShowGptPackagePrompt] = useState(false);
  const [gptGoalResultText, setGptGoalResultText] = useState("");
  const [gptGoalValidation, setGptGoalValidation] = useState<PatternGptGoalResultValidateResponse | null>(null);
  const [gptGoalValidationStatus, setGptGoalValidationStatus] = useState<GptValidationStatus>("idle");
  const [resolvedGptIndicatorKeys, setResolvedGptIndicatorKeys] = useState<string[]>([]);
  const [finalUsageByRowId, setFinalUsageByRowId] = useState<FinalUsageMap>({});
  const [focusedConditionRowIds, setFocusedConditionRowIds] = useState<string[]>([]);
  const [blockedBannerMessage, setBlockedBannerMessage] = useState("");
  const [currentRun, setCurrentRun] = useState<PatternResearchRun | null>(null);
  const [samples, setSamples] = useState<PatternResearchSample[]>([]);
  const [gptPackage, setGptPackage] = useState<PatternResearchGptPackage | null>(null);
  const [autoTestCandidates, setAutoTestCandidates] = useState<AutoParamCandidate[]>([]);
  const [autoTestCursor, setAutoTestCursor] = useState(0);
  const [autoTestResults, setAutoTestResults] = useState<AutoParamResult[]>([]);
  const [autoTesting, setAutoTesting] = useState(false);
  const [autoTestProgress, setAutoTestProgress] = useState("");
  const [selectedAutoTestResultId, setSelectedAutoTestResultId] = useState<string | null>(null);
  const [conditionsDirty, setConditionsDirty] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const gptValidationResultRef = useRef<HTMLDivElement | null>(null);

  const selectedAutoTestResult = autoTestResults.find((item) => item.id === selectedAutoTestResultId && item.status === "success") || null;
  const activeGptPackage = selectedAutoTestResult?.gptPackage || gptPackage;
  const summary = selectedAutoTestResult?.summary || currentRun?.summary || null;
  const parsedGoal = parsed?.parsed_goal || null;
  const confirmedConditions = [
    ...((parsedGoal?.success_criteria ? [parsedGoal.success_criteria] : []) as Array<Record<string, any>>),
    ...((parsedGoal?.failure_criteria ? [parsedGoal.failure_criteria] : []) as Array<Record<string, any>>),
    ...(((parsedGoal?.entry_filters || []) as Array<Record<string, any>>)),
    ...(((parsedGoal?.exclude_filters || []) as Array<Record<string, any>>)),
  ];
  const gptConditions = (gptGoalValidation?.validated_conditions || []) as Array<Record<string, any>>;
  const newIndicatorRequiredConditions = [
    ...gptConditions.filter((condition) => condition.validation_status === "new_indicator_required" && !resolvedGptIndicatorKeys.includes(String(condition.indicator_key || ""))),
    ...confirmedConditions.filter((condition) => condition.validation_status === "new_indicator_required"),
  ];
  const needsReviewCount = confirmedConditions.filter((condition) => condition.status === "needs_review" || condition.validation_status === "needs_review").length;
  const sampleBlockers = collectSampleBlockers(parsedGoal, finalUsageByRowId);
  const canCreateSamples = Boolean(parsed) && sampleBlockers.length === 0;
  const ruleStepItems: ResearchStepperItem[] = [
    {
      key: "setup",
      label: "1. 찾을 패턴 설정",
      description: "자연어 매매규칙을 입력하고 DrCT가 수식 후보로 해석할 조건을 확인합니다.",
      status: activeTab === "setup" ? "active" : parsed ? "complete" : "pending",
      statusLabel: activeTab === "setup" ? "진행 중" : parsed ? "완료" : "대기",
    },
    {
      key: "gptValidation",
      label: "2. 수식화 GPT 검증 및 확정",
      description: "수식 후보를 GPT 검증 결과와 비교해 포함 조건, 제외 조건, 비교용 조건을 확정합니다.",
      status: activeTab === "gptValidation" ? "active" : newIndicatorRequiredConditions.length || needsReviewCount ? "attention" : gptGoalValidation ? "complete" : "pending",
      statusLabel: activeTab === "gptValidation" ? "진행 중" : newIndicatorRequiredConditions.length || needsReviewCount ? "확인 필요" : gptGoalValidation ? "완료" : "대기",
    },
    {
      key: "samples",
      label: "3. 성공/실패 샘플 추출",
      description: "확정 조건으로 과거 가격 데이터를 검증하고 성공/실패/중립 샘플을 분리합니다.",
      status: activeTab === "samples" ? "active" : currentRun ? "complete" : "pending",
      statusLabel: activeTab === "samples" ? "진행 중" : currentRun ? "완료" : parsed ? "진행 가능" : "대기",
    },
    {
      key: "package",
      label: "4. GPT 연구 패키지",
      description: "성공/실패 샘플과 확정 조건을 GPT 연구 패키지로 정리해 복사합니다.",
      status: activeTab === "package" ? "active" : gptPackage ? "complete" : "pending",
      statusLabel: activeTab === "package" ? "진행 중" : gptPackage ? "완료" : currentRun ? "진행 가능" : "대기",
    },
  ];
  const diffRows = useMemo(() => {
    const labels: Record<string, string> = {
      close_vs_ma20_pct: "20일선 이격률",
      close_vs_ma60_pct: "60일선 이격률",
      volume_ratio_20: "거래량 20일 평균 배수",
      trading_value_ratio_20: "거래대금 20일 평균 배수",
      recent_3d_return: "최근 3일 수익률",
      recent_5d_return: "최근 5일 수익률",
      is_bullish_ratio: "양봉 비율",
      close_above_previous_high_ratio: "전일 고가 돌파 비율",
    };
    const avgSuccess = summary?.avg_success || {};
    const avgFailure = summary?.avg_failure || {};
    const differences = summary?.differences || {};
    return Object.keys(labels).map((key) => ({
      key,
      label: labels[key],
      success: avgSuccess[key],
      failure: avgFailure[key],
      diff: differences[key],
    }));
  }, [summary]);

  const loadStocks = async (keyword = stockKeyword) => {
    setLoading(true);
    setError("");
    try {
      const response = await repositories.patternResearch.fetchStocks({ keyword, limit: 30 });
      setStocks(response.items);
      setSelectedStock((prev) => prev ?? response.items[0] ?? null);
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : "분석 가능 종목을 불러오지 못했습니다.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadStocks("");
  }, []);

  useEffect(() => {
    if (!selectedStock?.last_price_date) return;
    const defaultStart = selectedStock.first_price_date
      ? maxDate(selectedStock.first_price_date, twoYearsBefore(selectedStock.last_price_date))
      : twoYearsBefore(selectedStock.last_price_date);
    setStartDate(defaultStart);
    setEndDate(selectedStock.last_price_date);
  }, [selectedStock?.stock_code]);

  const parseGoal = async () => {
    if (!goalText.trim()) {
      setError("찾고 싶은 매매패턴을 자연어로 입력해 주세요.");
      return;
    }
    setLoading(true);
    setError("");
    try {
      const response = await repositories.patternResearch.parseGoal(goalText, { use_llm: useLlmAssist, llm_mode: "assist" });
      setParsed(response);
      setFinalUsageByRowId({});
      setAutoTestCandidates([]);
      setAutoTestCursor(0);
      setAutoTestResults([]);
      setSelectedAutoTestResultId(null);
      setConditionsDirty(false);
      setMessage("매매목표 해석 초안을 생성했습니다.");
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : "매매목표를 해석하지 못했습니다.");
    } finally {
      setLoading(false);
    }
  };

  const updateParsedGoal = (updater: (goal: Record<string, any>) => Record<string, any>) => {
    setParsed((prev) => {
      if (!prev) return prev;
      const parsed_goal = updater({ ...prev.parsed_goal });
      return {
        ...prev,
        parsed_goal,
        entry_filters: parsed_goal.entry_filters || [],
        exclude_filters: parsed_goal.exclude_filters || [],
        needs_review_items: [...(parsed_goal.entry_filters || []), ...(parsed_goal.exclude_filters || [])].filter(
          (item) => item.status === "needs_review",
        ),
        warnings: parsed_goal.warnings || prev.warnings || [],
      };
    });
  };

  const updateCriteria = (kind: "success_criteria" | "failure_criteria", key: string, value: any) => {
    updateParsedGoal((goal) => {
      const criteria = { ...(goal[kind] || {}) };
      criteria[key] = value;
      if (kind === "success_criteria") {
        goal.target_return_pct = criteria.target_return_pct;
        goal.target_days = criteria.target_days;
        criteria.expression = `max_future_return_${criteria.target_days}d >= ${criteria.target_return_pct}`;
      } else {
        goal.stop_loss_pct = criteria.stop_loss_pct;
        criteria.target_days = goal.success_criteria?.target_days || criteria.target_days;
        criteria.expression = `min_future_return_${criteria.target_days}d <= ${criteria.stop_loss_pct}`;
      }
      criteria.source = "user_modified";
      goal[kind] = criteria;
      goal.success_rule = goal.success_criteria;
      goal.failure_rule = goal.failure_criteria;
      return goal;
    });
  };

  const updateFilter = (kind: "entry_filters" | "exclude_filters", index: number, updates: Record<string, any>) => {
    updateParsedGoal((goal) => {
      const rows = [...(goal[kind] || [])];
      const next = { ...rows[index], ...updates };
      if (updates.value !== undefined) next.expression = expressionForCondition(next);
      next.source = updates.source || "user_modified";
      rows[index] = next;
      goal[kind] = rows;
      goal.hypothesis_conditions = [...(goal.entry_filters || []), ...(goal.exclude_filters || [])];
      return goal;
    });
  };

  const updateFilterUsage = (kind: "entry_filters" | "exclude_filters", index: number, usage: ConditionUsage) => {
    updateParsedGoal((goal) => {
      const sourceRows = [...(goal[kind] || [])];
      const current = sourceRows[index];
      if (!current) return goal;
      sourceRows.splice(index, 1);
      goal[kind] = sourceRows;
      if (usage === "off") {
        const disabled = {
          ...current,
          apply_to_samples: false,
          apply_mode: "off",
          apply_mode_label: usageLabel(usage),
          status: "disabled",
          source: "user_modified",
        };
        goal.reference_conditions = [...(goal.reference_conditions || []), disabled];
      } else if (usage === "exclude") {
        const next = {
          ...current,
          exclude_when_true: true,
          apply_to_samples: true,
          apply_mode_label: usageLabel(usage),
          source: "user_modified",
        };
        goal.exclude_filters = [...(goal.exclude_filters || []), next];
      } else {
        const next = {
          ...current,
          exclude_when_true: false,
          apply_to_samples: usage === "include",
          apply_mode_label: usageLabel(usage),
          source: "user_modified",
        };
        goal.entry_filters = [...(goal.entry_filters || []), next];
      }
      goal.hypothesis_conditions = [...(goal.entry_filters || []), ...(goal.exclude_filters || [])];
      return goal;
    });
  };

  const buildFinalParsedGoal = (goal: Record<string, any>, usageOverrides: FinalUsageMap = finalUsageByRowId): Record<string, any> => {
    const next = { ...goal };
    const sourceEntries = ((goal.entry_filters || []) as Array<Record<string, any>>).filter((condition) => condition.gpt_verify_selected !== false);
    const sourceExcludes = ((goal.exclude_filters || []) as Array<Record<string, any>>).filter((condition) => condition.gpt_verify_selected !== false);
    const sourceReferences = ((goal.reference_conditions || []) as Array<Record<string, any>>);
    const entryFilters: Array<Record<string, any>> = [];
    const excludeFilters: Array<Record<string, any>> = [];
    const referenceConditions: Array<Record<string, any>> = [];

    sourceEntries.forEach((condition, index) => {
      const usage = usageOverrides[conditionRowId("parsed_entry", condition, index)] || usageForCondition(condition, "entry_filters");
      if (usage === "include") entryFilters.push({ ...condition, apply_to_samples: true, exclude_when_true: false, apply_mode_label: usageLabel("include") });
      else if (usage === "exclude") excludeFilters.push({ ...condition, apply_to_samples: true, exclude_when_true: true, apply_mode_label: usageLabel("exclude") });
      else if (usage === "reference") referenceConditions.push({ ...condition, apply_to_samples: false, exclude_when_true: false, apply_mode_label: usageLabel("reference") });
    });

    sourceReferences.forEach((condition, index) => {
      const usage = usageOverrides[conditionRowId("reference_condition", condition, index)] || "reference";
      if (usage === "include") entryFilters.push({ ...condition, apply_to_samples: true, exclude_when_true: false, apply_mode_label: usageLabel("include") });
      else if (usage === "exclude") excludeFilters.push({ ...condition, apply_to_samples: true, exclude_when_true: true, apply_mode_label: usageLabel("exclude") });
      else if (usage === "reference") referenceConditions.push({ ...condition, apply_to_samples: false, exclude_when_true: false, apply_mode_label: usageLabel("reference") });
    });

    sourceExcludes.forEach((condition, index) => {
      const usage = usageOverrides[conditionRowId("parsed_exclude", condition, index)] || usageForCondition(condition, "exclude_filters");
      if (usage === "include") entryFilters.push({ ...condition, apply_to_samples: true, exclude_when_true: false, apply_mode_label: usageLabel("include") });
      else if (usage === "exclude") excludeFilters.push({ ...condition, apply_to_samples: true, exclude_when_true: true, apply_mode_label: usageLabel("exclude") });
      else if (usage === "reference") referenceConditions.push({ ...condition, apply_to_samples: false, exclude_when_true: false, apply_mode_label: usageLabel("reference") });
    });

    next.entry_filters = entryFilters;
    next.exclude_filters = excludeFilters;
    next.reference_conditions = referenceConditions;
    next.hypothesis_conditions = [...entryFilters, ...excludeFilters];
    const selectedIndicatorKeys = new Set([...entryFilters, ...excludeFilters, ...referenceConditions].map((item) => String(item.indicator_key || item.indicator || "")));
    const temporaryByKey = new Map(
      ((goal.temporary_indicators || []) as Array<Record<string, any>>).map((item) => [String(item.indicator_key || ""), item]),
    );
    ([...(goal.unsupported_items || []), ...(goal.new_indicator_candidates || [])] as Array<Record<string, any>>).forEach((item) => {
      const key = String(item.indicator_key || item.suggested_indicator_key || "");
      if (!key || !selectedIndicatorKeys.has(key) || temporaryByKey.has(key)) return;
      temporaryByKey.set(key, {
        indicator_key: key,
        indicator_name: item.indicator_name || item.suggested_indicator_name || key,
        calculation_type: item.calculation_type,
        parameters: item.parameters || {},
        required_indicators: item.required_indicators || [],
        execution_supported: item.execution_supported,
        execution_status: item.execution_status,
        execution_message: item.execution_message || item.reason,
        scope: "run_only",
      });
    });
    next.temporary_indicators = Array.from(temporaryByKey.values());
    return next;
  };

  const buildAutoParamCandidates = (): AutoParamCandidate[] => {
    if (!parsed?.parsed_goal) return [];
    const baseline = buildFinalParsedGoal(parsed.parsed_goal);
    const knownKeys = new Set<string>();
    [...(baseline.entry_filters || []), ...(baseline.exclude_filters || []), ...(baseline.reference_conditions || [])].forEach((item: Record<string, any>) => {
      const key = String(item.indicator_key || item.indicator || "");
      if (key) knownKeys.add(key);
    });
    const options = [
      { key: "close_vs_ma20_pct", usage: "exclude", operator: ">=", values: [10], label: "20일선 이격 과열 제외" },
      { key: "max_return_1d_30d", usage: "exclude", operator: ">=", values: [20], label: "30일 내 과열 경험 제외" },
      { key: "recent_5d_return", usage: "exclude", operator: ">=", values: [12], label: "최근 5일 급등 제외" },
      { key: "ma5_vs_ma10_pct", usage: "include", operator: "between", values: [[-3, 3]], label: "5/10일선 근접 포함" },
      { key: "trading_value_ratio_20", usage: "include", operator: ">=", values: [1.3], label: "거래대금 배수 포함" },
      { key: "close_vs_ma20_pct", usage: "exclude", operator: ">=", values: [8, 12, 15], label: "20일선 이격 과열 제외" },
      { key: "max_return_1d_30d", usage: "exclude", operator: ">=", values: [25, 15], label: "30일 내 과열 경험 제외" },
      { key: "ma5_vs_ma10_pct", usage: "include", operator: "between", values: [[-2, 2], [-5, 5], [0, 3]], label: "5/10일선 근접 포함" },
      { key: "trading_value_ratio_20", usage: "include", operator: ">=", values: [1.5, 1.2, 2], label: "거래대금 배수 포함" },
      { key: "recent_3d_return", usage: "exclude", operator: ">=", values: [10, 20, 12, 15], label: "최근 3일 급등 제외" },
      { key: "recent_5d_return", usage: "exclude", operator: ">=", values: [15, 10, 20], label: "최근 5일 급등 제외" },
      { key: "ma60_slope_5d", usage: "include", operator: ">=", values: [0.3, 0, 0.1, 0.5], label: "60일선 기울기 포함" },
      { key: "max_return_1d_30d", usage: "include", operator: ">=", values: [10, 15], label: "30일 내 고점 경험 포함" },
      { key: "close_vs_ma20_pct", usage: "include", operator: "between", values: [[-5, 5], [-3, 5]], label: "20일선 눌림 범위 포함" },
    ] as Array<{ key: string; usage: "include" | "exclude"; operator: string; values: any[]; label: string }>;
    const candidates: AutoParamCandidate[] = [];
    const seen = new Set<string>([autoConditionHash(baseline), ...autoTestResults.map((item) => item.hash)]);
    options.forEach((option) => {
      if (knownKeys.size && !knownKeys.has(option.key) && !["recent_5d_return", "max_return_1d_30d", "ma60_slope_5d"].includes(option.key)) return;
      option.values.forEach((value) => {
        const next = cloneGoal(baseline);
        const condition = {
          indicator_key: option.key,
          operator: option.operator,
          value,
          apply_to_samples: true,
          exclude_when_true: option.usage === "exclude",
          apply_mode_label: usageLabel(option.usage),
          source: "auto_parameter_test",
          expression: option.operator === "between" && Array.isArray(value)
            ? `${option.key} between ${value[0]} and ${value[1]}`
            : `${option.key} ${option.operator} ${value}`,
        };
        const targetKey = option.usage === "exclude" ? "exclude_filters" : "entry_filters";
        next.entry_filters = (next.entry_filters || []).filter((item: Record<string, any>) => String(item.indicator_key || item.indicator || "") !== option.key);
        next.exclude_filters = (next.exclude_filters || []).filter((item: Record<string, any>) => String(item.indicator_key || item.indicator || "") !== option.key);
        next.reference_conditions = (next.reference_conditions || []).filter((item: Record<string, any>) => String(item.indicator_key || item.indicator || "") !== option.key);
        next[targetKey] = [...(next[targetKey] || []), condition];
        next.hypothesis_conditions = [...(next.entry_filters || []), ...(next.exclude_filters || [])];
        const executableGoal = ensureAutoDynamicIndicator(next, option.key);
        const hash = autoConditionHash(executableGoal);
        if (seen.has(hash)) return;
        seen.add(hash);
        const valueLabel = Array.isArray(value) ? `${value[0]}~${value[1]}` : String(value);
        candidates.push({
          id: `auto-${candidates.length + 1}-${option.key}-${option.usage}-${valueLabel}`,
          label: `${option.label} ${valueLabel}`,
          description: `${option.key} ${option.operator} ${valueLabel}`,
          parsedGoal: executableGoal,
          changedCondition: condition,
          hash,
        });
      });
    });
    return candidates;
  };

  const clearAutoParamTests = () => {
    if (!window.confirm("자동 수치변경 테스트 결과를 모두 초기화하시겠습니까? 기준 샘플 결과는 유지됩니다.")) return;
    setAutoTestCandidates([]);
    setAutoTestCursor(0);
    setAutoTestResults([]);
    setAutoTestProgress("");
    setSelectedAutoTestResultId(null);
    if (currentRun) void loadSamples(sampleTab, null);
    setMessage("자동 테스트 결과를 초기화했습니다.");
  };

  const runAutoParamTests = async () => {
    if (!selectedStock || !parsed || !currentRun || !summary) {
      setError("먼저 기준 샘플을 생성한 뒤 자동 수치변경 테스트를 실행해 주세요.");
      return;
    }
    const candidates = autoTestCandidates.length ? autoTestCandidates : buildAutoParamCandidates();
    if (!candidates.length) {
      setError("자동으로 변경할 수 있는 숫자 조건 후보가 없습니다.");
      return;
    }
    const start = autoTestCandidates.length ? autoTestCursor : 0;
    const batch = candidates.slice(start, start + 5);
    setAutoTestCandidates(candidates);
    setAutoTesting(true);
    setAutoTestProgress(`0/${batch.length}`);
    setError("");
    const baselineRate = Number((currentRun.summary || {}).success_rate || 0);
    const baselineTotal = Number((currentRun.summary || {}).total_samples || 0);
    const nextResults: AutoParamResult[] = [];
    for (let index = 0; index < batch.length; index += 1) {
      const candidate = batch[index];
      setAutoTestProgress(`${index + 1}/${batch.length}`);
      try {
        const simulated = await repositories.patternResearch.simulateRun({
          research_name: `${selectedStock.stock_name} auto parameter test`,
          stock_codes: [selectedStock.stock_code],
          start_date: startDate,
          end_date: endDate,
          goal_text: goalText,
          parsed_goal: candidate.parsedGoal,
        });
        const normalizedSamples = simulated.samples.map((sample, sampleIndex) => ({
          ...sample,
          id: Number(sample.id || sampleIndex + 1),
          run_id: Number(sample.run_id || 0),
          created_at: sample.created_at || "",
        })) as PatternResearchSample[];
        nextResults.push({
          ...candidate,
          seq: start + index + 1,
          status: "success",
          summary: simulated.summary,
          samples: normalizedSamples,
          gptPackage: simulated.gpt_package,
        });
        const delta = Number(simulated.summary?.success_rate || 0) - baselineRate;
        if (delta >= 5 && Number(simulated.summary?.total_samples || 0) >= Math.max(30, baselineTotal * 0.4)) {
          setSelectedAutoTestResultId(candidate.id);
        }
      } catch (nextError) {
        nextResults.push({
          ...candidate,
          seq: start + index + 1,
          status: "error",
          error: nextError instanceof Error ? nextError.message : "시뮬레이션에 실패했습니다.",
        });
      }
    }
    setAutoTestResults((prev) => [...prev, ...nextResults]);
    setAutoTestCursor(Math.min(start + batch.length, candidates.length));
    setAutoTesting(false);
    setAutoTestProgress("");
    setMessage("자동 수치변경 테스트 배치를 완료했습니다.");
  };

  const applyAutoTestConditionToValidation = (result: AutoParamResult) => {
    if (result.status === "error" || !parsed) return;
    const { condition, usage, targetKey } = buildConditionFromAutoResult(result);
    const nextGoal = cloneGoal(parsed.parsed_goal || {});
    nextGoal.entry_filters = [...(nextGoal.entry_filters || [])];
    nextGoal.exclude_filters = [...(nextGoal.exclude_filters || [])];
    nextGoal.reference_conditions = [...(nextGoal.reference_conditions || [])];
    const targetRows = nextGoal[targetKey] as Array<Record<string, any>>;
    const rowKind = targetKey === "exclude_filters" ? "parsed_exclude" : "parsed_entry";
    let focusedRowId = "";
    let duplicate = false;
    const sameAutoIndex = targetRows.findIndex((row) =>
      row.source === "auto_param_test" &&
      String(row.indicator_key || row.indicator || "") === String(condition.indicator_key || "") &&
      Boolean(row.exclude_when_true) === (usage === "exclude")
    );
    const sameDirectIndex = targetRows.findIndex((row) =>
      row.source !== "auto_param_test" &&
      String(row.indicator_key || row.indicator || "") === String(condition.indicator_key || "")
    );
    const exactIndex = targetRows.findIndex((row) =>
      row.source === "auto_param_test" &&
      String(row.indicator_key || row.indicator || "") === String(condition.indicator_key || "") &&
      String(row.operator || "") === String(condition.operator || "") &&
      autoValueKey(row.value) === autoValueKey(condition.value)
    );
    if (exactIndex >= 0) {
      duplicate = true;
      focusedRowId = conditionRowId(rowKind, targetRows[exactIndex], exactIndex);
    } else {
      const targetIndex = sameAutoIndex >= 0 ? sameAutoIndex : sameDirectIndex;
      if (targetIndex >= 0) {
        targetRows[targetIndex] = { ...targetRows[targetIndex], ...condition };
        focusedRowId = conditionRowId(rowKind, targetRows[targetIndex], targetIndex);
      } else {
        targetRows.push(condition);
        focusedRowId = conditionRowId(rowKind, condition, targetRows.length - 1);
      }
      nextGoal[targetKey] = targetRows;
      nextGoal.hypothesis_conditions = [...(nextGoal.entry_filters || []), ...(nextGoal.exclude_filters || [])];
      const goalWithDynamicIndicator = ensureAutoDynamicIndicator(nextGoal, String(condition.indicator_key || ""));
      setParsed({
        ...parsed,
        parsed_goal: goalWithDynamicIndicator,
        entry_filters: goalWithDynamicIndicator.entry_filters || [],
        exclude_filters: goalWithDynamicIndicator.exclude_filters || [],
        needs_review_items: [...(goalWithDynamicIndicator.entry_filters || []), ...(goalWithDynamicIndicator.exclude_filters || [])].filter((item: Record<string, any>) => item.status === "needs_review"),
        warnings: goalWithDynamicIndicator.warnings || parsed.warnings || [],
      });
    }
    if (focusedRowId) {
      setFinalUsageByRowId((prev) => ({ ...prev, [focusedRowId]: usage }));
      setFocusedConditionRowIds([focusedRowId]);
    }
    setConditionsDirty(true);
    setSelectedAutoTestResultId(null);
    setBlockedBannerMessage("자동 테스트 조건을 2단계 조건표에 반영했습니다. 조건값과 사용 방식을 확인한 뒤 3단계에서 샘플을 다시 생성하세요.");
    setActiveTab("gptValidation");
    setMessage(duplicate ? "이미 반영된 자동 테스트 조건입니다. 해당 행으로 이동합니다." : "자동 테스트 조건을 2단계 조건표에 반영했습니다.");
    window.setTimeout(() => {
      document.querySelector(".pattern-new-indicator-focus")?.scrollIntoView({ behavior: "smooth", block: "center" });
    }, 120);
  };

  const addCandidateToGoal = (candidate: Record<string, any>, applyToSamples: boolean) => {
    const isGptCandidate = candidate.source === "gpt_candidate";
    if (candidate.validation_status === "new_indicator_required" && applyToSamples) {
      setMessage("이 조건은 신규 지표 등록 또는 1회성 사용 처리가 먼저 필요합니다. 신규 지표 후보를 확인해 주세요.");
      scrollToIndicatorCandidate(candidate.indicator_key || "");
      return;
    }
    const category = candidate.category === "exclude_filter" ? "exclude_filters" : "entry_filters";
    const existingRows = [
      ...((parsed?.parsed_goal?.success_criteria ? [parsed.parsed_goal.success_criteria] : []) as Array<Record<string, any>>),
      ...((parsed?.parsed_goal?.failure_criteria ? [parsed.parsed_goal.failure_criteria] : []) as Array<Record<string, any>>),
      ...((parsed?.parsed_goal?.entry_filters || []) as Array<Record<string, any>>),
      ...((parsed?.parsed_goal?.exclude_filters || []) as Array<Record<string, any>>),
    ];
    const duplicateCandidate = existingRows.some(
      (row) =>
        conditionIdentity({ ...row, category: row.category || category }) === conditionIdentity({ ...candidate, category }) ||
        (row.expression && candidate.expression && row.expression === candidate.expression),
    );
    if (duplicateCandidate) {
      setMessage("이미 동일한 조건이 존재합니다. 기존 조건은 유지하고 GPT 후보는 참고 이력으로만 확인해 주세요.");
      return;
    }
    updateParsedGoal((goal) => {
      const next = {
        source_text: candidate.source_text || candidate.label || (isGptCandidate ? "GPT 후보" : "LLM 후보"),
        natural_text: candidate.source_text || candidate.label || (isGptCandidate ? "GPT 후보" : "LLM 후보"),
        label: candidate.label || candidate.source_text || (isGptCandidate ? "GPT 후보" : "LLM 후보"),
        indicator: candidate.indicator_key || candidate.indicator,
        indicator_key: candidate.indicator_key || candidate.indicator,
        operator: candidate.operator || "=",
        value: candidate.value,
        expression: candidate.expression || expressionForCondition(candidate),
        apply_to_samples: applyToSamples,
        exclude_when_true: candidate.category === "exclude_filter" || candidate.exclude_when_true,
        status: candidate.validation_status === "valid" ? "applied" : "needs_review",
        interpretation_status_label: candidate.validation_status === "valid" ? "확정" : "확인 필요",
        apply_mode_label: applyToSamples ? usageLabel(candidate.category === "exclude_filter" || candidate.exclude_when_true ? "exclude" : "include") : usageLabel("reference"),
        source: isGptCandidate ? "gpt_candidate_confirmed" : "llm_candidate_confirmed",
        original_source: isGptCandidate ? "gpt_candidate" : "llm_candidate",
        validation_status: candidate.validation_status,
        validation_message: candidate.validation_message,
        reason: candidate.reason,
      };
      const rows = [...(goal[category] || [])];
      const duplicate = rows.some(
        (row) =>
          (row.indicator_key || row.indicator) === next.indicator_key &&
          row.operator === next.operator &&
          JSON.stringify(row.value ?? null) === JSON.stringify(next.value ?? null),
      );
      if (!duplicate) rows.push(next);
      goal[category] = rows;
      goal.hypothesis_conditions = [...(goal.entry_filters || []), ...(goal.exclude_filters || [])];
      goal.confirmed_conditions = [...(goal.confirmed_conditions || []), next];
      return goal;
    });
    setMessage(isGptCandidate ? "GPT 후보를 조건표에 반영했습니다." : "LLM 후보를 조건표에 반영했습니다.");
  };

  const markGptCandidateDecision = (decision: string, targetText?: string | Record<string, any>) => {
    const labels: Record<string, string> = {
      reference: "조건 후보로 표시했습니다.",
      exclude: "후보를 제외 처리했습니다.",
      one_time: "신규 지표 후보를 1회성 사용으로 표시했습니다.",
    };
    const targetCandidate = typeof targetText === "object" ? (targetText as Record<string, any>) : null;
    const targetKey = targetCandidate ? String(targetCandidate.indicator_key || "") : String(targetText || "");
    if (decision === "one_time" && targetCandidate) {
      const isExecutable = targetCandidate.execution_supported === true || ["distance_pct", "rolling_high"].includes(String(targetCandidate.calculation_type || ""));
      if (!isExecutable) {
        setError(targetCandidate.execution_message || "아직 샘플 실행 엔진이 지원하지 않는 계산 유형입니다.");
        return;
      }
      updateParsedGoal((goal) => {
        const temporary = [...(goal.temporary_indicators || [])];
        const parameters = targetCandidate.parameters || {};
        const required = targetCandidate.required_indicators || [];
        if (!temporary.some((item) => item.indicator_key === targetCandidate.indicator_key)) {
          temporary.push({
            indicator_key: targetCandidate.indicator_key,
            indicator_name: targetCandidate.indicator_name || targetCandidate.indicator_key,
            calculation_type: targetCandidate.calculation_type,
            parameters: {
              target_indicator: parameters.target_indicator || required[0],
              base_indicator: parameters.base_indicator || required[1],
              unit: parameters.unit || "%",
            },
            required_indicators: required,
            execution_supported: true,
            execution_status: "supported",
            execution_message: targetCandidate.execution_message || `${targetCandidate.calculation_type || "dynamic"} 계산 유형은 샘플 엔진에서 실행 가능합니다.`,
            scope: "run_only",
          });
        }
        goal.temporary_indicators = temporary;
        return goal;
      });
      setGptGoalValidation((prev) => prev ? {
        ...prev,
        validated_conditions: (prev.validated_conditions || []).map((condition) =>
          condition.indicator_key === targetCandidate.indicator_key
            ? {
                ...condition,
                validation_status: "valid",
                validation_message: "1회성 사용 처리되어 비교용 지표 또는 조건 후보로 검토할 수 있습니다.",
                execution_supported: true,
                execution_status: "supported",
              }
            : condition,
        ),
        new_indicator_candidates: (prev.new_indicator_candidates || []).map((candidate) =>
          candidate.indicator_key === targetCandidate.indicator_key
            ? { ...candidate, decision_status: "run_only", execution_supported: true, execution_status: "supported" }
            : candidate,
        ),
      } : prev);
    }
    if (targetKey && ["reference", "exclude", "one_time"].includes(decision)) {
      setResolvedGptIndicatorKeys((prev) => (prev.includes(targetKey) ? prev : [...prev, targetKey]));
    }
    setMessage(`${labels[decision] || "처리했습니다."}${targetKey ? ` (${targetKey})` : ""}`);
  };

  const copyGptGoalPrompt = async () => {
    if (!goalText.trim()) {
      setError("먼저 매매목표를 입력해 주세요.");
      return;
    }
    setLoading(true);
    setError("");
    try {
      const promptParsedGoal = parsed?.parsed_goal ? buildFinalParsedGoal(parsed.parsed_goal) : null;
      const response = await repositories.patternResearch.fetchGptGoalParsePrompt(goalText, promptParsedGoal);
      setGptGoalPrompt(response.prompt_text);
      setShowGptGoalPrompt(true);
      await navigator.clipboard.writeText(response.prompt_text);
      setMessage("GPT 목표 해석 요청문을 복사했습니다.");
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : "GPT 목표 해석 요청문 생성에 실패했습니다.");
    } finally {
      setLoading(false);
    }
  };

  const validateGptGoalResult = async () => {
    const scrollToValidationResult = () => {
      window.setTimeout(() => {
        gptValidationResultRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
      }, 0);
    };
    if (!gptGoalResultText.trim()) {
      setError("GPT 결과 JSON을 붙여넣어 주세요.");
      return;
    }
    setLoading(true);
    setError("");
    setGptGoalValidationStatus("validating");
    setGptGoalValidation(null);
    setResolvedGptIndicatorKeys([]);
    try {
      const response = await repositories.patternResearch.validateGptGoalResult({
        goal_text: goalText,
        gpt_result_text: gptGoalResultText,
        parsed_goal: parsed?.parsed_goal || null,
      });
      setGptGoalValidation(response);
      if (response.status === "success") {
        setGptGoalValidationStatus("success");
        setShowGptResultInput(false);
        setMessage("GPT 결과 검증을 완료했습니다.");
      } else {
        const validationError = gptValidationErrorMessage(response, "GPT 결과 검증에 실패했습니다.");
        setGptGoalValidationStatus("failed");
        setError(validationError);
        setMessage("");
      }
      scrollToValidationResult();
    } catch (nextError) {
      const validationError = nextError instanceof Error ? nextError.message : "GPT 결과 검증에 실패했습니다.";
      setGptGoalValidationStatus("failed");
      setGptGoalValidation({
        status: "failed",
        validated_conditions: [],
        new_indicator_candidates: [],
        unsupported_items: [],
        warnings: [],
        interpretation_conflicts: [],
        raw_error: validationError,
        validation_message: validationError,
        parsed_json: {},
      });
      setError(validationError);
      setMessage("");
      scrollToValidationResult();
    } finally {
      setLoading(false);
    }
  };

  const saveIndicatorCandidate = async (candidate: Record<string, any>) => {
    setLoading(true);
    setError("");
    try {
      await repositories.analysisIndicators.createCandidate({
        source_type: "gpt_goal_parse",
        source_text: candidate.source_text,
        suggested_indicator_key: candidate.indicator_key,
        suggested_indicator_name: candidate.indicator_name,
        description: candidate.description,
        calculation_type: candidate.calculation_type,
        formula_description: candidate.formula_description,
        parameters_json: JSON.stringify(candidate.parameters || {}, null, 2),
        required_indicators_json: JSON.stringify(candidate.required_indicators || [], null, 2),
        usage_json: JSON.stringify(candidate.usage || [], null, 2),
        lookahead_risk: candidate.lookahead_risk ? 1 : 0,
        validation_status: candidate.validation_status,
        validation_message: candidate.validation_message,
        execution_supported: candidate.execution_supported ? 1 : 0,
        execution_status: candidate.execution_status,
        execution_message: candidate.execution_message,
        decision_status: "pending",
        is_active: 1,
      });
      setMessage("GPT 제안 지표 후보를 저장했습니다. 지표 설정 화면에서 검토할 수 있습니다.");
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : "GPT 제안 지표 후보 저장에 실패했습니다.");
    } finally {
      setLoading(false);
    }
  };

  const focusSampleBlockersInValidation = () => {
    const rowIds = sampleBlockers.map((item) => item.rowId);
    setFocusedConditionRowIds(rowIds);
    setBlockedBannerMessage("샘플 생성이 보류된 신규 지표를 확인해 주세요. 포함/제외 조건으로 사용하려면 계산 엔진 지원이 필요합니다. 현재는 비교용으로만 사용하거나 사용안함으로 변경한 뒤 샘플을 생성할 수 있습니다.");
    setActiveTab("gptValidation");
  };

  const createRun = async (usageOverrides: FinalUsageMap = finalUsageByRowId) => {
    if (!selectedStock) {
      setError("분석할 종목을 선택해 주세요.");
      return;
    }
    if (!parsed) {
      setError("먼저 매매목표를 해석해 주세요.");
      return;
    }
    setLoading(true);
    setError("");
    try {
      const finalParsedGoal = buildFinalParsedGoal(parsed.parsed_goal, usageOverrides);
      const created = await repositories.patternResearch.createRun({
        research_name: `${selectedStock.stock_name} 패턴 연구`,
        stock_codes: [selectedStock.stock_code],
        start_date: startDate,
        end_date: endDate,
        goal_text: goalText,
        parsed_goal: finalParsedGoal,
      });
      const run = await repositories.patternResearch.fetchRun(created.run_id);
      setCurrentRun(run);
      setSamples((await repositories.patternResearch.fetchSamples(created.run_id, sampleTab)).items);
      setGptPackage(await repositories.patternResearch.fetchGptPackage(created.run_id));
      setActiveTab("samples");
      setFocusedConditionRowIds([]);
      setBlockedBannerMessage("");
      setAutoTestCandidates([]);
      setAutoTestCursor(0);
      setAutoTestResults([]);
      setSelectedAutoTestResultId(null);
      setConditionsDirty(false);
      setMessage("성공/실패 샘플을 생성했습니다.");
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : "성공/실패 샘플 생성에 실패했습니다.");
    } finally {
      setLoading(false);
    }
  };

  const resolveBlockersAndCreateRun = async (usage: ConditionUsage) => {
    if (!sampleBlockers.length) {
      await createRun();
      return;
    }
    const nextUsage = sampleBlockers.reduce<FinalUsageMap>((acc, blocker) => ({ ...acc, [blocker.rowId]: usage }), { ...finalUsageByRowId });
    setFinalUsageByRowId(nextUsage);
    await createRun(nextUsage);
  };

  const loadSamples = async (label: SampleTab, selectedResult: AutoParamResult | null = selectedAutoTestResult) => {
    if (!currentRun) return;
    setSampleTab(label);
    if (selectedResult?.samples) {
      setSamples(resultSamplesForTab(selectedResult.samples, label));
      return;
    }
    setSamples((await repositories.patternResearch.fetchSamples(currentRun.id, label)).items);
  };

  const copyPrompt = async () => {
    if (!activeGptPackage?.gpt_prompt_text) return;
    await navigator.clipboard.writeText(activeGptPackage.gpt_prompt_text);
    setMessage("GPT에 붙여넣을 연구 요청문을 복사했습니다.");
  };

  const openCsv = () => {
    if (!currentRun) return;
    window.open(repositories.patternResearch.csvUrl(currentRun.id), "_blank", "noopener,noreferrer");
  };

  const scenarioSelectedStocks = selectedStock ? [selectedStock] : [];
  const scenarioMaxInputAmount = scenarioRiskPlan.initialAmount * (1 + (scenarioRiskPlan.addBuyEnabled ? scenarioRiskPlan.maxAddBuyCount : 0));
  const scenarioSetupReady = Boolean(
    scenarioGoal.targetReturnPct
    && scenarioGoal.holdingDays
    && scenarioGoal.stopLossPct
    && scenarioSelectedStocks.length > 0,
  );

  const buildScenarioGptPrompt = () => {
    const stockSummary = scenarioSelectedStocks.length
      ? scenarioSelectedStocks.map((stock) => `${stock.stock_name}(${stock.stock_code})`).join(", ")
      : "선택 종목 없음";
    const prompt = [
      "당신은 종목 추천자가 아니라 매매 시나리오 연구 설계자입니다.",
      "",
      "아래 DrCT 데이터 프로파일과 사용자의 목표를 바탕으로 실제 시뮬레이션 가능한 매매 시나리오 후보를 제안해 주세요.",
      "",
      "[중요 원칙]",
      "- 매수/매도 추천을 하지 마세요.",
      "- 결과는 투자 지시가 아니라 연구 후보와 훈련 후보로 표현하세요.",
      "- DrCT가 제공한 사용 가능 지표를 우선 사용하세요.",
      "- 지원되지 않는 지표가 필요하면 대체 수식 후보를 함께 제안하세요.",
      "- 각 시나리오는 진입 조건, 추가매수 전략, 손절 기준, 자금 효율 관점으로 구성하세요.",
      "- 출력은 반드시 JSON 형식으로 작성하세요.",
      "",
      "[탐색 목표]",
      `- 투자 유형: ${TRADE_TYPE_LABELS[scenarioGoal.tradeType]}`,
      `- 목표: 진입 후 ${scenarioGoal.holdingDays}거래일 안에 +${scenarioGoal.targetReturnPct}% 이상`,
      `- 실패 기준: ${scenarioGoal.stopLossPct}% 이하 하락`,
      `- 최소 후보 수: ${scenarioGoal.minSampleCount}개`,
      "",
      "[대상 종목]",
      `- ${stockSummary}`,
      "",
      "[기본 대응전략]",
      `- 추가매수 사용: ${scenarioRiskPlan.addBuyEnabled ? "사용" : "사용 안함"}`,
      `- 최대 추가매수 횟수: ${scenarioRiskPlan.addBuyEnabled ? scenarioRiskPlan.maxAddBuyCount : 0}회`,
      `- 1차 매수금액: ${fmtWon(scenarioRiskPlan.initialAmount)}`,
      `- 최대 투입금액: ${fmtWon(scenarioMaxInputAmount)}`,
      `- 추가매수 방식: 동일 금액`,
      `- 최종 손절 기준: ${scenarioRiskPlan.finalStopLossBasis === "average_price" ? "평균단가 기준" : "최초가 기준"}`,
      `- 최종 손절률: ${scenarioRiskPlan.finalStopLossPct}%`,
      "",
      "[사용 가능한 지표]",
      ...SCENARIO_AVAILABLE_INDICATORS.map((indicator) => `- ${indicator}`),
      "",
      "[JSON 출력 형식]",
      scenarioJsonExampleText(),
      "",
      "[JSON 작성 규칙]",
      "entry_conditions와 risk_filters는 반드시 객체 배열로 작성하세요.",
      "",
      "잘못된 예:",
      JSON.stringify(DRCT_SCENARIO_BAD_JSON_EXAMPLE, null, 2),
      "",
      "올바른 예:",
      JSON.stringify({
        entry_conditions: DRCT_SCENARIO_JSON_EXAMPLE.scenario_candidates[0].entry_conditions.slice(0, 2),
      }, null, 2),
      "",
      "주의:",
      "- entry_conditions 안에 문자열을 넣지 마세요.",
      "- indicator_key는 반드시 DrCT 사용 가능 지표 목록 중 하나를 사용하세요.",
      "- operator는 >, >=, <, <=, =, between 중 하나만 사용하세요.",
      "- between의 value는 반드시 숫자 2개 배열로 작성하세요. 예: [-5, 5]",
    ].join("\n");
    setScenarioGptPrompt(prompt);
    setShowScenarioGptPrompt(true);
    setScenarioStep("gpt_candidates");
    setMessage("GPT 시나리오 생성 요청문을 만들었습니다.");
    return prompt;
  };

  const copyScenarioGptPrompt = async () => {
    const prompt = scenarioGptPrompt || buildScenarioGptPrompt();
    if (!prompt) return;
    await navigator.clipboard.writeText(prompt);
    setMessage("객체형 JSON 형식이 반영된 GPT 요청문을 복사했습니다.");
  };

  const validateScenarioGptResponse = () => {
    setScenarioCandidateParseError("");
    setScenarioParseMessage("");
    try {
      const payload = JSON.parse(scenarioGptResponseText);
      const candidates = normalizeScenarioCandidates(payload);
      if (!candidates.length) {
        setScenarioCandidateParseError("scenario_candidates 또는 scenarios 배열을 찾지 못했습니다.");
        setScenarioCandidates([]);
        return;
      }
      setScenarioCandidates(candidates);
      setScenarioValidationResult(null);
      setScenarioValidationError("");
      setScenarioSimulationResult(null);
      setSelectedScenarioSimulationResult(null);
      setScenarioParseMessage(`GPT 시나리오 후보 ${candidates.length}개를 읽었습니다.`);
    } catch (nextError) {
      setScenarioCandidateParseError(nextError instanceof Error ? `JSON 형식 오류: ${nextError.message}` : "JSON 형식 오류");
      setScenarioCandidates([]);
      setScenarioValidationResult(null);
      setScenarioSimulationResult(null);
      setSelectedScenarioSimulationResult(null);
    }
  };

  const updateScenarioCandidateStatus = (id: string, status: ScenarioCandidateStatus) => {
    setScenarioCandidates((prev) => prev.map((candidate) => candidate.id === id ? { ...candidate, status } : candidate));
    setScenarioValidationResult(null);
    setScenarioValidationError("");
    setScenarioSimulationResult(null);
    setSelectedScenarioSimulationResult(null);
  };

  const validateScenarioCandidates = async () => {
    const included = scenarioCandidates.filter((candidate) => candidate.status === "included");
    if (!included.length) {
      setScenarioValidationError("검증할 포함 후보가 없습니다.");
      return;
    }
    setScenarioValidationLoading(true);
    setScenarioValidationError("");
    try {
      const response = await repositories.patternResearch.validateAiScenarioCandidates({
        goal: {
          trade_type: scenarioGoal.tradeType,
          target_return_pct: scenarioGoal.targetReturnPct,
          holding_days: scenarioGoal.holdingDays,
          stop_loss_pct: scenarioGoal.stopLossPct,
          min_sample_count: scenarioGoal.minSampleCount,
        },
        risk_plan: {
          add_buy_enabled: scenarioRiskPlan.addBuyEnabled,
          max_add_buy_count: scenarioRiskPlan.maxAddBuyCount,
          initial_amount: scenarioRiskPlan.initialAmount,
          add_buy_trigger_loss_pct: scenarioRiskPlan.addBuyTriggerLossPct,
          final_stop_loss_basis: scenarioRiskPlan.finalStopLossBasis,
          final_stop_loss_pct: scenarioRiskPlan.finalStopLossPct,
        },
        candidates: included.map((candidate) => ({
          ...candidate.raw,
          scenario_name: candidate.raw.scenario_name || candidate.name,
          entry_conditions: candidate.raw.entry_conditions || candidate.raw.conditions || candidate.raw.core_conditions || [],
          add_buy_plan: candidate.raw.add_buy_plan || {},
          risk_filters: candidate.raw.risk_filters || [],
        })),
      });
      setScenarioValidationResult(response);
      setScenarioSimulationResult(null);
      setSelectedScenarioSimulationResult(null);
      setScenarioStep("validation");
      if ((response.summary.simulation_ready || 0) > 0) {
        setMessage("AI 시나리오 조건 검증을 완료했습니다. 시뮬레이션 가능한 후보가 있습니다.");
      } else if ((response.summary.invalid || response.summary.structure_error || 0) > 0) {
        setMessage("검증은 완료되었지만, 시뮬레이션 가능한 후보가 없습니다. GPT 응답 형식을 확인하세요.");
      } else if ((response.summary.unsupported || 0) > 0) {
        setMessage("검증은 완료되었지만, 지원하지 않는 지표가 포함되어 시뮬레이션 가능한 후보가 없습니다.");
      } else {
        setMessage("검증은 완료되었지만, 시뮬레이션 가능한 후보가 없습니다. 조건을 확인하세요.");
      }
    } catch (nextError) {
      setScenarioValidationError(nextError instanceof Error ? nextError.message : "시나리오 조건 검증 중 오류가 발생했습니다. GPT 응답 JSON 구조와 네트워크 상태를 확인해 주세요.");
    } finally {
      setScenarioValidationLoading(false);
    }
  };

  const simulateScenarioCandidates = async () => {
    const readyCandidates = (scenarioValidationResult?.validated_candidates || []).filter((candidate) => candidate.is_simulation_ready);
    if (!readyCandidates.length) {
      setScenarioSimulationError("시뮬레이션 가능한 검증 후보가 없습니다.");
      return;
    }
    if (!scenarioSelectedStocks.length) {
      setScenarioSimulationError("시뮬레이션 대상 종목이 필요합니다.");
      return;
    }
    setScenarioSimulationLoading(true);
    setScenarioSimulationError("");
    try {
      const response = await repositories.patternResearch.simulateAiScenarioCandidates({
        goal: {
          trade_type: scenarioGoal.tradeType,
          target_return_pct: scenarioGoal.targetReturnPct,
          holding_days: scenarioGoal.holdingDays,
          stop_loss_pct: scenarioGoal.stopLossPct,
          min_sample_count: scenarioGoal.minSampleCount,
        },
        risk_plan: {
          add_buy_enabled: scenarioRiskPlan.addBuyEnabled,
          max_add_buy_count: scenarioRiskPlan.maxAddBuyCount,
          initial_amount: scenarioRiskPlan.initialAmount,
          add_buy_trigger_loss_pct: scenarioRiskPlan.addBuyTriggerLossPct,
          final_stop_loss_basis: scenarioRiskPlan.finalStopLossBasis,
          final_stop_loss_pct: scenarioRiskPlan.finalStopLossPct,
        },
        stocks: scenarioSelectedStocks.map((stock) => ({ stock_code: stock.stock_code, stock_name: stock.stock_name })),
        candidates: readyCandidates.map((candidate) => candidate.normalized_candidate),
      });
      setScenarioSimulationResult(response);
      setSelectedScenarioSimulationResult(response.scenario_results[0] || null);
      setScenarioStep("results");
      setMessage("AI 시나리오 시뮬레이션을 완료했습니다.");
    } catch (nextError) {
      setScenarioSimulationError(nextError instanceof Error ? nextError.message : "시나리오 시뮬레이션 중 오류가 발생했습니다. 검증 결과와 선택 종목의 가격 데이터 상태를 확인해 주세요.");
    } finally {
      setScenarioSimulationLoading(false);
    }
  };

  return (
    <div className="pattern-research-page space-y-4">
      <PageHeader
        title="매매패턴 AI연구"
        description="자연어 매매규칙 검증과 AI 시나리오 자동탐색을 통해 성공/실패 샘플을 분석하고, 훈련 가능한 매매 기준을 만듭니다."
      />
      {message ? <div className="alert success">{message}</div> : null}
      {error ? <div className="alert danger">{error}</div> : null}

      <section className="pattern-research-mode-switch" aria-label="연구 모드 선택">
        <button
          className={`pattern-research-mode-card ${researchMode === "rule_validation" ? "pattern-research-mode-card-active" : ""}`}
          type="button"
          onClick={() => setResearchMode("rule_validation")}
        >
          <span className="pattern-research-mode-badge">{researchMode === "rule_validation" ? "현재 모드" : "선택 가능"}</span>
          <strong>내 규칙 검증</strong>
          <span>내가 생각한 매매규칙을 자연어로 입력하고, 성공/실패 샘플로 검증합니다.</span>
        </button>
        <button
          className={`pattern-research-mode-card ${researchMode === "ai_scenario_search" ? "pattern-research-mode-card-active" : ""}`}
          type="button"
          onClick={() => setResearchMode("ai_scenario_search")}
        >
          <span className="pattern-research-mode-badge">{researchMode === "ai_scenario_search" ? "현재 모드" : "선택 가능"}</span>
          <strong>AI 시나리오 자동탐색</strong>
          <span>목표 수익률과 대상 종목을 기준으로 GPT가 후보를 제안하고 DrCT가 검증합니다.</span>
        </button>
      </section>

      {researchMode === "rule_validation" ? (
        <>
      <ResearchStepper
        title="연구 흐름"
        steps={ruleStepItems}
        currentStep={activeTab}
        onChangeStep={(step) => setActiveTab(step as TabKey)}
      />

      <div className="pattern-research-tabs">
        {[
          ["settings", "연구 설정"],
          ["analysis", "성공/실패 분석"],
          ["gpt", "GPT 연구 패키지"],
        ].map(([key, label]) => (
          <button
            key={key}
            className={`pattern-research-tab-button ${activeTab === key ? "active" : ""}`}
            type="button"
            onClick={() => setActiveTab(key as TabKey)}
          >
            {label}
          </button>
        ))}
      </div>

      <div className="pattern-target-summary-bar">
        <div>
          <span>분석 대상</span>
          <strong>{selectedStock ? `${selectedStock.stock_name} · ${selectedStock.stock_code} · ${selectedStock.market || "-"}` : "선택된 종목 없음"}</strong>
        </div>
        <div>
          <span>기간</span>
          <strong>{startDate || "-"} ~ {endDate || "-"}</strong>
        </div>
        <div>
          <span>가격 데이터</span>
          <strong>{fmtNumber(selectedStock?.price_count, 0)}개</strong>
        </div>
        <button className="btn btn-secondary" type="button" onClick={() => setTargetModalOpen(true)}>분석 대상 변경</button>
      </div>

      {targetModalOpen ? (
        <div className="pattern-modal-backdrop" role="presentation" onMouseDown={() => setTargetModalOpen(false)}>
          <div className="pattern-target-modal" role="dialog" aria-modal="true" onMouseDown={(event) => event.stopPropagation()}>
            <SectionCard title="분석 대상 설정">
              <div className="pattern-stock-search">
                <input
                  className="input-control"
                  value={stockKeyword}
                  onChange={(event) => setStockKeyword(event.target.value)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" && !event.nativeEvent.isComposing) void loadStocks();
                  }}
                  placeholder="종목명 또는 코드 검색"
                />
                <button className="btn btn-secondary" type="button" disabled={loading} onClick={() => void loadStocks()}>
                  <Search size={15} /> 검색
                </button>
              </div>
              <div className="pattern-stock-list">
                {stocks.map((stock) => (
                  <button
                    key={stock.stock_code}
                    type="button"
                    className={`pattern-stock-item ${selectedStock?.stock_code === stock.stock_code ? "selected" : ""}`}
                    onClick={() => setSelectedStock(stock)}
                  >
                    <strong>{stock.stock_name}</strong>
                    <span>{stock.stock_code} · {stock.market || "-"} · {fmtNumber(stock.price_count, 0)}개</span>
                    <small>{stock.first_price_date} ~ {stock.last_price_date}</small>
                  </button>
                ))}
                {stocks.length === 0 ? <EmptyState message="가격 데이터가 있는 종목이 없습니다." /> : null}
              </div>
              <div className="pattern-date-grid">
                <label><span>분석 시작일</span><input className="input-control" type="date" value={startDate} onChange={(event) => setStartDate(event.target.value)} /></label>
                <label><span>분석 종료일</span><input className="input-control" type="date" value={endDate} onChange={(event) => setEndDate(event.target.value)} /></label>
              </div>
              <p className="pattern-help-text">선택한 종목의 수집 기간을 기본값으로 설정합니다. 필요하면 직접 수정할 수 있습니다.</p>
              <div className="pattern-action-row">
                <button className="btn btn-secondary" type="button" onClick={() => setTargetModalOpen(false)}>취소</button>
                <button className="btn btn-primary" type="button" onClick={() => setTargetModalOpen(false)}>적용</button>
              </div>
            </SectionCard>
          </div>
        </div>
      ) : null}

      {activeTab === "setup" ? (
        <div className="pattern-step-panel">
          <SectionCard title="1. 찾을 패턴 설정">
            <p className="pattern-step-description">
              자연어 목표를 입력하면 DrCT가 1차 수식 후보를 만들고, GPT 검증 대상으로 보낼 항목을 선택합니다.
            </p>
            <label className="pattern-goal-input">
              <span>찾고 싶은 매매패턴</span>
              <textarea className={parsed ? "is-compact" : ""} value={goalText} onChange={(event) => setGoalText(event.target.value)} />
            </label>
            <div className="pattern-sentence-guide">
              한 문장에 하나의 조건을 적으면 DrCT가 더 정확하게 수식 후보를 만듭니다. 체크한 항목은 2단계 GPT 검증 대상으로 전달됩니다.
            </div>
            <div className="pattern-action-row">
              <button className="btn btn-secondary" type="button" disabled={loading} onClick={parseGoal}>목표 해석하기</button>
            </div>
            <PatternFormulaSummary parsed={parsed} />
            <PatternSetupReviewPanel parsed={parsed} onUpdateCriteria={updateCriteria} onUpdateFilter={updateFilter} onNext={() => setActiveTab("gptValidation")} />
          </SectionCard>
        </div>
      ) : null}

      {activeTab === "gptValidation" ? (
        <div className="pattern-step-panel">
          <SectionCard title="2. 수식화 GPT 검증 및 확정">
            <div className="pattern-condition-help">
              1단계에서 체크한 항목은 GPT 검증 대상으로 보고, 2단계에서 포함 조건·제외 조건·비교용·사용안함 중 실제 연구 반영 방식을 확정합니다.
            </div>
            <PatternVerifyDecisionPanel
              parsed={parsed}
              loading={loading}
              promptText={gptGoalPrompt}
              showPrompt={showGptGoalPrompt}
              showResultInput={showGptResultInput}
              resultText={gptGoalResultText}
              validation={gptGoalValidation}
              validationStatus={gptGoalValidationStatus}
              resultRef={gptValidationResultRef}
              finalUsageByRowId={finalUsageByRowId}
              focusedRowIds={focusedConditionRowIds}
              blockedBannerMessage={blockedBannerMessage}
              onFinalUsageChange={(rowId, usage) => setFinalUsageByRowId((prev) => ({ ...prev, [rowId]: usage }))}
              onTogglePrompt={() => setShowGptGoalPrompt((prev) => !prev)}
              onToggleResultInput={() => setShowGptResultInput((prev) => !prev)}
              onCopyPrompt={copyGptGoalPrompt}
              onChangeResultText={(value) => {
                setGptGoalResultText(value);
                setShowGptResultInput(true);
                setGptGoalValidation(null);
                setGptGoalValidationStatus("idle");
                setResolvedGptIndicatorKeys([]);
              }}
              onValidate={validateGptGoalResult}
              onApplyCandidate={addCandidateToGoal}
              onSaveIndicatorCandidate={saveIndicatorCandidate}
              onMarkDecision={markGptCandidateDecision}
              onUpdateCriteria={updateCriteria}
              onUpdateFilter={updateFilter}
              onChangeUsage={updateFilterUsage}
              onNext={() => setActiveTab("samples")}
            />
          </SectionCard>
        </div>
      ) : null}

      {activeTab === "samples" ? (
        <div className="pattern-step-panel">
          <SectionCard title="3. 성공/실패 샘플 추출">
            <p className="pattern-step-description">
              2단계에서 확정한 조건으로 과거 가격 데이터에서 성공/실패 샘플을 생성하고, GPT 연구 패키지로 넘기기 전 샘플 품질을 확인합니다.
            </p>
            <PatternFormulaSummary parsed={parsed} />
            {conditionsDirty ? <div className="pattern-sample-stale-warning">조건이 변경되었습니다. 현재 샘플 결과는 이전 조건 기준입니다. 3단계에서 샘플을 다시 생성하세요.</div> : null}
            <SampleReadinessCardV2
              parsed={parsed}
              blockers={sampleBlockers}
              canCreateSamples={canCreateSamples}
              onUseAsReference={() => void resolveBlockersAndCreateRun("reference")}
              onTurnOff={() => void resolveBlockersAndCreateRun("off")}
              onGoToGpt={focusSampleBlockersInValidation}
            />
            {sampleBlockers.length ? (
              <div className="alert warning">미해결 신규 지표 조건이 있어 포함/제외 조건으로 바로 쓰기 어렵습니다. 신규 지표 후보를 먼저 확인해 주세요.</div>
            ) : null}
            <div className="pattern-action-row">
              <button className="btn btn-primary" type="button" disabled={loading || !parsed || !canCreateSamples} onClick={() => void createRun()}>
                확정 조건으로 성공/실패 샘플 생성
              </button>
            </div>
            {!currentRun || !summary ? <EmptyState message="샘플 생성 후 결과 요약과 목록이 표시됩니다." /> : (
              <>
                <SampleStepReview summary={summary} onNext={() => setActiveTab("package")} />
                <AutoParamTestPanelV2
                  baselineSummary={currentRun.summary}
                  results={autoTestResults}
                  totalCandidates={autoTestCandidates.length}
                  cursor={autoTestCursor}
                  running={autoTesting}
                  progress={autoTestProgress}
                  selectedId={selectedAutoTestResultId}
                  onRunNext={() => void runAutoParamTests()}
                  onClear={clearAutoParamTests}
                  onSelect={(result) => {
                    setSelectedAutoTestResultId(result.id);
                    setSamples(resultSamplesForTab(result.samples || [], sampleTab));
                  }}
                  onApplyToConditions={applyAutoTestConditionToValidation}
                  onShowBaseline={() => {
                    setSelectedAutoTestResultId(null);
                    void loadSamples(sampleTab, null);
                  }}
                />
                {summary.sample_filter_warning ? <div className="alert warning">{summary.sample_filter_warning}</div> : null}
                <SampleTable samples={samples} sampleTab={sampleTab} onChangeTab={loadSamples} summary={summary} />
              </>
            )}
          </SectionCard>
        </div>
      ) : null}

      {activeTab === "package" ? (
        <div className="pattern-step-panel">
          <SectionCard title="4. GPT 연구 패키지">
            <p className="pattern-step-description">
              성공/실패 샘플과 확정 조건을 GPT 분석용 연구 패키지로 정리합니다. 복사 전에 포함 정보와 요청 목적을 확인하세요.
            </p>
            <div className={`auto-param-test-selected-banner ${selectedAutoTestResult ? "" : "is-baseline"}`}>
              <strong>{selectedAutoTestResult ? `이 GPT 패키지는 자동 테스트 #${selectedAutoTestResult.seq} 결과를 기준으로 생성되었습니다.` : "이 GPT 패키지는 기준 샘플 결과를 기준으로 생성되었습니다."}</strong>
              {selectedAutoTestResult ? <span>{autoResultInterpretation(selectedAutoTestResult, currentRun?.summary)}</span> : <span>자동 테스트 결과를 선택하면 4단계 패키지도 선택 결과 기준으로 전환됩니다.</span>}
            </div>
            {conditionsDirty ? <div className="pattern-sample-stale-warning">조건표가 변경되었습니다. GPT 패키지 생성 전 3단계에서 샘플을 다시 생성하는 것을 권장합니다.</div> : null}
            {!activeGptPackage ? <EmptyState message="샘플 생성 후 GPT 연구 패키지를 만들 수 있습니다." /> : (
              <GptPackageReview
                gptPackage={activeGptPackage}
                showPrompt={showGptPackagePrompt}
                onTogglePrompt={() => setShowGptPackagePrompt((prev) => !prev)}
                onCopyPrompt={copyPrompt}
                onOpenCsv={openCsv}
              />
            )}
          </SectionCard>
        </div>
      ) : null}

      {activeTab === "settings" ? (
        <div className="pattern-research-layout">
          <SectionCard title="분석 대상 설정">
            <div className="pattern-stock-search">
              <input
                className="input-control"
                value={stockKeyword}
                onChange={(event) => setStockKeyword(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === "Enter" && !event.nativeEvent.isComposing) void loadStocks();
                }}
                placeholder="종목명 또는 코드 검색"
              />
              <button className="btn btn-secondary" type="button" disabled={loading} onClick={() => void loadStocks()}>
                <Search size={15} /> 검색
              </button>
            </div>
            <div className="pattern-stock-list">
              {stocks.map((stock) => (
                <button
                  key={stock.stock_code}
                  type="button"
                  className={`pattern-stock-item ${selectedStock?.stock_code === stock.stock_code ? "selected" : ""}`}
                  onClick={() => setSelectedStock(stock)}
                >
                  <strong>{stock.stock_name}</strong>
                  <span>{stock.stock_code} · {stock.market || "-"} · {fmtNumber(stock.price_count, 0)}건</span>
                  <small>{stock.first_price_date} ~ {stock.last_price_date}</small>
                </button>
              ))}
              {stocks.length === 0 ? <EmptyState message="가격 데이터가 있는 종목이 없습니다." /> : null}
            </div>
            <div className="pattern-date-grid">
              <label><span>분석 시작일</span><input className="input-control" type="date" value={startDate} onChange={(event) => setStartDate(event.target.value)} /></label>
              <label><span>분석 종료일</span><input className="input-control" type="date" value={endDate} onChange={(event) => setEndDate(event.target.value)} /></label>
            </div>
          </SectionCard>

          <SectionCard title="매매목표 설정 및 해석">
            <label className="pattern-goal-input">
              <span>찾고 싶은 매매패턴</span>
              <textarea value={goalText} onChange={(event) => setGoalText(event.target.value)} />
            </label>
            <div className="pattern-sentence-guide">
              조건은 한 문장씩 입력해 주세요. 마침표(.) 또는 줄바꿈으로 구분하면 LLM 보조 해석 정확도가 높아집니다.
            </div>
            <div className="pattern-action-row">
              <label className="pattern-llm-toggle">
                <input type="checkbox" checked={useLlmAssist} onChange={(event) => setUseLlmAssist(event.target.checked)} />
                <span>LLM 보조 해석 사용</span>
              </label>
              <button className="btn btn-secondary" type="button" disabled={loading} onClick={parseGoal}>목표 해석하기</button>
              <button className="btn btn-primary" type="button" disabled={loading || !parsed} onClick={() => void createRun()}>기준으로 샘플 생성</button>
            </div>
            <GoalInterpretation parsed={parsed} onUpdateCriteria={updateCriteria} onUpdateFilter={updateFilter} onChangeUsage={updateFilterUsage} />
            <LlmAssistPanel parsed={parsed} onApplyCandidate={addCandidateToGoal} />
            <GptGoalResultPanelV2
              loading={loading}
              promptText={gptGoalPrompt}
              showPrompt={showGptGoalPrompt}
              resultText={gptGoalResultText}
              validation={gptGoalValidation}
              validationStatus={gptGoalValidationStatus}
              resultRef={gptValidationResultRef}
              onTogglePrompt={() => setShowGptGoalPrompt((prev) => !prev)}
              onCopyPrompt={copyGptGoalPrompt}
              onChangeResultText={(value) => {
                setGptGoalResultText(value);
                setGptGoalValidation(null);
                setGptGoalValidationStatus("idle");
              }}
              onValidate={validateGptGoalResult}
              onApplyCandidate={addCandidateToGoal}
              onSaveIndicatorCandidate={saveIndicatorCandidate}
              onMarkDecision={markGptCandidateDecision}
            />
          </SectionCard>
        </div>
      ) : null}

      {activeTab === "analysis" ? (
        <SectionCard title="성공/실패 분석">
          {!currentRun || !summary ? <EmptyState message="연구 설정 탭에서 샘플을 먼저 생성해 주세요." /> : (
            <>
              <div className="pattern-sample-kpi-grid">
                <Kpi label="전체 후보일" value={fmtNumber(summary.total_samples, 0)} />
                <Kpi label="원시 후보일" value={fmtNumber(summary.total_raw_candidate_days, 0)} />
                <Kpi label="진입조건 후" value={fmtNumber(summary.total_after_entry_filters, 0)} />
                <Kpi label="제외조건 후" value={fmtNumber(summary.total_after_exclude_filters, 0)} />
                <Kpi label="성공 샘플" value={fmtNumber(summary.success_count, 0)} />
                <Kpi label="실패 샘플" value={fmtNumber(summary.failure_count, 0)} />
                <Kpi label="중립 샘플" value={fmtNumber(summary.neutral_count, 0)} />
                <Kpi label="성공률" value={fmtPercent(summary.success_rate)} />
                <Kpi label="실패율" value={fmtPercent(summary.failure_rate)} />
              </div>
              {summary.sample_filter_warning ? <div className="alert warning">{summary.sample_filter_warning}</div> : null}
              <div className="table-shell">
                <table className="data-table compact-table pattern-diff-table">
                  <thead><tr><th>지표명</th><th className="numeric-cell">성공 평균</th><th className="numeric-cell">실패 평균</th><th className="numeric-cell">차이</th><th>해석 힌트</th></tr></thead>
                  <tbody>
                    {diffRows.map((row) => (
                      <tr key={row.key}>
                        <td>{row.label}</td>
                        <td className="numeric-cell">{fmtNumber(row.success)}</td>
                        <td className="numeric-cell">{fmtNumber(row.failure)}</td>
                        <td className="numeric-cell">{fmtNumber(row.diff)}</td>
                        <td>{Number(row.diff || 0) > 0 ? "성공 샘플에서 더 높게 나타납니다." : "실패 샘플과 비교 검토가 필요합니다."}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <SampleTable samples={samples} sampleTab={sampleTab} onChangeTab={loadSamples} />
            </>
          )}
        </SectionCard>
      ) : null}

      {activeTab === "gpt" ? (
        <SectionCard title="GPT 연구 패키지">
          {!gptPackage ? <EmptyState message="성공/실패 샘플 생성 후 GPT 연구 패키지가 표시됩니다." /> : (
            <>
              <div className="pattern-action-row">
                <button className="btn btn-secondary" type="button" onClick={copyPrompt}><Clipboard size={15} /> 요청문 복사</button>
                <button className="btn btn-secondary" type="button" onClick={openCsv}><Download size={15} /> CSV 다운로드</button>
              </div>
              <textarea className="pattern-gpt-prompt" readOnly value={gptPackage.gpt_prompt_text} />
            </>
          )}
        </SectionCard>
      ) : null}
        </>
      ) : (
        <ScenarioSearchShell
          step={scenarioStep}
          goal={scenarioGoal}
          riskPlan={scenarioRiskPlan}
          stocks={scenarioSelectedStocks}
          availableIndicators={SCENARIO_AVAILABLE_INDICATORS}
          gptPrompt={scenarioGptPrompt}
          showGptPrompt={showScenarioGptPrompt}
          gptResponseText={scenarioGptResponseText}
          candidates={scenarioCandidates}
          validationResult={scenarioValidationResult}
          validationError={scenarioValidationError}
          validationLoading={scenarioValidationLoading}
          simulationResult={scenarioSimulationResult}
          simulationError={scenarioSimulationError}
          simulationLoading={scenarioSimulationLoading}
          selectedSimulationResult={selectedScenarioSimulationResult}
          parseError={scenarioCandidateParseError}
          parseMessage={scenarioParseMessage}
          setupReady={scenarioSetupReady}
          maxInputAmount={scenarioMaxInputAmount}
          onChangeStep={setScenarioStep}
          onChangeGoal={(updates) => setScenarioGoal((prev) => ({ ...prev, ...updates }))}
          onChangeRiskPlan={(updates) => setScenarioRiskPlan((prev) => ({ ...prev, ...updates }))}
          onBuildPrompt={buildScenarioGptPrompt}
          onCopyPrompt={() => void copyScenarioGptPrompt()}
          onTogglePrompt={() => setShowScenarioGptPrompt((prev) => !prev)}
          onChangeResponseText={(value) => {
            setScenarioGptResponseText(value);
            setScenarioCandidateParseError("");
            setScenarioParseMessage("");
            setScenarioValidationResult(null);
            setScenarioValidationError("");
            setScenarioSimulationResult(null);
            setSelectedScenarioSimulationResult(null);
          }}
          onValidateResponse={validateScenarioGptResponse}
          onValidateScenarios={() => void validateScenarioCandidates()}
          onSimulateScenarios={() => void simulateScenarioCandidates()}
          onSelectSimulationResult={setSelectedScenarioSimulationResult}
          onSendToTrainingGuide={(result) => {
            setSelectedScenarioSimulationResult(result);
            setScenarioStep("training_guide");
          }}
          onChangeCandidateStatus={updateScenarioCandidateStatus}
        />
      )}
    </div>
  );
}

function Kpi({ label, value }: { label: string; value: string }) {
  return <div className="pattern-kpi-card"><span>{label}</span><strong>{value}</strong></div>;
}

function ScenarioSearchShell({
  step,
  goal,
  riskPlan,
  stocks,
  availableIndicators,
  gptPrompt,
  showGptPrompt,
  gptResponseText,
  candidates,
  validationResult,
  validationError,
  validationLoading,
  simulationResult,
  simulationError,
  simulationLoading,
  selectedSimulationResult,
  parseError,
  parseMessage,
  setupReady,
  maxInputAmount,
  onChangeStep,
  onChangeGoal,
  onChangeRiskPlan,
  onBuildPrompt,
  onCopyPrompt,
  onTogglePrompt,
  onChangeResponseText,
  onValidateResponse,
  onValidateScenarios,
  onSimulateScenarios,
  onSelectSimulationResult,
  onSendToTrainingGuide,
  onChangeCandidateStatus,
}: {
  step: ScenarioSearchStep;
  goal: ScenarioGoalState;
  riskPlan: ScenarioRiskPlanState;
  stocks: PatternResearchStock[];
  availableIndicators: string[];
  gptPrompt: string;
  showGptPrompt: boolean;
  gptResponseText: string;
  candidates: ScenarioCandidate[];
  validationResult: ScenarioValidationResponse | null;
  validationError: string;
  validationLoading: boolean;
  simulationResult: ScenarioSimulationResponse | null;
  simulationError: string;
  simulationLoading: boolean;
  selectedSimulationResult: ScenarioSimulationResult | null;
  parseError: string;
  parseMessage: string;
  setupReady: boolean;
  maxInputAmount: number;
  onChangeStep: (step: ScenarioSearchStep) => void;
  onChangeGoal: (updates: Partial<ScenarioGoalState>) => void;
  onChangeRiskPlan: (updates: Partial<ScenarioRiskPlanState>) => void;
  onBuildPrompt: () => void;
  onCopyPrompt: () => void;
  onTogglePrompt: () => void;
  onChangeResponseText: (value: string) => void;
  onValidateResponse: () => void;
  onValidateScenarios: () => void;
  onSimulateScenarios: () => void;
  onSelectSimulationResult: (result: ScenarioSimulationResult) => void;
  onSendToTrainingGuide: (result: ScenarioSimulationResult) => void;
  onChangeCandidateStatus: (id: string, status: ScenarioCandidateStatus) => void;
}) {
  const includedCandidates = candidates.filter((candidate) => candidate.status === "included");
  const validationSummary = validationResult?.summary;
  const simulationReadyCount = (validationResult?.validated_candidates || []).filter((candidate) => candidate.is_simulation_ready).length;
  const [scenarioTrainingPrompt, setScenarioTrainingPrompt] = useState("");
  const [showScenarioTrainingPrompt, setShowScenarioTrainingPrompt] = useState(false);
  const [scenarioTrainingResponseText, setScenarioTrainingResponseText] = useState("");
  const [scenarioTrainingPreviewText, setScenarioTrainingPreviewText] = useState("");
  const [scenarioTrainingMessage, setScenarioTrainingMessage] = useState("");
  const [showScenarioFormatExample, setShowScenarioFormatExample] = useState(false);
  const selectedStockText = stocks.length
    ? stocks.map((stock) => `${stock.stock_name} · ${stock.stock_code}`).join(", ")
    : "선택 0개";
  const readyValidationCandidates = (validationResult?.validated_candidates || []).filter((candidate) => candidate.is_simulation_ready);
  const selectedTrainingCandidate = selectedSimulationResult
    ? readyValidationCandidates[selectedSimulationResult.scenario_index]?.normalized_candidate || null
    : null;
  const parsedStringConditionCount = candidates.reduce((sum, candidate) => sum + candidate.stringConditionCount, 0);
  const parsedStructureIssueCount = candidates.reduce((sum, candidate) => sum + candidate.invalidStructureCount, 0);
  const currentScenarioStepIndex = SCENARIO_SEARCH_STEPS.findIndex((item) => item.key === step);
  const scenarioStepItems: ResearchStepperItem[] = SCENARIO_SEARCH_STEPS.map((item, index) => {
    const isActive = item.key === step;
    const isComplete = index < currentScenarioStepIndex;
    return {
      key: item.key,
      label: item.label,
      description: SCENARIO_STEP_DESCRIPTIONS[item.key],
      status: isActive ? "active" : isComplete ? "complete" : "pending",
      statusLabel: isActive ? "진행 중" : isComplete ? "완료" : "대기",
    };
  });

  return (
    <div className="scenario-search-shell">
      <ResearchStepper
        title="연구 흐름"
        steps={scenarioStepItems}
        currentStep={step}
        onChangeStep={(nextStep) => onChangeStep(nextStep as ScenarioSearchStep)}
      />

      {step === "setup" ? (
        <div className="scenario-search-layout">
          <div className="scenario-search-main">
            <SectionCard title="1. 탐색 설정" className="scenario-setup-section">
              <div className="scenario-search-card scenario-setup-section">
                <h4>A. 어떤 수익 시나리오?</h4>
                <div className="scenario-search-form-grid">
                  <label>
                    <span>투자 유형</span>
                    <select className="input-control" value={goal.tradeType} onChange={(event) => onChangeGoal({ tradeType: event.target.value as ScenarioGoalState["tradeType"] })}>
                      <option value="short">단기</option>
                      <option value="swing">스윙</option>
                      <option value="mid">중기</option>
                      <option value="long">장기</option>
                    </select>
                  </label>
                  <label>
                    <span>목표 수익률</span>
                    <select className="input-control" value={goal.targetReturnPct} onChange={(event) => onChangeGoal({ targetReturnPct: Number(event.target.value) })}>
                      {[3, 5, 7, 10].map((value) => <option key={value} value={value}>{value}%</option>)}
                    </select>
                  </label>
                  <label>
                    <span>목표 기간</span>
                    <select className="input-control" value={goal.holdingDays} onChange={(event) => onChangeGoal({ holdingDays: Number(event.target.value) })}>
                      {[3, 5, 10, 20, 60].map((value) => <option key={value} value={value}>{value}거래일</option>)}
                    </select>
                  </label>
                  <label>
                    <span>허용 손실률</span>
                    <select className="input-control" value={goal.stopLossPct} onChange={(event) => onChangeGoal({ stopLossPct: Number(event.target.value) })}>
                      {[-3, -5, -7, -10].map((value) => <option key={value} value={value}>{value}%</option>)}
                    </select>
                  </label>
                  <label>
                    <span>최소 후보 수</span>
                    <select className="input-control" value={goal.minSampleCount} onChange={(event) => onChangeGoal({ minSampleCount: Number(event.target.value) })}>
                      {[30, 50, 100].map((value) => <option key={value} value={value}>{value}개</option>)}
                    </select>
                  </label>
                </div>
                <p className="scenario-search-inline-summary">
                  진입 후 {goal.holdingDays}거래일 안에 +{goal.targetReturnPct}% 이상 상승하면 성공, {goal.stopLossPct}% 이하로 하락하면 실패로 분류합니다.
                </p>
              </div>

              <div className="scenario-search-card scenario-setup-section">
                <h4>B. 어떤 종목 데이터?</h4>
                <div className="scenario-search-segmented">
                  <button className="active" type="button">관심종목에서 선택</button>
                  <button type="button" disabled>테마별 선택</button>
                  <button type="button" disabled>직접 검색</button>
                </div>
                {stocks.length ? (
                  <div className="scenario-search-selected-stock">
                    {stocks.map((stock) => (
                      <span key={stock.stock_code}>{stock.stock_name} · {stock.stock_code} · {fmtNumber(stock.price_count, 0)}건</span>
                    ))}
                  </div>
                ) : (
                  <div className="scenario-search-empty">대상 종목 선택은 기존 관심종목 데이터를 기준으로 연결 예정입니다. 이번 단계에서는 화면 구조만 먼저 구성합니다.</div>
                )}
              </div>

              <div className="scenario-search-card scenario-setup-section">
                <h4>C. 하락 시 대응전략</h4>
                <div className="scenario-search-form-grid">
                  <label>
                    <span>추가매수 사용 여부</span>
                    <select className="input-control" value={riskPlan.addBuyEnabled ? "on" : "off"} onChange={(event) => onChangeRiskPlan({ addBuyEnabled: event.target.value === "on", maxAddBuyCount: event.target.value === "on" ? Math.max(1, riskPlan.maxAddBuyCount) : 0 })}>
                      <option value="off">사용 안함</option>
                      <option value="on">사용</option>
                    </select>
                  </label>
                  <label>
                    <span>최대 추가매수 횟수</span>
                    <select className="input-control" value={riskPlan.maxAddBuyCount} disabled={!riskPlan.addBuyEnabled} onChange={(event) => onChangeRiskPlan({ maxAddBuyCount: Number(event.target.value) })}>
                      {[0, 1, 2].map((value) => <option key={value} value={value}>{value}회</option>)}
                    </select>
                  </label>
                  <label>
                    <span>1차 매수금액</span>
                    <input className="input-control" type="number" step={100000} value={riskPlan.initialAmount} onChange={(event) => onChangeRiskPlan({ initialAmount: Number(event.target.value) })} />
                  </label>
                  <label>
                    <span>추가매수 방식</span>
                    <select className="input-control" value={riskPlan.addBuyAmountType} disabled>
                      <option value="same">동일 금액</option>
                    </select>
                  </label>
                  <label>
                    <span>최종 손절 기준</span>
                    <select className="input-control" value={riskPlan.finalStopLossBasis} onChange={(event) => onChangeRiskPlan({ finalStopLossBasis: event.target.value as ScenarioRiskPlanState["finalStopLossBasis"] })}>
                      <option value="initial_price">최초가 기준</option>
                      <option value="average_price">평균단가 기준</option>
                    </select>
                  </label>
                  <label>
                    <span>최종 손절률</span>
                    <input className="input-control" type="number" value={riskPlan.finalStopLossPct} onChange={(event) => onChangeRiskPlan({ finalStopLossPct: Number(event.target.value) })} />
                  </label>
                </div>
                <div className="scenario-search-warning">
                  추가매수는 평균단가를 낮출 수 있지만 총 투입금액과 실제 손실금액을 키울 수 있습니다. 반드시 최대 투입금액과 최종 손절 기준을 함께 확인하세요.
                </div>
              </div>
            </SectionCard>
          </div>

          <aside className="scenario-search-side scenario-setup-side-panel">
            <div className="scenario-search-summary-panel scenario-setup-side-panel">
              <h4>분석 준비 상태</h4>
              <div className="scenario-setup-summary-block">
                <span>탐색 목표</span>
                <strong>{TRADE_TYPE_LABELS[goal.tradeType]} / {goal.holdingDays}거래일 / +{goal.targetReturnPct}%</strong>
              </div>
              <div className="scenario-setup-summary-block">
                <span>실패 기준</span>
                <strong>{goal.stopLossPct}%</strong>
              </div>
              <div className="scenario-setup-summary-block">
                <span>대상 종목</span>
                <strong>{selectedStockText}</strong>
              </div>
              <div className="scenario-setup-summary-block">
                <span>대응전략</span>
                <strong>추가매수 최대 {riskPlan.addBuyEnabled ? riskPlan.maxAddBuyCount : 0}회</strong>
                <em>최대 투입금액 {fmtWon(maxInputAmount)}</em>
              </div>
              <div className="scenario-setup-summary-block">
                <span>손절 기준</span>
                <strong>{riskPlan.finalStopLossBasis === "average_price" ? "평균단가 기준" : "최초가 기준"} {riskPlan.finalStopLossPct}%</strong>
              </div>
              <div className={`scenario-setup-status-message ${setupReady ? "is-ready" : "is-warning"}`}>
                {setupReady ? "GPT 후보 생성 준비가 되었습니다." : "대상 종목을 1개 이상 선택하세요."}
              </div>
              <button className="btn btn-primary" type="button" disabled={!setupReady} onClick={onBuildPrompt}>
                다음: GPT 후보 생성
              </button>
            </div>
          </aside>
        </div>
      ) : null}

      {step === "gpt_candidates" ? (
        <SectionCard title="2. GPT 후보">
          <div className="scenario-gpt-section scenario-gpt-panel">
            <div className="scenario-gpt-section-header">
              <div>
                <h4 className="scenario-gpt-section-title">A. DrCT 데이터 프로파일 요약</h4>
                <p className="scenario-gpt-section-description">GPT가 사용할 탐색 목표, 종목 수, 사용 가능 지표를 확인합니다.</p>
              </div>
            </div>
            <div className="scenario-gpt-profile-kpi-grid">
              <div className="scenario-gpt-profile-kpi-card"><span className="scenario-gpt-profile-kpi-label">탐색 목표</span><strong className="scenario-gpt-profile-kpi-value">{goal.holdingDays}일 / +{goal.targetReturnPct}%</strong></div>
              <div className="scenario-gpt-profile-kpi-card"><span className="scenario-gpt-profile-kpi-label">허용 손실률</span><strong className="scenario-gpt-profile-kpi-value">{goal.stopLossPct}%</strong></div>
              <div className="scenario-gpt-profile-kpi-card"><span className="scenario-gpt-profile-kpi-label">선택 종목</span><strong className="scenario-gpt-profile-kpi-value">{stocks.length}개</strong></div>
              <div className="scenario-gpt-profile-kpi-card"><span className="scenario-gpt-profile-kpi-label">사용 가능 지표</span><strong className="scenario-gpt-profile-kpi-value">{availableIndicators.length}개</strong></div>
            </div>
            <div className="scenario-gpt-indicator-groups">
              {SCENARIO_INDICATOR_GROUPS.map((group) => (
                <div className="scenario-gpt-indicator-group" key={group.title}>
                  <strong className="scenario-gpt-indicator-group-title">{group.title}</strong>
                  <div className="scenario-gpt-indicator-chip-list">
                    {group.indicators.filter((indicator) => availableIndicators.includes(indicator)).map((indicator) => (
                      <code className="scenario-gpt-indicator-chip" key={indicator}>{indicator}</code>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="scenario-gpt-section scenario-gpt-panel scenario-gpt-prompt-card">
            <div className="scenario-gpt-section-header">
              <div>
                <h4 className="scenario-gpt-section-title">B. GPT 시나리오 생성 요청문</h4>
                <p className="scenario-gpt-section-description">아래 요청문을 GPT에 붙여넣어 시나리오 후보 JSON을 생성합니다.</p>
              </div>
            </div>
            <div className="scenario-gpt-json-actions">
              <button className="btn btn-secondary" type="button" onClick={onBuildPrompt}>GPT 시나리오 생성 요청문 만들기</button>
              <button className="btn btn-primary" type="button" onClick={onCopyPrompt}><Clipboard size={15} /> GPT 후보 요청문 복사</button>
              <button className="btn btn-secondary" type="button" disabled={!gptPrompt} onClick={onTogglePrompt}>{showGptPrompt ? "전체 요청문 접기" : "전체 요청문 보기"}</button>
            </div>
            {gptPrompt ? (
              <div className="scenario-gpt-prompt-box">
                {showGptPrompt
                  ? <textarea className="pattern-gpt-prompt scenario-gpt-prompt-textarea" readOnly value={gptPrompt} />
                  : <pre className="scenario-gpt-prompt-preview">{gptPrompt.split("\n").slice(0, 5).join("\n")}</pre>}
              </div>
            ) : null}
          </div>

          <div className="scenario-gpt-section scenario-gpt-panel scenario-gpt-json-card">
            <div className="scenario-gpt-section-header">
              <div>
                <h4 className="scenario-gpt-section-title">C. GPT JSON 응답 붙여넣기</h4>
                <p className="scenario-gpt-section-description">GPT가 생성한 JSON 응답을 그대로 붙여넣고 검증합니다. scenario_candidates 배열이 포함되어야 합니다.</p>
              </div>
            </div>
            <div className="scenario-gpt-json-input-wrap">
              <textarea
                className="scenario-search-json-input scenario-gpt-json-textarea"
                placeholder="GPT 시나리오 후보 JSON을 붙여넣으세요."
                value={gptResponseText}
                onChange={(event) => onChangeResponseText(event.target.value)}
              />
            </div>
            <div className="scenario-gpt-json-actions">
              <button className="btn btn-primary" type="button" disabled={!gptResponseText.trim()} onClick={onValidateResponse}>GPT 응답 검증</button>
              <button className="btn btn-secondary" type="button" disabled={!candidates.length} onClick={() => onChangeStep("validation")}>다음: 검증/실행</button>
            </div>
            {!parseMessage && !parseError ? <div className="scenario-gpt-parse-message">아직 GPT 응답을 검증하지 않았습니다.</div> : null}
            {parseMessage ? <div className="scenario-gpt-parse-message is-success">{parseMessage}</div> : null}
            {parseError ? <div className="scenario-gpt-parse-message is-error">JSON 형식을 해석하지 못했습니다. 괄호, 쉼표, scenario_candidates 배열을 확인하세요. {parseError}</div> : null}
            {parsedStringConditionCount || parsedStructureIssueCount ? (
              <div className="scenario-validation-diagnostic scenario-validation-diagnostic-error">
                <strong>GPT 응답에 문자열 조건 또는 형식 문제가 포함되어 있습니다.</strong>
                <span>DrCT 시뮬레이션 검증에는 indicator_key, operator, value가 분리된 객체형 조건이 필요합니다.</span>
                <div className="scenario-validation-diagnostic-actions">
                  <button className="btn btn-secondary" type="button" onClick={onValidateScenarios}>문자열 조건 자동 변환 시도</button>
                  <button className="btn btn-secondary" type="button" onClick={onCopyPrompt}>올바른 GPT 요청문 다시 복사</button>
                  <button className="btn btn-secondary" type="button" onClick={() => setShowScenarioFormatExample((prev) => !prev)}>객체형 JSON 예시 보기</button>
                </div>
              </div>
            ) : null}
            {showScenarioFormatExample ? <ScenarioJsonExamplePanel /> : null}
          </div>

          <div className="scenario-gpt-section scenario-gpt-panel">
            <div className="scenario-gpt-section-header">
              <div>
                <h4 className="scenario-gpt-section-title">D. GPT 시나리오 후보</h4>
                <p className="scenario-gpt-section-description">생성된 후보를 확인하고 시뮬레이션에 포함할 후보를 선택합니다.</p>
              </div>
            </div>
            {candidates.length ? (
              <div className="scenario-gpt-candidate-summary">
                <strong>GPT 시나리오 후보 {candidates.length}개</strong>
                <span>포함 {includedCandidates.length}개 · 제외 {candidates.length - includedCandidates.length}개 · high {candidates.filter((candidate) => String(candidate.raw.simulation_priority || "").toLowerCase() === "high").length}개 · medium {candidates.filter((candidate) => String(candidate.raw.simulation_priority || "medium").toLowerCase() === "medium").length}개</span>
              </div>
            ) : null}
            <div className="scenario-search-candidate-grid scenario-gpt-candidate-grid">
              {candidates.length ? candidates.map((candidate, index) => (
              <div className={`scenario-search-candidate-card scenario-gpt-candidate-card is-${candidate.status}`} key={candidate.id}>
                <div className="scenario-gpt-candidate-card-header">
                  <div>
                    <span>시나리오 후보 {index + 1}</span>
                    <strong className="scenario-gpt-candidate-title">{candidate.name}</strong>
                  </div>
                  <div className="scenario-gpt-card-badges">
                    <span className={`scenario-gpt-priority-badge is-${String(candidate.raw.simulation_priority || "medium").toLowerCase()}`}>{scenarioPriorityLabel(candidate.raw.simulation_priority)}</span>
                    <span className={`scenario-gpt-state-badge is-${candidate.status}`}>{scenarioCandidateStateLabel(candidate)}</span>
                  </div>
                </div>
                <p className="scenario-gpt-candidate-intent">{candidate.raw.intent || candidate.summary}</p>
                <div className="scenario-gpt-card-section">
                  <strong>진입 조건</strong>
                  <div className="scenario-gpt-condition-list">
                    {candidate.entryConditions.slice(0, 4).map((condition, conditionIndex) => (
                      <div className="scenario-gpt-condition-item" key={`${candidate.id}-${conditionIndex}`}>
                        <span className="scenario-gpt-condition-number">{conditionIndex + 1}</span>
                        <div>
                          <p className="scenario-gpt-condition-expression">{formatScenarioConditionParts(candidate.raw.entry_conditions?.[conditionIndex] ?? condition).expression}</p>
                          {formatScenarioConditionParts(candidate.raw.entry_conditions?.[conditionIndex] ?? condition).description ? (
                            <p className="scenario-gpt-condition-description">{formatScenarioConditionParts(candidate.raw.entry_conditions?.[conditionIndex] ?? condition).description}</p>
                          ) : null}
                        </div>
                      </div>
                    ))}
                    {candidate.entryConditions.length > 4 ? <em>외 {candidate.entryConditions.length - 4}개 조건</em> : null}
                  </div>
                </div>
                <div className="scenario-gpt-card-section scenario-gpt-card-block">
                  <strong className="scenario-gpt-card-block-title">추가매수</strong>
                  <p className="scenario-gpt-card-block-body">{candidate.addBuyStrategy}</p>
                </div>
                <div className="scenario-gpt-card-section scenario-gpt-card-block">
                  <strong className="scenario-gpt-card-block-title">위험 필터</strong>
                  {Array.isArray(candidate.raw.risk_filters) && candidate.raw.risk_filters.length
                    ? candidate.raw.risk_filters.map((filter: unknown, filterIndex: number) => <p className="scenario-gpt-risk-filter" key={`${candidate.id}-risk-${filterIndex}`}>{formatScenarioRiskFilter(filter)}</p>)
                    : <p>위험 필터 없음</p>}
                </div>
                <div className="scenario-gpt-card-section scenario-gpt-card-block">
                  <strong className="scenario-gpt-card-block-title">예상 리스크</strong>
                  <p className="scenario-gpt-card-block-body">{candidate.raw.expected_risk || candidate.fundingNote}</p>
                </div>
                {candidate.schemaWarnings.length ? (
                  <div className="scenario-validation-format-warning">
                    {candidate.schemaWarnings.map((warning) => <span key={warning}>{warning}</span>)}
                  </div>
                ) : null}
                <div className="scenario-gpt-card-actions">
                  <button className={`btn btn-secondary btn-xs ${candidate.status === "included" ? "active" : ""}`} type="button" onClick={() => onChangeCandidateStatus(candidate.id, "included")}>포함</button>
                  <button className={`btn btn-secondary btn-xs ${candidate.status === "excluded" ? "active" : ""}`} type="button" onClick={() => onChangeCandidateStatus(candidate.id, "excluded")}>제외</button>
                  <button className="btn btn-secondary btn-xs" type="button">상세 보기</button>
                </div>
              </div>
              )) : <div className="scenario-search-empty">GPT JSON 응답을 검증하면 시나리오 후보 카드가 표시됩니다.</div>}
            </div>
          </div>
        </SectionCard>
      ) : null}

      {step === "validation" ? (
        <SectionCard title="3. 검증 및 시뮬레이션">
          <div className="scenario-validation-kpi-grid">
            <Kpi label="GPT 후보" value={`${candidates.length}개`} />
            <Kpi label="시뮬레이션 가능" value={`${validationSummary?.simulation_ready || 0}개`} />
            <Kpi label="검토 필요" value={`${validationSummary?.needs_review || 0}개`} />
            <Kpi label="지원 불가" value={`${validationSummary?.unsupported || 0}개`} />
            <Kpi label="위험 조건" value={`${validationSummary?.risky || 0}개`} />
            <Kpi label="형식 오류" value={`${validationSummary?.structure_error || validationSummary?.invalid || 0}개`} />
            <Kpi label="자동 변환" value={`${validationSummary?.auto_converted || 0}개`} />
          </div>
          <div className="pattern-action-row">
            <button className="btn btn-primary" type="button" disabled={!includedCandidates.length || validationLoading} onClick={onValidateScenarios}>
              {validationLoading ? "검증 중..." : "계산 가능성 검증"}
            </button>
          </div>
          {validationError ? <div className="alert danger">{validationError}</div> : null}
          {validationResult && !simulationReadyCount ? (
            <ScenarioValidationDiagnostic
              summary={validationResult.summary}
              onCopyPrompt={onCopyPrompt}
              onRetryValidation={onValidateScenarios}
              onToggleExample={() => setShowScenarioFormatExample((prev) => !prev)}
            />
          ) : null}
          {showScenarioFormatExample ? <ScenarioJsonExamplePanel /> : null}
          <div className="scenario-validation-card-list">
            {validationResult?.validated_candidates.length ? validationResult.validated_candidates.map((candidate) => (
              <ScenarioValidationCandidateCard key={`validated-${candidate.candidate_index}`} candidate={candidate} />
            )) : includedCandidates.length ? includedCandidates.map((candidate) => (
              <div className="scenario-validation-card" key={`validation-${candidate.id}`}>
                <div className="scenario-validation-card-head">
                  <strong>{candidate.name}</strong>
                  <span className="scenario-validation-status scenario-validation-status-review">검증 전</span>
                </div>
                <p>{candidate.summary}</p>
                <button className="btn btn-secondary" type="button" onClick={onValidateScenarios}>계산 가능성 검증</button>
                <small>검증을 실행하면 DrCT 지표 카탈로그 기준으로 조건별 계산 가능 여부를 확인합니다.</small>
              </div>
            )) : <div className="scenario-search-empty">포함된 시나리오 후보가 없습니다.</div>}
          </div>
          <div className="scenario-search-card">
            <h4>공통 시뮬레이션 설정</h4>
            <div className="scenario-search-kpi-grid">
              <Kpi label="1차 매수금액" value={fmtWon(riskPlan.initialAmount)} />
              <Kpi label="추가매수 횟수" value={`${riskPlan.addBuyEnabled ? riskPlan.maxAddBuyCount : 0}회`} />
              <Kpi label="최종 손절 기준" value={riskPlan.finalStopLossBasis === "average_price" ? "평균단가" : "최초가"} />
              <Kpi label="최소 후보 수" value={`${goal.minSampleCount}개`} />
            </div>
            <button className="btn btn-primary" type="button" disabled={!simulationReadyCount || !stocks.length || simulationLoading} onClick={onSimulateScenarios}>
              {simulationLoading ? "시뮬레이션 실행 중..." : "시뮬레이션 실행"}
            </button>
            {simulationError ? <div className="alert danger">{simulationError}</div> : null}
            <div className="scenario-search-empty">
              {validationResult
                ? simulationReadyCount
                  ? "검증을 통과한 시나리오를 실제 가격 데이터로 계산합니다. 결과는 저장하지 않습니다."
                  : "시뮬레이션 가능한 후보가 없습니다. 검토 필요 또는 지원 불가 조건을 수정하세요."
                : "먼저 계산 가능성 검증을 실행하세요."}
            </div>
          </div>
        </SectionCard>
      ) : null}

      {step === "results" ? (
        <SectionCard title="4. 결과 분석">
          {!simulationResult ? (
            <div className="scenario-search-empty">
              조건 검증이 완료되었습니다. 시뮬레이션을 실행하면 실제 가격 데이터 기반 성공률, 실패율, 추가매수 효과, 자금 효율을 이곳에 표시합니다.
            </div>
          ) : (
            <ScenarioSimulationResults
              result={simulationResult}
              selectedResult={selectedSimulationResult}
              validationCandidates={readyValidationCandidates}
              onSelect={onSelectSimulationResult}
              onSendToTrainingGuide={onSendToTrainingGuide}
            />
          )}
        </SectionCard>
      ) : null}

      {step === "training_guide" ? (
        <SectionCard title="5. 훈련가이드">
          <ScenarioTrainingGuide
            goal={goal}
            riskPlan={riskPlan}
            scenarioResult={selectedSimulationResult}
            normalizedCandidate={selectedTrainingCandidate}
            promptText={scenarioTrainingPrompt}
            showPrompt={showScenarioTrainingPrompt}
            responseText={scenarioTrainingResponseText}
            previewText={scenarioTrainingPreviewText}
            message={scenarioTrainingMessage}
            onBackToResults={() => onChangeStep("results")}
            onBuildPrompt={() => {
              if (!selectedSimulationResult) return;
              const prompt = buildScenarioTrainingGuidePrompt(goal, riskPlan, selectedSimulationResult, selectedTrainingCandidate);
              setScenarioTrainingPrompt(prompt);
              setShowScenarioTrainingPrompt(true);
              setScenarioTrainingMessage("GPT 훈련가이드 요청문을 만들었습니다.");
            }}
            onCopyPrompt={() => {
              const prompt = scenarioTrainingPrompt || (selectedSimulationResult ? buildScenarioTrainingGuidePrompt(goal, riskPlan, selectedSimulationResult, selectedTrainingCandidate) : "");
              if (!prompt) return;
              setScenarioTrainingPrompt(prompt);
              setShowScenarioTrainingPrompt(true);
              void navigator.clipboard.writeText(prompt)
                .then(() => setScenarioTrainingMessage("GPT에 붙여넣을 훈련가이드 요청문을 복사했습니다."))
                .catch(() => setScenarioTrainingMessage("요청문 복사에 실패했습니다. 직접 선택하여 복사해 주세요."));
            }}
            onTogglePrompt={() => setShowScenarioTrainingPrompt((prev) => !prev)}
            onChangeResponseText={(value) => {
              setScenarioTrainingResponseText(value);
              setScenarioTrainingPreviewText("");
            }}
            onPreviewResponse={() => setScenarioTrainingPreviewText(scenarioTrainingResponseText)}
            onClearResponse={() => {
              setScenarioTrainingResponseText("");
              setScenarioTrainingPreviewText("");
            }}
          />
        </SectionCard>
      ) : null}
    </div>
  );
}

function ScenarioTrainingGuide({
  goal,
  riskPlan,
  scenarioResult,
  normalizedCandidate,
  promptText,
  showPrompt,
  responseText,
  previewText,
  message,
  onBackToResults,
  onBuildPrompt,
  onCopyPrompt,
  onTogglePrompt,
  onChangeResponseText,
  onPreviewResponse,
  onClearResponse,
}: {
  goal: ScenarioGoalState;
  riskPlan: ScenarioRiskPlanState;
  scenarioResult: ScenarioSimulationResult | null;
  normalizedCandidate: Record<string, any> | null;
  promptText: string;
  showPrompt: boolean;
  responseText: string;
  previewText: string;
  message: string;
  onBackToResults: () => void;
  onBuildPrompt: () => void;
  onCopyPrompt: () => void;
  onTogglePrompt: () => void;
  onChangeResponseText: (value: string) => void;
  onPreviewResponse: () => void;
  onClearResponse: () => void;
}) {
  if (!scenarioResult) {
    return (
      <div className="scenario-training-empty">
        <strong>훈련가이드를 생성할 시나리오가 선택되지 않았습니다.</strong>
        <span>결과 분석 화면에서 시나리오를 선택한 뒤 [GPT 훈련가이드로 보내기]를 클릭하세요.</span>
        <button className="btn btn-secondary" type="button" onClick={onBackToResults}>결과 분석으로 돌아가기</button>
      </div>
    );
  }
  const observations = scenarioTrainingObservations(scenarioResult, goal.minSampleCount);
  const addBuyPlan = normalizedCandidate?.add_buy_plan || {};
  return (
    <div className="scenario-training-shell">
      {message ? <div className="alert success">{message}</div> : null}

      <div className="scenario-training-summary-card">
        <div className="scenario-validation-card-head">
          <div>
            <span>선택 시나리오</span>
            <strong>{scenarioResult.scenario_name}</strong>
          </div>
          <span className={`scenario-simulation-judgement scenario-simulation-judgement-${scenarioResult.judgement}`}>{scenarioResult.judgement_label}</span>
        </div>
        <div className="scenario-search-kpi-grid">
          <Kpi label="후보일" value={`${fmtNumber(scenarioResult.candidate_count, 0)}개`} />
          <Kpi label="1차 성공률" value={fmtPercent(scenarioResult.base_success_rate)} />
          <Kpi label="전략 성공률" value={fmtPercent(scenarioResult.strategy_success_rate)} />
          <Kpi label="실패율" value={fmtPercent(scenarioResult.failure_rate)} />
          <Kpi label="추가매수 발생" value={`${fmtNumber(scenarioResult.add_buy_trigger_count, 0)}건`} />
          <Kpi label="손실 회복률" value={fmtPercent(scenarioResult.recovery_rate_after_add_buy)} />
          <Kpi label="평균 투입금액" value={fmtWon(scenarioResult.avg_capital_used)} />
          <Kpi label="최대 투입금액" value={fmtWon(scenarioResult.max_capital_used)} />
          <Kpi label="효율 점수" value={`${fmtNumber(scenarioResult.efficiency_score, 1)}점`} />
        </div>
        <div className="scenario-training-warning">
          <strong>DrCT 관찰</strong>
          {observations.map((item) => <span key={item}>{item}</span>)}
          {scenarioResult.warnings.map((warning) => <span key={`warning-${warning}`}>{warning}</span>)}
        </div>
        <div className="scenario-training-checklist">
          <span>추가매수: {addBuyPlan.enabled ? "사용" : "사용 안함"}</span>
          <span>최대 추가매수: {addBuyPlan.max_count ?? (riskPlan.addBuyEnabled ? riskPlan.maxAddBuyCount : 0)}회</span>
          <span>최종 손절: {addBuyPlan.stop_loss_basis === "entry_price" ? "최초가 기준" : "평균단가 기준"} {addBuyPlan.final_stop_loss_pct ?? riskPlan.finalStopLossPct}%</span>
        </div>
      </div>

      <div className="scenario-training-prompt-card">
        <h4>B. GPT 훈련가이드 요청문 생성/복사</h4>
        <div className="scenario-training-prompt-actions">
          <button className="btn btn-secondary" type="button" onClick={onBuildPrompt}>GPT 훈련가이드 요청문 만들기</button>
          <button className="btn btn-primary" type="button" onClick={onCopyPrompt}><Clipboard size={15} /> 요청문 복사</button>
          <button className="btn btn-secondary" type="button" disabled={!promptText} onClick={onTogglePrompt}>{showPrompt ? "전체 요청문 접기" : "전체 요청문 보기"}</button>
        </div>
        {showPrompt && promptText ? <textarea className="pattern-gpt-prompt" readOnly value={promptText} /> : null}
      </div>

      <div className="scenario-training-response-card">
        <h4>C. GPT 응답 붙여넣기</h4>
        <textarea
          className="scenario-search-json-input"
          placeholder="GPT 훈련가이드 응답을 붙여넣으세요."
          value={responseText}
          onChange={(event) => onChangeResponseText(event.target.value)}
        />
        <div className="pattern-action-row">
          <button className="btn btn-primary" type="button" disabled={!responseText.trim()} onClick={onPreviewResponse}>훈련가이드 미리보기</button>
          <button className="btn btn-secondary" type="button" disabled={!responseText.trim()} onClick={onClearResponse}>입력 초기화</button>
        </div>
      </div>

      <div className="scenario-training-preview">
        <h4>D. 훈련가이드 미리보기</h4>
        {!previewText ? (
          <div className="scenario-training-empty">GPT 훈련가이드 응답을 붙여넣으면 이곳에서 진입/추가매수/손절 체크리스트를 확인할 수 있습니다.</div>
        ) : (
          <>
            <div className="scenario-search-empty">붙여넣은 GPT 응답을 훈련가이드로 미리보기합니다. 저장 및 매매훈련 연결은 후속 단계에서 지원할 예정입니다.</div>
            <ScenarioTrainingPreview text={previewText} />
          </>
        )}
      </div>

      <div className="scenario-training-next-actions">
        <h4>다음 행동</h4>
        <ol>
          <li>GPT가 제안한 추가매수 금지 조건을 다음 DrCT 시뮬레이션 후보로 반영하세요.</li>
          <li>추가매수 효과가 낮다면 추가매수 없는 시나리오와 비교 테스트하세요.</li>
          <li>손절 기준이 너무 늦거나 빠른지 다른 손절률로 재검증하세요.</li>
          <li>훈련 체크리스트를 매매훈련 화면에 연결하는 기능은 후속 단계에서 지원 예정입니다.</li>
        </ol>
        <div className="pattern-action-row">
          <button className="btn btn-secondary" type="button" disabled>다음 테스트 조건으로 반영</button>
          <button className="btn btn-secondary" type="button" disabled>매매훈련으로 보내기</button>
          <button className="btn btn-secondary" type="button" disabled>시나리오 저장</button>
        </div>
      </div>
    </div>
  );
}

function ScenarioJsonExamplePanel() {
  return (
    <div className="scenario-validation-format-example">
      <div className="scenario-validation-card-head">
        <strong>DrCT가 읽을 수 있는 JSON 예시</strong>
        <span className="scenario-validation-status scenario-validation-status-ready">객체형 조건</span>
      </div>
      <pre>{scenarioJsonExampleText()}</pre>
    </div>
  );
}

function ScenarioValidationDiagnostic({
  summary,
  onCopyPrompt,
  onRetryValidation,
  onToggleExample,
}: {
  summary: ScenarioValidationSummary;
  onCopyPrompt: () => void;
  onRetryValidation: () => void;
  onToggleExample: () => void;
}) {
  const structureCount = summary.structure_error || summary.invalid || 0;
  const unsupportedCount = summary.unsupported || 0;
  const needsReviewCount = summary.needs_review || 0;
  let causeTitle = "조건을 확인해야 합니다.";
  let causeDetail = "일부 조건이 수식화 또는 값 확인이 필요합니다. 조건을 수정하거나 제외한 뒤 다시 검증하세요.";
  if (structureCount >= Math.max(unsupportedCount, needsReviewCount)) {
    causeTitle = "GPT가 entry_conditions를 문자열 또는 잘못된 구조로 작성했습니다.";
    causeDetail = "DrCT는 indicator_key, operator, value가 분리된 객체형 조건이 필요합니다.";
  } else if (unsupportedCount >= needsReviewCount) {
    causeTitle = "GPT가 DrCT에서 지원하지 않는 지표를 사용했습니다.";
    causeDetail = "사용 가능한 지표 목록 안에서 다시 생성해야 합니다.";
  }

  return (
    <div className="scenario-validation-diagnostic scenario-validation-diagnostic-error">
      <strong>시뮬레이션 가능한 후보가 없습니다.</strong>
      <span>검증은 완료되었지만 현재 조건으로는 시뮬레이션을 실행할 수 없습니다. 주요 원인을 확인하고 GPT 요청문을 다시 생성하거나 조건 자동 변환을 시도하세요.</span>
      <div className="scenario-validation-diagnostic-cause">
        <b>주요 원인</b>
        <span>{causeTitle}</span>
        <em>{causeDetail}</em>
      </div>
      <div className="scenario-validation-diagnostic-actions">
        <button className="btn btn-secondary" type="button" onClick={onCopyPrompt}>올바른 형식의 GPT 요청문 복사</button>
        <button className="btn btn-secondary" type="button" onClick={onRetryValidation}>문자열 조건 자동 변환</button>
        <button className="btn btn-secondary" type="button" onClick={onToggleExample}>객체형 JSON 예시 보기</button>
      </div>
    </div>
  );
}

function ScenarioTrainingPreview({ text }: { text: string }) {
  const sections = parseScenarioTrainingSections(text);
  const hasNextTestJson = text.includes("next_test_candidates");
  if (!sections.length) {
    return (
      <>
        {hasNextTestJson ? <NextTestCandidateNotice /> : null}
        <pre className="scenario-training-section">{text}</pre>
      </>
    );
  }
  return (
    <>
      {hasNextTestJson ? <NextTestCandidateNotice /> : null}
      <div className="scenario-training-section-grid">
        {sections.map((section) => (
          <div className="scenario-training-section" key={section.title}>
            <strong>{section.title}</strong>
            <pre>{section.body}</pre>
          </div>
        ))}
      </div>
    </>
  );
}

function NextTestCandidateNotice() {
  return (
    <div className="scenario-training-next-test-json">
      <strong>다음 DrCT 테스트 조건 JSON이 포함되어 있습니다.</strong>
      <span>후속 단계에서 이 조건을 시뮬레이션 후보로 반영할 수 있습니다.</span>
      <button className="btn btn-secondary" type="button" disabled>다음 테스트 조건으로 반영</button>
    </div>
  );
}

function buildScenarioTrainingGuidePrompt(
  goal: ScenarioGoalState,
  riskPlan: ScenarioRiskPlanState,
  result: ScenarioSimulationResult,
  candidate: Record<string, any> | null,
): string {
  const observations = scenarioTrainingObservations(result, goal.minSampleCount);
  const addBuyPlan = candidate?.add_buy_plan || {};
  const riskFilters = Array.isArray(candidate?.risk_filters) ? candidate?.risk_filters : [];
  return [
    "[역할]",
    "당신은 종목 추천자가 아니라, 개인 투자자의 매매 시나리오를 분석하고 훈련 기준으로 정리하는 매매 훈련 코치입니다.",
    "",
    "아래 DrCT 시뮬레이션 결과를 바탕으로 특정 종목의 매수/매도 추천을 하지 말고,",
    "시나리오의 구조, 성공/실패 차이, 추가매수 적절성, 손절 기준, 자금 효율, 훈련 체크리스트를 분석해 주세요.",
    "",
    "[분석 목적]",
    "이 요청의 목적은 수익률이 높은 종목을 찾는 것이 아니라, 사용자가 반복 훈련할 수 있는 매매 시나리오를 만드는 것입니다.",
    "특히 다음을 분석해 주세요.",
    "1. 이 시나리오가 어떤 조건에서 작동했는가",
    "2. 실패 샘플에서는 무엇이 달랐는가",
    "3. 추가매수는 성공률 개선에 기여했는가",
    "4. 추가매수를 하면 안 되는 조건은 무엇인가",
    "5. 평균단가 회복 실패 시 어떤 기준으로 손절해야 하는가",
    "6. 이 시나리오를 실제 훈련에 적용하려면 어떤 체크리스트가 필요한가",
    "",
    "[중요 원칙]",
    "- 종목 추천을 하지 마세요.",
    "- 매수/매도 지시를 하지 마세요.",
    "- 시뮬레이션 결과를 근거로 매매 시나리오를 평가해 주세요.",
    "- 성공률이 높아도 샘플 수가 부족하면 과최적화 위험을 지적해 주세요.",
    "- 추가매수는 손실을 줄이는 만능 수단이 아닙니다.",
    "- 추가매수로 성공률이 개선되지 않았다면 그 이유와 금지 조건을 제안해 주세요.",
    "- 손실률뿐 아니라 총 투입금액과 실제 손실금액 증가 위험도 함께 평가해 주세요.",
    "- 최종 답변은 훈련에 바로 사용할 수 있는 체크리스트 중심으로 작성해 주세요.",
    "",
    "[탐색 목표]",
    `투자 유형: ${TRADE_TYPE_LABELS[goal.tradeType]}`,
    `목표 수익률: 진입 후 ${goal.holdingDays}거래일 안에 +${goal.targetReturnPct}%`,
    `허용 손실률: ${goal.stopLossPct}%`,
    `최소 후보 수: ${goal.minSampleCount}개`,
    "",
    "[시나리오 정보]",
    `시나리오명: ${result.scenario_name}`,
    `시나리오 유형: ${result.scenario_type || candidate?.scenario_type || "-"}`,
    `판정: ${result.judgement_label}`,
    `효율 점수: ${fmtNumber(result.efficiency_score, 1)}`,
    candidate?.intent ? `시나리오 의도: ${candidate.intent}` : "",
    candidate?.expected_risk ? `예상 리스크: ${candidate.expected_risk}` : "",
    "",
    "[진입 조건]",
    formatScenarioConditions(candidate?.entry_conditions),
    "",
    "[추가매수/손절 전략]",
    `1차 매수금액: ${fmtWon(riskPlan.initialAmount)}`,
    `추가매수 사용: ${(addBuyPlan.enabled ?? riskPlan.addBuyEnabled) ? "사용" : "사용 안함"}`,
    `최대 추가매수 횟수: ${addBuyPlan.max_count ?? riskPlan.maxAddBuyCount}회`,
    `추가매수 기준: ${addBuyPlan.trigger_basis === "average_price" ? "평균단가" : "최초 진입가"} 대비 ${addBuyPlan.trigger_loss_pct ?? riskPlan.addBuyTriggerLossPct}% 하락`,
    `추가매수 금액: 1차 매수금액의 ${fmtNumber(addBuyPlan.amount_ratio ?? 1, 2)}배`,
    `최종 손절 기준: ${addBuyPlan.stop_loss_basis === "entry_price" ? "최초가 기준" : "평균단가 기준"} ${addBuyPlan.final_stop_loss_pct ?? riskPlan.finalStopLossPct}%`,
    "목표 회복 기준: 평균단가 기준 목표 수익률 도달",
    "",
    "[위험 필터]",
    riskFilters.length ? riskFilters.map(formatRiskFilter).join("\n") : "위험 필터가 없습니다.",
    "",
    "[시뮬레이션 결과 요약]",
    `후보일 수: ${fmtNumber(result.candidate_count, 0)}`,
    `1차 매수 성공 수: ${fmtNumber(result.success_count, 0)}`,
    `1차 매수 실패 수: ${fmtNumber(result.failure_count, 0)}`,
    `1차 매수 중립 수: ${fmtNumber(result.neutral_count, 0)}`,
    `1차 매수 성공률: ${fmtPercent(result.base_success_rate)}`,
    "",
    `전략 적용 성공 수: ${fmtNumber(result.strategy_success_count, 0)}`,
    `전략 적용 실패 수: ${fmtNumber(result.strategy_failure_count, 0)}`,
    `전략 적용 중립 수: ${fmtNumber(result.strategy_neutral_count, 0)}`,
    `전략 적용 성공률: ${fmtPercent(result.strategy_success_rate)}`,
    `실패율: ${fmtPercent(result.failure_rate)}`,
    "",
    `추가매수 발생 수: ${fmtNumber(result.add_buy_trigger_count, 0)}`,
    `추가매수 후 회복 성공 수: ${fmtNumber(result.recovery_count_after_add_buy, 0)}`,
    `손실 회복률: ${fmtPercent(result.recovery_rate_after_add_buy)}`,
    `평균 추가매수 횟수: ${fmtNumber(result.avg_add_buy_count, 2)}회`,
    "",
    `평균 투입금액: ${fmtWon(result.avg_capital_used)}`,
    `최대 투입금액: ${fmtWon(result.max_capital_used)}`,
    `평균 최대수익률: ${fmtPercent(result.avg_max_return_pct)}`,
    `평균 보유기간 최저수익률: ${fmtPercent(result.avg_max_drawdown_pct)}`,
    `효율 점수: ${fmtNumber(result.efficiency_score, 1)}`,
    `판정: ${result.judgement_label}`,
    "보유기간 최저수익률은 진입 후 목표 기간 동안 관찰된 가장 낮은 수익률입니다. 손절 기준과 별도로, 손절을 지키지 않았을 때 확대될 수 있는 위험을 보여줍니다.",
    "",
    "[성공 샘플]",
    formatScenarioSamples(result.success_samples),
    "",
    "[실패 샘플]",
    formatScenarioSamples(result.failure_samples),
    "",
    "[추가매수 후 회복 성공 샘플]",
    formatScenarioSamples(result.add_buy_success_samples || []),
    "",
    "[추가매수 후 회복 실패 샘플]",
    formatScenarioSamples(result.add_buy_failure_samples || []),
    "",
    "[DrCT 관찰]",
    observations.map((item) => `- ${item}`).join("\n"),
    "",
    "[GPT에게 요청할 분석]",
    "1. 이 매매 시나리오의 핵심 구조를 설명해 주세요.",
    "2. 성공 샘플과 실패 샘플의 가장 큰 차이를 한 문장으로 정리해 주세요.",
    "3. 진입 조건 중 실제로 효과가 있었을 가능성이 높은 조건과 약한 조건을 구분해 주세요.",
    "4. 추가매수는 성공률 개선에 기여했는지 평가해 주세요.",
    "5. 추가매수를 허용해도 되는 조건과 금지해야 하는 조건을 구분해 주세요.",
    "6. 추가매수 후 평균단가 회복에 실패한 경우 어떤 신호에서 손절해야 하는지 제안해 주세요.",
    "7. 현재 손절 기준이 적절한지 평가해 주세요.",
    "8. 자금 효율 관점에서 이 시나리오를 평가해 주세요.",
    "9. 후보 수와 샘플 특성을 바탕으로 과최적화 위험을 평가해 주세요.",
    "10. 다음 DrCT 시뮬레이션에서 테스트할 보완 조건을 3개 이상 제안해 주세요.",
    "11. 이 시나리오를 매매훈련에 사용한다면 진입/추가매수/손절 체크리스트를 만들어 주세요.",
    "12. 사용자가 반복해서 고쳐야 할 행동 습관을 제안해 주세요.",
    "13. 추가매수 후 회복 성공 샘플과 실패 샘플을 비교해 추가매수 허용 조건과 금지 조건을 더 구체화해 주세요.",
    "14. 추가매수 후 회복 실패 샘플에서 반복되는 위험 신호를 찾아 주세요.",
    "",
    "[출력 형식]",
    "아래 형식으로 답변해 주세요.",
    "1. 시나리오 핵심 요약",
    "2. 성공/실패 샘플의 가장 큰 차이",
    "3. 진입 조건 평가",
    "4. 추가매수 전략 평가",
    "5. 추가매수 허용 조건",
    "6. 추가매수 금지 조건",
    "7. 손절 기준 평가",
    "8. 자금 효율 평가",
    "9. 과최적화 위험",
    "10. 다음 DrCT 테스트 조건",
    "11. 매매훈련 체크리스트",
    "   - 진입 전 체크리스트",
    "   - 추가매수 체크리스트",
    "   - 손절 체크리스트",
    "   - 실패 회피 체크리스트",
    "12. 반복 훈련 과제",
    "",
    "[구조화된 다음 테스트 조건]",
    "마지막에 아래 JSON 형식으로 다음 DrCT 테스트 후보를 함께 제안해 주세요.",
    JSON.stringify({
      next_test_candidates: [
        {
          test_name: "거래대금 약화 시 추가매수 금지",
          change_type: "add_risk_filter",
          risk_filter: {
            indicator_key: "trading_value_ratio_20",
            operator: "<",
            value: 0.8,
            action: "block_add_buy",
            reason: "거래대금 약화 시 추가매수 차단",
          },
          expected_effect: "추가매수 실패 샘플 감소와 평균 투입금액 감소 여부 확인",
        },
      ],
    }, null, 2),
    "지원 change_type: add_risk_filter, tighten_entry_condition, loosen_entry_condition, disable_add_buy, change_add_buy_trigger, change_stop_loss",
  ].filter(Boolean).join("\n");
}

function scenarioTrainingObservations(result: ScenarioSimulationResult, minSampleCount: number): string[] {
  const observations: string[] = [];
  const delta = Number(result.strategy_success_rate || 0) - Number(result.base_success_rate || 0);
  if (Number(result.add_buy_trigger_count || 0) === 0) {
    observations.push("이번 시뮬레이션에서는 추가매수 조건에 도달한 사례가 없습니다. 추가매수 전략의 효과를 판단하기에는 샘플이 부족합니다.");
  } else if (delta >= 3) {
    observations.push("추가매수 전략 적용 후 성공률이 개선되었습니다. 다만 평균 투입금액 증가와 실패 거래의 손실 확대 가능성을 함께 평가해야 합니다.");
  } else if (delta > 0) {
    observations.push("추가매수 전략 적용 후 성공률 개선폭이 제한적입니다. 추가 투입금액 대비 효과가 충분한지 검토가 필요합니다.");
  } else if (delta === 0) {
    observations.push("추가매수가 발생했지만 전략 성공률은 개선되지 않았습니다. 추가매수 기준이 적절한지, 또는 추가매수를 금지해야 하는 조건이 있는지 분석이 필요합니다.");
  } else {
    observations.push("추가매수 전략 적용 후 성공률이 낮아졌습니다. 이 시나리오에서는 추가매수를 제거하거나 더 엄격한 추가매수 금지 조건을 두는 것이 적절한지 검토해야 합니다.");
  }
  if (result.candidate_count < minSampleCount) {
    observations.push("후보 수가 최소 후보 수보다 적습니다. 이 결과는 과최적화 가능성이 있으므로 일반화에 주의해야 합니다.");
  }
  if (result.avg_capital_used > 0 && result.max_capital_used > result.avg_capital_used) {
    observations.push(`평균 투입금액은 ${fmtWon(result.avg_capital_used)}이고 최대 투입금액은 ${fmtWon(result.max_capital_used)}입니다. 총 투입금액 증가 위험을 함께 평가해야 합니다.`);
  }
  return observations;
}

function formatScenarioConditions(rawConditions: unknown): string {
  const conditions = Array.isArray(rawConditions) ? rawConditions : [];
  if (!conditions.length) return "진입 조건 정보가 없습니다.";
  return conditions.map((condition, index) => `${index + 1}. ${formatScenarioCondition(condition)}`).join("\n");
}

function formatRiskFilter(filter: Record<string, any>): string {
  const value = Array.isArray(filter.value) ? `[${filter.value.join(", ")}]` : filter.value;
  return `- ${filter.indicator_key || "-"} ${filter.operator || ""} ${value ?? ""}이면 ${filter.action || "warning_only"}\n  이유: ${filter.reason || "위험 필터로 검토"}`;
}

function formatScenarioSamples(samples: ScenarioSimulationResult["success_samples"]): string {
  if (!samples.length) return "표시할 샘플이 없습니다.";
  return samples.slice(0, 5).map((sample, index) => [
    `${index + 1}. ${sample.stock_name || sample.stock_code || "-"} / ${sample.entry_date}`,
    `   - 진입가: ${fmtWon(sample.entry_price)}`,
    `   - 기본 결과: ${sample.base_result}`,
    `   - 전략 결과: ${sample.strategy_result}`,
    `   - 추가매수 횟수: ${fmtNumber(sample.add_buy_count, 0)}`,
    `   - 추가매수가: ${sample.add_buy_price ? fmtWon(sample.add_buy_price) : "-"}`,
    `   - 평균단가: ${sample.average_price ? fmtWon(sample.average_price) : "-"}`,
    `   - 투입금액: ${fmtWon(sample.capital_used)}`,
    `   - 최대수익률: ${fmtPercent(sample.max_return_pct)}`,
    `   - 보유기간 최저수익률: ${fmtPercent(sample.max_drawdown_pct)}`,
    `   - 종료 사유: ${sample.exit_reason}`,
  ].join("\n")).join("\n\n");
}

function parseScenarioTrainingSections(text: string): Array<{ title: string; body: string }> {
  const matches = [...text.matchAll(/(?:^|\n)(\d{1,2}\.\s*[^\n]+)\n/g)];
  if (!matches.length) return [];
  return matches.map((match, index) => {
    const start = (match.index || 0) + (match[0].startsWith("\n") ? 1 : 0);
    const bodyStart = start + match[1].length;
    const nextStart = index + 1 < matches.length ? matches[index + 1].index || text.length : text.length;
    return {
      title: match[1].trim(),
      body: text.slice(bodyStart, nextStart).trim(),
    };
  }).filter((section) => section.body);
}

function ScenarioValidationCandidateCard({ candidate }: { candidate: ValidatedScenarioCandidate }) {
  const statusClass = {
    simulation_ready: "ready",
    needs_review: "review",
    unsupported: "unsupported",
    risky: "risky",
    invalid: "invalid",
  }[candidate.status] || "review";
  const hasStructureError = Boolean(candidate.structure_error_count || candidate.condition_results.some((condition) => condition.status === "invalid_structure"));
  const hasAutoConverted = Boolean(candidate.auto_converted_count || candidate.condition_results.some((condition) => condition.status === "auto_converted") || candidate.risk_filter_results.some((condition) => condition.status === "auto_converted"));
  return (
    <div className={`scenario-validation-card is-${statusClass}`}>
      <div className="scenario-validation-card-head">
        <strong>{candidate.scenario_name}</strong>
        <span className={`scenario-validation-status scenario-validation-status-${statusClass}`}>{candidate.status_label}</span>
      </div>
      {hasStructureError ? (
        <div className="scenario-validation-structure-error">
          <strong>조건 형식 오류</strong>
          <span>entry_conditions 또는 risk_filters에 문자열 조건이 포함되어 있습니다. 조건을 indicator_key/operator/value 객체 형식으로 변환해야 합니다.</span>
        </div>
      ) : null}
      {hasAutoConverted ? (
        <div className="scenario-validation-auto-converted">
          <strong>자동 변환됨</strong>
          <span>일부 문자열 조건이 객체형 조건으로 자동 변환되었습니다. 시뮬레이션 전 조건을 확인하세요.</span>
        </div>
      ) : null}
      <div className="scenario-validation-ready-note">
        {candidate.is_simulation_ready ? "조건 검증 기준으로 시뮬레이션 후보에 포함할 수 있습니다." : "현재 상태에서는 시뮬레이션 실행 대상에서 제외하는 것이 좋습니다."}
      </div>

      <div className="scenario-validation-section">
        <h4>진입 조건 검증 결과</h4>
        <div className="scenario-validation-condition-list">
          {candidate.condition_results.map((condition, index) => (
            <ScenarioValidationConditionRow key={`entry-${candidate.candidate_index}-${index}`} condition={condition} />
          ))}
        </div>
      </div>

      <div className="scenario-validation-section">
        <h4>위험 필터 검증 결과</h4>
        {candidate.risk_filter_results.length ? (
          <div className="scenario-validation-condition-list">
            {candidate.risk_filter_results.map((condition, index) => (
              <ScenarioValidationConditionRow key={`risk-${candidate.candidate_index}-${index}`} condition={condition} />
            ))}
          </div>
        ) : <div className="scenario-search-empty">위험 필터가 없습니다.</div>}
      </div>

      {candidate.add_buy_result ? (
        <div className={`scenario-validation-add-buy is-${candidate.add_buy_result.status}`}>
          <strong>추가매수 전략</strong>
          <span>{candidate.add_buy_result.message}</span>
          {(candidate.add_buy_result.warnings || []).map((warning) => <em key={warning}>{warning}</em>)}
          {(candidate.add_buy_result.errors || []).map((error) => <b key={error}>{error}</b>)}
        </div>
      ) : null}

      {candidate.warnings.length ? (
        <div className="scenario-validation-warning">
          {candidate.warnings.map((warning) => <span key={warning}>{warning}</span>)}
        </div>
      ) : null}
      {candidate.errors.length ? (
        <div className="scenario-validation-error">
          {candidate.errors.map((error) => <span key={error}>{error}</span>)}
        </div>
      ) : null}
    </div>
  );
}

function ScenarioSimulationResults({
  result,
  selectedResult,
  validationCandidates,
  onSelect,
  onSendToTrainingGuide,
}: {
  result: ScenarioSimulationResponse;
  selectedResult: ScenarioSimulationResult | null;
  validationCandidates: ValidatedScenarioCandidate[];
  onSelect: (result: ScenarioSimulationResult) => void;
  onSendToTrainingGuide: (result: ScenarioSimulationResult) => void;
}) {
  const sortedResults = [...result.scenario_results].sort((a, b) => {
    if (b.efficiency_score !== a.efficiency_score) return b.efficiency_score - a.efficiency_score;
    if (b.strategy_success_rate !== a.strategy_success_rate) return b.strategy_success_rate - a.strategy_success_rate;
    return b.candidate_count - a.candidate_count;
  });
  const topResults = sortedResults.slice(0, 3);
  const active = selectedResult || sortedResults[0] || null;
  const activeCandidate = active ? validationCandidates[active.scenario_index]?.normalized_candidate || null : null;
  const addBuyInsight = active ? scenarioAddBuyInsight(active) : "";
  return (
    <div className="scenario-simulation-shell">
      <div className="scenario-simulation-kpi-grid">
        <Kpi label="실행 시나리오" value={`${fmtNumber(result.summary.executed_scenarios, 0)}개`} />
        <Kpi label="전체 후보일" value={`${fmtNumber(result.summary.total_candidates, 0)}개`} />
        <Kpi label="최고 전략 성공률" value={fmtPercent(result.summary.best_strategy_success_rate)} />
        <Kpi label="최고 효율 점수" value={`${fmtNumber(result.summary.best_efficiency_score, 1)}점`} />
        <Kpi label="추가매수 효과 있음" value={`${fmtNumber(result.summary.add_buy_effective_count, 0)}개`} />
        <Kpi label="과최적화 주의" value={`${fmtNumber(result.summary.overfit_warning_count, 0)}개`} />
      </div>

      <div className="scenario-simulation-card-grid">
        {topResults.map((item) => (
          <button className="scenario-simulation-card" type="button" key={`top-${item.scenario_index}`} onClick={() => onSelect(item)}>
            <div className="scenario-validation-card-head">
              <strong>{item.scenario_name}</strong>
              <span className={`scenario-simulation-judgement scenario-simulation-judgement-${item.judgement}`}>{item.judgement_label}</span>
            </div>
            <div className="scenario-simulation-metrics">
              <span>후보일 {fmtNumber(item.candidate_count, 0)}개</span>
              <span>1차 {fmtPercent(item.base_success_rate)}</span>
              <span>전략 {fmtPercent(item.strategy_success_rate)}</span>
              <span>실패율 {fmtPercent(item.failure_rate)}</span>
              <span>회복률 {fmtPercent(item.recovery_rate_after_add_buy)}</span>
              <span>효율 {fmtNumber(item.efficiency_score, 1)}점</span>
            </div>
            <p>
              추가매수 적용 후 성공률이 {fmtPercent(item.base_success_rate)}에서 {fmtPercent(item.strategy_success_rate)}로 계산되었습니다.
              평균 투입금액은 {fmtWon(item.avg_capital_used)}입니다.
            </p>
            {item.warnings[0] ? <em>{item.warnings[0]}</em> : null}
          </button>
        ))}
      </div>

      <div className="table-shell scenario-simulation-table">
        <table className="data-table compact-table">
          <thead>
            <tr>
              <th>순위</th>
              <th>시나리오명</th>
              <th>후보일</th>
              <th>1차 성공률</th>
              <th>전략 성공률</th>
              <th>실패율</th>
              <th>손실 회복률</th>
              <th>평균 투입금액</th>
              <th>효율 점수</th>
              <th>판정</th>
            </tr>
          </thead>
          <tbody>
            {sortedResults.map((item, index) => (
              <tr key={`scenario-result-${item.scenario_index}`} onClick={() => onSelect(item)}>
                <td>{index + 1}</td>
                <td>{item.scenario_name}</td>
                <td className="numeric-cell">{fmtNumber(item.candidate_count, 0)}</td>
                <td className="numeric-cell">{fmtPercent(item.base_success_rate)}</td>
                <td className="numeric-cell">{fmtPercent(item.strategy_success_rate)}</td>
                <td className="numeric-cell">{fmtPercent(item.failure_rate)}</td>
                <td className="numeric-cell">{fmtPercent(item.recovery_rate_after_add_buy)}</td>
                <td className="numeric-cell">{fmtWon(item.avg_capital_used)}</td>
                <td className="numeric-cell">{fmtNumber(item.efficiency_score, 1)}</td>
                <td><span className={`scenario-simulation-judgement scenario-simulation-judgement-${item.judgement}`}>{item.judgement_label}</span></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {active ? (
        <div className="scenario-simulation-detail">
          <div className="scenario-validation-card-head">
            <strong>{active.scenario_name}</strong>
            <button className="btn btn-primary" type="button" onClick={() => onSendToTrainingGuide(active)}>GPT 훈련가이드로 보내기</button>
          </div>
          {activeCandidate ? (
            <div className="scenario-simulation-condition-summary">
              <strong>진입 조건 요약</strong>
              {(Array.isArray(activeCandidate.entry_conditions) ? activeCandidate.entry_conditions : []).map((condition: unknown, index: number) => (
                <span key={`active-condition-${index}`}>{formatScenarioCondition(condition)}</span>
              ))}
              <em>{formatAddBuyPlan(activeCandidate.add_buy_plan)}</em>
            </div>
          ) : null}
          {addBuyInsight ? <div className="scenario-simulation-warning">{addBuyInsight}</div> : null}
          {active.warnings.length ? (
            <div className="scenario-simulation-warning">
              {active.warnings.map((warning) => <span key={warning}>{warning}</span>)}
            </div>
          ) : null}
          <div className="scenario-search-kpi-grid">
            <Kpi label="성공/실패/중립" value={`${fmtNumber(active.strategy_success_count, 0)} / ${fmtNumber(active.strategy_failure_count, 0)} / ${fmtNumber(active.strategy_neutral_count, 0)}`} />
            <Kpi label="추가매수 발생" value={`${fmtNumber(active.add_buy_trigger_count, 0)}건`} />
            <Kpi label="평균 추가매수" value={`${fmtNumber(active.avg_add_buy_count, 2)}회`} />
            <Kpi label="최대 투입금액" value={fmtWon(active.max_capital_used)} />
          </div>
          <div className="scenario-search-empty">
            실패 판정은 손절 기준 도달 여부로 계산됩니다. 표의 보유기간 최저수익률은 목표 기간 동안 관찰된 최저가 기준 수익률로, 손절을 지키지 않았을 때 확대될 수 있는 위험을 보여줍니다.
          </div>
          <ScenarioSimulationSampleTable title="성공 샘플" samples={active.success_samples} mode="success" />
          <ScenarioSimulationSampleTable title="실패 샘플" samples={active.failure_samples} mode="failure" />
          {active.add_buy_trigger_count > 0 ? (
            <>
              <ScenarioSimulationSampleTable title="추가매수 후 회복 성공 샘플" samples={active.add_buy_success_samples || []} mode="add_buy_success" />
              <ScenarioSimulationSampleTable title="추가매수 후 회복 실패 샘플" samples={active.add_buy_failure_samples || []} mode="add_buy_failure" />
            </>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

function scenarioAddBuyInsight(result: ScenarioSimulationResult): string {
  const delta = Number(result.strategy_success_rate || 0) - Number(result.base_success_rate || 0);
  if (!result.add_buy_trigger_count) {
    return "이번 시뮬레이션에서는 추가매수 조건에 도달한 사례가 없습니다. 추가매수 전략의 효과를 판단하기 어렵습니다.";
  }
  if (delta > 0) {
    return "추가매수 적용 후 성공률은 개선되었지만 평균 투입금액이 증가했습니다. 추가매수 후 회복 성공/실패 샘플을 함께 확인하세요.";
  }
  return "추가매수가 발생했지만 성공률 개선이 제한적입니다. 추가매수 금지 조건을 추가로 검증해야 합니다.";
}

function ScenarioSimulationSampleTable({ title, samples, mode }: { title: string; samples: ScenarioSimulationResult["success_samples"]; mode: "success" | "failure" | "add_buy_success" | "add_buy_failure" }) {
  const isAddBuyMode = mode === "add_buy_success" || mode === "add_buy_failure";
  return (
    <div className="scenario-simulation-sample-table">
      <h4>{title}</h4>
      {!samples.length ? <div className="scenario-search-empty">표시할 샘플이 없습니다.</div> : (
        <div className="table-shell">
          <table className="data-table compact-table">
            <thead>
              <tr>
                <th>종목</th>
                <th>진입일</th>
                <th>진입가</th>
                <th>전략 결과</th>
                <th>추가매수</th>
                {isAddBuyMode ? <th>추가매수가</th> : null}
                <th>평균단가</th>
                <th>투입금액</th>
                <th>최대수익률</th>
                <th>보유기간 최저수익률</th>
                {(mode === "failure" || isAddBuyMode) ? <th>종료 사유</th> : null}
              </tr>
            </thead>
            <tbody>
              {samples.map((sample) => (
                <tr key={`${sample.stock_code}-${sample.entry_date}-${sample.strategy_result}`}>
                  <td>{sample.stock_name || sample.stock_code || "-"}</td>
                  <td>{sample.entry_date}</td>
                  <td className="numeric-cell">{fmtWon(sample.entry_price)}</td>
                  <td>{sample.strategy_result}</td>
                  <td className="numeric-cell">{fmtNumber(sample.add_buy_count, 0)}회</td>
                  {isAddBuyMode ? <td className="numeric-cell">{sample.add_buy_price ? fmtWon(sample.add_buy_price) : "-"}</td> : null}
                  <td className="numeric-cell">{sample.average_price ? fmtWon(sample.average_price) : "-"}</td>
                  <td className="numeric-cell">{fmtWon(sample.capital_used)}</td>
                  <td className="numeric-cell">{fmtPercent(sample.max_return_pct)}</td>
                  <td className="numeric-cell">{fmtPercent(sample.max_drawdown_pct)}</td>
                  {(mode === "failure" || isAddBuyMode) ? <td>{sample.exit_reason}</td> : null}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function ScenarioValidationConditionRow({ condition }: { condition: ValidatedScenarioCandidate["condition_results"][number] }) {
  const isValid = condition.status === "valid" || condition.status === "auto_converted";
  const isError = ["invalid_value", "invalid_structure", "missing_field", "unsupported_indicator", "unsupported_operator", "unsupported_action"].includes(String(condition.status));
  const symbol = isValid ? "✓" : isError ? "✕" : "⚠";
  const expression = condition.original && condition.status === "invalid_structure"
    ? `"${String(condition.original)}"`
    : `${condition.indicator_key || "-"} ${condition.operator || ""} ${Array.isArray(condition.value) ? `[${condition.value.join(", ")}]` : condition.value ?? ""}`.trim();
  return (
    <div className={`scenario-validation-condition-row is-${condition.status}`}>
      <span>{symbol}</span>
      <div>
        <strong>{expression}</strong>
        <em>{condition.message}</em>
      </div>
    </div>
  );
}

function GptPackageReview({
  gptPackage,
  showPrompt,
  onTogglePrompt,
  onCopyPrompt,
  onOpenCsv,
}: {
  gptPackage: PatternResearchGptPackage;
  showPrompt: boolean;
  onTogglePrompt: () => void;
  onCopyPrompt: () => Promise<void>;
  onOpenCsv: () => void;
}) {
  const summary = gptPackage.summary || {};
  const promptText = gptPackage.gpt_prompt_text || "";
  const success = summary.applied_success_criteria || {};
  const failure = summary.applied_failure_criteria || {};
  const include = (summary.applied_entry_filters || []) as Array<Record<string, any>>;
  const exclude = (summary.applied_exclude_filters || []) as Array<Record<string, any>>;
  const reference = (summary.reference_entry_filters || []) as Array<Record<string, any>>;
  const observationIndicators = (summary.observation_indicators || []) as string[];
  const performance = (summary.condition_candidate_performance || []) as Array<Record<string, any>>;
  const total = Number(summary.total_samples || 0);
  const successCount = Number(summary.success_count || 0);
  const failureCount = Number(summary.failure_count || 0);
  const hasPrompt = Boolean(promptText);
  const requiredChecks = [
    { label: "사용자 목표", ok: promptText.includes("[사용자 매매목표]") },
    { label: "확정 조건", ok: Boolean(success.expression || failure.expression || include.length || exclude.length) },
    { label: "샘플 통계", ok: total > 0 },
    { label: "성공/실패 샘플 예시", ok: promptText.includes("[성공 샘플 예시]") && promptText.includes("[실패 샘플 예시]") },
    { label: "샘플 관찰 지표", ok: observationIndicators.length > 0 },
  ];
  const requestChecks = [
    { label: "핵심 통찰 한 문장 요청", ok: promptText.includes("한 문장 통찰") || promptText.includes("핵심 차이") },
    { label: "추가 조건 후보 최소 3개 요청", ok: promptText.includes("최소 3개") },
    { label: "복합 패턴 후보 2~3개 요청", ok: promptText.includes("복합 패턴 후보") },
    { label: "다음 DrCT 테스트 조건 세트 요청", ok: promptText.includes("다음 DrCT 테스트 조건 세트") },
    { label: "매매훈련 체크리스트 요청", ok: promptText.includes("매매훈련") },
  ];
  const completeCount = [...requiredChecks, ...requestChecks].filter((item) => item.ok).length;
  const allCount = requiredChecks.length + requestChecks.length;
  const researchReady = hasPrompt && total > 0 && successCount > 0 && failureCount > 0;
  const statusLabelText = researchReady ? "준비 완료" : "확인 필요";
  const conditionGroups = [
    { label: "성공 기준", rows: success.expression ? [success] : [] },
    { label: "실패 기준", rows: failure.expression ? [failure] : [] },
    { label: "포함 조건", rows: include },
    { label: "제외 조건", rows: exclude },
    { label: "비교용 지표", rows: reference },
  ];
  const requestItems = [
    "현재 성공률의 의미 평가",
    "성공 샘플과 실패 샘플의 가장 큰 차이 3가지",
    "성공 샘플과 실패 샘플의 핵심 차이 한 문장 통찰",
    "실패 샘플에서 반복되는 진입 실패 패턴",
    "사용자가 자연어로 제시한 조건의 유효성 평가",
    "성공/실패를 가장 잘 구분하는 샘플 관찰 지표",
    "사용자가 포함하지 않았지만 추가하면 좋을 조건 후보 최소 3개",
    "샘플 적용 조건으로 승격할 만한 조건 후보",
    "성공 가능성이 높은 복합 패턴 후보 2~3개",
    "각 복합 패턴 후보를 DrCT 조건식으로 정리",
    "다음 DrCT 테스트 우선순위 조건 세트",
    "매매훈련용 체크리스트",
    "과최적화 위험과 추가 검증 필요사항",
  ];

  return (
    <div className="gpt-package-review">
      <div className={`gpt-package-status is-${researchReady ? "ready" : "warning"}`}>
        <div>
          <strong>GPT 연구 패키지 {statusLabelText}</strong>
          <span>필수 정보 {completeCount}/{allCount} 포함 · 전체 샘플 {fmtNumber(total, 0)}개 · 성공 {fmtNumber(successCount, 0)} / 실패 {fmtNumber(failureCount, 0)} · 성공률 {fmtPercent(summary.success_rate)}</span>
        </div>
        <em>GPT 연구 가능: {researchReady ? "가능" : "확인 필요"}</em>
      </div>

      <div className="pattern-action-row">
        <button className="btn btn-primary" type="button" onClick={() => void onCopyPrompt()}><Clipboard size={15} /> 연구 요청문 복사</button>
        <button className="btn btn-secondary" type="button" onClick={onOpenCsv}><Download size={15} /> CSV 다운로드</button>
        <button className="btn btn-secondary" type="button" onClick={onTogglePrompt}>{showPrompt ? "전체 요청문 접기" : "전체 요청문 보기"}</button>
        <span className="gpt-package-csv-help">CSV는 성공/실패 샘플 원자료 확인용입니다.</span>
      </div>

      <div className="gpt-package-checklist">
        <div className="gpt-package-compact-card">
          <strong>필수 정보</strong>
          {requiredChecks.map((item) => <span key={item.label} className={item.ok ? "is-ok" : "is-warn"}>{item.ok ? "✓" : "!"} {item.label}</span>)}
          {!reference.length ? <em>조건 후보가 없어도 오류는 아닙니다. GPT가 새 조건 후보를 제안하도록 요청문에 포함되어 있습니다.</em> : null}
        </div>
        <div className="gpt-package-compact-card">
          <strong>분석 요청</strong>
          {requestChecks.map((item) => <span key={item.label} className={item.ok ? "is-ok" : "is-warn"}>{item.ok ? "✓" : "!"} {item.label}</span>)}
        </div>
      </div>

      <div className="gpt-package-condition-summary">
        {conditionGroups.map((group) => (
          <div key={group.label} className="gpt-package-compact-card">
            <strong>{group.label}</strong>
            {group.rows.length ? group.rows.slice(0, 8).map((item, index) => <span key={`${group.label}-${index}`}>{conditionSummaryLabel(item)}</span>) : (
              <em>{group.label === "비교용 지표" ? "비교용 지표가 없습니다." : "없음"}</em>
            )}
          </div>
        ))}
        <div className="gpt-package-compact-card">
          <strong>조건 후보</strong>
          {reference.length ? reference.slice(0, 8).map((item, index) => <span key={`candidate-${index}`}>{conditionSummaryLabel(item)}</span>) : (
            <em>조건 후보가 없습니다. 현재 패키지는 확정 조건과 샘플 관찰 지표 중심으로 분석됩니다. GPT가 성공/실패 차이를 바탕으로 새로운 조건 후보를 제안하도록 요청문에 포함되어 있습니다.</em>
          )}
        </div>
      </div>

      <div className="gpt-package-request-items">
        <strong>GPT에게 요청할 분석</strong>
        <p>목적은 종목 추천이 아니라, 성공/실패 샘플 차이를 분석해 검증 가능한 매매패턴 조건 후보를 찾는 것입니다.</p>
        <em>핵심 통찰 요청: 성공 샘플과 실패 샘플의 가장 큰 차이는 무엇이다.</em>
        <ol>
          {requestItems.map((item) => <li key={item}>{item}</li>)}
        </ol>
      </div>

      <div className="gpt-package-performance">
        <strong>조건 후보별 성과</strong>
        {performance.length ? (
          <div className="table-shell">
            <table className="data-table compact-table">
              <thead><tr><th>조건명</th><th>통과 샘플</th><th>성공률</th><th>해석</th></tr></thead>
              <tbody>
                {performance.slice(0, 8).map((item, index) => {
                  const passed = Number(item.passed_count || 0);
                  const diff = Number(item.lift_vs_base ?? item.success_rate_lift ?? 0);
                  return (
                    <tr key={`performance-${index}`}>
                      <td>{item.condition_label || item.expression || "-"}</td>
                      <td className="numeric-cell">{fmtNumber(passed, 0)}</td>
                      <td className="numeric-cell">{passed ? `${fmtNumber(item.success_rate)}%` : "-"}</td>
                      <td>{passed === 0 ? "통과 샘플이 없어 성과를 계산할 수 없습니다. 기준값이 너무 엄격하거나 조건 정의를 점검해야 합니다." : `기본 성공률 대비 ${diff > 0 ? "+" : ""}${fmtNumber(diff)}%p`}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        ) : <div className="pattern-empty-note">조건 후보별 성과 데이터가 없습니다. 조건 후보가 없거나 비교할 후보 조건이 부족할 수 있습니다.</div>}
      </div>

      <div className="gpt-package-prompt-preview">
        <strong>연구 요청문 미리보기</strong>
        <div className="gpt-package-preview-bullets">
          <span>역할</span><span>연구 목적</span><span>사용자 목표</span><span>적용 조건</span><span>샘플 요약</span><span>분석 요청</span>
        </div>
        {showPrompt ? <textarea className="pattern-gpt-prompt gpt-package-prompt-textarea" readOnly value={promptText} /> : null}
      </div>

      <div className="gpt-package-next-guide">
        <strong>다음 행동</strong>
        <span>1. 연구 요청문을 복사합니다.</span>
        <span>2. ChatGPT에 붙여넣고 분석 결과를 받습니다.</span>
        <span>3. GPT가 제안한 핵심 통찰, 조건 후보, 복합 패턴, 실패 패턴, 훈련 체크리스트를 확인합니다.</span>
        <span>4. 다음 개발 단계에서는 이 결과를 DrCT에 붙여넣고 패턴 후보로 저장할 수 있게 됩니다.</span>
        <em>다음 개발 예정: GPT 연구 결과 붙여넣기 및 패턴 후보 저장 기능</em>
      </div>
    </div>
  );
}

function GptPackagePreview({ summary }: { summary: Record<string, any> }) {
  const applied = [...(summary.applied_entry_filters || []), ...(summary.applied_exclude_filters || [])];
  const candidates = summary.reference_entry_filters || [];
  const observationIndicators = summary.observation_indicators || [];
  const performance = summary.condition_candidate_performance || [];

  return (
    <div className="pattern-package-preview">
      <div className="pattern-package-preview-card">
        <h4>실제 샘플 적용 조건</h4>
        {applied.length ? applied.slice(0, 5).map((item: Record<string, any>, index: number) => (
          <span key={`package-applied-${index}`}>{item.expression || item.label || item.indicator_key || "-"}</span>
        )) : <em>샘플 필터로 적용된 추가 조건이 없습니다.</em>}
      </div>
      <div className="pattern-package-preview-card">
        <h4>조건 후보</h4>
        {candidates.length ? candidates.slice(0, 5).map((item: Record<string, any>, index: number) => (
          <span key={`package-candidate-${index}`}>{item.expression || item.label || item.indicator_key || "-"}</span>
        )) : <em>조건 후보가 없습니다.</em>}
      </div>
      <div className="pattern-package-preview-card">
        <h4>샘플 관찰 지표</h4>
        {observationIndicators.length ? observationIndicators.slice(0, 12).map((key: string) => (
          <span key={`package-observation-${key}`}>{key}</span>
        )) : <em>샘플 관찰 지표가 없습니다. 기본 관찰 지표를 사용합니다.</em>}
      </div>
      <div className="pattern-package-preview-card">
        <h4>조건 후보별 성과</h4>
        {performance.length ? performance.slice(0, 4).map((item: Record<string, any>, index: number) => (
          <span key={`package-performance-${index}`}>
            {item.condition_label || item.expression || "-"} · 통과 {item.passed_count} · 성공률 {item.success_rate ?? "-"}%
          </span>
        )) : <em>조건 후보별 성과가 없습니다.</em>}
      </div>
    </div>
  );
}

function PatternSetupReviewPanel({
  parsed,
  onUpdateCriteria,
  onUpdateFilter,
  onNext,
}: {
  parsed: PatternGoalParseResponse | null;
  onUpdateCriteria: (kind: "success_criteria" | "failure_criteria", key: string, value: any) => void;
  onUpdateFilter: (kind: "entry_filters" | "exclude_filters", index: number, updates: Record<string, any>) => void;
  onNext: () => void;
}) {
  if (!parsed) {
    return <div className="pattern-empty-note">목표 해석 후 연구 기준, 문장별 해석 상태, GPT 검증 대상 목록이 표시됩니다.</div>;
  }
  const goal = parsed.parsed_goal || {};
  const success = goal.success_criteria || goal.success_rule || {};
  const failure = goal.failure_criteria || goal.failure_rule || {};
  const entryFilters = (goal.entry_filters || []) as Array<Record<string, any>>;
  const excludeFilters = (goal.exclude_filters || []) as Array<Record<string, any>>;
  const unsupportedItems = (goal.unsupported_items || parsed.unsupported_items || []) as Array<Record<string, any>>;
  const interpretedItems = (parsed.interpreted_items || []) as Array<Record<string, any>>;
  const conditionRows = [
    ...entryFilters.map((condition, index) => ({ condition, kind: "entry_filters" as const, index })),
    ...excludeFilters.map((condition, index) => ({ condition, kind: "exclude_filters" as const, index })),
  ];
  const selectedCount = conditionRows.filter(({ condition }) => condition.gpt_verify_selected !== false).length;
  const sentenceRows = [
    ...interpretedItems.map((item, index) => ({
      key: `interpreted-${index}`,
      text: item.natural_text || item.source_text || "-",
      expression: item.expression || item.indicator_key || "-",
      status: item.status === "applied" ? "해석됨" : item.status === "needs_review" ? "확인 필요" : friendlyStatusLabel(item.status),
      tone: item.status === "applied" ? "ok" : "warn",
    })),
    ...unsupportedItems.map((item, index) => ({
      key: `unsupported-${index}`,
      text: item.natural_text || item.source_text || "-",
      expression: item.expression || item.indicator_key || item.reason || "GPT 수식화 필요",
      status: item.display_group === "formula_required" || item.indicator_key ? "수식화 필요" : "미지원 또는 보류",
      tone: "warn",
    })),
  ];

  return (
    <div className="pattern-setup-review">
      <div className="pattern-setup-criteria">
        <div className="pattern-setup-section-head">
          <strong>연구 기준</strong>
          <span>성공/실패를 나누는 기준입니다. 연구에 항상 적용됩니다.</span>
        </div>
        <div className="pattern-criteria-card-grid">
          <div className="pattern-criteria-card">
            <strong>목표 수익률</strong>
            <code>{success.expression || formatConditionExpression(success, "always")}</code>
            <div className="pattern-condition-value-inputs compact">
              <label><span>수익률</span><input type="number" value={success.target_return_pct ?? goal.target_return_pct ?? ""} onChange={(event) => onUpdateCriteria("success_criteria", "target_return_pct", Number(event.target.value))} /></label>
              <label><span>거래일</span><input type="number" value={success.target_days ?? goal.target_days ?? ""} onChange={(event) => onUpdateCriteria("success_criteria", "target_days", Number(event.target.value))} /></label>
            </div>
          </div>
          <div className="pattern-criteria-card">
            <strong>손절 기준</strong>
            <code>{failure.expression || formatConditionExpression(failure, "always")}</code>
            <div className="pattern-condition-value-inputs compact">
              <label><span>손절%</span><input type="number" value={failure.stop_loss_pct ?? goal.stop_loss_pct ?? ""} onChange={(event) => onUpdateCriteria("failure_criteria", "stop_loss_pct", Number(event.target.value))} /></label>
            </div>
          </div>
        </div>
      </div>

      <div className="pattern-setup-sentence-panel">
        <div className="pattern-setup-section-head">
          <strong>문장별 해석 상태</strong>
          <span>입력한 자연어 문장이 빠짐없이 수식 후보 또는 수식화 필요 항목으로 잡혔는지 확인합니다.</span>
        </div>
        <div className="pattern-sentence-status-list">
          {sentenceRows.map((row) => (
            <div key={row.key} className={`pattern-sentence-status-item is-${row.tone}`}>
              <span>{row.tone === "ok" ? "해석됨" : row.status}</span>
              <strong>{row.text}</strong>
              <code>{row.expression}</code>
            </div>
          ))}
        </div>
      </div>

      <div className="pattern-setup-target-panel">
        <div className="pattern-setup-section-head">
          <strong>GPT 검증 대상으로 보낼 조건</strong>
          <span>체크된 항목은 2단계에서 GPT가 의미와 기준값을 검증합니다. 최종 사용 방식은 2단계에서 결정합니다.</span>
        </div>
        <div className="pattern-setup-selected-note">체크한 항목 = GPT 검증 대상 · 선택 {selectedCount}개</div>
        <div className="table-shell pattern-setup-table-shell">
          <table className="data-table compact-table pattern-setup-target-table">
            <thead>
              <tr>
                <th>선택</th>
                <th>자연어 표현</th>
                <th>DrCT 1차 수식</th>
                <th>상태</th>
                <th>기준값</th>
              </tr>
            </thead>
            <tbody>
              {conditionRows.map(({ condition, kind, index }) => {
                const isFormulaRequired = condition.display_group === "formula_required" || condition.validation_status === "new_indicator_required" || condition.source === "rule_base_candidate";
                return (
                  <tr key={`${kind}-${index}-${condition.indicator_key || condition.source_text}`} className={isFormulaRequired ? "is-formula-required" : ""}>
                    <td>
                      <input
                        className="pattern-setup-checkbox"
                        type="checkbox"
                        checked={condition.gpt_verify_selected !== false}
                        onChange={(event) => onUpdateFilter(kind, index, { gpt_verify_selected: event.target.checked })}
                        aria-label="GPT 검증 대상으로 선택"
                      />
                    </td>
                    <td>{condition.natural_text || condition.source_text || "-"}</td>
                    <td>
                      <strong>{condition.label || condition.indicator_key || "-"}</strong>
                      <code>{formatConditionExpression(condition, "reference")}</code>
                    </td>
                    <td>
                      <span className={`pattern-status-badge ${isFormulaRequired ? "pattern-status-needs_review" : "pattern-status-calculated"}`}>
                        {isFormulaRequired ? "수식화 필요" : "GPT 검증 대상"}
                      </span>
                      {isFormulaRequired ? <small>현재 기본 지표에는 없지만 GPT가 수식화 가능성을 검토합니다.</small> : null}
                    </td>
                    <td><ConditionValueEditor value={condition.value} onChange={(value) => onUpdateFilter(kind, index, { value })} /></td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      <div className="pattern-next-guide">
        <strong>다음 단계로 가기 전 확인하세요.</strong>
        <span>성공/실패 기준이 맞습니까?</span>
        <span>자연어 문장이 빠짐없이 해석되었습니까?</span>
        <span>GPT에게 검증받을 조건이 모두 체크되어 있습니까?</span>
        <span>수식화 필요 항목이 누락되지 않았습니까?</span>
        <button className="btn btn-primary" type="button" onClick={onNext}>다음: 수식화 GPT 검증 및 확정</button>
        <em>2단계에서 각 조건을 포함 조건, 제외 조건, 비교용, 사용안함 중 하나로 최종 확정합니다.</em>
      </div>
    </div>
  );
}

function PatternFormulaSummary({ parsed }: { parsed: PatternGoalParseResponse | null }) {
  const goal = parsed?.parsed_goal || {};
  const success = goal.success_criteria || goal.success_rule || null;
  const failure = goal.failure_criteria || goal.failure_rule || null;
  const entryFilters = ((goal.entry_filters || []) as Array<Record<string, any>>).filter((condition) => condition.gpt_verify_selected !== false);
  const excludeFilters = ((goal.exclude_filters || []) as Array<Record<string, any>>).filter((condition) => condition.gpt_verify_selected !== false);
  const referenceConditions = (goal.reference_conditions || []) as Array<Record<string, any>>;
  const alwaysCount = [success, failure].filter(Boolean).length;
  const formulaRequiredItems = [
    ...[...entryFilters, ...excludeFilters].filter((item) => item.display_group === "formula_required" || item.validation_status === "new_indicator_required"),
    ...((goal.unsupported_items || parsed?.unsupported_items || []) as Array<Record<string, any>>).filter((item) => item.display_group === "formula_required" || item.indicator_key),
  ];
  const gptTargets = [...entryFilters, ...excludeFilters].filter((item) => item.status !== "unsupported" && item.display_group !== "formula_required");
  const selectedCount = [...entryFilters, ...excludeFilters].filter((item) => item.gpt_verify_selected !== false).length;

  if (!parsed) {
    return <div className="pattern-empty-note">목표 해석 후 항상 적용, GPT 검증 대상, 수식화 필요 항목 요약이 표시됩니다.</div>;
  }

  return (
    <div className="pattern-formula-summary-grid">
      <Kpi label="항상 적용" value={`${alwaysCount}개`} />
      <Kpi label="GPT 검증 대상" value={`${gptTargets.length}개`} />
      <Kpi label="수식화 필요" value={`${formulaRequiredItems.length}개`} />
      <Kpi label="선택된 검증 항목" value={`${selectedCount}개`} />
    </div>
  );
}

function SampleReadinessCard({
  parsed,
  unresolvedConditions,
  canCreateSamples,
  onGoToGpt,
}: {
  parsed: PatternGoalParseResponse | null;
  unresolvedConditions: Array<Record<string, any>>;
  canCreateSamples: boolean;
  onGoToGpt: () => void;
}) {
  const statusText = !parsed
    ? "목표 해석 필요"
    : canCreateSamples
      ? "샘플 생성 가능"
      : "샘플 생성 보류";

  return (
    <div className={`sample-readiness-card ${canCreateSamples ? "is-ready" : "is-blocked"}`}>
      <div>
        <strong>{statusText}</strong>
        <span>
          {canCreateSamples
            ? "확정된 조건으로 성공/실패 샘플을 생성할 수 있습니다."
            : "신규 지표 조건은 기준정보 등록 또는 1회성 사용 확정 전까지 샘플 필터에 자동 반영하지 않습니다."}
        </span>
      </div>
      {unresolvedConditions.length ? (
        <div className="sample-readiness-reasons">
          <em>차단 사유 {unresolvedConditions.length}개</em>
          {unresolvedConditions.slice(0, 4).map((condition, index) => (
            <span key={`sample-blocker-${index}`}>
              {condition.indicator_key || condition.label || condition.source_text || "-"} · {friendlyStatusLabel(condition.validation_status)}
            </span>
          ))}
        </div>
      ) : null}
      {!canCreateSamples ? (
        <button className="btn btn-secondary next-step-action" type="button" onClick={onGoToGpt}>
          신규 지표 후보 처리하기
        </button>
      ) : null}
    </div>
  );
}

function SampleReadinessCardV2({
  parsed,
  blockers,
  canCreateSamples,
  onUseAsReference,
  onTurnOff,
  onGoToGpt,
}: {
  parsed: PatternGoalParseResponse | null;
  blockers: SampleBlocker[];
  canCreateSamples: boolean;
  onUseAsReference: () => void;
  onTurnOff: () => void;
  onGoToGpt: () => void;
}) {
  const statusText = !parsed ? "목표 해석 필요" : canCreateSamples ? "샘플 생성 가능" : "샘플 생성 전 확인이 필요합니다";
  return (
    <div className={`sample-readiness-card ${canCreateSamples ? "is-ready" : "is-blocked"}`}>
      <div>
        <strong>{statusText}</strong>
        <span>
          {canCreateSamples
            ? "확정한 조건으로 성공/실패 샘플을 생성할 수 있습니다."
            : "일부 조건은 새로 계산해야 하는 지표입니다. 해당 지표가 포함 조건 또는 제외 조건으로 선택되어 있으면 샘플 생성 전에 처리 방식이 필요합니다."}
        </span>
      </div>
      {blockers.length ? (
        <div className="sample-readiness-reasons">
          <em>미해결 조건 {blockers.length}개</em>
          {blockers.slice(0, 4).map((blocker) => (
            <div className="sample-readiness-blocker-card" key={blocker.rowId}>
              <strong>{blocker.label}</strong>
              <span>원문: {blocker.sourceText}</span>
              <span>제안 수식: {blocker.expression}</span>
              <span>현재 사용 방식: {usageLabel(blocker.finalUsage)}</span>
              <span>계산 유형: {blocker.calculationType}</span>
              <span>현재 상태: 엔진 보완 필요</span>
              <span>필요한 처리: 비교용으로 전환하거나 사용안함으로 변경한 뒤 샘플을 생성할 수 있습니다.</span>
            </div>
          ))}
        </div>
      ) : null}
      {!canCreateSamples ? (
        <div className="sample-readiness-actions">
          <button className="btn btn-primary next-step-action" type="button" onClick={onUseAsReference}>비교용으로 바꾸고 샘플 생성</button>
          <button className="btn btn-secondary next-step-action" type="button" onClick={onTurnOff}>사용안함으로 바꾸고 샘플 생성</button>
          <button className="btn btn-secondary next-step-action" type="button" onClick={onGoToGpt}>2단계에서 직접 수정</button>
        </div>
      ) : null}
    </div>
  );
}

function PatternConfirmPanel({
  parsed,
  gptValidation,
  unresolvedConditions,
  onGoToGpt,
  onGoToCandidate,
}: {
  parsed: PatternGoalParseResponse | null;
  gptValidation: PatternGptGoalResultValidateResponse | null;
  unresolvedConditions: Array<Record<string, any>>;
  onGoToGpt: () => void;
  onGoToCandidate: (indicatorKey: string) => void;
}) {
  const goal = parsed?.parsed_goal || {};
  const confirmed: Array<Record<string, any> & { groupLabel: string }> = [
    ...((goal.success_criteria ? [{ ...goal.success_criteria, groupLabel: "성공 기준" }] : []) as Array<Record<string, any> & { groupLabel: string }>),
    ...((goal.failure_criteria ? [{ ...goal.failure_criteria, groupLabel: "실패 기준" }] : []) as Array<Record<string, any> & { groupLabel: string }>),
    ...(((goal.entry_filters || []) as Array<Record<string, any>>).map((item) => ({ ...item, groupLabel: "진입 조건" }))),
    ...(((goal.exclude_filters || []) as Array<Record<string, any>>).map((item) => ({ ...item, groupLabel: "제외 조건" }))),
  ];
  const gptReference = ((gptValidation?.validated_conditions || []) as Array<Record<string, any>>).filter(
    (condition) => condition.validation_status !== "new_indicator_required",
  );
  const newCandidates = (gptValidation?.new_indicator_candidates || []) as Array<Record<string, any>>;
  const candidateByKey = new Map(newCandidates.map((candidate) => [String(candidate.indicator_key || ""), candidate]));
  const needsReview = confirmed.filter((condition) => condition.status === "needs_review" || condition.validation_status === "needs_review");

  return (
    <div className="pattern-confirm-layout">
      <div className="pattern-confirm-card condition-section-card">
        <h4>확정 조건 목록 <span>{confirmed.length}개</span></h4>
        {confirmed.length ? (
          <div className="pattern-confirm-list">
            {confirmed.map((condition, index) => (
              <div key={`confirmed-${index}`} className="pattern-confirm-item">
                <strong>{condition.label || condition.natural_text || condition.source_text || expressionForCondition(condition)}</strong>
                <span>{condition.groupLabel} · {condition.source === "gpt_candidate_confirmed" ? "GPT 후보 반영" : condition.source || "기본 해석"}</span>
                <em>{friendlyStatusLabel(condition.validation_status || condition.status)}</em>
              </div>
            ))}
          </div>
        ) : (
          <div className="pattern-empty-note">아직 확정 조건이 없습니다. 1단계 목표 해석 또는 2단계 GPT 후보 반영을 진행해 주세요.</div>
        )}
      </div>
      <div className="pattern-confirm-card condition-section-card is-warning">
        <h4>신규 지표 필요 조건 <span>{unresolvedConditions.length}개</span></h4>
        {unresolvedConditions.length ? (
          <>
            <div className="pattern-confirm-list">
              {unresolvedConditions.map((condition, index) => {
                const linkedCandidate = candidateByKey.get(String(condition.indicator_key || ""));
                return (
                  <div key={`unresolved-${index}`} className="pattern-confirm-item unresolved-indicator-card">
                    <strong>{condition.label || condition.source_text || condition.indicator_key || "-"}</strong>
                    <span>{condition.indicator_key || "-"} · {friendlyStatusLabel(condition.validation_status)}</span>
                    <em>{condition.validation_message || "신규 지표 후보 확인 필요"}</em>
                    {linkedCandidate ? (
                      <button className="linked-candidate-badge" type="button" onClick={() => onGoToCandidate(String(condition.indicator_key || ""))}>
                        연결 후보 보기 · {friendlyStatusLabel(linkedCandidate.validation_status)}
                      </button>
                    ) : null}
                  </div>
                );
              })}
            </div>
            <button className="btn btn-secondary next-step-action" type="button" onClick={onGoToGpt}>신규 지표 후보 처리하기</button>
          </>
        ) : (
          <div className="pattern-empty-note">미해결 신규 지표 조건이 없습니다.</div>
        )}
      </div>
      <div className="pattern-confirm-card condition-section-card">
        <h4>GPT 검증 대상 조건 <span>{needsReview.length}개</span></h4>
        {needsReview.length ? (
          <div className="pattern-confirm-list">
            {needsReview.map((condition, index) => (
              <div key={`needs-review-${index}`} className="pattern-confirm-item">
                <strong>{condition.label || condition.natural_text || expressionForCondition(condition)}</strong>
                <span>{condition.groupLabel} · {condition.indicator_key || "-"}</span>
                <em>{friendlyStatusLabel(condition.validation_status || condition.status)}</em>
              </div>
            ))}
          </div>
        ) : (
          <div className="pattern-empty-note">사용자 확인이 필요한 기존 조건은 없습니다.</div>
        )}
      </div>
      <div className="pattern-confirm-card condition-section-card">
        <h4>조건 후보 <span>{gptReference.length}개</span></h4>
        {gptReference.length ? (
          <div className="pattern-confirm-list">
            {gptReference.slice(0, 6).map((condition, index) => (
              <div key={`gpt-reference-${index}`} className="pattern-confirm-item">
                <strong>{condition.label || condition.source_text || "-"}</strong>
                <span>{friendlyStatusLabel(condition.category)} · {condition.indicator_key || "-"}</span>
                <em>{friendlyStatusLabel(condition.validation_status)}</em>
              </div>
            ))}
          </div>
        ) : (
          <div className="pattern-empty-note">조건 후보가 아직 없습니다.</div>
        )}
      </div>
      <div className="pattern-confirm-card condition-section-card">
        <h4>신규 지표 후보 <span>{newCandidates.length}개</span></h4>
        {newCandidates.length ? (
          <div className="pattern-confirm-list">
            {newCandidates.map((candidate, index) => (
              <div key={`new-candidate-${index}`} className="pattern-confirm-item">
                <strong>{candidate.indicator_key || "-"}</strong>
                <span>{candidate.calculation_type || "-"} · {(candidate.required_indicators || []).join(", ") || "-"}</span>
                <em>{friendlyStatusLabel(candidate.validation_status)}</em>
              </div>
            ))}
          </div>
        ) : (
          <div className="pattern-empty-note">신규 지표 후보가 없습니다.</div>
        )}
      </div>
    </div>
  );
}

function GoalInterpretation({
  parsed,
  onUpdateCriteria,
  onUpdateFilter,
  onChangeUsage,
}: {
  parsed: PatternGoalParseResponse | null;
  onUpdateCriteria: (kind: "success_criteria" | "failure_criteria", key: string, value: any) => void;
  onUpdateFilter: (kind: "entry_filters" | "exclude_filters", index: number, updates: Record<string, any>) => void;
  onChangeUsage: (kind: "entry_filters" | "exclude_filters", index: number, usage: ConditionUsage) => void;
}) {
  if (!parsed) return <div className="pattern-empty-card">목표 해석 전입니다. 자연어 목표를 입력하고 해석해 주세요.</div>;
  const goal = parsed.parsed_goal;
  const success = goal.success_criteria || goal.success_rule || {};
  const failure = goal.failure_criteria || goal.failure_rule || {};
  const entryFilters = goal.entry_filters || parsed.entry_filters || [];
  const excludeFilters = goal.exclude_filters || parsed.exclude_filters || [];
  const unsupportedItems = parsed.unsupported_items || [];
  const warnings = goal.warnings || parsed.warnings || [];

  return (
    <div className="pattern-goal-interpretation">
      {warnings.length > 0 ? (
        <div className="pattern-warning-list">
          {warnings.map((warning: string, index: number) => <span key={`warning-${index}`}>⚠ {warning}</span>)}
        </div>
      ) : null}
      <div className="pattern-condition-help">
        체크한 항목 = GPT 검증 대상입니다. 2단계에서는 각 수식을 포함 조건, 제외 조건, 비교용, 사용안함 중 하나로 확정합니다.
      </div>
      <div className="table-shell pattern-condition-shell">
        <table className="data-table compact-table pattern-condition-table">
          <thead>
            <tr>
              <th>자연어 표현</th>
              <th>해석 수식</th>
              <th>사용 지표</th>
              <th>1단계 구분</th>
              <th>해석 출처</th>
              <th>최종 사용 방식</th>
              <th>해석 상태</th>
              <th>수정값</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td>{success.natural_text || "목표 수익률"}</td>
              <td>{success.expression || expressionForCondition({ indicator_key: `max_future_return_${success.target_days || goal.target_days}d`, operator: ">=", value: success.target_return_pct || goal.target_return_pct })}</td>
              <td>미래 최대수익률</td>
              <td>항상 적용</td>
              <td>{success.source || "rule_base"}</td>
              <td>항상 적용</td>
              <td><em className={`pattern-status-badge pattern-status-${statusClass(success.status || "applied")}`}>{success.interpretation_status_label || statusLabel(success.status || "applied")}</em></td>
              <td>
                <div className="pattern-condition-value-inputs">
                  <label><span>수익률</span><input type="number" value={success.target_return_pct ?? goal.target_return_pct ?? ""} onChange={(event) => onUpdateCriteria("success_criteria", "target_return_pct", Number(event.target.value))} /></label>
                  <label><span>거래일</span><input type="number" value={success.target_days ?? goal.target_days ?? ""} onChange={(event) => onUpdateCriteria("success_criteria", "target_days", Number(event.target.value))} /></label>
                </div>
              </td>
            </tr>
            <tr>
              <td>{failure.natural_text || "손절 기준"}</td>
              <td>{failure.expression || expressionForCondition({ indicator_key: `min_future_return_${success.target_days || goal.target_days}d`, operator: "<=", value: failure.stop_loss_pct || goal.stop_loss_pct })}</td>
              <td>미래 최대하락률</td>
              <td>항상 적용</td>
              <td>{failure.source || "rule_base"}</td>
              <td>항상 적용</td>
              <td><em className={`pattern-status-badge pattern-status-${statusClass(failure.status || "applied")}`}>{failure.interpretation_status_label || statusLabel(failure.status || "applied")}</em></td>
              <td>
                <div className="pattern-condition-value-inputs">
                  <label><span>손절%</span><input type="number" value={failure.stop_loss_pct ?? goal.stop_loss_pct ?? ""} onChange={(event) => onUpdateCriteria("failure_criteria", "stop_loss_pct", Number(event.target.value))} /></label>
                </div>
              </td>
            </tr>
            {entryFilters.map((condition: Record<string, any>, index: number) => (
              <ConditionRow
                key={`entry-${index}`}
                condition={condition}
                category="GPT 검증 대상"
                kind="entry_filters"
                onChangeUsage={(usage) => onChangeUsage("entry_filters", index, usage)}
                onChangeValue={(value) => onUpdateFilter("entry_filters", index, { value })}
              />
            ))}
            {excludeFilters.map((condition: Record<string, any>, index: number) => (
              <ConditionRow
                key={`exclude-${index}`}
                condition={condition}
                category="GPT 검증 대상"
                kind="exclude_filters"
                onChangeUsage={(usage) => onChangeUsage("exclude_filters", index, usage)}
                onChangeValue={(value) => onUpdateFilter("exclude_filters", index, { value })}
              />
            ))}
            {unsupportedItems.map((item, index) => (
              <tr key={`unsupported-${index}`}>
                <td>{item.natural_text || item.source_text || JSON.stringify(item)}</td>
                <td>-</td>
                <td>{item.indicator_key || "-"}</td>
                <td>수식화 필요</td>
                <td>{item.source || "-"}</td>
                <td>GPT 검증 대상</td>
                <td><em className="pattern-status-badge pattern-status-needs_review">수식화 필요</em></td>
                <td>-</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function ConditionRow({
  condition,
  category,
  kind,
  onChangeUsage,
  onChangeValue,
}: {
  condition: Record<string, any>;
  category: string;
  kind: "entry_filters" | "exclude_filters";
  onChangeUsage: (usage: ConditionUsage) => void;
  onChangeValue: (value: any) => void;
}) {
  const usage = usageForCondition(condition, kind);
  return (
    <tr>
      <td>{condition.natural_text || condition.source_text || "-"}</td>
      <td>{condition.expression || expressionForCondition(condition)}</td>
      <td>{condition.indicator_key || condition.indicator || "-"}</td>
      <td>{category}</td>
      <td>{condition.source || "-"}</td>
      <td>
        <select className="input-control" value={usage} onChange={(event) => onChangeUsage(event.target.value as ConditionUsage)}>
          <option value="include">포함 조건으로 사용</option>
          <option value="exclude">제외 조건으로 사용</option>
          <option value="reference">비교용으로만 사용</option>
          <option value="off">사용안함</option>
        </select>
        <small className="disabled-action-help">{applyModeLabel(condition)}</small>
      </td>
      <td><em className={`pattern-status-badge pattern-status-${statusClass(condition.status || "needs_review")}`}>{condition.interpretation_status_label || statusLabel(condition.status || "needs_review")}</em></td>
      <td><ConditionValueEditor value={condition.value} onChange={onChangeValue} /></td>
    </tr>
  );
}

function ConditionValueEditor({ value, onChange }: { value: any; onChange: (value: any) => void }) {
  if (Array.isArray(value)) {
    return (
      <div className="pattern-condition-value-inputs">
        <input type="number" value={value[0] ?? ""} onChange={(event) => onChange([Number(event.target.value), value[1]])} />
        <span>~</span>
        <input type="number" value={value[1] ?? ""} onChange={(event) => onChange([value[0], Number(event.target.value)])} />
      </div>
    );
  }
  if (typeof value === "number") {
    return <input className="pattern-condition-single-input" type="number" value={value} onChange={(event) => onChange(Number(event.target.value))} />;
  }
  if (value === null || value === undefined || value === "") return <span>-</span>;
  return <span>{String(value)}</span>;
}

type VerifyRowKind = "always" | "parsed_entry" | "parsed_exclude" | "parsed_reference" | "gpt_condition" | "new_indicator" | "unsupported";
type VerifyRow = {
  key: string;
  kind: VerifyRowKind;
  conditionType?: string;
  finalUsage?: ConditionUsage | "always";
  condition: Record<string, any>;
  index?: number;
  linkedCandidate?: Record<string, any>;
  warnings?: Array<unknown>;
  conflicts?: Array<Record<string, any>>;
};

function isAlwaysCriteriaRow(row: VerifyRow): boolean {
  const condition = row.condition || {};
  const linked = row.linkedCandidate || {};
  const candidates = [
    row.conditionType,
    row.kind,
    condition.conditionType,
    condition.type,
    condition.kind,
    condition.group,
    condition.role,
    condition.usage,
    condition.category,
    condition.original?.conditionType,
    condition.original?.type,
    condition.original?.kind,
    condition.original?.group,
    condition.original?.role,
    condition.original?.usage,
    condition.original?.category,
    linked.conditionType,
    linked.type,
    linked.kind,
    linked.group,
    linked.role,
    linked.usage,
    linked.category,
  ].map((value) => String(value || ""));
  return candidates.some((value) => value === "success_criteria" || value === "failure_criteria");
}

function compactCategoryLabel(value: unknown): string {
  const raw = String(value || "");
  const labels: Record<string, string> = {
    success_criteria: "항상 적용",
    failure_criteria: "항상 적용",
    entry_filter: "조건 후보",
    exclude_filter: "제외 후보",
    reference_condition: "비교용 후보",
    reference: "비교용 후보",
  };
  return labels[raw] || friendlyStatusLabel(raw);
}

function candidateTitle(condition: Record<string, any>): string {
  return String(condition.label || condition.indicator_name || condition.natural_text || condition.source_text || condition.indicator_key || condition.expression || "-");
}

function conditionBrief(condition: Record<string, any>): string {
  return formatConditionExpression(condition);
}

function relatedMessages<T extends Record<string, any> | unknown>(
  items: T[],
  condition: Record<string, any>,
): T[] {
  const source = String(condition.source_text || condition.natural_text || condition.label || "");
  const indicator = String(condition.indicator_key || condition.indicator || "");
  return items.filter((item) => {
    if (!item || typeof item !== "object") return source ? String(item).includes(source) : false;
    const row = item as Record<string, any>;
    const text = String(row.source_text || row.natural_text || row.message || row.warning || row.reason || "");
    const key = String(row.indicator_key || row.suggested_indicator_key || "");
    return Boolean((source && text.includes(source)) || (indicator && key === indicator));
  });
}

function PatternVerifyDecisionPanel({
  parsed,
  loading,
  promptText,
  showPrompt,
  showResultInput,
  resultText,
  validation,
  validationStatus,
  resultRef,
  finalUsageByRowId,
  focusedRowIds,
  blockedBannerMessage,
  onFinalUsageChange,
  onTogglePrompt,
  onToggleResultInput,
  onCopyPrompt,
  onChangeResultText,
  onValidate,
  onApplyCandidate,
  onSaveIndicatorCandidate,
  onMarkDecision,
  onUpdateCriteria,
  onUpdateFilter,
  onChangeUsage,
  onNext,
}: {
  parsed: PatternGoalParseResponse | null;
  loading: boolean;
  promptText: string;
  showPrompt: boolean;
  showResultInput: boolean;
  resultText: string;
  validation: PatternGptGoalResultValidateResponse | null;
  validationStatus: GptValidationStatus;
  resultRef: { current: HTMLDivElement | null };
  finalUsageByRowId: FinalUsageMap;
  focusedRowIds?: string[];
  blockedBannerMessage?: string;
  onFinalUsageChange: (rowId: string, usage: ConditionUsage) => void;
  onTogglePrompt: () => void;
  onToggleResultInput: () => void;
  onCopyPrompt: () => Promise<void>;
  onChangeResultText: (value: string) => void;
  onValidate: () => Promise<void>;
  onApplyCandidate: (candidate: Record<string, any>, applyToSamples: boolean) => void;
  onSaveIndicatorCandidate: (candidate: Record<string, any>) => Promise<void>;
  onMarkDecision: (decision: string, targetText?: string | Record<string, any>) => void;
  onUpdateCriteria: (kind: "success_criteria" | "failure_criteria", key: string, value: any) => void;
  onUpdateFilter: (kind: "entry_filters" | "exclude_filters", index: number, updates: Record<string, any>) => void;
  onChangeUsage: (kind: "entry_filters" | "exclude_filters", index: number, usage: ConditionUsage) => void;
  onNext: () => void;
}) {
  const [expandedRows, setExpandedRows] = useState<Record<string, boolean>>({});
  const [showAllMessages, setShowAllMessages] = useState(false);
  const goal = parsed?.parsed_goal || {};
  const success = goal.success_criteria || goal.success_rule || null;
  const failure = goal.failure_criteria || goal.failure_rule || null;
  const entryFilters = (goal.entry_filters || []) as Array<Record<string, any>>;
  const excludeFilters = (goal.exclude_filters || []) as Array<Record<string, any>>;
  const referenceConditions = (goal.reference_conditions || []) as Array<Record<string, any>>;
  const gptConditions = (validation?.validated_conditions || []) as Array<Record<string, any>>;
  const newCandidates = (validation?.new_indicator_candidates || []) as Array<Record<string, any>>;
  const temporaryIndicators = (goal.temporary_indicators || []) as Array<Record<string, any>>;
  const unsupported = [...((goal.unsupported_items || parsed?.unsupported_items || []) as Array<Record<string, any>>), ...((validation?.unsupported_items || []) as Array<Record<string, any>>)];
  const warnings = (validation?.warnings || []) as Array<unknown>;
  const conflicts = (validation?.interpretation_conflicts || []) as Array<Record<string, any>>;
  const candidateByKey = new Map(
    [...temporaryIndicators, ...newCandidates, ...unsupported.filter((item) => item.indicator_key)].map((candidate) => [String(candidate.indicator_key || ""), candidate]),
  );
  const parsedIdentities = new Set([...entryFilters, ...excludeFilters, ...referenceConditions].map((condition) => conditionIdentity(condition)));
  const gptRows = gptConditions.filter((condition) => !parsedIdentities.has(conditionIdentity(condition)));
  const gptKeys = new Set(gptRows.map((condition) => String(condition.indicator_key || "")));
  const rowIndicatorKeys = new Set([...entryFilters, ...excludeFilters, ...referenceConditions, ...gptRows].map((condition) => String(condition.indicator_key || condition.indicator || "")));
  const standaloneCandidates = newCandidates.filter((candidate) => !gptKeys.has(String(candidate.indicator_key || "")) && !rowIndicatorKeys.has(String(candidate.indicator_key || "")));
  const standaloneUnsupported = unsupported.filter((condition) => !rowIndicatorKeys.has(String(condition.indicator_key || "")));

  const rows: VerifyRow[] = [
    ...(success ? [{ key: conditionRowId("success_criteria", success, 0), kind: "always" as VerifyRowKind, conditionType: "success_criteria", finalUsage: "always" as const, condition: { ...success, conditionType: "success_criteria", label: success.label || "목표 수익률" } }] : []),
    ...(failure ? [{ key: conditionRowId("failure_criteria", failure, 0), kind: "always" as VerifyRowKind, conditionType: "failure_criteria", finalUsage: "always" as const, condition: { ...failure, conditionType: "failure_criteria", label: failure.label || "손절 기준" } }] : []),
    ...entryFilters.map((condition, index) => ({
      key: conditionRowId("parsed_entry", condition, index),
      kind: "parsed_entry" as VerifyRowKind,
      conditionType: "entry_filter",
      finalUsage: usageForCondition(condition, "entry_filters"),
      condition,
      index,
      linkedCandidate: candidateByKey.get(String(condition.indicator_key || condition.indicator || "")),
    })),
    ...excludeFilters.map((condition, index) => ({
      key: conditionRowId("parsed_exclude", condition, index),
      kind: "parsed_exclude" as VerifyRowKind,
      conditionType: "exclude_filter",
      finalUsage: usageForCondition(condition, "exclude_filters"),
      condition,
      index,
      linkedCandidate: candidateByKey.get(String(condition.indicator_key || condition.indicator || "")),
    })),
    ...referenceConditions.map((condition, index) => ({
      key: conditionRowId("reference_condition", condition, index),
      kind: "parsed_reference" as VerifyRowKind,
      conditionType: "reference_condition",
      finalUsage: "reference" as const,
      condition: { ...condition, apply_to_samples: false },
      index,
      linkedCandidate: candidateByKey.get(String(condition.indicator_key || condition.indicator || "")),
    })),
    ...gptRows.map((condition, index) => ({
      key: conditionRowId("gpt_condition", condition, index),
      kind: "gpt_condition" as VerifyRowKind,
      conditionType: String(condition.category || "reference_condition"),
      finalUsage: condition.category === "exclude_filter" ? "exclude" as const : condition.apply_to_samples ? "include" as const : "reference" as const,
      condition,
      linkedCandidate: candidateByKey.get(String(condition.indicator_key || "")),
      warnings: relatedMessages(warnings, condition),
      conflicts: relatedMessages(conflicts, condition),
    })),
    ...standaloneCandidates.map((condition, index) => ({
      key: conditionRowId("new_indicator", condition, index),
      kind: "new_indicator" as VerifyRowKind,
      conditionType: "new_indicator_candidate",
      finalUsage: "reference" as const,
      condition,
      linkedCandidate: condition,
    })),
    ...standaloneUnsupported.map((condition, index) => ({
      key: conditionRowId("formula_required", condition, index),
      kind: "unsupported" as VerifyRowKind,
      conditionType: "formula_required",
      finalUsage: "reference" as const,
      condition,
      linkedCandidate: candidateByKey.get(String(condition.indicator_key || "")),
    })),
  ];
  const focusedRowIdSet = new Set(focusedRowIds || []);

  useEffect(() => {
    if (!focusedRowIds?.length) return;
    window.setTimeout(() => {
      document.querySelector(".pattern-new-indicator-focus")?.scrollIntoView({ behavior: "smooth", block: "center" });
    }, 0);
  }, [focusedRowIds?.join("|")]);

  const getEffectiveFinalUsage = (row: VerifyRow): ConditionUsage | "always" => {
    if (isAlwaysCriteriaRow(row)) return "always";
    return finalUsageByRowId[row.key] || row.finalUsage || "reference";
  };

  const usageCounts = rows.reduce(
    (acc, row) => {
      const usage = getEffectiveFinalUsage(row);
      if (usage === "always") acc.always += 1;
      else if (usage === "include") acc.include += 1;
      else if (usage === "exclude") acc.exclude += 1;
      else if (usage === "off") acc.off += 1;
      else acc.reference += 1;
      return acc;
    },
    { always: 0, include: 0, exclude: 0, reference: 0, off: 0 },
  );
  const newIndicatorCount = rows.filter((row) => row.linkedCandidate || row.condition.validation_status === "new_indicator_required" || row.condition.display_group === "formula_required").length;

  const handleUsageChange = (row: VerifyRow, usage: ConditionUsage) => {
    onFinalUsageChange(row.key, usage);
    if (row.kind === "gpt_condition") {
      if (usage === "include") onApplyCandidate({ ...row.condition, category: "entry_filter" }, true);
      else if (usage === "exclude") onApplyCandidate({ ...row.condition, category: "exclude_filter", exclude_when_true: true }, true);
      else if (usage === "reference") onApplyCandidate(row.condition, false);
      else onMarkDecision("exclude", row.condition.label || row.condition.source_text);
    } else if (row.kind === "new_indicator") {
      if (usage === "off") onMarkDecision("exclude", row.condition);
      else onMarkDecision("reference", row.condition.indicator_key || row.condition.source_text);
    } else if (row.kind === "unsupported") {
      onMarkDecision(usage === "off" ? "exclude" : "reference", row.condition.indicator_key || row.condition.source_text);
    }
  };

  const handleValueChange = (row: VerifyRow, value: any) => {
    if (row.kind === "parsed_entry" && row.index !== undefined) onUpdateFilter("entry_filters", row.index, { value });
    if (row.kind === "parsed_exclude" && row.index !== undefined) onUpdateFilter("exclude_filters", row.index, { value });
  };

  const uniqueSummaryRows = (items: VerifyRow[]) => {
    const seen = new Set<string>();
    return items.filter((row) => {
      const key = row.key;
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    });
  };

  const summaryGroups = [
    { label: "항상 적용", rows: uniqueSummaryRows(rows.filter((row) => getEffectiveFinalUsage(row) === "always")) },
    { label: "포함 조건", rows: uniqueSummaryRows(rows.filter((row) => getEffectiveFinalUsage(row) === "include")) },
    { label: "제외 조건", rows: uniqueSummaryRows(rows.filter((row) => getEffectiveFinalUsage(row) === "exclude")) },
    { label: "비교용", rows: uniqueSummaryRows(rows.filter((row) => getEffectiveFinalUsage(row) === "reference")) },
    { label: "사용안함", rows: uniqueSummaryRows(rows.filter((row) => getEffectiveFinalUsage(row) === "off")) },
  ];

  return (
    <div className="pattern-verify-panel" ref={resultRef}>
      <p className="pattern-verify-description">
        GPT 검증 결과를 확인하고 각 조건의 최종 사용 방식을 정합니다. 사용 방식과 기준값을 확정하면 다음 단계에서 성공/실패 샘플을 생성합니다.
      </p>
      {blockedBannerMessage ? <div className="pattern-blocked-banner">{blockedBannerMessage}</div> : null}
      <div className="pattern-verify-summary">
        <span>전체 {rows.length}개</span>
        <span>항상 적용 {usageCounts.always}개</span>
        <span>포함 {usageCounts.include}개</span>
        <span>제외 {usageCounts.exclude}개</span>
        <span>비교용 {usageCounts.reference}개</span>
        <span>사용안함 {usageCounts.off}개</span>
        <span>새 지표 필요 {newIndicatorCount}개</span>
        <span>경고 {warnings.length}개</span>
        <span>해석 충돌 {conflicts.length}개</span>
      </div>

      <div className={`pattern-verify-gpt-box is-${validationStatus}`}>
        <div className="pattern-verify-gpt-head">
          <strong>{validationStatus === "success" ? "GPT 결과 검증 완료" : "GPT 결과 붙여넣기"}</strong>
          <span className={`pattern-llm-status pattern-llm-status-${validationStatus}`}>{gptValidationStatusLabel(validationStatus)}</span>
        </div>
        <div className="pattern-action-row">
          <button className="btn btn-secondary btn-compact" type="button" disabled={loading} onClick={() => void onCopyPrompt()}>
            <Clipboard size={14} /> GPT 목표 해석 요청문 복사
          </button>
          {promptText ? <button className="btn btn-secondary btn-compact" type="button" onClick={onTogglePrompt}>{showPrompt ? "요청문 접기" : "요청문 미리보기"}</button> : null}
          {validationStatus === "success" ? <button className="btn btn-secondary btn-compact" type="button" onClick={onToggleResultInput}>{showResultInput ? "붙여넣기 내용 접기" : "붙여넣기 내용 다시 보기"}</button> : null}
          {validationStatus === "success" && !showResultInput ? <button className="btn btn-secondary btn-compact" type="button" disabled={loading || !resultText.trim()} onClick={() => void onValidate()}>다시 검증하기</button> : null}
        </div>
        {showPrompt && promptText ? <textarea className="pattern-gpt-prompt compact" readOnly value={promptText} /> : null}
        {showResultInput || validationStatus !== "success" ? (
          <>
            <div className="pattern-gpt-json-help">
              이 영역에는 ChatGPT가 반환한 JSON 객체만 붙여넣어 주세요.
              <span>{resultText.length.toLocaleString("ko-KR")}자 입력됨</span>
            </div>
            <textarea
              className="pattern-gpt-result-input compact"
              value={resultText}
              onChange={(event) => onChangeResultText(event.target.value)}
              placeholder="GPT가 반환한 JSON을 여기에 붙여넣고 검증하세요."
            />
            <div className="pattern-action-row">
              <button className="btn btn-primary btn-compact" type="button" disabled={loading || !resultText.trim()} onClick={() => void onValidate()}>
                {validationStatus === "success" ? "다시 검증하기" : "GPT 결과 검증"}
              </button>
            </div>
          </>
        ) : (
          <div className="pattern-verify-result-summary">조건 후보 {gptConditions.length}개, 신규 지표 후보 {newCandidates.length}개를 검증했습니다.</div>
        )}
        {validationStatus === "failed" ? <div className="alert danger">검증 실패: {gptValidationErrorMessage(validation, "GPT 결과 검증에 실패했습니다.")}</div> : null}
      </div>

      <div className="table-shell pattern-verify-table-shell">
        <table className="data-table compact-table pattern-verify-table">
          <thead>
            <tr>
              <th>원문</th>
              <th>GPT 제안 수식</th>
              <th>상태</th>
              <th>최종 사용 방식</th>
              <th>기준값</th>
              <th>상세</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => {
              const usage = getEffectiveFinalUsage(row);
              const isExpanded = Boolean(expandedRows[row.key]);
              const rowWarnings = row.warnings || relatedMessages(warnings, row.condition);
              const rowConflicts = row.conflicts || relatedMessages(conflicts, row.condition);
              const newIndicatorUsageStatus = getNewIndicatorUsageStatus(row.condition, usage === "always" ? "reference" : usage, row.linkedCandidate);
              const statusBadges = [
                row.kind === "always" ? "항상 적용" : row.condition.validation_status === "new_indicator_required" || row.linkedCandidate ? "새 지표 필요" : row.condition.status === "needs_review" ? "확인 필요" : "검증 완료",
                row.linkedCandidate && (row.linkedCandidate.execution_supported || row.linkedCandidate.calculation_type === "distance_pct" || row.linkedCandidate.calculation_type === "rolling_high") ? "계산 가능" : "",
                rowWarnings.length ? "경고 있음" : "",
                rowConflicts.length ? "해석 충돌" : "",
              ].filter(Boolean);
              const renderedStatusBadges = Array.from(new Set([...statusBadges.filter((badge) => !String(badge).includes("계산")), ...newIndicatorStatusLabels(newIndicatorUsageStatus), row.condition.source === "auto_param_test" ? "자동 테스트 반영" : ""])).filter(Boolean);
              return (
                <>
                  <tr key={row.key} className={[focusedRowIdSet.has(row.key) ? "pattern-row-needs-action pattern-new-indicator-focus" : "", row.condition.source === "auto_param_test" ? "pattern-row-auto-applied auto-param-applied-row" : ""].filter(Boolean).join(" ") || undefined}>
                    <td title={String(row.condition.source_text || row.condition.natural_text || "")}>
                      <span className="pattern-verify-source">{row.condition.source_text || row.condition.natural_text || "-"}</span>
                    </td>
                    <td>
                      <strong className="pattern-verify-title">{candidateTitle(row.condition)}</strong>
                      <code>{formatConditionExpression(row.condition, usage)}</code>
                    </td>
                    <td>
                      <div className="pattern-verify-badges">
                        {renderedStatusBadges.map((badge) => <span key={`${row.key}-${badge}`}>{badge}</span>)}
                      </div>
                    </td>
                    <td>
                      {usage === "always" ? (
                        <span className="pattern-verify-locked">항상 적용</span>
                      ) : (
                        <select className="input-control pattern-verify-compact-select" value={usage} onChange={(event) => handleUsageChange(row, event.target.value as ConditionUsage)}>
                          <option value="include">포함 조건으로 사용</option>
                          <option value="exclude">제외 조건으로 사용</option>
                          <option value="reference">비교용으로만 사용</option>
                          <option value="off">사용안함</option>
                        </select>
                      )}
                    </td>
                    <td>
                      {row.kind === "always" && row.condition.target_return_pct !== undefined ? (
                        <div className="pattern-condition-value-inputs compact">
                          <input type="number" value={row.condition.target_return_pct ?? ""} onChange={(event) => onUpdateCriteria("success_criteria", "target_return_pct", Number(event.target.value))} />
                          <input type="number" value={row.condition.target_days ?? goal.target_days ?? ""} onChange={(event) => onUpdateCriteria("success_criteria", "target_days", Number(event.target.value))} />
                        </div>
                      ) : row.kind === "always" && row.condition.stop_loss_pct !== undefined ? (
                        <input className="pattern-condition-single-input" type="number" value={row.condition.stop_loss_pct ?? ""} onChange={(event) => onUpdateCriteria("failure_criteria", "stop_loss_pct", Number(event.target.value))} />
                      ) : row.kind === "parsed_entry" || row.kind === "parsed_exclude" ? (
                        <ConditionValueEditor value={row.condition.value} onChange={(value) => handleValueChange(row, value)} />
                      ) : (
                        <ConditionValueEditor value={row.condition.value} onChange={() => undefined} />
                      )}
                    </td>
                    <td>
                      <button className="btn btn-secondary btn-compact" type="button" onClick={() => setExpandedRows((prev) => ({ ...prev, [row.key]: !prev[row.key] }))}>
                        {isExpanded ? "접기" : "상세"}
                      </button>
                    </td>
                  </tr>
                  {isExpanded ? (
                    <tr className="pattern-verify-row-detail" key={`${row.key}-detail`}>
                      <td colSpan={6}>
                        <div>
                          <span>구분: {compactCategoryLabel(row.condition.category || row.kind)}</span>
                          <span>지표: {row.condition.indicator_key || row.condition.indicator || row.linkedCandidate?.indicator_key || "-"}</span>
                          <span>출처: {row.condition.source || "-"}</span>
                          {row.linkedCandidate ? <span>지표명: {row.linkedCandidate.indicator_name || row.linkedCandidate.indicator_key || "-"}</span> : null}
                          {row.linkedCandidate ? <span>계산 유형: {row.linkedCandidate.calculation_type || "-"}</span> : null}
                          {row.linkedCandidate ? <span>필요 지표: {(row.linkedCandidate.required_indicators || []).join(", ") || "-"}</span> : null}
                          {row.linkedCandidate?.execution_message ? <span>처리 상태: {row.linkedCandidate.execution_message}</span> : null}
                          {row.kind === "new_indicator" ? (
                            <span className="pattern-verify-detail-actions">
                              <button className="btn btn-secondary btn-compact" type="button" onClick={() => onMarkDecision("one_time", row.condition)}>이번 연구에서 1회성 사용</button>
                              <button className="btn btn-secondary btn-compact" type="button" onClick={() => void onSaveIndicatorCandidate(row.condition)}>지표 기준정보 등록</button>
                            </span>
                          ) : null}
                          {rowWarnings.map((item, index) => <span key={`warning-${index}`}>경고: {itemText(item, "message", "warning")}</span>)}
                          {rowConflicts.map((item, index) => <span key={`conflict-${index}`}>해석 충돌: {item.gpt_correction || item.drct_first_pass || item.source_text || "-"}</span>)}
                        </div>
                      </td>
                    </tr>
                  ) : null}
                </>
              );
            })}
          </tbody>
        </table>
      </div>

      <div className="pattern-verify-result-summary-grid">
        {summaryGroups.map((group) => (
          <div key={group.label} className="pattern-verify-result-card">
            <strong>{group.label}</strong>
            {group.rows.length ? group.rows.slice(0, 5).map((row) => <span key={`${group.label}-${row.key}`}>{candidateTitle(row.condition)}: {formatConditionExpression(row.condition, getEffectiveFinalUsage(row))}</span>) : <em>없음</em>}
          </div>
        ))}
      </div>

      {warnings.length || conflicts.length ? (
        <div className="pattern-verify-all-messages">
          <button className="btn btn-secondary btn-compact" type="button" onClick={() => setShowAllMessages((prev) => !prev)}>
            전체 경고/해석 충돌 {showAllMessages ? "접기" : "보기"}
          </button>
          {showAllMessages ? (
            <div>
              {warnings.map((item, index) => <span key={`all-warning-${index}`}>경고: {itemText(item, "message", "warning")}</span>)}
              {conflicts.map((item, index) => <span key={`all-conflict-${index}`}>해석 충돌: {item.source_text || "-"} / {item.gpt_correction || item.drct_first_pass || "-"}</span>)}
            </div>
          ) : null}
        </div>
      ) : null}

      <div className="pattern-action-row pattern-verify-next-row">
        <button className="btn btn-primary" type="button" disabled={!parsed} onClick={onNext}>다음: 성공/실패 샘플 추출</button>
      </div>
    </div>
  );
}

function GptGoalResultPanelV2({
  loading,
  promptText,
  showPrompt,
  resultText,
  validation,
  validationStatus,
  resultRef,
  onTogglePrompt,
  onCopyPrompt,
  onChangeResultText,
  onValidate,
  onApplyCandidate,
  onSaveIndicatorCandidate,
  onMarkDecision,
}: {
  loading: boolean;
  promptText: string;
  showPrompt: boolean;
  resultText: string;
  validation: PatternGptGoalResultValidateResponse | null;
  validationStatus: GptValidationStatus;
  resultRef: { current: HTMLDivElement | null };
  onTogglePrompt: () => void;
  onCopyPrompt: () => Promise<void>;
  onChangeResultText: (value: string) => void;
  onValidate: () => Promise<void>;
  onApplyCandidate: (candidate: Record<string, any>, applyToSamples: boolean) => void;
  onSaveIndicatorCandidate: (candidate: Record<string, any>) => Promise<void>;
  onMarkDecision: (decision: string, targetText?: string | Record<string, any>) => void;
}) {
  const conditions = (validation?.validated_conditions || []) as Array<Record<string, any>>;
  const candidates = (validation?.new_indicator_candidates || []) as Array<Record<string, any>>;
  const unsupported = (validation?.unsupported_items || []) as Array<Record<string, any>>;
  const warnings = (validation?.warnings || []) as Array<unknown>;
  const conflicts = (validation?.interpretation_conflicts || []) as Array<Record<string, any>>;
  const candidateByKey = new Map(candidates.map((candidate) => [String(candidate.indicator_key || ""), candidate]));
  const failedMessage = validationStatus === "failed" ? gptValidationErrorMessage(validation, "GPT 결과 검증에 실패했습니다.") : "";
  const hasResult = validationStatus === "success" || validationStatus === "failed" || Boolean(validation);
  const hasNoCandidates = validationStatus === "success" && conditions.length === 0 && candidates.length === 0;

  return (
    <div className="pattern-gpt-goal-panel">
      <div className="pattern-llm-panel-head">
        <h4>GPT 목표 해석 결과 붙여넣기</h4>
        <span className={`pattern-llm-status pattern-llm-status-${validationStatus}`}>{gptValidationStatusLabel(validationStatus)}</span>
      </div>
      <div className="pattern-action-row">
        <button className="btn btn-secondary" type="button" disabled={loading} onClick={() => void onCopyPrompt()}>
          <Clipboard size={15} /> GPT 목표 해석 요청문 복사
        </button>
        {promptText ? <button className="btn btn-secondary" type="button" onClick={onTogglePrompt}>{showPrompt ? "요청문 접기" : "요청문 미리보기"}</button> : null}
      </div>
      {showPrompt && promptText ? <textarea className="pattern-gpt-prompt compact" readOnly value={promptText} /> : null}
      <div className="pattern-gpt-json-help">
        이 영역에는 ChatGPT가 반환한 JSON 객체만 붙여넣어 주세요. DrCT 요청문 전체를 붙여넣으면 검증에 실패할 수 있습니다.
        <span>{resultText.length.toLocaleString("ko-KR")}자 입력됨</span>
      </div>
      <textarea
        className="pattern-gpt-result-input"
        value={resultText}
        onChange={(event) => onChangeResultText(event.target.value)}
        placeholder="GPT가 반환한 JSON을 여기에 붙여넣고 검증하세요."
      />
      <div className="pattern-action-row">
        <button className="btn btn-primary" type="button" disabled={loading || !resultText.trim()} onClick={() => void onValidate()}>GPT 결과 검증</button>
      </div>
      {hasResult ? (
        <div ref={resultRef} className="pattern-gpt-validation-result">
          {validationStatus === "success" ? (
            <div className="pattern-gpt-summary-card">
              <strong>GPT 결과 검증 완료</strong>
              <span>
                조건 후보 {conditions.length}개 / 신규 지표 후보 {candidates.length}개 / 미지원 {unsupported.length}개 / 경고 {warnings.length}개
              </span>
            </div>
          ) : null}
          {failedMessage ? <div className="alert danger">검증 실패: {failedMessage}</div> : null}
          {hasNoCandidates ? (
            <div className="alert warning">
              검증은 완료되었지만 반영 가능한 조건 후보가 없습니다. GPT 반환 JSON의 conditions 또는 new_indicator_candidates 항목을 확인해 주세요.
            </div>
          ) : null}
          {conditions.length ? (
            <div className="table-shell pattern-llm-table-shell">
              <table className="data-table compact-table pattern-gpt-validation-table">
                <thead>
                  <tr><th>원문</th><th>조건명</th><th>수식</th><th>지표</th><th>구분</th><th>검증 상태</th><th>추천 방식</th><th>최종 사용 방식</th></tr>
                </thead>
                <tbody>
                  {conditions.map((condition, index) => {
                    const linkedCandidate = candidateByKey.get(String(condition.indicator_key || ""));
                    const cannotApplyToSamples = condition.validation_status === "rejected" || condition.validation_status === "new_indicator_required";
                    const cannotUseAsReference = condition.validation_status === "rejected";
                    return (
                      <tr key={`gpt-condition-${index}`}>
                        <td>{condition.source_text || "-"}</td>
                        <td>{condition.label || "-"}</td>
                        <td>{condition.expression || expressionForCondition(condition)}</td>
                        <td>{condition.indicator_key || "-"}</td>
                        <td>{condition.category || "-"}</td>
                        <td>
                          <span className={`condition-status-badge is-${condition.validation_status || "unknown"}`}>{friendlyStatusLabel(condition.validation_status)}</span>
                          {condition.validation_message ? <small className="disabled-action-help">{condition.validation_message}</small> : null}
                          {linkedCandidate ? (
                            <button className="linked-candidate-badge" type="button" onClick={() => scrollToIndicatorCandidate(String(condition.indicator_key || ""))}>
                              연결된 신규 지표 후보 있음 · {friendlyStatusLabel(linkedCandidate.validation_status)}
                            </button>
                          ) : null}
                        </td>
                        <td>{condition.apply_mode_label || (condition.apply_to_samples ? "포함 조건으로 사용" : "비교용으로만 사용")}</td>
                        <td>
                          <div className="pattern-llm-actions">
                            {condition.validation_status === "new_indicator_required" ? <button className="btn btn-secondary" type="button" onClick={() => scrollToIndicatorCandidate(String(condition.indicator_key || ""))}>신규 지표 후보 보기</button> : null}
                            <button className="btn btn-primary" type="button" disabled={cannotApplyToSamples} onClick={() => onApplyCandidate({ ...condition, category: "entry_filter" }, true)}>포함 조건으로 사용</button>
                            <button className="btn btn-secondary" type="button" disabled={cannotApplyToSamples} onClick={() => onApplyCandidate({ ...condition, category: "exclude_filter", exclude_when_true: true }, true)}>제외 조건으로 사용</button>
                            <button className="btn btn-secondary" type="button" disabled={cannotUseAsReference} onClick={() => onApplyCandidate(condition, false)}>비교용으로만 사용</button>
                            <button className="btn btn-secondary" type="button" onClick={() => onMarkDecision("exclude", condition.label || condition.source_text)}>사용안함</button>
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          ) : null}
          {candidates.length ? (
            <div className="table-shell">
              <table className="data-table compact-table pattern-gpt-candidate-table">
                <thead>
                  <tr><th>원문 표현</th><th>제안 지표키</th><th>제안 지표명</th><th>계산 유형</th><th>계산식 설명</th><th>필요 지표</th><th>검증 상태</th><th>처리</th></tr>
                </thead>
                <tbody>
                  {candidates.map((candidate, index) => (
                    <tr id={`gpt-candidate-${candidate.indicator_key || index}`} key={`gpt-new-indicator-${index}`} data-gpt-indicator-key={candidate.indicator_key || ""}>
                      <td>{candidate.source_text || "-"}</td>
                      <td>{candidate.indicator_key || "-"}</td>
                      <td>{candidate.indicator_name || "-"}</td>
                      <td>{candidate.calculation_type || "-"}</td>
                      <td>{candidate.formula_description || candidate.description || "-"}</td>
                      <td>{(candidate.required_indicators || []).join(", ") || "-"}</td>
                      <td>
                        <span className={`condition-status-badge is-${candidate.validation_status || "unknown"}`}>{friendlyStatusLabel(candidate.validation_status)}</span>
                        {candidate.validation_message ? <small className="disabled-action-help">{candidate.validation_message}</small> : null}
                        <span className={`condition-status-badge ${candidate.execution_supported || ["distance_pct", "rolling_high"].includes(String(candidate.calculation_type || "")) ? "is-calculatable" : "is-needs_engine"}`}>
                          샘플 실행: {candidate.execution_supported || ["distance_pct", "rolling_high"].includes(String(candidate.calculation_type || "")) ? "실행 가능" : "엔진 필요"}
                        </span>
                        {candidate.execution_message ? <small className="disabled-action-help">{candidate.execution_message}</small> : null}
                      </td>
                      <td>
                        <div className="pattern-llm-actions">
                          <button className="btn btn-secondary" type="button" disabled={candidate.execution_supported === false && !["distance_pct", "rolling_high"].includes(String(candidate.calculation_type || ""))} onClick={() => onMarkDecision("one_time", candidate)}>비교용으로만 사용</button>
                          <button className="btn btn-primary" type="button" onClick={() => void onSaveIndicatorCandidate(candidate)}>지표 기준정보 등록</button>
                          <button className="btn btn-secondary" type="button" onClick={() => onMarkDecision("reference", candidate.indicator_key)}>수식화 필요로 유지</button>
                          <button className="btn btn-secondary" type="button" onClick={() => onMarkDecision("exclude", candidate.indicator_key)}>사용안함</button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : null}
          {unsupported.length ? (
            <div className="pattern-gpt-message-list">
              <strong>미지원 항목</strong>
              {unsupported.map((item, index) => <span key={`gpt-unsupported-${index}`}>{itemText(item)}: {itemText(item, "reason", "validation_message")}</span>)}
            </div>
          ) : null}
          {warnings.length ? (
            <div className="pattern-gpt-message-list warning">
              <strong>경고</strong>
              {warnings.map((item, index) => <span key={`gpt-warning-${index}`}>{itemText(item)}: {itemText(item, "message", "warning")}</span>)}
            </div>
          ) : null}
          {conflicts.length ? (
            <div className="pattern-gpt-conflict-list">
              <strong>해석 충돌</strong>
              {conflicts.map((item, index) => (
                <div key={`gpt-conflict-${index}`} className="pattern-gpt-conflict-item">
                  <span>원문: {item.source_text || "-"}</span>
                  <span>DrCT 1차 해석: {item.drct_first_pass || "-"}</span>
                  <span>GPT 보정: {item.gpt_correction || "-"}</span>
                  <span>제안 지표: {item.suggested_indicator_key || "-"}</span>
                </div>
              ))}
            </div>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

function GptGoalResultPanel({
  loading,
  promptText,
  showPrompt,
  resultText,
  validation,
  onTogglePrompt,
  onCopyPrompt,
  onChangeResultText,
  onValidate,
  onApplyCandidate,
  onSaveIndicatorCandidate,
}: {
  loading: boolean;
  promptText: string;
  showPrompt: boolean;
  resultText: string;
  validation: Record<string, any> | null;
  onTogglePrompt: () => void;
  onCopyPrompt: () => Promise<void>;
  onChangeResultText: (value: string) => void;
  onValidate: () => Promise<void>;
  onApplyCandidate: (candidate: Record<string, any>, applyToSamples: boolean) => void;
  onSaveIndicatorCandidate: (candidate: Record<string, any>) => Promise<void>;
}) {
  const conditions = (validation?.validated_conditions || []) as Array<Record<string, any>>;
  const candidates = (validation?.new_indicator_candidates || []) as Array<Record<string, any>>;
  const unsupported = (validation?.unsupported_items || []) as Array<Record<string, any>>;
  return (
    <div className="pattern-gpt-goal-panel">
      <div className="pattern-llm-panel-head">
        <h4>GPT 목표 해석 결과 붙여넣기</h4>
        <span className={`pattern-llm-status pattern-llm-status-${validation?.status || "skipped"}`}>{validation?.status || "대기"}</span>
      </div>
      <div className="pattern-action-row">
        <button className="btn btn-secondary" type="button" disabled={loading} onClick={() => void onCopyPrompt()}>
          <Clipboard size={15} /> GPT 목표 해석 요청문 복사
        </button>
        {promptText ? <button className="btn btn-secondary" type="button" onClick={onTogglePrompt}>{showPrompt ? "요청문 접기" : "요청문 미리보기"}</button> : null}
      </div>
      {showPrompt && promptText ? <textarea className="pattern-gpt-prompt compact" readOnly value={promptText} /> : null}
      <textarea
        className="pattern-gpt-result-input"
        value={resultText}
        onChange={(event) => onChangeResultText(event.target.value)}
        placeholder="GPT가 반환한 JSON을 여기에 붙여넣고 검증하세요."
      />
      <div className="pattern-action-row">
        <button className="btn btn-primary" type="button" disabled={loading || !resultText.trim()} onClick={() => void onValidate()}>GPT 결과 검증</button>
      </div>
      {validation?.raw_error ? <div className="alert danger">{validation.raw_error}</div> : null}
      {conditions.length ? (
        <div className="table-shell pattern-llm-table-shell">
          <table className="data-table compact-table pattern-gpt-validation-table">
            <thead>
              <tr><th>원문</th><th>조건명</th><th>수식</th><th>지표</th><th>구분</th><th>검증 상태</th><th>적용</th></tr>
            </thead>
            <tbody>
              {conditions.map((condition, index) => {
                const rejected = condition.validation_status === "rejected" || condition.validation_status === "new_indicator_required";
                return (
                  <tr key={`gpt-condition-${index}`}>
                    <td>{condition.source_text || "-"}</td>
                    <td>{condition.label || "-"}</td>
                    <td>{condition.expression || expressionForCondition(condition)}</td>
                    <td>{condition.indicator_key || "-"}</td>
                    <td>{condition.category || "-"}</td>
                    <td>{condition.validation_status || "-"} {condition.validation_message ? `· ${condition.validation_message}` : ""}</td>
                    <td>
                      <div className="pattern-llm-actions">
                        <button className="btn btn-secondary" type="button" disabled={rejected} onClick={() => onApplyCandidate(condition, false)}>조건 후보</button>
                        <button className="btn btn-primary" type="button" disabled={rejected} onClick={() => onApplyCandidate(condition, true)}>포함 조건으로 사용</button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      ) : null}
      {candidates.length ? (
        <div className="table-shell">
          <table className="data-table compact-table pattern-gpt-candidate-table">
            <thead>
              <tr><th>원문</th><th>제안 지표</th><th>계산 유형</th><th>필요 지표</th><th>검증 상태</th><th>처리</th></tr>
            </thead>
            <tbody>
              {candidates.map((candidate, index) => (
                <tr key={`gpt-new-indicator-${index}`}>
                  <td>{candidate.source_text || "-"}</td>
                  <td>{candidate.indicator_key}<br /><small>{candidate.indicator_name}</small></td>
                  <td>{candidate.calculation_type || "-"}</td>
                  <td>{(candidate.required_indicators || []).join(", ") || "-"}</td>
                  <td>{candidate.validation_status || "-"} {candidate.validation_message ? `· ${candidate.validation_message}` : ""}</td>
                  <td>
                    <div className="pattern-llm-actions">
                      <button className="btn btn-secondary" type="button" onClick={() => void onSaveIndicatorCandidate(candidate)}>지표 후보 저장</button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
      {unsupported.length ? (
        <div className="pattern-llm-unsupported">
          <strong>미지원/주의 항목</strong>
          {unsupported.map((item, index) => <span key={`gpt-unsupported-${index}`}>{item.source_text || "-"}: {item.reason || "-"}</span>)}
        </div>
      ) : null}
    </div>
  );
}

function LlmAssistPanel({
  parsed,
  onApplyCandidate,
}: {
  parsed: PatternGoalParseResponse | null;
  onApplyCandidate: (candidate: Record<string, any>, applyToSamples: boolean) => void;
}) {
  const assist = parsed?.llm_assist || parsed?.parsed_goal?.llm_assist_result || null;
  if (!assist || assist.status === "skipped") return null;
  const candidates = [
    ...((assist.candidate_conditions || []) as Array<Record<string, any>>),
    ...((assist.suggested_additional_conditions || []) as Array<Record<string, any>>),
  ];
  const diagnostics = assist.diagnostics || assist.debug || {};
  const catalogSize = diagnostics.catalog_size || {};
  const missingCatalogRequests = (assist.missing_catalog_requests || []) as Array<Record<string, any>>;
  const sentenceResults = (assist.sentence_results || []) as Array<Record<string, any>>;
  const failedSentences = sentenceResults.filter((item) => item.llm_required && item.status !== "success");

  return (
    <div className="pattern-llm-panel">
      <div className="pattern-llm-panel-head">
        <h4>LLM 보조 해석 후보</h4>
        <span className={`pattern-llm-status pattern-llm-status-${assist.status}`}>{assist.status}</span>
      </div>
      <div className="pattern-llm-diagnostics">
        <span>상태: {assist.status}</span>
        <span>재시도: {diagnostics.retry_count ?? 0}</span>
        <span>mode: {diagnostics.used_mode || diagnostics.used_catalog_mode || "-"}</span>
        <span>문장: {fmtNumber(diagnostics.sentence_count, 0)}</span>
        <span>LLM 대상: {fmtNumber(diagnostics.llm_target_sentence_count, 0)}</span>
        <span>성공: {fmtNumber(diagnostics.llm_success_sentence_count, 0)}</span>
        <span>실패: {fmtNumber(diagnostics.llm_failed_sentence_count, 0)}</span>
        <span>prompt: {fmtNumber(diagnostics.prompt_char_length, 0)} chars</span>
        <span>indicators: {fmtNumber(catalogSize.sent_detailed_indicators, 0)} detail / {fmtNumber(catalogSize.sent_summary_indicators, 0)} summary / {fmtNumber(catalogSize.full_indicators, 0)} full</span>
        <span>aliases: {fmtNumber(catalogSize.sent_aliases, 0)} / {fmtNumber(catalogSize.full_aliases, 0)}</span>
        <span>templates: {fmtNumber(catalogSize.sent_templates, 0)} / {fmtNumber(catalogSize.full_templates, 0)}</span>
      </div>
      {sentenceResults.length ? (
        <div className="pattern-llm-sentence-grid">
          {sentenceResults.map((item, index) => (
            <span key={`llm-sentence-${index}`} className={`pattern-llm-sentence-chip is-${item.status || "skipped"}`}>
              {item.llm_required ? "LLM" : "Rule"} · {item.status || "-"} · {item.sentence}
            </span>
          ))}
        </div>
      ) : null}
      {assist.status === "failed" ? (
        <div className="alert warning">{assist.warnings?.[0] || "LLM 보조 해석에 실패했습니다. Rule base 1차 해석 결과만 표시합니다."}</div>
      ) : null}
      {assist.error_message ? <p className="pattern-llm-error">{assist.error_message}</p> : null}
      {assist.status === "success" && candidates.length === 0 ? <EmptyState message="LLM이 추가 후보를 제안하지 않았습니다." /> : null}
      {candidates.length > 0 ? (
        <div className="table-shell pattern-llm-table-shell">
          <table className="data-table compact-table pattern-llm-table">
            <thead>
              <tr>
                <th>원문 표현</th>
                <th>제안 조건</th>
                <th>해석 수식</th>
                <th>사용 지표</th>
                <th>적용 구분</th>
                <th>해석 상태</th>
                <th>검증 상태</th>
                <th>신뢰도</th>
                <th>사유</th>
                <th>적용 방식</th>
              </tr>
            </thead>
            <tbody>
              {candidates.map((candidate, index) => (
                <LlmCandidateRow key={`llm-${index}`} candidate={candidate} onApplyCandidate={onApplyCandidate} />
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
      {assist.unsupported_items?.length ? (
        <div className="pattern-llm-unsupported">
          <strong>LLM 미지원/거절 항목</strong>
          {assist.unsupported_items.map((item: Record<string, any>, index: number) => (
            <span key={`llm-unsupported-${index}`}>{item.source_text || "-"}: {item.reason || item.validation_message || "-"}</span>
          ))}
        </div>
      ) : null}
      {failedSentences.length ? (
        <div className="pattern-llm-unsupported">
          <strong>실패 sentence</strong>
          {failedSentences.map((item, index) => (
            <span key={`llm-failed-sentence-${index}`}>
              {item.sentence || "-"}: {item.error_message || item.reason || "-"} / retry {item.retry_count ?? 0}
            </span>
          ))}
        </div>
      ) : null}
      {missingCatalogRequests.length ? (
        <div className="pattern-llm-missing">
          <strong>추가 지표 필요 후보</strong>
          <div className="table-shell">
            <table className="data-table compact-table pattern-llm-missing-table">
              <thead>
                <tr>
                  <th>source_text</th>
                  <th>needed_concept</th>
                  <th>reason</th>
                  <th>처리 상태</th>
                </tr>
              </thead>
              <tbody>
                {missingCatalogRequests.map((item, index) => (
                  <tr key={`llm-missing-${index}`}>
                    <td>{item.source_text || item.text || "-"}</td>
                    <td>{item.needed_concept || item.concept || item.indicator_key || "-"}</td>
                    <td>{item.reason || item.validation_message || "-"}</td>
                    <td>{item.validation_status || item.status || "catalog_missing"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : null}
    </div>
  );
}

function LlmCandidateRow({
  candidate,
  onApplyCandidate,
}: {
  candidate: Record<string, any>;
  onApplyCandidate: (candidate: Record<string, any>, applyToSamples: boolean) => void;
}) {
  const options = Array.isArray(candidate.candidate_options) ? candidate.candidate_options : [];
  const directCandidate = candidate.indicator_key ? [candidate] : [];
  const rows = [...directCandidate, ...options];
  return (
    <>
      {(rows.length ? rows : [candidate]).map((option, optionIndex) => {
        const merged = { ...candidate, ...option, label: option.label || candidate.label, source_text: candidate.source_text };
        const rejected = merged.validation_status === "rejected" || merged.validation_status === "catalog_missing";
        return (
          <tr key={`${candidate.source_text || candidate.label}-${optionIndex}`}>
            <td>{candidate.source_text || "-"}</td>
            <td>{merged.label || "-"}</td>
            <td>{merged.expression || expressionForCondition(merged)}</td>
            <td>{merged.indicator_key || "-"}</td>
            <td>{merged.category || candidate.category || "entry_filter"}</td>
            <td>{candidate.interpretation_status_label || statusLabel(candidate.status || "needs_review")}</td>
            <td>{merged.validation_status || candidate.validation_status || "-"}</td>
            <td>{fmtNumber(candidate.confidence, 2)}</td>
            <td>{candidate.reason || merged.validation_message || "-"}</td>
            <td>
              <div className="pattern-llm-actions">
                <button className="btn btn-secondary" type="button" disabled={rejected} onClick={() => onApplyCandidate(merged, false)}>조건 후보</button>
                <button className="btn btn-primary" type="button" disabled={rejected} onClick={() => onApplyCandidate(merged, true)}>포함 조건으로 사용</button>
              </div>
            </td>
          </tr>
        );
      })}
    </>
  );
}

function conditionSummaryLabel(item: Record<string, any>): string {
  const label = item.label || item.natural_text || item.source_text || item.indicator_key || item.indicator || "조건";
  return `${label}: ${formatConditionExpression(item, item.exclude_when_true ? "exclude" : item.apply_to_samples ? "include" : "reference")}`;
}

function sampleQuality(summary: Record<string, any>) {
  const total = Number(summary.total_samples || 0);
  const success = Number(summary.success_count || 0);
  const failure = Number(summary.failure_count || 0);
  const neutral = Number(summary.neutral_count || 0);
  const successRate = Number(summary.success_rate || 0);
  const sampleStatus = total >= 100 ? "충분" : total >= 30 ? "검토 가능" : "부족";
  const rateStatus = successRate >= 60 ? "양호" : successRate >= 45 ? "검토 가능" : "개선 필요";
  const researchReady = total >= 30 && success >= 10 && failure >= 10 ? "가능" : "보류 권장";
  const balance = success < 10 ? "성공 샘플 부족" : failure < 10 ? "실패 샘플 부족" : success > failure ? "성공 샘플이 더 많음" : failure > success ? "실패 샘플이 더 많음" : "균형";
  const neutralStatus = neutral > total * 0.5 ? "중립 과다" : neutral > 0 ? "일부 존재" : "없음";
  const restriction = total < 30 ? "높음" : total < 100 ? "검토 필요" : "낮음";
  const message = successRate < 45
    ? "성공률은 아직 낮은 편입니다. 다음 단계에서 성공/실패 차이를 분석해 조건을 보완하는 것이 좋습니다."
    : successRate < 60
      ? "성공률은 검토 가능한 구간입니다. 성공/실패 차이를 확인해 조건값을 조정해 보세요."
      : "성공률은 양호한 편입니다. 과최적화 가능성도 함께 점검하세요.";
  return { sampleStatus, rateStatus, researchReady, balance, neutralStatus, restriction, message };
}

function SampleStepReview({ summary, onNext }: { summary: Record<string, any>; onNext: () => void }) {
  const quality = sampleQuality(summary);
  const success = summary.applied_success_criteria || {};
  const failure = summary.applied_failure_criteria || {};
  const include = (summary.applied_entry_filters || []) as Array<Record<string, any>>;
  const exclude = (summary.applied_exclude_filters || []) as Array<Record<string, any>>;
  const reference = (summary.reference_entry_filters || []) as Array<Record<string, any>>;
  const avgSuccess = summary.avg_success || {};
  const avgFailure = summary.avg_failure || {};
  const differences = summary.differences || {};
  const observationIndicators = (summary.observation_indicators || []) as string[];
  const comparisonRows = observationIndicators
    .filter((key) => avgSuccess[key] !== null && avgSuccess[key] !== undefined && avgFailure[key] !== null && avgFailure[key] !== undefined)
    .slice(0, 8)
    .map((key) => ({
      key,
      success: avgSuccess[key],
      failure: avgFailure[key],
      diff: differences[key],
    }));

  const conditionGroups = [
    { label: "성공 기준", rows: success.expression ? [success] : [] },
    { label: "실패 기준", rows: failure.expression ? [failure] : [] },
    { label: "포함 조건", rows: include },
    { label: "제외 조건", rows: exclude },
    { label: "비교용 지표", rows: reference },
  ];

  return (
    <div className="sample-step-summary">
      <div className="sample-condition-summary">
        <div className="sample-step-head">
          <strong>이번 샘플 생성에 적용된 조건</strong>
          <span>2단계에서 확정한 조건이 실제 샘플 생성에 반영된 결과입니다.</span>
        </div>
        <div className="sample-condition-grid">
          {conditionGroups.map((group) => (
            <div key={group.label} className="sample-condition-card">
              <strong>{group.label}</strong>
              {group.rows.length ? group.rows.slice(0, 6).map((item, index) => <span key={`${group.label}-${index}`}>{conditionSummaryLabel(item)}</span>) : <em>없음</em>}
            </div>
          ))}
        </div>
      </div>

      <div className="sample-kpi-grid">
        <Kpi label="전체 후보" value={fmtNumber(summary.total_samples, 0)} />
        <Kpi label="성공 샘플" value={fmtNumber(summary.success_count, 0)} />
        <Kpi label="실패 샘플" value={fmtNumber(summary.failure_count, 0)} />
        <Kpi label="중립 샘플" value={fmtNumber(summary.neutral_count, 0)} />
        <Kpi label="성공률" value={fmtPercent(summary.success_rate)} />
      </div>
      <div className="sample-quality-card">
        <span>성공률 상태: <strong>{quality.rateStatus}</strong></span>
        <span>샘플 수: <strong>{quality.sampleStatus}</strong></span>
        <span>GPT 연구 가능: <strong>{quality.researchReady}</strong></span>
        <em>{quality.message}</em>
      </div>

      <div className="sample-quality-diagnostics">
        <strong>샘플 품질 진단</strong>
        <span>샘플 수: {quality.sampleStatus}</span>
        <span>성공/실패 균형: {quality.balance}</span>
        <span>중립 샘플: {quality.neutralStatus}</span>
        <span>조건 과도 제한: {quality.restriction}</span>
        <span>GPT 연구 가능 여부: {quality.researchReady}</span>
      </div>

      <div className="sample-compare-block">
        <div className="sample-step-head">
          <strong>성공/실패 주요 지표 평균 비교</strong>
          <span>연구용 관찰 결과입니다. 투자 판단이 아니라 다음 조건 보완을 위한 참고값입니다.</span>
        </div>
        {comparisonRows.length ? (
          <div className="table-shell">
            <table className="data-table compact-table sample-compare-table">
              <thead>
                <tr><th>지표</th><th>성공 평균</th><th>실패 평균</th><th>차이 해석</th></tr>
              </thead>
              <tbody>
                {comparisonRows.map((row) => {
                  const diff = Number(row.diff || 0);
                  const interpretation = Math.abs(diff) < 0.1 ? "차이 작음" : diff > 0 ? "성공 높음" : "실패 높음";
                  return (
                    <tr key={row.key}>
                      <td>{row.key}</td>
                      <td className="numeric-cell">{fmtNumber(row.success)}</td>
                      <td className="numeric-cell">{fmtNumber(row.failure)}</td>
                      <td>{interpretation}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        ) : <div className="pattern-empty-note">샘플 feature 데이터가 충분하지 않아 평균 비교를 표시할 수 없습니다.</div>}
      </div>

      <div className="sample-next-guide">
        <strong>다음 단계에서 GPT가 성공/실패 샘플의 차이를 분석합니다.</strong>
        <span>적용 조건, 샘플 요약, 주요 지표 평균 비교, 조건 후보별 성과, 성공/실패 예시 샘플이 연구 패키지에 포함됩니다.</span>
        {quality.researchReady !== "가능" ? <em>성공 또는 실패 샘플이 너무 적습니다. 조건을 완화한 뒤 다시 생성하는 것을 권장합니다.</em> : null}
        <button className="btn btn-primary" type="button" onClick={onNext}>다음: GPT 연구 패키지 생성</button>
      </div>
    </div>
  );
}

function AutoParamTestPanel({
  baselineSummary,
  results,
  totalCandidates,
  cursor,
  running,
  progress,
  selectedId,
  onRunNext,
  onClear,
  onSelect,
  onApplyToConditions,
  onShowBaseline,
}: {
  baselineSummary: Record<string, any> | null | undefined;
  results: AutoParamResult[];
  totalCandidates: number;
  cursor: number;
  running: boolean;
  progress: string;
  selectedId: string | null;
  onRunNext: () => void;
  onClear: () => void;
  onSelect: (result: AutoParamResult) => void;
  onApplyToConditions: (result: AutoParamResult) => void;
  onShowBaseline: () => void;
}) {
  const baselineRate = Number(baselineSummary?.success_rate || 0);
  const baselineTotal = Number(baselineSummary?.total_samples || 0);
  const hasMore = !totalCandidates || cursor < totalCandidates;
  return (
    <div className="auto-param-panel">
      <div className="auto-param-head">
        <div>
          <strong>자동 수치변경 테스트</strong>
          <span>확정 조건의 숫자만 바꿔 5개씩 비교합니다. 결과는 저장하지 않고 현재 화면에서만 사용합니다.</span>
        </div>
        <div className="auto-param-actions">
          <button className="btn btn-primary" type="button" disabled={running || !hasMore} onClick={onRunNext}>
            {results.length ? "다음 5개 테스트" : "첫 5개 테스트"}
          </button>
          <button className="btn btn-secondary" type="button" disabled={running || !results.length} onClick={onClear}>결과 초기화</button>
          <button className="btn btn-secondary" type="button" disabled={running || !selectedId} onClick={onShowBaseline}>기준 결과 보기</button>
        </div>
      </div>
      <div className="auto-param-baseline">
        <span>기준 성공률 <strong>{fmtPercent(baselineRate)}</strong></span>
        <span>기준 샘플 <strong>{fmtNumber(baselineTotal, 0)}</strong></span>
        <span>{running ? `진행 ${progress}` : totalCandidates ? `${Math.min(cursor, totalCandidates)}/${totalCandidates} 실행` : "후보 미생성"}</span>
      </div>
      {!results.length ? <div className="pattern-empty-note">아직 자동 수치변경 테스트 결과가 없습니다.</div> : (
        <div className="table-shell auto-param-table-shell">
          <table className="data-table compact-table auto-param-table">
            <thead>
              <tr>
                <th>#</th>
                <th>변경 조건</th>
                <th className="numeric-cell">성공</th>
                <th className="numeric-cell">실패</th>
                <th className="numeric-cell">중립</th>
                <th className="numeric-cell">성공률</th>
                <th className="numeric-cell">차이</th>
                <th>판정</th>
                <th>사용</th>
              </tr>
            </thead>
            <tbody>
              {results.map((result) => {
                const resultSummary = result.summary || {};
                const delta = Number(resultSummary.success_rate || 0) - baselineRate;
                const verdict = autoResultVerdict(result, baselineSummary);
                return (
                  <tr key={result.id} className={selectedId === result.id ? "selected-auto-result" : ""}>
                    <td>{result.seq}</td>
                    <td>
                      <strong>{result.label}</strong>
                      <span>{result.status === "error" ? result.error : result.description}</span>
                    </td>
                    <td className="numeric-cell">{result.status === "error" ? "-" : fmtNumber(resultSummary.success_count, 0)}</td>
                    <td className="numeric-cell">{result.status === "error" ? "-" : fmtNumber(resultSummary.failure_count, 0)}</td>
                    <td className="numeric-cell">{result.status === "error" ? "-" : fmtNumber(resultSummary.neutral_count, 0)}</td>
                    <td className="numeric-cell">{result.status === "error" ? "-" : fmtPercent(resultSummary.success_rate)}</td>
                    <td className={`numeric-cell ${delta >= 0 ? "positive" : "negative"}`}>{result.status === "error" ? "-" : `${delta >= 0 ? "+" : ""}${fmtPercent(delta)}`}</td>
                    <td><span className={`auto-param-verdict verdict-${verdict.replace(/\s/g, "-")}`}>{verdict}</span></td>
                    <td>
                      <button className="btn btn-secondary btn-xs" type="button" disabled={result.status === "error"} onClick={() => onSelect(result)}>
                        이 결과로 보기
                      </button>
                      <button className="btn btn-secondary btn-xs auto-param-apply-button" type="button" disabled={result.status === "error"} title="이 자동 테스트 조건을 2단계 조건 확정 목록에 추가하거나 기존 조건값으로 반영합니다." onClick={() => onApplyToConditions(result)}>
                        2단계 조건에 반영
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function AutoParamTestPanelV2({
  baselineSummary,
  results,
  totalCandidates,
  cursor,
  running,
  progress,
  selectedId,
  onRunNext,
  onClear,
  onSelect,
  onApplyToConditions,
  onShowBaseline,
}: {
  baselineSummary: Record<string, any> | null | undefined;
  results: AutoParamResult[];
  totalCandidates: number;
  cursor: number;
  running: boolean;
  progress: string;
  selectedId: string | null;
  onRunNext: () => void;
  onClear: () => void;
  onSelect: (result: AutoParamResult) => void;
  onApplyToConditions: (result: AutoParamResult) => void;
  onShowBaseline: () => void;
}) {
  const baselineRate = Number(baselineSummary?.success_rate || 0);
  const baselineTotal = Number(baselineSummary?.total_samples || 0);
  const hasMore = !totalCandidates || cursor < totalCandidates;
  const selectedResult = results.find((result) => result.id === selectedId && result.status === "success") || null;
  const promisingCount = results.filter((result) => autoResultVerdictV2(result, baselineSummary) === "유망").length;
  const reviewCount = results.filter((result) => autoResultVerdictV2(result, baselineSummary) === "검토").length;
  const lowSampleCount = results.filter((result) => ["샘플 부족", "과최적화 주의"].includes(autoResultVerdictV2(result, baselineSummary))).length;
  const worseCount = results.filter((result) => autoResultVerdictV2(result, baselineSummary) === "악화").length;
  const topResults = sortAutoResultsByPromise(results, baselineSummary).slice(0, 3);
  const bestSuccessRate = Math.max(0, ...results.filter((result) => result.status === "success").map((result) => Number(result.summary?.success_rate || 0)));
  const bestRateDelta = Math.max(0, ...results.filter((result) => result.status === "success").map((result) => autoResultMetrics(result, baselineSummary).rateDelta));
  const bestFailureReduction = Math.max(0, ...results.filter((result) => result.status === "success").map((result) => -autoResultMetrics(result, baselineSummary).failureDelta));

  return (
    <div className="auto-param-panel">
      <div className="auto-param-head">
        <div>
          <strong>자동 수치변경 테스트</strong>
          <span>성공률만 보지 않고 샘플 수, 실패 샘플 변화, 과최적화 위험까지 함께 비교합니다. 결과는 저장하지 않습니다.</span>
        </div>
        <div className="auto-param-actions">
          <button className="btn btn-primary" type="button" disabled={running || !hasMore} onClick={onRunNext}>
            {results.length ? "다음 5개 테스트" : "자동 수치변경 테스트 5개 실행"}
          </button>
          <button className="btn btn-secondary auto-param-test-reset" type="button" disabled={running || !results.length} onClick={onClear}>결과 초기화</button>
          <button className="btn btn-secondary" type="button" disabled={running || !selectedId} onClick={onShowBaseline}>기준 결과 보기</button>
        </div>
      </div>

      <div className="auto-param-test-explain">
        <strong>후보 생성 규칙</strong>
        <span>실패 샘플의 과열 가능성을 줄이는 제외 조건을 먼저 테스트한 뒤, 눌림 범위, 거래대금, 추세 강도, 급등 이력 포함 조건 순서로 후보를 만듭니다. 한 번에 5개만 실행해 계산 부담을 줄입니다.</span>
      </div>

      <div className="auto-param-baseline">
        <span>기준 후보 <strong>{fmtNumber(baselineTotal, 0)}</strong></span>
        <span>기준 성공 <strong>{fmtNumber(baselineSummary?.success_count, 0)}</strong></span>
        <span>기준 실패 <strong>{fmtNumber(baselineSummary?.failure_count, 0)}</strong></span>
        <span>기준 중립 <strong>{fmtNumber(baselineSummary?.neutral_count, 0)}</strong></span>
        <span>기준 성공률 <strong>{fmtPercent(baselineRate)}</strong></span>
        <span>{running ? `진행 ${progress}` : totalCandidates ? `${Math.min(cursor, totalCandidates)}/${totalCandidates} 실행` : "후보 미생성"}</span>
      </div>

      {selectedResult ? (
        <div className="auto-param-test-selected-banner">
          <strong>선택한 결과 적용 중: #{selectedResult.seq} {selectedResult.label}</strong>
          <span>현재 3단계 KPI/샘플과 4단계 GPT 패키지는 이 자동 테스트 결과를 기준으로 표시됩니다.</span>
        </div>
      ) : (
        <div className="auto-param-test-selected-banner is-baseline">
          <strong>현재 화면은 기준 샘플 결과를 기준으로 표시 중입니다.</strong>
          <span>자동 테스트 결과를 선택하면 선택 결과와 기준 결과 비교 카드가 표시됩니다.</span>
        </div>
      )}

      <div className="auto-param-test-summary">
        <span>실행 {fmtNumber(results.length, 0)}</span>
        <span className="auto-param-test-promising-badge">유망 {fmtNumber(promisingCount, 0)}</span>
        <span>검토 {fmtNumber(reviewCount, 0)}</span>
        <span className="auto-param-test-warning-badge">샘플/과최적화 주의 {fmtNumber(lowSampleCount, 0)}</span>
        <span>악화 {fmtNumber(worseCount, 0)}</span>
        <span>최고 성공률 {bestSuccessRate ? fmtPercent(bestSuccessRate) : "-"}</span>
        <span>최대 개선 {bestRateDelta ? `+${fmtPercent(bestRateDelta)}` : "-"}</span>
        <span>실패 최대 감소 {bestFailureReduction ? `${fmtNumber(bestFailureReduction, 0)}개` : "-"}</span>
        <span>선택 {selectedResult ? `#${selectedResult.seq}` : "없음"}</span>
      </div>

      <AutoParamPromisingCard results={topResults} baselineSummary={baselineSummary} onApplyToConditions={onApplyToConditions} />

      {selectedResult ? <AutoParamSelectedCompareCard baselineSummary={baselineSummary} result={selectedResult} onShowBaseline={onShowBaseline} onApplyToConditions={onApplyToConditions} /> : null}

      {!results.length ? <div className="pattern-empty-note">아직 자동 수치변경 테스트 결과가 없습니다.</div> : (
        <div className="table-shell auto-param-table-shell">
          <table className="data-table compact-table auto-param-table">
            <thead>
              <tr>
                <th>#</th>
                <th>변경 내용</th>
                <th className="numeric-cell">후보</th>
                <th className="numeric-cell">성공</th>
                <th className="numeric-cell">실패</th>
                <th className="numeric-cell">중립</th>
                <th className="numeric-cell">성공률</th>
                <th className="numeric-cell">기준 대비</th>
                <th className="numeric-cell">샘플 변화</th>
                <th>판정</th>
                <th>해석</th>
                <th>액션</th>
              </tr>
            </thead>
            <tbody>
              {results.map((result) => {
                const resultSummary = result.summary || {};
                const metrics = autoResultMetrics(result, baselineSummary);
                const verdict = autoResultVerdictV2(result, baselineSummary);
                const rowClassName = [
                  selectedId === result.id ? "selected-auto-result" : "",
                  verdict === "유망" ? "auto-param-test-highlight-row" : "",
                ].filter(Boolean).join(" ");
                return (
                  <tr key={result.id} className={rowClassName}>
                    <td>{result.seq}</td>
                    <td>
                      <strong>{result.label}</strong>
                      <span>{result.status === "error" ? result.error : result.description}</span>
                    </td>
                    <td className="numeric-cell">{result.status === "error" ? "-" : fmtNumber(resultSummary.total_samples, 0)}</td>
                    <td className="numeric-cell">{result.status === "error" ? "-" : fmtNumber(resultSummary.success_count, 0)}</td>
                    <td className="numeric-cell">{result.status === "error" ? "-" : fmtNumber(resultSummary.failure_count, 0)}</td>
                    <td className="numeric-cell">{result.status === "error" ? "-" : fmtNumber(resultSummary.neutral_count, 0)}</td>
                    <td className="numeric-cell">{result.status === "error" ? "-" : fmtPercent(resultSummary.success_rate)}</td>
                    <td className={`numeric-cell ${metrics.rateDelta >= 0 ? "positive" : "negative"}`}>{result.status === "error" ? "-" : `${metrics.rateDelta >= 0 ? "+" : ""}${fmtPercent(metrics.rateDelta)}`}</td>
                    <td className={`numeric-cell ${metrics.sampleDelta >= 0 ? "positive" : "negative"}`}>{result.status === "error" ? "-" : `${metrics.sampleDelta >= 0 ? "+" : ""}${fmtNumber(metrics.sampleDelta, 0)}`}</td>
                    <td><span className={`auto-param-verdict verdict-${verdict.replace(/\s/g, "-")}`}>{verdict}</span></td>
                    <td className="auto-param-test-interpretation">
                      <strong>{autoResultShortInterpretation(result, baselineSummary)}</strong>
                      <span>{autoResultInterpretation(result, baselineSummary)}</span>
                    </td>
                    <td>
                      <button className="btn btn-secondary btn-xs" type="button" disabled={result.status === "error"} onClick={() => onSelect(result)}>
                        이 결과로 보기
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function AutoParamSelectedCompareCard({
  baselineSummary,
  result,
  onShowBaseline,
  onApplyToConditions,
}: {
  baselineSummary: Record<string, any> | null | undefined;
  result: AutoParamResult;
  onShowBaseline: () => void;
  onApplyToConditions: (result: AutoParamResult) => void;
}) {
  const metrics = autoResultMetrics(result, baselineSummary);
  const verdict = autoResultVerdictV2(result, baselineSummary);
  return (
    <div className="auto-param-test-compare-card">
      <div>
        <strong>선택한 자동 테스트 결과 비교</strong>
        <span>기준 결과와 선택 결과를 나란히 비교합니다.</span>
      </div>
      <div className="auto-param-compare-grid">
        <Kpi label="기준 후보" value={fmtNumber(metrics.baselineTotal, 0)} />
        <Kpi label="선택 후보" value={fmtNumber(metrics.total, 0)} />
        <Kpi label="성공률 변화" value={`${metrics.rateDelta >= 0 ? "+" : ""}${fmtPercent(metrics.rateDelta)}`} />
        <Kpi label="후보 변화" value={`${metrics.sampleDelta >= 0 ? "+" : ""}${fmtNumber(metrics.sampleDelta, 0)}`} />
        <Kpi label="실패 변화" value={`${metrics.failureDelta >= 0 ? "+" : ""}${fmtNumber(metrics.failureDelta, 0)}`} />
        <Kpi label="판정" value={verdict} />
      </div>
      <div className="auto-param-test-interpretation">
        <strong>{result.label}</strong>
        <span>{autoResultInterpretation(result, baselineSummary)}</span>
        <em>2단계 조건 반영은 다음 단계에서 자동화할 예정입니다. 현재는 위 변경 조건을 참고해 2단계에서 직접 조정할 수 있습니다.</em>
      </div>
      <div className="auto-param-actions">
        <button className="btn btn-secondary" type="button" onClick={onShowBaseline}>기준 결과 보기</button>
        <button className="btn btn-primary auto-param-apply-button" type="button" onClick={() => onApplyToConditions(result)}>2단계 조건에 반영</button>
      </div>
    </div>
  );
}

function AutoParamPromisingCard({
  results,
  baselineSummary,
  onApplyToConditions,
}: {
  results: AutoParamResult[];
  baselineSummary: Record<string, any> | null | undefined;
  onApplyToConditions: (result: AutoParamResult) => void;
}) {
  const promisingOrReview = results.filter((result) => ["유망", "검토"].includes(autoResultVerdictV2(result, baselineSummary)));
  const displayResults = promisingOrReview.length ? promisingOrReview : results;
  const hasResults = displayResults.length > 0;
  const overheatedCount = displayResults.filter((result) => {
    const key = String(result.changedCondition?.indicator_key || "");
    return result.changedCondition?.exclude_when_true && (key.includes("return") || key.includes("ma20") || key.includes("max_return"));
  }).length;
  return (
    <div className="auto-param-promising-card">
      <div>
        <strong>이번 자동 테스트의 유망 후보</strong>
        <span>
          {hasResults
            ? overheatedCount
              ? "이번 테스트에서는 과열 제외 조건이 상대적으로 좋은 결과를 보였습니다. 성공률 개선과 실패 샘플 감소를 함께 확인하세요."
              : "이번 테스트에서 기준 결과를 개선할 가능성이 있는 조건을 우선 정렬했습니다."
            : "아직 표시할 자동 테스트 결과가 없습니다. 첫 5개 테스트를 실행하면 유망 후보가 여기에 정리됩니다."}
        </span>
      </div>
      {hasResults ? (
        <div className="auto-param-promising-list">
          {displayResults.map((result, index) => {
            const metrics = autoResultMetrics(result, baselineSummary);
            const verdict = autoResultVerdictV2(result, baselineSummary);
            return (
              <div className="auto-param-promising-item" key={`promising-${result.id}`}>
                <em>{index + 1}</em>
                <div>
                  <strong>{result.label}</strong>
                  <code>{result.description}</code>
                  <span>성공률 {fmtPercent(metrics.successRate)} · 기준 대비 {metrics.rateDelta >= 0 ? "+" : ""}{fmtPercent(metrics.rateDelta)} · 후보 {fmtNumber(metrics.total, 0)}개 · 실패 {metrics.failureDelta <= 0 ? fmtNumber(Math.abs(metrics.failureDelta), 0) : `+${fmtNumber(metrics.failureDelta, 0)}`}개 변화</span>
                </div>
                <span className={`auto-param-verdict verdict-${verdict.replace(/\s/g, "-")}`}>{verdict}</span>
                <button className="btn btn-secondary btn-xs auto-param-apply-button" type="button" onClick={() => onApplyToConditions(result)}>
                  2단계 조건에 반영
                </button>
              </div>
            );
          })}
        </div>
      ) : (
        <div className="pattern-empty-note">기준 결과를 뚜렷하게 개선한 후보가 아직 없습니다.</div>
      )}
      <small>이 카드는 매수 추천이 아니라 다음 조건 연구 후보를 정리한 것입니다.</small>
    </div>
  );
}

function SampleTable({
  samples,
  sampleTab,
  onChangeTab,
  summary,
}: {
  samples: PatternResearchSample[];
  sampleTab: SampleTab;
  onChangeTab: (tab: SampleTab) => Promise<void>;
  summary?: Record<string, any> | null;
}) {
  const tabCounts: Record<SampleTab, number> = {
    SUCCESS: Number(summary?.success_count || 0),
    FAILURE: Number(summary?.failure_count || 0),
    NEUTRAL: Number(summary?.neutral_count || 0),
  };
  const tabHelp: Record<SampleTab, string> = {
    SUCCESS: `성공 기준을 충족한 샘플입니다. 예: ${summary?.applied_success_criteria?.expression || "목표 수익률 조건 충족"}`,
    FAILURE: `실패 기준을 충족한 샘플입니다. 예: ${summary?.applied_failure_criteria?.expression || "손절 기준 조건 충족"}`,
    NEUTRAL: "성공/실패 기준 어느 쪽에도 해당하지 않는 샘플입니다.",
  };
  return (
    <div className="pattern-samples-block">
      <div className="pattern-sample-tabs">
        {(["SUCCESS", "FAILURE", "NEUTRAL"] as SampleTab[]).map((tab) => (
          <button key={tab} type="button" className={sampleTab === tab ? "active" : ""} onClick={() => void onChangeTab(tab)}>{tab} {fmtNumber(tabCounts[tab], 0)}</button>
        ))}
      </div>
      <div className="sample-tab-help">{tabHelp[sampleTab]}</div>
      <div className="table-shell sample-table-compact-shell">
        <table className="data-table compact-table sample-table-compact">
          <thead>
            <tr>
              <th>날짜</th>
              <th className="numeric-cell">종가</th>
              <th>라벨</th>
              <th className="numeric-cell">최대상승률</th>
              <th className="numeric-cell">최대하락률</th>
              <th>target</th>
              <th>stop</th>
              <th>포함 조건</th>
              <th>제외사유</th>
              <th className="numeric-cell">거래대금 20일배수</th>
              <th className="numeric-cell">20일선 이격률</th>
              <th className="numeric-cell">최근 5일</th>
              <th>60일선 상승</th>
              <th>태그</th>
            </tr>
          </thead>
          <tbody>
            {samples.map((sample) => (
              <tr key={sample.id}>
                <td>{sample.trade_date}</td>
                <td className="numeric-cell">{fmtWon(sample.features?.close_price)}</td>
                <td>{sample.result_label}</td>
                <td className="numeric-cell">{fmtPercent(sample.max_future_return_pct)}</td>
                <td className="numeric-cell">{fmtPercent(sample.min_future_return_pct)}</td>
                <td>{sample.target_hit ? "Y" : "N"}</td>
                <td>{sample.stop_hit ? "Y" : "N"}</td>
                <td>{sample.features?.is_entry_candidate ? "Y" : "N"}</td>
                <td>{sample.features?.exclude_reason || "-"}</td>
                <td className="numeric-cell">{fmtNumber(sample.features?.trading_value_ratio_20)}</td>
                <td className="numeric-cell">{fmtPercent(sample.features?.close_vs_ma20_pct)}</td>
                <td className="numeric-cell">{fmtPercent(sample.features?.recent_5d_return)}</td>
                <td>{sample.features?.is_ma60_rising_5d ? "Y" : "N"}</td>
                <td>{(sample.pattern_tags || []).join(", ") || "-"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export default PatternResearchPage;
