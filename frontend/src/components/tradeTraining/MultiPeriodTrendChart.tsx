import { useMemo } from "react";
import type { MultiPeriodSelectedDetail } from "@/types/multiPeriodTechnicalAnalysis";

const MA_STYLES: Record<string, { color: string; width: number }> = {
  ma5: { color: "#111827", width: 1.2 },
  ma10: { color: "#ef4444", width: 1.2 },
  ma20: { color: "#eab308", width: 1.8 },
  ma60: { color: "#16a34a", width: 1.3 },
  ma120: { color: "#2563eb", width: 1.3 },
};

export default function MultiPeriodTrendChart({ detail }: { detail: MultiPeriodSelectedDetail }) {
  const candles = detail.chart_candles || [];
  const overlay = detail.trend_overlay;
  const events = detail.transition_events || [];
  const layout = useMemo(() => {
    const width = 960;
    const height = 430;
    const pad = { top: 28, right: 58, bottom: 30, left: 58 };
    const priceHeight = 292;
    const volumeTop = pad.top + priceHeight + 20;
    const volumeHeight = 58;
    const plotWidth = width - pad.left - pad.right;
    const slot = plotWidth / Math.max(candles.length, 1);
    const values = candles.flatMap((item) => [item.high, item.low]);
    const min = values.length ? Math.min(...values) : 0;
    const max = values.length ? Math.max(...values) : 1;
    const span = Math.max(1, max - min);
    const maxVolume = Math.max(1, ...candles.map((item) => item.volume || 0));
    return {
      width, height, pad, priceHeight, volumeTop, volumeHeight, plotWidth, slot, min, max, span, maxVolume,
      x: (index: number) => pad.left + slot * index + slot / 2,
      y: (value: number) => pad.top + ((max - value) / span) * priceHeight,
    };
  }, [candles]);
  if (!candles.length) return <div className="training-trend-chart-empty">선택 기간의 차트 데이터가 부족합니다.</div>;

  const indexByDate = new Map(candles.map((item, index) => [item.trade_date, index]));
  const polyline = (points: Array<{ date: string; value: number }>) => points
    .map((point) => {
      const index = indexByDate.get(point.date);
      return index === undefined ? null : `${layout.x(index)},${layout.y(Number(point.value))}`;
    })
    .filter(Boolean)
    .join(" ");
  const trendStartIndex = overlay.trend_start_date
    ? candles.findIndex((item) => item.trade_date >= String(overlay.trend_start_date))
    : -1;
  const bodyWidth = Math.max(1.2, Math.min(7, layout.slot * 0.58));
  const current = overlay.current_point;
  const currentIndex = current ? indexByDate.get(current.date) : undefined;

  return (
    <div className="training-trend-chart-shell">
      <svg viewBox={`0 0 ${layout.width} ${layout.height}`} role="img" aria-label="선택 기간 추세 캔들차트">
        <rect width={layout.width} height={layout.height} rx={10} fill="#fff" />
        {[0, .25, .5, .75, 1].map((rate) => {
          const y = layout.pad.top + layout.priceHeight * rate;
          const price = layout.max - layout.span * rate;
          return <g key={rate}>
            <line x1={layout.pad.left} x2={layout.width-layout.pad.right} y1={y} y2={y} stroke="#e8edf4" />
            <text x={layout.width-layout.pad.right+7} y={y+4} fontSize="10" fill="#64748b">{Math.round(price).toLocaleString("ko-KR")}</text>
          </g>;
        })}
        {trendStartIndex >= 0 ? <g pointerEvents="none">
          <rect x={layout.x(trendStartIndex)-layout.slot/2} y={layout.pad.top} width={layout.width-layout.pad.right-(layout.x(trendStartIndex)-layout.slot/2)} height={layout.priceHeight} fill="#64748b" opacity={0.055} />
          <line x1={layout.x(trendStartIndex)} x2={layout.x(trendStartIndex)} y1={layout.pad.top} y2={layout.pad.top+layout.priceHeight} stroke="#64748b" strokeWidth={1} strokeDasharray="4 5" />
          <text x={Math.min(layout.width-layout.pad.right-122, layout.x(trendStartIndex)+6)} y={layout.pad.top+13} fontSize="10" fontWeight="700" fill="#475569">현재 추세 시작 {overlay.trend_start_date}</text>
        </g> : null}
        {Object.entries(MA_STYLES).map(([key, style]) => {
          const points = candles.map((item, index) => {
            const value = item.moving_averages?.[key];
            return value == null ? null : `${layout.x(index)},${layout.y(Number(value))}`;
          }).filter(Boolean).join(" ");
          return points ? <polyline key={key} points={points} fill="none" stroke={style.color} strokeWidth={style.width} opacity={.85} /> : null;
        })}
        {candles.map((item, index) => {
          const up = item.close >= item.open;
          const color = up ? "#ef4444" : "#2563eb";
          const x = layout.x(index);
          const top = layout.y(Math.max(item.open, item.close));
          const bottom = layout.y(Math.min(item.open, item.close));
          return <g key={item.trade_date}>
            <line x1={x} x2={x} y1={layout.y(item.high)} y2={layout.y(item.low)} stroke={color} strokeWidth={Math.max(.7, Math.min(1.2, layout.slot*.15))} />
            <rect x={x-bodyWidth/2} y={top} width={bodyWidth} height={Math.max(1, bottom-top)} fill={up ? "#fff" : color} stroke={color} strokeWidth={.8} />
            <rect x={x-bodyWidth/2} y={layout.volumeTop+layout.volumeHeight-(item.volume/layout.maxVolume)*layout.volumeHeight} width={bodyWidth} height={(item.volume/layout.maxVolume)*layout.volumeHeight} fill={color} opacity={.24} />
          </g>;
        })}
        <polyline points={polyline(overlay.upper_channel_points || [])} fill="none" stroke="#94a3b8" strokeWidth={1} />
        <polyline points={polyline(overlay.lower_channel_points || [])} fill="none" stroke="#94a3b8" strokeWidth={1} />
        <polyline points={polyline(overlay.regression_points || [])} fill="none" stroke="#1f2937" strokeWidth={1.5} strokeDasharray="6 4" />
        {events.map((event) => {
          const index = indexByDate.get(event.observation_date);
          if (index === undefined) return null;
          const y = layout.y(candles[index].high) - 7;
          return <g key={`${event.observation_date}-${event.current_state}`}>
            <path d={`M ${layout.x(index)} ${y-5} L ${layout.x(index)-4} ${y+2} L ${layout.x(index)+4} ${y+2} Z`} fill="#7c3aed" />
            <title>{event.observation_date} · {event.previous_state_label} → {event.current_state_label}</title>
          </g>;
        })}
        {current && currentIndex !== undefined ? <circle cx={layout.x(currentIndex)} cy={layout.y(Number(current.value))} r={3.2} fill="#111827" stroke="#fff" strokeWidth={1} /> : null}
        <line x1={layout.pad.left} x2={layout.width-layout.pad.right} y1={layout.volumeTop+layout.volumeHeight} y2={layout.volumeTop+layout.volumeHeight} stroke="#cbd5e1" />
        <text x={layout.pad.left} y={layout.height-8} fontSize="10" fill="#64748b">{candles[0].trade_date}</text>
        <text x={layout.width-layout.pad.right} y={layout.height-8} textAnchor="end" fontSize="10" fill="#64748b">{candles[candles.length-1].trade_date}</text>
      </svg>
      <div className="training-trend-chart-legend">
        <span><i className="actual" />캔들</span><span><i className="regression" />현재 추세 회귀선</span><span><i className="channel" />추세 채널</span><span><i className="transition" />상태 전환</span>
      </div>
    </div>
  );
}
