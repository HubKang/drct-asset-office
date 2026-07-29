import { useEffect, useState } from "react";
import { X } from "lucide-react";
import PeriodOverviewTrendChart from "@/components/tradeTraining/PeriodOverviewTrendChart";
import type { TechnicalAnalysisConfiguration, TechnicalAnalysisPeriod } from "@/types/tradeTraining";
import type { MultiPeriodTechnicalAnalysis } from "@/types/multiPeriodTechnicalAnalysis";
import "./TechnicalAnalysisDrawer.css";
import "./PeriodTrendAnalysisDrawer.css";

const PERIODS: TechnicalAnalysisPeriod[] = ["1M", "3M", "6M", "1Y", "ALL"];
const DEFAULT_CONFIGURATION: Partial<TechnicalAnalysisConfiguration> = {
  short_window: 20,
  medium_window: 60,
  trend_window: 120,
  channel_multiplier: 1.8,
  minimum_break_persistence: 3,
  reversal_persistence: 5,
  swing_confirmation_width: 3,
};
const number = (value: unknown, digits = 0) => value == null ? "-" : Number(value).toLocaleString("ko-KR", { maximumFractionDigits: digits });
const percent = (value: unknown) => value == null ? "-" : `${Number(value) >= 0 ? "+" : ""}${Number(value).toFixed(2)}%`;

