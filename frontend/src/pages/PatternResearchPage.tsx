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
  if (status === "error") return "오류";
  if (status === "catalog_missing") return "catalog 필요";
  return status || "-";
}

function statusClass(status: string): string {
  if (status === "applied" || status === "confirmed" || status === "sample_applied") return "confirmed";
  if (status === "calculated" || status === "calculable" || status === "calculatable" || status === "available") return "calculable";
  if (status === "needs_review") return "needs_review";
  if (status === "unsupported" || status === "catalog_missing") return "unsupported";
  if (status === "error") return "error";
  return "unknown";
}

function applyModeLabel(condition: Record<string, any>): string {
  if (condition.apply_mode_label) return String(condition.apply_mode_label);
  if (condition.status === "unsupported") return "미적용";
  return condition.apply_to_samples ? "샘플 필터 적용" : "조건 후보";
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
  if (value === true) return "샘플 필터 적용";
  if (value === false) return "조건 후보";
  return "항상 적용";
}

function conditionIdentity(condition: Record<string, any>): string {
  const indicator = condition.indicator_key || condition.indicator || "";
  const operator = condition.operator || "";
  const value = JSON.stringify(condition.value ?? null);
  const category = condition.category || condition.group || "";
  const expression = condition.expression || expressionForCondition(condition);
  return [indicator, operator, value, category, expression].join("|");
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
  const [gptGoalResultText, setGptGoalResultText] = useState("");
  const [gptGoalValidation, setGptGoalValidation] = useState<PatternGptGoalResultValidateResponse | null>(null);
  const [gptGoalValidationStatus, setGptGoalValidationStatus] = useState<GptValidationStatus>("idle");
  const [resolvedGptIndicatorKeys, setResolvedGptIndicatorKeys] = useState<string[]>([]);
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
  const canCreateSamples = Boolean(parsed) && newIndicatorRequiredConditions.length === 0;
  const stepItems = [
    { key: "setup" as TabKey, label: "1. 찾을 패턴 설정", status: parsed ? "완료" : activeTab === "setup" ? "진행 중" : "대기" },
    { key: "gptValidation" as TabKey, label: "2. 수식화 GPT 검증", status: gptValidationStatusLabel(gptGoalValidationStatus) },
    { key: "confirm" as TabKey, label: "3. 패턴 수식 확정", status: newIndicatorRequiredConditions.length || needsReviewCount ? "확인 필요" : parsed ? "완료" : "대기" },
    { key: "samples" as TabKey, label: "4. 성공/실패 샘플 추출", status: currentRun ? "완료" : parsed ? "대기" : "대기" },
    { key: "package" as TabKey, label: "5. GPT 연구 패키지", status: gptPackage ? "완료" : currentRun ? "진행 가능" : "대기" },
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
        status: candidate.validation_status === "valid" ? "applied" : "needs_review",
        interpretation_status_label: candidate.validation_status === "valid" ? "확정" : "확인 필요",
        apply_mode_label: applyToSamples ? "샘플 필터 적용" : "조건 후보",
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
                validation_message: "1회성 사용 처리되어 샘플 필터 적용이 가능합니다.",
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
      const response = await repositories.patternResearch.fetchGptGoalParsePrompt(goalText, parsed?.parsed_goal || null);
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

  const createRun = async () => {
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
      const created = await repositories.patternResearch.createRun({
        research_name: `${selectedStock.stock_name} 패턴 연구`,
        stock_codes: [selectedStock.stock_code],
        start_date: startDate,
        end_date: endDate,
        goal_text: goalText,
        parsed_goal: parsed.parsed_goal,
      });
      const run = await repositories.patternResearch.fetchRun(created.run_id);
      setCurrentRun(run);
      setSamples((await repositories.patternResearch.fetchSamples(created.run_id, sampleTab)).items);
      setGptPackage(await repositories.patternResearch.fetchGptPackage(created.run_id));
      setActiveTab("samples");
      setMessage("성공/실패 샘플을 생성했습니다.");
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : "성공/실패 샘플 생성에 실패했습니다.");
    } finally {
      setLoading(false);
    }
  };

  const loadSamples = async (label: SampleTab) => {
    if (!currentRun) return;
    setSampleTab(label);
    setSamples((await repositories.patternResearch.fetchSamples(currentRun.id, label)).items);
  };

  const copyPrompt = async () => {
    if (!gptPackage?.gpt_prompt_text) return;
    await navigator.clipboard.writeText(gptPackage.gpt_prompt_text);
    setMessage("GPT 연구 요청문을 복사했습니다.");
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
          <span className={currentRun ? "active" : ""}>② 성공/실패 분석</span>
          <span className={gptPackage ? "active" : ""}>③ GPT 연구 패키지</span>
          <span className="disabled">④ 전략 연결 예정</span>
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
            <label className="pattern-goal-input">
              <span>찾고 싶은 매매패턴</span>
              <textarea value={goalText} onChange={(event) => setGoalText(event.target.value)} />
            </label>
            <div className="pattern-sentence-guide">
              조건은 문장 단위로 입력해 주세요. 목표 해석 후 성공/실패 기준과 진입/제외 조건을 확인합니다.
            </div>
            <div className="pattern-action-row">
              <button className="btn btn-secondary" type="button" disabled={loading} onClick={parseGoal}>목표 해석하기</button>
            </div>
            <PatternFormulaSummary parsed={parsed} />
            <GoalInterpretation parsed={parsed} onUpdateCriteria={updateCriteria} onUpdateFilter={updateFilter} />
          </SectionCard>
        </div>
      ) : null}

      {activeTab === "gptValidation" ? (
        <div className="pattern-step-panel">
          <SectionCard title="2. 수식화 GPT 검증">
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
                setResolvedGptIndicatorKeys([]);
              }}
              onValidate={validateGptGoalResult}
              onApplyCandidate={addCandidateToGoal}
              onSaveIndicatorCandidate={saveIndicatorCandidate}
              onMarkDecision={markGptCandidateDecision}
            />
          </SectionCard>
        </div>
      ) : null}

      {activeTab === "confirm" ? (
        <div className="pattern-step-panel">
          <SectionCard title="3. 패턴 수식 확정">
            <PatternFormulaSummary parsed={parsed} />
            <PatternConfirmPanel
              parsed={parsed}
              gptValidation={gptGoalValidation}
              unresolvedConditions={newIndicatorRequiredConditions}
              onGoToGpt={() => setActiveTab("gptValidation")}
              onGoToCandidate={(indicatorKey) => {
                setActiveTab("gptValidation");
                window.setTimeout(() => scrollToIndicatorCandidate(indicatorKey), 120);
              }}
            />
            <GoalInterpretation parsed={parsed} onUpdateCriteria={updateCriteria} onUpdateFilter={updateFilter} />
          </SectionCard>
        </div>
      ) : null}

      {activeTab === "samples" ? (
        <div className="pattern-step-panel">
          <SectionCard title="4. 성공/실패 샘플 추출">
            <PatternFormulaSummary parsed={parsed} />
            <SampleReadinessCard
              parsed={parsed}
              unresolvedConditions={newIndicatorRequiredConditions}
              canCreateSamples={canCreateSamples}
              onGoToGpt={() => setActiveTab("gptValidation")}
            />
            {newIndicatorRequiredConditions.length ? (
              <div className="alert warning">미해결 신규 지표 조건이 있어 샘플 필터 적용에 주의가 필요합니다. 신규 지표 후보를 먼저 확인해 주세요.</div>
            ) : null}
            <div className="pattern-action-row">
              <button className="btn btn-primary" type="button" disabled={loading || !parsed || !canCreateSamples} onClick={createRun}>
                확정 조건으로 성공/실패 샘플 생성
              </button>
            </div>
            {!currentRun || !summary ? <EmptyState message="샘플 생성 후 결과 요약과 목록이 표시됩니다." /> : (
              <>
                <div className="pattern-sample-kpi-grid">
                  <Kpi label="전체 후보" value={fmtNumber(summary.total_samples, 0)} />
                  <Kpi label="성공 샘플" value={fmtNumber(summary.success_count, 0)} />
                  <Kpi label="실패 샘플" value={fmtNumber(summary.failure_count, 0)} />
                  <Kpi label="중립 샘플" value={fmtNumber(summary.neutral_count, 0)} />
                  <Kpi label="성공률" value={fmtPercent(summary.success_rate)} />
                </div>
                {summary.sample_filter_warning ? <div className="alert warning">{summary.sample_filter_warning}</div> : null}
                <SampleTable samples={samples} sampleTab={sampleTab} onChangeTab={loadSamples} />
              </>
            )}
          </SectionCard>
        </div>
      ) : null}

      {activeTab === "package" ? (
        <div className="pattern-step-panel">
          <SectionCard title="5. GPT 연구 패키지">
            {!gptPackage ? <EmptyState message="샘플 생성 후 GPT 연구 패키지를 만들 수 있습니다." /> : (
              <>
                <div className="pattern-action-row">
                  <button className="btn btn-secondary" type="button" onClick={copyPrompt}><Clipboard size={15} /> 연구 요청문 복사</button>
                  <button className="btn btn-secondary" type="button" onClick={openCsv}><Download size={15} /> CSV 다운로드</button>
                </div>
                <div className="pattern-package-summary">
                  <span>사용자 목표 포함</span>
                  <span>확정 조건 포함</span>
                  <span>샘플 통계 포함</span>
                  <span>성공/실패 예시 포함</span>
                  <span>신규 지표 사용 여부 포함</span>
                </div>
                <GptPackagePreview summary={gptPackage.summary || {}} />
                <textarea className="pattern-gpt-prompt" readOnly value={gptPackage.gpt_prompt_text} />
              </>
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
              <button className="btn btn-primary" type="button" disabled={loading || !parsed} onClick={createRun}>기준으로 샘플 생성</button>
            </div>
            <GoalInterpretation parsed={parsed} onUpdateCriteria={updateCriteria} onUpdateFilter={updateFilter} />
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

function PatternFormulaSummary({ parsed }: { parsed: PatternGoalParseResponse | null }) {
  const goal = parsed?.parsed_goal || {};
  const success = goal.success_criteria || goal.success_rule || null;
  const failure = goal.failure_criteria || goal.failure_rule || null;
  const entryFilters = (goal.entry_filters || []) as Array<Record<string, any>>;
  const excludeFilters = (goal.exclude_filters || []) as Array<Record<string, any>>;
  const reviewCount = [...entryFilters, ...excludeFilters].filter((item) => item.status === "needs_review" || item.validation_status === "needs_review").length;

  if (!parsed) {
    return <div className="pattern-empty-note">목표 해석 후 성공 기준, 실패 기준, 진입/제외 조건 요약이 표시됩니다.</div>;
  }

  return (
    <div className="pattern-formula-summary-grid">
      <Kpi label="성공 기준" value={success?.expression || expressionForCondition(success || {})} />
      <Kpi label="실패 기준" value={failure?.expression || expressionForCondition(failure || {})} />
      <Kpi label="진입 조건" value={`${entryFilters.length}개`} />
      <Kpi label="제외 조건" value={`${excludeFilters.length}개`} />
      <Kpi label="확인 필요" value={`${reviewCount}개`} />
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
        <h4>확인 필요 조건 <span>{needsReview.length}개</span></h4>
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
}: {
  parsed: PatternGoalParseResponse | null;
  onUpdateCriteria: (kind: "success_criteria" | "failure_criteria", key: string, value: any) => void;
  onUpdateFilter: (kind: "entry_filters" | "exclude_filters", index: number, updates: Record<string, any>) => void;
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
        조건의 적용 방식은 실제 샘플 필터에 사용할지, GPT 연구 참고로만 넘길지 결정합니다.
      </div>
      <div className="table-shell pattern-condition-shell">
        <table className="data-table compact-table pattern-condition-table">
          <thead>
            <tr>
              <th>자연어 표현</th>
              <th>해석 수식</th>
              <th>사용 지표</th>
              <th>적용 구분</th>
              <th>해석 출처</th>
              <th>적용 방식</th>
              <th>해석 상태</th>
              <th>수정값</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td>{success.natural_text || "목표 수익률"}</td>
              <td>{success.expression || expressionForCondition({ indicator_key: `max_future_return_${success.target_days || goal.target_days}d`, operator: ">=", value: success.target_return_pct || goal.target_return_pct })}</td>
              <td>미래 최대수익률</td>
              <td>성공 기준</td>
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
              <td>실패 기준</td>
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
                category="진입 조건"
                onToggle={(checked) => onUpdateFilter("entry_filters", index, { apply_to_samples: checked })}
                onChangeValue={(value) => onUpdateFilter("entry_filters", index, { value })}
              />
            ))}
            {excludeFilters.map((condition: Record<string, any>, index: number) => (
              <ConditionRow
                key={`exclude-${index}`}
                condition={condition}
                category="제외 조건"
                onToggle={(checked) => onUpdateFilter("exclude_filters", index, { apply_to_samples: checked })}
                onChangeValue={(value) => onUpdateFilter("exclude_filters", index, { value })}
              />
            ))}
            {unsupportedItems.map((item, index) => (
              <tr key={`unsupported-${index}`}>
                <td>{item.natural_text || item.source_text || JSON.stringify(item)}</td>
                <td>-</td>
                <td>{item.indicator_key || "-"}</td>
                <td>미지원</td>
                <td>{item.source || "-"}</td>
                <td>적용 안 함</td>
                <td><em className="pattern-status-badge pattern-status-unsupported">미지원</em></td>
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
  onToggle,
  onChangeValue,
}: {
  condition: Record<string, any>;
  category: string;
  onToggle: (checked: boolean) => void;
  onChangeValue: (value: any) => void;
}) {
  return (
    <tr>
      <td>{condition.natural_text || condition.source_text || "-"}</td>
      <td>{condition.expression || expressionForCondition(condition)}</td>
      <td>{condition.indicator_key || condition.indicator || "-"}</td>
      <td>{category}</td>
      <td>{condition.source || "-"}</td>
      <td>
        <label className="pattern-condition-toggle">
          <input type="checkbox" checked={Boolean(condition.apply_to_samples)} onChange={(event) => onToggle(event.target.checked)} />
          <span>{applyModeLabel(condition)}</span>
        </label>
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
                  <tr><th>원문</th><th>조건명</th><th>수식</th><th>지표</th><th>구분</th><th>검증 상태</th><th>적용 방식</th><th>처리</th></tr>
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
                        <td>{condition.apply_mode_label || (condition.apply_to_samples ? "조건표 반영" : "조건 후보")}</td>
                        <td>
                          <div className="pattern-llm-actions">
                            {condition.validation_status === "new_indicator_required" ? <button className="btn btn-secondary" type="button" onClick={() => scrollToIndicatorCandidate(String(condition.indicator_key || ""))}>신규 지표 후보 보기</button> : null}
                            <button className="btn btn-primary" type="button" disabled={cannotApplyToSamples} onClick={() => onApplyCandidate(condition, true)}>조건표에 반영</button>
                            <button className="btn btn-secondary" type="button" disabled={cannotUseAsReference} onClick={() => onApplyCandidate(condition, false)}>조건 후보</button>
                            <button className="btn btn-secondary" type="button" onClick={() => onMarkDecision("exclude", condition.label || condition.source_text)}>제외</button>
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
                          <button className="btn btn-secondary" type="button" disabled={candidate.execution_supported === false && candidate.calculation_type !== "distance_pct"} onClick={() => onMarkDecision("one_time", candidate)}>1회성 사용</button>
                          <button className="btn btn-primary" type="button" onClick={() => void onSaveIndicatorCandidate(candidate)}>지표 기준정보 등록</button>
                          <button className="btn btn-secondary" type="button" onClick={() => onMarkDecision("reference", candidate.indicator_key)}>조건 후보</button>
                          <button className="btn btn-secondary" type="button" onClick={() => onMarkDecision("exclude", candidate.indicator_key)}>제외</button>
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
                        <button className="btn btn-primary" type="button" disabled={rejected} onClick={() => onApplyCandidate(condition, true)}>샘플 필터 적용</button>
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
                <button className="btn btn-primary" type="button" disabled={rejected} onClick={() => onApplyCandidate(merged, true)}>샘플 필터 적용</button>
              </div>
            </td>
          </tr>
        );
      })}
    </>
  );
}

