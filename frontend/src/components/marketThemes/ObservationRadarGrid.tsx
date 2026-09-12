import { useEffect, useId, useLayoutEffect, useRef, useState } from "react";
import { Info } from "lucide-react";
import type { MarketThemeObservationItem } from "@/types/marketTheme";

const SIGNAL_AXES = [
  { key: "price_score", label: "가격강도" },
  { key: "flow_score", label: "수급강도" },
  { key: "flow_acceleration_score", label: "수급가속" },
  { key: "breadth_score", label: "확산" },
  { key: "sustainability_score", label: "지속성" },
] as const;
const LEGACY_AXES = [
  { key: "price_score", label: "가격" },
  { key: "flow_score", label: "수급" },
  { key: "breadth_score", label: "확산" },
  { key: "technical_score", label: "기술" },
  { key: "data_coverage_rate", label: "완전성", ratio: true },
] as const;
type AxisKey = (typeof SIGNAL_AXES)[number]["key"];
const AXIS_DESCRIPTIONS: Record<AxisKey, string> = {
  price_score: "오늘과 최근 가격 방향·상대강도를 활성 테마 전체의 0~100 상대 위치로 나타냅니다.",
  flow_score: "테마수급추이와 같은 외국인·기관 합산 수급을 활성 테마 전체에서 비교합니다.",
  flow_acceleration_score: "최근 3일 수급과 직전 3일 수급의 변화 속도를 활성 테마 전체에서 비교합니다.",
  breadth_score: "상승 종목 비율과 외국인·기관 합산 순매수가 양수인 종목 비율로 테마 내부 참여 폭을 나타냅니다.",
  sustainability_score: "연속 순매수·수급가속·확산 유지·가격 과열·종목 쏠림을 같은 방향으로 종합한 상대점수입니다.",
};
const cx = 120;
const cy = 96;
const radius = 72;
const point = (index: number, ratio: number) => {
  const angle = -Math.PI / 2 + index * Math.PI * 2 / 5;
  return [cx + Math.cos(angle) * radius * ratio, cy + Math.sin(angle) * radius * ratio] as const;
};
const polygon = (ratio: number) => SIGNAL_AXES.map((_, index) => point(index, ratio).join(",")).join(" ");
const scoreText = (value: number | null | undefined) => value == null ? "-" : value.toFixed(1);
const gapText = (value: number | null | undefined) => value == null ? "-" : `${value > 0 ? "+" : ""}${value.toFixed(1)}`;

