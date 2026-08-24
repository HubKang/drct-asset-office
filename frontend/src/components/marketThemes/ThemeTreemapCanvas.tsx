import { useEffect, useMemo, useRef, useState } from "react";
import type { CSSProperties, ReactNode } from "react";

import { getThemeReturnHeatmapColor, getThemeReturnTextColor } from "@/utils/marketThemeReturnColor";
import { buildTreemapLayout, getTreemapTextMetrics } from "@/utils/treemapLayout";

export type ThemeTreemapViewItem = {
  id: number;
  title: string;
  rank: number;
  value: number | null;
  areaValue: number;
  stockCount: number;
  tooltip: string;
};

type CellLevel = "large" | "medium" | "small" | "tiny";

const cellLevel = (width: number, height: number): CellLevel => {
  if (width >= 250 && height >= 100) return "large";
  if (width >= 150 && height >= 70) return "medium";
  if (width >= 80 && height >= 50) return "small";
  return "tiny";
};

export default function ThemeTreemapCanvas({ title, subtitle, tools, items, selectedId, emptyMessage, onSelect }: {
  title: string;
  subtitle: string;
  tools: ReactNode;
  items: ThemeTreemapViewItem[];
  selectedId: number | null;
  emptyMessage: string;
  onSelect: (id: number) => void;
}) {
  const canvasRef = useRef<HTMLDivElement | null>(null);
  const [size, setSize] = useState({ width: 0, height: 0 });
  const layout = useMemo(() => {
    const started = performance.now();
    const rects = buildTreemapLayout(items.map((item) => ({ id: String(item.id), value: item.areaValue })), { preserveOrder: true });
    return { rects: new Map(rects.map((rect) => [Number(rect.id), rect])), durationMs: performance.now() - started };
  }, [items]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const update = () => setSize({ width: canvas.clientWidth, height: canvas.clientHeight });
    update();
    const observer = new ResizeObserver(update);
    observer.observe(canvas);
    return () => observer.disconnect();
  }, [items.length]);

  return <section className="realtime-theme-placeholder" aria-label={title}>
    <div className="realtime-theme-treemap-head">
      <div><strong>{title}</strong><span>{subtitle}</span></div>
      <div className="realtime-theme-treemap-tools">{tools}<small>Layout {layout.durationMs.toFixed(2)}ms</small></div>
    </div>
    {items.some((item) => item.areaValue > 0) ? <div ref={canvasRef} className="realtime-theme-treemap-canvas">{items.map((item) => {
      const rect = layout.rects.get(item.id);
      if (!rect) return null;
      const level = cellLevel(size.width * rect.width / 100, size.height * rect.height / 100);
      const metrics = getTreemapTextMetrics(rect, item.title, { variant: "marketTrend" });
      const style = {
        left: `calc(${rect.x}% + 2px)`, top: `calc(${rect.y}% + 2px)`,
        width: `calc(${rect.width}% - 4px)`, height: `calc(${rect.height}% - 4px)`,
        background: getThemeReturnHeatmapColor(item.value), color: getThemeReturnTextColor(item.value),
        "--realtime-title-size": `${metrics.titleFontSize}px`, "--realtime-title-lines": metrics.titleLineClamp,
      } as CSSProperties;
      const formatted = item.value == null ? "-" : `${item.value > 0 ? "+" : ""}${item.value.toFixed(2)}%`;
      return <button key={item.id} type="button" className={`realtime-theme-tile is-${level}${selectedId === item.id ? " is-selected" : ""}`} style={style} title={item.tooltip} aria-pressed={selectedId === item.id} onClick={() => onSelect(item.id)}><b>{item.rank}</b><strong>{item.title}</strong><em>{formatted} <span>({item.stockCount}종목)</span></em></button>;
    })}</div> : <p>{emptyMessage}</p>}
  </section>;
}
