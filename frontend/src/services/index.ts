import { advisoryPackageApiRepository } from "@/services/api/advisoryPackageApiRepository";
import { analysisIndicatorApiRepository } from "@/services/api/analysisIndicatorApiRepository";
import { architectureApiRepository } from "@/services/api/architectureApiRepository";
import { backtestApiRepository } from "@/services/api/backtestApiRepository";
import { classificationRuleApiRepository } from "@/services/api/classificationRuleApiRepository";
import { collectionRunApiRepository } from "@/services/api/collectionRunApiRepository";
import { disclosureApiRepository } from "@/services/api/disclosureApiRepository";
import { economicBriefingApiRepository } from "@/services/api/economicBriefingApiRepository";
import { newsApiRepository } from "@/services/api/newsApiRepository";
import { patternResearchApiRepository } from "@/services/api/patternResearchApiRepository";
import { telegramApiRepository } from "@/services/api/telegramApiRepository";
import { marketCalendarApiRepository } from "@/services/api/marketCalendarApiRepository";
import { dashboardApiRepository } from "@/services/api/dashboardApiRepository";
import { marketIndexApiRepository } from "@/services/api/marketIndexApiRepository";
import { marketDataApiRepository } from "@/services/api/marketDataApiRepository";
import { marketIndicatorApiRepository } from "@/services/api/marketIndicatorApiRepository";
import { marketSignalApiRepository } from "@/services/api/marketSignalApiRepository";
import { marketThemeApiRepository } from "@/services/api/marketThemeApiRepository";
import { marketTrendApiRepository } from "@/services/api/marketTrendApiRepository";
import { gptPromptTemplateApiRepository } from "@/services/api/gptPromptTemplateApiRepository";
import { kmsApiRepository } from "@/services/api/kmsApiRepository";
import { imageApiRepository } from "@/services/api/imageApiRepository";
import { schemaCommentApiRepository } from "@/services/api/schemaCommentApiRepository";
import { stockApiRepository } from "@/services/api/stockApiRepository";
import { usStockApiRepository } from "@/services/api/usStockApiRepository";
import { usMarketThemeApiRepository } from "@/services/api/usMarketThemeApiRepository";
import { stockPriceApiRepository } from "@/services/api/stockPriceApiRepository";
import { stockTrackingApiRepository } from "@/services/api/stockTrackingApiRepository";
import { tradeJournalApiRepository } from "@/services/api/tradeJournalApiRepository";
import { tradeReviewApiRepository } from "@/services/api/tradeReviewApiRepository";
import { tradeTrainingApiRepository } from "@/services/api/tradeTrainingApiRepository";
import { chartMarkerApiRepository } from "@/services/api/chartMarkerApiRepository";
import { watchlistApiRepository } from "@/services/api/watchlistApiRepository";
import { watchlistEvaluationApiRepository } from "@/services/api/watchlistEvaluationApiRepository";
import { advisoryPackageMockRepository } from "@/services/mock/advisoryPackageMockRepository";
import { classificationRuleMockRepository } from "@/services/mock/classificationRuleMockRepository";
import { collectionRunMockRepository } from "@/services/mock/collectionRunMockRepository";
import { disclosureMockRepository } from "@/services/mock/disclosureMockRepository";
import { newsMockRepository } from "@/services/mock/newsMockRepository";
import { marketThemeMockRepository } from "@/services/mock/marketThemeMockRepository";
import { marketCalendarMockRepository } from "@/services/mock/marketCalendarMockRepository";
import { marketIndexMockRepository } from "@/services/mock/marketIndexMockRepository";
import { marketIndicatorMockRepository } from "@/services/mock/marketIndicatorMockRepository";
import { gptPromptTemplateMockRepository } from "@/services/mock/gptPromptTemplateMockRepository";
import { schemaCommentMockRepository } from "@/services/mock/schemaCommentMockRepository";
import { stockMockRepository } from "@/services/mock/stockMockRepository";
import { stockPriceMockRepository } from "@/services/mock/stockPriceMockRepository";
import { stockTrackingMockRepository } from "@/services/mock/stockTrackingMockRepository";
import { watchlistMockRepository } from "@/services/mock/watchlistMockRepository";
import { watchlistEvaluationMockRepository } from "@/services/mock/watchlistEvaluationMockRepository";
import { appConfig } from "@/services/config/appConfig";

const useMock = appConfig.dataSource !== "api";

export const repositories = {
  dashboard: dashboardApiRepository,
  analysisIndicators: analysisIndicatorApiRepository,
  architecture: architectureApiRepository,
  backtest: backtestApiRepository,
  stocks: useMock ? stockMockRepository : stockApiRepository,
  usStocks: usStockApiRepository,
  usMarketThemes: usMarketThemeApiRepository,
  stockPrices: useMock ? stockPriceMockRepository : stockPriceApiRepository,
  stockTracking: useMock ? stockTrackingMockRepository : stockTrackingApiRepository,
  watchlist: useMock ? watchlistMockRepository : watchlistApiRepository,
  watchlistEvaluation: useMock ? watchlistEvaluationMockRepository : watchlistEvaluationApiRepository,
  schemaComments: useMock ? schemaCommentMockRepository : schemaCommentApiRepository,
  news: useMock ? newsMockRepository : newsApiRepository,
  marketThemes: useMock ? marketThemeMockRepository : marketThemeApiRepository,
  marketCalendar: useMock ? marketCalendarMockRepository : marketCalendarApiRepository,
  marketIndexes: useMock ? marketIndexMockRepository : marketIndexApiRepository,
  marketData: marketDataApiRepository,
  marketIndicators: useMock ? marketIndicatorMockRepository : marketIndicatorApiRepository,
  marketSignals: marketSignalApiRepository,
  marketTrends: marketTrendApiRepository,
  kms: kmsApiRepository,
  images: imageApiRepository,
  disclosures: useMock ? disclosureMockRepository : disclosureApiRepository,
  economicBriefing: economicBriefingApiRepository,
  telegram: telegramApiRepository,
  advisoryPackages: useMock ? advisoryPackageMockRepository : advisoryPackageApiRepository,
  collectionRuns: useMock ? collectionRunMockRepository : collectionRunApiRepository,
  classificationRules: useMock ? classificationRuleMockRepository : classificationRuleApiRepository,
  gptPromptTemplates: useMock ? gptPromptTemplateMockRepository : gptPromptTemplateApiRepository,
  tradeJournals: tradeJournalApiRepository,
  tradeReviews: tradeReviewApiRepository,
  tradeTraining: tradeTrainingApiRepository,
  chartMarkers: chartMarkerApiRepository,
  patternResearch: patternResearchApiRepository,
};

export const dataSourceLabel = useMock ? "mock" : "api";

