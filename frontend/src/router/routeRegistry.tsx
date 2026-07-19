import AdvisoryPackagePage from "@/pages/AdvisoryPackagePage";
import AnalysisIndicatorSettingsPage from "@/pages/AnalysisIndicatorSettingsPage";
import BacktestPage from "@/pages/BacktestPage";
import ClassificationRulesPage from "@/pages/ClassificationRulesPage";
import CollectionRunsPage from "@/pages/CollectionRunsPage";
import DashboardPage from "@/pages/DashboardPage";
import DrctArchitecturePage from "@/pages/DrctArchitecturePage";
import DisclosuresPage from "@/pages/DisclosuresPage";
import EconomicBriefingPage from "@/pages/EconomicBriefingPage";
import GptPromptSettingsPage from "@/pages/GptPromptSettingsPage";
import KmsHomePage from "@/pages/KmsHomePage";
import KmsPostDetailPage from "@/pages/KmsPostDetailPage";
import KmsPostsPage from "@/pages/KmsPostsPage";
import KmsSettingsPage from "@/pages/KmsSettingsPage";
import TelegramBriefingPage from "@/pages/TelegramBriefingPage";
import TradeCalendarPage from "@/pages/TradeCalendarPage";
import TradeMethodsPage from "@/pages/TradeMethodsPage";
import TradeJournalsPage from "@/pages/TradeJournalsPage";
import TradeReviewsPage from "@/pages/TradeReviewsPage";
import TradeTrainingCalendarPage from "@/pages/TradeTrainingCalendarPage";
import TradeTrainingPage from "@/pages/TradeTrainingPage";
import MarketCalendarPage from "@/pages/MarketCalendarPage";
import MarketIndexesPage from "@/pages/MarketIndexesPage";
import MarketSignalsPage from "@/pages/MarketSignalsPage";
import MarketThemesPage from "@/pages/MarketThemesPage";
import MarketTrendsPage from "@/pages/MarketTrendsPage";
import NewsPage from "@/pages/NewsPage";
import SchemaCommentsPage from "@/pages/SchemaCommentsPage";
import StockPricesPage from "@/pages/StockPricesPage";
import StockTrackingPage from "@/pages/StockTrackingPage";
import StocksPage from "@/pages/StocksPage";
import WatchlistPage from "@/pages/WatchlistPage";
import WatchlistSijeSuchaJaePage from "@/pages/WatchlistSijeSuchaJaePage";
import PageHeader from "@/components/common/PageHeader";
import PatternResearchPage from "@/pages/PatternResearchPage";

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
  { routeKey: "market-calendar", path: "/market-calendar", title: "증시 캘린더", description: "테마별 뉴스와 일정을 월간 캘린더로 관리", component: <MarketCalendarPage /> },
  { routeKey: "advisory-packages", path: "/advisory-packages", title: "GPT 자문 패키지", description: "최종 투자 자문용 패키지 생성", component: <AdvisoryPackagePage /> },
  { routeKey: "stocks", path: "/stocks", title: "종목 관리", description: "종목 마스터 관리", component: <StocksPage /> },
  { routeKey: "watchlist", path: "/watchlist", title: "관심 종목", description: "분석 우선 종목 Pool 관리", component: <WatchlistPage /> },
  { routeKey: "watchlist-sije-sucha-jae", path: "/watchlist/sije-sucha-jae", title: "관심 종목 시재수차재", description: "관심종목 평가 전용 화면", component: <WatchlistSijeSuchaJaePage /> },
  { routeKey: "stock-prices", path: "/stock-prices", title: "관심 종목 분석", description: "일봉/이동평균 데이터 검증", component: <StockPricesPage /> },
  { routeKey: "stock-tracking", path: "/stock-tracking", title: "종목 트래킹", description: "수급 이벤트 후보 종목을 그룹별로 추적하고 복기", component: <StockTrackingPage /> },
  { routeKey: "schema-comments", path: "/schema-comments", title: "DrCT테이블정보", description: "DrCT에셋 데이터베이스의 테이블/컬럼 구조 조회", component: <SchemaCommentsPage /> },
  { routeKey: "news", path: "/news", title: "뉴스 관리", description: "뉴스 수집/요약 결과 조회", component: <NewsPage /> },
  { routeKey: "disclosures", path: "/disclosures", title: "공시 관리", description: "DART 공시 수집/요약 결과 조회", component: <DisclosuresPage /> },
  { routeKey: "collection-runs", path: "/collection-runs", title: "수집 이력", description: "수집 실행 로그 확인", component: <CollectionRunsPage /> },
  { routeKey: "classification-rules", path: "/classification-rules", title: "분류 규칙 관리", description: "뉴스/공시 자동 분류 규칙 관리", component: <ClassificationRulesPage /> },
  { routeKey: "market-themes", path: "/market-themes", title: "시장 테마 관리", description: "테마 등록/종목 매핑 관리", component: <MarketThemesPage /> },
  { routeKey: "market-trends", path: "/market-trends", title: "시장 수급 테마(종목)", description: "수급 이벤트 감지/테마·종목 흐름 집계", component: <MarketTrendsPage /> },
  { routeKey: "market-indicators", path: "/market-indicators", title: "시장 지표 관리", description: "코스피, 코스닥, 업종지수, 금 현물 등 주요 시장지표를 수집하고 시장 흐름을 비교합니다.", component: <MarketIndexesPage /> },
  { routeKey: "market-indexes", path: "/market-indexes", title: "시장 지표 관리", description: "코스피, 코스닥, 업종지수, 금 현물 등 주요 시장지표를 수집하고 시장 흐름을 비교합니다.", component: <MarketIndexesPage /> },
  { routeKey: "market-indicator-signals", path: "/market-indexes/signals", title: "지표 신호 관리", description: "시장 지표의 변화 방향과 전환점 신호를 관리합니다.", component: <MarketSignalsPage /> },
  { routeKey: "market-economic-flows", path: "/market-indexes/economic-flows", title: "경제 흐름 관리", description: "경제 흐름 룰 관리는 후속 단계에서 구현합니다.", component: <ComingSoonPage title="경제 흐름 관리" /> },
  { routeKey: "market-scenario-diagnosis", path: "/market-indexes/scenario-diagnosis", title: "경제 시나리오 진단", description: "경제 시나리오 진단은 후속 단계에서 구현합니다.", component: <ComingSoonPage title="경제 시나리오 진단" /> },
  { routeKey: "economic-briefing", path: "/economic-briefing", title: "경제 브리핑", description: "경제 영상 메타데이터/요약 관리", component: <EconomicBriefingPage /> },
  { routeKey: "telegram-briefing", path: "/telegram-briefing", title: "텔레그램 브리핑", description: "텔레그램 채널 수집/요약 관리", component: <TelegramBriefingPage /> },
  { routeKey: "kms-home", path: "/kms", title: "KMS 홈", description: "투자 지식 대시보드", component: <KmsHomePage /> },
  { routeKey: "kms-posts", path: "/kms/posts", title: "지식 보드", description: "KMS 지식 등록/조회", component: <KmsPostsPage /> },
  { routeKey: "kms-post-detail", path: "/kms/posts/:postId", title: "지식글 상세", description: "KMS 지식글 상세/수정", component: <KmsPostDetailPage /> },
  { routeKey: "kms-settings", path: "/kms/settings", title: "KMS 설정", description: "KMS 카테고리 관리", component: <KmsSettingsPage /> },
  { routeKey: "trade-methods", path: "/trade-methods", title: "매매기법", description: "매매기법 등록/수정/비활성화 관리", component: <TradeMethodsPage /> },
  { routeKey: "trade-journals", path: "/trade-journals", title: "매매일지", description: "매매일지 등록/조회", component: <TradeJournalsPage /> },
  { routeKey: "trade-calendar", path: "/trade-calendar", title: "매매일지 캘린더", description: "매매일지의 매수·매도 기록을 달력으로 확인", component: <TradeCalendarPage /> },
  { routeKey: "trade-reviews", path: "/trade-reviews", title: "매매일지 복기", description: "매매일지 데이터를 기반으로 원칙 준수와 반복 실수를 점검", component: <TradeReviewsPage /> },
  { routeKey: "trade-training", path: "/trading/training", title: "매매훈련", description: "과거 일봉을 하루씩 넘기며 매수·매도 판단을 훈련", component: <TradeTrainingPage /> },
  { routeKey: "trade-training-calendar", path: "/trade-training-calendar", title: "매매훈련 캘린더", description: "일별 매매훈련 기록과 복기 상태, 훈련점수 추이", component: <TradeTrainingCalendarPage /> },
  { routeKey: "backtest", path: "/trading/backtest", title: "매매기준 백테스트", description: "계산 가능한 기준을 과거 일봉에 적용해 성과와 손실 구조를 검증", component: <BacktestPage /> },
  { routeKey: "pattern-research", path: "/trading/pattern-research", title: "매매패턴 AI연구", description: "자연어 목표를 성공/실패 샘플과 GPT 연구 패키지로 변환", component: <PatternResearchPage /> },
  { routeKey: "settings", path: "/settings", title: "설정", description: "GPT 분석 프롬프트 설정 관리", component: <GptPromptSettingsPage /> },
  { routeKey: "analysis-indicator-settings", path: "/settings/analysis-indicators", title: "매매연구 지표 설정", description: "매매목표 해석용 지표·별칭·조건 템플릿 관리", component: <AnalysisIndicatorSettingsPage /> },
  { routeKey: "drct-architecture", path: "/drct-architecture", title: "DrCT아키텍처", description: "폴더 구조/정리 정책 점검", component: <DrctArchitecturePage /> },
];

export const routeRegistryMap = Object.fromEntries(routeRegistry.map((route) => [route.routeKey, route]));
