import type { DrctInsightStock, DrctInsightToday, ExecutionGate, IntradayState, PatternStatus, ReadinessStatus } from "@/types/drctInsight";

export const insightLabels = {
  candidate: { NONE: "관찰 종목", PRELIMINARY: "1차 후보", FOCUS: "집중 후보", FINAL: "검증 후보" },
  execution: { WAIT: "대기", WATCH: "관찰", READY: "실행 검토", TRIGGERED: "실행 조건 도달", INVALID: "관찰 제외" },
  intraday: { STRENGTHENING: "강화 중", STABLE: "흐름 유지", WEAKENING: "약화 중", WARNING: "주의" },
  pattern: { PROMISING: "유망 · 검증 중", VERIFIED: "검증 가능", WATCH: "추가 관찰", WEAK: "구분력 낮음", NOT_READY: "비교 사례 부족" },
  readiness: { READY: "준비 완료", PARTIAL: "일부 데이터 대기", NOT_READY: "데이터 준비 필요", STALE: "갱신 필요", ERROR: "확인 필요" },
} as const;

export function candidateLabel(stock: DrctInsightStock) {
  if (stock.final_candidate) return insightLabels.candidate.FINAL;
  if (stock.focus_candidate) return insightLabels.candidate.FOCUS;
  return insightLabels.candidate[stock.candidate_level];
}

export function executionLabel(value?: string | null) {
  return insightLabels.execution[(value || "WAIT") as keyof typeof insightLabels.execution] || "대기";
}

export function intradayLabel(value: IntradayState) {
  return insightLabels.intraday[value];
}

export function patternLabel(value: PatternStatus) {
  return insightLabels.pattern[value];
}

export function readinessText(value: ReadinessStatus) {
  return insightLabels.readiness[value];
}

export function statusSymbol(value: IntradayState) {
  return value === "STRENGTHENING" ? "▲" : value === "STABLE" ? "→" : value === "WEAKENING" ? "▼" : "!";
}

export function nextCheck(stock: DrctInsightStock, state: IntradayState, realtime: ReadinessStatus) {
  if (realtime !== "READY" || stock.theme_strength == null) return "테마 장중 강도 확인 필요";
  if (stock.relative_strength == null) return "테마 대비 강도 확인 필요";
  if ((stock.gates.execution as ExecutionGate | null) === "READY") return "현재 강도와 계획 조건 유지 여부 확인";
  if (state === "STRENGTHENING") return "강화 흐름과 종목 우위가 유지되는지 확인";
  if (state === "WEAKENING" || state === "WARNING") return "테마 약화가 지속되는지 확인";
  return "테마 강도와 상승 확산이 개선되는지 확인";
}

export function patternInterpretation(stock: DrctInsightStock) {
  const hasFailure = stock.failure_similarity != null && stock.failure_sample_count >= stock.required_failure_sample_count;
  if (!hasFailure) return "과거 성공 사례와는 닮았지만 실패 사례와 비교할 데이터가 부족합니다.";
  if ((stock.pattern_edge ?? 0) >= 10) return "성공 사례와 유사하면서 실패 사례와는 비교적 잘 구분됩니다.";
  if ((stock.pattern_edge ?? 0) <= 0) return "성공 사례와 닮았지만 실패 사례와도 유사해 구분력이 낮습니다.";
  return "성공 사례와의 유사성은 확인되며, 구분력은 추가 사례로 검증 중입니다.";
}

export function todayJudgment(data: DrctInsightToday, states: IntradayState[]) {
  const focusThemes = data.themes.filter((theme) => theme.focus_candidate_count > 0).sort((a, b) => (a.observation_rank ?? 999) - (b.observation_rank ?? 999));
  const names = focusThemes.slice(0, 2).map((theme) => theme.theme_name).join("·") || "상위 관찰 테마";
  const strengthening = states.filter((state) => state === "STRENGTHENING").length;
  const first = `오늘은 ${names} 중심으로 ${data.summary.focus_candidate_count}개 종목을 집중 관찰합니다.`;
  if (data.summary.ready_count > 0) return `${first} 현재 ${data.summary.ready_count}개 종목은 실행 검토 단계입니다.`;
  if (strengthening > 0) return `${first} 현재 ${strengthening}개 종목의 장중 흐름이 강화되고 있습니다.`;
  if (data.readiness.realtime.status !== "READY") return `${first} 장중 테마 데이터가 아직 없어 실행 판단은 대기 중입니다.`;
  if (data.summary.final_candidate_count === 0 && data.readiness.pattern.status !== "READY") return `${first} 검증 후보는 아직 없으며 비교 사례가 더 필요합니다.`;
  return first;
}
