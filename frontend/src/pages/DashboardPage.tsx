import { useCallback, useEffect, useState } from "react";
import type { CSSProperties } from "react";
import { useNavigate } from "react-router-dom";
import PageHeader from "@/components/common/PageHeader";
import SectionCard from "@/components/common/SectionCard";
import StatusBadge from "@/components/common/StatusBadge";
import { dataSourceLabel, repositories } from "@/services";
import type { CollectionRun } from "@/types/collectionRun";
import type { Disclosure } from "@/types/disclosure";
import type { BriefingVideo } from "@/types/economicBriefing";
import type { MonthlyThemeFlowTrendResponse } from "@/types/marketTrend";
import type { NewsItem } from "@/types/news";
import type { TelegramItem } from "@/types/telegram";
import type { TradeReviewListItem } from "@/types/tradeReview";

type SourceKey = "news" | "disclosure" | "youtube" | "telegram";
type SourceStatus = "normal" | "warning" | "idle";
type DetailFilter = "all" | "summarized" | "pending" | "issue";
type ThemeFlowViewMode = "THEME_GROUP" | "THEME";

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
  scoreSum: number;
  stockCount: number;
  eventCount: number;
  relatedStocks: string[];
  rank: number;
  sourceDates: string[];
  latestDate: string | null;
  supplyValueSum: number;
  latestFinalRank: number | null;
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

const getMonthKey = (date: string) => date.slice(0, 7);

