import { useCallback, useEffect, useMemo, useState } from "react";
import type { CSSProperties } from "react";
import { useNavigate } from "react-router-dom";
import PageHeader from "@/components/common/PageHeader";
import SectionCard from "@/components/common/SectionCard";
import StatusBadge from "@/components/common/StatusBadge";
import {
  buildNaverKoreaMarketChartUrl,
  buildNaverMarketIndexAreaChartUrl,
  buildNaverWorldIndexChartUrl,
  createNaverChartSidcode,
} from "@/utils/naverChart";
import { buildTreemapLayout, getTreemapLabelClass, getTreemapTextMetrics } from "@/utils/treemapLayout";
import { dataSourceLabel, repositories } from "@/services";
import type { CollectionRun } from "@/types/collectionRun";
import type { Disclosure } from "@/types/disclosure";
import type { BriefingVideo } from "@/types/economicBriefing";
import type { MarketThemeMonthlyReturnResponse, MarketThemeMonthlyReturnThemeItem } from "@/types/marketTheme";
import type { NewsItem } from "@/types/news";
import type { TelegramItem } from "@/types/telegram";
import type { TradeReviewListItem } from "@/types/tradeReview";

type SourceKey = "news" | "disclosure" | "youtube" | "telegram";
type SourceStatus = "normal" | "warning" | "idle";
type DetailFilter = "all" | "summarized" | "pending" | "issue";
type ThemeFlowViewMode = "THEME_GROUP" | "THEME";

type DashboardIndicator = {
  title: string;
  category: string;
  imageUrl: string;
  helpType?: "dollar-index";
};

type SourceSummary = {
  source: SourceKey;
  label: string;
  collected_count: number;
  summarized_count: number;
  pending_count: number;
  failed_count: number;
  last_collected_at: string | null;
  status: SourceStatus;
  top_keywords: string[];
};

type CalendarDay = {
  date: string;
  news_count: number;
  disclosure_count: number;
  youtube_count: number;
  telegram_count: number;
  failed_count: number;
};

type FeedItem = {
  id: string;
  source: SourceKey;
  title: string;
  collected_at: string;
  ai_status: string;
  status_group: "summarized" | "pending" | "issue";
  related_stock?: string | null;
  keywords: string[];
  summary_text?: string | null;
  original_url?: string | null;
  target_url: string;
};

type KeywordIssueItem = {
  keyword: string;
  total: number;
  sourceCounts: Partial<Record<SourceKey, number>>;
  relatedStocks: string[];
  summarized_count: number;
  pending_count: number;
  recent_title: string;
};

type ThemeTreemapItem = {
  marketThemeId: number;
  themeName: string;
  viewMode: ThemeFlowViewMode;
  themeGroupId: number | null;
  themeGroupName: string | null;
  childThemeCount: number;
  topChildThemes: string[];
  returnSum: number;
  sizeValue: number;
  tradingValue100m: number;
  stockCount: number;
  successStockCount: number;
  dataDays: number;
  risingDays: number;
  fallingDays: number;
  flatDays: number;
  rank: number;
};

type TrainingStatus = {
  total_trades: number;
  reviewed_count: number;
  unreviewed_count: number;
  review_rate: number;
  recent_completed: number;
  recent_return_rate: number | null;
  discipline_score: number | null;
  gpt_review_ready_count: number;
  next_training_goal: string;
};

type AttentionItem = {
  id: string;
  label: string;
  detail: string;
  tone: "amber" | "rose" | "blue" | "slate";
  target_url: string;
};

type DashboardData = {
  today: string;
  source_summaries: SourceSummary[];
  weekly_calendar: CalendarDay[];
  feed_by_source: Record<SourceKey, FeedItem[]>;
  issue_keywords: KeywordIssueItem[];
  cross_keywords: KeywordIssueItem[];
  theme_treemap: ThemeTreemapItem[];
  training_status: TrainingStatus;
  attention_items: AttentionItem[];
};

const SOURCE_LABEL: Record<SourceKey, string> = {
  news: "뉴스",
  disclosure: "공시",
  youtube: "유튜브",
  telegram: "텔레그램",
};

const SOURCE_ROUTE: Record<SourceKey, string> = {
  news: "/news",
  disclosure: "/disclosures",
  youtube: "/economic-briefing",
  telegram: "/telegram-briefing",
};

const SOURCE_RUN_KEYWORDS: Record<SourceKey, string[]> = {
  news: ["news"],
  disclosure: ["disclosure", "dart"],
  youtube: ["youtube", "economic", "briefing", "transcript"],
  telegram: ["telegram"],
};

const DETAIL_TABS: Array<{ key: DetailFilter; label: string }> = [
  { key: "all", label: "전체" },
  { key: "summarized", label: "요약완료" },
  { key: "pending", label: "요약대기" },
  { key: "issue", label: "오류·스킵" },
];

const todayInKst = () =>
  new Intl.DateTimeFormat("sv-SE", { timeZone: "Asia/Seoul" }).format(new Date());

const shiftDate = (baseDate: string, days: number) => {
  const date = new Date(`${baseDate}T00:00:00+09:00`);
  date.setDate(date.getDate() + days);
  return new Intl.DateTimeFormat("sv-SE", { timeZone: "Asia/Seoul" }).format(date);
};

const subtractOneMonth = (baseDate: string) => {
  const [year, month, day] = baseDate.split("-").map(Number);
  const date = new Date(Date.UTC(year, (month ?? 1) - 1, day ?? 1));
  date.setUTCMonth(date.getUTCMonth() - 1);
  return new Intl.DateTimeFormat("sv-SE", { timeZone: "UTC" }).format(date);
};

const getDatePart = (value?: string | null) => {
  if (!value) return "";
  const raw = value.trim();
  if (!raw) return "";
  if (raw.length >= 10 && /^\d{4}-\d{2}-\d{2}/.test(raw)) return raw.slice(0, 10);
  const parsed = new Date(raw);
  if (Number.isNaN(parsed.getTime())) return "";
  return new Intl.DateTimeFormat("sv-SE", { timeZone: "Asia/Seoul" }).format(parsed);
};

