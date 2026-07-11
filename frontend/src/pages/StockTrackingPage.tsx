import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import PageHeader from "@/components/common/PageHeader";
import SectionCard from "@/components/common/SectionCard";
import { repositories } from "@/services";
import { appConfig } from "@/services/config/appConfig";
import type { AppImage } from "@/types/image";
import type {
  CollectStockTrackingPricesResponse,
  StockTrackingChartPrice,
  StockTrackingBaseMetricSummary,
  StockTrackingChartResponse,
  StockTrackingGroup,
  StockTrackingGroupAnalysis,
  StockTrackingGroupAnalysisSample,
  StockTrackingImage,
  StockTrackingImageType,
  StockTrackingItem,
  StockTrackingPriceStatus,
  StockTrackingStatus,
} from "@/types/stockTracking";

const STATUS_LABELS: Record<StockTrackingStatus, string> = {
  TRACKING: "트래킹중",
  SUCCESS: "성공",
  FAIL: "실패",
  HOLD: "보류",
  EXCLUDED: "제외",
};

const PRICE_STATUS_LABELS: Record<StockTrackingPriceStatus, string> = {
  NOT_COLLECTED: "미수집",
  COLLECTING: "수집중",
  LATEST: "최신",
  PARTIAL: "부분누락",
  STOPPED: "중단",
  ERROR: "오류",
};

const IMAGE_TYPE_OPTIONS: Array<{ value: StockTrackingImageType; label: string }> = [
  { value: "BASE_DATE", label: "기준일 차트" },
  { value: "SUCCESS", label: "성공 근거" },
  { value: "FAIL", label: "실패 근거" },
  { value: "PULLBACK", label: "눌림 구간" },
  { value: "OVERHEAT", label: "과열 구간" },
  { value: "ENTRY_POINT", label: "진입 가능 구간" },
  { value: "ETC", label: "기타" },
];

const ITEM_PAGE_SIZE = 20;
type TrackingCollectionScope = "all" | "checked" | "detail";
type TrackingCollectionMode = "recent" | "full";
type TrackingFullRefreshTarget = Exclude<TrackingCollectionScope, "detail">;

const emptyImageForm: { image_type: StockTrackingImageType; caption: string; file: File | null } = {
  image_type: "BASE_DATE",
  caption: "",
  file: null,
};

const emptyGroupForm = {
  name: "",
  description: "",
  success_rule_note: "",
  fail_rule_note: "",
  observation_note: "",
  is_active: 1,
};

