import { Fragment, FormEvent, MouseEvent, useEffect, useMemo, useRef, useState } from "react";
import { BarChart3, PauseCircle, Play, Search, Settings, ShoppingCart, StepForward, X } from "lucide-react";
import EmptyState from "@/components/common/EmptyState";
import PageHeader from "@/components/common/PageHeader";
import SectionCard from "@/components/common/SectionCard";
import { repositories } from "@/services";
import type { TradeMethod, TradeMethodSaveRequest } from "@/types/tradeJournal";
import type {
  SimulationReview,
  TrainingCandle,
  TrainingEquityCurvePoint,
  TrainingGptPackage,
  TrainingMethodReview,
  TrainingOrderRequest,
  TrainingResult,
  TrainingSessionDetail,
  TrainingStockItem,
  TrainingTrade,
} from "@/types/tradeTraining";

type OrderMode = "BUY" | "SELL";
type TradeMarkerSide = "BUY" | "SELL";
type DrawingTool = "horizontal" | "trend" | null;
type TrendPoint = {
  index: number;
  price: number;
};
type ChartDrawing =
  | {
      id: string;
      type: "horizontal";
      price: number;
    }
  | {
      id: string;
      type: "trend";
      startIndex: number;
      startPrice: number;
      endIndex: number;
      endPrice: number;
    };
type TradeMarker = {
  key: string;
  tradeDate: string;
  side: TradeMarkerSide;
  trades: TrainingTrade[];
  x: number;
  y: number;
};
type TradeMarkerTooltip = TradeMarker & {
  tooltipX: number;
  tooltipY: number;
};
type TradeLogRow = {
  trade: TrainingTrade;
  tradeAmount: number;
  currentInvestedAmount: number;
};
type ReasonQualityGrade = "충분" | "보통" | "부족" | "미작성";

const DEFAULT_MA_TEXT = "5,10,20,60,120";
const STOCKS_PAGE_SIZE = 6;
const BUY_REVIEW_TAGS = [
  { value: "planned", label: "계획 매수" },
  { value: "confirmation", label: "확인 매수" },
  { value: "pullback", label: "눌림 매수" },
  { value: "breakout", label: "돌파 매수" },
  { value: "add_buy", label: "추가매수" },
  { value: "early_entry", label: "조기 진입" },
  { value: "chase_risk", label: "추격매수 가능성 있음" },
  { value: "test", label: "테스트 매수" },
];
const SELL_REVIEW_TAGS = [
  { value: "planned", label: "계획 매도" },
  { value: "target_reached", label: "목표 도달" },
  { value: "stop_loss", label: "손절" },
  { value: "reduce", label: "비중 축소" },
  { value: "profit_protection", label: "수익 보호" },
  { value: "trend_break", label: "추세 이탈" },
  { value: "resistance", label: "저항 도달" },
  { value: "spike_burden", label: "급등 부담" },
  { value: "emotion_risk", label: "감정 매도 가능성" },
  { value: "other", label: "기타" },
];
const BUY_METHOD_FIT_OPTIONS = [
  { value: "", label: "선택 안 함" },
  { value: "fit", label: "충족" },
  { value: "partial", label: "일부 충족" },
  { value: "miss", label: "미충족" },
  { value: "hold", label: "판단 보류" },
];
const SELL_METHOD_FIT_OPTIONS = [
  { value: "", label: "선택 안 함" },
  { value: "fit", label: "매매기법 기준에 따른 매도" },
  { value: "partial", label: "일부 기준에 따른 매도" },
  { value: "unrelated", label: "기준과 무관한 매도" },
  { value: "none", label: "최초 계획이 없었음" },
];
const PLAN_ALIGNMENT_OPTIONS = [
  { value: "", label: "선택 안 함" },
  { value: "match", label: "일치" },
  { value: "partial", label: "일부 일치" },
  { value: "mismatch", label: "불일치" },
  { value: "none", label: "최초 계획 없음" },
];
const ADD_BUY_PLAN_OPTIONS = [
  { value: "none", label: "추가매수 계획 없음" },
  { value: "pullback", label: "눌림 시 추가매수" },
  { value: "breakout", label: "돌파 확인 시 추가매수" },
  { value: "loss", label: "손실 구간 추가매수" },
  { value: "profit", label: "수익 구간 추가매수" },
  { value: "undecided", label: "아직 정하지 않음" },
];
const BUY_REVIEW_TEMPLATES: Array<{ title: string; description: string; review: TrainingMethodReview }> = [
  {
    title: "20일선 눌림 확인",
    description: "20일선 부근 지지와 반등 확인을 기록",
    review: {
      selected_template: "20일선 눌림 확인",
      entry_type_tags: ["pullback", "confirmation"],
      method_fit: "partial",
      matched_entry_rules: "20일선 부근 눌림 후 지지 확인",
      failure_criteria: "20일선 이탈 또는 직전 저점 이탈 시 실패로 본다.",
      stop_loss_rule: "20일선 종가 이탈 또는 -5% 도달 시 손절 검토",
      target_exit_rule: "+5% 또는 전고점 부근에서 1차 청산 검토",
      add_buy_plan_type: "none",
    },
  },
  {
    title: "20일선 돌파",
    description: "20일선 회복 또는 돌파 확인을 기록",
    review: {
      selected_template: "20일선 돌파",
      entry_type_tags: ["breakout", "confirmation"],
      method_fit: "partial",
      matched_entry_rules: "20일선 돌파",
      failure_criteria: "20일선 재이탈 시 실패로 본다.",
      stop_loss_rule: "20일선 종가 이탈 또는 -5% 도달 시 손절 검토",
      target_exit_rule: "+5% 또는 직전 저항 구간에서 청산 검토",
      add_buy_plan_type: "undecided",
      add_buy_condition: "안착 확인 전 추가매수는 보류",
    },
  },
  {
    title: "전고점 돌파",
    description: "전고점 돌파와 추격 위험을 함께 기록",
    review: {
      selected_template: "전고점 돌파",
      entry_type_tags: ["breakout"],
      method_fit: "partial",
      matched_entry_rules: "전고점 돌파",
      risk_or_violation_notes: "단기 급등 후 추격매수 위험 여부 확인 필요",
      failure_criteria: "돌파한 전고점 아래로 재하락하면 실패로 본다.",
      stop_loss_rule: "전고점 재이탈 또는 -5% 도달 시 손절 검토",
      target_exit_rule: "돌파 후 탄력 둔화 또는 목표 수익률 도달 시 청산 검토",
      add_buy_plan_type: "breakout",
      add_buy_condition: "추가매수는 돌파 후 안착 확인 시에만 검토",
    },
  },
  {
    title: "5일선/10일선 회복",
    description: "단기 이동평균 회복 확인을 기록",
    review: {
      selected_template: "5일선/10일선 회복",
      entry_type_tags: ["confirmation"],
      method_fit: "partial",
      matched_entry_rules: "5일선 또는 10일선 회복",
      risk_or_violation_notes: "20일선 지지 여부와 거래량 확인 필요",
      failure_criteria: "회복한 단기 이동평균선을 다시 이탈하면 실패로 본다.",
      stop_loss_rule: "단기 이동평균선 재이탈 또는 -5% 도달 시 손절 검토",
      target_exit_rule: "전고점 또는 목표 수익률 도달 시 청산 검토",
      add_buy_plan_type: "none",
    },
  },
  {
    title: "추가매수",
    description: "계획된 추가 진입인지 구분해 기록",
    review: {
      selected_template: "추가매수",
      entry_type_tags: ["add_buy"],
      method_fit: "partial",
      matched_entry_rules: "기존 매수 근거 유지 후 추가 확인 신호 발생",
      risk_or_violation_notes: "계획된 추가매수인지 추격매수인지 구분 필요",
      failure_criteria: "기존 매수 근거가 훼손되면 실패로 본다.",
      stop_loss_rule: "평균단가 기준 손절 또는 기준선 이탈 시 축소 검토",
      target_exit_rule: "총 보유 비중 기준으로 분할 청산 검토",
      add_buy_plan_type: "undecided",
      add_buy_condition: "추가매수 후 총 비중 한도를 확인한다.",
      max_position_plan: "총 비중 한도 확인 필요",
    },
  },
  {
    title: "추격매수 위험",
    description: "뒤늦은 진입 가능성을 명시해 기록",
    review: {
      selected_template: "추격매수 위험",
      entry_type_tags: ["chase_risk"],
      method_fit: "hold",
      risk_or_violation_notes: "이미 상승한 뒤 뒤늦게 진입하는 추격매수 가능성이 있음",
      failure_criteria: "돌파 기준선 재이탈 또는 단기 급등 후 음봉 전환 시 실패로 본다.",
      stop_loss_rule: "매수가 대비 -5% 또는 기준선 이탈 시 손절 검토",
      target_exit_rule: "짧은 보유와 빠른 리스크 관리 필요",
      add_buy_plan_type: "none",
      add_buy_condition: "추가매수 금지",
      max_position_plan: "비중 확대 금지",
    },
  },
  { title: "직접 입력", description: "템플릿 없이 직접 판단 기준을 기록", review: { selected_template: "직접 입력", add_buy_plan_type: "none" } },
];
const SELL_REVIEW_TEMPLATES: Array<{ title: string; description: string; review: TrainingMethodReview }> = [
  {
    title: "목표 수익 도달",
    description: "목표 수익률 또는 목표가 도달 청산 기록",
    review: { selected_template: "목표 수익 도달", exit_type_tags: ["planned", "target_reached"], method_exit_fit: "fit", matched_exit_rules: "목표 수익률 또는 목표가 도달", plan_alignment: "match", exit_reason_detail: "목표 수익 구간에 도달하여 계획에 따라 청산" },
  },
  {
    title: "5일선 이탈",
    description: "단기 추세 약화와 수익 보호 기록",
    review: { selected_template: "5일선 이탈", exit_type_tags: ["profit_protection", "trend_break"], method_exit_fit: "partial", matched_exit_rules: "5일선 이탈", plan_alignment: "partial", exit_reason_detail: "단기 상승 흐름 약화로 수익 보호 목적 청산" },
  },
  {
    title: "20일선 이탈",
    description: "기준선 훼손에 따른 정리 기록",
    review: { selected_template: "20일선 이탈", exit_type_tags: ["trend_break"], method_exit_fit: "fit", matched_exit_rules: "20일선 이탈", plan_alignment: "match", exit_reason_detail: "매수 근거였던 20일선 기준이 훼손되어 정리" },
  },
  {
    title: "저항선/전고점 도달",
    description: "저항 구간 도달과 수익 보호 기록",
    review: { selected_template: "저항선/전고점 도달", exit_type_tags: ["resistance", "profit_protection"], method_exit_fit: "partial", matched_exit_rules: "저항선 또는 전고점 부근 도달", plan_alignment: "partial", exit_reason_detail: "저항 구간 도달로 수익 보호 또는 일부 청산" },
  },
  {
    title: "급등 후 윗꼬리",
    description: "단기 과열 후 매물 출회 가능성 기록",
    review: { selected_template: "급등 후 윗꼬리", exit_type_tags: ["spike_burden", "profit_protection"], method_exit_fit: "partial", matched_exit_rules: "급등 후 윗꼬리 또는 매물 출회 가능성", plan_alignment: "partial", exit_reason_detail: "단기 급등 후 매물 출회 가능성이 있어 수익 보호" },
  },
  {
    title: "손절 기준 도달",
    description: "사전에 정한 실패 기준 도달 기록",
    review: { selected_template: "손절 기준 도달", exit_type_tags: ["stop_loss"], method_exit_fit: "fit", matched_exit_rules: "사전 손절 기준 또는 실패 기준 도달", plan_alignment: "match", exit_reason_detail: "사전에 정한 실패 기준에 도달하여 손실 제한" },
  },
  {
    title: "비중 축소",
    description: "노출 비중 조절과 위험 관리 기록",
    review: { selected_template: "비중 축소", exit_type_tags: ["reduce"], method_exit_fit: "partial", matched_exit_rules: "위험 관리 또는 노출 비중 조절", plan_alignment: "partial", exit_reason_detail: "보유 비중 조절과 리스크 관리를 위해 일부 또는 전량 축소" },
  },
  {
    title: "감정 매도 위험",
    description: "불안감에 따른 매도 가능성 기록",
    review: { selected_template: "감정 매도 위험", exit_type_tags: ["emotion_risk"], method_exit_fit: "unrelated", plan_alignment: "mismatch", exit_reason_detail: "불안감 또는 수익 반납 우려로 인한 감정 매도 가능성", after_review_memo: "계획된 매도 기준이 있었는지 복기 필요" },
  },
  { title: "직접 입력", description: "템플릿 없이 직접 청산 기준을 기록", review: { selected_template: "직접 입력" } },
];

