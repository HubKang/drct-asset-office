import type { MarketSignalCurrentStateItem } from "@/types/marketSignal";

export type MarketSignalChangeItem = MarketSignalCurrentStateItem & {
  isTodayTransition: boolean;
};

export type MarketSignalChangeGroup = "BREAK" | "WEAKENING" | "RECOVERY" | "OTHER";

export const MARKET_SIGNAL_STATE_LABELS: Record<string, string> = {
  TREND_WEAKENING: "추세 약화",
  BREAK_CANDIDATE: "추세 이탈 후보",
  BREAK_CONFIRMED: "추세 이탈 확인",
  REVERSAL_CONFIRMED: "반전 확인",
  FALSE_BREAK: "일시 이탈 후 복귀",
  TREND_RESUMED: "기존 추세 재개",
  RELEASED: "현상 해제",
  DATA_SHORTAGE: "데이터 부족",
  DATA_INSUFFICIENT: "데이터 부족",
  INSUFFICIENT_DATA: "데이터 부족",
  ERROR: "평가 오류",
  NOT_EVALUATED: "미평가",
};

export const MARKET_SIGNAL_SEVERITY: Record<string, number> = {
  ERROR: 0,
  BREAK_CONFIRMED: 1,
  REVERSAL_CONFIRMED: 2,
  BREAK_CANDIDATE: 3,
  TREND_WEAKENING: 4,
  FALSE_BREAK: 5,
  TREND_RESUMED: 6,
  RELEASED: 6,
  DATA_SHORTAGE: 7,
  DATA_INSUFFICIENT: 7,
  INSUFFICIENT_DATA: 7,
  NOT_EVALUATED: 8,
};

const MAINTAINED_STATES = new Set(["TREND_INTACT", "TREND_MAINTAINED", "MAINTAINED"]);
const DATA_UNAVAILABLE_STATES = new Set(["DATA_SHORTAGE", "DATA_INSUFFICIENT", "INSUFFICIENT_DATA", "NOT_EVALUATED"]);
const RECOVERY_STATES = new Set(["FALSE_BREAK", "TREND_RESUMED", "RELEASED"]);

export function marketSignalStateLabel(state: string | null | undefined): string {
  const normalized = String(state ?? "NOT_EVALUATED").toUpperCase();
  return MARKET_SIGNAL_STATE_LABELS[normalized] ?? normalized;
}

export function marketSignalTone(state: string): "danger" | "warning" | "recovery" | "neutral" | "info" {
  if (["ERROR", "BREAK_CONFIRMED", "REVERSAL_CONFIRMED"].includes(state)) return "danger";
  if (["BREAK_CANDIDATE", "TREND_WEAKENING"].includes(state)) return "warning";
  if (RECOVERY_STATES.has(state)) return "recovery";
  if (DATA_UNAVAILABLE_STATES.has(state)) return "neutral";
  return "info";
}

export function isMarketSignalDataUnavailable(item: MarketSignalCurrentStateItem): boolean {
  return item.evaluation_status === "DATA_SHORTAGE" || DATA_UNAVAILABLE_STATES.has(item.current_state);
}

export function isMarketSignalRecovery(state: string): boolean {
  return RECOVERY_STATES.has(state);
}

export function marketSignalChangeGroup(state: string): MarketSignalChangeGroup {
  if (["BREAK_CANDIDATE", "BREAK_CONFIRMED", "REVERSAL_CONFIRMED"].includes(state)) return "BREAK";
  if (state === "TREND_WEAKENING") return "WEAKENING";
  if (RECOVERY_STATES.has(state)) return "RECOVERY";
  return "OTHER";
}

export function marketSignalItemCode(item: MarketSignalCurrentStateItem): string {
  if (item.item_code) return item.item_code;
  const condition = item.conditions.find((row) => row.indicator_code || row.item_code);
  return String(condition?.indicator_code ?? condition?.item_code ?? "");
}

export function selectMeaningfulMarketSignals(
  currentItems: MarketSignalCurrentStateItem[],
  todayItems: MarketSignalCurrentStateItem[],
): MarketSignalChangeItem[] {
  const transitionsById = new Map(todayItems.map((item) => [item.definition_id, item]));
  return currentItems
    .map((item): MarketSignalChangeItem => {
      const transition = transitionsById.get(item.definition_id);
      return {
        ...item,
        ...(transition ?? {}),
        category: transition?.category ?? item.category,
        item_code: transition?.item_code ?? item.item_code,
        isTodayTransition: Boolean(transition),
      };
    })
    .filter((item) => !MAINTAINED_STATES.has(item.current_state) && !isMarketSignalDataUnavailable(item))
    .sort((a, b) =>
      Number(b.isTodayTransition) - Number(a.isTodayTransition)
      || (MARKET_SIGNAL_SEVERITY[a.current_state] ?? 99) - (MARKET_SIGNAL_SEVERITY[b.current_state] ?? 99)
      || String(b.last_transition_at ?? b.evaluated_at ?? "").localeCompare(String(a.last_transition_at ?? a.evaluated_at ?? ""))
      || String(a.title ?? a.signal_code ?? "").localeCompare(String(b.title ?? b.signal_code ?? ""), "ko-KR"));
}