const fmtDate = (value?: string | null) => value || "-";
const formatDateTime = (value?: string | null) => {
  if (!value) return "-";
  const normalized = value.replace("T", " ").slice(0, 16);
  return normalized || "-";
};
const getImageTypeLabel = (type: string, label?: string | null) => label || IMAGE_TYPE_OPTIONS.find((option) => option.value === type)?.label || type;
const getImageUrl = (url?: string | null) => {
  if (!url) return "";
  if (/^https?:\/\//i.test(url) || url.startsWith("blob:")) return url;
  const normalized = url.startsWith("/") ? url : "/" + url;
  return appConfig.apiBaseUrl + normalized;
};
const fmtPct = (value?: number | null) => (value == null ? "-" : `${Number(value).toFixed(2)}%`);
const fmtSignedPct = (value?: number | null) => {
  if (value == null || !Number.isFinite(value)) return "-";
  if (Object.is(value, -0) || Math.abs(value) < 0.005) return "0.00%";
  return `${value > 0 ? "+" : ""}${Number(value).toFixed(2)}%`;
};
const fmtNumber = (value?: number | null) => (value == null ? "-" : Number(value).toLocaleString("ko-KR"));
const fmtEok = (value?: number | null) => (value == null ? "-" : `${(Number(value) / 100000000).toLocaleString("ko-KR", { maximumFractionDigits: 1 })}억`);
const canCollectItem = (item: StockTrackingItem) => (item.status === "TRACKING" || item.status === "HOLD") && item.price_status !== "STOPPED";
const getCollectResultMessage = (response: CollectStockTrackingPricesResponse, mode: TrackingCollectionMode) => {
  if (response.requested_count === 0) return "갱신할 트래킹 종목이 없습니다.";
  const label = mode === "full" ? "전체수집" : "최근7일수집";
  const savedCount = response.items.reduce((sum, item) => sum + Number(item.saved_count || 0), 0);
  const fromDates = response.items.map((item) => item.requested_start_date).filter((value): value is string => Boolean(value));
  const toDates = response.items.map((item) => item.requested_end_date).filter((value): value is string => Boolean(value));
  const range = fromDates.length && toDates.length ? `${fromDates.sort()[0]} ~ ${toDates.sort()[toDates.length - 1]}, 저장 ${savedCount.toLocaleString("ko-KR")}건` : `${response.requested_count}개 종목 가격 데이터 갱신`;
  return `${label} 완료: ${range} / 성공 ${response.success_count}건, 일부 누락 ${response.partial_count}건, 실패 ${response.failed_count}건`;
};

function pathFromPoints(points: Array<{ x: number; y: number }>) {
  return points.map((point, index) => `${index === 0 ? "M" : "L"}${point.x.toFixed(1)},${point.y.toFixed(1)}`).join(" ");
}

type TrackingReturnSummary = {
  currentReturnPct: number | null;
  maxReturnPct: number | null;
  maxDrawdownPct: number | null;
  elapsedTradingDays: number | null;
  basePrice: number | null;
};

const normalizeDate = (value?: string | null) => value?.slice(0, 10) || "";
const calculateReturnPct = (value: number | null, basePrice: number | null) => {
  if (value == null || basePrice == null || basePrice <= 0) return null;
  const pct = ((value - basePrice) / basePrice) * 100;
  return Number.isFinite(pct) ? pct : null;
};
const calculateTrackingReturnSummary = (chart: StockTrackingChartResponse, item?: StockTrackingItem | null): TrackingReturnSummary | null => {
  const baseDate = normalizeDate(item?.tracking_base_date || chart.tracking_base_date);
  const prices = chart.prices.filter((price) => normalizeDate(price.date) >= baseDate);
  if (!baseDate || prices.length === 0) return null;
  const baseDatePrice = prices.find((price) => normalizeDate(price.date) === baseDate);
  const fallbackFirstPrice = prices.find((price) => price.close != null);
  const basePrice = baseDatePrice?.close ?? item?.base_price ?? fallbackFirstPrice?.close ?? null;
  if (basePrice == null || basePrice <= 0) {
    return { currentReturnPct: null, maxReturnPct: null, maxDrawdownPct: null, elapsedTradingDays: null, basePrice: null };
  }
  const lastClose = [...prices].reverse().find((price) => price.close != null)?.close ?? null;
  const highs = prices.map((price) => price.high).filter((value): value is number => value != null);
  const lows = prices.map((price) => price.low).filter((value): value is number => value != null);
  return {
    currentReturnPct: calculateReturnPct(lastClose, basePrice),
    maxReturnPct: highs.length > 0 ? calculateReturnPct(Math.max(...highs), basePrice) : null,
    maxDrawdownPct: lows.length > 0 ? calculateReturnPct(Math.min(...lows), basePrice) : null,
    elapsedTradingDays: Math.max(0, prices.length - 1),
    basePrice,
  };
};
const formatReturnPct = (value: number | null) => {
  if (value == null || !Number.isFinite(value)) return "-";
  if (Object.is(value, -0) || Math.abs(value) < 0.05) return "0.0%";
  return `${value > 0 ? "+" : ""}${value.toFixed(1)}%`;
};
const getReturnClass = (value: number | null) => value == null || Math.abs(value) < 0.05 ? "stock-tracking-return-neutral" : value > 0 ? "stock-tracking-return-positive" : "stock-tracking-return-negative";
const formatPlainPct = (value?: number | null) => value == null || !Number.isFinite(value) ? "-" : `${Number(value).toFixed(1)}%`;
const getSuccessRateReliabilityText = (completedCount: number) => completedCount > 0 && completedCount < 5 ? `판단완료 ${completedCount}건 기준, 신뢰도 낮음` : "";
const formatSuccessRateLabel = (successRate?: number | null, completedCount = 0) => {
  const base = formatPlainPct(successRate);
  const note = getSuccessRateReliabilityText(completedCount);
  return note ? `${base} (${note})` : base;
};
const formatAnalysisReturn = (value?: number | null) => formatReturnPct(value ?? null);
const formatTradingDays = (value?: number | null) => value == null ? "-" : Math.round(Number(value)) + "거래일";
type BaseMetricKey = keyof StockTrackingBaseMetricSummary;
const BASE_METRIC_DEFINITIONS: Array<{ key: BaseMetricKey; label: string; unit: "pct" | "ratio" }> = [
  { key: "close_vs_ma20_pct", label: "20일선 이격", unit: "pct" },
  { key: "close_vs_ma60_pct", label: "60일선 이격", unit: "pct" },
  { key: "recent_5d_return_pct", label: "최근 5일 상승률", unit: "pct" },
  { key: "trading_value_ratio_20", label: "거래대금 배율", unit: "ratio" },
  { key: "ma60_slope_5d_pct", label: "60일선 기울기", unit: "pct" },
  { key: "high_vs_close_pct", label: "고가 대비 종가 괴리", unit: "pct" },
  { key: "close_position_pct", label: "종가 위치", unit: "pct" },
];
const getMetricDefinition = (key: BaseMetricKey) => BASE_METRIC_DEFINITIONS.find((metric) => metric.key === key);
const formatBaseMetricValue = (key: BaseMetricKey, value?: number | null) => {
  if (value == null || !Number.isFinite(value)) return "-";
  const definition = getMetricDefinition(key);
  if (definition?.unit === "ratio") return Number(value).toFixed(1) + "배";
  if (Object.is(value, -0) || Math.abs(value) < 0.05) return "0.0%";
  return (value > 0 ? "+" : "") + Number(value).toFixed(1) + "%";
};
const formatBaseMetricDiff = (key: BaseMetricKey, value?: number | null) => {
  if (value == null || !Number.isFinite(value)) return "-";
  const definition = getMetricDefinition(key);
  if (definition?.unit === "ratio") return (value > 0 ? "+" : "") + Number(value).toFixed(1) + "배";
  if (Object.is(value, -0) || Math.abs(value) < 0.05) return "0.0%p";
  return (value > 0 ? "+" : "") + Number(value).toFixed(1) + "%p";
};
const getBaseMetricClass = (value?: number | null) => value == null || Math.abs(value) < 0.05 ? "stock-tracking-return-neutral" : value > 0 ? "stock-tracking-return-positive" : "stock-tracking-return-negative";
const getBaseMetricInterpretation = (key: BaseMetricKey, success?: number | null, fail?: number | null, diffValue?: number | null) => {
  if (success == null || fail == null || diffValue == null) return "비교 샘플 부족";
  if (key === "close_vs_ma20_pct") {
    if (fail - success >= 8) return "실패 샘플 과열 가능성";
    if (success >= 0 && success <= 8 && success < fail) return "성공 샘플 눌림권 가능성";
  }
  if (key === "close_vs_ma60_pct" && fail - success >= 15) return "실패 샘플 중기 고점권 가능성";
  if (key === "recent_5d_return_pct" && fail - success >= 10) return "실패 샘플 단기 추격 위험";
  if (key === "trading_value_ratio_20" && success - fail >= 1) return "성공 샘플 수급 강도 우위 가능성";
  if (key === "ma60_slope_5d_pct" && success > 0 && fail <= 0) return "성공 샘플 중기 추세 우위 가능성";
  if (key === "high_vs_close_pct" && fail < success && fail - success <= -3) return "실패 샘플 장중 고점 이탈 가능성";
  if (key === "close_position_pct" && success - fail >= 20) return "성공 샘플 종가 압력 우위 가능성";
  return "추가 샘플 필요";
};
type AnalysisPromptMode = "COMPARISON" | "FAIL_ONLY" | "SUCCESS_ONLY" | "NO_JUDGEMENT";
const getAnalysisPromptMode = (analysis: StockTrackingGroupAnalysis): AnalysisPromptMode => {
  if (analysis.success_count > 0 && analysis.fail_count > 0) return "COMPARISON";
  if (analysis.success_count === 0 && analysis.fail_count > 0) return "FAIL_ONLY";
  if (analysis.success_count > 0 && analysis.fail_count === 0) return "SUCCESS_ONLY";
  return "NO_JUDGEMENT";
};
const truncateMemo = (value?: string | null, limit = 110) => {
  const normalized = (value || "-").replace(/\s+/g, " ").trim();
  return normalized.length > limit ? normalized.slice(0, limit) + "..." : normalized;
};
const formatPromptSampleRows = (samples: StockTrackingGroupAnalysisSample[]) => {
  if (samples.length === 0) return "- 샘플 없음";
  return samples.slice(0, 10).map((sample, index) => [
    String(index + 1) + ". " + (sample.stock_name || "-") + " (" + (sample.stock_code || "-") + ")",
    "기준일 " + fmtDate(sample.tracking_base_date),
    "현재 " + formatAnalysisReturn(sample.current_return_pct),
    "최고 " + formatAnalysisReturn(sample.max_return_pct),
    "최대하락 " + formatAnalysisReturn(sample.max_drawdown_pct),
    "20일선 이격 " + formatBaseMetricValue("close_vs_ma20_pct", sample.close_vs_ma20_pct),
    "최근5일 " + formatBaseMetricValue("recent_5d_return_pct", sample.recent_5d_return_pct),
    "거래대금 배율 " + formatBaseMetricValue("trading_value_ratio_20", sample.trading_value_ratio_20),
    "경과 " + formatTradingDays(sample.elapsed_trading_days),
    "판단일 " + fmtDate(sample.review_date),
    "메모 " + truncateMemo(sample.review_note),
  ].join(" | ")).join("\n");
};
const buildPromptPurposeSection = (mode: AnalysisPromptMode) => {
  if (mode === "COMPARISON") return [
    "[분석 목적]",
    "1. 이 그룹이 어떤 특징을 가진 조건검색/관찰 그룹인지 평가",
    "2. 성공 샘플과 실패 샘플의 가장 큰 차이 도출",
    "3. 실패를 줄이기 위해 제외해야 할 조건 후보 제안",
    "4. 성공률을 높이기 위해 추가로 확인할 조건 후보 제안",
    "5. 다음 매매훈련에서 확인할 체크리스트 작성",
  ];
  if (mode === "FAIL_ONLY") return [
    "[분석 목적]",
    "1. 현재 실패 샘플에서 관찰 가능한 위험 신호 도출",
    "2. 성공 샘플이 없다는 한계를 먼저 명시",
    "3. 실패를 줄이기 위해 향후 확인해야 할 제외 조건 후보 제안",
    "4. 성공 샘플이 생기면 비교해야 할 관찰 항목 제안",
    "5. 다음 매매훈련에서 확인할 체크리스트 작성",
  ];
  if (mode === "SUCCESS_ONLY") return [
    "[분석 목적]",
    "1. 현재 성공 샘플에서 관찰 가능한 긍정 신호 도출",
    "2. 실패 샘플이 없다는 한계를 먼저 명시",
    "3. 성공률을 유지하기 위해 확인할 보조 조건 후보 제안",
    "4. 실패 샘플이 생기면 비교해야 할 위험 항목 제안",
    "5. 다음 매매훈련에서 확인할 체크리스트 작성",
  ];
  return [
    "[분석 목적]",
    "1. 아직 성공/실패 분석이 불가능함을 명확히 표시",
    "2. 현재 트래킹중 또는 보류 종목에서 관찰할 포인트 정리",
    "3. 향후 성공/실패 판단 때 반드시 기록해야 할 항목 제안",
    "4. 다음 매매훈련에서 확인할 체크리스트 작성",
  ];
};
const buildPromptBaseMetricSection = (analysis: StockTrackingGroupAnalysis, mode: AnalysisPromptMode) => {
  const summary = analysis.base_metric_summary;
  const avg = summary?.avg ?? {};
  const successAvg = summary?.success_avg ?? {};
  const failAvg = summary?.fail_avg ?? {};
  const diff = summary?.diff ?? {};
  const hasComparison = mode === "COMPARISON";
  const lines = ["[성공/실패 기준일 지표 비교]"];
  if (!hasComparison) lines.push("- 성공 또는 실패 샘플이 부족하여 기준일 지표 비교는 제한적입니다.");
  BASE_METRIC_DEFINITIONS.forEach((metric) => {
    const key = metric.key;
    if (hasComparison) {
      lines.push("- " + metric.label + ": 전체 평균 " + formatBaseMetricValue(key, avg[key]) + " / 성공 평균 " + formatBaseMetricValue(key, successAvg[key]) + " / 실패 평균 " + formatBaseMetricValue(key, failAvg[key]) + " / 차이 " + formatBaseMetricDiff(key, diff[key]));
    } else {
      lines.push("- 전체 평균 " + metric.label + ": " + formatBaseMetricValue(key, avg[key]));
    }
  });
  return lines;
};

const buildPromptComparisonSection = (analysis: StockTrackingGroupAnalysis, mode: AnalysisPromptMode) => {
  if (mode !== "COMPARISON") return [
    "[성공/실패 차이]",
    "- 성공 또는 실패 샘플이 부족하여 비교할 수 없습니다.",
  ];
  return [
    "[성공/실패 차이]",
    "- 현재수익률 차이: " + formatAnalysisReturn(analysis.diff_avg_current_return_pct),
    "- 최고수익률 차이: " + formatAnalysisReturn(analysis.diff_avg_max_return_pct),
    "- 최대하락률 차이: " + formatAnalysisReturn(analysis.diff_avg_max_drawdown_pct),
  ];
};
const buildDataLimitationSection = (analysis: StockTrackingGroupAnalysis, mode: AnalysisPromptMode) => {
  const lines = ["[데이터 부족 안내]"];
  lines.push("- 가격 데이터가 부족한 종목은 수익률 평균에서 제외되었을 수 있습니다.");
  if (analysis.completed_count === 0) lines.push("- 성공/실패 판단완료 종목이 없어 성과 분석은 불가능합니다.");
  else if (analysis.completed_count < 5) lines.push("- 성공+실패 판단완료 수가 5건 미만이므로 결론을 단정하지 말고 가설로 표현해 주세요.");
  else if (analysis.completed_count < 20) lines.push("- 판단완료 수가 아직 충분하지 않으므로 결론은 예비 가설로 표현해 주세요.");
  else lines.push("- 표본 수는 어느 정도 확보되었지만 시장 환경과 기간 영향을 함께 고려해 주세요.");
  if (mode === "FAIL_ONLY") lines.push("- 성공 샘플이 없으므로 긍정 신호를 확정하지 말고, 향후 확인할 항목만 제안해 주세요.");
  if (mode === "SUCCESS_ONLY") lines.push("- 실패 샘플이 없으므로 위험 신호를 확정하지 말고, 향후 확인할 항목만 제안해 주세요.");
  if (mode === "NO_JUDGEMENT") lines.push("- 성공/실패 비교가 불가능하므로 관찰 체크리스트 중심으로만 답변해 주세요.");
  if ((analysis.avg_elapsed_trading_days ?? 999) <= 1) lines.push("- 평균 경과 거래일이 1거래일 이하이므로 추세 판단이 아니라 초기 반응 관찰 수준으로 해석해 주세요.");
  else if ((analysis.avg_elapsed_trading_days ?? 999) < 5) lines.push("- 평균 경과 거래일이 5거래일 미만이므로 단기 초기 반응 중심으로 해석해 주세요.");
  else lines.push("- 기준일 이후 단기 흐름을 기준으로 해석해 주세요.");
  return lines;
};
const buildPromptRequestSection = (mode: AnalysisPromptMode) => {
  if (mode === "COMPARISON") return [
    "[분석 요청]",
    "1. 이 그룹의 현재 성과를 요약해 주세요.",
    "2. 성공 샘플과 실패 샘플의 가장 큰 차이를 3가지로 정리해 주세요.",
    "3. 실패 샘플에서 반복되는 위험 신호를 찾아 주세요.",
    "4. 성공 샘플에서 반복되는 긍정 신호를 찾아 주세요.",
    "5. 이 조건검색 그룹에서 제외 조건으로 추가할 후보를 제안해 주세요.",
    "6. 이 조건검색 그룹에서 보조 확인 조건으로 추가할 후보를 제안해 주세요.",
    "7. 다음 매매훈련에서 확인할 체크리스트를 작성해 주세요.",
    "8. 데이터가 부족하거나 판단이 어려운 부분은 명확히 표시해 주세요.",
    "9. 종목 추천이나 매수/매도 추천은 하지 말고, 조건과 패턴 중심으로만 답변해 주세요.",
  ];
  if (mode === "FAIL_ONLY") return [
    "[분석 요청]",
    "1. 이 그룹의 현재 성과를 데이터 부족을 전제로 요약해 주세요.",
    "2. 성공 샘플이 없으므로 성공/실패 차이는 비교하지 말고, 실패 샘플에서 관찰 가능한 위험 신호를 정리해 주세요.",
    "3. 실패 샘플을 기준으로 향후 제외 조건 후보로 검토할 만한 항목을 제안해 주세요.",
    "4. 성공 샘플이 생기면 반드시 비교해야 할 관찰 항목을 제안해 주세요.",
    "5. 계속 관찰할 가치와 추가로 필요한 판단완료 데이터 수를 제안해 주세요.",
    "6. 다음 매매훈련에서 확인할 체크리스트를 작성해 주세요.",
    "7. 결론을 단정하지 말고 조건과 패턴 중심으로만 답변해 주세요.",
  ];
  if (mode === "SUCCESS_ONLY") return [
    "[분석 요청]",
    "1. 이 그룹의 현재 성과를 데이터 부족을 전제로 요약해 주세요.",
    "2. 실패 샘플이 없으므로 성공/실패 차이는 비교하지 말고, 성공 샘플에서 관찰 가능한 긍정 신호를 정리해 주세요.",
    "3. 성공 샘플을 기준으로 보조 확인 조건 후보로 검토할 만한 항목을 제안해 주세요.",
    "4. 실패 샘플이 생기면 반드시 비교해야 할 위험 항목을 제안해 주세요.",
    "5. 계속 관찰할 가치와 추가로 필요한 판단완료 데이터 수를 제안해 주세요.",
    "6. 다음 매매훈련에서 확인할 체크리스트를 작성해 주세요.",
    "7. 결론을 단정하지 말고 조건과 패턴 중심으로만 답변해 주세요.",
  ];
  return [
    "[분석 요청]",
    "1. 아직 성공/실패 판단 데이터가 없어 성과 분석이 불가능하다고 명확히 말해 주세요.",
    "2. 현재 전체 수익률 요약을 바탕으로 관찰 가능한 초기 흐름만 조심스럽게 정리해 주세요.",
    "3. 향후 성공/실패 판단 때 반드시 기록해야 할 항목을 제안해 주세요.",
    "4. 최소 몇 건 이상의 성공/실패 판단 데이터가 쌓이면 분석이 나아질지 제안해 주세요.",
    "5. 다음 매매훈련에서 확인할 체크리스트를 작성해 주세요.",
    "6. 종목 추천이나 매수/매도 추천은 하지 말고, 조건과 패턴 중심으로만 답변해 주세요.",
  ];
};
const buildGroupAnalysisGptPrompt = (analysis: StockTrackingGroupAnalysis) => {
  const mode = getAnalysisPromptMode(analysis);
  const lines = [
    "[DrCT 종목트래킹 그룹 분석 요청]",
    "",
    "당신은 종목 추천자가 아니라, 조건검색 결과를 검증하고 매매 판단 습관을 개선하기 위한 데이터 분석 코치입니다.",
    "아래 종목트래킹 그룹 데이터를 바탕으로 조건검색 그룹의 유효성과 관찰 포인트를 분석해 주세요.",
    "특정 종목의 매수/매도 추천은 하지 마세요. 조건과 패턴 중심으로만 답변해 주세요.",
    "",
    "주의:",
    "- 이 분석은 종목 추천이나 매수/매도 판단이 아닙니다.",
    "- 성공/실패 차이를 통해 조건검색식과 매매훈련 체크리스트를 개선하기 위한 목적입니다.",
    "- 데이터 수가 적으면 통계적 신뢰도가 낮을 수 있으므로 샘플 부족 여부를 먼저 평가해 주세요.",
    "- 결론을 단정하지 말고 데이터 수준에 맞는 표현을 사용해 주세요.",
    "",
    ...buildPromptPurposeSection(mode),
    "",
    "[그룹 정보]",
    "- 그룹명: " + analysis.group_name,
    "- 전체 종목 수: " + analysis.total_count,
    "- 트래킹중: " + analysis.tracking_count,
    "- 보류: " + analysis.hold_count,
    "- 성공: " + analysis.success_count,
    "- 실패: " + analysis.fail_count,
    "- 제외: " + analysis.excluded_count,
    "- 판단완료: " + analysis.completed_count,
    "- 성공률: " + formatSuccessRateLabel(analysis.success_rate, analysis.completed_count),
    "- 수익률 계산 가능 종목 수: " + analysis.return_calculated_count,
    "",
    "[전체 수익률 요약]",
    "- 평균 현재수익률: " + formatAnalysisReturn(analysis.avg_current_return_pct),
    "- 평균 최고수익률: " + formatAnalysisReturn(analysis.avg_max_return_pct),
    "- 평균 최대하락률: " + formatAnalysisReturn(analysis.avg_max_drawdown_pct),
    "- 평균 경과 거래일: " + formatTradingDays(analysis.avg_elapsed_trading_days),
    "",
    "[성공 샘플 평균]",
    ...(analysis.success_count > 0 ? [
      "- 평균 현재수익률: " + formatAnalysisReturn(analysis.success_avg_current_return_pct),
      "- 평균 최고수익률: " + formatAnalysisReturn(analysis.success_avg_max_return_pct),
      "- 평균 최대하락률: " + formatAnalysisReturn(analysis.success_avg_max_drawdown_pct),
      "- 평균 경과 거래일: " + formatTradingDays(analysis.success_avg_elapsed_trading_days),
    ] : ["- 성공 샘플 없음"]),
    "",
    "[실패 샘플 평균]",
    ...(analysis.fail_count > 0 ? [
      "- 평균 현재수익률: " + formatAnalysisReturn(analysis.fail_avg_current_return_pct),
      "- 평균 최고수익률: " + formatAnalysisReturn(analysis.fail_avg_max_return_pct),
      "- 평균 최대하락률: " + formatAnalysisReturn(analysis.fail_avg_max_drawdown_pct),
      "- 평균 경과 거래일: " + formatTradingDays(analysis.fail_avg_elapsed_trading_days),
    ] : ["- 실패 샘플 없음"]),
    "",
    ...buildPromptComparisonSection(analysis, mode),
    "",
    ...buildPromptBaseMetricSection(analysis, mode),
    "",
    "[성공 샘플]",
    formatPromptSampleRows(analysis.success_samples),
    "",
    "[실패 샘플]",
    formatPromptSampleRows(analysis.fail_samples),
    "",
    ...buildDataLimitationSection(analysis, mode),
    "",
    ...buildPromptRequestSection(mode),
  ];
  return lines.join("\n");
};
function StockTrackingChart({ chart, item }: { chart: StockTrackingChartResponse; item?: StockTrackingItem | null }) {
  const prices = chart.prices;
  const scrollRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const scrollEl = scrollRef.current;
    if (!scrollEl) return;
    requestAnimationFrame(() => {
      scrollEl.scrollLeft = scrollEl.scrollWidth;
    });
  }, [chart.stock_code, chart.tracking_base_date, prices.length, prices[prices.length - 1]?.date]);

  if (prices.length === 0) return null;

  const width = Math.max(1240, prices.length * 10);
  const height = 500;
  const pad = { left: 58, right: 28, top: 22 };
  const priceHeight = 330;
  const volumeTop = 368;
  const volumeHeight = 92;
  const xStep = prices.length > 1 ? (width - pad.left - pad.right) / (prices.length - 1) : 0;
  const allPriceValues = prices
    .flatMap((row) => [row.high, row.low, row.open, row.close, row.ma5, row.ma10, row.ma20, row.ma60, row.ma120])
    .filter((value): value is number => value != null);
  const minPrice = Math.min(...allPriceValues);
  const maxPrice = Math.max(...allPriceValues);
  const priceRange = Math.max(1, maxPrice - minPrice);
  const maxVolume = Math.max(1, ...prices.map((row) => row.volume ?? 0));
  const candleWidth = Math.max(5, Math.min(7, xStep * 0.62));
  const x = (idx: number) => pad.left + idx * xStep;
  const y = (value: number) => pad.top + ((maxPrice - value) / priceRange) * priceHeight;
  const linePoints = (key: keyof StockTrackingChartPrice) => prices
    .map((row, idx) => (typeof row[key] === "number" ? { x: x(idx), y: y(row[key] as number) } : null))
    .filter((point): point is { x: number; y: number } => point !== null);
  const baseIdx = prices.findIndex((row) => row.date === chart.tracking_base_date);
  const baseX = baseIdx >= 0 ? x(baseIdx) : null;
  const maLines: Array<{ key: keyof StockTrackingChartPrice; label: string; color: string; width: number }> = [
    { key: "ma5", label: "MA5", color: "#111827", width: 1.7 },
    { key: "ma10", label: "MA10", color: "#ef4444", width: 1.7 },
    { key: "ma20", label: "MA20", color: "#d97706", width: 1.7 },
    { key: "ma60", label: "MA60", color: "#16a34a", width: 1.7 },
    { key: "ma120", label: "MA120", color: "#2563eb", width: 1.7 },
  ];
  const last = prices[prices.length - 1];
  const returnSummary = calculateTrackingReturnSummary(chart, item);

  return (
    <div className="stock-tracking-chart-shell stock-tracking-candle-chart">
      <div className="stock-tracking-chart-range">
        <span>{prices[0]?.date} ~ {last?.date}</span>
        <span>최근 종가 {fmtNumber(last?.close)} · 거래량 {fmtNumber(last?.volume)}</span>
      </div>
      {returnSummary && returnSummary.basePrice ? (
        <div className="stock-tracking-return-summary" aria-label="기준일 이후 수익률 요약">
          <span className="stock-tracking-return-summary-item">기준일 이후 현재수익률 <strong className={getReturnClass(returnSummary.currentReturnPct)}>{formatReturnPct(returnSummary.currentReturnPct)}</strong></span>
          <span className="stock-tracking-return-summary-item">최고수익률 <strong className={getReturnClass(returnSummary.maxReturnPct)}>{formatReturnPct(returnSummary.maxReturnPct)}</strong></span>
          <span className="stock-tracking-return-summary-item">최대하락률 <strong className={getReturnClass(returnSummary.maxDrawdownPct)}>{formatReturnPct(returnSummary.maxDrawdownPct)}</strong></span>
          <span className="stock-tracking-return-summary-item muted">경과 {returnSummary.elapsedTradingDays ?? "-"}거래일</span>
        </div>
      ) : (
        <div className="stock-tracking-return-summary muted">수익률 요약을 계산할 수 없습니다.</div>
      )}
      <div className="stock-tracking-chart-scroll" ref={scrollRef}>
        <svg className="stock-tracking-chart-inner" viewBox={`0 0 ${width} ${height}`} role="img" aria-label="종목 트래킹 캔들 차트">
          {[0, 1, 2, 3, 4].map((tick) => {
            const gy = pad.top + tick * (priceHeight / 4);
            const value = maxPrice - tick * (priceRange / 4);
            return (
              <g key={`grid-${tick}`}>
                <line x1={pad.left} x2={width - pad.right} y1={gy} y2={gy} className="chart-grid-line" />
                <text x={pad.left - 8} y={gy + 4} textAnchor="end" className="chart-axis-text">{Math.round(value).toLocaleString("ko-KR")}</text>
              </g>
            );
          })}
          {prices.map((row, idx) => {
            const cx = x(idx);
            const open = row.open ?? row.close ?? 0;
            const close = row.close ?? row.open ?? 0;
            const high = row.high ?? Math.max(open, close);
            const low = row.low ?? Math.min(open, close);
            const rising = close >= open;
            const colorClass = rising ? "rising" : "falling";
            const bodyY = Math.min(y(open), y(close));
            const bodyHeight = Math.max(2, Math.abs(y(open) - y(close)));
            const barHeight = ((row.volume ?? 0) / maxVolume) * volumeHeight;
            return (
              <g key={`candle-${row.date}`}>
                <rect x={cx - candleWidth / 2} y={volumeTop + volumeHeight - barHeight} width={candleWidth} height={barHeight} className={`chart-volume-bar ${colorClass}`} />
                <line x1={cx} x2={cx} y1={y(high)} y2={y(low)} className={`chart-candle-wick ${colorClass}`} />
                <rect x={cx - candleWidth / 2} y={bodyY} width={candleWidth} height={bodyHeight} rx={1} className={`chart-candle-body ${colorClass}`}>
                  <title>{`${row.date}\n시가 ${fmtNumber(row.open)}\n고가 ${fmtNumber(row.high)}\n저가 ${fmtNumber(row.low)}\n종가 ${fmtNumber(row.close)}\n거래량 ${fmtNumber(row.volume)}`}</title>
                </rect>
              </g>
            );
          })}
          {maLines.map((line) => {
            const points = linePoints(line.key);
            return points.length > 1 ? <path key={line.key} d={pathFromPoints(points)} fill="none" stroke={line.color} strokeWidth={line.width} strokeLinecap="round" strokeLinejoin="round" /> : null;
          })}
          {baseX != null ? (
            <g>
              <line x1={baseX} x2={baseX} y1={pad.top} y2={volumeTop + volumeHeight} className="chart-base-line" />
              <text x={baseX + 6} y={pad.top + 16} className="chart-base-label">기준일</text>
            </g>
          ) : null}
          {[0, Math.floor(prices.length / 2), prices.length - 1].map((idx) => (
            <text key={`date-${idx}`} x={x(idx)} y={height - 8} textAnchor={idx === 0 ? "start" : idx === prices.length - 1 ? "end" : "middle"} className="chart-axis-text">{prices[idx]?.date}</text>
          ))}
          <text x={pad.left} y={volumeTop - 10} className="chart-axis-text">거래량</text>
        </svg>
      </div>
      <div className="stock-tracking-chart-legend">
        <span style={{ "--legend-color": "#ef4444" } as React.CSSProperties}>상승캔들</span>
        <span style={{ "--legend-color": "#2563eb" } as React.CSSProperties}>하락캔들</span>
        {maLines.map((line) => <span key={line.key} style={{ "--legend-color": line.color } as React.CSSProperties}>{line.label}</span>)}
        <span style={{ "--legend-color": "#94a3b8" } as React.CSSProperties}>거래량</span>
      </div>
    </div>
  );
}
const copyTextToClipboard = async (text: string) => {
  if (navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(text);
    return;
  }
  const textarea = document.createElement("textarea");
  textarea.value = text;
  textarea.setAttribute("readonly", "true");
  textarea.style.position = "fixed";
  textarea.style.left = "-9999px";
  document.body.appendChild(textarea);
  textarea.select();
  try {
    document.execCommand("copy");
  } finally {
    document.body.removeChild(textarea);
  }
};

