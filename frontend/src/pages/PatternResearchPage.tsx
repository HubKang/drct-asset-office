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
} from "@/types/patternResearch";

type TabKey = "setup" | "gptValidation" | "confirm" | "samples" | "package" | "settings" | "analysis" | "gpt";
type SampleTab = "SUCCESS" | "FAILURE" | "NEUTRAL";
type GptValidationStatus = "idle" | "validating" | "success" | "failed";
type ConditionUsage = "include" | "exclude" | "reference" | "off";
type FinalUsageMap = Record<string, ConditionUsage>;
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
  return ["distance_pct"].includes(calculationType);
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

function PatternResearchPage() {
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
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const gptValidationResultRef = useRef<HTMLDivElement | null>(null);

  const summary = currentRun?.summary || null;
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
  const stepItems = [
    { key: "setup" as TabKey, label: "1. 찾을 패턴 설정", status: parsed ? "완료" : activeTab === "setup" ? "진행 중" : "대기" },
    { key: "gptValidation" as TabKey, label: "2. 수식화 GPT 검증 및 확정", status: newIndicatorRequiredConditions.length || needsReviewCount ? "확인 필요" : gptValidationStatusLabel(gptGoalValidationStatus) },
    { key: "samples" as TabKey, label: "3. 성공/실패 샘플 추출", status: currentRun ? "완료" : parsed ? "대기" : "대기" },
    { key: "package" as TabKey, label: "4. GPT 연구 패키지", status: gptPackage ? "완료" : currentRun ? "진행 가능" : "대기" },
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
      const isExecutable = targetCandidate.execution_supported === true || targetCandidate.calculation_type === "distance_pct";
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
            execution_message: targetCandidate.execution_message || "distance_pct 계산 유형은 샘플 엔진에서 실행 가능합니다.",
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

  const loadSamples = async (label: SampleTab) => {
    if (!currentRun) return;
    setSampleTab(label);
    setSamples((await repositories.patternResearch.fetchSamples(currentRun.id, label)).items);
  };

  const copyPrompt = async () => {
    if (!gptPackage?.gpt_prompt_text) return;
    await navigator.clipboard.writeText(gptPackage.gpt_prompt_text);
    setMessage("GPT에 붙여넣을 연구 요청문을 복사했습니다.");
  };

  const openCsv = () => {
    if (!currentRun) return;
    window.open(repositories.patternResearch.csvUrl(currentRun.id), "_blank", "noopener,noreferrer");
  };

  return (
    <div className="pattern-research-page space-y-4">
      <PageHeader
        title="매매패턴 AI연구"
        description="자연어 매매목표를 데이터 기반 조건으로 해석하고 성공/실패 샘플과 GPT 연구 패키지를 생성합니다."
      />
      {message ? <div className="alert success">{message}</div> : null}
      {error ? <div className="alert danger">{error}</div> : null}

      <SectionCard title="연구 흐름">
        <div className="pattern-stepper">
          {stepItems.map((step) => (
            <button
              key={step.key}
              className={`pattern-step-button ${activeTab === step.key ? "active" : ""} is-${step.status.replace(/\s/g, "-")}`}
              type="button"
              onClick={() => setActiveTab(step.key)}
            >
              <span>{step.label}</span>
              <em>{step.status}</em>
            </button>
          ))}
          <span className="active">① 연구 설정</span>
          <span className={gptGoalValidation || parsed ? "active" : ""}>② 수식 확정</span>
          <span className={currentRun ? "active" : ""}>③ 성공/실패 분석</span>
          <span className={gptPackage ? "active" : ""}>④ GPT 연구 패키지</span>
        </div>
        <p className="pattern-help-text">
          자연어 목표를 해석한 뒤 조건을 확인하고, 과거 가격 데이터에서 성공/실패 샘플을 분리합니다.
        </p>
      </SectionCard>

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
            {!gptPackage ? <EmptyState message="샘플 생성 후 GPT 연구 패키지를 만들 수 있습니다." /> : (
              <GptPackageReview
                gptPackage={gptPackage}
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
    </div>
  );
}

function Kpi({ label, value }: { label: string; value: string }) {
  return <div className="pattern-kpi-card"><span>{label}</span><strong>{value}</strong></div>;
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
              const renderedStatusBadges = Array.from(new Set([...statusBadges.filter((badge) => !String(badge).includes("계산")), ...newIndicatorStatusLabels(newIndicatorUsageStatus)]));
              return (
                <>
                  <tr key={row.key} className={focusedRowIdSet.has(row.key) ? "pattern-row-needs-action pattern-new-indicator-focus" : undefined}>
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
                        <span className={`condition-status-badge ${candidate.execution_supported || candidate.calculation_type === "distance_pct" ? "is-calculatable" : "is-needs_engine"}`}>
                          샘플 실행: {candidate.execution_supported || candidate.calculation_type === "distance_pct" ? "실행 가능" : "엔진 필요"}
                        </span>
                        {candidate.execution_message ? <small className="disabled-action-help">{candidate.execution_message}</small> : null}
                      </td>
                      <td>
                        <div className="pattern-llm-actions">
                          <button className="btn btn-secondary" type="button" disabled={candidate.execution_supported === false && candidate.calculation_type !== "distance_pct"} onClick={() => onMarkDecision("one_time", candidate)}>비교용으로만 사용</button>
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
