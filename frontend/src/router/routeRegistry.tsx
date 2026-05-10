import AdvisoryPackagePage from "@/pages/AdvisoryPackagePage";
import ClassificationRulesPage from "@/pages/ClassificationRulesPage";
import CollectionRunsPage from "@/pages/CollectionRunsPage";
import DashboardPage from "@/pages/DashboardPage";
import DisclosuresPage from "@/pages/DisclosuresPage";
import NewsPage from "@/pages/NewsPage";
import SchemaCommentsPage from "@/pages/SchemaCommentsPage";
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
  { routeKey: "dashboard", path: "/dashboard", title: "대시보드", description: "투자운영 현황 요약", component: <DashboardPage /> },
  { routeKey: "stocks", path: "/stocks", title: "종목 관리", description: "종목 등록/수정/비활성화", component: <StocksPage /> },
  { routeKey: "watchlist", path: "/watchlist", title: "관심종목 관리", description: "관심종목 등록/수정/삭제", component: <WatchlistPage /> },
  {
    routeKey: "advisory-packages",
    path: "/advisory-packages",
    title: "GPT 자문 패키지",
    description: "GPT Plus 검토용 Markdown 패키지를 생성합니다.",
    component: <AdvisoryPackagePage />,
  },
  { routeKey: "schema-comments", path: "/schema-comments", title: "스키마 코멘트", description: "테이블/컬럼 한글 설명 데이터 사전", component: <SchemaCommentsPage /> },
  { routeKey: "news", path: "/news", title: "뉴스 관리", description: "수집된 종목 뉴스를 조회하고 검토합니다.", component: <NewsPage /> },
  { routeKey: "disclosures", path: "/disclosures", title: "공시 관리", description: "DART 공시 수집 결과를 조회하고 검토합니다.", component: <DisclosuresPage /> },
  { routeKey: "collection-runs", path: "/collection-runs", title: "수집 이력", description: "데이터 수집 실행 이력을 확인합니다.", component: <CollectionRunsPage /> },
  { routeKey: "classification-rules", path: "/classification-rules", title: "분류 규칙 관리", description: "뉴스와 공시의 태그·중요도·감성/리스크 분류 기준을 관리합니다.", component: <ClassificationRulesPage /> },
  { routeKey: "settings", path: "/settings", title: "설정", description: "시스템 설정 준비중", component: <div className="rounded-xl border border-slate-200 bg-white p-6">설정 화면 준비중입니다.</div> },
];

export const routeRegistryMap = Object.fromEntries(routeRegistry.map((route) => [route.routeKey, route]));
