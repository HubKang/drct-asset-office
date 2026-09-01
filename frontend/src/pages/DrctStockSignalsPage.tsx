import { useState } from "react";

import PageHeader from "@/components/common/PageHeader";
import SignalPerformanceTab from "@/components/drctStockSignals/SignalPerformanceTab";
import SignalResearchTab from "@/components/drctStockSignals/SignalResearchTab";
import StockSignalTab from "@/components/drctStockSignals/StockSignalTab";

type SignalTab = "signals" | "research" | "performance";

const TABS: Array<{ id: SignalTab; label: string }> = [
  { id: "signals", label: "종목 시그널" },
  { id: "research", label: "검색식 관리 & 성공패턴 학습" },
  { id: "performance", label: "시그널 성과" },
];

function DrctStockSignalsPage() {
  const [activeTab, setActiveTab] = useState<SignalTab>("signals");

  return (
    <div className="drct-stock-signals-page">
      <PageHeader
        title="DrCT 종목 시그널"
        description="국내 테마 연결 종목에서 검색식과 학습된 성공패턴을 이용해 관찰 가치가 높은 종목 시그널을 선별합니다."
      />

      <nav className="drct-signal-tabs" aria-label="DrCT 종목 시그널 화면" role="tablist">
        {TABS.map((tab) => (
          <button
            key={tab.id}
            type="button"
            className={activeTab === tab.id ? "is-active" : ""}
            id={`drct-signal-tab-${tab.id}`}
            aria-controls={`drct-signal-panel-${tab.id}`}
            aria-selected={activeTab === tab.id}
            role="tab"
            onClick={() => setActiveTab(tab.id)}
          >
            {tab.label}
          </button>
        ))}
      </nav>

      <div
        className="drct-signal-tab-panel"
        id={`drct-signal-panel-${activeTab}`}
        aria-labelledby={`drct-signal-tab-${activeTab}`}
        role="tabpanel"
      >
        {activeTab === "signals" ? <StockSignalTab /> : null}
        {activeTab === "research" ? <SignalResearchTab /> : null}
        {activeTab === "performance" ? <SignalPerformanceTab /> : null}
      </div>
    </div>
  );
}

export default DrctStockSignalsPage;
