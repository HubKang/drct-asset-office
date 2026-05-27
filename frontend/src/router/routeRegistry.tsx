import AdvisoryPackagePage from "@/pages/AdvisoryPackagePage";
import ClassificationRulesPage from "@/pages/ClassificationRulesPage";
import CollectionRunsPage from "@/pages/CollectionRunsPage";
import DashboardPage from "@/pages/DashboardPage";
import DisclosuresPage from "@/pages/DisclosuresPage";
import EconomicBriefingPage from "@/pages/EconomicBriefingPage";
import GptPromptSettingsPage from "@/pages/GptPromptSettingsPage";
import TelegramBriefingPage from "@/pages/TelegramBriefingPage";
import TradeCalendarPage from "@/pages/TradeCalendarPage";
import TradeMethodsPage from "@/pages/TradeMethodsPage";
import TradeJournalsPage from "@/pages/TradeJournalsPage";
import MarketThemesPage from "@/pages/MarketThemesPage";
import MarketTrendsPage from "@/pages/MarketTrendsPage";
import NewsPage from "@/pages/NewsPage";
import SchemaCommentsPage from "@/pages/SchemaCommentsPage";
import StockPricesPage from "@/pages/StockPricesPage";
import StocksPage from "@/pages/StocksPage";
import WatchlistPage from "@/pages/WatchlistPage";
import PageHeader from "@/components/common/PageHeader";

function ComingSoonPage({ title }: { title: string }) {
  return (
    <div className="space-y-4">
      <PageHeader title={title} description="해당 화면은 준비 중입니다." />
    </div>
  );
}

export type RouteItem = {
  routeKey: string;
  path: string;
  title: string;
  description: string;
  component: JSX.Element;
};

export const routeRegistry: RouteItem[] = [
  { routeKey: "dashboard", path: "/dashboard", title: "대시보드", description: "투자 리서치 현황 요약", component: <DashboardPage /> },
  { routeKey: "advisory-packages", path: "/advisory-packages", title: "GPT 자문 패키지", description: "최종 투자 자문용 패키지 생성", component: <AdvisoryPackagePage /> },
  { routeKey: "stocks", path: "/stocks", title: "종목 관리", description: "종목 마스터 관리", component: <StocksPage /> },
  { routeKey: "watchlist", path: "/watchlist", title: "관심종목 Data수집", description: "분석 우선 종목 Pool 관리", component: <WatchlistPage /> },
  { routeKey: "stock-prices", path: "/stock-prices", title: "관심종목 Data분석", description: "일봉/이동평균 데이터 검증", component: <StockPricesPage /> },
  { routeKey: "schema-comments", path: "/schema-comments", title: "스키마 코멘트", description: "테이블/컬럼 코멘트 사전", component: <SchemaCommentsPage /> },
  { routeKey: "news", path: "/news", title: "뉴스 관리", description: "뉴스 수집/요약 결과 조회", component: <NewsPage /> },
  { routeKey: "disclosures", path: "/disclosures", title: "공시 관리", description: "DART 공시 수집/요약 결과 조회", component: <DisclosuresPage /> },
  { routeKey: "collection-runs", path: "/collection-runs", title: "수집 이력", description: "수집 실행 로그 확인", component: <CollectionRunsPage /> },
  { routeKey: "classification-rules", path: "/classification-rules", title: "분류 규칙 관리", description: "뉴스/공시 자동 분류 규칙 관리", component: <ClassificationRulesPage /> },
  { routeKey: "market-themes", path: "/market-themes", title: "시장 테마 관리", description: "테마 등록/종목 매핑 관리", component: <MarketThemesPage /> },
  { routeKey: "market-trends", path: "/market-trends", title: "시장 트렌드 분석", description: "수급 이벤트 감지/테마 흐름 집계", component: <MarketTrendsPage /> },
  { routeKey: "economic-briefing", path: "/economic-briefing", title: "경제 브리핑", description: "경제 영상 메타데이터/요약 관리", component: <EconomicBriefingPage /> },
  { routeKey: "telegram-briefing", path: "/telegram-briefing", title: "텔레그램 브리핑", description: "텔레그램 채널 수집/요약 관리", component: <TelegramBriefingPage /> },
  { routeKey: "trade-methods", path: "/trade-methods", title: "매매기법", description: "매매기법 등록/수정/비활성화 관리", component: <TradeMethodsPage /> },
  { routeKey: "trade-journals", path: "/trade-journals", title: "매매일지", description: "매매일지 등록/조회", component: <TradeJournalsPage /> },
  { routeKey: "trade-calendar", path: "/trade-calendar", title: "매매달력", description: "월간 매매달력/통계", component: <TradeCalendarPage /> },
  { routeKey: "settings", path: "/settings", title: "설정", description: "GPT 분석 프롬프트 설정 관리", component: <GptPromptSettingsPage /> },
];

export const routeRegistryMap = Object.fromEntries(routeRegistry.map((route) => [route.routeKey, route]));


