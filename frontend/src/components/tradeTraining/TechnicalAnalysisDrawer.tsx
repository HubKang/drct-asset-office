import { useEffect, useState } from "react";
import { X } from "lucide-react";
import type { TechnicalAnalysisConfiguration, TechnicalAnalysisPreview } from "@/types/tradeTraining";
import "./TechnicalAnalysisDrawer.css";

type Tab = "summary" | "trend" | "moving" | "volume" | "position";
const TABS: Array<[Tab, string]> = [["summary", "종합"], ["trend", "추세"], ["moving", "이동평균"], ["volume", "거래량"], ["position", "가격 위치"]];
const DEFAULT_CONFIGURATION: Partial<TechnicalAnalysisConfiguration> = { short_window: 20, medium_window: 60, trend_window: 120, channel_multiplier: 1.8, minimum_break_persistence: 3, reversal_persistence: 5, swing_confirmation_width: 3 };
const pct = (value: unknown) => value === null || value === undefined ? "-" : (Number(value) >= 0 ? "+" : "") + Number(value).toFixed(2) + "%";
const num = (value: unknown) => value === null || value === undefined ? "-" : Number(value).toLocaleString("ko-KR");

export default function TechnicalAnalysisDrawer({
  open, stockName, data, loading, error, onClose, onRetry, onApplyConfiguration,
}: {
  open: boolean;
  stockName: string;
  data: TechnicalAnalysisPreview | null;
  loading: boolean;
  error: string;
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
    setDraft(data?.applied_configuration || {});
  }, [open, data?.as_of_date]);
  useEffect(() => {
    if (!open) return;
    const close = (event: KeyboardEvent) => event.key === "Escape" && onClose();
    window.addEventListener("keydown", close);
    return () => window.removeEventListener("keydown", close);
  }, [open, onClose]);
  if (!open) return null;
  const trend = data?.trend || {};
  const moving = data?.moving_averages || {};
  const volume = data?.volume || {};
  const position = data?.price_position || {};
  const candle = data?.current_candle || {};
  const metric = (label: string, value: unknown) => <div><dt>{label}</dt><dd>{String(value ?? "-")}</dd></div>;
  return (
    <div className="training-technical-drawer-backdrop" role="presentation" onMouseDown={onClose}>
      <aside className="training-technical-drawer" role="dialog" aria-modal="true" aria-label="DrCT 기술분석" onMouseDown={(event) => event.stopPropagation()}>
        <header><div><span>DrCT 기술분석</span><strong>{stockName}</strong><small>훈련 기준일 {data?.as_of_date || "-"}</small></div><button type="button" onClick={onClose} aria-label="닫기"><X size={20} /></button></header>
        <div className="training-technical-tabs" role="tablist">{TABS.map(([key, label]) => <button key={key} type="button" role="tab" aria-selected={tab === key} className={tab === key ? "active" : ""} onClick={() => setTab(key)}>{label}</button>)}</div>
        <div className="training-technical-drawer-body">
          {loading ? <div className="training-technical-drawer-state">기술 분석을 계산하고 있습니다.</div> : error ? <div className="training-technical-drawer-state error">기술 분석을 불러오지 못했습니다.<button type="button" onClick={onRetry}>다시 시도</button></div> : !data ? <div className="training-technical-drawer-state">분석 결과가 없습니다.</div> : editing ? (
            <section className="training-technical-settings">
              <p>변경값은 현재 훈련 화면의 임시 분석에만 적용되며 저장되지 않습니다.</p>
              {([
                ["short_window", "단기 관찰 기간", 2, 120, 1], ["medium_window", "중기 관찰 기간", 5, 240, 1],
                ["trend_window", "추세 분석 기간", 20, 240, 1], ["channel_multiplier", "채널 폭", .5, 5, .1],
                ["minimum_break_persistence", "추세 이탈 확인 기간", 1, 20, 1], ["reversal_persistence", "반전 확인 기간", 1, 30, 1],
                ["swing_confirmation_width", "스윙 확인 폭", 1, 10, 1],
              ] as Array<[keyof TechnicalAnalysisConfiguration, string, number, number, number]>).map(([key, label, min, max, step]) => (
                <label key={key}><span>{label}</span><input type="number" min={min} max={max} step={step} value={Number(draft[key] ?? data.applied_configuration[key])} onChange={(event) => setDraft((current) => ({ ...current, [key]: Number(event.target.value) }))} /></label>
              ))}
            </section>
          ) : tab === "summary" ? <>
            <section className="training-technical-lead"><span>현재 기술 상태</span><strong>{data.summary.status_label}</strong><p>{data.summary.easy_explanation}</p></section>
            <dl className="training-technical-metrics">
              {metric("이평선 배열", moving.arrangement_label)}
              {metric("거래량", volume.ratio_to_average_20 == null ? "-" : "20일 평균의 " + Number(volume.ratio_to_average_20).toFixed(2) + "배")}
              {metric("최근 전고점 대비", pct(position.confirmed_high?.distance_pct))}
              {metric("최근 전저점 대비", pct(position.confirmed_low?.distance_pct))}
              {metric("현재 캔들", candle.direction_label)}
              {metric("ATR 대비 당일 범위", candle.range_to_atr == null ? "-" : Number(candle.range_to_atr).toFixed(2) + "배")}
            </dl>
            <section><h3>다음 확인</h3><ul>{(data.summary.next_checks || []).map((item) => <li key={item}>{item}</li>)}</ul></section>
          </> : tab === "trend" ? <>
            <section className="training-technical-lead"><strong>{trend.direction_label} · {trend.state_label}</strong><p>표시 {data.display_start_date} ~ {data.display_end_date} ({data.display_observation_count}개) · 분석 {data.analysis_start_date} ~ {data.analysis_end_date} ({data.analysis_observation_count}개)</p></section>
            <dl className="training-technical-metrics">{metric("추세 강도", num(trend.trend_strength))}{metric("회귀 기울기", num(trend.regression_slope))}{metric("정규화 기울기", pct(trend.normalized_slope))}{metric("R²", num(trend.r_squared))}{metric("채널 위치", pct(Number(trend.channel_position || 0) * 100))}{metric("지속기간", trend.duration_count ? trend.duration_count + "개 봉" : "-")}</dl>
          </> : tab === "moving" ? <>
            <section className="training-technical-lead"><strong>{moving.arrangement_label}</strong><p>{moving.latest_cross ? moving.latest_cross.label + " · " + moving.latest_cross.date : "최근 MA5·MA20 교차 없음"}</p></section>
            <dl className="training-technical-metrics">{Object.entries(moving.values || {}).map(([key, item]) => metric(key.toUpperCase(), num(item.value) + " · 현재가 대비 " + pct(item.distance_pct)))}</dl>
          </> : tab === "volume" ? <>
            <section className="training-technical-lead"><strong>거래량 관찰</strong><p>{String(volume.observation || "-")}</p></section>
            <dl className="training-technical-metrics">{metric("현재 거래량", num(volume.current))}{metric("5일 평균", num(volume.average_5))}{metric("20일 평균", num(volume.average_20))}{metric("20일 평균 배율", volume.ratio_to_average_20 == null ? "-" : Number(volume.ratio_to_average_20).toFixed(2) + "배")}{metric("상승 캔들 평균", num(volume.up_candle_average))}{metric("하락 캔들 평균", num(volume.down_candle_average))}</dl>
          </> : <>
            <dl className="training-technical-metrics">{metric("최근 확정 전고점", position.confirmed_high ? num(position.confirmed_high.value) + " · " + pct(position.confirmed_high.distance_pct) : "-")}{metric("최근 확정 전저점", position.confirmed_low ? num(position.confirmed_low.value) + " · " + pct(position.confirmed_low.distance_pct) : "-")}{metric("스윙 고점 후보", position.high_candidate ? num(position.high_candidate.value) + " · " + position.high_candidate.date : "-")}{metric("스윙 저점 후보", position.low_candidate ? num(position.low_candidate.value) + " · " + position.low_candidate.date : "-")}{metric("60일 최고", num(position.range_60?.high))}{metric("60일 최저", num(position.range_60?.low))}</dl>
          </>}
        </div>
        <footer>{editing ? <><button type="button" onClick={() => setDraft(DEFAULT_CONFIGURATION)}>기본값 복원</button><div><button type="button" onClick={() => setEditing(false)}>취소</button><button className="primary" type="button" onClick={() => { onApplyConfiguration(draft); setEditing(false); }}>현재 화면에 적용</button></div></> : <><button title="변경한 설정은 현재 화면에만 적용되고 저장되지 않습니다." type="button" onClick={() => setEditing(true)}>설정 조정</button><button type="button" onClick={onClose}>닫기</button></>}</footer>
      </aside>
    </div>
  );
}
