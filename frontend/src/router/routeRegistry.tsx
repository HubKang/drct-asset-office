import AdvisoryPackagePage from "@/pages/AdvisoryPackagePage";
import ClassificationRulesPage from "@/pages/ClassificationRulesPage";
import CollectionRunsPage from "@/pages/CollectionRunsPage";
import DashboardPage from "@/pages/DashboardPage";
import DisclosuresPage from "@/pages/DisclosuresPage";
import GptPromptSettingsPage from "@/pages/GptPromptSettingsPage";
import MarketThemesPage from "@/pages/MarketThemesPage";
import MarketTrendsPage from "@/pages/MarketTrendsPage";
import NewsPage from "@/pages/NewsPage";
import SchemaCommentsPage from "@/pages/SchemaCommentsPage";
import StockPricesPage from "@/pages/StockPricesPage";
import StocksPage from "@/pages/StocksPage";
import WatchlistPage from "@/pages/WatchlistPage";

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
  { routeKey: "watchlist", path: "/watchlist", title: "관심종목 Pool", description: "분석 우선 종목 Pool 관리", component: <WatchlistPage /> },
  { routeKey: "stock-prices", path: "/stock-prices", title: "가격·캔들 관리", description: "일봉/이동평균 데이터 검증", component: <StockPricesPage /> },
  { routeKey: "schema-comments", path: "/schema-comments", title: "스키마 코멘트", description: "테이블/컬럼 코멘트 사전", component: <SchemaCommentsPage /> },
  { routeKey: "news", path: "/news", title: "뉴스 관리", description: "뉴스 수집/요약 결과 조회", component: <NewsPage /> },
  { routeKey: "disclosures", path: "/disclosures", title: "공시 관리", description: "DART 공시 수집/요약 결과 조회", component: <DisclosuresPage /> },
  { routeKey: "collection-runs", path: "/collection-runs", title: "수집 이력", description: "수집 실행 로그 확인", component: <CollectionRunsPage /> },
  { routeKey: "classification-rules", path: "/classification-rules", title: "분류 규칙 관리", description: "뉴스/공시 자동 분류 규칙 관리", component: <ClassificationRulesPage /> },
  { routeKey: "market-themes", path: "/market-themes", title: "시장 테마 관리", description: "테마 등록/종목 매핑 관리", component: <MarketThemesPage /> },
  { routeKey: "market-trends", path: "/market-trends", title: "시장 트렌드 분석", description: "수급 이벤트 감지/테마 흐름 집계", component: <MarketTrendsPage /> },
  { routeKey: "settings", path: "/settings", title: "설정", description: "GPT 분석 프롬프트 설정 관리", component: <GptPromptSettingsPage /> },
];

export const routeRegistryMap = Object.fromEntries(routeRegistry.map((route) => [route.routeKey, route]));
