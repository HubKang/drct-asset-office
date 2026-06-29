import type {
  CollectStockTrackingPricesPayload,
  CreateStockTrackingGroupPayload,
  CreateTrackingFromConditionResultsPayload,
  RegisterTrackingItemsFromCandidatesPayload,
  StockTrackingChartPrice,
  StockTrackingChartResponse,
  StockTrackingGroup,
  StockTrackingGroupAnalysis,
  StockTrackingGroupAnalysisListResponse,
  StockTrackingImage,
  StockTrackingImageType,
  StockTrackingItem,
  StockTrackingStatus,
  UpdateStockTrackingGroupPayload,
  UpdateStockTrackingReviewPayload,
} from "@/types/stockTracking";

let groups: StockTrackingGroup[] = [
  {
    id: 1,
    name: "15% 급등",
    description: "강한 수급 후보 관찰",
    success_rule_note: "추세 지속 여부 확인",
    fail_rule_note: "거래대금 급감",
    observation_note: "테마 연결과 눌림 구간 기록",
    is_active: 1,
    item_count: 0,
    tracking_count: 0,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  },
];
let items: StockTrackingItem[] = [];
let chartMap: Record<number, StockTrackingChartPrice[]> = {};
let imageMap: Record<number, StockTrackingImage[]> = {};
let nextImageId = 1;

const IMAGE_TYPE_LABELS: Record<StockTrackingImageType, string> = {
  BASE_DATE: "기준일 차트",
  SUCCESS: "성공 근거",
  FAIL: "실패 근거",
  PULLBACK: "눌림 구간",
  OVERHEAT: "과열 구간",
  ENTRY_POINT: "진입 가능 구간",
  ETC: "기타",
};
let nextGroupId = 2;
let nextItemId = 1;

const today = () => new Date().toISOString().slice(0, 10);
const isoDate = (offset: number) => {
  const d = new Date();
  d.setDate(d.getDate() + offset);
  return d.toISOString().slice(0, 10);
};


const avg = (values: Array<number | null | undefined>) => {
  const numbers = values.filter((value): value is number => value != null && Number.isFinite(value));
  return numbers.length > 0 ? Number((numbers.reduce((sum, value) => sum + value, 0) / numbers.length).toFixed(4)) : null;
};

const diff = (left: number | null, right: number | null) => left == null || right == null ? null : Number((left - right).toFixed(4));
const pct = (value: number | null, base: number | null) => value == null || base == null || base <= 0 ? null : Number((((value - base) / base) * 100).toFixed(4));
const BASE_METRIC_KEYS = ["close_vs_ma20_pct", "close_vs_ma60_pct", "recent_5d_return_pct", "trading_value_ratio_20", "ma60_slope_5d_pct", "high_vs_close_pct", "close_position_pct"] as const;
type MockBaseMetricKey = typeof BASE_METRIC_KEYS[number];
const emptyMetricRecord = (): Record<MockBaseMetricKey, number | null> => ({
  close_vs_ma20_pct: null,
  close_vs_ma60_pct: null,
  recent_5d_return_pct: null,
  trading_value_ratio_20: null,
  ma60_slope_5d_pct: null,
  high_vs_close_pct: null,
  close_position_pct: null,
});
const metricSummary = (rows: Array<Record<MockBaseMetricKey, number | null>>): Record<MockBaseMetricKey, number | null> => {
  const result = emptyMetricRecord();
  BASE_METRIC_KEYS.forEach((key) => {
    result[key] = avg(rows.map((row) => row[key]));
  });
  return result;
};
const metricDiff = (left: Record<MockBaseMetricKey, number | null>, right: Record<MockBaseMetricKey, number | null>): Record<MockBaseMetricKey, number | null> => {
  const result = emptyMetricRecord();
  BASE_METRIC_KEYS.forEach((key) => {
    result[key] = diff(left[key], right[key]);
  });
  return result;
};

