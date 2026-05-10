import { Activity, BookOpenText, Briefcase, Database, FileText, Newspaper } from "lucide-react";
import PageHeader from "@/components/common/PageHeader";
import SectionCard from "@/components/common/SectionCard";
import StatCard from "@/components/common/StatCard";
import StatusBadge from "@/components/common/StatusBadge";
import { useEffect, useMemo, useState } from "react";
import { dataSourceLabel, repositories } from "@/services";

function DashboardPage() {
  const [stockCount, setStockCount] = useState(0);
  const [watchlistCount, setWatchlistCount] = useState(0);
  const [schemaCount, setSchemaCount] = useState(0);
  const [health, setHealth] = useState("확인중");

  useEffect(() => {
    const run = async () => {
      try {
        const [stocks, watchlist, comments] = await Promise.all([
          repositories.stocks.list(),
          repositories.watchlist.list(),
          repositories.schemaComments.list(),
        ]);
        setStockCount(stocks.length);
        setWatchlistCount(watchlist.length);
        setSchemaCount(comments.length);
        setHealth("정상");
      } catch {
        setHealth("연결 실패");
      }
    };
    run();
  }, []);

  const stats = useMemo(
    () => [
      { title: "API 연결 상태", value: health, icon: Activity },
      { title: "종목 수", value: `${stockCount}`, icon: Briefcase },
      { title: "관심종목 수", value: `${watchlistCount}`, icon: BookOpenText },
      { title: "Schema Comment 수", value: `${schemaCount}`, icon: Database },
    ],
    [health, schemaCount, stockCount, watchlistCount],
  );

  return (
    <div className="space-y-4">
      <PageHeader
        theme="dark"
        title="대시보드"
        description="오늘의 투자 판단 근거를 정리하고, 수집·분석 흐름 상태를 확인합니다."
        action={<span className="keyword-chip">AI 분석 콘솔</span>}
      />

      <SectionCard theme="dark">
        <div className="hero-panel">
          <p className="text-xs uppercase tracking-wider text-white/70">DrCT에셋</p>
          <h3 className="mt-2 text-2xl font-semibold">AI 기반 투자 근거 운영실</h3>
          <p className="mt-2 text-sm text-white/72">자동 판단이 아닌, 뉴스·공시·데이터 근거를 정리해 최종 검토를 돕습니다.</p>
          <div className="mt-4 flex flex-wrap gap-2">
            <StatusBadge label={`데이터 소스: ${dataSourceLabel.toUpperCase()}`} tone="blue" />
            <StatusBadge label={`종목 ${stockCount}건`} tone="emerald" />
            <StatusBadge label={`관심종목 ${watchlistCount}건`} tone="amber" />
          </div>
        </div>
      </SectionCard>

      <div className="stats-grid">
        {stats.map((stat) => (
          <StatCard key={stat.title} title={stat.title} value={stat.value} icon={stat.icon} theme="dark" />
        ))}
      </div>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <StatCard title="뉴스/공시 수집" value="준비중" icon={Newspaper} description="수집 파이프라인 연동 예정" badge="Roadmap" theme="dark" />
        <StatCard title="리포트/GPT 자문" value="준비중" icon={FileText} description="리서치 자동화 연동 예정" badge="Roadmap" theme="dark" />
      </div>
    </div>
  );
}

export default DashboardPage;
