import { useEffect, useState } from "react";
import { X } from "lucide-react";
import MultiPeriodTrendChart from "@/components/tradeTraining/MultiPeriodTrendChart";
import type { TechnicalAnalysisConfiguration, TechnicalAnalysisPeriod } from "@/types/tradeTraining";
import type { MultiPeriodTechnicalAnalysis } from "@/types/multiPeriodTechnicalAnalysis";
import "./TechnicalAnalysisDrawer.css";
import "./MultiPeriodTechnicalAnalysisDrawer.css";

type Tab = "summary" | "trend" | "moving" | "volume" | "position";
const PERIODS: TechnicalAnalysisPeriod[] = ["1M", "3M", "6M", "1Y", "ALL"];
const TABS: Array<[Tab, string]> = [
  ["summary", "종합"],
  ["trend", "추세"],
  ["moving", "이동평균"],
  ["volume", "거래량"],
  ["position", "가격 위치"],
];
const DEFAULT_CONFIGURATION: Partial<TechnicalAnalysisConfiguration> = {
  short_window: 20,
  medium_window: 60,
  trend_window: 120,
  channel_multiplier: 1.8,
  minimum_break_persistence: 3,
  reversal_persistence: 5,
  swing_confirmation_width: 3,
};
const pct = (value: unknown) => value === null || value === undefined ? "-" : `${Number(value) >= 0 ? "+" : ""}${Number(value).toFixed(2)}%`;
const num = (value: unknown) => value === null || value === undefined ? "-" : Number(value).toLocaleString("ko-KR");
const shortDate = (value: string | null | undefined) => value ? value.slice(5) : "판정 보류";