function createDrawingId(): string {
  if (typeof crypto !== "undefined" && crypto.randomUUID) return crypto.randomUUID();
  return `drawing-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function clampNumber(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}

function fmtNumber(value: number | null | undefined, digits = 0): string {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "-";
  return Number(value).toLocaleString("ko-KR", { maximumFractionDigits: digits });
}

function fmtWon(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "-";
  return `${fmtNumber(value, 0)}원`;
}

function fmtSignedWon(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "-";
  const sign = Number(value) > 0 ? "+" : "";
  return `${sign}${fmtWon(value)}`;
}

function fmtPercent(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "-";
  const sign = Number(value) > 0 ? "+" : "";
  return `${sign}${Number(value).toFixed(2)}%`;
}

function profitClass(value: number | null | undefined): string {
  const amount = Number(value || 0);
  if (amount > 0) return "training-positive";
  if (amount < 0) return "training-negative";
  return "";
}

function buildTradeLogRows(trades: TrainingTrade[]): TradeLogRow[] {
  let runningQty = 0;
  let runningAvgPrice = 0;
  let runningInvestedAmount = 0;

  return trades.map((trade) => {
    const side = String(trade.side || "").toUpperCase();
    const price = Number(trade.price || 0);
    const quantity = Number(trade.quantity || 0);
    const tradeAmount = price * quantity;

    if (side === "BUY" || trade.side === "매수") {
      const previousInvestedAmount = runningQty * runningAvgPrice;
      runningQty += quantity;
      runningInvestedAmount = previousInvestedAmount + tradeAmount;
      runningAvgPrice = runningQty > 0 ? runningInvestedAmount / runningQty : 0;
    } else if (side === "SELL" || trade.side === "매도") {
      runningQty = Math.max(0, runningQty - quantity);
      runningInvestedAmount = runningQty > 0 ? runningQty * runningAvgPrice : 0;
      if (runningQty === 0) runningAvgPrice = 0;
    }

    return {
      trade,
      tradeAmount,
      currentInvestedAmount: runningInvestedAmount,
    };
  });
}

function normalizeMas(value: string): number[] {
  const items = value
    .split(",")
    .map((item) => Number(item.trim()))
    .filter((item) => Number.isFinite(item) && item > 0 && item <= 240);
  return Array.from(new Set(items)).sort((a, b) => a - b);
}

function maStyle(key: string): { color: string; width: number } {
  const period = Number(key.replace("ma", ""));
  switch (period) {
    case 5:
      return { color: "#111827", width: 1.4 };
    case 10:
      return { color: "#ef4444", width: 1.4 };
    case 20:
      return { color: "#eab308", width: 2.1 };
    case 60:
      return { color: "#16a34a", width: 1.5 };
    case 120:
      return { color: "#2563eb", width: 1.5 };
    default:
      return { color: "#64748b", width: 1.2 };
  }
}

function CandleChart({
  sessionId,
  candles,
  trades,
  avgPriceLine,
  displayDays,
  scrollTargetDate,
  highlightedTradeDate,
  highlightedTradeId,
  onMarkerClick,
}: {
  sessionId?: number | string | null;
  candles: TrainingCandle[];
  trades: TrainingTrade[];
  avgPriceLine?: number | null;
  displayDays: number;
  scrollTargetDate?: string | null;
  highlightedTradeDate?: string | null;
  highlightedTradeId?: number | null;
  onMarkerClick?: (tradeDate: string, tradeId: number | null) => void;
}) {
  const [tooltip, setTooltip] = useState<{ candle: TrainingCandle; x: number; y: number; changeRate: number | null } | null>(null);
  const [markerTooltip, setMarkerTooltip] = useState<TradeMarkerTooltip | null>(null);
  const [drawingTool, setDrawingTool] = useState<DrawingTool>(null);
  const [chartDrawings, setChartDrawings] = useState<ChartDrawing[]>([]);
  const [selectedDrawingId, setSelectedDrawingId] = useState<string | null>(null);
  const [pendingTrendStart, setPendingTrendStart] = useState<TrendPoint | null>(null);
  const scrollRef = useRef<HTMLDivElement | null>(null);
  const fallbackWidth = 1080;
  const [chartViewportWidth, setChartViewportWidth] = useState(fallbackWidth);
  const priceHeight = 420;
  const volumeHeight = 96;
  const pad = { top: 22, right: 46, bottom: 30, left: 62 };
  const baseChartWidth = Math.max(320, chartViewportWidth - pad.left - pad.right);
  const visibleDays = Math.max(20, displayDays || 80);
  const slot = Math.max(4, baseChartWidth / visibleDays);
  const chartWidth = Math.max(baseChartWidth, candles.length * slot);
  const width = Math.ceil(chartWidth + pad.left + pad.right);
  const height = pad.top + priceHeight + volumeHeight + pad.bottom + 22;

  const priced = candles.filter((candle) => candle.high !== null && candle.low !== null);
  const minPrice = priced.length ? Math.min(...priced.map((candle) => Number(candle.low))) : 0;
  const maxPrice = priced.length ? Math.max(...priced.map((candle) => Number(candle.high))) : 1;
  const span = Math.max(1, maxPrice - minPrice);
  const maxVolume = Math.max(1, ...candles.map((candle) => Number(candle.volume || 0)));
  const bodyWidth = Math.max(4, Math.min(13, slot * 0.58));
  const maKeys = Array.from(new Set(candles.flatMap((candle) => Object.keys(candle.moving_averages || {})))).sort(
    (a, b) => Number(a.replace("ma", "")) - Number(b.replace("ma", "")),
  );

  const yPrice = (value: number | null) => {
    if (value === null || !Number.isFinite(value)) return pad.top + priceHeight;
    return pad.top + ((maxPrice - value) / span) * priceHeight;
  };
  const xAt = (idx: number) => pad.left + idx * slot + slot / 2;
  const priceAtY = (y: number) => maxPrice - ((y - pad.top) / priceHeight) * span;
  const showAvgLine = !!avgPriceLine && avgPriceLine > 0 && avgPriceLine >= minPrice && avgPriceLine <= maxPrice;
  const avgLineY = showAvgLine ? yPrice(avgPriceLine) : 0;
  const tooltipWidth = 174;
  const tooltipHeight = 154;
  const chartCenterX = pad.left + chartWidth / 2;
  const preferredTooltipX = tooltip && tooltip.x > chartCenterX ? tooltip.x - tooltipWidth - 12 : (tooltip?.x || 0) + 12;
  const tooltipX = tooltip ? Math.min(width - pad.right - tooltipWidth, Math.max(pad.left + 8, preferredTooltipX)) : 0;
  const tooltipY = tooltip ? Math.min(pad.top + priceHeight - tooltipHeight, Math.max(pad.top + 8, tooltip.y - tooltipHeight / 2)) : 0;
  const tradeMarkers = useMemo<TradeMarker[]>(() => {
    const markerOffset = 16;
    const candleByDate = new Map(candles.map((candle, idx) => [candle.trade_date, { candle, idx }]));
    const grouped = new Map<string, { tradeDate: string; side: TradeMarkerSide; trades: TrainingTrade[] }>();

    trades.forEach((trade) => {
      const sideText = String(trade.side || "").toUpperCase();
      const side: TradeMarkerSide | null = sideText === "BUY" || trade.side === "매수" ? "BUY" : sideText === "SELL" || trade.side === "매도" ? "SELL" : null;
      if (!side || !candleByDate.has(trade.trade_date)) return;
      const key = `${trade.trade_date}-${side}`;
      const current = grouped.get(key);
      if (current) {
        current.trades.push(trade);
      } else {
        grouped.set(key, { tradeDate: trade.trade_date, side, trades: [trade] });
      }
    });

    return Array.from(grouped.values()).flatMap((group) => {
      const target = candleByDate.get(group.tradeDate);
      if (!target) return [];
      const high = Number(target.candle.high || 0);
      const low = Number(target.candle.low || 0);
      if (!high || !low) return [];
      const y = group.side === "BUY"
        ? Math.min(pad.top + priceHeight + markerOffset, yPrice(low) + markerOffset)
        : Math.max(pad.top + markerOffset / 2, yPrice(high) - markerOffset);
      return [{
        key: `${group.tradeDate}-${group.side}`,
        tradeDate: group.tradeDate,
        side: group.side,
        trades: group.trades,
        x: xAt(target.idx),
        y,
      }];
    });
  }, [candles, trades, maxPrice, span, slot]);
  const markerTooltipWidth = 238;
  const markerTooltipHeight = markerTooltip ? 46 + Math.min(3, markerTooltip.trades.length) * 56 + (markerTooltip.trades.length > 3 ? 18 : 0) : 0;
  const markerTooltipX = markerTooltip ? Math.min(width - pad.right - markerTooltipWidth, Math.max(pad.left + 8, markerTooltip.tooltipX + 12)) : 0;
  const markerTooltipY = markerTooltip ? Math.min(pad.top + priceHeight - markerTooltipHeight, Math.max(pad.top + 8, markerTooltip.tooltipY - markerTooltipHeight / 2)) : 0;

  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    const updateWidth = () => {
      setChartViewportWidth(Math.max(320, Math.floor(el.clientWidth || fallbackWidth)));
    };
    updateWidth();
    const observer = new ResizeObserver(updateWidth);
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    const el = scrollRef.current;
    if (!el || candles.length === 0 || scrollTargetDate) return;
    requestAnimationFrame(() => {
      el.scrollLeft = el.scrollWidth;
    });
  }, [candles.length, candles[candles.length - 1]?.trade_date, scrollTargetDate]);

  useEffect(() => {
    const el = scrollRef.current;
    if (!el || !scrollTargetDate) return;
    const targetIndex = candles.findIndex((candle) => candle.trade_date === scrollTargetDate);
    if (targetIndex < 0) return;
    requestAnimationFrame(() => {
      const targetX = xAt(targetIndex);
      el.scrollLeft = Math.max(0, targetX - el.clientWidth / 2);
    });
  }, [scrollTargetDate, candles]);

  useEffect(() => {
    setChartDrawings([]);
    setSelectedDrawingId(null);
    setPendingTrendStart(null);
    setDrawingTool(null);
  }, [sessionId]);

  const toggleDrawingTool = (tool: Exclude<DrawingTool, null>) => {
    setDrawingTool((current) => {
      const nextTool = current === tool ? null : tool;
      setPendingTrendStart(null);
      return nextTool;
    });
    setTooltip(null);
    setMarkerTooltip(null);
  };

  const handleDeleteSelectedDrawing = () => {
    if (!selectedDrawingId) return;
    setChartDrawings((prev) => prev.filter((drawing) => drawing.id !== selectedDrawingId));
    setSelectedDrawingId(null);
    setPendingTrendStart(null);
  };

  const handleClearAllDrawings = () => {
    setChartDrawings([]);
    setSelectedDrawingId(null);
    setPendingTrendStart(null);
    setDrawingTool(null);
  };

  const getChartPointFromMouseEvent = (event: MouseEvent<SVGRectElement>): TrendPoint | null => {
    if (!candles.length || slot <= 0 || priceHeight <= 0 || !Number.isFinite(minPrice) || !Number.isFinite(maxPrice)) return null;
    const rect = event.currentTarget.ownerSVGElement?.getBoundingClientRect();
    if (!rect || rect.width <= 0 || rect.height <= 0) return null;

    const rawX = ((event.clientX - rect.left) / rect.width) * width;
    const rawY = ((event.clientY - rect.top) / rect.height) * height;
    if (!Number.isFinite(rawX) || !Number.isFinite(rawY)) return null;

    const minX = pad.left + slot / 2;
    const maxX = pad.left + Math.max(0, candles.length - 1) * slot + slot / 2;
    const x = clampNumber(rawX, minX, maxX);
    const y = clampNumber(rawY, pad.top, pad.top + priceHeight);
    const index = clampNumber(Math.round((x - pad.left - slot / 2) / slot), 0, candles.length - 1);
    const price = priceAtY(y);
    if (!Number.isFinite(price)) return null;
    return { index, price };
  };

  const handleChartDrawingClick = (event: MouseEvent<SVGRectElement>) => {
    if (!drawingTool) return;
    event.stopPropagation();

    const point = getChartPointFromMouseEvent(event);
    if (!point) return;

    if (drawingTool === "horizontal") {
      setChartDrawings((prev) => [...prev, { id: createDrawingId(), type: "horizontal", price: point.price }]);
      setSelectedDrawingId(null);
      setTooltip(null);
      setMarkerTooltip(null);
      return;
    }

    if (!pendingTrendStart) {
      setPendingTrendStart(point);
      setSelectedDrawingId(null);
      setTooltip(null);
      setMarkerTooltip(null);
      return;
    }

    const samePoint = pendingTrendStart.index === point.index && Math.abs(pendingTrendStart.price - point.price) < span * 0.001;
    if (samePoint) return;

    setChartDrawings((prev) => [
      ...prev,
      {
        id: createDrawingId(),
        type: "trend",
        startIndex: pendingTrendStart.index,
        startPrice: pendingTrendStart.price,
        endIndex: point.index,
        endPrice: point.price,
      },
    ]);
    setPendingTrendStart(null);
    setSelectedDrawingId(null);
    setTooltip(null);
    setMarkerTooltip(null);
  };

  if (candles.length === 0) {
    return <div className="training-chart-empty">훈련을 시작하면 차트가 표시됩니다.</div>;
  }

  return (
    <div className="training-chart-card">
      <div className="training-chart-tools">
        <button className={`training-chart-tool-btn ${drawingTool === "horizontal" ? "active" : ""}`} type="button" onClick={() => toggleDrawingTool("horizontal")}>
          수평선
        </button>
        <button className={`training-chart-tool-btn ${drawingTool === "trend" ? "active" : ""}`} type="button" onClick={() => toggleDrawingTool("trend")}>
          추세선
        </button>
        <button className="training-chart-tool-btn" type="button" onClick={handleDeleteSelectedDrawing} disabled={!selectedDrawingId}>
          선택삭제
        </button>
        <button className="training-chart-tool-btn" type="button" onClick={handleClearAllDrawings} disabled={chartDrawings.length === 0 && !pendingTrendStart}>
          전체삭제
        </button>
      </div>
      <div className="training-chart-viewport" ref={scrollRef}>
        <div className="training-chart-track" style={{ width }}>
          <svg
            className="training-chart-svg"
            width={width}
            height={height}
            viewBox={`0 0 ${width} ${height}`}
            role="img"
            aria-label="일봉 훈련 차트"
            onMouseLeave={() => {
              setTooltip(null);
              setMarkerTooltip(null);
            }}
          >
        <rect x={0} y={0} width={width} height={height} rx={8} fill="#ffffff" />
        {[0, 0.25, 0.5, 0.75, 1].map((rate) => {
          const y = pad.top + priceHeight * rate;
          const price = maxPrice - span * rate;
          return (
            <g key={rate}>
              <line x1={pad.left} x2={width - pad.right} y1={y} y2={y} stroke="#e2e8f0" />
              <text x={width - pad.right + 6} y={y + 4} fontSize="11" fill="#64748b">
                {fmtNumber(price)}
              </text>
            </g>
          );
        })}

        {maKeys.map((key) => {
          const style = maStyle(key);
          const points = candles
            .map((candle, candleIdx) => {
              const value = candle.moving_averages?.[key];
              return value === null || value === undefined ? null : `${xAt(candleIdx)},${yPrice(Number(value))}`;
            })
            .filter(Boolean)
            .join(" ");
          return points ? <polyline key={key} points={points} fill="none" stroke={style.color} strokeWidth={style.width} /> : null;
        })}

        {showAvgLine ? (
          <g pointerEvents="none">
            <line x1={pad.left} x2={width - pad.right} y1={avgLineY} y2={avgLineY} stroke="#7c3aed" strokeWidth={1.4} strokeDasharray="4 4" />
            <rect x={width - pad.right - 112} y={avgLineY - 13} width={106} height={22} rx={6} fill="#f5f3ff" stroke="#c4b5fd" />
            <text x={width - pad.right - 102} y={avgLineY + 2} fontSize="11" fill="#5b21b6">
              평균단가 {fmtNumber(avgPriceLine)}
            </text>
          </g>
        ) : null}

        {candles.map((candle, idx) => {
          const x = xAt(idx);
          const open = Number(candle.open || 0);
          const close = Number(candle.close || 0);
          const high = Number(candle.high || 0);
          const low = Number(candle.low || 0);
          const isUp = close >= open;
          const color = isUp ? "#dc2626" : "#2563eb";
          const top = yPrice(Math.max(open, close));
          const bottom = yPrice(Math.min(open, close));
          const bodyHeight = Math.max(2, bottom - top);
          const volumeBarHeight = (Number(candle.volume || 0) / maxVolume) * volumeHeight;
          const prevClose = idx > 0 ? Number(candles[idx - 1]?.close || 0) : 0;
          const changeRate = prevClose > 0 && close > 0 ? ((close - prevClose) / prevClose) * 100 : null;
          return (
            <g key={candle.trade_date}>
              {highlightedTradeDate === candle.trade_date ? (
                <rect x={x - slot / 2} y={pad.top} width={slot} height={priceHeight + 22 + volumeHeight} fill="#fef3c7" opacity={0.42} />
              ) : null}
              <line x1={x} x2={x} y1={yPrice(high)} y2={yPrice(low)} stroke={color} strokeWidth={1.4} />
              <rect x={x - bodyWidth / 2} y={top} width={bodyWidth} height={bodyHeight} fill={isUp ? "#fff1f2" : "#eff6ff"} stroke={color} strokeWidth={1.2} />
              <rect x={x - bodyWidth / 2} y={pad.top + priceHeight + 22 + volumeHeight - volumeBarHeight} width={bodyWidth} height={volumeBarHeight} fill={isUp ? "#fecaca" : "#bfdbfe"} />
              <rect
                x={x - slot / 2}
                y={pad.top}
                width={slot}
                height={priceHeight + 22 + volumeHeight}
                fill="transparent"
                onMouseEnter={() => !drawingTool && setTooltip({ candle, x, y: yPrice(high), changeRate })}
                onMouseMove={() => !drawingTool && setTooltip({ candle, x, y: yPrice(high), changeRate })}
              />
            </g>
          );
        })}

        {chartDrawings.map((drawing) => {
          const isSelected = selectedDrawingId === drawing.id;
          const lineProps = drawing.type === "horizontal"
            ? { x1: pad.left, x2: width - pad.right, y1: yPrice(drawing.price), y2: yPrice(drawing.price) }
            : { x1: xAt(drawing.startIndex), x2: xAt(drawing.endIndex), y1: yPrice(drawing.startPrice), y2: yPrice(drawing.endPrice) };
          const className = drawing.type === "horizontal"
            ? `training-drawing-line training-drawing-horizontal ${isSelected ? "active" : ""}`
            : `training-drawing-line training-drawing-trend ${isSelected ? "active" : ""}`;
          return (
            <g key={drawing.id}>
              <line
                className="training-drawing-hit-line"
                {...lineProps}
                onClick={(event) => {
                  event.stopPropagation();
                  setSelectedDrawingId(drawing.id);
                }}
              />
              <line className={className} {...lineProps} pointerEvents="none" />
            </g>
          );
        })}

        {pendingTrendStart ? (
          <circle
            className="training-drawing-pending-point"
            cx={xAt(pendingTrendStart.index)}
            cy={yPrice(pendingTrendStart.price)}
            r={4}
            pointerEvents="none"
          />
        ) : null}

        {tradeMarkers.map((marker) => {
          const isActive = highlightedTradeDate === marker.tradeDate || marker.trades.some((trade) => trade.id === highlightedTradeId);
          const label = marker.side === "BUY" ? "B" : "S";
          const sideLabel = marker.side === "BUY" ? "매수" : "매도";
          return (
            <g
              key={marker.key}
              className={`training-trade-marker training-trade-marker-${marker.side.toLowerCase()} ${isActive ? "training-trade-marker-active" : ""}`}
              transform={`translate(${marker.x}, ${marker.y})`}
              pointerEvents={drawingTool ? "none" : "auto"}
              onMouseEnter={() => {
                if (drawingTool) return;
                setTooltip(null);
                setMarkerTooltip({ ...marker, tooltipX: marker.x, tooltipY: marker.y });
              }}
              onMouseMove={() => {
                if (drawingTool) return;
                setTooltip(null);
                setMarkerTooltip({ ...marker, tooltipX: marker.x, tooltipY: marker.y });
              }}
              onClick={(event) => {
                event.stopPropagation();
                if (drawingTool) return;
                onMarkerClick?.(marker.tradeDate, marker.trades[0]?.id ?? null);
              }}
            >
              <circle r={8.5} />
              <text className="training-trade-marker-text" y={3.5}>{label}</text>
              <title>{marker.tradeDate} {sideLabel} {marker.trades.length}건</title>
            </g>
          );
        })}

        {drawingTool ? (
          <rect
            className="training-chart-drawing-layer"
            x={pad.left}
            y={pad.top}
            width={Math.max(1, chartWidth)}
            height={priceHeight}
            fill="transparent"
            pointerEvents="all"
            onClick={handleChartDrawingClick}
          />
        ) : null}

        {markerTooltip ? (
          <g className="training-trade-tooltip" transform={`translate(${markerTooltipX}, ${markerTooltipY})`} pointerEvents="none">
            <rect width={markerTooltipWidth} height={markerTooltipHeight} rx={8} fill="#0f172a" opacity={0.82} />
            <text x={12} y={21} fontSize="12" fontWeight={800} fill="#f8fafc">
              {markerTooltip.tradeDate} {markerTooltip.side === "BUY" ? "매수" : "매도"} {markerTooltip.trades.length > 1 ? `${markerTooltip.trades.length}건` : ""}
            </text>
            {markerTooltip.trades.slice(0, 3).map((trade, idx) => {
              const baseY = 45 + idx * 56;
              return (
                <g key={trade.id}>
                  <text x={12} y={baseY} fontSize="11" fill="#cbd5e1">가격</text>
                  <text x={64} y={baseY} fontSize="11" fontWeight={700} fill="#ffffff">{fmtWon(trade.price)}</text>
                  <text x={132} y={baseY} fontSize="11" fill="#cbd5e1">수량</text>
                  <text x={170} y={baseY} fontSize="11" fontWeight={700} fill="#ffffff">{fmtNumber(trade.quantity)}주</text>
                  <text x={12} y={baseY + 18} fontSize="11" fill="#cbd5e1">거래금액</text>
                  <text x={76} y={baseY + 18} fontSize="11" fontWeight={700} fill="#ffffff">{fmtWon(trade.amount)}</text>
                  <text x={12} y={baseY + 36} fontSize="11" fill="#cbd5e1">손익</text>
                  <text x={64} y={baseY + 36} fontSize="11" fontWeight={700} fill={Number(trade.realized_profit || 0) > 0 ? "#fecaca" : Number(trade.realized_profit || 0) < 0 ? "#bfdbfe" : "#ffffff"}>
                    {fmtSignedWon(trade.realized_profit)}
                  </text>
                  <text x={132} y={baseY + 36} fontSize="11" fill="#cbd5e1">사유</text>
                  <text x={170} y={baseY + 36} fontSize="11" fontWeight={700} fill="#ffffff">{trade.reason || "-"}</text>
                </g>
              );
            })}
            {markerTooltip.trades.length > 3 ? (
              <text x={12} y={markerTooltipHeight - 12} fontSize="11" fill="#cbd5e1">외 {markerTooltip.trades.length - 3}건</text>
            ) : null}
          </g>
        ) : tooltip ? (
          <g className="training-candle-tooltip" transform={`translate(${tooltipX}, ${tooltipY})`} pointerEvents="none">
            <rect width={tooltipWidth} height={tooltipHeight} rx={8} fill="#0f172a" opacity={0.7} />
            <text x={12} y={21} fontSize="12" fontWeight={800} fill="#f8fafc">{tooltip.candle.trade_date}</text>
            <text x={12} y={43} fontSize="11" fill="#cbd5e1">시가</text>
            <text x={92} y={43} fontSize="11" fontWeight={700} fill="#ffffff">{fmtWon(tooltip.candle.open)}</text>
            <text x={12} y={61} fontSize="11" fill="#cbd5e1">고가</text>
            <text x={92} y={61} fontSize="11" fontWeight={700} fill="#ffffff">{fmtWon(tooltip.candle.high)}</text>
            <text x={12} y={79} fontSize="11" fill="#cbd5e1">저가</text>
            <text x={92} y={79} fontSize="11" fontWeight={700} fill="#ffffff">{fmtWon(tooltip.candle.low)}</text>
            <text x={12} y={97} fontSize="11" fill="#cbd5e1">종가</text>
            <text x={92} y={97} fontSize="11" fontWeight={700} fill="#ffffff">{fmtWon(tooltip.candle.close)}</text>
            <text x={12} y={115} fontSize="11" fill="#cbd5e1">등락률</text>
            <text x={92} y={115} fontSize="11" fontWeight={700} fill={Number(tooltip.changeRate || 0) > 0 ? "#fecaca" : Number(tooltip.changeRate || 0) < 0 ? "#bfdbfe" : "#ffffff"}>
              {tooltip.changeRate === null ? "-" : fmtPercent(tooltip.changeRate)}
            </text>
            <text x={12} y={133} fontSize="11" fill="#cbd5e1">거래량</text>
            <text x={92} y={133} fontSize="11" fontWeight={700} fill="#ffffff">{fmtNumber(tooltip.candle.volume)}</text>
          </g>
        ) : null}

        <line x1={pad.left} x2={width - pad.right} y1={pad.top + priceHeight + 22 + volumeHeight} y2={pad.top + priceHeight + 22 + volumeHeight} stroke="#cbd5e1" />
        <text x={pad.left} y={height - 8} fontSize="11" fill="#64748b">{candles[0]?.trade_date}</text>
        <text x={width - pad.right - 84} y={height - 8} fontSize="11" fill="#64748b">{candles[candles.length - 1]?.trade_date}</text>
        {maKeys.map((key, idx) => {
          const style = maStyle(key);
          return (
            <g key={key} transform={`translate(${pad.left + idx * 76}, 15)`}>
              <line x1={0} x2={18} y1={0} y2={0} stroke={style.color} strokeWidth={style.width} />
              <text x={22} y={4} fontSize="11" fill="#475569">{key.toUpperCase()}</text>
            </g>
          );
        })}
          </svg>
        </div>
      </div>
    </div>
  );
}

function EquityCurveChart({ points }: { points: TrainingEquityCurvePoint[] }) {
  const width = 760;
  const height = 180;
  const pad = { top: 16, right: 22, bottom: 28, left: 56 };
  if (points.length === 0) return <div className="training-chart-empty training-equity-empty">자산 스냅샷이 아직 없습니다.</div>;
  const values = points.map((point) => Number(point.total_asset || 0));
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = Math.max(1, max - min);
  const innerWidth = width - pad.left - pad.right;
  const innerHeight = height - pad.top - pad.bottom;
  const xAt = (idx: number) => pad.left + (idx / Math.max(1, points.length - 1)) * innerWidth;
  const yAt = (value: number) => pad.top + ((max - value) / span) * innerHeight;
  const polyline = points.map((point, idx) => `${xAt(idx)},${yAt(Number(point.total_asset || 0))}`).join(" ");
  return (
    <div className="training-equity-chart-shell">
      <svg viewBox={`0 0 ${width} ${height}`} className="training-equity-chart" role="img" aria-label="자산 흐름">
        <rect x={0} y={0} width={width} height={height} rx={8} fill="#ffffff" />
        {[0, 0.5, 1].map((rate) => {
          const y = pad.top + innerHeight * rate;
          const value = max - span * rate;
          return (
            <g key={rate}>
              <line x1={pad.left} x2={width - pad.right} y1={y} y2={y} stroke="#e2e8f0" />
              <text x={6} y={y + 4} fontSize="11" fill="#64748b">{fmtNumber(value)}</text>
            </g>
          );
        })}
        <polyline points={polyline} fill="none" stroke="#111827" strokeWidth={2} />
        {points.map((point, idx) => (
          <circle key={`${point.trade_date}-${idx}`} cx={xAt(idx)} cy={yAt(Number(point.total_asset || 0))} r={2.4} fill="#111827" />
        ))}
        <text x={pad.left} y={height - 8} fontSize="11" fill="#64748b">{points[0]?.trade_date}</text>
        <text x={width - pad.right - 82} y={height - 8} fontSize="11" fill="#64748b">{points[points.length - 1]?.trade_date}</text>
      </svg>
    </div>
  );
}

function tradeMethodValue(method: TradeMethod | null | undefined, ...fields: Array<keyof TradeMethod>): string {
  if (!method) return "";
  for (const field of fields) {
    const value = method[field];
    if (typeof value === "string" && value.trim()) return value.trim();
  }
  return "";
}

function rulePreview(value?: string | null): string {
  const text = (value || "").trim();
  if (!text) return "등록된 원칙이 없습니다.";
  return text;
}

function cleanRuleText(value?: string | null): string {
  const text = (value || "").trim();
  if (!text) return "등록된 내용이 없습니다.";
  return text
    .split("\n")
    .map((line) => line.replace(/^\s{0,3}#{1,6}\s*/, "").replace(/^\s*[-*]\s+/, "• "))
    .join("\n")
    .trim();
}

type TrainingMethodEditableField = "core_concept" | "buy_condition" | "sell_condition" | "stop_loss_rule" | "checklist";

type TrainingMethodPrinciplesForm = Record<TrainingMethodEditableField, string>;

type TrainingMethodPrinciplesTab = {
  key: TrainingMethodEditableField | "lessons";
  label: string;
  value: string;
  editableField?: TrainingMethodEditableField;
};

function methodPrinciplesFormFromMethod(method: TradeMethod): TrainingMethodPrinciplesForm {
  return {
    core_concept: tradeMethodValue(method, "core_concept", "description"),
    buy_condition: tradeMethodValue(method, "buy_condition", "entry_rule"),
    sell_condition: tradeMethodValue(method, "sell_condition", "exit_rule", "take_profit_rule"),
    stop_loss_rule: tradeMethodValue(method, "stop_loss_rule"),
    checklist: tradeMethodValue(method, "checklist"),
  };
}

function normalizePrincipleText(value: string): string {
  return value.trim();
}

function reasonQualityClass(grade?: string | null): string {
  if (grade === "충분") return "quality-good";
  if (grade === "보통") return "quality-normal";
  if (grade === "부족") return "quality-weak";
  return "quality-empty";
}

function reasonQualityGuide(grade?: string | null, guide?: string | null): string {
  if (guide) return guide;
  if (grade === "부족") return "'익절'은 결과입니다. 목표가 도달, 저항선 도달, 5일선 이탈, 거래량 둔화 등 실제 판단 근거를 적어주세요.";
  if (grade === "미작성") return "사유가 없으면 다음 훈련에서 판단 과정을 재현하기 어렵습니다.";
  return "복기 품질을 높이려면 판단 근거와 대응 기준을 함께 적어주세요.";
}

function ReasonQualityBadge({ grade, guide }: { grade?: string | null; guide?: string | null }) {
  const safeGrade = (grade || "미작성") as ReasonQualityGrade;
  return (
    <span className={`reason-quality-badge ${reasonQualityClass(safeGrade)}`} title={reasonQualityGuide(safeGrade, guide)}>
      {safeGrade}
    </span>
  );
}

function qualitySummaryText(summary?: Record<string, number>): string {
  const data = summary || {};
  return ["충분", "보통", "부족", "미작성"].map((label) => `${label} ${fmtNumber(data[label] || 0)}건`).join(" / ");
}

function optionLabel(options: Array<{ value: string; label: string }>, value?: string | null): string {
  if (!value) return "기록 없음";
  return options.find((option) => option.value === value)?.label || value;
}

function tagLabels(options: Array<{ value: string; label: string }>, values?: string[]): string {
  if (!values?.length) return "기록 없음";
  return values.map((value) => optionLabel(options, value)).join(", ");
}

function hasMethodReview(review?: TrainingMethodReview | null): boolean {
  if (!review) return false;
  return Object.entries(review).some(([key, value]) => {
    if (Array.isArray(value)) return value.length > 0;
    const text = String(value || "").trim();
    if (!text) return false;
    if (key === "add_buy_plan_type" && text === "none") return false;
    return true;
  });
}

function writtenFlag(value?: string | null): string {
  return value?.trim() ? "작성" : "기록 없음";
}

function methodReviewSummary(mode: OrderMode, review?: TrainingMethodReview | null): string {
  if (!hasMethodReview(review)) return "기법 복기: 미작성";
  const template = review?.selected_template || "직접 입력";
  if (mode === "BUY") {
    const fit = optionLabel(BUY_METHOD_FIT_OPTIONS, review?.method_fit);
    const failure = review?.failure_criteria?.trim() ? "실패 기준 작성" : "실패 기준 없음";
    return `기법 복기: ${template} / ${fit} / ${failure}`;
  }
  const fit = optionLabel(SELL_METHOD_FIT_OPTIONS, review?.method_exit_fit);
  const alignment = optionLabel(PLAN_ALIGNMENT_OPTIONS, review?.plan_alignment);
  return `기법 복기: ${template} / ${fit} / ${alignment}`;
}

function TrainingMethodPrinciples({
  method,
  compact = false,
}: {
  method: TradeMethod | null | undefined;
  compact?: boolean;
}) {
  if (!method) return null;
  const items = [
    { label: "핵심개념", value: tradeMethodValue(method, "core_concept") },
    { label: "설명", value: tradeMethodValue(method, "description") },
    { label: "매수조건", value: tradeMethodValue(method, "buy_condition", "entry_rule") },
    { label: "매도조건", value: tradeMethodValue(method, "sell_condition", "exit_rule") },
    { label: "익절기준", value: tradeMethodValue(method, "take_profit_rule") },
    { label: "손절기준", value: tradeMethodValue(method, "stop_loss_rule") },
    { label: "진입&비중 방식", value: tradeMethodValue(method, "position_sizing_rule") },
    { label: "체크리스트", value: tradeMethodValue(method, "checklist", "take_profit_rule") },
  ];
  return (
    <div className={`training-method-principles ${compact ? "compact" : ""}`}>
      <div className="training-method-principles-title">{method.method_name}</div>
      <div className="training-method-principles-grid">
        {items.map((item) => (
          <div key={item.label} className="training-method-principle-card">
            <span>{item.label}</span>
            <p>{rulePreview(item.value)}</p>
          </div>
        ))}
      </div>
    </div>
  );
}

function SettingsModal({
  q,
  setQ,
  stocks,
  selectedStock,
  setSelectedStock,
  tradeMethods,
  selectedMethodId,
  setSelectedMethodId,
  methodLoadError,
  initialCash,
  setInitialCash,
  feeRatePct,
  setFeeRatePct,
  displayDays,
  setDisplayDays,
  movingAverageText,
  setMovingAverageText,
  startDate,
  setStartDate,
  endDate,
  setEndDate,
  loading,
  onSearch,
  onStart,
  onClose,
}: {
  q: string;
  setQ: (value: string) => void;
  stocks: TrainingStockItem[];
  selectedStock: TrainingStockItem | null;
  setSelectedStock: (stock: TrainingStockItem) => void;
  tradeMethods: TradeMethod[];
  selectedMethodId: number | null;
  setSelectedMethodId: (methodId: number | null) => void;
  methodLoadError: string;
  initialCash: number;
  setInitialCash: (value: number) => void;
  feeRatePct: number;
  setFeeRatePct: (value: number) => void;
  displayDays: number;
  setDisplayDays: (value: number) => void;
  movingAverageText: string;
  setMovingAverageText: (value: string) => void;
  startDate: string;
  setStartDate: (value: string) => void;
  endDate: string;
  setEndDate: (value: string) => void;
  loading: boolean;
  onSearch: () => Promise<void>;
  onStart: () => Promise<void>;
  onClose: () => void;
}) {
  const [stockPage, setStockPage] = useState(1);
  const totalStockPages = Math.max(1, Math.ceil(stocks.length / STOCKS_PAGE_SIZE));
  const safeStockPage = Math.min(stockPage, totalStockPages);
  const pagedStocks = stocks.slice((safeStockPage - 1) * STOCKS_PAGE_SIZE, safeStockPage * STOCKS_PAGE_SIZE);

  useEffect(() => {
    setStockPage(1);
  }, [q]);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    await onStart();
  };
  const searchStocks = async () => {
    setStockPage(1);
    await onSearch();
  };

  return (
    <div className="training-modal-backdrop" role="presentation">
      <form className="training-modal training-settings-modal" onSubmit={submit}>
        <div className="training-modal-head">
          <div>
            <h3>매매훈련 설정</h3>
            <p className="training-result-subtitle">가격 데이터가 있는 종목과 훈련 조건을 선택합니다.</p>
          </div>
          <button type="button" className="training-icon-button" onClick={onClose} aria-label="닫기">
            <X size={18} />
          </button>
        </div>

        <div className="training-stock-search training-settings-top-row">
          <input
            className="input-control"
            value={q}
            onChange={(event) => {
              setQ(event.target.value);
              setStockPage(1);
            }}
            onKeyDown={(event) => {
              if (event.key === "Enter" && !event.nativeEvent.isComposing) {
                event.preventDefault();
                void searchStocks();
              }
            }}
            placeholder="종목명 또는 코드 검색"
          />
          <button className="btn btn-secondary" type="button" disabled={loading} onClick={() => void searchStocks()}>
            <Search size={16} /> 검색
          </button>
          <select
            className="select-control training-method-select"
            value={selectedMethodId ?? ""}
            onChange={(event) => setSelectedMethodId(event.target.value ? Number(event.target.value) : null)}
            aria-label="훈련기법 선택"
          >
            <option value="">선택 안함 / 자유훈련</option>
            {tradeMethods.map((method) => (
              <option key={method.id} value={method.id}>
                {method.method_name}
              </option>
            ))}
          </select>
        </div>
        {methodLoadError ? <p className="training-method-load-error">{methodLoadError}</p> : null}

        <div className="training-stock-list training-settings-stock-list">
          {stocks.length === 0 ? <EmptyState message="가격 데이터가 있는 종목이 없습니다." /> : null}
          {pagedStocks.map((stock) => (
            <button
              type="button"
              className={`training-stock-item ${selectedStock?.stock_id === stock.stock_id ? "selected" : ""}`}
              key={stock.stock_id}
              onClick={() => setSelectedStock(stock)}
            >
              <strong>{stock.stock_name}</strong>
              <span>{stock.stock_code} · {stock.market || "-"} · {fmtNumber(stock.price_count)}개 · {stock.first_date}~{stock.last_date}</span>
            </button>
          ))}
        </div>
        {stocks.length > STOCKS_PAGE_SIZE ? (
          <div className="training-stock-pagination">
            <button type="button" className="training-stock-page-button" disabled={safeStockPage <= 1} onClick={() => setStockPage((prev) => Math.max(1, prev - 1))}>
              이전
            </button>
            <span>{safeStockPage} / {totalStockPages}</span>
            <button type="button" className="training-stock-page-button" disabled={safeStockPage >= totalStockPages} onClick={() => setStockPage((prev) => Math.min(totalStockPages, prev + 1))}>
              다음
            </button>
          </div>
        ) : null}

        <div className="training-option-grid training-settings-option-grid">
          <label><span>초기자금</span><input className="input-control" type="number" min={1} value={initialCash} onChange={(event) => setInitialCash(Number(event.target.value) || 0)} /></label>
          <label><span>수수료율(%)</span><input className="input-control" type="number" min={0} step={0.01} value={feeRatePct} onChange={(event) => setFeeRatePct(Number(event.target.value) || 0)} /></label>
          <label><span>표시 일수</span><input className="input-control" type="number" min={1} max={400} value={displayDays} onChange={(event) => setDisplayDays(Number(event.target.value) || 80)} /></label>
          <label><span>이동평균선</span><input className="input-control" value={movingAverageText} onChange={(event) => setMovingAverageText(event.target.value)} /></label>
          <label><span>시작일</span><input className="input-control" type="date" value={startDate} onChange={(event) => setStartDate(event.target.value)} /></label>
          <label><span>종료일</span><input className="input-control" type="date" value={endDate} onChange={(event) => setEndDate(event.target.value)} /></label>
        </div>
        <p className="training-settings-help">선택한 종목의 수집 기간이 기본값으로 설정됩니다. 필요하면 직접 수정할 수 있습니다.</p>

        <div className="training-modal-actions">
          <button type="button" className="btn btn-secondary" onClick={onClose}>닫기</button>
          <button type="submit" className="btn btn-primary" disabled={!selectedStock || loading}>
            {loading ? "시작 중..." : "훈련 시작"}
          </button>
        </div>
      </form>
    </div>
  );
}

function ResultModal({ result, onClose }: { result: TrainingResult; onClose: () => void }) {
  const [review, setReview] = useState<SimulationReview | null>(null);
  const [gptPackage, setGptPackage] = useState<TrainingGptPackage | null>(null);
  const [reviewLoading, setReviewLoading] = useState(false);
  const [packageLoading, setPackageLoading] = useState(false);
  const [saveMessage, setSaveMessage] = useState("");
  const [reviewError, setReviewError] = useState("");

  useEffect(() => {
    const loadReview = async () => {
      setReviewLoading(true);
      setReviewError("");
      try {
        const response = await repositories.tradeTraining.getReview(result.session_id);
        setReview(response);
      } catch (error) {
        setReviewError(error instanceof Error ? error.message : "훈련 회고를 불러오지 못했습니다.");
      } finally {
        setReviewLoading(false);
      }
    };
    void loadReview();
  }, [result.session_id]);

  const updateReview = (field: keyof SimulationReview, value: string | number | null) => {
    setReview((prev) => {
      const base: SimulationReview = prev ?? {
        session_id: result.session_id,
        review_status: "미복기",
        self_review_text: "",
        gpt_prompt_text: "",
        gpt_review_text: "",
        improvement_point: "",
        next_training_goal: "",
        main_mistake: "",
        discipline_score: null,
        reviewed_at: null,
        created_at: null,
        updated_at: null,
      };
      return { ...base, [field]: value };
    });
  };

  const saveReview = async (nextPrompt?: string) => {
    if (!review) return;
    setReviewLoading(true);
    setSaveMessage("");
    setReviewError("");
    try {
      const response = await repositories.tradeTraining.saveReview(result.session_id, {
        review_status: review.review_status,
        self_review_text: review.self_review_text,
        gpt_prompt_text: nextPrompt ?? review.gpt_prompt_text,
        gpt_review_text: review.gpt_review_text,
        improvement_point: review.improvement_point,
        next_training_goal: review.next_training_goal,
        main_mistake: review.main_mistake,
        discipline_score: review.discipline_score,
      });
      setReview(response);
      setSaveMessage("훈련 복기를 저장했습니다.");
    } catch (error) {
      setReviewError(error instanceof Error ? error.message : "훈련 복기를 저장하지 못했습니다.");
    } finally {
      setReviewLoading(false);
    }
  };

  const buildGptPackage = async () => {
    setPackageLoading(true);
    setSaveMessage("");
    setReviewError("");
    try {
      if (review) {
        await repositories.tradeTraining.saveReview(result.session_id, {
          review_status: review.review_status,
          self_review_text: review.self_review_text,
          gpt_prompt_text: review.gpt_prompt_text,
          gpt_review_text: review.gpt_review_text,
          improvement_point: review.improvement_point,
          next_training_goal: review.next_training_goal,
          main_mistake: review.main_mistake,
          discipline_score: review.discipline_score,
        });
      }
      const response = await repositories.tradeTraining.getGptPackage(result.session_id);
      setGptPackage(response);
      if (review) {
        const saved = await repositories.tradeTraining.saveReview(result.session_id, {
          review_status: review.review_status,
          self_review_text: review.self_review_text,
          gpt_prompt_text: response.generated_prompt,
          gpt_review_text: review.gpt_review_text,
          improvement_point: review.improvement_point,
          next_training_goal: review.next_training_goal,
          main_mistake: review.main_mistake,
          discipline_score: review.discipline_score,
        });
        setReview(saved);
      }
      setSaveMessage("GPT 훈련복기 패키지를 생성했습니다.");
    } catch (error) {
      setReviewError(error instanceof Error ? error.message : "GPT 복기 패키지를 생성하지 못했습니다.");
    } finally {
      setPackageLoading(false);
    }
  };

  const copyPrompt = async () => {
    if (!gptPackage) return;
    try {
      await navigator.clipboard.writeText(gptPackage.generated_prompt);
      setSaveMessage("GPT 훈련복기 패키지를 복사했습니다.");
    } catch {
      setSaveMessage("복사에 실패했습니다. 아래 내용을 직접 선택해 복사해 주세요.");
    }
  };

  const hasLossTrades = result.losing_trade_count > 0;

  const summaryItems = [
    { label: "초기자금", value: fmtWon(result.initial_cash) },
    { label: "최종자산", value: fmtWon(result.final_total_asset) },
    { label: "누적손익", value: fmtSignedWon(result.total_profit), className: profitClass(result.total_profit) },
    { label: "누적수익률", value: fmtPercent(result.total_return_rate), className: profitClass(result.total_return_rate) },
    { label: "총 거래", value: `${fmtNumber(result.trade_count)}건` },
    { label: "승률", value: fmtPercent(result.win_rate) },
    { label: "평균수익", value: fmtPercent(result.average_profit_rate), className: "training-positive" },
    { label: "평균손실", value: hasLossTrades ? fmtPercent(result.average_loss_rate) : "-", className: "training-negative" },
    { label: "최대수익", value: fmtSignedWon(result.max_profit_amount), className: profitClass(result.max_profit_amount) },
    { label: "최대손실", value: hasLossTrades ? fmtSignedWon(result.max_loss_amount) : "-", className: hasLossTrades ? profitClass(result.max_loss_amount) : "" },
    { label: "평균보유일", value: result.average_holding_days === null ? "-" : `${fmtNumber(result.average_holding_days, 1)}일` },
    { label: "총 수수료", value: fmtWon(result.total_fees) },
  ];

  return (
    <div className="training-modal-backdrop" role="presentation">
      <div className="training-modal training-result-modal" role="dialog" aria-modal="true" aria-label="훈련 결과 리포트">
        <div className="training-modal-head">
          <div>
            <h3>훈련 결과 리포트</h3>
            <p className="training-result-subtitle">{result.stock_name || result.stock_code} · {result.start_date} ~ {result.current_date || result.end_date} · {result.status}</p>
          </div>
          <button type="button" className="training-icon-button" onClick={onClose} aria-label="닫기">
            <X size={18} />
          </button>
        </div>

        <div className="training-result-grid">
          {summaryItems.map((item) => (
            <div key={item.label}>
              <span>{item.label}</span>
              <strong className={item.className || ""}>{item.value}</strong>
            </div>
          ))}
        </div>

        <div className="training-result-grid training-result-small-grid">
          <div><span>매수 사유 입력률</span><strong>{fmtPercent(result.buy_reason_fill_rate)}</strong></div>
          <div><span>매도 사유 입력률</span><strong>{fmtPercent(result.sell_reason_fill_rate)}</strong></div>
          <div><span>매수 사유 품질</span><strong>{qualitySummaryText(result.buy_reason_quality_summary)}</strong></div>
          <div><span>매도 사유 품질</span><strong>{qualitySummaryText(result.sell_reason_quality_summary)}</strong></div>
          <div><span>매수/매도</span><strong>{fmtNumber(result.buy_count)} / {fmtNumber(result.sell_count)}</strong></div>
          <div><span>승/패/보합</span><strong>{fmtNumber(result.winning_trade_count)} / {fmtNumber(result.losing_trade_count)} / {fmtNumber(result.break_even_trade_count)}</strong></div>
          <div><span>부족한 매수 사유</span><strong>{fmtNumber(result.weak_buy_reason_count || 0)}건</strong></div>
          <div><span>부족한 매도 사유</span><strong>{fmtNumber(result.weak_sell_reason_count || 0)}건</strong></div>
        </div>

        <section className="training-result-section">
          <h4>자산 흐름</h4>
          <EquityCurveChart points={result.equity_curve} />
        </section>

        <section className="training-result-section">
          <h4>거래별 결과</h4>
          {result.trade_pairs.length === 0 ? <EmptyState message="아직 청산된 거래쌍이 없습니다." /> : (
            <div className="table-shell">
              <table className="data-table compact-table training-result-table">
                <thead>
                  <tr>
                    <th>매수일</th>
                    <th>매도일</th>
                    <th className="numeric-cell">보유일</th>
                    <th className="numeric-cell">매수가</th>
                    <th className="numeric-cell">매도가</th>
                    <th className="numeric-cell">수량</th>
                    <th className="numeric-cell">손익</th>
                    <th className="numeric-cell">수익률</th>
                    <th>매수 사유</th>
                    <th>매수 품질</th>
                    <th>매도 사유</th>
                    <th>매도 품질</th>
                  </tr>
                </thead>
                <tbody>
                  {result.trade_pairs.map((pair, idx) => {
                    const buyReview = pair.buy_method_review || null;
                    const sellReview = pair.sell_method_review || null;
                    return (
                      <Fragment key={`${pair.buy_date}-${pair.sell_date}-${idx}`}>
                        <tr>
                          <td>{pair.buy_date}</td>
                          <td>{pair.sell_date}</td>
                          <td className="numeric-cell">{fmtNumber(pair.holding_days)}</td>
                          <td className="numeric-cell">{fmtWon(pair.buy_price)}</td>
                          <td className="numeric-cell">{fmtWon(pair.sell_price)}</td>
                          <td className="numeric-cell">{fmtNumber(pair.quantity)}</td>
                          <td className={`numeric-cell ${profitClass(pair.profit_amount)}`}>{fmtSignedWon(pair.profit_amount)}</td>
                          <td className={`numeric-cell ${profitClass(pair.profit_rate)}`}>{fmtPercent(pair.profit_rate)}</td>
                          <td>{pair.buy_reason || "-"}</td>
                          <td><ReasonQualityBadge grade={pair.buy_reason_quality} guide={pair.buy_reason_quality_guide} /></td>
                          <td>{pair.sell_reason || "-"}</td>
                          <td><ReasonQualityBadge grade={pair.sell_reason_quality} guide={pair.sell_reason_quality_guide} /></td>
                        </tr>
                        <tr className="training-method-review-result-row">
                          <td colSpan={12}>
                            <div className="training-method-review-result">
                              <div>
                                <strong>매수 기준 복기</strong>
                                <span>선택 카드: {buyReview?.selected_template || "미작성"}</span>
                                <span>매수 유형: {tagLabels(BUY_REVIEW_TAGS, buyReview?.entry_type_tags)}</span>
                                <span>기법 기준: {optionLabel(BUY_METHOD_FIT_OPTIONS, buyReview?.method_fit)}</span>
                                <span>실패 기준: {writtenFlag(buyReview?.failure_criteria)}</span>
                                <span>손절 기준: {writtenFlag(buyReview?.stop_loss_rule)}</span>
                                <span>목표/청산 기준: {writtenFlag(buyReview?.target_exit_rule)}</span>
                                <span>추가매수 기준: {optionLabel(ADD_BUY_PLAN_OPTIONS, buyReview?.add_buy_plan_type)}</span>
                              </div>
                              <div>
                                <strong>매도 기준 복기</strong>
                                <span>선택 카드: {sellReview?.selected_template || "미작성"}</span>
                                <span>매도 유형: {tagLabels(SELL_REVIEW_TAGS, sellReview?.exit_type_tags)}</span>
                                <span>기법 기준 매도: {optionLabel(SELL_METHOD_FIT_OPTIONS, sellReview?.method_exit_fit)}</span>
                                <span>최초 계획 일치: {optionLabel(PLAN_ALIGNMENT_OPTIONS, sellReview?.plan_alignment)}</span>
                                <span>매도조건 근거: {writtenFlag(sellReview?.matched_exit_rules)}</span>
                              </div>
                            </div>
                          </td>
                        </tr>
                      </Fragment>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </section>

        <section className="training-result-section training-review-section">
          <h4>훈련 회고</h4>
          <p className="training-result-help">먼저 자기 회고와 다음 훈련 목표를 적으면 GPT 복기 패키지가 더 좋아집니다. GPT 복기에서 나온 핵심 교훈을 바탕으로 다음 훈련에서 반드시 지킬 행동 기준을 적어주세요.</p>
          {reviewLoading && !review ? <p className="text-sm text-muted">훈련 회고를 불러오는 중입니다.</p> : null}
          {reviewError ? <div className="inline-result inline-error">{reviewError}</div> : null}
          {review ? (
            <>
              <div className="training-review-grid">
                <label>
                  <span>복기 상태</span>
                  <select className="select-control" value={review.review_status} onChange={(event) => updateReview("review_status", event.target.value)}>
                    <option value="미복기">미복기</option>
                    <option value="복기완료">복기완료</option>
                  </select>
                </label>
                <label>
                  <span>핵심 실수</span>
                  <select className="select-control" value={review.main_mistake} onChange={(event) => updateReview("main_mistake", event.target.value)}>
                    <option value="">선택 안 함</option>
                    <option value="추격매수">추격매수</option>
                    <option value="손절 지연">손절 지연</option>
                    <option value="조기 매도">조기 매도</option>
                    <option value="근거 부족 매수">근거 부족 매수</option>
                    <option value="비중 과다">비중 과다</option>
                    <option value="매도 기준 부재">매도 기준 부재</option>
                    <option value="감정 개입">감정 개입</option>
                    <option value="기타">기타</option>
                  </select>
                </label>
                <label>
                  <span>원칙 준수 점수</span>
                  <input
                    className="input-control"
                    type="number"
                    min={0}
                    max={100}
                    value={review.discipline_score ?? ""}
                    onChange={(event) => updateReview("discipline_score", event.target.value === "" ? null : Number(event.target.value))}
                  />
                </label>
              </div>
              <div className="training-review-text-grid">
                <label><span>자기 회고</span><textarea className="textarea-control" value={review.self_review_text} onChange={(event) => updateReview("self_review_text", event.target.value)} /></label>
                <label><span>개선할 점</span><textarea className="textarea-control" value={review.improvement_point} onChange={(event) => updateReview("improvement_point", event.target.value)} /></label>
                <label>
                  <span>다음 훈련 목표</span>
                  <textarea
                    className="textarea-control"
                    value={review.next_training_goal}
                    onChange={(event) => updateReview("next_training_goal", event.target.value)}
                    placeholder={"매수 전 실패 기준을 반드시 작성한다.\n매도 사유에 '익절'만 쓰지 않는다.\n추가매수는 사전 계획이 있을 때만 실행한다.\n손절 기준 없이 매수하지 않는다.\n1회 매수 비중을 10% 이하로 제한한다."}
                  />
                </label>
                <label><span>GPT 복기 결과</span><textarea className="textarea-control" value={review.gpt_review_text} onChange={(event) => updateReview("gpt_review_text", event.target.value)} /></label>
              </div>
              <div className="training-result-actions">
                <button type="button" className="btn btn-secondary" disabled={reviewLoading} onClick={() => void saveReview()}>
                  훈련 복기 저장
                </button>
                <button type="button" className="btn btn-primary" disabled={packageLoading} onClick={() => void buildGptPackage()}>
                  GPT 훈련복기 패키지 생성
                </button>
              </div>
            </>
          ) : null}
        </section>

        <section className="training-result-section training-gpt-section">
          <h4>GPT 훈련복기</h4>
          <div className="training-result-note">
            GPT 자동 호출은 하지 않습니다. 아래 요청문을 복사해 GPT에 붙여넣어 사용하세요. 이 기능은 투자 조언이 아니라 훈련 복기와 습관 교정을 위한 기능입니다.
          </div>
          {gptPackage ? (
            <div className="training-gpt-package">
              <div className="training-gpt-package-head">
                <strong>{gptPackage.package_title}</strong>
                <button type="button" className="btn btn-secondary" onClick={() => void copyPrompt()}>복사</button>
              </div>
              <textarea className="textarea-control training-gpt-prompt" value={gptPackage.generated_prompt} readOnly />
            </div>
          ) : (
            <p className="training-result-help">GPT 훈련복기 패키지 생성 버튼을 누르면 결과 리포트와 훈련 회고를 묶은 요청문이 생성됩니다.</p>
          )}
        </section>

        {saveMessage ? <div className="inline-result">{saveMessage}</div> : null}
      </div>
    </div>
  );
}

function OrderModal({
  mode,
  detail,
  onClose,
  onSubmit,
}: {
  mode: OrderMode;
  detail: TrainingSessionDetail;
  onClose: () => void;
  onSubmit: (payload: TrainingOrderRequest) => Promise<void>;
}) {
  const candle = detail.current_candle;
  const close = Number(candle?.close || 0);
  const defaultPercent = mode === "BUY" ? 10 : 100;
  const [price, setPrice] = useState(close);
  const [percent, setPercent] = useState(defaultPercent);
  const [quantity, setQuantity] = useState(1);
  const [reason, setReason] = useState("");
  const [activeOrderTab, setActiveOrderTab] = useState<"order" | "review">("order");
  const [templateMessage, setTemplateMessage] = useState("");
  const [methodReview, setMethodReview] = useState<TrainingMethodReview>(() => ({
    add_buy_plan_type: "none",
  }));
  const [submitting, setSubmitting] = useState(false);
  const feeRate = Number(detail.session.options?.fee_rate || 0);
  const amount = price * quantity;
  const fee = amount * feeRate;
  const expectedProfit = mode === "SELL" ? (price - detail.session.avg_price) * quantity - fee : null;
  const expectedProfitRate = mode === "SELL" && detail.session.avg_price > 0 ? ((price - detail.session.avg_price) / detail.session.avg_price) * 100 : null;
  const totalCost = amount + fee;
  const remainingCash = detail.session.cash - totalCost;
  const maxAffordableQuantity =
    mode === "BUY"
      ? Math.floor(detail.session.cash / Math.max(1, price * (1 + feeRate)))
      : detail.session.position_qty;
  const invalidOrder =
    quantity < 1 ||
    price < 1 ||
    (mode === "BUY" && totalCost > detail.session.cash) ||
    (mode === "SELL" && quantity > detail.session.position_qty);

  const calculateQuantity = (nextPercent: number, nextPrice = price) => {
    if (mode === "BUY") {
      const targetAmount = detail.session.initial_cash * (nextPercent / 100);
      const cashLimitedAmount = Math.min(targetAmount, detail.session.cash);
      return Math.max(0, Math.floor(cashLimitedAmount / Math.max(1, nextPrice * (1 + feeRate))));
    }
    return Math.max(0, Math.floor(detail.session.position_qty * (nextPercent / 100)));
  };

  useEffect(() => {
    setQuantity(calculateQuantity(percent, price));
  }, [percent, price, mode, feeRate]);

  const onQuantityChange = (nextQuantity: number) => {
    const safeQuantity = Math.max(0, Math.min(nextQuantity || 0, maxAffordableQuantity));
    setQuantity(safeQuantity);
    if (mode === "BUY") {
      const nextPercent = Math.min(100, Math.round(((safeQuantity * price) / Math.max(1, detail.session.initial_cash)) * 100));
      setPercent(nextPercent);
    } else {
      const nextPercent = Math.min(100, Math.round((safeQuantity / Math.max(1, detail.session.position_qty)) * 100));
      setPercent(nextPercent);
    }
  };

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setSubmitting(true);
    try {
      await onSubmit({ price, quantity, reason: reason.trim() || null, method_review: hasMethodReview(methodReview) ? methodReview : null });
    } finally {
      setSubmitting(false);
    }
  };

  const quickPercents = mode === "BUY" ? [10, 20, 30, 50, 100] : [25, 50, 100];
  const updateMethodReview = (field: keyof TrainingMethodReview, value: string | string[]) => {
    setMethodReview((prev) => ({ ...prev, [field]: value }));
  };
  const toggleReviewTag = (field: "entry_type_tags" | "exit_type_tags", value: string) => {
    setMethodReview((prev) => {
      const current = Array.isArray(prev[field]) ? [...(prev[field] || [])] : [];
      const next = current.includes(value) ? current.filter((item) => item !== value) : [...current, value];
      return { ...prev, [field]: next };
    });
  };
  const weakSellReason = mode === "SELL" && ["익절", "손절"].includes(reason.trim());
  const missingBuyRiskRule = mode === "BUY" && activeOrderTab === "review" && (!methodReview.failure_criteria?.trim() || !methodReview.stop_loss_rule?.trim());
  const applyReviewTemplate = (template: { title: string; review: TrainingMethodReview }) => {
    setMethodReview((prev) => {
      if (template.title === "직접 입력") {
        return mode === "BUY"
          ? { selected_template: "직접 입력", entry_type_tags: [], method_fit: "", add_buy_plan_type: "none" }
          : { selected_template: "직접 입력", exit_type_tags: [], method_exit_fit: "", plan_alignment: "" };
      }
      return { ...template.review };
    });
    setTemplateMessage(
      template.title === "직접 입력"
        ? "직접 입력 카드가 선택되었습니다. 필요한 기준을 자유롭게 작성해 주세요."
        : "선택한 카드의 기본 복기 문구가 입력되었습니다. 실제 판단과 다르면 수정해 주세요."
    );
  };

  return (
    <div className="training-modal-backdrop" role="presentation">
      <form className="training-modal training-order-modal" onSubmit={submit}>
        <div className="training-modal-head">
          <h3>{mode === "BUY" ? "매수 주문" : "매도 주문"}</h3>
          <button type="button" className="training-icon-button" onClick={onClose} aria-label="닫기">
            <X size={18} />
          </button>
        </div>

        <div className="training-modal-market">
          <strong>{detail.session.current_date}</strong>
          <span>시가 {fmtWon(candle?.open)} · 고가 {fmtWon(candle?.high)} · 저가 {fmtWon(candle?.low)} · 종가 {fmtWon(candle?.close)}</span>
        </div>

        <div className="training-order-tabs" role="tablist" aria-label="주문 입력 구분">
          <button type="button" className={activeOrderTab === "order" ? "active" : ""} onClick={() => setActiveOrderTab("order")}>주문 입력</button>
          <button type="button" className={activeOrderTab === "review" ? "active" : ""} onClick={() => setActiveOrderTab("review")}>기법 기준 복기</button>
        </div>

        {activeOrderTab === "order" ? (
          <div className="training-order-tab-panel">
            {mode === "SELL" ? (
              <div className="training-order-summary">
                <div><span>보유수량</span><strong>{fmtNumber(detail.session.position_qty)}주</strong></div>
                <div><span>평균단가</span><strong>{fmtWon(detail.session.avg_price)}</strong></div>
              </div>
            ) : null}

            <div className="training-order-grid">
              <label>
                <span>주문가격</span>
                <input className="input-control" type="number" min={1} value={price} onChange={(event) => setPrice(Number(event.target.value) || 0)} />
              </label>
              <label>
                <span>주문수량</span>
                <input className="input-control" type="number" min={0} max={maxAffordableQuantity} value={quantity} onChange={(event) => onQuantityChange(Number(event.target.value) || 0)} />
              </label>
            </div>

            <div className="training-slider-block">
              <div className="training-slider-head">
                <span>{mode === "BUY" ? `초기자금 기준 ${percent}%` : `보유수량 기준 ${percent}%`}</span>
                <strong>{fmtNumber(quantity)}주</strong>
              </div>
              <input className="training-order-slider" type="range" min={0} max={100} step={1} value={percent} onChange={(event) => setPercent(Number(event.target.value))} />
              <div className="training-quick-percent-row">
                {quickPercents.map((value) => (
                  <button type="button" className={value === percent ? "selected" : ""} key={value} onClick={() => setPercent(value)}>
                    {value}%
                  </button>
                ))}
              </div>
            </div>

            <div className="training-order-summary">
              <div><span>{mode === "BUY" ? "주문금액" : "예상 매도금액"}</span><strong>{fmtWon(amount)}</strong></div>
              <div><span>수수료</span><strong>{fmtWon(fee)}</strong></div>
              {mode === "BUY" ? <div><span>총 필요금액</span><strong>{fmtWon(totalCost)}</strong></div> : null}
              {mode === "BUY" ? <div><span>주문 후 예상 현금</span><strong className={profitClass(remainingCash)}>{fmtWon(remainingCash)}</strong></div> : null}
              {mode === "SELL" ? <div><span>예상 실현손익</span><strong className={profitClass(expectedProfit)}>{fmtSignedWon(expectedProfit)}</strong></div> : null}
              {mode === "SELL" ? <div><span>예상 실현수익률</span><strong className={profitClass(expectedProfitRate)}>{fmtPercent(expectedProfitRate)}</strong></div> : null}
            </div>

            {mode === "BUY" && totalCost > detail.session.cash ? (
              <div className="inline-result inline-error">수수료를 포함한 총 필요금액이 현재 현금을 초과합니다.</div>
            ) : null}
            {mode === "SELL" && quantity > detail.session.position_qty ? (
              <div className="inline-result inline-error">매도 수량이 현재 보유수량을 초과합니다.</div>
            ) : null}

            <label className="training-reason-field">
              <span>{mode === "BUY" ? "매수 사유" : "매도 사유"}</span>
              <textarea className="textarea-control" value={reason} onChange={(event) => setReason(event.target.value)} />
            </label>

            <div className="training-method-review-summary-badge">{methodReviewSummary(mode, methodReview)}</div>
          </div>
        ) : (
          <div className="training-method-review-panel training-method-review-tab-panel">
            <p className="training-result-help">
              {mode === "BUY"
                ? "카드는 매수 판단 기록을 빠르게 남기기 위한 템플릿입니다. 실제 판단과 다르면 선택 후 수정하세요."
                : "카드는 매도 판단 기록을 빠르게 남기기 위한 템플릿입니다. 실제 판단과 다르면 선택 후 수정하세요."}
            </p>
            <div className="training-review-template-grid">
              {(mode === "BUY" ? BUY_REVIEW_TEMPLATES : SELL_REVIEW_TEMPLATES).map((template) => (
                <button
                  type="button"
                  key={template.title}
                  className={methodReview.selected_template === template.title ? "active" : ""}
                  onClick={() => applyReviewTemplate(template)}
                >
                  <strong>{template.title}</strong>
                  <span>{template.description}</span>
                </button>
              ))}
            </div>
            {templateMessage ? <div className="inline-result inline-warning">{templateMessage}</div> : null}
            <div className="training-method-review-body">
              {mode === "BUY" ? (
                <>
                  <div className="training-review-chip-section">
                    <span>이번 매수 유형</span>
                    <div className="training-review-chip-row">
                      {BUY_REVIEW_TAGS.map((tag) => (
                        <button
                          type="button"
                          key={tag.value}
                          className={(methodReview.entry_type_tags || []).includes(tag.value) ? "selected" : ""}
                          onClick={() => toggleReviewTag("entry_type_tags", tag.value)}
                        >
                          {tag.label}
                        </button>
                      ))}
                    </div>
                  </div>
                  <label>
                    <span>매매기법 기준 충족 여부</span>
                    <select className="select-control" value={methodReview.method_fit || ""} onChange={(event) => updateMethodReview("method_fit", event.target.value)}>
                      {BUY_METHOD_FIT_OPTIONS.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
                    </select>
                    <small>현재 선택한 매매기법 기준으로 이번 매수가 어느 정도 적합했는지 기록합니다.</small>
                  </label>
                  <label><span>근거가 된 매수조건</span><textarea className="textarea-control" value={methodReview.matched_entry_rules || ""} onChange={(event) => updateMethodReview("matched_entry_rules", event.target.value)} placeholder="20일선 돌파, 전고점 돌파, 거래량 증가" /></label>
                  <label><span>주의 또는 위반 조건</span><textarea className="textarea-control" value={methodReview.risk_or_violation_notes || ""} onChange={(event) => updateMethodReview("risk_or_violation_notes", event.target.value)} placeholder="예) 60일선 아래라 중기 추세는 아직 불안함" /></label>
                  <label><span>실패 기준</span><textarea className="textarea-control" value={methodReview.failure_criteria || ""} onChange={(event) => updateMethodReview("failure_criteria", event.target.value)} placeholder="예) 20일선 재이탈 시 실패로 본다." /></label>
                  <label><span>손절 기준</span><textarea className="textarea-control" value={methodReview.stop_loss_rule || ""} onChange={(event) => updateMethodReview("stop_loss_rule", event.target.value)} placeholder="예) -5% 도달 시 전량 손절" /></label>
                  <label><span>목표 / 청산 기준</span><textarea className="textarea-control" value={methodReview.target_exit_rule || ""} onChange={(event) => updateMethodReview("target_exit_rule", event.target.value)} placeholder="예) +5% 도달 시 1차 매도" /></label>
                  <label>
                    <span>추가매수 기준</span>
                    <select className="select-control" value={methodReview.add_buy_plan_type || "none"} onChange={(event) => updateMethodReview("add_buy_plan_type", event.target.value)}>
                      {ADD_BUY_PLAN_OPTIONS.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
                    </select>
                  </label>
                  <label><span>추가매수 조건</span><textarea className="textarea-control" value={methodReview.add_buy_condition || ""} onChange={(event) => updateMethodReview("add_buy_condition", event.target.value)} placeholder="예) 전고점 돌파 후 안착 시 1회 추가매수" /></label>
                  <div className="training-method-review-two-col">
                    <label><span>추가매수 후 총 비중 한도</span><input className="input-control" value={methodReview.max_position_plan || ""} onChange={(event) => updateMethodReview("max_position_plan", event.target.value)} placeholder="예) 총 비중 20% 이하" /></label>
                    <label><span>추가매수 후 손절 기준</span><input className="input-control" value={methodReview.add_buy_stop_loss_rule || ""} onChange={(event) => updateMethodReview("add_buy_stop_loss_rule", event.target.value)} placeholder="예) 평균단가 -5%" /></label>
                  </div>
                  {missingBuyRiskRule ? <div className="inline-result inline-warning">실패 기준 또는 손절 기준이 비어 있습니다. 매수는 가능하지만 GPT 복기에서 손실 관리 평가가 제한될 수 있습니다.</div> : null}
                </>
              ) : (
                <>
                  <div className="training-review-chip-section">
                    <span>이번 매도 유형</span>
                    <div className="training-review-chip-row">
                      {SELL_REVIEW_TAGS.map((tag) => (
                        <button
                          type="button"
                          key={tag.value}
                          className={(methodReview.exit_type_tags || []).includes(tag.value) ? "selected" : ""}
                          onClick={() => toggleReviewTag("exit_type_tags", tag.value)}
                        >
                          {tag.label}
                        </button>
                      ))}
                    </div>
                  </div>
                  <label>
                    <span>매매기법 기준 매도 여부</span>
                    <select className="select-control" value={methodReview.method_exit_fit || ""} onChange={(event) => updateMethodReview("method_exit_fit", event.target.value)}>
                      {SELL_METHOD_FIT_OPTIONS.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
                    </select>
                  </label>
                  <label><span>근거가 된 매도조건</span><textarea className="textarea-control" value={methodReview.matched_exit_rules || ""} onChange={(event) => updateMethodReview("matched_exit_rules", event.target.value)} placeholder="목표 수익률 도달, 전고점 저항 도달, 5일선 이탈" /></label>
                  <label>
                    <span>최초 매수 계획과 일치 여부</span>
                    <select className="select-control" value={methodReview.plan_alignment || ""} onChange={(event) => updateMethodReview("plan_alignment", event.target.value)}>
                      {PLAN_ALIGNMENT_OPTIONS.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
                    </select>
                  </label>
                  {weakSellReason ? <div className="inline-result inline-warning">‘익절’ 또는 ‘손절’은 결과입니다. 복기 품질을 높이려면 왜 이 시점에서 매도했는지 적어주세요. 예: 목표가 도달, 저항선 도달, 5일선 이탈, 거래량 둔화, 급등 후 윗꼬리, 전고점 돌파 실패</div> : null}
                  <label><span>매도 사유 상세</span><textarea className="textarea-control" value={methodReview.exit_reason_detail || ""} onChange={(event) => updateMethodReview("exit_reason_detail", event.target.value)} placeholder="예) 목표 수익률 초과 후 급등 부담으로 전량 매도" /></label>
                  <label><span>매도 후 복기 메모</span><textarea className="textarea-control" value={methodReview.after_review_memo || ""} onChange={(event) => updateMethodReview("after_review_memo", event.target.value)} placeholder="예) 계획대로 매도했지만 분할매도 기준이 부족했다." /></label>
                </>
              )}
            </div>
          </div>
        )}

        <div className="training-modal-actions">
          <button type="button" className="btn btn-secondary" onClick={onClose}>취소</button>
          <button type="submit" className={mode === "BUY" ? "btn btn-primary" : "btn btn-danger"} disabled={submitting || invalidOrder}>
            {submitting ? "처리 중..." : mode === "BUY" ? "매수 실행" : "매도 실행"}
          </button>
        </div>
      </form>
    </div>
  );
}

function TrainingKpiStrip({
  detail,
  showAvgPriceLine,
  onToggleAvgPriceLine,
}: {
  detail: TrainingSessionDetail;
  showAvgPriceLine: boolean;
  onToggleAvgPriceLine: () => void;
}) {
  const positionProfit = detail.account.position_profit ?? detail.account.unrealized_profit;
  const positionReturnRate = detail.account.position_return_rate ?? detail.account.unrealized_return_rate;
  const realizedProfit = detail.account.realized_profit ?? detail.session.realized_profit;
  const items = [
    { label: "현재가", value: fmtWon(detail.account.current_price ?? detail.current_candle?.close) },
    { label: "보유수량", value: `${fmtNumber(detail.session.position_qty)}주` },
    {
      label: "평균단가",
      value: fmtWon(detail.session.avg_price),
      hint: showAvgPriceLine ? "차트표시중" : "차트표시",
      onClick: onToggleAvgPriceLine,
      active: showAvgPriceLine,
      disabled: detail.session.position_qty <= 0 || detail.session.avg_price <= 0,
    },
    { label: "현재포지션손익", value: fmtSignedWon(positionProfit), className: profitClass(positionProfit) },
    { label: "현재포지션수익률", value: fmtPercent(positionReturnRate), className: profitClass(positionReturnRate) },
    { label: "실현손익", value: fmtSignedWon(realizedProfit), className: profitClass(realizedProfit) },
  ];
  return (
    <div className="training-kpi-strip">
      {items.map((item) => (
        <button
          type="button"
          key={item.label}
          className={`training-kpi-card ${item.active ? "active" : ""} ${item.disabled ? "disabled" : ""}`}
          onClick={item.onClick}
          disabled={item.disabled}
          tabIndex={item.onClick ? 0 : -1}
          aria-disabled={item.disabled || !item.onClick}
        >
          <span>{item.label}</span>
          <strong className={item.className || ""}>{item.value}</strong>
          {item.hint ? <small>{item.hint}</small> : null}
        </button>
      ))}
    </div>
  );
}

function TrainingChartSummary({
  detail,
  onNext,
  nextDisabled,
}: {
  detail: TrainingSessionDetail;
  onNext: () => void;
  nextDisabled: boolean;
}) {
  const items = [
    { label: "현재투자금", value: fmtWon(detail.account.evaluation_amount) },
    { label: "남은투자금", value: fmtWon(detail.session.cash) },
    { label: "누적손익", value: fmtSignedWon(detail.account.total_profit), className: profitClass(detail.account.total_profit) },
    { label: "누적수익률", value: fmtPercent(detail.account.total_return_rate), className: profitClass(detail.account.total_return_rate) },
  ];
  return (
    <div className="training-bottom-summary-row">
      <div className="training-bottom-kpis">
        {items.map((item) => (
          <div className="training-bottom-kpi" key={item.label}>
            <span>{item.label}</span>
            <strong className={item.className || ""}>{item.value}</strong>
          </div>
        ))}
      </div>
      <button className="training-bottom-next-button" type="button" disabled={nextDisabled} onClick={onNext}>
        <StepForward size={15} /> 다음
      </button>
    </div>
  );
}

function TrainingMethodPrinciplesModal({
  method,
  onSave,
  onClose,
}: {
  method: TradeMethod;
  onSave: (methodId: number, payload: Partial<TradeMethodSaveRequest>) => Promise<TradeMethod>;
  onClose: () => void;
}) {
  const [editForm, setEditForm] = useState<TrainingMethodPrinciplesForm>(() => methodPrinciplesFormFromMethod(method));
  const [isEditMode, setIsEditMode] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [saveError, setSaveError] = useState("");
  const tabs: TrainingMethodPrinciplesTab[] = [
    { key: "core_concept", label: "핵심개념", value: tradeMethodValue(method, "core_concept", "description"), editableField: "core_concept" },
    { key: "buy_condition", label: "매수조건", value: tradeMethodValue(method, "buy_condition", "entry_rule"), editableField: "buy_condition" },
    {
      key: "sell_condition",
      label: "매도조건",
      value: tradeMethodValue(method, "sell_condition", "exit_rule", "take_profit_rule"),
      editableField: "sell_condition",
    },
    { key: "stop_loss_rule", label: "실패패턴", value: tradeMethodValue(method, "stop_loss_rule"), editableField: "stop_loss_rule" },
    { key: "checklist", label: "체크리스트", value: tradeMethodValue(method, "checklist"), editableField: "checklist" },
    { key: "lessons", label: "최근 복기 교훈", value: "최근 GPT 복기에서 도출된 교훈이 여기에 표시됩니다." },
  ];
  const [activeTab, setActiveTab] = useState(tabs[0].key);
  const active = tabs.find((tab) => tab.key === activeTab) || tabs[0];

  useEffect(() => {
    setEditForm(methodPrinciplesFormFromMethod(method));
  }, [method]);

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return;
      if (isEditMode) {
        setEditForm(methodPrinciplesFormFromMethod(method));
        setIsEditMode(false);
        setSaveError("");
        return;
      }
      onClose();
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isEditMode, method, onClose]);

  const handleBackdropClose = () => {
    if (isSaving) return;
    onClose();
  };

  const handleEdit = () => {
    setEditForm(methodPrinciplesFormFromMethod(method));
    setSaveError("");
    setIsEditMode(true);
  };

  const handleCancelEdit = () => {
    setEditForm(methodPrinciplesFormFromMethod(method));
    setSaveError("");
    setIsEditMode(false);
  };

  const handleChangePrinciple = (field: TrainingMethodEditableField, value: string) => {
    setEditForm((prev) => ({ ...prev, [field]: value }));
  };

  const handleSave = async () => {
    setIsSaving(true);
    setSaveError("");
    const buyCondition = normalizePrincipleText(editForm.buy_condition);
    const sellCondition = normalizePrincipleText(editForm.sell_condition);
    try {
      await onSave(method.id, {
        core_concept: normalizePrincipleText(editForm.core_concept),
        buy_condition: buyCondition,
        entry_rule: buyCondition,
        sell_condition: sellCondition,
        exit_rule: sellCondition,
        stop_loss_rule: normalizePrincipleText(editForm.stop_loss_rule),
        checklist: normalizePrincipleText(editForm.checklist),
      });
      setIsEditMode(false);
    } catch (nextError) {
      setSaveError(nextError instanceof Error ? nextError.message : "매매원칙을 저장하지 못했습니다.");
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div className="training-modal-backdrop" role="presentation" onMouseDown={handleBackdropClose}>
      <div
        className="training-modal training-principles-modal"
        role="dialog"
        aria-modal="true"
        aria-label="매매원칙 보기"
        onMouseDown={(event) => event.stopPropagation()}
      >
        <div className="training-modal-head">
          <div>
            <h3>{isEditMode ? "매매원칙 수정" : "매매원칙 보기"}</h3>
            <p className="training-result-subtitle">{method.method_name}</p>
          </div>
          <div className="training-principles-head-actions">
            {isEditMode ? (
              <>
                <button type="button" className="btn btn-secondary" disabled={isSaving} onClick={handleCancelEdit}>
                  취소
                </button>
                <button type="button" className="btn btn-primary" disabled={isSaving} onClick={handleSave}>
                  {isSaving ? "저장 중..." : "저장"}
                </button>
              </>
            ) : (
              <button type="button" className="btn btn-primary" onClick={handleEdit}>
                수정
              </button>
            )}
            <button type="button" className="training-icon-button" disabled={isSaving} onClick={onClose} aria-label="닫기">
              <X size={18} />
            </button>
          </div>
        </div>

        {saveError ? <div className="inline-result inline-error">{saveError}</div> : null}

        <div className="training-principles-tabs" role="tablist" aria-label="매매원칙 구분">
          {tabs.map((tab) => (
            <button
              key={tab.key}
              type="button"
              className={activeTab === tab.key ? "active" : ""}
              onClick={() => setActiveTab(tab.key)}
              role="tab"
              aria-selected={activeTab === tab.key}
            >
              {tab.label}
            </button>
          ))}
        </div>

        <div className="training-principles-content">
          <h4>{active.label}</h4>
          {isEditMode && active.editableField ? (
            <textarea
              className="training-principles-editor"
              value={editForm[active.editableField]}
              onChange={(event) => handleChangePrinciple(active.editableField!, event.target.value)}
              aria-label={`${active.label} 수정`}
            />
          ) : (
            <>
              <pre>{cleanRuleText(active.editableField && isEditMode ? editForm[active.editableField] : active.value)}</pre>
              {isEditMode && !active.editableField ? <p className="training-principles-readonly-note">최근 복기 교훈은 별도 복기 결과 영역에서 관리됩니다.</p> : null}
            </>
          )}
        </div>
      </div>
    </div>
  );
}

function TradeTrainingPage() {
  const [q, setQ] = useState("");
  const [stocks, setStocks] = useState<TrainingStockItem[]>([]);
  const [selectedStock, setSelectedStock] = useState<TrainingStockItem | null>(null);
  const [tradeMethods, setTradeMethods] = useState<TradeMethod[]>([]);
  const [selectedMethodId, setSelectedMethodId] = useState<number | null>(null);
  const [methodLoadError, setMethodLoadError] = useState("");
  const [initialCash, setInitialCash] = useState(50_000_000);
  const [feeRatePct, setFeeRatePct] = useState(0.1);
  const [displayDays, setDisplayDays] = useState(80);
  const [movingAverageText, setMovingAverageText] = useState(DEFAULT_MA_TEXT);
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [detail, setDetail] = useState<TrainingSessionDetail | null>(null);
  const [result, setResult] = useState<TrainingResult | null>(null);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [resultLoading, setResultLoading] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [orderMode, setOrderMode] = useState<OrderMode | null>(null);
  const [showAvgPriceLine, setShowAvgPriceLine] = useState(false);
  const [scrollTargetDate, setScrollTargetDate] = useState<string | null>(null);
  const [highlightedTradeDate, setHighlightedTradeDate] = useState<string | null>(null);
  const [highlightedTradeId, setHighlightedTradeId] = useState<number | null>(null);
  const [showMethodPrinciples, setShowMethodPrinciples] = useState(false);

  const selectedTrainingMethod = useMemo(
    () => tradeMethods.find((method) => method.id === selectedMethodId) ?? null,
    [tradeMethods, selectedMethodId]
  );

  const loadStocks = async (keyword = q) => {
    setLoading(true);
    setError("");
    try {
      const response = await repositories.tradeTraining.listStocks({ q: keyword.trim() || undefined, limit: 30 });
      setStocks(response.items);
      setSelectedStock((prev) => prev ?? response.items[0] ?? null);
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : "훈련 가능 종목을 불러오지 못했습니다.");
      setStocks([]);
    } finally {
      setLoading(false);
    }
  };

  const loadTradeMethods = async () => {
    setMethodLoadError("");
    try {
      const rows = await repositories.tradeJournals.listTradeMethods({ is_active: 1 });
      setTradeMethods(rows);
      setSelectedMethodId((prev) => (prev && rows.some((method) => method.id === prev) ? prev : null));
    } catch (nextError) {
      setTradeMethods([]);
      setSelectedMethodId(null);
      setMethodLoadError(
        nextError instanceof Error ? nextError.message : "매매기법 목록을 불러오지 못했습니다. 자유훈련으로 시작할 수 있습니다."
      );
    }
  };

  useEffect(() => {
    void loadStocks("");
    void loadTradeMethods();
  }, []);

  useEffect(() => {
    if (!selectedStock) return;
    setStartDate(selectedStock.first_date || "");
    setEndDate(selectedStock.last_date || "");
  }, [selectedStock?.stock_id]);

  useEffect(() => {
    if (detail && (detail.session.position_qty <= 0 || detail.session.avg_price <= 0)) {
      setShowAvgPriceLine(false);
    }
  }, [detail?.session.position_qty, detail?.session.avg_price]);

  const startSession = async () => {
    if (!selectedStock) return;
    setLoading(true);
    setError("");
    setMessage("");
    setResult(null);
    try {
      const response = await repositories.tradeTraining.createSession({
        stock_code: selectedStock.stock_code,
        method_id: selectedMethodId,
        initial_cash: initialCash,
        fee_rate: feeRatePct / 100,
        display_days: displayDays,
        start_date: startDate || null,
        end_date: endDate || null,
        moving_averages: normalizeMas(movingAverageText),
      });
      setDetail(response);
      setShowAvgPriceLine(false);
      setScrollTargetDate(null);
      setHighlightedTradeDate(null);
      setHighlightedTradeId(null);
      setShowMethodPrinciples(false);
      setSettingsOpen(false);
      setMessage("훈련 세션을 시작했습니다.");
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : "훈련 세션을 시작하지 못했습니다.");
    } finally {
      setLoading(false);
    }
  };

  const openResultReport = async (sessionId?: number) => {
    const targetSessionId = sessionId ?? detail?.session.id;
    if (!targetSessionId) return;
    setResultLoading(true);
    setError("");
    try {
      const response = await repositories.tradeTraining.getResult(targetSessionId);
      setResult(response);
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : "결과 리포트를 불러오지 못했습니다.");
    } finally {
      setResultLoading(false);
    }
  };

  const mutateDetail = async (action: () => Promise<TrainingSessionDetail>, successMessage: string) => {
    setLoading(true);
    setError("");
    setMessage("");
    try {
      const response = await action();
      setDetail(response);
      setScrollTargetDate(null);
      setMessage(successMessage);
      if (response.session.status === "완료") {
        await openResultReport(response.session.id);
      }
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : "요청을 처리하지 못했습니다.");
    } finally {
      setLoading(false);
    }
  };

  const finishSession = async () => {
    if (!detail) return;
    setLoading(true);
    setError("");
    setMessage("");
    try {
      const response = await repositories.tradeTraining.finish(detail.session.id);
      setDetail((prev) => (prev ? { ...prev, session: response.session, account: response.account } : prev));
      setScrollTargetDate(null);
      setMessage(response.message);
      await openResultReport(response.session.id);
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : "훈련을 종료하지 못했습니다.");
    } finally {
      setLoading(false);
    }
  };

  const submitOrder = async (payload: TrainingOrderRequest) => {
    if (!detail || !orderMode) return;
    const response =
      orderMode === "BUY"
        ? await repositories.tradeTraining.buy(detail.session.id, payload)
        : await repositories.tradeTraining.sell(detail.session.id, payload);
    setDetail(response);
    setScrollTargetDate(null);
    setOrderMode(null);
    setMessage(orderMode === "BUY" ? "매수 체결되었습니다." : "매도 체결되었습니다.");
  };

  const handleSaveMethodPrinciples = async (methodId: number, payload: Partial<TradeMethodSaveRequest>) => {
    const updated = await repositories.tradeJournals.updateTradeMethod(methodId, payload);
    setTradeMethods((prev) => prev.map((method) => (method.id === updated.id ? updated : method)));
    setDetail((prev) => {
      if (!prev || prev.trade_method?.id !== updated.id) return prev;
      return { ...prev, trade_method: updated };
    });
    setMessage("매매원칙이 저장되었습니다.");
    return updated;
  };

  const focusTradeDate = (tradeDate: string) => {
    if (!detail?.candles.some((candle) => candle.trade_date === tradeDate)) {
      setMessage("해당 거래일의 캔들을 찾을 수 없습니다.");
      return;
    }
    setHighlightedTradeDate(tradeDate);
    setHighlightedTradeId(null);
    setScrollTargetDate(tradeDate);
  };

  const highlightTradeMarker = (tradeDate: string, tradeId: number | null) => {
    setHighlightedTradeDate(tradeDate);
    setHighlightedTradeId(tradeId);
  };

  const handleNextDay = () => {
    if (!detail) return;
    void mutateDetail(() => repositories.tradeTraining.next(detail.session.id), "다음 거래일로 이동했습니다.");
  };

  const toggleAvgPriceLine = () => {
    if (!detail || detail.session.position_qty <= 0 || detail.session.avg_price <= 0) {
      setMessage("보유 중인 포지션이 없어 평균단가선을 표시할 수 없습니다.");
      return;
    }
    setShowAvgPriceLine((prev) => !prev);
  };

  const progressText = useMemo(() => {
    if (!detail) return "-";
    return `${fmtNumber(detail.session.current_index + 1)}일차 · ${detail.session.start_date} ~ ${detail.session.end_date}`;
  }, [detail]);
  const tradeLogRows = useMemo(() => buildTradeLogRows(detail?.trades ?? []), [detail?.trades]);

  const canTrade = detail?.session.status === "진행중";

  return (
    <div className="trade-training-page space-y-4">
      <PageHeader
        title="매매훈련"
        description="과거 일봉을 하루씩 넘기며 매수·매도 판단을 훈련합니다."
        action={
          <button
            type="button"
            className="btn btn-primary"
            onClick={() => {
              void loadTradeMethods();
              setSettingsOpen(true);
            }}
          >
            <Settings size={16} /> 훈련 설정
          </button>
        }
      />

      <div className="training-main training-main-focused">
        <div className="training-status-row">
          <div className="training-message-panel">
            {error ? <div className="inline-result inline-error">{error}</div> : null}
            {!error && message ? <div className="inline-result">{message}</div> : null}
          </div>
          {detail ? (
            <div className="training-method-reference">
              <span>훈련 기법: {detail.trade_method?.method_name || "자유훈련"}</span>
              <button
                type="button"
                className="btn btn-secondary"
                disabled={!detail.trade_method}
                onClick={() => setShowMethodPrinciples(true)}
              >
                원칙 보기
              </button>
            </div>
          ) : null}
        </div>

        {!detail ? (
          <SectionCard title="훈련 화면">
            <EmptyState message="훈련 설정 버튼을 눌러 종목과 조건을 선택하세요." />
          </SectionCard>
        ) : (
          <>
            <SectionCard title={`${detail.session.stock_name || detail.session.stock_code} 리플레이`}>
              <div className="training-session-head">
                <div>
                  <strong>{detail.session.current_date}</strong>
                  <span>{progressText} · 상태 {detail.session.status}</span>
                </div>
                <div className="training-session-actions">
                  <button className="btn btn-secondary" type="button" disabled={!canTrade || loading} onClick={handleNextDay}>
                    <StepForward size={16} /> 다음
                  </button>
                  <button className="btn btn-primary" type="button" disabled={!canTrade || loading} onClick={() => setOrderMode("BUY")}>
                    <ShoppingCart size={16} /> 매수
                  </button>
                  <button className="btn btn-danger" type="button" disabled={!canTrade || detail.session.position_qty <= 0 || loading} onClick={() => setOrderMode("SELL")}>
                    매도
                  </button>
                  <button className="btn btn-secondary" type="button" disabled={resultLoading} onClick={() => void openResultReport()}>
                    <BarChart3 size={16} /> 결과 리포트
                  </button>
                  <button className="btn btn-secondary" type="button" disabled={loading} onClick={finishSession}>
                    <PauseCircle size={16} /> 종료
                  </button>
                </div>
              </div>

              <TrainingKpiStrip detail={detail} showAvgPriceLine={showAvgPriceLine} onToggleAvgPriceLine={toggleAvgPriceLine} />
              <CandleChart
                sessionId={detail.session.id}
                candles={detail.candles}
                trades={detail.trades}
                avgPriceLine={showAvgPriceLine && detail.session.position_qty > 0 ? detail.session.avg_price : null}
                displayDays={displayDays}
                scrollTargetDate={scrollTargetDate}
                highlightedTradeDate={highlightedTradeDate}
                highlightedTradeId={highlightedTradeId}
                onMarkerClick={highlightTradeMarker}
              />
              <TrainingChartSummary detail={detail} onNext={handleNextDay} nextDisabled={!canTrade || loading} />
            </SectionCard>

            <SectionCard title="거래 로그">
              {detail.trades.length === 0 ? <EmptyState message="아직 체결된 훈련 거래가 없습니다." /> : (
                <div className="table-shell">
                  <table className="data-table compact-table training-log-table">
                    <thead><tr><th>일자</th><th>구분</th><th className="numeric-cell">가격</th><th className="numeric-cell">수량</th><th className="numeric-cell">매매금액</th><th className="numeric-cell">현투자금액</th><th className="numeric-cell">손익</th><th>사유</th></tr></thead>
                    <tbody>
                      {tradeLogRows.map((row) => {
                        const trade = row.trade;
                        return (
                          <tr
                            key={trade.id}
                            className={`training-log-row ${highlightedTradeDate === trade.trade_date || highlightedTradeId === trade.id ? "active" : ""}`}
                            onClick={() => focusTradeDate(trade.trade_date)}
                            title="차트에서 보기"
                          >
                            <td>{trade.trade_date}</td>
                            <td><span className={trade.side === "BUY" ? "badge badge-blue" : "badge badge-rose"}>{trade.side === "BUY" ? "매수" : "매도"}</span></td>
                            <td className="numeric-cell">{fmtWon(trade.price)}</td>
                            <td className="numeric-cell">{fmtNumber(trade.quantity)}</td>
                            <td className="numeric-cell">{fmtWon(row.tradeAmount)}</td>
                            <td className="numeric-cell">{fmtWon(row.currentInvestedAmount)}</td>
                            <td className={`numeric-cell ${profitClass(trade.realized_profit)}`}>{fmtSignedWon(trade.realized_profit)}</td>
                            <td className="training-log-reason-cell">{trade.reason || "-"}</td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              )}
            </SectionCard>
          </>
        )}
      </div>

      {settingsOpen ? (
        <SettingsModal
          q={q}
          setQ={setQ}
          stocks={stocks}
          selectedStock={selectedStock}
          setSelectedStock={setSelectedStock}
          tradeMethods={tradeMethods}
          selectedMethodId={selectedMethodId}
          setSelectedMethodId={setSelectedMethodId}
          methodLoadError={methodLoadError}
          initialCash={initialCash}
          setInitialCash={setInitialCash}
          feeRatePct={feeRatePct}
          setFeeRatePct={setFeeRatePct}
          displayDays={displayDays}
          setDisplayDays={setDisplayDays}
          movingAverageText={movingAverageText}
          setMovingAverageText={setMovingAverageText}
          startDate={startDate}
          setStartDate={setStartDate}
          endDate={endDate}
          setEndDate={setEndDate}
          loading={loading}
          onSearch={() => loadStocks()}
          onStart={startSession}
          onClose={() => setSettingsOpen(false)}
        />
      ) : null}
      {detail?.trade_method && showMethodPrinciples ? (
        <TrainingMethodPrinciplesModal
          method={detail.trade_method}
          onSave={handleSaveMethodPrinciples}
          onClose={() => setShowMethodPrinciples(false)}
        />
      ) : null}
      {detail && orderMode ? <OrderModal mode={orderMode} detail={detail} onClose={() => setOrderMode(null)} onSubmit={submitOrder} /> : null}
      {result ? <ResultModal result={result} onClose={() => setResult(null)} /> : null}
    </div>
  );
}

export default TradeTrainingPage;