const formatDateTime = (value?: string | null) => {
  if (!value) return "-";
  const normalized = value.replace(" ", "T");
  const dt = new Date(normalized);
  if (Number.isNaN(dt.getTime())) return value;
  return new Intl.DateTimeFormat("ko-KR", {
    timeZone: "Asia/Seoul",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(dt);
};

const maxDate = (values: Array<string | null | undefined>) => {
  const filtered = values.filter((v): v is string => Boolean(v && v.trim()));
  if (!filtered.length) return null;
  return filtered.sort()[filtered.length - 1] ?? null;
};

const statusLabel = (status: SourceStatus) => {
  if (status === "normal") return "정상";
  if (status === "warning") return "확인 필요";
  return "미수집";
};

const toneByStatus = (status: SourceStatus): "emerald" | "amber" | "slate" => {
  if (status === "normal") return "emerald";
  if (status === "warning") return "amber";
  return "slate";
};

const sourceTone = (source: SourceKey): "emerald" | "amber" | "blue" | "slate" => {
  if (source === "telegram") return "emerald";
  if (source === "youtube") return "amber";
  if (source === "news") return "blue";
  return "slate";
};

const summarizeStatusLabel = (value: string) => {
  const key = (value || "").toLowerCase();
  if (["summarized", "success", "completed"].includes(key)) return "요약완료";
  if (["failed", "error"].includes(key)) return "오류·스킵";
  if (["pending", "running", "queued"].includes(key)) return "요약대기";
  return value || "미확인";
};

const inferStatusGroup = (value: string): FeedItem["status_group"] => {
  const key = (value || "").toLowerCase();
  if (["summarized", "success", "completed"].includes(key)) return "summarized";
  if (["failed", "error", "skipped"].includes(key)) return "issue";
  return "pending";
};

const inferSourceFromRun = (run: CollectionRun): SourceKey | null => {
  const haystack = `${run.collector_name} ${run.collector_display_name ?? ""} ${run.collector_group ?? ""}`.toLowerCase();
  const found = (Object.keys(SOURCE_RUN_KEYWORDS) as SourceKey[]).find((key) =>
    SOURCE_RUN_KEYWORDS[key].some((keyword) => haystack.includes(keyword)),
  );
  return found ?? null;
};

const splitKeywords = (value?: string | null): string[] =>
  (value || "")
    .split(/[\s,|/#·]+/g)
    .map((v) => v.trim())
    .filter((v) => v.length >= 2 && v.length <= 18);

const uniqueCompact = (values: Array<string | null | undefined>, limit: number) =>
  Array.from(new Set(values.map((v) => (v || "").trim()).filter(Boolean))).slice(0, limit);

const getTopKeywords = (items: FeedItem[], limit = 3) => {
  const counts = new Map<string, number>();
  items.forEach((item) => item.keywords.forEach((keyword) => counts.set(keyword, (counts.get(keyword) ?? 0) + 1)));
  return Array.from(counts.entries())
    .sort((a, b) => b[1] - a[1])
    .slice(0, limit)
    .map(([keyword]) => keyword);
};

const buildKeywordIssues = (items: FeedItem[], requireMultiSource: boolean, limit: number): KeywordIssueItem[] => {
  const map = new Map<string, KeywordIssueItem>();
  items.forEach((item) => {
    item.keywords.forEach((keyword) => {
      const row =
        map.get(keyword) ??
        {
          keyword,
          total: 0,
          sourceCounts: {},
          relatedStocks: [],
          summarized_count: 0,
          pending_count: 0,
          recent_title: item.title,
        };
      row.total += 1;
      row.sourceCounts[item.source] = (row.sourceCounts[item.source] ?? 0) + 1;
      if (item.related_stock && !row.relatedStocks.includes(item.related_stock)) row.relatedStocks.push(item.related_stock);
      if (item.status_group === "summarized") row.summarized_count += 1;
      if (item.status_group === "pending") row.pending_count += 1;
      if (item.collected_at >= (items.find((x) => x.title === row.recent_title)?.collected_at ?? "")) {
        row.recent_title = item.title;
      }
      map.set(keyword, row);
    });
  });
  return Array.from(map.values())
    .filter((row) => !requireMultiSource || Object.keys(row.sourceCounts).length >= 2)
    .sort((a, b) => b.total - a.total)
    .slice(0, limit)
    .map((row) => ({ ...row, relatedStocks: row.relatedStocks.slice(0, 4) }));
};

const getInclusiveDateSpan = (startDate: string, endDate: string) => {
  const start = new Date(`${startDate}T00:00:00Z`);
  const end = new Date(`${endDate}T00:00:00Z`);
  const diff = Math.floor((end.getTime() - start.getTime()) / 86400000) + 1;
  return Number.isFinite(diff) && diff > 0 ? diff : 30;
};

const sumThemeReturnRates = (theme: MarketThemeMonthlyReturnThemeItem) => {
  if (theme.period_sum_return != null) return Number(theme.period_sum_return);
  const rates = theme.daily_returns
    .map((day) => day.avg_change_rate)
    .filter((value): value is number => value != null && Number.isFinite(Number(value)))
    .map(Number);
  return rates.length ? rates.reduce((sum, value) => sum + value, 0) : 0;
};

const buildThemeReturnTreemapItems = (
  response: MarketThemeMonthlyReturnResponse | null,
  viewMode: ThemeFlowViewMode,
): ThemeTreemapItem[] => {
  if (!response) return [];
  const map = new Map<number, Omit<ThemeTreemapItem, "rank">>();

  (response.themes ?? []).forEach((theme) => {
    const returnSum = sumThemeReturnRates(theme);
    if (!Number.isFinite(returnSum) || returnSum === 0) return;

    const key = viewMode === "THEME_GROUP" ? theme.theme_group_id ?? -1 : theme.theme_id;
    const current = map.get(key) ?? {
      marketThemeId: key,
      themeName: viewMode === "THEME_GROUP" ? theme.theme_group_name || "??? ????" : theme.theme_name,
      viewMode,
      themeGroupId: theme.theme_group_id ?? null,
      themeGroupName: theme.theme_group_name ?? null,
      childThemeCount: 0,
      topChildThemes: [],
      returnSum: 0,
      sizeValue: 0,
      tradingValue100m: 0,
      stockCount: 0,
      successStockCount: 0,
      dataDays: 0,
      risingDays: 0,
      fallingDays: 0,
      flatDays: 0,
    };

    const latestDaily = theme.daily_returns[theme.daily_returns.length - 1];
    const latestStockCount =
      Number(latestDaily?.rising_stock_count ?? 0) +
      Number(latestDaily?.falling_stock_count ?? 0) +
      Number(latestDaily?.flat_stock_count ?? 0);

    if (viewMode === "THEME_GROUP") {
      current.childThemeCount += 1;
      current.topChildThemes = Array.from(new Set([...current.topChildThemes, theme.theme_name])).slice(0, 3);
      current.stockCount += latestStockCount;
      current.successStockCount += latestStockCount;
    } else {
      current.stockCount = latestStockCount;
      current.successStockCount = latestStockCount;
    }
    current.returnSum += returnSum;
    current.sizeValue = Math.abs(current.returnSum);
    current.tradingValue100m += Number(theme.total_trading_value_100m || 0);
    current.dataDays = Math.max(current.dataDays, Number(theme.data_days || 0));
    current.risingDays += Number(theme.rising_days || 0);
    current.fallingDays += Number(theme.falling_days || 0);
    current.flatDays += Number(theme.flat_days || 0);
    map.set(key, current);
  });

  return Array.from(map.values())
    .map((item) => ({ ...item, returnSum: Math.round(item.returnSum * 100) / 100, sizeValue: Math.abs(Math.round(item.returnSum * 100) / 100) }))
    .filter((item) => item.sizeValue > 0)
    .sort((a, b) => b.sizeValue - a.sizeValue || a.themeName.localeCompare(b.themeName))
    .map((item, idx) => ({ ...item, rank: idx + 1 }));
};

const getThemeTreemapSizeClass = (item: ThemeTreemapItem, maxScore: number) => {
  const ratio = maxScore > 0 ? item.sizeValue / maxScore : 0;
  if (item.rank === 1 || ratio >= 0.72) return "large";
  if (item.rank <= 5 || ratio >= 0.36) return "medium";
  if (ratio >= 0.15) return "small";
  return "tiny";
};

const getDashboardThemeReturnTreemapColor = (value: number | null | undefined) => {
  const n = Number(value ?? 0);
  if (n <= -30) return "#1D4ED8";
  if (n <= -20) return "#2563EB";
  if (n <= -10) return "#3B82F6";
  if (n < 0) return "#93C5FD";
  if (n === 0) return "#E5E7EB";
  if (n < 10) return "#FCA5A5";
  if (n < 20) return "#EF4444";
  if (n < 30) return "#DC2626";
  return "#991B1B";
};

const getDashboardThemeReturnTreemapToneClass = (value: number | null | undefined) => {
  const n = Number(value ?? 0);
  return n <= -10 || n >= 10 ? "is-dark" : "is-light";
};

const formatSignedPct = (value: number | null | undefined) => {
  if (value == null || !Number.isFinite(Number(value))) return "-";
  const n = Number(value);
  return `${n > 0 ? "+" : ""}${n.toFixed(2)}%`;
};

const formatEok = (value: number | null | undefined) => {
  if (value == null || !Number.isFinite(Number(value))) return "-";
  return `${Number(value).toLocaleString("ko-KR", { maximumFractionDigits: 1 })}억`;
};

const DASHBOARD_RETURN_LEGEND = [
  { label: "-30% 이하", color: "#1D4ED8" },
  { label: "-20%", color: "#2563EB" },
  { label: "-10%", color: "#3B82F6" },
  { label: "-5%", color: "#93C5FD" },
  { label: "0%", color: "#E5E7EB" },
  { label: "+5%", color: "#FCA5A5" },
  { label: "+10%", color: "#EF4444" },
  { label: "+20%", color: "#DC2626" },
  { label: "+30% 이상", color: "#991B1B" },
];

const DOLLAR_INDEX_HELP_URL = "https://blog.naver.com/annalife_/224280737671?photoView=3";

function DashboardPage() {
  const navigate = useNavigate();
  const [dashboard, setDashboard] = useState<DashboardData | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");
  const [detailSource, setDetailSource] = useState<SourceKey | null>(null);
  const [detailFilter, setDetailFilter] = useState<DetailFilter>("all");
  const [selectedThemeId, setSelectedThemeId] = useState<number | null>(null);
  const [treemapViewMode, setTreemapViewMode] = useState<ThemeFlowViewMode>("THEME");
  const [treemapTooltip, setTreemapTooltip] = useState<{ x: number; y: number; item: ThemeTreemapItem } | null>(null);
  const [isDollarIndexHelpOpen, setIsDollarIndexHelpOpen] = useState(false);
  const chartSidcode = useMemo(() => createNaverChartSidcode(), []);
  const dashboardIndicators = useMemo<DashboardIndicator[]>(
    () => [
      {
        title: "코스피",
        category: "국내지수 · 90일",
        imageUrl: buildNaverKoreaMarketChartUrl("KOSPI", chartSidcode),
      },
      {
        title: "코스닥",
        category: "국내지수 · 90일",
        imageUrl: buildNaverKoreaMarketChartUrl("KOSDAQ", chartSidcode),
      },
      {
        title: "국제 금",
        category: "원자재 · 3개월",
        imageUrl: buildNaverMarketIndexAreaChartUrl("CMDT_GC", "month3", chartSidcode),
      },
      {
        title: "다우지수",
        category: "해외증시 · 3개월",
        imageUrl: buildNaverWorldIndexChartUrl("DJI@DJI", "month3", chartSidcode),
      },
      {
        title: "나스닥",
        category: "해외증시 · 3개월",
        imageUrl: buildNaverWorldIndexChartUrl("NAS@IXIC", "month3", chartSidcode),
      },
      {
        title: "S&P500",
        category: "해외증시 · 3개월",
        imageUrl: buildNaverWorldIndexChartUrl("SPI@SPX", "month3", chartSidcode),
      },
      {
        title: "달러 환율",
        category: "환율 · 3개월",
        imageUrl: buildNaverMarketIndexAreaChartUrl("FX_USDKRW", "month3", chartSidcode),
      },
      {
        title: "달러 인덱스",
        category: "환율·지수 · 3개월",
        imageUrl: buildNaverMarketIndexAreaChartUrl("FX_USDX", "month3", chartSidcode),
        helpType: "dollar-index",
      },
      {
        title: "WTI",
        category: "원자재 · 3개월",
        imageUrl: buildNaverMarketIndexAreaChartUrl("OIL_CL", "month3"),
      },
    ],
    [chartSidcode],
  );

  const loadDashboard = useCallback(async () => {
    setIsLoading(true);
    setErrorMessage("");
    const today = todayInKst();
    const from30 = shiftDate(today, -29);
    const themePeriodStartDate = subtractOneMonth(today);
    try {
      const themeReturnDays = getInclusiveDateSpan(themePeriodStartDate, today);
      const [runsRes, newsItems, disclosures, videosRes, telegramItemsRes, reviewSummary, recentReviews, themeReturnResponse] = await Promise.all([
        repositories.collectionRuns.listCollectionRuns({ limit: 500, offset: 0 }),
        repositories.news.listNews({ limit: 300, offset: 0 }),
        repositories.disclosures.listDisclosures({ limit: 300, offset: 0 }),
        repositories.economicBriefing.getBriefingVideos({ limit: 300 }),
        repositories.telegram.listItems({ date_from: from30, date_to: today, limit: 500, offset: 0 }),
        repositories.tradeReviews.fetchTradeReviewSummary({ from_date: from30, to_date: today }),
        repositories.tradeReviews.fetchTradeReviews({ from_date: from30, to_date: today, limit: 20, offset: 0 }),
        repositories.marketThemes.listRangeReturns({ end_date: today, days: themeReturnDays, active_only: true }),
      ]);

      const videos = videosRes.items ?? [];
      const runs = runsRes.items ?? [];
      const telegramItems = telegramItemsRes.items ?? [];
      const todayFilter = (value?: string | null) => getDatePart(value) === today;
      const recentFilter = (value?: string | null) => getDatePart(value) >= from30 && getDatePart(value) <= today;
      const todaysRuns = runs.filter((run) => todayFilter(run.started_at || run.created_at));
      const runIssuesBySource = todaysRuns.reduce<Record<SourceKey, number>>(
        (acc, run) => {
          const source = inferSourceFromRun(run);
          if (!source) return acc;
          if (run.status === "failed" || run.status === "partial") acc[source] += 1;
          return acc;
        },
        { news: 0, disclosure: 0, youtube: 0, telegram: 0 },
      );

      const newsFeed: FeedItem[] = newsItems
        .filter((item: NewsItem) => recentFilter(item.collected_at || item.created_at))
        .map((item: NewsItem) => {
          const status = item.ai_summary_error ? "failed" : item.ai_processed_at && item.ai_summary ? "summarized" : "pending";
          const keywords = uniqueCompact([...splitKeywords(item.ai_tags), ...splitKeywords(item.title).slice(0, 2)], 6);
          return {
            id: `news-${item.id}`,
            source: "news",
            title: item.title || "제목 없음",
            collected_at: item.collected_at || item.created_at,
            ai_status: status,
            status_group: inferStatusGroup(status),
            related_stock: item.stock_name || item.stock_code || null,
            keywords,
            summary_text: item.ai_summary || item.summary,
            original_url: item.url,
            target_url: SOURCE_ROUTE.news,
          };
        });

      const disclosureFeed: FeedItem[] = disclosures
        .filter((item: Disclosure) => recentFilter(item.created_at || item.disclosed_at))
        .map((item: Disclosure) => {
          const status = item.ai_summary_error ? "failed" : item.ai_processed_at && item.ai_summary ? "summarized" : "pending";
          const keywords = uniqueCompact([item.ai_event_type, ...splitKeywords(item.ai_tags), ...splitKeywords(item.disclosure_title).slice(0, 2)], 6);
          return {
            id: `disclosure-${item.id}`,
            source: "disclosure",
            title: item.disclosure_title || "공시 제목 없음",
            collected_at: item.created_at || item.disclosed_at || "",
            ai_status: status,
            status_group: inferStatusGroup(status),
            related_stock: item.stock_name || item.stock_code || null,
            keywords,
            summary_text: item.ai_summary || item.summary,
            original_url: item.url,
            target_url: SOURCE_ROUTE.disclosure,
          };
        });

      const youtubeFeed: FeedItem[] = videos
        .filter((item: BriefingVideo) => recentFilter(item.created_at || item.updated_at || item.published_at))
        .map((item: BriefingVideo) => {
          const status = item.analysis_status || "pending";
          return {
            id: `youtube-${item.id}`,
            source: "youtube",
            title: item.title || "영상 제목 없음",
            collected_at: item.updated_at || item.created_at || item.published_at || "",
            ai_status: status,
            status_group: inferStatusGroup(status),
            related_stock: item.channel_name,
            keywords: uniqueCompact(splitKeywords(item.title).slice(0, 5), 5),
            summary_text: item.description_summary,
            original_url: item.video_url,
            target_url: SOURCE_ROUTE.youtube,
          };
        });

      const telegramFeed: FeedItem[] = telegramItems.map((item: TelegramItem) => ({
        id: `telegram-${item.id}`,
        source: "telegram",
        title: item.item_title || item.message_text || "메시지 제목 없음",
        collected_at: item.updated_at || item.message_date,
        ai_status: item.summary_status,
        status_group: inferStatusGroup(item.summary_status),
        related_stock: item.related_stock_name || item.related_stock_code || null,
        keywords: uniqueCompact([item.tag, item.event_type, item.related_theme, ...splitKeywords(item.item_title || item.message_text).slice(0, 2)], 6),
        summary_text: item.summary_text,
        original_url: item.item_url || item.normalized_url,
        target_url: SOURCE_ROUTE.telegram,
      }));

      const allFeed = [...newsFeed, ...disclosureFeed, ...youtubeFeed, ...telegramFeed].sort((a, b) =>
        a.collected_at < b.collected_at ? 1 : -1,
      );
      const feedBySource: Record<SourceKey, FeedItem[]> = {
        news: newsFeed.filter((item) => getDatePart(item.collected_at) === today).sort((a, b) => (a.collected_at < b.collected_at ? 1 : -1)),
        disclosure: disclosureFeed.filter((item) => getDatePart(item.collected_at) === today).sort((a, b) => (a.collected_at < b.collected_at ? 1 : -1)),
        youtube: youtubeFeed.filter((item) => getDatePart(item.collected_at) === today).sort((a, b) => (a.collected_at < b.collected_at ? 1 : -1)),
        telegram: telegramFeed.filter((item) => getDatePart(item.collected_at) === today).sort((a, b) => (a.collected_at < b.collected_at ? 1 : -1)),
      };

      const sourceSummaries = (Object.keys(SOURCE_LABEL) as SourceKey[]).map((source) => {
        const items = feedBySource[source];
        const summarized = items.filter((item) => item.status_group === "summarized").length;
        const pending = items.filter((item) => item.status_group === "pending").length;
        const failed = items.filter((item) => item.status_group === "issue").length + runIssuesBySource[source];
        const status: SourceStatus = items.length === 0 ? "idle" : failed > 0 || pending > 0 ? "warning" : "normal";
        return {
          source,
          label: SOURCE_LABEL[source],
          collected_count: items.length,
          summarized_count: summarized,
          pending_count: pending,
          failed_count: failed,
          last_collected_at: maxDate(items.map((item) => item.collected_at)),
          status,
          top_keywords: getTopKeywords(items, 3),
        };
      });

      const weeklyCalendar = Array.from({ length: 7 }, (_, idx) => {
        const date = shiftDate(today, idx - 6);
        return {
          date,
          news_count: newsFeed.filter((item) => getDatePart(item.collected_at) === date).length,
          disclosure_count: disclosureFeed.filter((item) => getDatePart(item.collected_at) === date).length,
          youtube_count: youtubeFeed.filter((item) => getDatePart(item.collected_at) === date).length,
          telegram_count: telegramFeed.filter((item) => getDatePart(item.collected_at) === date).length,
          failed_count: runs.filter((run) => getDatePart(run.started_at || run.created_at) === date && (run.status === "failed" || run.status === "partial")).length,
        };
      });

      const issueKeywords = buildKeywordIssues(allFeed.filter((item) => getDatePart(item.collected_at) === today), false, 8);
      const crossKeywords = buildKeywordIssues(allFeed.filter((item) => getDatePart(item.collected_at) === today), true, 8);
      const themeTreemap = buildThemeReturnTreemapItems(themeReturnResponse, treemapViewMode);
      const reviews = recentReviews.items ?? [];
      const completedReviews = reviews.filter((item: TradeReviewListItem) => item.review_status === "복기완료");
      const trainingStatus: TrainingStatus = {
        total_trades: reviewSummary.total_trades,
        reviewed_count: reviewSummary.reviewed_count,
        unreviewed_count: reviewSummary.unreviewed_count,
        review_rate: reviewSummary.review_rate,
        recent_completed: completedReviews.length,
        recent_return_rate:
          reviews.length > 0
            ? reviews.reduce((sum: number, item: TradeReviewListItem) => sum + (item.profit_rate ?? 0), 0) / reviews.length
            : null,
        discipline_score: null,
        gpt_review_ready_count: reviews.filter((item: TradeReviewListItem) => item.review_status !== "복기완료").length,
        next_training_goal: reviewSummary.unreviewed_count > 0 ? "미복기 거래를 먼저 정리" : "최근 복기 기준 유지",
      };

      const attentionItems: AttentionItem[] = [
        ...sourceSummaries
          .filter((summary) => summary.pending_count > 0)
          .map((summary) => ({
            id: `${summary.source}-pending`,
            label: `${summary.label} 요약대기`,
            detail: `${summary.pending_count}건의 요약 상태 확인이 필요합니다.`,
            tone: "amber" as const,
            target_url: SOURCE_ROUTE[summary.source],
          })),
        ...sourceSummaries
          .filter((summary) => summary.failed_count > 0)
          .map((summary) => ({
            id: `${summary.source}-issue`,
            label: `${summary.label} 오류·스킵`,
            detail: `${summary.failed_count}건의 처리 이력을 확인하세요.`,
            tone: "rose" as const,
            target_url: SOURCE_ROUTE[summary.source],
          })),
        ...sourceSummaries
          .filter((summary) => summary.collected_count === 0)
          .map((summary) => ({
            id: `${summary.source}-empty`,
            label: `${summary.label} 미수집`,
            detail: "오늘 기준 수집 데이터가 없습니다.",
            tone: "slate" as const,
            target_url: SOURCE_ROUTE[summary.source],
          })),
        ...(trainingStatus.unreviewed_count > 0
          ? [
              {
                id: "training-review",
                label: "최근 복기 미완료",
                detail: `${trainingStatus.unreviewed_count}건의 매매 복기가 남아 있습니다.`,
                tone: "blue" as const,
                target_url: "/trade-reviews",
              },
            ]
          : []),
      ].slice(0, 8);

      setDashboard({
        today,
        source_summaries: sourceSummaries,
        weekly_calendar: weeklyCalendar,
        feed_by_source: feedBySource,
        issue_keywords: issueKeywords,
        cross_keywords: crossKeywords,
        theme_treemap: themeTreemap,
        training_status: trainingStatus,
        attention_items: attentionItems,
      });
    } catch (error) {
      console.error("[Dashboard] load failed", error);
      setErrorMessage("대시보드 데이터를 불러오지 못했습니다.");
    } finally {
      setIsLoading(false);
    }
  }, [treemapViewMode]);

  useEffect(() => {
    void loadDashboard();
  }, [loadDashboard]);

  useEffect(() => {
    if (!detailSource) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") setDetailSource(null);
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [detailSource]);

  useEffect(() => {
    if (!isDollarIndexHelpOpen) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") setIsDollarIndexHelpOpen(false);
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [isDollarIndexHelpOpen]);

  const summaryCards = dashboard?.source_summaries ?? [];
  const detailSummary = detailSource ? summaryCards.find((item) => item.source === detailSource) : null;
  const detailItems = detailSource ? dashboard?.feed_by_source[detailSource] ?? [] : [];
  const filteredDetailItems = detailItems.filter((item) => detailFilter === "all" || item.status_group === detailFilter);
  const themeItems = dashboard?.theme_treemap ?? [];
  const selectedTheme = themeItems.find((item) => item.marketThemeId === selectedThemeId) ?? themeItems[0] ?? null;
  const themePeriodStart = subtractOneMonth(dashboard?.today ?? todayInKst());
  const themePeriodEnd = dashboard?.today ?? todayInKst();
  const maxThemeScore = Math.max(...themeItems.map((item) => item.sizeValue), 1);
  const themeTreemapRects = useMemo(
    () => buildTreemapLayout(themeItems.map((item) => ({ id: `${item.viewMode}-${item.marketThemeId}`, value: item.sizeValue }))),
    [themeItems],
  );
  const themeTreemapRectMap = useMemo(
    () => new Map(themeTreemapRects.map((rect) => [rect.id, rect])),
    [themeTreemapRects],
  );
  const topThemeSummary = themeItems.length
    ? `최근 1개월 누적 등락률 변동폭 상위 테마는 ${themeItems
        .slice(0, 3)
        .map((item) => `${item.themeName} ${formatSignedPct(item.returnSum)}`)
        .join(", ")}입니다.`
    : "최근 1개월 테마등락률 데이터가 부족하여 요약을 생성하지 않았습니다.";

  return (
    <div className="space-y-4">
      <PageHeader
        title="DrCT 대시보드"
        description="수집 정보, 테마 흐름, 복기 상태를 한눈에 확인합니다."
        action={(
          <div className="flex flex-wrap items-center justify-end gap-2">
            <span className="rounded-full border border-slate-200 px-3 py-1 text-xs text-slate-500">{dataSourceLabel.toUpperCase()}</span>
            <StatusBadge label={`기준일 ${dashboard?.today ?? todayInKst()}`} tone="slate" />
            <button type="button" className="btn btn-secondary transition-all duration-150 active:scale-[0.98]" onClick={() => void loadDashboard()} disabled={isLoading}>
              {isLoading ? "새로고침 중..." : "새로고침"}
            </button>
          </div>
        )}
      />

      {errorMessage ? (
        <SectionCard title="오류">
          <p className="text-sm text-rose-600">{errorMessage}</p>
        </SectionCard>
      ) : null}

      <SectionCard title="주요 지표 흐름">
        <div className="dashboard-indicator-panel">
          <div className="dashboard-indicator-header">
            <p>국내지수, 해외증시, 환율·원자재 흐름을 네이버 차트 기준으로 빠르게 확인합니다.</p>
          </div>
          <div className="dashboard-indicator-grid">
            {dashboardIndicators.map((indicator) => (
              <article key={indicator.title} className="dashboard-indicator-card">
                <div className="dashboard-indicator-card-title">
                  <div>
                    <strong>{indicator.title}</strong>
                    <span>{indicator.category}</span>
                  </div>
                  {indicator.helpType === "dollar-index" ? (
                    <button
                      type="button"
                      className="dashboard-indicator-help-button"
                      aria-label="달러 인덱스 설명 보기"
                      onClick={() => setIsDollarIndexHelpOpen(true)}
                    >
                      ?
                    </button>
                  ) : null}
                </div>
                <img
                  src={indicator.imageUrl}
                  alt={`${indicator.title} 흐름 차트`}
                  className="dashboard-indicator-chart"
                  loading="lazy"
                />
              </article>
            ))}
          </div>
        </div>
      </SectionCard>

      <SectionCard title="최근 1개월 테마등락률 트리맵">
        <div className="mb-4 flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
          <p className="text-sm text-slate-600">최근 1개월 동안 저장된 테마등락률을 합산하여, 테마별 상승·하락 강도를 면적으로 표현합니다.</p>
          <div className="dashboard-treemap-toolbar">
            <div className="dashboard-treemap-view-toggle" aria-label="트리맵 표시 기준">
              <button
                type="button"
                className={`dashboard-treemap-toggle-button ${treemapViewMode === "THEME_GROUP" ? "active" : ""}`}
                onClick={() => {
                  setSelectedThemeId(null);
                  setTreemapViewMode("THEME_GROUP");
                }}
              >
                테마그룹 기준
              </button>
              <button
                type="button"
                className={`dashboard-treemap-toggle-button ${treemapViewMode === "THEME" ? "active" : ""}`}
                onClick={() => {
                  setSelectedThemeId(null);
                  setTreemapViewMode("THEME");
                }}
              >
                테마 기준
              </button>
            </div>
            <StatusBadge label={`기간 ${themePeriodStart} ~ ${themePeriodEnd}`} tone="slate" />
          </div>
        </div>
        {!themeItems.length ? (
          <div className="rounded-lg border border-dashed border-slate-300 bg-slate-50 p-4">
            <p className="text-sm font-semibold text-slate-700">최근 1개월 기준으로 집계된 테마등락률 데이터가 없습니다.</p>
            <p className="mt-1 text-sm text-slate-500">시장테마관리에서 테마등락률 갱신 후 다시 확인해 주세요.</p>
          </div>
        ) : (
          <div className="space-y-4">
            <p className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-700">{topThemeSummary}</p>
            <div className="dashboard-return-legend" aria-label="테마등락률 색상 기준">
              {DASHBOARD_RETURN_LEGEND.map((item) => (
                <span key={item.label} className="dashboard-return-legend-item">
                  <span className="dashboard-return-legend-swatch" style={{ background: item.color }} />
                  {item.label}
                </span>
              ))}
            </div>
            <div className="theme-treemap dashboard-theme-treemap-frame" onMouseLeave={() => setTreemapTooltip(null)}>
              {themeItems.map((item) => {
                const rect = themeTreemapRectMap.get(`${item.viewMode}-${item.marketThemeId}`);
                const sizeClass = getThemeTreemapSizeClass(item, maxThemeScore);
                const textMetrics = getTreemapTextMetrics(rect, item.themeName, { variant: "dashboard" });
                const labelClass = getTreemapLabelClass(rect, item.themeName, { variant: "dashboard" });
                const intensity = Math.max(0.22, Math.min(1, item.sizeValue / maxThemeScore));
                const style = {
                  "--theme-intensity": intensity,
                  "--tile-title-size": `${textMetrics.titleFontSize}px`,
                  "--tile-title-lines": textMetrics.titleLineClamp,
                  "--return-color": getDashboardThemeReturnTreemapColor(item.returnSum),
                  left: `calc(${rect?.x ?? 0}% + 2px)`,
                  top: `calc(${rect?.y ?? 0}% + 2px)`,
                  width: `calc(${rect?.width ?? 0}% - 4px)`,
                  height: `calc(${rect?.height ?? 0}% - 4px)`,
                } as CSSProperties;
                return (
                  <button
                    key={`${item.viewMode}-${item.marketThemeId}`}
                    type="button"
                    title={`${item.themeName} · 기간 ${themePeriodStart} ~ ${themePeriodEnd} · 합산 등락률 ${formatSignedPct(item.returnSum)} · 거래대금 ${formatEok(item.tradingValue100m)}`}
                    className={`theme-treemap-tile dashboard-return-treemap-tile ${getDashboardThemeReturnTreemapToneClass(item.returnSum)} ${sizeClass} ${labelClass} ${selectedTheme?.marketThemeId === item.marketThemeId ? "selected" : ""}`}
                    style={style}
                    onClick={() => setSelectedThemeId(item.marketThemeId)}
                    onMouseMove={(event) => setTreemapTooltip({ x: event.clientX, y: event.clientY, item })}
                    onFocus={(event) => {
                      const box = event.currentTarget.getBoundingClientRect();
                      setTreemapTooltip({ x: box.left + box.width / 2, y: box.top + 12, item });
                    }}
                    onBlur={() => setTreemapTooltip(null)}
                  >
                    <span className="theme-treemap-title">{item.themeName}</span>
                    {item.viewMode === "THEME_GROUP" && item.topChildThemes.length ? (
                      <span className="theme-treemap-subthemes">{item.topChildThemes.join(" · ")}</span>
                    ) : item.viewMode === "THEME" && item.themeGroupName ? (
                      <span className="theme-treemap-subthemes">{item.themeGroupName}</span>
                    ) : null}
                    <span className="theme-treemap-stock-count">{formatSignedPct(item.returnSum)} · {formatEok(item.tradingValue100m)}</span>
                  </button>
                );
              })}
              {treemapTooltip ? (
                <div
                  className="theme-treemap-tooltip"
                  style={{
                    left: Math.max(8, Math.min(treemapTooltip.x + 14, (typeof window === "undefined" ? 1440 : window.innerWidth) - 340)),
                    top: Math.max(8, Math.min(treemapTooltip.y + 14, (typeof window === "undefined" ? 900 : window.innerHeight) - 220)),
                  }}
                >
                  <strong>{treemapTooltip.item.themeName}</strong>
                  <dl>
                    <div><dt>기간</dt><dd>{themePeriodStart} ~ {themePeriodEnd}</dd></div>
                    <div><dt>합산 등락률</dt><dd>{formatSignedPct(treemapTooltip.item.returnSum)}</dd></div>
                    <div><dt>거래대금</dt><dd>{formatEok(treemapTooltip.item.tradingValue100m)}</dd></div>
                    <div><dt>상승/하락/보합</dt><dd>{treemapTooltip.item.risingDays}일 / {treemapTooltip.item.fallingDays}일 / {treemapTooltip.item.flatDays}일</dd></div>
                    <div><dt>데이터</dt><dd>{treemapTooltip.item.dataDays}일 · {treemapTooltip.item.stockCount}종목</dd></div>
                  </dl>
                </div>
              ) : null}
            </div>

            {selectedTheme ? (
              <div className="theme-detail-panel">
                <div className="theme-detail-header">
                  <div>
                    <h3 className="theme-detail-title">{selectedTheme.themeName} 상세</h3>
                    <p className="theme-detail-period">기간 {themePeriodStart} ~ {themePeriodEnd}</p>
                  </div>
                  <div className="theme-detail-actions">
                    <StatusBadge label={`${selectedTheme.rank}위`} tone="blue" />
                    <button type="button" className="btn btn-secondary theme-detail-link-btn" onClick={() => navigate("/market-themes")}>시장테마관리로 이동</button>
                  </div>
                </div>
                <div className="theme-detail-kpis">
                  <div className="theme-detail-kpi">
                    <p className="theme-detail-kpi-label">합산 등락률</p>
                    <p className="theme-detail-kpi-value">{formatSignedPct(selectedTheme.returnSum)}</p>
                  </div>
                  <div className="theme-detail-kpi">
                    <p className="theme-detail-kpi-label">종목수</p>
                    <p className="theme-detail-kpi-value">{selectedTheme.stockCount}종목</p>
                  </div>
                  <div className="theme-detail-kpi">
                    <p className="theme-detail-kpi-label">거래대금</p>
                    <p className="theme-detail-kpi-value">{formatEok(selectedTheme.tradingValue100m)}</p>
                  </div>
                  <div className="theme-detail-kpi">
                    <p className="theme-detail-kpi-label">데이터 일수</p>
                    <p className="theme-detail-kpi-value">{selectedTheme.dataDays}일</p>
                  </div>
                </div>
                <div className="theme-detail-info-row">
                  <div className="theme-detail-info-box">
                    <span className="theme-detail-info-label">등락 일수</span>
                    <span className="theme-detail-info-value">
                      상승 {selectedTheme.risingDays}일 · 하락 {selectedTheme.fallingDays}일 · 보합 {selectedTheme.flatDays}일
                    </span>
                  </div>
                  <div className="theme-detail-info-box">
                    <span className="theme-detail-info-label">조회 성공 종목</span>
                    <span className="theme-detail-info-value">{selectedTheme.successStockCount || selectedTheme.stockCount}종목</span>
                  </div>
                </div>
                <div className="theme-detail-context-row">
                  {selectedTheme.viewMode === "THEME_GROUP" ? (
                    <div className="theme-detail-context-box">
                      <span className="theme-detail-info-label">하위 테마</span>
                      <span className="theme-detail-info-value">
                        {selectedTheme.topChildThemes.length ? selectedTheme.topChildThemes.join(", ") : "하위 테마 정보 없음"}
                        {selectedTheme.childThemeCount > selectedTheme.topChildThemes.length ? ` 외 ${selectedTheme.childThemeCount - selectedTheme.topChildThemes.length}개` : ""}
                      </span>
                    </div>
                  ) : (
                    <div className="theme-detail-context-box">
                      <span className="theme-detail-info-label">테마그룹</span>
                      <span className="theme-detail-info-value">{selectedTheme.themeGroupName || "미지정 테마그룹"}</span>
                    </div>
                  )}
                </div>
                <p className="theme-score-note">
                  <b>면적 기준:</b> 최근 1개월 테마등락률 합산값의 절댓값입니다. 색상은 실제 합산 등락률 기준이며, 상승은 빨간 계열, 하락은 파란 계열로 표시합니다.
                </p>
              </div>
            ) : null}
          </div>
        )}
      </SectionCard>

      {isDollarIndexHelpOpen ? (
        <div className="dashboard-indicator-modal" role="presentation" onClick={() => setIsDollarIndexHelpOpen(false)}>
          <div
            className="dashboard-indicator-modal-panel"
            role="dialog"
            aria-modal="true"
            aria-labelledby="dollar-index-help-title"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="dashboard-indicator-modal-header">
              <div>
                <h3 id="dollar-index-help-title">달러 인덱스 설명</h3>
                <p>네이버 블로그 자료를 참고해 달러 인덱스 의미와 흐름을 확인합니다.</p>
              </div>
              <button type="button" className="btn btn-secondary" onClick={() => setIsDollarIndexHelpOpen(false)}>
                닫기
              </button>
            </div>
            <iframe
              title="달러 인덱스 설명"
              src={DOLLAR_INDEX_HELP_URL}
              className="dashboard-indicator-modal-frame"
            />
            <a className="dashboard-indicator-modal-link" href={DOLLAR_INDEX_HELP_URL} target="_blank" rel="noreferrer">
              새 창에서 보기
            </a>
          </div>
        </div>
      ) : null}

      <SectionCard title="오늘 소스별 수집 현황">
        {summaryCards.length === 0 ? (
          <p className="text-sm text-slate-500">오늘 수집된 데이터가 없습니다.</p>
        ) : (
          <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-4">
            {summaryCards.map((item) => (
              <button
                key={item.source}
                type="button"
                className="rounded-lg border border-slate-200 bg-white p-4 text-left transition-colors hover:bg-slate-50"
                onClick={() => {
                  setDetailSource(item.source);
                  setDetailFilter("all");
                }}
              >
                <div className="mb-3 flex items-center justify-between">
                  <h3 className="text-base font-semibold text-slate-900">{item.label}</h3>
                  <StatusBadge label={statusLabel(item.status)} tone={toneByStatus(item.status)} />
                </div>
                <div className="grid grid-cols-2 gap-2 text-xs text-slate-600">
                  <span>수집 {item.collected_count}건</span>
                  <span>요약완료 {item.summarized_count}건</span>
                  <span>요약대기 {item.pending_count}건</span>
                  <span>오류·스킵 {item.failed_count}건</span>
                </div>
                <p className="mt-3 text-xs text-slate-500">마지막 수집: {formatDateTime(item.last_collected_at)}</p>
                <div className="mt-3 flex min-h-[24px] flex-wrap gap-1">
                  {item.top_keywords.length ? (
                    item.top_keywords.map((keyword) => <StatusBadge key={`${item.source}-${keyword}`} label={keyword} tone={sourceTone(item.source)} />)
                  ) : (
                    <span className="text-xs text-slate-400">추출 키워드 없음</span>
                  )}
                </div>
                <span className="mt-3 inline-flex text-sm font-semibold text-blue-700">상세 보기</span>
              </button>
            ))}
          </div>
        )}
      </SectionCard>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-3">
        <SectionCard title="오늘 추출 이슈·키워드" className="xl:col-span-2">
          {!dashboard?.issue_keywords.length ? (
            <p className="text-sm text-slate-500">오늘 추출된 키워드가 없습니다.</p>
          ) : (
            <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
              {dashboard.issue_keywords.map((row) => (
                <div key={row.keyword} className="rounded-lg border border-slate-200 bg-white p-3">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <p className="text-sm font-semibold text-slate-950">{row.keyword}</p>
                      <p className="mt-1 line-clamp-1 text-xs text-slate-500">{row.recent_title}</p>
                    </div>
                    <StatusBadge label={`${row.total}건`} tone="blue" />
                  </div>
                  <div className="mt-3 flex flex-wrap gap-1">
                    {(Object.keys(SOURCE_LABEL) as SourceKey[]).map((src) =>
                      row.sourceCounts[src] ? <StatusBadge key={`${row.keyword}-${src}`} label={`${SOURCE_LABEL[src]} ${row.sourceCounts[src]}`} tone={sourceTone(src)} /> : null,
                    )}
                  </div>
                  <p className="mt-2 text-xs text-slate-600">
                    요약완료 {row.summarized_count}건 · 요약대기 {row.pending_count}건
                  </p>
                  <p className="mt-1 text-xs text-slate-500">관련 종목: {row.relatedStocks.length ? row.relatedStocks.join(", ") : "-"}</p>
                </div>
              ))}
            </div>
          )}
        </SectionCard>

        <SectionCard title="소스 교차 등장 키워드">
          {!dashboard?.cross_keywords.length ? (
            <p className="text-sm text-slate-500">오늘 2개 이상 소스에서 반복된 키워드가 없습니다.</p>
          ) : (
            <div className="space-y-3">
              {dashboard.cross_keywords.map((row) => {
                const max = Math.max(...dashboard.cross_keywords.map((x) => x.total), 1);
                const width = Math.max(12, Math.round((row.total / max) * 100));
                return (
                  <div key={row.keyword} className="space-y-1">
                    <div className="flex items-center justify-between">
                      <p className="text-sm font-semibold text-slate-900">{row.keyword}</p>
                      <span className="text-xs text-slate-500">총 {row.total}건</span>
                    </div>
                    <div className="h-2 w-full rounded bg-slate-100">
                      <div className="h-2 rounded bg-slate-700" style={{ width: `${width}%` }} />
                    </div>
                    <div className="flex flex-wrap gap-1 text-[11px]">
                      {(Object.keys(SOURCE_LABEL) as SourceKey[]).map((src) =>
                        row.sourceCounts[src] ? <StatusBadge key={`${row.keyword}-${src}`} label={`${SOURCE_LABEL[src]} ${row.sourceCounts[src]}`} tone={sourceTone(src)} /> : null,
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </SectionCard>
      </div>


      <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
        <SectionCard title="매매훈련 현황">
          {!dashboard?.training_status.total_trades ? (
            <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
              <p className="text-sm text-slate-500">최근 30일 기준 매매 복기 데이터가 없습니다.</p>
              <button type="button" className="btn btn-primary" onClick={() => navigate("/trading/training")}>매매훈련 시작하기</button>
            </div>
          ) : (
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
                <div className="rounded-lg border border-slate-200 p-3">
                  <p className="text-xs text-slate-500">최근 거래</p>
                  <p className="mt-1 text-xl font-bold text-slate-950">{dashboard.training_status.total_trades}건</p>
                </div>
                <div className="rounded-lg border border-slate-200 p-3">
                  <p className="text-xs text-slate-500">최근 완료</p>
                  <p className="mt-1 text-xl font-bold text-slate-950">{dashboard.training_status.recent_completed}건</p>
                </div>
                <div className="rounded-lg border border-slate-200 p-3">
                  <p className="text-xs text-slate-500">최근 수익률</p>
                  <p className="mt-1 text-xl font-bold text-slate-950">
                    {dashboard.training_status.recent_return_rate == null ? "-" : `${dashboard.training_status.recent_return_rate.toFixed(2)}%`}
                  </p>
                </div>
                <div className="rounded-lg border border-slate-200 p-3">
                  <p className="text-xs text-slate-500">GPT 복기 상태</p>
                  <p className="mt-1 text-xl font-bold text-slate-950">{dashboard.training_status.gpt_review_ready_count}건</p>
                </div>
              </div>
              <div className="rounded-lg border border-slate-200 bg-slate-50 p-3">
                <p className="text-xs font-semibold text-slate-500">다음 훈련 목표</p>
                <p className="mt-1 text-sm text-slate-800">{dashboard.training_status.next_training_goal}</p>
              </div>
              <div className="flex flex-wrap gap-2">
                <button type="button" className="btn btn-primary" onClick={() => navigate("/trading/training")}>훈련 이어가기</button>
                <button type="button" className="btn btn-secondary" onClick={() => navigate("/trade-reviews")}>최근 복기 보기</button>
              </div>
            </div>
          )}
        </SectionCard>

        <SectionCard title="오늘 확인 필요">
          {!dashboard?.attention_items.length ? (
            <p className="text-sm text-slate-500">오늘 바로 확인할 항목이 없습니다.</p>
          ) : (
            <div className="space-y-2">
              {dashboard.attention_items.map((item) => (
                <button key={item.id} type="button" className="flex w-full items-center justify-between gap-3 rounded-lg border border-slate-200 px-3 py-2 text-left hover:bg-slate-50" onClick={() => navigate(item.target_url)}>
                  <div>
                    <p className="text-sm font-semibold text-slate-900">{item.label}</p>
                    <p className="text-xs text-slate-500">{item.detail}</p>
                  </div>
                  <StatusBadge label="확인" tone={item.tone} />
                </button>
              ))}
            </div>
          )}
        </SectionCard>
      </div>

      <SectionCard title="최근 7일 수집 캘린더">
        {!dashboard?.weekly_calendar.length ? (
          <p className="text-sm text-slate-500">최근 7일 수집 이력이 없습니다.</p>
        ) : (
          <div className="grid grid-cols-1 gap-2 md:grid-cols-2 xl:grid-cols-7">
            {dashboard.weekly_calendar.map((day) => (
              <button type="button" key={day.date} onClick={() => navigate("/collection-runs")} className="rounded-lg border border-slate-200 bg-slate-50 p-3 text-left transition-colors hover:bg-white">
                <div className="text-xs font-semibold text-slate-800">{day.date}</div>
                <div className="mt-2 flex flex-wrap gap-1 text-[11px]">
                  <StatusBadge label={`뉴스 ${day.news_count}`} tone="blue" />
                  <StatusBadge label={`공시 ${day.disclosure_count}`} tone="slate" />
                  <StatusBadge label={`유튜브 ${day.youtube_count}`} tone="amber" />
                  <StatusBadge label={`텔레그램 ${day.telegram_count}`} tone="emerald" />
                  {day.failed_count > 0 ? <StatusBadge label={`확인 ${day.failed_count}`} tone="rose" /> : null}
                </div>
              </button>
            ))}
          </div>
        )}
      </SectionCard>

      {detailSource && detailSummary ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 px-4 py-6" onClick={() => setDetailSource(null)}>
          <div className="max-h-[88vh] w-full max-w-4xl overflow-hidden rounded-xl bg-white shadow-xl" onClick={(event) => event.stopPropagation()}>
            <div className="flex items-start justify-between gap-3 border-b border-slate-200 px-5 py-4">
              <div>
                <h2 className="text-lg font-bold text-slate-950">{detailSummary.label} 수집 상세</h2>
                <p className="mt-1 text-sm text-slate-500">기준일 {dashboard?.today} · 수집 {detailSummary.collected_count}건 · 요약완료 {detailSummary.summarized_count}건 · 확인 필요 {detailSummary.pending_count + detailSummary.failed_count}건</p>
              </div>
              <button type="button" className="rounded-lg border border-slate-200 px-3 py-1 text-sm font-semibold text-slate-700 hover:bg-slate-50" onClick={() => setDetailSource(null)}>닫기</button>
            </div>
            <div className="border-b border-slate-200 px-5 pt-3">
              <div className="flex flex-wrap gap-2">
                {DETAIL_TABS.map((tab) => (
                  <button
                    key={tab.key}
                    type="button"
                    className={`rounded-full border px-3 py-1 text-sm font-semibold ${detailFilter === tab.key ? "border-blue-600 bg-blue-50 text-blue-700" : "border-slate-200 text-slate-600 hover:bg-slate-50"}`}
                    onClick={() => setDetailFilter(tab.key)}
                  >
                    {tab.label}
                  </button>
                ))}
                <button type="button" className="ml-auto rounded-full border border-slate-200 px-3 py-1 text-sm font-semibold text-slate-700 hover:bg-slate-50" onClick={() => navigate(SOURCE_ROUTE[detailSource])}>관리 화면으로 이동</button>
              </div>
            </div>
            <div className="max-h-[58vh] overflow-y-auto px-5 py-4">
              {!filteredDetailItems.length ? (
                <p className="text-sm text-slate-500">해당 조건의 수집 항목이 없습니다.</p>
              ) : (
                <div className="space-y-2">
                  {filteredDetailItems.map((item) => (
                    <div key={item.id} className="rounded-lg border border-slate-200 p-3">
                      <div className="flex flex-wrap items-center gap-2">
                        <StatusBadge label={SOURCE_LABEL[item.source]} tone={sourceTone(item.source)} />
                        <StatusBadge label={summarizeStatusLabel(item.ai_status)} tone={item.status_group === "summarized" ? "emerald" : item.status_group === "issue" ? "rose" : "amber"} />
                        <span className="text-xs text-slate-500">{formatDateTime(item.collected_at)}</span>
                        {item.related_stock ? <span className="text-xs text-slate-500">· {item.related_stock}</span> : null}
                      </div>
                      <p className="mt-2 text-sm font-semibold text-slate-950">{item.title}</p>
                      {item.summary_text ? <p className="mt-1 line-clamp-2 text-xs text-slate-600">{item.summary_text}</p> : null}
                      <div className="mt-2 flex flex-wrap gap-1">
                        {item.keywords.map((keyword) => <StatusBadge key={`${item.id}-${keyword}`} label={keyword} tone={sourceTone(item.source)} />)}
                      </div>
                      <div className="mt-3 flex flex-wrap gap-2">
                        {item.original_url ? (
                          <a href={item.original_url} target="_blank" rel="noreferrer" className="text-sm font-semibold text-blue-700 hover:underline">원문/상세 링크</a>
                        ) : null}
                        <button type="button" className="text-sm font-semibold text-slate-700 hover:underline" onClick={() => navigate(item.target_url)}>관리 화면</button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}

export default DashboardPage;
