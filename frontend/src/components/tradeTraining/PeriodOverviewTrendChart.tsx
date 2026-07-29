import { useLayoutEffect, useMemo, useRef, useState } from "react";
import type { MultiPeriodSelectedDetail } from "@/types/multiPeriodTechnicalAnalysis";

const formatPrice = (value: number) => Math.round(value).toLocaleString("ko-KR");
const formatVolume = (value: number) => Math.round(value).toLocaleString("ko-KR");

export default function PeriodOverviewTrendChart({ detail }: { detail: MultiPeriodSelectedDetail }) {
  const candles = detail.chart_candles || [];
  const overlay = detail.period_overlay;
  const [hovered, setHovered] = useState<number | null>(null);
  const chartRef = useRef<SVGSVGElement | null>(null);
  const [viewWidth, setViewWidth] = useState(1040);
  useLayoutEffect(() => {
    const svg = chartRef.current;
    if (!svg) return;
    const updateViewWidth = () => {
      const rect = svg.getBoundingClientRect();
      if (rect.width > 0 && rect.height > 0) {
        setViewWidth(Math.max(760, Math.round(540 * rect.width / rect.height)));
      }
    };
    updateViewWidth();
    const observer = new ResizeObserver(updateViewWidth);
    observer.observe(svg);
    return () => observer.disconnect();
  }, []);
  const layout = useMemo(() => {
    const width = viewWidth;
    const height = 540;
    const pad = { top: 30, right: 68, bottom: 28, left: 58 };
    const priceHeight = 360;
    const volumeTop = 416;
    const volumeHeight = 72;
    const plotWidth = width - pad.left - pad.right;
    const slot = plotWidth / Math.max(candles.length, 1);
    const channelValues = [
      ...(overlay?.upper_channel_points || []).map((point) => Number(point.value)),
      ...(overlay?.lower_channel_points || []).map((point) => Number(point.value)),
    ];
    const priceValues = [...candles.flatMap((item) => [item.high, item.low]), ...channelValues];
    const rawMin = priceValues.length ? Math.min(...priceValues) : 0;
    const rawMax = priceValues.length ? Math.max(...priceValues) : 1;
    const margin = Math.max(1, (rawMax - rawMin) * .06);
    const min = rawMin - margin;
    const max = rawMax + margin;
    const span = Math.max(1, max - min);
    const maxVolume = Math.max(1, ...candles.map((item) => item.volume || 0));
    return {
      width, height, pad, priceHeight, volumeTop, volumeHeight, plotWidth, slot, min, max, span, maxVolume,
      x: (index: number) => pad.left + slot * index + slot / 2,
      y: (value: number) => pad.top + ((max - value) / span) * priceHeight,
    };
  }, [candles, overlay, viewWidth]);

  if (!candles.length || !overlay) {
    return <div className="training-period-chart-empty">선택 기간의 차트 데이터가 부족합니다.</div>;
  }

  const indexByDate = new Map(candles.map((item, index) => [item.trade_date, index]));
  const points = (series: Array<{ date: string; value: number }>) => series
    .map((point) => {
      const index = indexByDate.get(point.date);
      return index === undefined ? null : `${layout.x(index)},${layout.y(Number(point.value))}`;
    })
    .filter(Boolean)
    .join(" ");
  const line = (key: "ma20" | "ma60") => candles
    .map((item, index) => {
      const value = item.moving_averages?.[key];
      return value == null ? null : `${layout.x(index)},${layout.y(Number(value))}`;
    })
    .filter(Boolean)
    .join(" ");
  const bodyWidth = Math.max(.8, Math.min(7, layout.slot * .62));
  const currentIndex = candles.length - 1;
  const current = candles[currentIndex];
  const hover = hovered == null ? null : candles[hovered];
  const hoverX = hovered == null ? 0 : layout.x(hovered);
  const tooltipX = Math.min(layout.width - layout.pad.right - 176, Math.max(layout.pad.left + 4, hoverX + 12));

  return (
    <div className={`training-period-chart-shell ${candles.length >= 500 ? "dense" : ""}`}>
      <svg
        ref={chartRef}
        viewBox={`0 0 ${layout.width} ${layout.height}`}
        role="img"
        aria-label={`선택 기간 전체 캔들차트, ${candles.length}개 봉`}
        onPointerMove={(event) => {
          const rect = event.currentTarget.getBoundingClientRect();
          const viewX = ((event.clientX - rect.left) / rect.width) * layout.width;
          const index = Math.round((viewX - layout.pad.left - layout.slot / 2) / layout.slot);
          setHovered(Math.max(0, Math.min(candles.length - 1, index)));
        }}
        onPointerLeave={() => setHovered(null)}
      >
        <rect width={layout.width} height={layout.height} rx={12} fill="#fff" />
        {[0, .25, .5, .75, 1].map((rate) => {
          const y = layout.pad.top + layout.priceHeight * rate;
          const price = layout.max - layout.span * rate;
          return <g key={rate}>
            <line x1={layout.pad.left} x2={layout.width - layout.pad.right} y1={y} y2={y} stroke="#e7edf5" />
            <text x={layout.width - layout.pad.right + 8} y={y + 4} fontSize="11" fill="#64748b">{formatPrice(price)}</text>
          </g>;
        })}
        <line x1={layout.x(0)} x2={layout.x(0)} y1={layout.pad.top} y2={layout.volumeTop + layout.volumeHeight} stroke="#94a3b8" strokeDasharray="4 5" />
        <text x={layout.x(0) + 7} y={layout.pad.top + 14} fontSize="11" fontWeight="700" fill="#475569">기간 분석 시작</text>
        <polyline points={points(overlay.upper_channel_points || [])} fill="none" stroke="#8fa2bc" strokeWidth={1.2} />
        <polyline points={points(overlay.lower_channel_points || [])} fill="none" stroke="#8fa2bc" strokeWidth={1.2} />
        <polyline points={points(overlay.regression_points || [])} fill="none" stroke="#172033" strokeWidth={1.8} strokeDasharray="7 5" />
        {line("ma20") ? <polyline points={line("ma20")} fill="none" stroke="#e3a500" strokeWidth={1.5} opacity={.9} /> : null}
        {line("ma60") ? <polyline points={line("ma60")} fill="none" stroke="#15965a" strokeWidth={1.4} opacity={.9} /> : null}
        {candles.map((item, index) => {
          const up = item.close >= item.open;
          const color = up ? "#dc2626" : "#2563eb";
          const bodyFill = up ? "#fee2e2" : "#dbeafe";
          const x = layout.x(index);
          const top = layout.y(Math.max(item.open, item.close));
          const bottom = layout.y(Math.min(item.open, item.close));
          const volumeHeight = (item.volume / layout.maxVolume) * layout.volumeHeight;
          return <g key={item.trade_date}>
            <line x1={x} x2={x} y1={layout.y(item.high)} y2={layout.y(item.low)} stroke={color} strokeWidth={Math.max(.55, Math.min(1.15, layout.slot * .16))} />
            <rect x={x - bodyWidth / 2} y={top} width={bodyWidth} height={Math.max(.75, bottom - top)} fill={bodyFill} stroke={color} strokeWidth={.75} />
            <rect x={x - bodyWidth / 2} y={layout.volumeTop + layout.volumeHeight - volumeHeight} width={bodyWidth} height={volumeHeight} fill={color} opacity={.25} />
          </g>;
        })}
        <circle cx={layout.x(currentIndex)} cy={layout.y(current.close)} r={4} fill={current.close >= current.open ? "#dc2626" : "#2563eb"} stroke="#fff" strokeWidth={1.5} />
        {hover ? <g pointerEvents="none">
          <line x1={hoverX} x2={hoverX} y1={layout.pad.top} y2={layout.volumeTop + layout.volumeHeight} stroke="#334155" strokeWidth={1} strokeDasharray="3 4" opacity={.65} />
          <rect x={tooltipX} y={layout.pad.top + 6} width={168} height={93} rx={7} fill="#0f172a" opacity={.94} />
          <text x={tooltipX + 10} y={layout.pad.top + 24} fontSize="11" fontWeight="700" fill="#fff">{hover.trade_date}</text>
          <text x={tooltipX + 10} y={layout.pad.top + 42} fontSize="10" fill="#dbeafe">시 {formatPrice(hover.open)}  고 {formatPrice(hover.high)}</text>
          <text x={tooltipX + 10} y={layout.pad.top + 58} fontSize="10" fill="#dbeafe">저 {formatPrice(hover.low)}  종 {formatPrice(hover.close)}</text>
          <text x={tooltipX + 10} y={layout.pad.top + 76} fontSize="10" fill="#cbd5e1">거래량 {formatVolume(hover.volume)}</text>
        </g> : null}
        <line x1={layout.pad.left} x2={layout.width - layout.pad.right} y1={layout.volumeTop + layout.volumeHeight} y2={layout.volumeTop + layout.volumeHeight} stroke="#cbd5e1" />
        <text x={layout.pad.left} y={layout.height - 8} fontSize="10" fill="#64748b">{candles[0].trade_date}</text>
        <text x={layout.width - layout.pad.right} y={layout.height - 8} textAnchor="end" fontSize="10" fill="#64748b">{current.trade_date}</text>
      </svg>
      <div className="training-period-chart-legend">
        <span><i className="candles" />캔들·거래량</span>
        <span><i className="regression" />기간 전체 회귀선</span>
        <span><i className="channel" />상·하단 채널</span>
        <span><i className="ma20" />MA20</span>
        <span><i className="ma60" />MA60</span>
        {candles.length >= 500 ? <b>Dense · {candles.length.toLocaleString("ko-KR")}봉</b> : null}
      </div>
    </div>
  );
}