export default function PeriodTrendAnalysisDrawer({
  open, stockName, data, loading, error, selectedPeriod, onPeriodChange, onClose, onRetry, onApplyConfiguration,
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
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState<Partial<TechnicalAnalysisConfiguration>>({});
  useEffect(() => {
    if (open) setEditing(false);
  }, [open]);
  useEffect(() => {
    if (data) setDraft(data.applied_configuration || {});
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
  const ma20 = moving.values?.ma20;
  const ratio = volume.ratio_to_average_20 == null ? null : Number(volume.ratio_to_average_20);
  const high = position.confirmed_high;
  const low = position.confirmed_low;
  const cards = [
    ["종합", detail?.summary?.status_label || summary?.period_direction_label || "-", detail?.current_candle?.direction_label || "현재 캔들 판정 대기"],
    ["추세", summary?.period_direction_label || "-", `강도 ${number(summary?.period_trend_strength, 1)} · R² ${number(summary?.period_r_squared, 3)}`],
    ["이동평균", moving.arrangement_label || "-", ma20?.distance_pct == null ? "MA20 데이터 부족" : `현재가가 MA20 ${Number(ma20.distance_pct) >= 0 ? "상단" : "하단"} · ${percent(ma20.distance_pct)}`],
    ["거래량", ratio == null ? "20일 평균 데이터 부족" : `20일 평균의 ${ratio.toFixed(2)}배`, ratio == null ? "판정 대기" : ratio >= 1 ? "평균 이상" : "평균 이하"],
    ["가격 위치", high ? `전고점 대비 ${percent(high.distance_pct)}` : "확정 전고점 없음", low ? `전저점 대비 ${percent(low.distance_pct)}` : "확정 전저점 없음"],
  ];

  return (
    <div className="training-technical-drawer-backdrop" role="presentation" onMouseDown={onClose}>
      <aside className="training-technical-drawer training-period-drawer" role="dialog" aria-modal="true" aria-label="기간별 전체 추세 기술분석" onMouseDown={(event) => event.stopPropagation()}>
        <header>
          <div><span>DrCT 기술분석</span><strong>{stockName}</strong><small>훈련 기준일 {data?.as_of_date || "-"}</small></div>
          <button type="button" onClick={onClose} aria-label="닫기"><X size={20} /></button>
        </header>
        <div className="training-period-toolbar">
          <div className="training-period-buttons" role="group" aria-label="전체 추세 분석 기간">
            {PERIODS.map((period) => <button key={period} type="button" className={selectedPeriod === period ? "active" : ""} aria-pressed={selectedPeriod === period} onClick={() => onPeriodChange(period)}>{period}</button>)}
          </div>
          <div className="training-period-range">
            <b>{selectedPeriod} · {summary?.observation_count || 0}개 봉</b>
            <span>{summary?.display_start_date || "-"} ~ {summary?.display_end_date || "-"}</span>
          </div>
        </div>
        <div className="training-period-drawer-body">
          {error && !data ? <div className="training-technical-drawer-state error">기술 분석을 불러오지 못했습니다.<button type="button" onClick={onRetry}>다시 시도</button></div>
            : !data || !detail ? <div className="training-technical-drawer-state">{loading ? "선택 기간 전체 차트를 계산하고 있습니다." : "분석 결과가 없습니다."}</div>
            : editing ? <section className="training-technical-settings training-period-settings">
              <p>변경한 설정은 현재 매매훈련 화면에만 임시 적용되며 저장되지 않습니다.</p>
              {([
                ["short_window", "단기 이동평균 기간", 2, 120, 1],
                ["medium_window", "중기 이동평균 기간", 5, 240, 1],
                ["trend_window", "회귀 추세 관찰 기간", 20, 240, 1],
                ["channel_multiplier", "채널 배수", .5, 5, .1],
                ["swing_confirmation_width", "스윙 고점·저점 기준", 1, 10, 1],
              ] as Array<[keyof TechnicalAnalysisConfiguration, string, number, number, number]>).map(([key, label, min, max, step]) => <label key={key}>
                <span>{label}</span>
                <input type="number" min={min} max={max} step={step} value={Number(draft[key] ?? data.applied_configuration[key])} onChange={(event) => setDraft((current) => ({ ...current, [key]: Number(event.target.value) }))} />
              </label>)}
            </section>
            : <>
              <div className="training-analysis-cards" aria-label="선택 기간 기술분석 요약">
                {cards.map(([label, value, support]) => <article key={label}><span>{label}</span><strong>{value}</strong><small>{support}</small></article>)}
              </div>
              <section className={`training-period-chart-section ${loading ? "loading" : ""}`} aria-busy={loading}>
                {loading ? <div className="training-period-chart-loading">선택 기간을 계산하고 있습니다.</div> : null}
                <div className="training-period-chart-guide">
                  <div><span>표시 구간</span><b>{summary?.display_start_date} ~ {summary?.display_end_date}</b></div>
                  <div><span>기간 추세 강도</span><b>{number(summary?.period_trend_strength, 1)}</b></div>
                  <div><span>현재 채널 위치</span><b>{summary?.period_channel_position_label || "-"}</b></div>
                </div>
                <PeriodOverviewTrendChart detail={detail} />
                <p className="training-period-basis-note">상세 추세선은 선택한 {selectedPeriod} 전체 {summary?.observation_count || 0}봉 기준입니다. 최근 80봉만 계산하는 메인 자동 추세선과 분석 시작점이 달라 방향이 다를 수 있습니다.</p>
              </section>
              <section className="training-period-commentary">
                <article className="training-period-insight-card">
                  <header><strong>분석 요약</strong><span>{selectedPeriod} 전체 기준</span></header>
                  <p>{detail.easy_explanation}</p>
                </article>
                <article className="training-period-check-card">
                  <header><strong>다음 확인</strong><span>핵심 관찰 3개</span></header>
                  <ol>{detail.next_checks.slice(0, 3).map((item, index) => <li key={item}><b>{index + 1}</b><span>{item}</span></li>)}</ol>
                </article>
              </section>
            </>}
        </div>
        <footer>{editing ? <>
          <button type="button" onClick={() => setDraft(DEFAULT_CONFIGURATION)}>기본값 복원</button>
          <div><button type="button" onClick={() => setEditing(false)}>취소</button><button className="primary" type="button" onClick={() => { onApplyConfiguration(draft); setEditing(false); }}>현재 차트에 적용</button></div>
        </> : <><button type="button" onClick={() => setEditing(true)}>설정 조정</button><button type="button" onClick={onClose}>닫기</button></>}</footer>
      </aside>
    </div>
  );
}
