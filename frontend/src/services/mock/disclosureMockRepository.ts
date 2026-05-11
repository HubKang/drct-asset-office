import type { AiSummarizeResponse } from "@/types/analysis";
import type {
  Disclosure,
  DisclosureCollectRequest,
  DisclosureCollectResponse,
  DisclosureCollectSelectedResponse,
  DisclosureCollectSelectedWatchlistRequest,
  DisclosureCollectWatchlistRequest,
  DisclosureListParams,
} from "@/types/disclosure";

const sample: Disclosure[] = [
  {
    id: 1,
    stock_id: 1,
    dart_receipt_no: "20260509000123",
    disclosure_title: "사업보고서 (샘플)",
    disclosure_type: "정기공시",
    disclosed_at: "2026-05-09 00:00:00",
    url: "https://dart.fss.or.kr/dsaf001/main.do?rcpNo=20260509000123",
    raw_text_path: "data/raw/dart/disclosures/005930_20260509_170000_response.json",
    summary: null,
    importance_score: 0,
    created_at: "2026-05-09 17:00:00",
  },
];

export const disclosureMockRepository = {
  async listDisclosures(params?: DisclosureListParams): Promise<Disclosure[]> {
    let result = [...sample];
    if (params?.stock_id !== undefined) result = result.filter((d) => d.stock_id === params.stock_id);
    if (params?.keyword) {
      result = result.filter(
        (d) => d.disclosure_title.includes(params.keyword as string) || (d.dart_receipt_no || "").includes(params.keyword as string),
      );
    }
    if (params?.disclosure_type) result = result.filter((d) => (d.disclosure_type || "") === params.disclosure_type);
    const offset = params?.offset ?? 0;
    const limit = params?.limit ?? 50;
    return result.slice(offset, offset + limit);
  },
  async getDisclosure(disclosureId: number): Promise<Disclosure> {
    const found = sample.find((d) => d.id === disclosureId);
    if (!found) throw new Error("disclosure not found");
    return found;
  },
  async collectDisclosuresForStock(payload: DisclosureCollectRequest): Promise<DisclosureCollectResponse> {
    return {
      collector_name: "dart_disclosure_collector",
      status: "success",
      target: "MOCK",
      collected_count: payload.page_count,
      saved_count: 0,
      skipped_count: payload.page_count,
      message: "mock mode: disclosure collection not executed",
    };
  },
  async collectDisclosuresForWatchlist(payload: DisclosureCollectWatchlistRequest): Promise<DisclosureCollectResponse> {
    return {
      collector_name: "dart_disclosure_collector",
      status: "success",
      target: "watchlist",
      collected_count: payload.page_count,
      saved_count: 0,
      skipped_count: payload.page_count,
      message: "mock mode: watchlist disclosure collection not executed",
    };
  },
  async collectDisclosuresForSelectedWatchlist(payload: DisclosureCollectSelectedWatchlistRequest): Promise<DisclosureCollectSelectedResponse> {
    return {
      requested_count: payload.stock_ids.length,
      success_count: payload.stock_ids.length,
      failed_count: 0,
      message: "mock mode: selected watchlist disclosure collection not executed",
      results: payload.stock_ids.map((stockId) => ({
        stock_id: stockId,
        stock_code: `MOCK-${stockId}`,
        stock_name: `Mock Stock ${stockId}`,
        status: "success",
        collected_count: payload.page_count,
        saved_count: 0,
        skipped_count: payload.page_count,
        message: "mock success",
      })),
    };
  },
  async summarizeSelectedDisclosures(disclosureIds: number[]): Promise<AiSummarizeResponse> {
    return {
      status: "success",
      target: "disclosures",
      processed_count: disclosureIds.length,
      success_count: disclosureIds.length,
      failed_count: 0,
      skipped_count: 0,
      message: "mock mode: selected disclosures summarize completed",
    };
  },
};
