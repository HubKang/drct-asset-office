import type { EcosDiscoverCandidatesRequest, EcosDiscoverCandidatesResponse, EcosDiscoverMappingCandidatesRequest, EcosDiscoverMappingCandidatesResponse, EcosMappingCandidateTestRequest, EcosItemListResponse, EcosTableListResponse, EcosTableSearchResponse, ExternalProviderStatusListResponse, MarketIndicatorCollectRequest, MarketIndicatorCollectResponse, MarketIndicatorListResponse, MarketIndicatorProviderMapping, MarketIndicatorProviderMappingListResponse, MarketIndicatorProviderMappingTestRequest, MarketIndicatorProviderMappingTestResponse, MarketIndicatorProviderMappingUpsertRequest, MarketIndicatorReadinessListResponse, MarketIndicatorValueResponse } from "@/types/marketIndicator";

const providerStatuses: ExternalProviderStatusListResponse = {
  items: [
    { provider: "KIWOOM_REST", display_name: "?? REST API", configured: true, masked_key: "mock********key", status: "CONFIGURED", message: "mock configured", last_checked_at: "mock" },
    { provider: "KRX_OPEN_API", display_name: "KRX Open API", configured: false, masked_key: null, status: "MISSING_KEY", message: "mock missing", last_checked_at: "mock" },
    { provider: "DATA_GO_KR", display_name: "???????", configured: false, masked_key: null, status: "MISSING_KEY", message: "mock missing", last_checked_at: "mock" },
    { provider: "BOK_ECOS", display_name: "BOK ECOS", configured: false, masked_key: null, status: "MISSING_KEY", message: "mock missing", last_checked_at: "mock" },
    { provider: "KOSIS", display_name: "KOSIS", configured: false, masked_key: null, status: "MISSING_KEY", message: "mock missing", last_checked_at: "mock" },
    { provider: "FRED", display_name: "FRED", configured: false, masked_key: null, status: "MISSING_KEY", message: "mock missing", last_checked_at: "mock" },
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
  async readiness(): Promise<MarketIndicatorReadinessListResponse> {
    return { items: [], summary_counts: {} };
  },
  async providerStatuses(): Promise<ExternalProviderStatusListResponse> {
    return providerStatuses;
  },
  async ecosTableList(): Promise<EcosTableListResponse> {
    return { status: "WAITING", message: "mock", total_count: 0, items: [] };
  },
  async ecosTableSearch(params: { keyword: string }): Promise<EcosTableSearchResponse> {
    return { keyword: params.keyword, status: "WAITING", message: "mock", searched_count: 0, items: [] };
  },
  async discoverCandidates(_payload: EcosDiscoverCandidatesRequest = {}): Promise<EcosDiscoverCandidatesResponse> {
    return { status: "WAITING", message: "mock", searched_count: 0, items: [] };
  },
  async discoverMappingCandidates(_payload: EcosDiscoverMappingCandidatesRequest = {}): Promise<EcosDiscoverMappingCandidatesResponse> {
    return { status: "WAITING", message: "mock", items: [] };
  },
  async ecosItemList(params: { stat_code: string }): Promise<EcosItemListResponse> {
    return { stat_code: params.stat_code, status: "WAITING", message: "mock", list_total_count: 0, items: [] };
  },
  async upsertProviderMapping(indicatorCode: string, payload: MarketIndicatorProviderMappingUpsertRequest): Promise<MarketIndicatorProviderMapping> {
    return { indicator_code: indicatorCode, provider: payload.provider || "BOK_ECOS", api_type: payload.api_type, api_id: payload.api_id, endpoint_url: payload.endpoint_url, provider_symbol: payload.provider_symbol, request_params_json: JSON.stringify(payload.request_params_json || {}), is_enabled: false, is_verified: false, last_test_status: "WAITING", last_test_message: "mock" };
  },
  async testProviderMapping(indicatorCode: string, _payload: MarketIndicatorProviderMappingTestRequest): Promise<MarketIndicatorProviderMappingTestResponse> {
    return { indicator_code: indicatorCode, provider: "BOK_ECOS", status: "WAITING", message: "mock", sample_count: 0, sample_rows: [] };
  },
  async testCandidate(indicatorCode: string, _payload: EcosMappingCandidateTestRequest): Promise<MarketIndicatorProviderMappingTestResponse> {
    return { indicator_code: indicatorCode, provider: "BOK_ECOS", status: "WAITING", message: "mock", sample_count: 0, sample_rows: [] };
  },
  async activateProviderMapping(indicatorCode: string): Promise<MarketIndicatorProviderMapping> {
    return { indicator_code: indicatorCode, provider: "BOK_ECOS", is_enabled: true, is_verified: true };
  },
  async collect(_payload: MarketIndicatorCollectRequest = {}): Promise<MarketIndicatorCollectResponse> {
    return { requested_count: 0, success_count: 0, waiting_count: 0, failed_count: 0, message: "mock", results: [] };
  },
};
