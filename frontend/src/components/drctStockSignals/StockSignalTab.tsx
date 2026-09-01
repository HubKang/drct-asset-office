import { ListFilter, Search } from "lucide-react";

import SignalEmptyState from "@/components/drctStockSignals/SignalEmptyState";
import SignalSummaryCards from "@/components/drctStockSignals/SignalSummaryCards";

const SUMMARY_ITEMS = [
  { label: "분석 대상", description: "국내 테마 연결 종목" },
  { label: "검색식 포착", description: "DrCT 검색식 조건 만족" },
  { label: "DrCT 시그널", description: "성공패턴 필터 통과" },
  { label: "신규 시그널", description: "오늘 신규 포착" },
];

function StockSignalTab() {
  return (
    <div className="drct-signal-tab-content">
      <SignalSummaryCards items={SUMMARY_ITEMS} />

      <section className="drct-signal-filter-shell" aria-labelledby="signal-filter-title">
        <div>
          <span className="drct-signal-section-icon" aria-hidden="true"><ListFilter size={17} /></span>
          <div>
            <h2 id="signal-filter-title">시그널 탐색</h2>
            <p>검색식, 테마, 상태와 종목명 필터가 이 영역에 연결됩니다.</p>
          </div>
        </div>
        <span className="drct-signal-ready-badge">데이터 연결 후 제공</span>
      </section>

      <section className="drct-signal-panel drct-signal-list-panel" aria-labelledby="signal-list-title">
        <header className="drct-signal-panel-header">
          <div>
            <h2 id="signal-list-title">종목 시그널</h2>
            <p>종목 · 테마 · 시그널 · DrCT 평가 · 현재가 · 포착 · 상태</p>
          </div>
          <span>목록 준비 중</span>
        </header>
        <SignalEmptyState
          icon={Search}
          title="아직 생성된 DrCT 종목 시그널이 없습니다."
          description="검색식 엔진과 성공패턴 모델이 연결되면 이곳에서 종목 시그널을 확인할 수 있습니다."
        />
      </section>
    </div>
  );
}

export default StockSignalTab;
