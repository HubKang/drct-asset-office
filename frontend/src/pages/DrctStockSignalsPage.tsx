import { useState } from "react";

import PageHeader from "@/components/common/PageHeader";
import SignalPerformanceTab from "@/components/drctStockSignals/SignalPerformanceTab";
import SignalResearchHub from "@/components/drctStockSignals/SignalResearchHub";
import StockSignalTab from "@/components/drctStockSignals/StockSignalTab";

type SignalTab = "signals" | "research" | "performance";

const TABS: Array<{ id: SignalTab; label: string }> = [
  { id: "signals", label: "종목 시그널" },
  { id: "research", label: "차트마커 학습 & 검색식 관리" },
  { id: "performance", label: "시그널 성과" },
];

function DrctStockSignalsPage() {
  const [activeTab, setActiveTab] = useState<SignalTab>("signals");

  return (
    <div className="drct-stock-signals-page">
      <PageHeader
        title="DrCT 종목 시그널"
        description="국내 테마 연결 종목에서 과거 성공 패턴과 유사한 종목을 찾아 관찰 후보로 제시합니다."
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
        {activeTab === "research" ? <SignalResearchHub /> : null}
        {activeTab === "performance" ? <SignalPerformanceTab /> : null}
      </div>
    </div>
  );
}

export default DrctStockSignalsPage;
