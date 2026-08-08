import { useEffect, useRef } from "react";
import MarketThemePriceFlowPanel from "@/components/marketThemes/MarketThemePriceFlowPanel";

type MarketThemePriceFlowModalProps = {
  stockId: number;
  stockName: string;
  themeId: number;
  focusDate?: string | null;
  onClose: () => void;
  className?: string;
};

export default function MarketThemePriceFlowModal({
  stockId,
  stockName,
  themeId,
  focusDate,
  onClose,
  className = "",
}: MarketThemePriceFlowModalProps) {
  const closeButtonRef = useRef<HTMLButtonElement | null>(null);

  useEffect(() => {
    window.setTimeout(() => closeButtonRef.current?.focus(), 0);
  }, []);

  return (
    <div
      className={`market-flow-modal-backdrop ${className}`.trim()}
      onClick={onClose}
      onKeyDown={(event) => {
        if (event.key === "Escape") {
          event.preventDefault();
          event.stopPropagation();
          onClose();
          return;
        }
        if (event.key !== "Tab") return;
        const focusable = Array.from(
          event.currentTarget.querySelectorAll<HTMLElement>(
            'button:not(:disabled), [href], input:not(:disabled), select:not(:disabled), textarea:not(:disabled), [tabindex]:not([tabindex="-1"])',
          ),
        ).filter((element) => element.offsetParent !== null);
        if (!focusable.length) return;
        const first = focusable[0];
        const last = focusable[focusable.length - 1];
        if (event.shiftKey && document.activeElement === first) {
          event.preventDefault();
          last.focus();
        } else if (!event.shiftKey && document.activeElement === last) {
          event.preventDefault();
          first.focus();
        }
      }}
    >
      <section
        className="market-flow-modal"
        role="dialog"
        aria-modal="true"
        aria-label={`${stockName} 가격·수급 추이`}
        onClick={(event) => event.stopPropagation()}
      >
        <header className="market-flow-modal-header">
          <div><h3>{stockName}</h3><p>가격·수급 추이</p></div>
          <button ref={closeButtonRef} type="button" className="btn btn-secondary btn-table-sm" onClick={onClose}>닫기</button>
        </header>
        <div className="market-flow-modal-body">
          <MarketThemePriceFlowPanel stockId={stockId} themeId={themeId} focusDate={focusDate} />
        </div>
      </section>
    </div>
  );
}
