import { advisoryPackageApiRepository } from "@/services/api/advisoryPackageApiRepository";
import { architectureApiRepository } from "@/services/api/architectureApiRepository";
import { classificationRuleApiRepository } from "@/services/api/classificationRuleApiRepository";
import { collectionRunApiRepository } from "@/services/api/collectionRunApiRepository";
import { disclosureApiRepository } from "@/services/api/disclosureApiRepository";
import { economicBriefingApiRepository } from "@/services/api/economicBriefingApiRepository";
import { newsApiRepository } from "@/services/api/newsApiRepository";
import { telegramApiRepository } from "@/services/api/telegramApiRepository";
import { marketThemeApiRepository } from "@/services/api/marketThemeApiRepository";
import { marketTrendApiRepository } from "@/services/api/marketTrendApiRepository";
import { gptPromptTemplateApiRepository } from "@/services/api/gptPromptTemplateApiRepository";
import { schemaCommentApiRepository } from "@/services/api/schemaCommentApiRepository";
import { stockApiRepository } from "@/services/api/stockApiRepository";
import { stockPriceApiRepository } from "@/services/api/stockPriceApiRepository";
import { tradeJournalApiRepository } from "@/services/api/tradeJournalApiRepository";
import { watchlistApiRepository } from "@/services/api/watchlistApiRepository";
import { advisoryPackageMockRepository } from "@/services/mock/advisoryPackageMockRepository";
import { classificationRuleMockRepository } from "@/services/mock/classificationRuleMockRepository";
import { collectionRunMockRepository } from "@/services/mock/collectionRunMockRepository";
import { disclosureMockRepository } from "@/services/mock/disclosureMockRepository";
import { newsMockRepository } from "@/services/mock/newsMockRepository";
import { marketThemeMockRepository } from "@/services/mock/marketThemeMockRepository";
import { gptPromptTemplateMockRepository } from "@/services/mock/gptPromptTemplateMockRepository";
import { schemaCommentMockRepository } from "@/services/mock/schemaCommentMockRepository";
import { stockMockRepository } from "@/services/mock/stockMockRepository";
import { stockPriceMockRepository } from "@/services/mock/stockPriceMockRepository";
import { watchlistMockRepository } from "@/services/mock/watchlistMockRepository";
import { appConfig } from "@/services/config/appConfig";

const useMock = appConfig.dataSource !== "api";

export const repositories = {
  architecture: architectureApiRepository,
  stocks: useMock ? stockMockRepository : stockApiRepository,
  stockPrices: useMock ? stockPriceMockRepository : stockPriceApiRepository,
  watchlist: useMock ? watchlistMockRepository : watchlistApiRepository,
  schemaComments: useMock ? schemaCommentMockRepository : schemaCommentApiRepository,
  news: useMock ? newsMockRepository : newsApiRepository,
  marketThemes: useMock ? marketThemeMockRepository : marketThemeApiRepository,
  marketTrends: marketTrendApiRepository,
  disclosures: useMock ? disclosureMockRepository : disclosureApiRepository,
  economicBriefing: economicBriefingApiRepository,
  telegram: telegramApiRepository,
  advisoryPackages: useMock ? advisoryPackageMockRepository : advisoryPackageApiRepository,
  collectionRuns: useMock ? collectionRunMockRepository : collectionRunApiRepository,
  classificationRules: useMock ? classificationRuleMockRepository : classificationRuleApiRepository,
  gptPromptTemplates: useMock ? gptPromptTemplateMockRepository : gptPromptTemplateApiRepository,
  tradeJournals: tradeJournalApiRepository,
};

export const dataSourceLabel = useMock ? "mock" : "api";