function AnalysisBaseMetricTable({ analysis }: { analysis: StockTrackingGroupAnalysis }) {
  const summary = analysis.base_metric_summary;
  const avg = summary?.avg ?? {};
  const successAvg = summary?.success_avg ?? {};
  const failAvg = summary?.fail_avg ?? {};
  const diff = summary?.diff ?? {};
  return (
    <div className="stock-tracking-analysis-metrics">
      <div className="stock-tracking-card-title"><h4>성공/실패 기준일 지표 비교</h4><span>계산 가능 {analysis.base_metric_calculated_count ?? 0}건 기준</span></div>
      <div className="table-shell stock-tracking-analysis-metric-table-shell">
        <table className="data-table compact-table stock-tracking-analysis-metric-table">
          <thead>
            <tr><th>지표</th><th>전체 평균</th><th>성공 평균</th><th>실패 평균</th><th>차이</th><th>해석</th></tr>
          </thead>
          <tbody>
            {BASE_METRIC_DEFINITIONS.map((metric) => {
              const key = metric.key;
              return (
                <tr key={key}>
                  <td><strong>{metric.label}</strong></td>
                  <td className={getBaseMetricClass(avg[key])}>{formatBaseMetricValue(key, avg[key])}</td>
                  <td className={getBaseMetricClass(successAvg[key])}>{formatBaseMetricValue(key, successAvg[key])}</td>
                  <td className={getBaseMetricClass(failAvg[key])}>{formatBaseMetricValue(key, failAvg[key])}</td>
                  <td className={getBaseMetricClass(diff[key])}>{formatBaseMetricDiff(key, diff[key])}</td>
                  <td><span className="stock-tracking-analysis-metric-interpretation">{getBaseMetricInterpretation(key, successAvg[key], failAvg[key], diff[key])}</span></td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function AnalysisSampleList({ title, samples }: { title: string; samples: StockTrackingGroupAnalysisSample[] }) {
  return (
    <div className="stock-tracking-analysis-sample-card">
      <h4>{title}</h4>
      {samples.length === 0 ? (
        <p className="stock-tracking-analysis-sample-empty">표시할 샘플이 없습니다.</p>
      ) : (
        <div className="stock-tracking-analysis-sample-list">
          {samples.map((sample) => (
            <div className="stock-tracking-analysis-sample-row" key={sample.item_id}>
              <div>
                <strong>{sample.stock_name || sample.stock_code || "-"}</strong>
                <span>{sample.stock_code || "-"} · {sample.tracking_base_date}</span>
              </div>
              <div className="stock-tracking-analysis-sample-metrics">
                <span className={getReturnClass(sample.current_return_pct)}>현재 {formatAnalysisReturn(sample.current_return_pct)}</span>
                <span className={getReturnClass(sample.max_return_pct)}>최고 {formatAnalysisReturn(sample.max_return_pct)}</span>
                <span className={getReturnClass(sample.max_drawdown_pct)}>하락 {formatAnalysisReturn(sample.max_drawdown_pct)}</span>
                <span className={getBaseMetricClass(sample.close_vs_ma20_pct)}>20일 {formatBaseMetricValue("close_vs_ma20_pct", sample.close_vs_ma20_pct)}</span>
                <span className={getBaseMetricClass(sample.recent_5d_return_pct)}>5일 {formatBaseMetricValue("recent_5d_return_pct", sample.recent_5d_return_pct)}</span>
                <span>거래대금 {formatBaseMetricValue("trading_value_ratio_20", sample.trading_value_ratio_20)}</span>
                <span>경과 {sample.elapsed_trading_days ?? "-"}일</span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function StockTrackingPage() {
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState<"groups" | "items" | "analysis">("items");
  const [groups, setGroups] = useState<StockTrackingGroup[]>([]);
  const [items, setItems] = useState<StockTrackingItem[]>([]);
  const [itemTotal, setItemTotal] = useState(0);
  const [itemPage, setItemPage] = useState(1);
  const [selectedItem, setSelectedItem] = useState<StockTrackingItem | null>(null);
  const [checkedItemIds, setCheckedItemIds] = useState<Set<number>>(() => new Set());
  const [editingGroup, setEditingGroup] = useState<StockTrackingGroup | null>(null);
  const [groupModalOpen, setGroupModalOpen] = useState(false);
  const [groupForm, setGroupForm] = useState(emptyGroupForm);
  const [filters, setFilters] = useState({ group_id: "", status: "", price_status: "", keyword: "" });
  const [reviewStatus, setReviewStatus] = useState<StockTrackingStatus>("TRACKING");
  const [reviewNote, setReviewNote] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [collecting, setCollecting] = useState(false);
  const [fullRefreshTarget, setFullRefreshTarget] = useState<TrackingFullRefreshTarget | null>(null);
  const [fullRefreshMenuOpen, setFullRefreshMenuOpen] = useState(false);
  const fullRefreshMenuRef = useRef<HTMLDivElement | null>(null);
  const [chartLoading, setChartLoading] = useState(false);
  const [chart, setChart] = useState<StockTrackingChartResponse | null>(null);
  const [imageRows, setImageRows] = useState<StockTrackingImage[]>([]);
  const [appImageRows, setAppImageRows] = useState<AppImage[]>([]);
  const [imageModalOpen, setImageModalOpen] = useState(false);
  const [previewImage, setPreviewImage] = useState<StockTrackingImage | null>(null);
  const [previewAppImage, setPreviewAppImage] = useState<AppImage | null>(null);
  const [imageUploading, setImageUploading] = useState(false);
  const [imageForm, setImageForm] = useState(emptyImageForm);
  const [analysisRows, setAnalysisRows] = useState<StockTrackingGroupAnalysis[]>([]);
  const [selectedAnalysis, setSelectedAnalysis] = useState<StockTrackingGroupAnalysis | null>(null);
  const [analysisLoading, setAnalysisLoading] = useState(false);

  const activeGroups = useMemo(() => groups.filter((group) => group.is_active === 1), [groups]);
  const trackingCount = useMemo(() => items.filter((item) => item.status === "TRACKING").length, [items]);
  const completedCount = useMemo(() => items.filter((item) => item.status === "SUCCESS" || item.status === "FAIL").length, [items]);
  const groupStatusCounts = useMemo(() => {
    const map = new Map<number, { success: number; fail: number; hold: number }>();
    for (const item of items) {
      const current = map.get(item.group_id) ?? { success: 0, fail: 0, hold: 0 };
      if (item.status === "SUCCESS") current.success += 1;
      if (item.status === "FAIL") current.fail += 1;
      if (item.status === "HOLD") current.hold += 1;
      map.set(item.group_id, current);
    }
    return map;
  }, [items]);
  const collectableItems = useMemo(() => items.filter(canCollectItem), [items]);
  const checkedCollectableItems = useMemo(() => collectableItems.filter((item) => checkedItemIds.has(item.id)), [checkedItemIds, collectableItems]);
  const allCollectableChecked = collectableItems.length > 0 && checkedCollectableItems.length === collectableItems.length;
  const selectedCanCollect = Boolean(selectedItem && canCollectItem(selectedItem));
  const itemTotalPages = Math.max(1, Math.ceil(itemTotal / ITEM_PAGE_SIZE));
  const itemPageStart = itemTotal === 0 ? 0 : (itemPage - 1) * ITEM_PAGE_SIZE + 1;
  const itemPageEnd = Math.min(itemTotal, itemPage * ITEM_PAGE_SIZE);
  const canCopyGptPrompt = Boolean(selectedAnalysis && selectedAnalysis.total_count > 0);

  const analysisCopyNotice = selectedAnalysis
    ? selectedAnalysis.total_count === 0
      ? "그룹에 등록된 종목이 없어 분석 요청문을 만들 수 없습니다."
      : selectedAnalysis.success_count > 0 && selectedAnalysis.fail_count > 0
        ? "성공/실패 샘플을 비교하는 GPT 분석 요청문을 복사합니다."
        : selectedAnalysis.success_count === 0 && selectedAnalysis.fail_count > 0
          ? "성공 샘플이 없어 실패 위험 신호 중심의 요청문을 복사합니다."
          : selectedAnalysis.success_count > 0 && selectedAnalysis.fail_count === 0
            ? "실패 샘플이 없어 성공 긍정 신호 중심의 요청문을 복사합니다."
            : "성공/실패 판단 데이터가 없어 관찰 체크리스트 중심의 요청문을 복사합니다."
    : "그룹을 선택하면 GPT 분석 요청문을 복사할 수 있습니다.";

  const copyGptPrompt = async () => {
    if (!selectedAnalysis || !canCopyGptPrompt) return;
    try {
      await copyTextToClipboard(buildGroupAnalysisGptPrompt(selectedAnalysis));
      setMessage("GPT 분석 요청문을 복사했습니다.");
    } catch {
      setError("분석 요청문 복사에 실패했습니다. 다시 시도해 주세요.");
    }
  };

  const analysisSummary = useMemo(() => {
    const totalGroups = analysisRows.length;
    const totalItems = analysisRows.reduce((sum, row) => sum + row.total_count, 0);
    const completedItems = analysisRows.reduce((sum, row) => sum + row.completed_count, 0);
    const successCount = analysisRows.reduce((sum, row) => sum + row.success_count, 0);
    const failCount = analysisRows.reduce((sum, row) => sum + row.fail_count, 0);
    const denominator = successCount + failCount;
    return {
      totalGroups,
      totalItems,
      completedItems,
      successRate: denominator > 0 ? (successCount / denominator) * 100 : null,
    };
  }, [analysisRows]);

  const loadGroups = async () => {
    const rows = await repositories.stockTracking.listGroups();
    setGroups(rows);
  };

  const loadAnalysis = async () => {
    setAnalysisLoading(true);
    try {
      const response = await repositories.stockTracking.listGroupAnalysis({ active_only: true });
      const rows: StockTrackingGroupAnalysis[] = response.items;
      setAnalysisRows(rows);
      setSelectedAnalysis((prev) => prev ? rows.find((row) => row.group_id === prev.group_id) ?? rows[0] ?? null : rows[0] ?? null);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setAnalysisLoading(false);
    }
  };

  const loadItems = async (page = itemPage) => {
    const nextPage = Math.max(1, page);
    const response = await repositories.stockTracking.listItems({
      group_id: filters.group_id ? Number(filters.group_id) : undefined,
      status: filters.status as StockTrackingStatus | "",
      price_status: filters.price_status as StockTrackingPriceStatus | "",
      keyword: filters.keyword.trim() || undefined,
      limit: ITEM_PAGE_SIZE,
      offset: (nextPage - 1) * ITEM_PAGE_SIZE,
    });
    setItemPage(nextPage);
    setItemTotal(response.total);
    setItems(response.items);
    setCheckedItemIds((prev) => new Set(response.items.filter((item) => prev.has(item.id) && canCollectItem(item)).map((item) => item.id)));
    if (selectedItem) {
      const next = response.items.find((item) => item.id === selectedItem.id) ?? null;
      setSelectedItem(next);
      if (!next) {
        setChart(null);
        setImageRows([]);
      }
    }
  };

  useEffect(() => {
    setLoading(true);
    Promise.all([loadGroups(), loadItems()])
      .catch((err) => setError(err instanceof Error ? err.message : String(err)))
      .finally(() => setLoading(false));
  }, []);

  const resetGroupForm = () => {
    setEditingGroup(null);
    setGroupForm(emptyGroupForm);
  };

  const openCreateGroup = () => {
    resetGroupForm();
    setGroupModalOpen(true);
  };

  const editGroup = (group: StockTrackingGroup) => {
    setEditingGroup(group);
    setGroupForm({
      name: group.name,
      description: group.description ?? "",
      success_rule_note: group.success_rule_note ?? "",
      fail_rule_note: group.fail_rule_note ?? "",
      observation_note: group.observation_note ?? "",
      is_active: group.is_active,
    });
    setGroupModalOpen(true);
  };

  const saveGroup = async () => {
    setError("");
    if (!groupForm.name.trim()) {
      setError("그룹명을 입력해 주세요.");
      return;
    }
    const payload = { ...groupForm, name: groupForm.name.trim() };
    if (editingGroup) await repositories.stockTracking.updateGroup(editingGroup.id, payload);
    else await repositories.stockTracking.createGroup(payload);
    setMessage(editingGroup ? "종목트래킹 그룹을 수정했습니다." : "종목트래킹 그룹을 등록했습니다.");
    setGroupModalOpen(false);
    resetGroupForm();
    await loadGroups();
  };

  const deleteGroup = async (group: StockTrackingGroup) => {
    if (!window.confirm("연결된 트래킹 종목이 없는 경우에만 그룹이 삭제됩니다. 삭제할까요?")) return;
    try {
      await repositories.stockTracking.deleteGroup(group.id);
      setMessage("종목트래킹 그룹을 삭제했습니다.");
      await loadGroups();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  };

  const loadChart = async (itemId: number) => {
    setChartLoading(true);
    try {
      const response = await repositories.stockTracking.getChart(itemId);
      setChart(response);
    } catch (err) {
      setChart(null);
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setChartLoading(false);
    }
  };

  const loadImages = async (itemId: number) => {
    try {
      const [legacyResponse, appResponse] = await Promise.all([
        repositories.stockTracking.listImages(itemId),
        repositories.images.listImages({ domain: "stock_tracking", owner_type: "stock_tracking", owner_id: itemId }),
      ]);
      setImageRows(legacyResponse.items);
      setAppImageRows(appResponse.items);
    } catch (err) {
      setImageRows([]);
      setAppImageRows([]);
      setError(err instanceof Error ? err.message : String(err));
    }
  };

  const resetImageForm = () => {
    setImageForm({ ...emptyImageForm });
  };

  const openImageModal = () => {
    resetImageForm();
    setImageModalOpen(true);
  };

  const uploadImage = async () => {
    if (!selectedItem) return;
    if (!imageForm.file) {
      setError("등록할 이미지 파일을 선택해 주세요.");
      return;
    }
    setError("");
    setImageUploading(true);
    try {
      const imageTypeLabel = getImageTypeLabel(imageForm.image_type);
      const caption = imageForm.caption.trim();
      const row = await repositories.images.uploadImage({
        domain: "stock_tracking",
        owner_type: "stock_tracking",
        owner_id: selectedItem.id,
        file: imageForm.file,
        description: caption ? imageTypeLabel + " - " + caption : imageTypeLabel,
      });
      setAppImageRows((prev) => [row, ...prev]);
      setImageModalOpen(false);
      resetImageForm();
      setMessage("첨부 이미지를 등록했습니다.");
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setImageUploading(false);
    }
  };

  const deleteImage = async (image: StockTrackingImage) => {
    if (!window.confirm("이 첨부 이미지를 삭제할까요?")) return;
    try {
      await repositories.stockTracking.deleteImage(image.id);
      setImageRows((prev) => prev.filter((row) => row.id !== image.id));
      if (previewImage?.id === image.id) setPreviewImage(null);
      setMessage("첨부 이미지를 삭제했습니다.");
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  };

  const deleteAppImage = async (image: AppImage) => {
    if (!window.confirm("이 첨부 이미지를 삭제할까요?")) return;
    try {
      await repositories.images.deleteImage(image.id);
      setAppImageRows((prev) => prev.filter((row) => row.id !== image.id));
      if (previewAppImage?.id === image.id) setPreviewAppImage(null);
      setMessage("첨부 이미지를 삭제했습니다.");
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  };

  const closeDetail = () => {
    setSelectedItem(null);
    setChart(null);
    setImageRows([]);
    setAppImageRows([]);
    setPreviewImage(null);
    setPreviewAppImage(null);
    setImageModalOpen(false);
  };

  useEffect(() => {
    if (!selectedItem) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") closeDetail();
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [selectedItem]);

  const selectItem = (item: StockTrackingItem) => {
    setSelectedItem(item);
    setReviewStatus(item.status);
    setReviewNote(item.review_note ?? "");
    void loadChart(item.id);
    void loadImages(item.id);
  };

  const toggleCheckedItem = (item: StockTrackingItem) => {
    if (!canCollectItem(item)) return;
    setCheckedItemIds((prev) => {
      const next = new Set(prev);
      if (next.has(item.id)) next.delete(item.id);
      else next.add(item.id);
      return next;
    });
  };

  const toggleAllCheckedItems = () => {
    setCheckedItemIds((prev) => {
      if (allCollectableChecked) return new Set();
      const next = new Set(prev);
      for (const item of collectableItems) next.add(item.id);
      return next;
    });
  };

  const runItemSearch = async () => {
    setCheckedItemIds(new Set());
    await loadItems(1);
  };

  const moveItemPage = async (page: number) => {
    if (page < 1 || page > itemTotalPages || page === itemPage) return;
    setCheckedItemIds(new Set());
    await loadItems(page);
  };

  const refreshAfterCollect = async (response: CollectStockTrackingPricesResponse, mode: TrackingCollectionMode, selectedId?: number) => {
    setMessage(getCollectResultMessage(response, mode));
    setCheckedItemIds(new Set());
    await loadItems();
    await loadGroups();
    if (selectedId) {
      const updated = await repositories.stockTracking.getItem(selectedId);
      setSelectedItem(updated);
      await loadChart(selectedId);
      await loadImages(selectedId);
    }
  };

  const getCollectTargets = (scope: TrackingCollectionScope) => scope === "checked"
    ? checkedCollectableItems
    : scope === "detail"
      ? (selectedItem && selectedCanCollect ? [selectedItem] : [])
      : collectableItems;

  const openFullRefreshConfirm = (target: TrackingFullRefreshTarget) => {
    const targetItems = getCollectTargets(target);
    if (targetItems.length === 0) {
      setFullRefreshMenuOpen(false);
      setError(target === "checked" ? "선택한 종목이 없습니다." : "갱신할 트래킹 종목이 없습니다.");
      return;
    }
    setError("");
    setFullRefreshMenuOpen(false);
    setFullRefreshTarget(target);
  };

  const collectPrices = async (scope: TrackingCollectionScope, collectionMode: TrackingCollectionMode = "recent") => {
    const targetItems = getCollectTargets(scope);
    if (targetItems.length === 0) {
      setError(scope === "all" ? "갱신할 트래킹 종목이 없습니다." : scope === "checked" ? "선택한 종목이 없습니다." : "가격정보를 갱신할 종목을 선택해 주세요.");
      return;
    }
    setError("");
    setMessage("");
    setCollecting(true);
    const targetIds = new Set(targetItems.map((item) => item.id));
    setItems((prev) => prev.map((item) => targetIds.has(item.id) ? { ...item, price_status: "COLLECTING" } : item));
    try {
      const isSelectedScope = scope === "checked" || scope === "detail";
      const action = collectionMode === "full"
        ? (isSelectedScope ? "selected_full" : "all_full")
        : (isSelectedScope ? "selected_recent_7d" : "all_recent_7d");
      const mode = collectionMode === "full" ? "tracking_full_refresh" : "tracking_incremental_overlap";
      const response = await repositories.stockTracking.collectPrices({
        item_ids: isSelectedScope ? Array.from(targetIds) : [],
        overlap_days: 7,
        force_full_refresh: collectionMode === "full",
        action,
        mode,
      });
      console.info("[TRACKING COLLECT]", {
        action: response.action,
        selectedCount: response.selected_count,
        targetCount: response.target_count,
        mode: response.mode,
        totalPages: response.total_pages,
        totalCollected: response.total_collected,
        totalSaved: response.total_saved,
        totalMs: response.total_ms,
      });
      await refreshAfterCollect(response, collectionMode, selectedItem && targetIds.has(selectedItem.id) ? selectedItem.id : undefined);
      if (collectionMode === "full") setFullRefreshTarget(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setCollecting(false);
    }
  };

  useEffect(() => {
    if (!fullRefreshMenuOpen) return;
    const handlePointerDown = (event: MouseEvent) => {
      if (!fullRefreshMenuRef.current?.contains(event.target as Node)) setFullRefreshMenuOpen(false);
    };
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") setFullRefreshMenuOpen(false);
    };
    document.addEventListener("mousedown", handlePointerDown);
    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("mousedown", handlePointerDown);
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [fullRefreshMenuOpen]);
  const saveReview = async () => {
    if (!selectedItem) return;
    const updated = await repositories.stockTracking.updateReview(selectedItem.id, { status: reviewStatus, review_note: reviewNote });
    setSelectedItem(updated);
    setMessage("트래킹 판단 메모를 저장했습니다.");
    await loadItems();
    await loadGroups();
  };

  const deleteItem = async (item: StockTrackingItem) => {
    if (!window.confirm("이 트래킹 종목을 삭제합니다. 트래킹 등록 정보, 메모, 이미지, 가격 수집 대상 정보가 삭제됩니다. 다른 기능에서 함께 사용하는 가격 데이터는 삭제되지 않습니다.")) return;
    if (selectedItem?.id === item.id && appImageRows.length > 0) {
      await Promise.all(appImageRows.map((image) => repositories.images.deleteImage(image.id)));
    }
    await repositories.stockTracking.deleteItem(item.id);
    setCheckedItemIds((prev) => {
      const next = new Set(prev);
      next.delete(item.id);
      return next;
    });
    if (selectedItem?.id === item.id) {
      setSelectedItem(null);
      setChart(null);
      setImageRows([]);
      setAppImageRows([]);
      setPreviewAppImage(null);
    }
    setMessage("트래킹 종목을 삭제했습니다.");
    await loadItems();
    await loadGroups();
  };

  return (
    <div className="stock-tracking-page space-y-4">
      <PageHeader
        title="종목 트래킹"
        description="조건검색 후보를 그룹별로 추적하고 성공/실패 패턴을 복기합니다."
        action={(
          <div className="stock-tracking-kpis">
            <span>그룹 {groups.length}</span>
            <span>트래킹중 {trackingCount}</span>
            <span>판단완료 {completedCount}</span>
          </div>
        )}
      />
      {message ? <div className="inline-result inline-success">{message}</div> : null}
      {error ? <div className="inline-result inline-error">{error}</div> : null}
      <SectionCard title="" className="stock-tracking-tabs-card market-theme-tabs-card">
        <div className="gpt-domain-tabs stock-tracking-tabs market-theme-primary-tabs">
          <button type="button" className={`gpt-domain-tab stock-tracking-tab market-theme-primary-tab ${activeTab === "groups" ? "active" : ""}`} onClick={() => setActiveTab("groups")}>종목트래킹 그룹</button>
          <button type="button" className={`gpt-domain-tab stock-tracking-tab market-theme-primary-tab ${activeTab === "items" ? "active" : ""}`} onClick={() => { setActiveTab("items"); void loadItems(itemPage); }}>종목트래킹</button>
          <button type="button" className={`gpt-domain-tab stock-tracking-tab market-theme-primary-tab ${activeTab === "analysis" ? "active" : ""}`} onClick={() => { setActiveTab("analysis"); void loadAnalysis(); }}>그룹 분석</button>
        </div>
      </SectionCard>

      {activeTab === "groups" ? (
        <SectionCard className="stock-tracking-group-section">
          <div className="stock-tracking-section-head">
            <div>
              <h3 className="section-title m-0">종목트래킹 그룹</h3>
              <p>조건검색 후보를 연구 목적별 그룹으로 관리합니다.</p>
            </div>
            <button type="button" className="btn btn-primary" onClick={openCreateGroup}>+ 그룹 등록</button>
          </div>
          {groups.length === 0 ? (
            <div className="stock-tracking-empty-state">
              <strong>등록된 종목트래킹 그룹이 없습니다.</strong>
              <p>먼저 15% 급등, 500억 이상 거래, 20일선 돌파처럼 관찰 목적에 맞는 그룹을 등록해 주세요.</p>
              <button type="button" className="btn btn-primary" onClick={openCreateGroup}>그룹 등록</button>
            </div>
          ) : (
            <div className="table-shell">
              <table className="data-table compact-table stock-tracking-group-table">
                <thead>
                  <tr><th>그룹명</th><th>설명</th><th>활성</th><th>트래킹중</th><th>성공</th><th>실패</th><th>보류</th><th>관리</th></tr>
                </thead>
                <tbody>
                  {groups.map((group) => {
                    const counts = groupStatusCounts.get(group.id) ?? { success: 0, fail: 0, hold: 0 };
                    return (
                      <tr key={group.id}>
                        <td><strong>{group.name}</strong></td>
                        <td className="stock-tracking-muted-cell">{group.description || "-"}</td>
                        <td>{group.is_active ? "활성" : "비활성"}</td>
                        <td>{group.tracking_count}</td>
                        <td>{counts.success}</td>
                        <td>{counts.fail}</td>
                        <td>{counts.hold}</td>
                        <td>
                          <div className="stock-tracking-row-actions">
                            <button type="button" className="btn btn-secondary btn-table-sm" onClick={() => editGroup(group)}>수정</button>
                            <button type="button" className="btn btn-danger btn-table-sm" onClick={() => void deleteGroup(group)}>삭제</button>
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </SectionCard>
      ) : activeTab === "analysis" ? (
        <div className="stock-tracking-analysis">
          <SectionCard className="stock-tracking-analysis-section">
            <div className="stock-tracking-section-head">
              <div>
                <h3 className="section-title m-0">그룹 분석</h3>
                <p>그룹별 성공/실패 결과와 기준일 이후 수익률 흐름을 비교합니다.</p>
              </div>
              <button type="button" className="btn btn-secondary" disabled={analysisLoading} onClick={() => void loadAnalysis()}>{analysisLoading ? "분석 중..." : "분석 새로고침"}</button>
            </div>
            <div className="stock-tracking-analysis-summary">
              <div className="stock-tracking-analysis-card"><span>전체 그룹</span><strong>{analysisSummary.totalGroups}</strong></div>
              <div className="stock-tracking-analysis-card"><span>전체 트래킹 종목</span><strong>{analysisSummary.totalItems}</strong></div>
              <div className="stock-tracking-analysis-card"><span>판단완료 종목</span><strong>{analysisSummary.completedItems}</strong></div>
              <div className="stock-tracking-analysis-card"><span>평균 성공률</span><strong>{formatPlainPct(analysisSummary.successRate)}</strong></div>
            </div>
            <div className="table-shell stock-tracking-analysis-table-shell">
              <table className="data-table compact-table stock-tracking-analysis-table">
                <thead>
                  <tr><th>그룹명</th><th>전체</th><th>트래킹중</th><th>보류</th><th>성공</th><th>실패</th><th>제외</th><th>성공률</th><th>평균 현재</th><th>평균 최고</th><th>평균 최대하락</th><th>계산</th></tr>
                </thead>
                <tbody>
                  {analysisRows.map((row) => (
                    <tr key={row.group_id} className={selectedAnalysis?.group_id === row.group_id ? "stock-tracking-analysis-row-selected selected" : ""} onClick={() => setSelectedAnalysis(row)}>
                      <td><strong>{row.group_name}</strong></td>
                      <td>{row.total_count}</td>
                      <td>{row.tracking_count}</td>
                      <td>{row.hold_count}</td>
                      <td><span className="analysis-count-badge success">{row.success_count}</span></td>
                      <td><span className="analysis-count-badge fail">{row.fail_count}</span></td>
                      <td>{row.excluded_count}</td>
                      <td><span>{formatPlainPct(row.success_rate)}</span>{getSuccessRateReliabilityText(row.completed_count) ? <small className="stock-tracking-analysis-reliability">{getSuccessRateReliabilityText(row.completed_count)}</small> : null}</td>
                      <td className={getReturnClass(row.avg_current_return_pct)}>{formatAnalysisReturn(row.avg_current_return_pct)}</td>
                      <td className={getReturnClass(row.avg_max_return_pct)}>{formatAnalysisReturn(row.avg_max_return_pct)}</td>
                      <td className={getReturnClass(row.avg_max_drawdown_pct)}>{formatAnalysisReturn(row.avg_max_drawdown_pct)}</td>
                      <td>{row.return_calculated_count}</td>
                    </tr>
                  ))}
                  {analysisRows.length === 0 ? <tr><td colSpan={12}><div className="stock-tracking-empty-state compact"><strong>분석할 그룹 데이터가 없습니다.</strong><p>종목트래킹 그룹에 종목을 등록하고 가격정보를 갱신하면 분석 결과가 표시됩니다.</p></div></td></tr> : null}
                </tbody>
              </table>
            </div>
          </SectionCard>
          {selectedAnalysis ? (
            <SectionCard className="stock-tracking-analysis-detail">
              <div className="stock-tracking-section-head stock-tracking-analysis-detail-head">
                <div>
                  <h3 className="section-title m-0">{selectedAnalysis.group_name}</h3>
                  <p>성공 샘플과 실패 샘플의 평균 수익률 차이를 비교합니다.</p>
                </div>
                <button type="button" className="btn btn-secondary" disabled={!canCopyGptPrompt} onClick={() => void copyGptPrompt()}>GPT 분석 복사</button>
              </div>
              <p className={`stock-tracking-analysis-copy-notice ${canCopyGptPrompt ? "" : "disabled"}`}>{analysisCopyNotice}</p>
              <div className="stock-tracking-analysis-compare">
                <div><span>성공 평균 현재 / 실패 평균 현재</span><strong><b className={getReturnClass(selectedAnalysis.success_avg_current_return_pct)}>{formatAnalysisReturn(selectedAnalysis.success_avg_current_return_pct)}</b> / <b className={getReturnClass(selectedAnalysis.fail_avg_current_return_pct)}>{formatAnalysisReturn(selectedAnalysis.fail_avg_current_return_pct)}</b></strong></div>
                <div><span>성공 평균 최고 / 실패 평균 최고</span><strong><b className={getReturnClass(selectedAnalysis.success_avg_max_return_pct)}>{formatAnalysisReturn(selectedAnalysis.success_avg_max_return_pct)}</b> / <b className={getReturnClass(selectedAnalysis.fail_avg_max_return_pct)}>{formatAnalysisReturn(selectedAnalysis.fail_avg_max_return_pct)}</b></strong></div>
                <div><span>성공 평균 최대하락 / 실패 평균 최대하락</span><strong><b className={getReturnClass(selectedAnalysis.success_avg_max_drawdown_pct)}>{formatAnalysisReturn(selectedAnalysis.success_avg_max_drawdown_pct)}</b> / <b className={getReturnClass(selectedAnalysis.fail_avg_max_drawdown_pct)}>{formatAnalysisReturn(selectedAnalysis.fail_avg_max_drawdown_pct)}</b></strong></div>
              </div>
              <p className="stock-tracking-analysis-note">{selectedAnalysis.diff_avg_max_return_pct != null && selectedAnalysis.diff_avg_max_return_pct > 0 ? "성공 샘플은 실패 샘플보다 평균 최고수익률이 높게 나타납니다." : "성공/실패 샘플 차이는 누적 데이터가 늘어나면 더 선명해집니다."}</p>
              <AnalysisBaseMetricTable analysis={selectedAnalysis} />
              <div className="stock-tracking-analysis-samples">
                <AnalysisSampleList title="성공 샘플" samples={selectedAnalysis.success_samples} />
                <AnalysisSampleList title="실패 샘플" samples={selectedAnalysis.fail_samples} />
              </div>
            </SectionCard>
          ) : null}
        </div>
      ) : (
        <div className="stock-tracking-item-layout">
          <SectionCard className="stock-tracking-list-card">
            <div className="stock-tracking-list-head">
              <h3 className="section-title m-0">트래킹 목록</h3>
              <div className="stock-tracking-list-actions">
                <button type="button" className="btn stock-tracking-collect-button stock-tracking-primary-collect-button" disabled={collecting} onClick={() => void collectPrices("all", "recent")}>{collecting ? "수집 중..." : "목록 최근7일수집"}</button>
                <button type="button" className="btn stock-tracking-collect-button" disabled={checkedCollectableItems.length === 0 || collecting} title={checkedCollectableItems.length === 0 ? "체크박스로 수집할 종목을 선택해 주세요." : "체크한 종목만 최근 7일 기준으로 수집합니다."} onClick={() => void collectPrices("checked", "recent")}>{collecting ? "수집 중..." : checkedCollectableItems.length > 0 ? `선택 ${checkedCollectableItems.length}건 최근7일수집` : "선택 최근7일수집"}</button>
                <div className="stock-tracking-full-refresh-menu" ref={fullRefreshMenuRef}>
                  <button type="button" className="btn stock-tracking-full-refresh-button" disabled={collecting} title="전체수집은 target 시작일부터 오늘까지 다시 upsert합니다." aria-haspopup="menu" aria-expanded={fullRefreshMenuOpen} onClick={() => setFullRefreshMenuOpen((prev) => !prev)}>전체수집 ▾</button>
                  {fullRefreshMenuOpen ? (
                    <div className="stock-tracking-full-refresh-menu-list" role="menu">
                      <button type="button" role="menuitem" onClick={() => openFullRefreshConfirm("all")}>목록 전체수집</button>
                      <button type="button" role="menuitem" disabled={checkedCollectableItems.length === 0} title={checkedCollectableItems.length === 0 ? "체크박스로 수집할 종목을 선택해 주세요." : "체크한 종목만 전체 기간으로 다시 수집합니다."} onClick={() => openFullRefreshConfirm("checked")}>{checkedCollectableItems.length > 0 ? `선택 ${checkedCollectableItems.length}건 전체수집` : "선택 전체수집"}</button>
                    </div>
                  ) : null}
                </div>
              </div>
            </div>
            <div className="stock-tracking-filter-row">
              <select className="select-control" value={filters.group_id} onChange={(event) => setFilters((prev) => ({ ...prev, group_id: event.target.value }))}><option value="">그룹 전체</option>{activeGroups.map((group) => <option key={group.id} value={group.id}>{group.name}</option>)}</select>
              <select className="select-control" value={filters.status} onChange={(event) => setFilters((prev) => ({ ...prev, status: event.target.value }))}><option value="">상태 전체</option>{Object.entries(STATUS_LABELS).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select>
              <select className="select-control" value={filters.price_status} onChange={(event) => setFilters((prev) => ({ ...prev, price_status: event.target.value }))}><option value="">가격상태 전체</option>{Object.entries(PRICE_STATUS_LABELS).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select>
              <input className="input-control" placeholder="종목명/코드 검색" value={filters.keyword} onChange={(event) => setFilters((prev) => ({ ...prev, keyword: event.target.value }))} />
              <button type="button" className="btn btn-secondary" onClick={() => void runItemSearch()}>조회</button>
            </div>
            {loading ? <p className="text-muted">조회 중...</p> : null}
            <div className="table-shell stock-tracking-list-shell">
              <table className="data-table compact-table stock-tracking-table">
                <thead><tr><th className="stock-tracking-check-col"><input type="checkbox" className="stock-tracking-checkbox" aria-label="갱신 가능 종목 전체 선택" checked={allCollectableChecked} disabled={collectableItems.length === 0} onChange={toggleAllCheckedItems} onClick={(event) => event.stopPropagation()} /></th><th>상태</th><th>기준일</th><th>종목</th><th>그룹</th><th className="text-right">트래킹 등락률</th><th>가격상태</th><th>판단일</th></tr></thead>
                <tbody>
                  {items.map((item) => (
                    <tr key={item.id} className={selectedItem?.id === item.id ? "stock-tracking-row-selected selected" : ""} onClick={() => selectItem(item)}>
                      <td className="stock-tracking-check-col" onClick={(event) => event.stopPropagation()}>
                        <input type="checkbox" className="stock-tracking-checkbox" aria-label={`${item.stock_name || item.stock_code || "종목"} 갱신 선택`} checked={checkedItemIds.has(item.id)} disabled={!canCollectItem(item)} onChange={() => toggleCheckedItem(item)} />
                      </td>
                      <td><span className={`tracking-status-badge status-${item.status.toLowerCase()}`}>{STATUS_LABELS[item.status]}</span></td>
                      <td>{fmtDate(item.tracking_base_date)}</td>
                      <td><strong>{item.stock_name || "-"}</strong><small>{item.stock_code || "-"}</small></td>
                      <td>{item.group_name}</td>
                      <td className={`text-right ${getReturnClass(item.tracking_return_pct)}`} title={item.entry_close_date && item.latest_close_date ? `${item.entry_close_date} 종가 대비 ${item.latest_close_date} 종가` : "기준 종가 대비 최신 종가"}>{fmtSignedPct(item.tracking_return_pct)}</td>
                      <td><span className={`tracking-price-badge price-${item.price_status.toLowerCase()}`}>{PRICE_STATUS_LABELS[item.price_status]}</span></td>
                      <td>{fmtDate(item.review_date)}</td>
                    </tr>
                  ))}
                  {items.length === 0 ? (
                    <tr>
                      <td colSpan={8}>
                        <div className="stock-tracking-empty-state compact">
                          <strong>등록된 트래킹 종목이 없습니다.</strong>
                          <p>시장 수급 테마(종목)의 저장된 수급 이벤트 후보에서 종목을 선택해 종목트래킹 그룹에 등록할 수 있습니다.</p>
                          <button type="button" className="btn btn-secondary" onClick={() => navigate("/market-trends")}>시장 수급 테마(종목) 화면으로 이동</button>
                        </div>
                      </td>
                    </tr>
                  ) : null}
                </tbody>
              </table>
            </div>
            <div className="stock-tracking-pagination">
              <span>{itemTotal > 0 ? itemPageStart + "-" + itemPageEnd + " / " + itemTotal + "건" : "0건"}</span>
              <div className="stock-tracking-pagination-buttons">
                <button type="button" className="btn btn-secondary btn-table-sm" disabled={itemPage <= 1} onClick={() => void moveItemPage(itemPage - 1)}>이전</button>
                {Array.from({ length: itemTotalPages }, (_, index) => index + 1).filter((page) => page === 1 || page === itemTotalPages || Math.abs(page - itemPage) <= 1).map((page, index, pages) => (
                  <button type="button" key={page} className={`btn btn-secondary btn-table-sm ${page === itemPage ? "active" : ""}`} onClick={() => void moveItemPage(page)} disabled={page === itemPage}>
                    {index > 0 && page - pages[index - 1] > 1 ? "... " + page : page}
                  </button>
                ))}
                <button type="button" className="btn btn-secondary btn-table-sm" disabled={itemPage >= itemTotalPages} onClick={() => void moveItemPage(itemPage + 1)}>다음</button>
              </div>
            </div>
          </SectionCard>

          {selectedItem ? <div className="stock-tracking-detail-backdrop" onClick={closeDetail} /> : null}
          <SectionCard className={`stock-tracking-detail-card ${selectedItem ? "open" : ""}`}> 
            {selectedItem ? (
              <div className="stock-tracking-detail">
                <div className="stock-tracking-detail-head">
                  <div>
                    <h3>{selectedItem.stock_name || "-"}</h3>
                    <p>{selectedItem.stock_code || "-"} · {selectedItem.group_name}</p>
                  </div>
                  <div className="stock-tracking-detail-badges">
                    <span className={`tracking-status-badge status-${selectedItem.status.toLowerCase()}`}>{STATUS_LABELS[selectedItem.status]}</span>
                    <span className={`tracking-price-badge price-${selectedItem.price_status.toLowerCase()}`}>{PRICE_STATUS_LABELS[selectedItem.price_status]}</span>
                    <button type="button" className="btn btn-secondary btn-table-sm" onClick={closeDetail}>닫기</button>
                  </div>
                </div>

                <div className="stock-tracking-chart-card">
                  <div className="stock-tracking-card-title"><h4>기준일 차트</h4><span>{chart?.prices.length ? "가격/이동평균/거래량" : "가격정보 갱신 후 표시"}</span></div>
                  {chartLoading ? <div className="stock-tracking-chart-empty">차트 조회 중...</div> : chart && chart.prices.length > 0 ? (
                    <StockTrackingChart chart={chart} item={selectedItem} />
                  ) : (
                    <div className="stock-tracking-chart-empty">
                      <strong>가격정보가 아직 수집되지 않았습니다.</strong>
                      <p>가격정보 갱신 후 차트를 확인할 수 있습니다.</p>
                      <button type="button" className="btn btn-secondary" disabled={!selectedCanCollect || collecting} onClick={() => void collectPrices("detail", "recent")}>이 종목 최근7일수집</button>
                    </div>
                  )}
                </div>

                <div className="stock-tracking-info-card">
                  <div className="stock-tracking-card-title"><h4>기본정보</h4><span>감지 조건과 기준 데이터를 확인합니다.</span></div>
                  <div className="stock-tracking-detail-grid">
                    <div className="info-condition"><span>조건식</span><strong>{selectedItem.condition_name || selectedItem.condition_no || "-"}</strong></div>
                    <div><span>기준일</span><strong>{fmtDate(selectedItem.tracking_base_date)}</strong></div>
                    <div><span>트래킹 등락률</span><strong className={getReturnClass(selectedItem.tracking_return_pct)}>{fmtSignedPct(selectedItem.tracking_return_pct)}</strong></div>
                    <div><span>기준 종가</span><strong>{fmtNumber(selectedItem.entry_close_price)}{selectedItem.entry_close_date ? ` (${fmtDate(selectedItem.entry_close_date)})` : ""}</strong></div>
                    <div><span>최신 종가</span><strong>{fmtNumber(selectedItem.latest_close_price)}{selectedItem.latest_close_date ? ` (${fmtDate(selectedItem.latest_close_date)})` : ""}</strong></div>
                    <div><span>당시 등락률</span><strong>{fmtPct(selectedItem.base_change_rate)}</strong></div>
                    <div><span>당시 거래대금</span><strong>{fmtEok(selectedItem.base_trading_value)}</strong></div>
                    <div><span>판단일</span><strong>{fmtDate(selectedItem.review_date)}</strong></div>
                  </div>
                </div>

                <div className="stock-tracking-info-card">
                  <div className="stock-tracking-card-title"><h4>판단/메모</h4><span>차트 복기와 판단 근거를 기록합니다.</span></div>
                  <label className="stock-tracking-review-field">판단 상태<select className="select-control" value={reviewStatus} onChange={(event) => setReviewStatus(event.target.value as StockTrackingStatus)}>{Object.entries(STATUS_LABELS).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
                  <label className="stock-tracking-review-field">메모<textarea className="textarea-control" placeholder="기준일 당시 차트 위치, 거래량 변화, 이동평균선 상태, 성공/실패로 판단한 이유를 기록해 주세요." value={reviewNote} onChange={(event) => setReviewNote(event.target.value)} /></label>
                  <p className="stock-tracking-review-help">성공/실패/제외로 저장하면 이후 가격 갱신 대상에서 제외됩니다. 보류는 계속 가격 갱신 대상에 포함됩니다.</p>
                </div>

                <div className="stock-tracking-info-card">
                  <div className="stock-tracking-card-title stock-tracking-image-title">
                    <div><h4>첨부 이미지</h4><span>차트 캡처와 복기 이미지를 관리합니다.</span></div>
                    <button type="button" className="btn btn-secondary btn-table-sm" onClick={openImageModal}>+ 이미지 추가</button>
                  </div>
                  {imageRows.length === 0 && appImageRows.length === 0 ? (
                    <div className="stock-tracking-image-placeholder">
                      <strong>등록된 이미지가 없습니다.</strong>
                      <p>기준일 차트, 성공/실패 근거, 진입 가능 구간 이미지를 추가해 복기 자료로 남길 수 있습니다.</p>
                    </div>
                  ) : (
                    <div className="stock-tracking-image-list">
                      {imageRows.map((image) => (
                        <article className="stock-tracking-image-card" key={image.id}>
                          <button type="button" className="stock-tracking-image-thumb" onClick={() => setPreviewImage(image)} aria-label="이미지 크게 보기">
                            <img src={getImageUrl(image.image_url)} alt={image.original_filename || getImageTypeLabel(image.image_type, image.image_type_label)} />
                          </button>
                          <div className="stock-tracking-image-meta">
                            <div className="stock-tracking-image-meta-head">
                              <span className="stock-tracking-image-badge">{getImageTypeLabel(image.image_type, image.image_type_label)}</span>
                              <span>{formatDateTime(image.created_at)}</span>
                            </div>
                            <strong>{image.original_filename || "첨부 이미지"}</strong>
                            {image.caption ? <p className="stock-tracking-image-caption">{image.caption}</p> : <p className="stock-tracking-image-caption muted">캡션 없음</p>}
                            <div className="stock-tracking-image-actions">
                              <button type="button" className="btn btn-secondary btn-table-sm" onClick={() => setPreviewImage(image)}>원본보기</button>
                              <button type="button" className="btn btn-danger btn-table-sm" onClick={() => void deleteImage(image)}>삭제</button>
                            </div>
                          </div>
                        </article>
                      ))}
                      {appImageRows.map((image) => (
                        <article className="stock-tracking-image-card" key={"app-" + image.id}>
                          <button type="button" className="stock-tracking-image-thumb" onClick={() => setPreviewAppImage(image)} aria-label="이미지 크게 보기">
                            <img src={getImageUrl(image.file_url)} alt={image.original_file_name || "첨부 이미지"} />
                          </button>
                          <div className="stock-tracking-image-meta">
                            <div className="stock-tracking-image-meta-head">
                              <span className="stock-tracking-image-badge">공통 이미지</span>
                              <span>{formatDateTime(image.created_at)}</span>
                            </div>
                            <strong>{image.original_file_name || "첨부 이미지"}</strong>
                            {image.description ? <p className="stock-tracking-image-caption">{image.description}</p> : <p className="stock-tracking-image-caption muted">메모 없음</p>}
                            <div className="stock-tracking-image-actions">
                              <button type="button" className="btn btn-secondary btn-table-sm" onClick={() => setPreviewAppImage(image)}>원본보기</button>
                              <button type="button" className="btn btn-danger btn-table-sm" onClick={() => void deleteAppImage(image)}>삭제</button>
                            </div>
                          </div>
                        </article>
                      ))}
                    </div>
                  )}
                </div>

                <div className="stock-tracking-actions">
                  <button type="button" className="btn btn-danger" onClick={() => void deleteItem(selectedItem)}>삭제</button>
                  <button type="button" className="btn btn-primary" onClick={() => void saveReview()}>저장</button>
                </div>
              </div>
            ) : (
              <div className="stock-tracking-empty-state detail-empty">
                <strong>왼쪽 목록에서 트래킹 종목을 선택해 주세요.</strong>
                <p>선택한 종목의 기준일 차트, 이동평균/거래량, 판단 상태와 메모, 첨부 이미지를 확인할 수 있습니다.</p>
              </div>
            )}
          </SectionCard>
        </div>
      )}


      {fullRefreshTarget ? (
        <div className="modal-backdrop stock-tracking-refresh-confirm-backdrop" onClick={() => setFullRefreshTarget(null)}>
          <div className="modal-card stock-tracking-refresh-confirm-modal" onClick={(event) => event.stopPropagation()}>
            <div className="trade-journal-detail-header">
              <h3>전체수집을 실행하시겠습니까?</h3>
              <button type="button" className="btn btn-secondary btn-table-sm" onClick={() => setFullRefreshTarget(null)}>닫기</button>
            </div>
            <div className="stock-tracking-refresh-confirm-body">
              <p>{fullRefreshTarget === "all" ? "목록의 수집 가능 트래킹 종목을 전체 기간 기준으로 다시 요청합니다." : `선택한 ${checkedCollectableItems.length}개 트래킹 종목을 전체 기간 기준으로 다시 요청합니다.`}</p>
              <div className="stock-tracking-refresh-confirm-note">
                최근7일수집은 기존 저장 데이터를 기준으로 증분 요청하고, 전체수집은 과거 기간을 다시 확인합니다. 저장은 기존 upsert 흐름을 사용합니다.
              </div>
            </div>
            <div className="stock-tracking-refresh-confirm-actions">
              <button type="button" className="btn btn-secondary" disabled={collecting} onClick={() => setFullRefreshTarget(null)}>취소</button>
              <button type="button" className="btn btn-danger" disabled={collecting} onClick={() => void collectPrices(fullRefreshTarget, "full")}>{collecting ? "전체수집 중..." : "전체수집 실행"}</button>
            </div>
          </div>
        </div>
      ) : null}
      {imageModalOpen && selectedItem ? (
        <div className="modal-backdrop stock-tracking-image-modal-backdrop">
          <div className="modal-card stock-tracking-image-modal" onClick={(event) => event.stopPropagation()}>
            <div className="trade-journal-detail-header">
              <h3>차트 이미지 등록</h3>
              <button type="button" className="btn btn-secondary btn-table-sm" onClick={() => setImageModalOpen(false)}>닫기</button>
            </div>
            <div className="stock-tracking-image-form">
              <label>이미지 파일
                <input className="input-control" type="file" accept="image/png,image/jpeg,image/webp" onChange={(event) => setImageForm((prev) => ({ ...prev, file: event.target.files?.[0] ?? null }))} />
              </label>
              <label>이미지 유형
                <select className="select-control" value={imageForm.image_type} onChange={(event) => setImageForm((prev) => ({ ...prev, image_type: event.target.value as StockTrackingImageType }))}>
                  {IMAGE_TYPE_OPTIONS.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
                </select>
              </label>
              <label className="wide">캡션
                <textarea className="textarea-control" placeholder="이미지에서 확인할 포인트를 간단히 기록해 주세요." value={imageForm.caption} onChange={(event) => setImageForm((prev) => ({ ...prev, caption: event.target.value }))} />
              </label>
              <p className="stock-tracking-image-help">PNG, JPG, WEBP 파일만 등록할 수 있으며 최대 10MB까지 업로드됩니다.</p>
            </div>
            <div className="stock-tracking-actions stock-tracking-modal-actions">
              <button type="button" className="btn btn-secondary" onClick={() => setImageModalOpen(false)}>취소</button>
              <button type="button" className="btn btn-primary" disabled={imageUploading} onClick={() => void uploadImage()}>{imageUploading ? "등록 중..." : "등록"}</button>
            </div>
          </div>
        </div>
      ) : null}

      {previewImage ? (
        <div className="modal-backdrop stock-tracking-image-modal-backdrop" onClick={() => setPreviewImage(null)}>
          <div className="modal-card stock-tracking-image-preview-modal" onClick={(event) => event.stopPropagation()}>
            <div className="trade-journal-detail-header">
              <div>
                <h3>{getImageTypeLabel(previewImage.image_type, previewImage.image_type_label)}</h3>
                <p>{previewImage.original_filename || "첨부 이미지"}</p>
              </div>
              <button type="button" className="btn btn-secondary btn-table-sm" onClick={() => setPreviewImage(null)}>닫기</button>
            </div>
            <div className="stock-tracking-image-preview">
              <img src={getImageUrl(previewImage.image_url)} alt={previewImage.original_filename || "첨부 이미지"} />
            </div>
            {previewImage.caption ? <p className="stock-tracking-image-preview-caption">{previewImage.caption}</p> : null}
          </div>
        </div>
      ) : null}

      {previewAppImage ? (
        <div className="modal-backdrop stock-tracking-image-modal-backdrop" onClick={() => setPreviewAppImage(null)}>
          <div className="modal-card stock-tracking-image-preview-modal" onClick={(event) => event.stopPropagation()}>
            <div className="trade-journal-detail-header">
              <div>
                <h3>첨부 이미지</h3>
                <p>{previewAppImage.original_file_name || "첨부 이미지"}</p>
              </div>
              <button type="button" className="btn btn-secondary btn-table-sm" onClick={() => setPreviewAppImage(null)}>닫기</button>
            </div>
            <div className="stock-tracking-image-preview">
              <img src={getImageUrl(previewAppImage.file_url)} alt={previewAppImage.original_file_name || "첨부 이미지"} />
            </div>
            {previewAppImage.description ? <p className="stock-tracking-image-preview-caption">{previewAppImage.description}</p> : null}
          </div>
        </div>
      ) : null}

      {groupModalOpen ? (
        <div className="modal-backdrop">
          <div className="modal-card stock-tracking-group-modal" onClick={(event) => event.stopPropagation()}>
            <div className="trade-journal-detail-header">
              <h3>{editingGroup ? "그룹 수정" : "그룹 등록"}</h3>
              <button type="button" className="btn btn-secondary btn-table-sm" onClick={() => setGroupModalOpen(false)}>닫기</button>
            </div>
            <div className="stock-tracking-form-grid">
              <label>그룹명<input className="input-control" value={groupForm.name} onChange={(event) => setGroupForm((prev) => ({ ...prev, name: event.target.value }))} /></label>
              <label>활성 여부<select className="select-control" value={groupForm.is_active} onChange={(event) => setGroupForm((prev) => ({ ...prev, is_active: Number(event.target.value) }))}><option value={1}>활성</option><option value={0}>비활성</option></select></label>
              <label className="wide">설명<textarea className="textarea-control" value={groupForm.description} onChange={(event) => setGroupForm((prev) => ({ ...prev, description: event.target.value }))} /></label>
              <label className="wide">성공 기준 메모<textarea className="textarea-control" value={groupForm.success_rule_note} onChange={(event) => setGroupForm((prev) => ({ ...prev, success_rule_note: event.target.value }))} /></label>
              <label className="wide">실패 기준 메모<textarea className="textarea-control" value={groupForm.fail_rule_note} onChange={(event) => setGroupForm((prev) => ({ ...prev, fail_rule_note: event.target.value }))} /></label>
              <label className="wide">관찰 포인트<textarea className="textarea-control" value={groupForm.observation_note} onChange={(event) => setGroupForm((prev) => ({ ...prev, observation_note: event.target.value }))} /></label>
            </div>
            <div className="stock-tracking-actions">
              <button type="button" className="btn btn-secondary" onClick={() => { setGroupModalOpen(false); resetGroupForm(); }}>취소</button>
              <button type="button" className="btn btn-primary" onClick={() => void saveGroup()}>{editingGroup ? "수정" : "등록"}</button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}

export default StockTrackingPage;


