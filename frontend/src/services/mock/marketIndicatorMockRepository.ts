import type { ExternalProviderStatusListResponse, MarketIndicatorListResponse, MarketIndicatorProviderMappingListResponse, MarketIndicatorValueResponse } from "@/types/marketIndicator";

const providerStatuses: ExternalProviderStatusListResponse = {
  items: [
    { provider: "KIWOOM_REST", display_name: "?? REST API", configured: true, masked_key: "mock********key", status: "CONFIGURED", message: "mock configured", last_checked_at: "mock" },
    { provider: "KRX_OPEN_API", display_name: "KRX Open API", configured: false, masked_key: null, status: "MISSING_KEY", message: "mock missing", last_checked_at: "mock" },
    { provider: "DATA_GO_KR", display_name: "???????", configured: false, masked_key: null, status: "MISSING_KEY", message: "mock missing", last_checked_at: "mock" },
    { provider: "BOK_ECOS", display_name: "BOK ECOS", configured: false, masked_key: null, status: "MISSING_KEY", message: "mock missing", last_checked_at: "mock" },
    { provider: "KOSIS", display_name: "KOSIS", configured: false, masked_key: null, status: "MISSING_KEY", message: "mock missing", last_checked_at: "mock" },
  ],
};

export const marketIndicatorMockRepository = {
  async list(): Promise<MarketIndicatorListResponse> {
    return { items: [], category_counts: {} };
  },
  async get(indicatorCode: string) {
    return { indicator_code: indicatorCode, indicator_name: indicatorCode, category: "FX", data_frequency: "DAILY", chart_type: "LINE", display_order: 0, priority_rank: 0, is_active: true, collection_status: "WAITING" };
  },
  async values(indicatorCode: string): Promise<MarketIndicatorValueResponse> {
    return { indicator_code: indicatorCode, items: [] };
  },
  async providerMappings(): Promise<MarketIndicatorProviderMappingListResponse> {
    return { items: [] };
  },
  async providerStatuses(): Promise<ExternalProviderStatusListResponse> {
    return providerStatuses;
  },
};
