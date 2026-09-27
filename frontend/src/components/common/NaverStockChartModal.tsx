import { useEffect } from "react";
import { buildNaverStockFullChartUrl, normalizeNaverStockCode } from "@/utils/naverChart";

export type NaverStockChartModalData = {
  url: string;
  alt: string;
  title?: string;
  stockCode?: string | number | null;
};

function inferStockCode(chart: NaverStockChartModalData): string {
  const explicitCode = normalizeNaverStockCode(chart.stockCode);
  if (explicitCode) return explicitCode;

  const pathMatch = chart.url.match(/\/(?:day|week|month)\/(\d{6})\.png/i)
    ?? chart.url.match(/\/[FI]_(\d{6})\.png/i);
  return pathMatch?.[1] ?? "";
}

export default function NaverStockChartModal({ chart, onClose }: {
  chart: NaverStockChartModalData;
  onClose: () => void;
}) {
  const stockCode = inferStockCode(chart);
  const naverChartUrl = buildNaverStockFullChartUrl(stockCode);

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [onClose]);

  return (
    <div className="theme-linked-stock-chart-modal" onClick={onClose}>
      <section className="theme-linked-stock-chart-modal-panel" role="dialog" aria-modal="true" aria-label={chart.title || chart.alt} onClick={(event) => event.stopPropagation()}>
        <header className="theme-linked-stock-chart-modal-header">
          <h3>{chart.title || chart.alt}</h3>
          <div className="theme-linked-stock-chart-modal-actions">
            {naverChartUrl ? (
              <a className="btn btn-secondary btn-table-sm" href={naverChartUrl} target="_blank" rel="noopener noreferrer">
                네이버차트
              </a>
            ) : null}
            <button type="button" className="btn btn-secondary btn-table-sm" onClick={onClose}>닫기</button>
          </div>
        </header>
        <img src={chart.url} alt={chart.alt} className="theme-linked-stock-chart-modal-image theme-linked-stock-chart-modal-image-clickable" onClick={onClose} />
      </section>
    </div>
  );
}