const calcBaseMetrics = (item: StockTrackingItem) => {
  const prices = chartMap[item.id] ?? [];
  const baseIdx = prices.findIndex((row) => row.date.slice(0, 10) >= item.tracking_base_date.slice(0, 10));
  if (baseIdx < 0) return null;
  const row = prices[baseIdx];
  const close = row.close ?? null;
  const high = row.high ?? null;
  const low = row.low ?? null;
  const ma20 = row.ma20 ?? null;
  const ma60 = row.ma60 ?? null;
  const close5 = baseIdx >= 5 ? prices[baseIdx - 5]?.close ?? null : null;
  const ma605 = baseIdx >= 5 ? prices[baseIdx - 5]?.ma60 ?? null : null;
  const previousValues = prices.slice(Math.max(0, baseIdx - 20), baseIdx).map((price) => price.trading_value).filter((value): value is number => value != null);
  const avgPreviousTradingValue = previousValues.length >= 10 ? previousValues.reduce((sum, value) => sum + value, 0) / previousValues.length : null;
  const metrics = {
    close_vs_ma20_pct: close != null && ma20 != null ? pct(close - ma20, ma20) : null,
    close_vs_ma60_pct: close != null && ma60 != null ? pct(close - ma60, ma60) : null,
    recent_5d_return_pct: close != null && close5 != null ? pct(close - close5, close5) : null,
    trading_value_ratio_20: row.trading_value != null && avgPreviousTradingValue ? Number((row.trading_value / avgPreviousTradingValue).toFixed(4)) : null,
    ma60_slope_5d_pct: ma60 != null && ma605 != null ? pct(ma60 - ma605, ma605) : null,
    high_vs_close_pct: close != null && high != null ? pct(close - high, high) : null,
    close_position_pct: close != null && high != null && low != null && high !== low ? pct(close - low, high - low) : null,
  };
  return Object.values(metrics).some((value) => value != null) ? metrics : null;
};

const calcItemMetrics = (item: StockTrackingItem) => {
  const prices = (chartMap[item.id] ?? []).filter((row) => row.date.slice(0, 10) >= item.tracking_base_date.slice(0, 10));
  if (prices.length === 0) return null;
  const baseRow = prices.find((row) => row.date.slice(0, 10) === item.tracking_base_date.slice(0, 10));
  const firstClose = prices.find((row) => row.close != null);
  const base = baseRow?.close ?? item.base_price ?? firstClose?.close ?? null;
  if (base == null || base <= 0) return null;
  const closes = prices.map((row) => row.close).filter((value): value is number => value != null);
  const highs = prices.map((row) => row.high).filter((value): value is number => value != null);
  const lows = prices.map((row) => row.low).filter((value): value is number => value != null);
  if (closes.length === 0) return null;
  return {
    current_return_pct: pct(closes[closes.length - 1], base),
    max_return_pct: highs.length > 0 ? pct(Math.max(...highs), base) : null,
    max_drawdown_pct: lows.length > 0 ? pct(Math.min(...lows), base) : null,
    elapsed_trading_days: Math.max(0, prices.length - 1),
  };
};

const movingAverage = (values: number[], idx: number, window: number) => {
  if (idx + 1 < window) return null;
  const slice = values.slice(idx - window + 1, idx + 1);
  return Number((slice.reduce((sum, value) => sum + value, 0) / window).toFixed(2));
};

const generateChart = (itemId: number) => {
  const closes: number[] = [];
  const rows: StockTrackingChartPrice[] = [];
  let price = 9000 + itemId * 370;
  for (let i = 0; i < 110; i += 1) {
    const drift = Math.sin(i / 7) * 140 + (i % 9 - 4) * 18;
    const close = Math.max(1000, price + drift);
    const open = close - Math.sin(i / 4) * 90;
    const high = Math.max(open, close) + 120 + (i % 5) * 12;
    const low = Math.min(open, close) - 120 - (i % 3) * 18;
    closes.push(close);
    rows.push({
      date: isoDate(i - 109),
      open: Math.round(open),
      high: Math.round(high),
      low: Math.round(low),
      close: Math.round(close),
      volume: 600000 + i * 4500 + (i % 11) * 24000,
      trading_value: Math.round(close * (600000 + i * 4500)),
      ma5: movingAverage(closes, i, 5),
      ma10: movingAverage(closes, i, 10),
      ma20: movingAverage(closes, i, 20),
      ma60: movingAverage(closes, i, 60),
      ma120: movingAverage(closes, i, 120),
    });
    price = close + 12;
  }
  chartMap[itemId] = rows;
  return rows;
};