export default function ObservationRadarGrid(props: {
  items: MarketThemeObservationItem[];
  statusNames: Record<string, string>;
  onThemeClick: (themeId: number) => void;
  hideHeader?: boolean;
}) {
  const [infoOpen, setInfoOpen] = useState(false);
  const infoRef = useRef<HTMLDivElement | null>(null);
  const popoverRef = useRef<HTMLDivElement | null>(null);
  const infoId = useId();

  useEffect(() => {
    if (!infoOpen) return;
    const closeOnPointerDown = (event: MouseEvent) => {
      if (!infoRef.current?.contains(event.target as Node)) setInfoOpen(false);
    };
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") setInfoOpen(false);
    };
    document.addEventListener("mousedown", closeOnPointerDown);
    window.addEventListener("keydown", closeOnEscape);
    return () => {
      document.removeEventListener("mousedown", closeOnPointerDown);
      window.removeEventListener("keydown", closeOnEscape);
    };
  }, [infoOpen]);

  useLayoutEffect(() => {
    if (!infoOpen) return;
    const updatePopoverPosition = () => {
      const anchor = infoRef.current;
      const popover = popoverRef.current;
      if (!anchor || !popover) return;

      const margin = 12;
      popover.style.top = "calc(100% + 8px)";
      popover.style.bottom = "auto";
      popover.style.maxHeight = "560px";
      popover.style.transform = "none";

      const anchorRect = anchor.getBoundingClientRect();
      const naturalRect = popover.getBoundingClientRect();
      const availableBelow = window.innerHeight - naturalRect.top - margin;
      const availableAbove = anchorRect.top - margin;
      if (availableBelow < Math.min(naturalRect.height, 240) && availableAbove > availableBelow) {
        popover.style.top = "auto";
        popover.style.bottom = "calc(100% + 8px)";
        popover.style.maxHeight = `${Math.max(160, Math.min(560, availableAbove))}px`;
      } else {
        popover.style.maxHeight = `${Math.max(160, Math.min(560, availableBelow))}px`;
      }

      const positionedRect = popover.getBoundingClientRect();
      const leftCorrection = Math.max(0, margin - positionedRect.left);
      const rightCorrection = Math.min(0, window.innerWidth - margin - positionedRect.right);
      popover.style.transform = `translateX(${leftCorrection + rightCorrection}px)`;
    };

    updatePopoverPosition();
    window.addEventListener("resize", updatePopoverPosition);
    window.addEventListener("scroll", updatePopoverPosition, true);
    return () => {
      window.removeEventListener("resize", updatePopoverPosition);
      window.removeEventListener("scroll", updatePopoverPosition, true);
    };
  }, [infoOpen]);

  return <section className={`observation-radar-section${props.hideHeader ? " is-headerless" : ""}`} aria-label={props.hideHeader ? "D+1 가격·수급 신호 구조" : undefined} aria-labelledby={props.hideHeader ? undefined : "observation-radar-title"}>
    {!props.hideHeader ? <header>
      <div>
        <div className="observation-radar-title-row" ref={infoRef}>
          <h3 id="observation-radar-title">테마 구조 비교</h3>
          <button
            type="button"
            className="observation-radar-info-button"
            aria-label="테마 구조 비교 기준 설명"
            aria-expanded={infoOpen}
            aria-controls={infoId}
            onClick={() => setInfoOpen((value) => !value)}
          >
            <Info size={14} aria-hidden="true" />
          </button>
          {infoOpen ? <div ref={popoverRef} id={infoId} className="observation-radar-info-popover" role="dialog" aria-label="테마 구조 비교 기준 설명">
            <strong>테마 구조 비교 기준</strong>
            <p>다섯 축은 동일 기준일의 활성 테마 전체에서 계산한 0~100 상대점수입니다.</p>
            <dl>
              {SIGNAL_AXES.map((axis) => <div key={axis.key}>
                <dt>{axis.label}</dt>
                <dd>{AXIS_DESCRIPTIONS[axis.key]}</dd>
              </div>)}
            </dl>
            <div className="observation-radar-info-note">
              <p>데이터 완전성은 예측 축과 분리해 화면 상단 운영 상태에서 확인합니다.</p>
              <p>개편 전에 저장된 결과는 당시 계산된 가격·수급·확산·기술·완전성 5축으로 즉시 표시합니다.</p>
              <p>레이더는 가격×수급 단계를 설명하며, D+1 후보점수의 순위를 직접 결정하지 않습니다.</p>
            </div>
          </div> : null}
        </div>
        <p>가격강도·수급강도·수급가속·확산·지속가능성으로 현재 단계를 비교합니다.</p>
      </div>
      <span>동일 축 · 최대 100</span>
    </header> : null}
    <div className="observation-radar-grid">
      {props.items.map((item) => {
        const signalRadarAvailable = item.flow_acceleration_score != null && item.sustainability_score != null;
        const axes = signalRadarAvailable ? SIGNAL_AXES : LEGACY_AXES;
        const values = axes.map((axis) => {
          const raw = item[axis.key];
          return raw == null ? null : Math.max(0, Math.min(100, "ratio" in axis && axis.ratio ? raw * 100 : raw));
        });
        const complete = values.every((value) => value != null);
        const dataPoints = complete ? values.map((value, index) => point(index, (value ?? 0) / 100).join(",")).join(" ") : null;
        const detail = axes.map((axis, index) => `${axis.label} ${scoreText(values[index])}`).join(", ");
        const actualText = item.actual_relative_strength == null ? "실측 대기" : `실측 ${scoreText(item.actual_relative_strength)} · Gap ${gapText(item.relative_strength_gap)}`;
        return <button type="button" key={item.theme_id} className="observation-radar-card" onClick={() => props.onThemeClick(item.theme_id)} aria-label={`${item.observation_rank ?? "-"}위 ${item.theme_name}, ${item.stage_label ?? "단계 대기"}, D+1 후보 ${scoreText(item.relative_strength_score)}, ${detail}, ${actualText}`} title={detail}>
          <header><b>#{item.observation_rank ?? "-"}</b><span className={`theme-observation-state stage-${item.stage_code?.toLowerCase() ?? "pending"}`}>{item.stage_label ?? props.statusNames[item.status_code] ?? "분석 대기"}</span></header>
          <div className="observation-radar-visual">
            <svg viewBox="0 0 240 192" role="img" aria-label={`${item.theme_name} 5축 구조`}>
              {[.25, .5, .75, 1].map((ratio) => <polygon key={ratio} points={polygon(ratio)} className="observation-radar-grid-line" />)}
              {axes.map((axis, index) => { const [x, y] = point(index, 1); const [labelX, labelY] = point(index, 1.2); return <g key={axis.key}><line x1={cx} y1={cy} x2={x} y2={y} className="observation-radar-axis" /><circle cx={labelX} cy={labelY} r="16" className="observation-radar-axis-hit"><title>{axis.label} {scoreText(values[index])}</title></circle><text x={labelX} y={labelY} className="observation-radar-label">{axis.label}</text></g>; })}
              {dataPoints ? <><polygon points={dataPoints} className="observation-radar-data" />{values.map((value, index) => { const [x, y] = point(index, (value ?? 0) / 100); return <circle key={axes[index].key} cx={x} cy={y} r="3" className="observation-radar-point"><title>{axes[index].label} {scoreText(value)}</title></circle>; })}</> : null}
            </svg>
            <span className="observation-radar-center"><b>{item.theme_name}</b><small>D+1 후보</small><strong>{scoreText(item.relative_strength_score ?? item.relative_strength_probability)}</strong></span>
          </div>
          <footer>{signalRadarAvailable ? (complete ? item.stage_summary ?? actualText : `구조 데이터 부족 · ${item.stage_summary ?? actualText}`) : `기존 저장 5축 · ${actualText}`}</footer>
        </button>;
      })}
    </div>
  </section>;
}