const getMonthKeysBetween = (startDate: string, endDate: string) => {
  const start = new Date(`${getMonthKey(startDate)}-01T00:00:00Z`);
  const end = new Date(`${getMonthKey(endDate)}-01T00:00:00Z`);
  const keys: string[] = [];
  const cursor = new Date(start);
  while (cursor <= end) {
    keys.push(`${cursor.getUTCFullYear()}-${String(cursor.getUTCMonth() + 1).padStart(2, "0")}`);
    cursor.setUTCMonth(cursor.getUTCMonth() + 1);
  }
  return keys;
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

const buildThemeSupplyTreemapItems = (
  monthlyResponses: MonthlyThemeFlowTrendResponse[],
  startDate: string,
  endDate: string,
  viewMode: ThemeFlowViewMode,
): ThemeTreemapItem[] => {
  const map = new Map<number, Omit<ThemeTreemapItem, "rank">>();
  monthlyResponses.forEach((response) => {
    (response.themes ?? []).forEach((theme) => {
      const current =
        map.get(theme.market_theme_id) ??
        {
          marketThemeId: theme.market_theme_id,
          themeName: theme.theme_name,
          viewMode,
          themeGroupId: theme.theme_group_id ?? null,
          themeGroupName: theme.theme_group_name ?? null,
          childThemeCount: theme.child_theme_count ?? 0,
          topChildThemes: theme.top_child_themes ?? [],
          scoreSum: 0,
          stockCount: 0,
          eventCount: 0,
          relatedStocks: theme.related_stocks ?? [],
          sourceDates: [],
          latestDate: null,
          supplyValueSum: 0,
          latestFinalRank: null,
        };
      current.viewMode = viewMode;
      current.themeGroupId = theme.theme_group_id ?? current.themeGroupId;
      current.themeGroupName = theme.theme_group_name ?? current.themeGroupName;
      current.childThemeCount = Math.max(current.childThemeCount, theme.child_theme_count ?? 0);
      current.topChildThemes = Array.from(new Set([...current.topChildThemes, ...(theme.top_child_themes ?? [])])).slice(0, 3);
      current.relatedStocks = Array.from(new Set([...current.relatedStocks, ...(theme.related_stocks ?? [])])).slice(0, 8);
      theme.series
        .filter((point) => point.trade_date >= startDate && point.trade_date <= endDate)
        .forEach((point) => {
          const dailyScore = Number(point.daily_score || 0);
          if (dailyScore <= 0) return;
          current.scoreSum += dailyScore;
          current.stockCount = Math.max(current.stockCount, Number(point.stock_count || 0));
          current.eventCount += Number(point.event_count || 0);
          current.supplyValueSum += Number(point.estimated_trading_value_sum || 0);
          current.sourceDates.push(point.trade_date);
          if (!current.latestDate || point.trade_date > current.latestDate) {
            current.latestDate = point.trade_date;
            current.latestFinalRank = point.final_rank;
          }
        });
      map.set(theme.market_theme_id, current);
    });
  });

  return Array.from(map.values())
    .filter((item) => item.scoreSum > 0)
    .sort((a, b) => b.scoreSum - a.scoreSum || a.themeName.localeCompare(b.themeName))
    .map((item, idx) => ({
      ...item,
      sourceDates: Array.from(new Set(item.sourceDates)).sort(),
      rank: idx + 1,
    }));
};

const getThemeTreemapSizeClass = (item: ThemeTreemapItem, maxScore: number) => {
  const ratio = maxScore > 0 ? item.scoreSum / maxScore : 0;
  if (item.rank === 1 || ratio >= 0.72) return "large";
  if (item.rank <= 5 || ratio >= 0.36) return "medium";
  return "small";
};

function DashboardPage() {
  const navigate = useNavigate();
  const [dashboard, setDashboard] = useState<DashboardData | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");
  const [detailSource, setDetailSource] = useState<SourceKey | null>(null);
  const [detailFilter, setDetailFilter] = useState<DetailFilter>("all");
  const [selectedThemeId, setSelectedThemeId] = useState<number | null>(null);
  const [treemapViewMode, setTreemapViewMode] = useState<ThemeFlowViewMode>("THEME_GROUP");

  const loadDashboard = useCallback(async () => {
    setIsLoading(true);
    setErrorMessage("");
    const today = todayInKst();
    const from30 = shiftDate(today, -29);
    const themePeriodStartDate = subtractOneMonth(today);
    const themeMonthKeys = getMonthKeysBetween(themePeriodStartDate, today);
    try {
      const [runsRes, newsItems, disclosures, videosRes, telegramItemsRes, reviewSummary, recentReviews, monthlyThemeFlowResponses] = await Promise.all([
        repositories.collectionRuns.listCollectionRuns({ limit: 500, offset: 0 }),
        repositories.news.listNews({ limit: 300, offset: 0 }),
        repositories.disclosures.listDisclosures({ limit: 300, offset: 0 }),
        repositories.economicBriefing.getBriefingVideos({ limit: 300 }),
        repositories.telegram.listItems({ date_from: from30, date_to: today, limit: 500, offset: 0 }),
        repositories.tradeReviews.fetchTradeReviewSummary({ from_date: from30, to_date: today }),
        repositories.tradeReviews.fetchTradeReviews({ from_date: from30, to_date: today, limit: 20, offset: 0 }),
        Promise.all(themeMonthKeys.map((month) => repositories.marketTrends.getExternalMonthlyThemeFlowTrend(month, { view_mode: treemapViewMode }))),
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
      const themeTreemap = buildThemeSupplyTreemapItems(monthlyThemeFlowResponses, themePeriodStartDate, today, treemapViewMode);
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

  const summaryCards = dashboard?.source_summaries ?? [];
  const todayCollected = summaryCards.reduce((sum, item) => sum + item.collected_count, 0);
  const summarizedCount = summaryCards.reduce((sum, item) => sum + item.summarized_count, 0);
  const attentionCount = summaryCards.reduce((sum, item) => sum + item.pending_count + item.failed_count, 0);
  const recentReviewCount = dashboard?.training_status.reviewed_count ?? 0;
  const detailSummary = detailSource ? summaryCards.find((item) => item.source === detailSource) : null;
  const detailItems = detailSource ? dashboard?.feed_by_source[detailSource] ?? [] : [];
  const filteredDetailItems = detailItems.filter((item) => detailFilter === "all" || item.status_group === detailFilter);
  const themeItems = dashboard?.theme_treemap ?? [];
  const selectedTheme = themeItems.find((item) => item.marketThemeId === selectedThemeId) ?? themeItems[0] ?? null;
  const themePeriodStart = subtractOneMonth(dashboard?.today ?? todayInKst());
  const themePeriodEnd = dashboard?.today ?? todayInKst();
  const maxThemeScore = Math.max(...themeItems.map((item) => item.scoreSum), 1);
  const topThemeSummary = themeItems.length
    ? `최근 1개월 기준 점수 합산 상위 테마는 ${themeItems
        .slice(0, 3)
        .map((item) => item.themeName)
        .join(", ")}입니다.`
    : "최근 1개월 테마 수급 점수 데이터가 부족하여 요약을 생성하지 않았습니다.";

  const kpiCards = [
    { label: "오늘 수집", value: `${todayCollected}건`, tone: "blue" as const, help: "4개 정보 소스 합산" },
    { label: "요약 완료", value: `${summarizedCount}건`, tone: "emerald" as const, help: "AI 요약 또는 분석 완료" },
    { label: "확인 필요", value: `${attentionCount}건`, tone: "amber" as const, help: "대기, 오류, 스킵 포함" },
    { label: "최근 복기", value: `${recentReviewCount}건`, tone: "slate" as const, help: "최근 30일 복기 완료" },
  ];

  return (
    <div className="space-y-4">
      <PageHeader
        title="DrCT 정보 파악 대시보드"
        description="수집된 투자 정보, 추출 키워드, 테마 흐름, 매매훈련 상태를 한눈에 확인합니다."
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

      <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-4">
        {kpiCards.map((card) => (
          <div key={card.label} className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
            <div className="mb-3 flex items-center justify-between">
              <p className="text-sm font-semibold text-slate-600">{card.label}</p>
              <StatusBadge label={card.help} tone={card.tone} />
            </div>
            <p className="text-3xl font-bold text-slate-950">{card.value}</p>
          </div>
        ))}
      </div>

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

      <SectionCard title="최근 1개월 테마 수급 트리맵">
        <div className="mb-4 flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
          <p className="text-sm text-slate-600">시장트렌드분석의 월간 테마 누적 흐름 점수를 최근 1개월 기준으로 합산하여, 테마별 수급 집중도를 면적으로 표현합니다.</p>
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
            <p className="text-sm font-semibold text-slate-700">최근 1개월 테마 수급 점수 데이터가 없습니다.</p>
            <p className="mt-1 text-sm text-slate-500">시장트렌드분석 데이터가 생성되면 테마 수급 트리맵이 표시됩니다.</p>
          </div>
        ) : (
          <div className="space-y-4">
            <p className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-700">{topThemeSummary}</p>
            <div className="theme-treemap">
              {themeItems.map((item, idx) => {
                const sizeClass = getThemeTreemapSizeClass(item, maxThemeScore);
                const intensity = Math.max(0.22, Math.min(1, item.scoreSum / maxThemeScore));
                return (
                  <button
                    key={item.marketThemeId}
                    type="button"
                    title={`${item.themeName} · 점수 합산 ${item.scoreSum}점 · ${item.stockCount}종목`}
                    className={`theme-treemap-tile ${sizeClass} ${selectedTheme?.marketThemeId === item.marketThemeId ? "selected" : ""}`}
                    style={{ "--theme-intensity": intensity } as CSSProperties}
                    onClick={() => setSelectedThemeId(item.marketThemeId)}
                  >
                    <span className="theme-treemap-title">{item.themeName}</span>
                    {item.viewMode === "THEME_GROUP" && item.topChildThemes.length ? (
                      <span className="theme-treemap-subthemes">{item.topChildThemes.join(" · ")}</span>
                    ) : item.viewMode === "THEME" && item.themeGroupName ? (
                      <span className="theme-treemap-subthemes">{item.themeGroupName}</span>
                    ) : null}
                    <span className="theme-treemap-stock-count">{item.stockCount}종목</span>
                  </button>
                );
              })}
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
                    <button type="button" className="btn btn-secondary theme-detail-link-btn" onClick={() => navigate("/market-trends")}>시장트렌드분석으로 이동</button>
                  </div>
                </div>
                <div className="theme-detail-kpis">
                  <div className="theme-detail-kpi">
                    <p className="theme-detail-kpi-label">점수 합산</p>
                    <p className="theme-detail-kpi-value">{selectedTheme.scoreSum}점</p>
                  </div>
                  <div className="theme-detail-kpi">
                    <p className="theme-detail-kpi-label">종목수</p>
                    <p className="theme-detail-kpi-value">{selectedTheme.stockCount}종목</p>
                  </div>
                  <div className="theme-detail-kpi">
                    <p className="theme-detail-kpi-label">이벤트</p>
                    <p className="theme-detail-kpi-value">{selectedTheme.eventCount}건</p>
                  </div>
                  <div className="theme-detail-kpi">
                    <p className="theme-detail-kpi-label">마지막 순위</p>
                    <p className="theme-detail-kpi-value">{selectedTheme.latestFinalRank ? `${selectedTheme.latestFinalRank}위` : "-"}</p>
                  </div>
                </div>
                <div className="theme-detail-info-row">
                  <div className="theme-detail-info-box">
                    <span className="theme-detail-info-label">등장 날짜</span>
                    <span className="theme-detail-info-value">
                      {selectedTheme.sourceDates.length ? selectedTheme.sourceDates.join(", ") : "-"} · 마지막 등장일: {selectedTheme.latestDate ?? "-"}
                    </span>
                  </div>
                  <div className="theme-detail-info-box">
                    <span className="theme-detail-info-label">관련 종목</span>
                    <span className="theme-detail-info-value">
                      {selectedTheme.relatedStocks.length ? selectedTheme.relatedStocks.join(", ") : "월간 테마 누적 흐름 그래프 데이터에 포함되지 않음"}
                    </span>
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
                  <b>점수 기준:</b> 시장트렌드분석 월간 테마 누적 흐름 그래프의 daily_score를 최근 1개월 기준으로 합산하며, 타일 면적은 종목수가 아니라 점수 합산값 기준입니다.
                </p>
              </div>
            ) : null}
          </div>
        )}
      </SectionCard>

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