export default function MultiPeriodTechnicalAnalysisDrawer({
  open,
  stockName,
  data,
  loading,
  error,
  selectedPeriod,
  onPeriodChange,
  onClose,
  onRetry,
  onApplyConfiguration,
}: {
  open: boolean;
  stockName: string;
  data: MultiPeriodTechnicalAnalysis | null;
  loading: boolean;
  error: string;
  selectedPeriod: TechnicalAnalysisPeriod;
  onPeriodChange: (period: TechnicalAnalysisPeriod) => void;
  onClose: () => void;
  onRetry: () => void;
  onApplyConfiguration: (configuration: Partial<TechnicalAnalysisConfiguration>) => void;
}) {
  const [tab, setTab] = useState<Tab>("summary");
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState<Partial<TechnicalAnalysisConfiguration>>({});
  useEffect(() => {
    if (!open) return;
    setTab("summary");
    setEditing(false);
  }, [open]);
  useEffect(() => {
    if (!data) return;
    setDraft(data.applied_configuration || {});
  }, [data?.selected_period, data?.as_of_date]);
  useEffect(() => {
    if (!open) return;
    const close = (event: KeyboardEvent) => event.key === "Escape" && onClose();
    window.addEventListener("keydown", close);
    return () => window.removeEventListener("keydown", close);
  }, [open, onClose]);
  if (!open) return null;

  const detail = data?.selected_period_detail;
  const summary = detail?.period_summary;
  const moving = detail?.moving_averages || {};
  const volume = detail?.volume || {};
  const position = detail?.price_position || {};
  const candle = detail?.current_candle || {};
  const metric = (label: string, value: unknown) => <div><dt>{label}</dt><dd>{String(value ?? "-")}</dd></div>;

  return (
    <div className="training-technical-drawer-backdrop" role="presentation" onMouseDown={onClose}>
      <aside className="training-technical-drawer training-technical-drawer-wide" role="dialog" aria-modal="true" aria-label="DrCT 기술분석" onMouseDown={(event) => event.stopPropagation()}>
        <header>
          <div><span>DrCT 기술분석</span><strong>{stockName}</strong><small>훈련 기준일 {data?.as_of_date || "-"}</small></div>
          <button type="button" onClick={onClose} aria-label="닫기"><X size={20} /></button>
        </header>
        <div className="training-multi-period-head">
          <div className="training-multi-period-buttons" role="group" aria-label="기술분석 상세 기간">
            {PERIODS.map((period) => <button key={period} type="button" className={selectedPeriod === period ? "active" : ""} onClick={() => onPeriodChange(period)}>{period}</button>)}
          </div>
          {data ? <div className="training-multi-period-cards">
            {data.period_summaries.map((item) => <button key={item.period} type="button" className={selectedPeriod === item.period ? "active" : ""} onClick={() => onPeriodChange(item.period)}>
              <strong>{item.period}</strong>
              <span>전체 {item.period_direction_label}</span>
              <span>현재 {item.current_trend_label.replace(" 추세", "")} · {item.current_state_label}</span>
              <small>{item.available ? `시작 ${shortDate(item.trend_start_date)}` : `${item.observation_count}/${item.minimum_observation_count}봉`}</small>
            </button>)}
          </div> : null}
        </div>
        <div className="training-technical-tabs" role="tablist">
          {TABS.map(([key, label]) => <button key={key} type="button" role="tab" aria-selected={tab === key} className={tab === key ? "active" : ""} onClick={() => setTab(key)}>{label}</button>)}
        </div>
        <div className="training-technical-drawer-body">
          {loading && !data ? <div className="training-technical-drawer-state">다중 기간 기술 분석을 계산하고 있습니다.</div>
            : error && !data ? <div className="training-technical-drawer-state error">기술 분석을 불러오지 못했습니다.<button type="button" onClick={onRetry}>다시 시도</button></div>
            : !data || !detail ? <div className="training-technical-drawer-state">분석 결과가 없습니다.</div>
            : editing ? <section className="training-technical-settings">
              <p>변경값은 현재 훈련 화면의 선택 기간 분석에만 적용되며 저장되지 않습니다.</p>
              {([
                ["short_window", "단기 관찰 기간", 2, 120, 1],
                ["medium_window", "중기 관찰 기간", 5, 240, 1],
                ["trend_window", "추세 분석 기간", 20, 240, 1],
                ["channel_multiplier", "채널 폭", .5, 5, .1],
                ["minimum_break_persistence", "추세 이탈 확인 기간", 1, 20, 1],
                ["reversal_persistence", "반전 확인 기간", 1, 30, 1],
                ["swing_confirmation_width", "스윙 확인 폭", 1, 10, 1],
              ] as Array<[keyof TechnicalAnalysisConfiguration, string, number, number, number]>).map(([key, label, min, max, step]) => <label key={key}>
                <span>{label}</span>
                <input type="number" min={min} max={max} step={step} value={Number(draft[key] ?? data.applied_configuration[key])} onChange={(event) => setDraft((current) => ({ ...current, [key]: Number(event.target.value) }))} />
              </label>)}
            </section>
            : tab === "summary" ? <>
              <section className="training-technical-lead training-period-summary-lead">
                <span>선택 기간 · {selectedPeriod} · {summary?.observation_count || 0}개 봉</span>
                <strong>{summary?.display_start_date || "-"} ~ {summary?.display_end_date || "-"}</strong>
                <div className="training-period-summary-grid">
                  <div><small>기간 전체 방향</small><b>{summary?.period_direction_label}</b></div>
                  <div><small>현재 진행 추세</small><b>{summary?.current_trend_label} · {summary?.current_state_label}</b></div>
                  <div><small>현재 추세 시작</small><b>{summary?.trend_start_date || "판정 보류"}</b></div>
                  <div><small>현재 추세 지속</small><b>{summary?.persistence_count ? `${summary.persistence_count}개 봉` : "-"}</b></div>
                  <div><small>추세 강도</small><b>{num(summary?.trend_strength)}</b></div>
                  <div><small>현재 채널 위치</small><b>{summary?.channel_position_label}</b></div>
                </div>
                <p>{detail.easy_explanation}</p>
              </section>
              <section><h3>기간별 추세 정합성</h3>
                <dl className="training-technical-metrics">
                  {metric("단기 1M", data.alignment.short_label)}
                  {metric("중기 6M", data.alignment.medium_label)}
                  {metric("장기 1Y", data.alignment.long_label)}
                  {metric("추세 정합성", data.alignment.alignment_label)}
                </dl>
                <p>{data.alignment.easy_explanation}</p>
              </section>
              <section><h3>다음 확인</h3><ul>{detail.next_checks.map((item) => <li key={item}>{item}</li>)}</ul></section>
            </>
            : tab === "trend" ? <>
              <section className="training-technical-lead">
                <span>{summary?.model_label} · 민감도 {summary?.sensitivity_label}</span>
                <strong>{summary?.current_trend_label} · {summary?.current_state_label}</strong>
                <p>{detail.easy_explanation}</p>
              </section>
              <MultiPeriodTrendChart detail={detail} />
              <dl className="training-technical-metrics">
                {metric("기간 전체 방향", summary?.period_direction_label)}
                {metric("기간 전체 R²", num(summary?.period_r_squared))}
                {metric("현재 추세 시작", summary?.trend_start_date || "판정 보류")}
                {metric("지속기간", summary?.persistence_count ? `${summary.persistence_count}개 봉` : "-")}
                {metric("추세 강도", num(summary?.trend_strength))}
                {metric("채널 위치", summary?.channel_position_label)}
              </dl>
              <section className="training-transition-history"><h3>최근 추세 변화</h3>
                {detail.transition_events.length ? <ol>{detail.transition_events.map((event) => <li key={`${event.observation_date}-${event.current_state}`}>
                  <time>{event.observation_date}</time>
                  <strong>{event.previous_state_label} → {event.current_state_label}</strong>
                  <p>{event.reason}</p>
                  <small>당시 강도 {num(event.trend_strength)} · 채널 {event.channel_position == null ? "-" : pct(Number(event.channel_position)*100)}</small>
                </li>)}</ol> : <p>선택 기간에 표시할 확정 전환 이력이 없습니다.</p>}
              </section>
            </>
            : tab === "moving" ? <>
              <section className="training-technical-lead"><span>{selectedPeriod} 기준</span><strong>{moving.arrangement_label}</strong><p>{moving.latest_cross ? `${moving.latest_cross.label} · ${moving.latest_cross.date}` : "최근 MA5·MA20 교차 없음"}</p></section>
              <dl className="training-technical-metrics">{Object.entries(moving.values || {}).map(([key, item]) => metric(key.toUpperCase(), `${num(item.value)} · 현재가 대비 ${pct(item.distance_pct)}`))}</dl>
            </>
            : tab === "volume" ? <>
              <section className="training-technical-lead"><span>{selectedPeriod} 기준</span><strong>거래량 관찰</strong><p>{String(volume.observation || "-")}</p></section>
              <dl className="training-technical-metrics">{metric("현재 거래량", num(volume.current))}{metric("5일 평균", num(volume.average_5))}{metric("20일 평균", num(volume.average_20))}{metric("20일 평균 배율", volume.ratio_to_average_20 == null ? "-" : `${Number(volume.ratio_to_average_20).toFixed(2)}배`)}{metric("상승 캔들 평균", num(volume.up_candle_average))}{metric("하락 캔들 평균", num(volume.down_candle_average))}</dl>
            </>
            : <>
              <section className="training-technical-lead"><span>{selectedPeriod} 기준</span><strong>가격 위치</strong><p>선택 기간과 현재 훈련 기준일 안에서 확정된 고점·저점만 표시합니다.</p></section>
              <dl className="training-technical-metrics">{metric("최근 확정 전고점", position.confirmed_high ? `${num(position.confirmed_high.value)} · ${pct(position.confirmed_high.distance_pct)}` : "-")}{metric("최근 확정 전저점", position.confirmed_low ? `${num(position.confirmed_low.value)} · ${pct(position.confirmed_low.distance_pct)}` : "-")}{metric("스윙 고점 후보", position.high_candidate ? `${num(position.high_candidate.value)} · ${position.high_candidate.date}` : "-")}{metric("스윙 저점 후보", position.low_candidate ? `${num(position.low_candidate.value)} · ${position.low_candidate.date}` : "-")}{metric("현재 캔들", candle.direction_label)}{metric("ATR 대비 당일 범위", candle.range_to_atr == null ? "-" : `${Number(candle.range_to_atr).toFixed(2)}배`)}</dl>
            </>}
        </div>
        <footer>{editing ? <>
          <button type="button" onClick={() => setDraft(DEFAULT_CONFIGURATION)}>기본값 복원</button>
          <div><button type="button" onClick={() => setEditing(false)}>취소</button><button className="primary" type="button" onClick={() => { onApplyConfiguration(draft); setEditing(false); }}>현재 기간에 적용</button></div>
        </> : <><button title="변경한 설정은 현재 화면에만 적용되고 저장되지 않습니다." type="button" onClick={() => setEditing(true)}>설정 조정</button><button type="button" onClick={onClose}>닫기</button></>}</footer>
      </aside>
    </div>
  );
}