const refreshGroupCounts = () => {
  groups = groups.map((group) => {
    const groupItems = items.filter((item) => item.group_id === group.id);
    return {
      ...group,
      item_count: groupItems.length,
      tracking_count: groupItems.filter((item) => item.status === "TRACKING").length,
    };
  });
};

export const stockTrackingMockRepository = {
  listGroups: async (params?: { active_only?: boolean }) => {
    refreshGroupCounts();
    return params?.active_only ? groups.filter((group) => group.is_active === 1) : groups;
  },
  createGroup: async (payload: CreateStockTrackingGroupPayload) => {
    const row: StockTrackingGroup = {
      id: nextGroupId++,
      name: payload.name,
      description: payload.description ?? null,
      success_rule_note: payload.success_rule_note ?? null,
      fail_rule_note: payload.fail_rule_note ?? null,
      observation_note: payload.observation_note ?? null,
      is_active: payload.is_active ?? 1,
      item_count: 0,
      tracking_count: 0,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    };
    groups = [row, ...groups];
    return row;
  },
  updateGroup: async (groupId: number, payload: UpdateStockTrackingGroupPayload) => {
    groups = groups.map((group) => (group.id === groupId ? { ...group, ...payload, updated_at: new Date().toISOString() } : group));
    return groups.find((group) => group.id === groupId)!;
  },
  deleteGroup: async (groupId: number) => {
    groups = groups.filter((group) => group.id !== groupId);
    return { success: true, group_id: groupId };
  },
  listGroupAnalysis: async (params?: { active_only?: boolean; group_id?: number; min_completed_count?: number }): Promise<StockTrackingGroupAnalysisListResponse> => {
    const targetGroups = groups.filter((group) => (params?.active_only === false || group.is_active === 1) && (params?.group_id === undefined || group.id === params.group_id));
    const rows: StockTrackingGroupAnalysis[] = targetGroups.map((group) => {
      const groupItems = items.filter((item) => item.group_id === group.id);
      const metrics = groupItems.map((item) => {
        const returnMetrics = calcItemMetrics(item);
        const baseMetrics = calcBaseMetrics(item);
        return { item, metrics: returnMetrics && baseMetrics ? { ...returnMetrics, ...baseMetrics } : returnMetrics, baseMetrics };
      }).filter((row): row is { item: StockTrackingItem; metrics: NonNullable<ReturnType<typeof calcItemMetrics>> & Partial<Record<MockBaseMetricKey, number | null>>; baseMetrics: NonNullable<ReturnType<typeof calcBaseMetrics>> | null } => row.metrics != null);
      const baseMetrics = metrics.map((row) => row.baseMetrics).filter((row): row is NonNullable<ReturnType<typeof calcBaseMetrics>> => row != null);
      const successRows = metrics.filter((row) => row.item.status === "SUCCESS");
      const failRows = metrics.filter((row) => row.item.status === "FAIL");
      const successBaseMetrics = successRows.map((row) => row.baseMetrics).filter((row): row is NonNullable<ReturnType<typeof calcBaseMetrics>> => row != null);
      const failBaseMetrics = failRows.map((row) => row.baseMetrics).filter((row): row is NonNullable<ReturnType<typeof calcBaseMetrics>> => row != null);
      const successCount = groupItems.filter((item) => item.status === "SUCCESS").length;
      const failCount = groupItems.filter((item) => item.status === "FAIL").length;
      const completedCount = successCount + failCount;
      const successAvgCurrent = avg(successRows.map((row) => row.metrics.current_return_pct));
      const failAvgCurrent = avg(failRows.map((row) => row.metrics.current_return_pct));
      const successAvgMax = avg(successRows.map((row) => row.metrics.max_return_pct));
      const failAvgMax = avg(failRows.map((row) => row.metrics.max_return_pct));
      const successAvgDrawdown = avg(successRows.map((row) => row.metrics.max_drawdown_pct));
      const failAvgDrawdown = avg(failRows.map((row) => row.metrics.max_drawdown_pct));
      const successBaseAvg = metricSummary(successBaseMetrics);
      const failBaseAvg = metricSummary(failBaseMetrics);
      const toSample = (row: { item: StockTrackingItem; metrics: NonNullable<ReturnType<typeof calcItemMetrics>> }) => ({
        item_id: row.item.id,
        stock_code: row.item.stock_code,
        stock_name: row.item.stock_name,
        tracking_base_date: row.item.tracking_base_date,
        review_date: row.item.review_date,
        review_note: row.item.review_note,
        ...row.metrics,
      });
      return {
        group_id: group.id,
        group_name: group.name,
        total_count: groupItems.length,
        tracking_count: groupItems.filter((item) => item.status === "TRACKING").length,
        hold_count: groupItems.filter((item) => item.status === "HOLD").length,
        success_count: successCount,
        fail_count: failCount,
        excluded_count: groupItems.filter((item) => item.status === "EXCLUDED").length,
        completed_count: completedCount,
        success_rate: completedCount > 0 ? Number(((successCount / completedCount) * 100).toFixed(2)) : null,
        return_calculated_count: metrics.length,
        base_metric_calculated_count: baseMetrics.length,
        base_metric_summary: {
          avg: metricSummary(baseMetrics),
          success_avg: successBaseAvg,
          fail_avg: failBaseAvg,
          diff: metricDiff(successBaseAvg, failBaseAvg),
        },
        avg_current_return_pct: avg(metrics.map((row) => row.metrics.current_return_pct)),
        avg_max_return_pct: avg(metrics.map((row) => row.metrics.max_return_pct)),
        avg_max_drawdown_pct: avg(metrics.map((row) => row.metrics.max_drawdown_pct)),
        avg_elapsed_trading_days: avg(metrics.map((row) => row.metrics.elapsed_trading_days)),
        success_avg_current_return_pct: successAvgCurrent,
        success_avg_max_return_pct: successAvgMax,
        success_avg_max_drawdown_pct: successAvgDrawdown,
        success_avg_elapsed_trading_days: avg(successRows.map((row) => row.metrics.elapsed_trading_days)),
        fail_avg_current_return_pct: failAvgCurrent,
        fail_avg_max_return_pct: failAvgMax,
        fail_avg_max_drawdown_pct: failAvgDrawdown,
        fail_avg_elapsed_trading_days: avg(failRows.map((row) => row.metrics.elapsed_trading_days)),
        diff_avg_current_return_pct: diff(successAvgCurrent, failAvgCurrent),
        diff_avg_max_return_pct: diff(successAvgMax, failAvgMax),
        diff_avg_max_drawdown_pct: diff(successAvgDrawdown, failAvgDrawdown),
        success_samples: successRows.sort((a, b) => (b.metrics.max_return_pct ?? -999999) - (a.metrics.max_return_pct ?? -999999)).slice(0, 5).map(toSample),
        fail_samples: failRows.sort((a, b) => (a.metrics.max_drawdown_pct ?? 999999) - (b.metrics.max_drawdown_pct ?? 999999)).slice(0, 5).map(toSample),
      };
    }).filter((row) => params?.min_completed_count === undefined || row.completed_count >= params.min_completed_count);
    return { items: rows.sort((a, b) => b.completed_count - a.completed_count || (b.success_rate ?? -1) - (a.success_rate ?? -1)) };
  },
  listItems: async (params?: { group_id?: number; status?: StockTrackingStatus | ""; keyword?: string; limit?: number; offset?: number }) => {
    let rows = [...items];
    if (params?.group_id) rows = rows.filter((item) => item.group_id === params.group_id);
    if (params?.status) rows = rows.filter((item) => item.status === params.status);
    if (params?.keyword) {
      const keyword = params.keyword.toLowerCase();
      rows = rows.filter((item) => `${item.stock_name ?? ""} ${item.stock_code ?? ""}`.toLowerCase().includes(keyword));
    }
    const total = rows.length;
    const offset = params?.offset ?? 0;
    const limit = params?.limit ?? total;
    return { items: rows.slice(offset, offset + limit), total };
  },
  registerFromConditionResults: async (payload: CreateTrackingFromConditionResultsPayload) => {
    const group = groups.find((row) => row.id === payload.group_id);
    const createdIds: number[] = [];
    let skippedCount = 0;
    const resultItems = payload.items.map((source) => {
      const stockCode = String(source.stock_code || "").replace(/[^0-9]/g, "").slice(-6).padStart(6, "0");
      const duplicate = items.find((item) => item.group_id === payload.group_id && item.stock_code === stockCode && item.tracking_base_date === payload.detected_date);
      if (duplicate) {
        skippedCount += 1;
        return { stock_code: stockCode, stock_name: source.stock_name ?? null, status: "SKIPPED" as const, tracking_item_id: duplicate.id, reason: "이미 같은 그룹/기준일로 등록된 종목입니다." };
      }
      const id = nextItemId++;
      const row: StockTrackingItem = {
        id,
        group_id: payload.group_id,
        group_name: group?.name ?? "Mock 그룹",
        candidate_id: null,
        condition_no: payload.condition_no ?? null,
        condition_name: payload.condition_name ?? null,
        stock_id: id,
        stock_code: stockCode,
        stock_name: source.stock_name ?? stockCode,
        detected_date: payload.detected_date,
        tracking_base_date: payload.detected_date,
        base_price: source.current_price ?? null,
        base_change_rate: source.change_rate ?? null,
        base_volume: source.volume ?? null,
        base_trading_value: source.trading_value ?? null,
        status: "TRACKING",
        review_date: null,
        review_note: null,
        price_status: "NOT_COLLECTED",
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      };
      items = [row, ...items];
      createdIds.push(id);
      return { stock_code: stockCode, stock_name: row.stock_name, status: "CREATED" as const, tracking_item_id: id, reason: null };
    });
    refreshGroupCounts();
    return {
      success: true,
      requested_count: payload.items.length,
      created_count: createdIds.length,
      skipped_count: skippedCount,
      item_ids: createdIds,
      items: resultItems,
      message: `종목트래킹 등록 완료: 신규 ${createdIds.length}건, 중복 제외 ${skippedCount}건`,
    };
  },
  registerFromCandidates: async (payload: RegisterTrackingItemsFromCandidatesPayload) => {
    const group = groups.find((row) => row.id === payload.group_id);
    const createdIds: number[] = [];
    const resultItems = payload.candidate_ids.map((candidateId) => {
      const duplicate = items.find((item) => item.group_id === payload.group_id && item.candidate_id === candidateId);
      if (duplicate) {
        return { candidate_id: candidateId, stock_code: duplicate.stock_code, stock_name: duplicate.stock_name, status: "SKIPPED" as const, message: "이미 해당 그룹에 등록된 후보입니다." };
      }
      const id = nextItemId++;
      const row: StockTrackingItem = {
        id,
        group_id: payload.group_id,
        group_name: group?.name ?? "Mock 그룹",
        candidate_id: candidateId,
        condition_no: "mock",
        condition_name: "저장된 수급 이벤트 후보",
        stock_id: id,
        stock_code: String(100000 + candidateId).slice(-6),
        stock_name: `후보 ${candidateId}`,
        detected_date: today(),
        tracking_base_date: today(),
        base_price: null,
        base_change_rate: null,
        base_volume: null,
        base_trading_value: null,
        status: "TRACKING",
        review_date: null,
        review_note: null,
        price_status: "NOT_COLLECTED",
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      };
      items = [row, ...items];
      createdIds.push(id);
      return { candidate_id: candidateId, stock_code: row.stock_code, stock_name: row.stock_name, status: "CREATED" as const, message: null };
    });
    refreshGroupCounts();
    const skippedCount = resultItems.filter((item) => item.status === "SKIPPED").length;
    return {
      success: true,
      requested_count: payload.candidate_ids.length,
      created_count: createdIds.length,
      skipped_count: skippedCount,
      item_ids: createdIds,
      items: resultItems,
      message: `종목트래킹 등록 완료: 신규 ${createdIds.length}건, 중복 제외 ${skippedCount}건`,
    };
  },
  collectPrices: async (payload: CollectStockTrackingPricesPayload) => {
    let successCount = 0;
    let partialCount = 0;
    const results = payload.item_ids.map((itemId) => {
      const item = items.find((row) => row.id === itemId);
      if (!item || !["TRACKING", "HOLD"].includes(item.status)) {
        partialCount += 1;
        return { item_id: itemId, stock_code: item?.stock_code ?? null, stock_name: item?.stock_name ?? null, status: "SKIPPED" as const, collected_count: 0, last_collected_date: null, message: "갱신 대상이 아닙니다." };
      }
      const prices = generateChart(itemId);
      items = items.map((row) => (row.id === itemId ? { ...row, price_status: "LATEST", updated_at: new Date().toISOString() } : row));
      successCount += 1;
      return { item_id: itemId, stock_code: item.stock_code, stock_name: item.stock_name, status: "SUCCESS" as const, collected_count: prices.length, last_collected_date: prices[prices.length - 1]?.date ?? today(), message: null };
    });
    return {
      requested_count: payload.item_ids.length,
      success_count: successCount,
      partial_count: partialCount,
      failed_count: 0,
      items: results,
      message: `가격정보 갱신 완료: 성공 ${successCount}건, 일부 누락 ${partialCount}건, 실패 0건`,
    };
  },
  getChart: async (itemId: number): Promise<StockTrackingChartResponse> => {
    const item = items.find((row) => row.id === itemId);
    return {
      item_id: itemId,
      stock_code: item?.stock_code ?? null,
      stock_name: item?.stock_name ?? null,
      tracking_base_date: item?.tracking_base_date ?? today(),
      review_date: item?.review_date ?? null,
      prices: chartMap[itemId] ?? [],
    };
  },
  getItem: async (itemId: number) => items.find((item) => item.id === itemId)!,
  listImages: async (itemId: number) => ({ items: imageMap[itemId] ?? [] }),
  uploadImage: async (itemId: number, payload: { file: File; image_type: StockTrackingImageType; caption?: string }) => {
    const row: StockTrackingImage = {
      id: nextImageId++,
      tracking_item_id: itemId,
      image_url: URL.createObjectURL(payload.file),
      image_path: null,
      original_filename: payload.file.name,
      image_type: payload.image_type,
      image_type_label: IMAGE_TYPE_LABELS[payload.image_type],
      caption: payload.caption ?? null,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    };
    imageMap[itemId] = [row, ...(imageMap[itemId] ?? [])];
    return row;
  },
  deleteImage: async (imageId: number) => {
    for (const itemId of Object.keys(imageMap)) {
      imageMap[Number(itemId)] = imageMap[Number(itemId)].filter((image) => image.id !== imageId);
    }
    return { success: true, image_id: imageId };
  },
  updateReview: async (itemId: number, payload: UpdateStockTrackingReviewPayload) => {
    items = items.map((item) => (item.id === itemId ? { ...item, status: payload.status as StockTrackingStatus, review_note: payload.review_note ?? null, price_status: ["SUCCESS", "FAIL", "EXCLUDED"].includes(payload.status) ? "STOPPED" : item.price_status } : item));
    refreshGroupCounts();
    return items.find((item) => item.id === itemId)!;
  },
  deleteItem: async (itemId: number) => {
    items = items.filter((item) => item.id !== itemId);
    delete chartMap[itemId];
    delete imageMap[itemId];
    refreshGroupCounts();
    return { success: true, item_id: itemId };
  },
};
