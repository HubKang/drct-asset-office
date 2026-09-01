import { BarChart3, TableProperties } from "lucide-react";

import SignalEmptyState from "@/components/drctStockSignals/SignalEmptyState";
import SignalSummaryCards from "@/components/drctStockSignals/SignalSummaryCards";

const SUMMARY_ITEMS = [
  { label: "전체 시그널", description: "누적 포착 결과" },
  { label: "평가 완료", description: "성과 평가 완료" },
  { label: "성공", description: "성공 기준 충족" },
  { label: "성공률", description: "평가 완료 대비" },
];

function SignalPerformanceTab() {
  return (
    <div className="drct-signal-tab-content">
      <SignalSummaryCards items={SUMMARY_ITEMS} />

      <section className="drct-signal-panel" aria-labelledby="performance-title">
        <header className="drct-signal-panel-header">
          <div>
            <h2 id="performance-title">검색식 대비 DrCT 필터 성과</h2>
            <p>검색식 포착 결과와 DrCT 성공패턴 필터 적용 결과를 비교하여 알고리즘의 개선 효과를 검증합니다.</p>
          </div>
          <span>D+5 · D+10 · D+20 · MFE · MAE</span>
        </header>
        <SignalEmptyState
          icon={BarChart3}
          title="비교할 시그널 성과가 아직 없습니다."
          description="검색식 엔진과 성과 평가 데이터가 연결되면 필터 적용 전후의 결과를 비교할 수 있습니다."
        />
      </section>

      <section className="drct-signal-panel drct-signal-performance-table" aria-labelledby="performance-table-title">
        <header className="drct-signal-panel-header">
          <div>
            <h2 id="performance-table-title">검색식별 성과</h2>
            <p>검색식별 포착 건수와 DrCT 필터 성과가 이 영역에 표시됩니다.</p>
          </div>
          <TableProperties size={19} aria-hidden="true" />
        </header>
        <div className="drct-signal-table-placeholder" aria-hidden="true">
          <span>검색식</span><span>포착</span><span>필터 후</span><span>성공률</span><span>D+20</span>
        </div>
      </section>
    </div>
  );
}

export default SignalPerformanceTab;