function SampleTable({ samples, sampleTab, onChangeTab }: { samples: PatternResearchSample[]; sampleTab: SampleTab; onChangeTab: (tab: SampleTab) => Promise<void> }) {
  return (
    <div className="pattern-samples-block">
      <div className="pattern-sample-tabs">
        {(["SUCCESS", "FAILURE", "NEUTRAL"] as SampleTab[]).map((tab) => (
          <button key={tab} type="button" className={sampleTab === tab ? "active" : ""} onClick={() => void onChangeTab(tab)}>{tab}</button>
        ))}
      </div>
      <div className="table-shell">
        <table className="data-table compact-table">
          <thead>
            <tr>
              <th>날짜</th>
              <th className="numeric-cell">종가</th>
              <th className="numeric-cell">최대상승률</th>
              <th className="numeric-cell">최대하락률</th>
              <th>target</th>
              <th>stop</th>
              <th>라벨</th>
              <th>진입후보</th>
              <th>제외사유</th>
              <th className="numeric-cell">전일대비 거래량</th>
              <th className="numeric-cell">전일대비 거래대금</th>
              <th className="numeric-cell">거래량 20일배수</th>
              <th className="numeric-cell">거래대금 20일배수</th>
              <th className="numeric-cell">20일선 이격률</th>
              <th>60일선 상승</th>
              <th>일치 조건</th>
              <th>태그</th>
            </tr>
          </thead>
          <tbody>
            {samples.map((sample) => (
              <tr key={sample.id}>
                <td>{sample.trade_date}</td>
                <td className="numeric-cell">{fmtWon(sample.features?.close_price)}</td>
                <td className="numeric-cell">{fmtPercent(sample.max_future_return_pct)}</td>
                <td className="numeric-cell">{fmtPercent(sample.min_future_return_pct)}</td>
                <td>{sample.target_hit ? "Y" : "N"}</td>
                <td>{sample.stop_hit ? "Y" : "N"}</td>
                <td>{sample.result_label}</td>
                <td>{sample.features?.is_entry_candidate ? "Y" : "N"}</td>
                <td>{sample.features?.exclude_reason || "-"}</td>
                <td className="numeric-cell">{fmtNumber(sample.features?.volume_vs_prev_day)}</td>
                <td className="numeric-cell">{fmtNumber(sample.features?.trading_value_vs_prev_day)}</td>
                <td className="numeric-cell">{fmtNumber(sample.features?.volume_ratio_20)}</td>
                <td className="numeric-cell">{fmtNumber(sample.features?.trading_value_ratio_20)}</td>
                <td className="numeric-cell">{fmtPercent(sample.features?.close_vs_ma20_pct)}</td>
                <td>{sample.features?.is_ma60_rising_5d ? "Y" : "N"}</td>
                <td>{(sample.features?.matched_conditions || []).join(", ") || "-"}</td>
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
