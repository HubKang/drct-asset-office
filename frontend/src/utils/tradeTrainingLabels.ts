const TRADE_TRAINING_EVENT_LABELS: Record<string, string> = {
  CREATE: "매매시나리오 생성",
  ACTIVATE: "매매시나리오 활성화",
  CLOSED: "매매시나리오 종료",
  CANCELLED: "매매시나리오 취소",
  BUY_PLAN_MATCHED: "매수 계획 일치",
  SELL_PLAN_MATCHED: "매도 계획 일치",
  PLAN_STEP_EXECUTED: "계획 단계 실행 완료",
  UNPLANNED_BUY: "계획 외 매수",
  UNPLANNED_SELL: "계획 외 매도",
  BUY_PRICE_DEVIATION: "매수 계획가 이탈",
  SELL_PRICE_DEVIATION: "매도 계획가 이탈",
  RISK_BUDGET_NEAR_LIMIT: "계좌 위험예산 근접",
  RISK_BUDGET_EXCEEDED: "계좌 위험예산 초과",
  PRICE_LINES_UPDATED: "계획 가격선 변경",
  PLAN_REVISED: "매매시나리오 수정",
  TAKE_PROFIT_REACHED: "익절 목표가 도달",
  PARTIAL_STOP_REACHED: "분할손절 가격 도달",
  FULL_STOP_REACHED: "전량손절 가격 도달",
  MULTIPLE_PLAN_LEVELS_REACHED: "복수 계획가격 동시 도달",
  TAKE_PROFIT_RESPONSE_SELL: "익절 도달 후 매도",
  TAKE_PROFIT_RESPONSE_HOLD: "익절 도달 후 계속 보유",
  TAKE_PROFIT_RESPONSE_PLAN_REVISED: "익절 도달 후 계획 수정",
  PARTIAL_STOP_RESPONSE_SELL: "분할손절 도달 후 매도",
  PARTIAL_STOP_RESPONSE_HOLD: "분할손절 도달 후 계속 보유",
  PARTIAL_STOP_RESPONSE_PLAN_REVISED: "분할손절 도달 후 계획 수정",
  FULL_STOP_RESPONSE_SELL: "전량손절 도달 후 매도",
  FULL_STOP_RESPONSE_HOLD: "전량손절 도달 후 계속 보유",
  FULL_STOP_RESPONSE_PLAN_REVISED: "전량손절 도달 후 계획 수정",
  RISK_BUDGET_NEAR_LIMIT_ACKNOWLEDGED: "위험예산 근접 경고 확인",
  RISK_BUDGET_EXCEEDED_ACKNOWLEDGED: "위험예산 초과 경고 확인",
};

export function getTradeTrainingEventLabel(eventType?: string | null): string {
  const normalized = String(eventType || "").trim().toUpperCase();
  if (!normalized) return "이벤트 정보 없음";
  if (TRADE_TRAINING_EVENT_LABELS[normalized]) return TRADE_TRAINING_EVENT_LABELS[normalized];

  return normalized
    .split("_")
    .filter(Boolean)
    .map((word) => word.charAt(0) + word.slice(1).toLowerCase())
    .join(" ");
}

export function formatHoldingBars(value?: number | null): string {
  if (value == null) return "-";
  const numericValue = Number(value);
  return Number.isFinite(numericValue) ? `${Math.round(numericValue)}봉` : "-";
}