import type {
  CollectionRun,
  CollectionRunCleanupPreviewResponse,
  CollectionRunCleanupResponse,
  CollectionRunListParams,
  CollectionRunListResponse,
} from "@/types/collectionRun";

const sampleRuns: CollectionRun[] = [
  {
    id: 101,
    collector_name: "naver_news_collector",
    target: "005930",
    status: "success",
    started_at: "2026-05-09 16:10:00",
    finished_at: "2026-05-09 16:10:05",
    message: "keyword=삼성전자, total=20, collected_count=20, saved_count=18, skipped_count=2",
    created_at: "2026-05-09 16:10:00",
  },
  {
    id: 102,
    collector_name: "naver_news_collector",
    target: "000660",
    status: "failed",
    started_at: "2026-05-09 16:20:00",
    finished_at: "2026-05-09 16:20:03",
    message: "collector error",
    created_at: "2026-05-09 16:20:00",
  },
  {
    id: 103,
    collector_name: "naver_news_collector",
    target: "watchlist",
    status: "partial",
    started_at: "2026-05-09 16:30:00",
    finished_at: "2026-05-09 16:30:30",
    message: "partial success",
    created_at: "2026-05-09 16:30:00",
  },
  {
    id: 104,
    collector_name: "naver_news_collector",
    target: "035420",
    status: "running",
    started_at: "2026-05-09 16:40:00",
    finished_at: null,
    message: null,
    created_at: "2026-05-09 16:40:00",
  },
];

export const collectionRunMockRepository = {
  async listCollectionRuns(params?: CollectionRunListParams): Promise<CollectionRunListResponse> {
    let result = [...sampleRuns];
    if (params?.collector_name) result = result.filter((r) => r.collector_name.includes(params.collector_name as string));
    if (params?.status) result = result.filter((r) => r.status === params.status);
    if (params?.target) result = result.filter((r) => (r.target || "").includes(params.target as string));
    const offset = params?.offset ?? 0;
    const limit = params?.limit ?? 20;
    return {
      items: result.slice(offset, offset + limit),
      total_count: result.length,
      limit,
      offset,
    };
  },
  async getCollectionRun(runId: number): Promise<CollectionRun> {
    const found = sampleRuns.find((r) => r.id === runId);
    if (!found) throw new Error("collection run not found");
    return found;
  },
  async previewCleanupOlderThanOneMonth(): Promise<CollectionRunCleanupPreviewResponse> {
    return {
      success: true,
      cutoff_date: "2026-04-24 00:00:00",
      target_count: 0,
      message: "1달 전 수집 이력 0건이 삭제 대상입니다.",
    };
  },
  async cleanupOlderThanOneMonth(): Promise<CollectionRunCleanupResponse> {
    return {
      success: true,
      cutoff_date: "2026-04-24 00:00:00",
      deleted_count: 0,
      message: "삭제할 1달 전 수집 이력이 없습니다.",
    };
  },
};
