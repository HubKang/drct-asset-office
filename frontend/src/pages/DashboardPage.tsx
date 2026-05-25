import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import PageHeader from "@/components/common/PageHeader";
import SectionCard from "@/components/common/SectionCard";
import StatusBadge from "@/components/common/StatusBadge";
import { dataSourceLabel, repositories } from "@/services";
import type { CollectionRun } from "@/types/collectionRun";
import type { Disclosure } from "@/types/disclosure";
import type { BriefingVideo } from "@/types/economicBriefing";
import type { NewsItem } from "@/types/news";
import type { TelegramItem } from "@/types/telegram";

type SourceKey = "news" | "disclosure" | "youtube" | "telegram";
type SourceStatus = "normal" | "warning" | "failed" | "idle";
type FeedTab = SourceKey;

type SourceSummary = {
  source: SourceKey;
  label: string;
  collected_count: number;
  summarized_count: number;
  pending_count: number;
  failed_count: number;
  last_collected_at: string | null;
  status: SourceStatus;
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
  source: SourceKey;
  title: string;
  collected_at: string;
  ai_status: string;
  score?: number | null;
  event_type?: string | null;
  target_url: string;
};

type CandidateItem = {
  source: SourceKey;
  title: string;
  score: number;
  tag: string;
  event_type: string;
  reason: string;
  collected_at: string;
  target_url: string;
};

type CrossKeywordItem = {
  keyword: string;
  total: number;
  sourceCounts: Partial<Record<SourceKey, number>>;
};

type DashboardData = {
  today: string;
  source_summaries: SourceSummary[];
  weekly_calendar: CalendarDay[];
  feed_by_source: Record<SourceKey, FeedItem[]>;
  candidates_top5: CandidateItem[];
  cross_keywords: CrossKeywordItem[];
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

const HIGH_IMPACT_EVENTS = new Set(["실적", "수주", "투자", "정책", "공급계약", "테마확산", "수급"]);

const todayInKst = () =>
  new Intl.DateTimeFormat("sv-SE", { timeZone: "Asia/Seoul" }).format(new Date());

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
  const sorted = filtered.sort();
  return sorted[sorted.length - 1] ?? null;
};

const toneByStatus = (status: SourceStatus): "emerald" | "amber" | "rose" | "slate" => {
  if (status === "normal") return "emerald";
  if (status === "warning") return "amber";
  if (status === "failed") return "rose";
  return "slate";
};

const statusLabel = (status: SourceStatus) => {
  if (status === "normal") return "정상";
  if (status === "warning") return "주의";
  if (status === "failed") return "실패";
  return "미수집";
};

const summarizeStatusLabel = (value: string) => {
  const key = (value || "").toLowerCase();
  if (["summarized", "success", "completed"].includes(key)) return "요약완료";
  if (["failed", "error"].includes(key)) return "요약실패";
  if (["pending", "running", "queued"].includes(key)) return "요약대기";
  return value || "미확인";
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
    .split(/[\s,|/]+/g)
    .map((v) => v.trim())
    .filter((v) => v.length >= 2);

function DashboardPage() {
  const navigate = useNavigate();
  const [dashboard, setDashboard] = useState<DashboardData | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");
  const [feedTab, setFeedTab] = useState<FeedTab>("news");

  const loadDashboard = useCallback(async () => {
    setIsLoading(true);
    setErrorMessage("");
    const today = todayInKst();
    try {
      const [runsRes, newsItems, disclosures, videosRes, telegramItemsRes] = await Promise.all([
        repositories.collectionRuns.listCollectionRuns({ limit: 500, offset: 0 }),
        repositories.news.listNews({ limit: 300, offset: 0 }),
        repositories.disclosures.listDisclosures({ limit: 300, offset: 0 }),
        repositories.economicBriefing.getBriefingVideos({ limit: 300 }),
        repositories.telegram.listItems({ date_from: today, date_to: today, limit: 300, offset: 0 }),
      ]);

      const videos = videosRes.items ?? [];
      const runs = runsRes.items ?? [];
      const todaysNews = newsItems.filter((item) => getDatePart(item.collected_at || item.created_at) === today);
      const todaysDisclosures = disclosures.filter((item) => getDatePart(item.created_at || item.disclosed_at) === today);
      const todaysVideos = videos.filter((item) => getDatePart(item.created_at || item.updated_at || item.published_at) === today);
      const todaysTelegram = telegramItemsRes.items ?? [];

      const todaysRuns = runs.filter((run) => getDatePart(run.started_at || run.created_at) === today);
      const runFailuresBySource = todaysRuns.reduce<Record<SourceKey, number>>(
        (acc, run) => {
          const source = inferSourceFromRun(run);
          if (!source) return acc;
          if (run.status === "failed" || run.status === "partial") acc[source] += 1;
          return acc;
        },
        { news: 0, disclosure: 0, youtube: 0, telegram: 0 },
      );

      const baseSummaries: SourceSummary[] = [
        {
          source: "news",
          label: SOURCE_LABEL.news,
          collected_count: todaysNews.length,
          summarized_count: todaysNews.filter((n) => !!n.ai_processed_at && !!n.ai_summary).length,
          pending_count: todaysNews.filter((n) => !n.ai_processed_at && !n.ai_summary_error).length,
          failed_count: todaysNews.filter((n) => !!n.ai_summary_error).length + runFailuresBySource.news,
          last_collected_at: maxDate(todaysNews.map((n) => n.collected_at || n.created_at)),
          status: "idle",
        },
        {
          source: "disclosure",
          label: SOURCE_LABEL.disclosure,
          collected_count: todaysDisclosures.length,
          summarized_count: todaysDisclosures.filter((d) => !!d.ai_processed_at && !!d.ai_summary).length,
          pending_count: todaysDisclosures.filter((d) => !d.ai_processed_at && !d.ai_summary_error).length,
          failed_count: todaysDisclosures.filter((d) => !!d.ai_summary_error).length + runFailuresBySource.disclosure,
          last_collected_at: maxDate(todaysDisclosures.map((d) => d.created_at || d.disclosed_at)),
          status: "idle",
        },
        {
          source: "youtube",
          label: SOURCE_LABEL.youtube,
          collected_count: todaysVideos.length,
          summarized_count: todaysVideos.filter((v) => (v.analysis_status || "").toLowerCase().includes("success")).length,
          pending_count: todaysVideos.filter((v) => !["success", "completed", "failed", "error"].includes((v.analysis_status || "").toLowerCase())).length,
          failed_count: todaysVideos.filter((v) => ["failed", "error"].includes((v.analysis_status || "").toLowerCase())).length + runFailuresBySource.youtube,
          last_collected_at: maxDate(todaysVideos.map((v) => v.updated_at || v.created_at || v.published_at)),
          status: "idle",
        },
        {
          source: "telegram",
          label: SOURCE_LABEL.telegram,
          collected_count: todaysTelegram.length,
          summarized_count: todaysTelegram.filter((t) => t.summary_status === "summarized" && t.summary_has_content === 1).length,
          pending_count: todaysTelegram.filter((t) => t.summary_status === "pending").length,
          failed_count: todaysTelegram.filter((t) => t.summary_status === "failed").length + runFailuresBySource.telegram,
          last_collected_at: maxDate(todaysTelegram.map((t) => t.updated_at || t.message_date)),
          status: "idle",
        },
      ];

      const sourceSummaries: SourceSummary[] = baseSummaries.map((row) => {
        let status: SourceStatus = "normal";
        if (row.collected_count === 0) status = "idle";
        else if (runFailuresBySource[row.source] > 0) status = "failed";
        else if (row.failed_count > 0 || row.pending_count > 5) status = "warning";
        return { ...row, status };
      });

      const weeklyCalendar = Array.from({ length: 7 }, (_, idx) => {
        const target = new Date();
        target.setDate(target.getDate() - idx);
        const date = new Intl.DateTimeFormat("sv-SE", { timeZone: "Asia/Seoul" }).format(target);
        const failedCount = runs.filter((r) => getDatePart(r.started_at || r.created_at) === date && (r.status === "failed" || r.status === "partial")).length;
        return {
          date,
          news_count: newsItems.filter((n) => getDatePart(n.collected_at || n.created_at) === date).length,
          disclosure_count: disclosures.filter((d) => getDatePart(d.created_at || d.disclosed_at) === date).length,
          youtube_count: videos.filter((v) => getDatePart(v.created_at || v.updated_at || v.published_at) === date).length,
          telegram_count: runs.filter((r) => getDatePart(r.started_at || r.created_at) === date && inferSourceFromRun(r) === "telegram").length,
          failed_count: failedCount,
        };
      }).reverse();

      const feedBySource: Record<SourceKey, FeedItem[]> = {
        news: todaysNews
          .map((n: NewsItem) => ({
            source: "news" as const,
            title: n.title || "제목 없음",
            collected_at: n.collected_at || n.created_at,
            ai_status: n.ai_summary_error ? "failed" : n.ai_processed_at ? "summarized" : "pending",
            score: n.ai_importance_score ?? n.importance_score,
            event_type: null,
            target_url: SOURCE_ROUTE.news,
          }))
          .sort((a, b) => (a.collected_at < b.collected_at ? 1 : -1))
          .slice(0, 10),
        disclosure: todaysDisclosures
          .map((d: Disclosure) => ({
            source: "disclosure" as const,
            title: d.disclosure_title || "공시 제목 없음",
            collected_at: d.created_at || d.disclosed_at || "",
            ai_status: d.ai_summary_error ? "failed" : d.ai_processed_at ? "summarized" : "pending",
            score: d.ai_importance_score ?? d.importance_score,
            event_type: d.ai_event_type || null,
            target_url: SOURCE_ROUTE.disclosure,
          }))
          .sort((a, b) => (a.collected_at < b.collected_at ? 1 : -1))
          .slice(0, 10),
        youtube: todaysVideos
          .map((v: BriefingVideo) => ({
            source: "youtube" as const,
            title: v.title || "영상 제목 없음",
            collected_at: v.updated_at || v.created_at || "",
            ai_status: v.analysis_status || "pending",
            score: null,
            event_type: null,
            target_url: SOURCE_ROUTE.youtube,
          }))
          .sort((a, b) => (a.collected_at < b.collected_at ? 1 : -1))
          .slice(0, 10),
        telegram: todaysTelegram
          .map((t: TelegramItem) => ({
            source: "telegram" as const,
            title: t.item_title || t.message_text || "메시지 제목 없음",
            collected_at: t.updated_at || t.message_date,
            ai_status: t.summary_status,
            score: t.score,
            event_type: t.event_type || null,
            target_url: SOURCE_ROUTE.telegram,
          }))
          .sort((a, b) => (a.collected_at < b.collected_at ? 1 : -1))
          .slice(0, 10),
      };

      const keywordSourceMap = new Map<string, Partial<Record<SourceKey, number>>>();
      const addKeywordCount = (source: SourceKey, keyword: string) => {
        const key = keyword.trim();
        if (!key || key.length < 2) return;
        const prev = keywordSourceMap.get(key) ?? {};
        prev[source] = (prev[source] ?? 0) + 1;
        keywordSourceMap.set(key, prev);
      };

      todaysNews.forEach((n) => splitKeywords(n.ai_tags).forEach((k) => addKeywordCount("news", k)));
      todaysDisclosures.forEach((d) => {
        addKeywordCount("disclosure", d.ai_event_type || "");
        splitKeywords(d.ai_tags).forEach((k) => addKeywordCount("disclosure", k));
      });
      todaysTelegram.forEach((t) => {
        addKeywordCount("telegram", t.tag || "");
        addKeywordCount("telegram", t.event_type || "");
      });
      todaysVideos.forEach((v) => splitKeywords(v.title).slice(0, 3).forEach((k) => addKeywordCount("youtube", k)));

      const crossKeywords = Array.from(keywordSourceMap.entries())
        .map(([keyword, sourceCounts]) => {
          const total = Object.values(sourceCounts).reduce((sum, count) => sum + (count ?? 0), 0);
          return { keyword, total, sourceCounts };
        })
        .filter((row) => Object.keys(row.sourceCounts).length >= 2)
        .sort((a, b) => b.total - a.total)
        .slice(0, 10);

      const multiSourceKeywordSet = new Set(crossKeywords.map((k) => k.keyword));
      const disclosureStockSet = new Set(todaysDisclosures.map((d) => d.stock_code).filter(Boolean));

      const candidatePool: CandidateItem[] = [
        ...todaysNews.map((n) => {
          const score = n.ai_importance_score ?? n.importance_score ?? 0;
          const tags = splitKeywords(n.ai_tags);
          const hotTag = tags.find((t) => multiSourceKeywordSet.has(t)) || tags[0] || "뉴스";
          const reasonParts: string[] = [];
          if (score >= 80) reasonParts.push("고점수");
          if ((n.ai_sentiment || "").toLowerCase() === "positive" || (n.ai_sentiment || "").toLowerCase() === "negative") reasonParts.push("감성 신호");
          if (tags.some((t) => multiSourceKeywordSet.has(t))) reasonParts.push("교차 키워드");
          if (n.stock_code && disclosureStockSet.has(n.stock_code)) reasonParts.push("공시 동시 포착");
          return {
            source: "news" as const,
            title: n.title || "제목 없음",
            score,
            tag: hotTag,
            event_type: "뉴스",
            reason: reasonParts.join(" · ") || "오늘 수집 핵심 뉴스",
            collected_at: n.collected_at || n.created_at,
            target_url: SOURCE_ROUTE.news,
          };
        }),
        ...todaysDisclosures.map((d) => {
          const score = d.ai_importance_score ?? d.importance_score ?? 0;
          const event = d.ai_event_type || "공시";
          const reasonParts: string[] = [];
          if (score >= 80) reasonParts.push("고점수");
          if ((d.ai_risk_level || "").toLowerCase() === "high") reasonParts.push("고위험");
          if (HIGH_IMPACT_EVENTS.has(event)) reasonParts.push("중요 이벤트");
          if (d.stock_code && todaysNews.some((n) => n.stock_code === d.stock_code)) reasonParts.push("뉴스 동시 포착");
          return {
            source: "disclosure" as const,
            title: d.disclosure_title || "공시 제목 없음",
            score,
            tag: d.ai_tags || "공시",
            event_type: event,
            reason: reasonParts.join(" · ") || "오늘 수집 핵심 공시",
            collected_at: d.created_at || d.disclosed_at || "",
            target_url: SOURCE_ROUTE.disclosure,
          };
        }),
        ...todaysTelegram.map((t) => {
          const score = t.score ?? 0;
          const event = t.event_type || "기타";
          const reasonParts: string[] = [];
          if (score >= 80) reasonParts.push("고점수");
          if ((t.risk_level || "").toLowerCase() === "high") reasonParts.push("고위험");
          if (HIGH_IMPACT_EVENTS.has(event)) reasonParts.push("중요 이벤트");
          if (t.tag && multiSourceKeywordSet.has(t.tag)) reasonParts.push("교차 키워드");
          return {
            source: "telegram" as const,
            title: t.item_title || t.message_text || "메시지 제목 없음",
            score,
            tag: t.tag || "텔레그램",
            event_type: event,
            reason: reasonParts.join(" · ") || "오늘 수집 핵심 텔레그램",
            collected_at: t.updated_at || t.message_date,
            target_url: SOURCE_ROUTE.telegram,
          };
        }),
      ];

      const candidatesTop5 = candidatePool
        .filter((c) => c.score >= 80 || c.reason.includes("고위험") || c.reason.includes("교차 키워드") || c.reason.includes("동시 포착"))
        .sort((a, b) => {
          if (b.score !== a.score) return b.score - a.score;
          return a.collected_at < b.collected_at ? 1 : -1;
        })
        .slice(0, 5);

      setDashboard({
        today,
        source_summaries: sourceSummaries,
        weekly_calendar: weeklyCalendar,
        feed_by_source: feedBySource,
        candidates_top5: candidatesTop5,
        cross_keywords: crossKeywords,
      });
    } catch (error) {
      console.error("[Dashboard] load failed", error);
      setErrorMessage("대시보드 데이터를 불러오지 못했습니다.");
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadDashboard();
  }, [loadDashboard]);

  const summaryCards = useMemo(() => dashboard?.source_summaries ?? [], [dashboard]);
  const calendar = useMemo(() => dashboard?.weekly_calendar ?? [], [dashboard]);
  const feedItems = dashboard?.feed_by_source?.[feedTab] ?? [];

  return (
    <div className="space-y-4">
      <PageHeader
        title="투자 정보 수집 대시보드"
        description="뉴스·공시·유튜브·텔레그램 수집 및 AI 처리 현황"
        action={(
          <div className="flex items-center gap-2">
            <StatusBadge label={`데이터 소스: ${dataSourceLabel.toUpperCase()}`} tone="blue" />
            <StatusBadge label={`기준일 ${dashboard?.today ?? todayInKst()}`} tone="slate" />
            <button
              type="button"
              className="btn btn-secondary transition-all duration-150 active:scale-[0.98]"
              onClick={() => void loadDashboard()}
              disabled={isLoading}
            >
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

      <SectionCard title="오늘의 수집 요약">
        {summaryCards.length === 0 ? (
          <p className="text-sm text-slate-500">오늘 수집된 데이터가 없습니다.</p>
        ) : (
          <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-4">
            {summaryCards.map((item) => (
              <button
                key={item.source}
                type="button"
                className="rounded-lg border border-slate-200 bg-white p-4 text-left transition-colors hover:bg-slate-50"
                onClick={() => navigate(SOURCE_ROUTE[item.source])}
              >
                <div className="mb-2 flex items-center justify-between">
                  <h3 className="text-sm font-semibold text-slate-900">{item.label}</h3>
                  <StatusBadge label={statusLabel(item.status)} tone={toneByStatus(item.status)} />
                </div>
                <div className="space-y-1 text-xs text-slate-600">
                  <div>수집 {item.collected_count}건</div>
                  <div>요약완료 {item.summarized_count}건</div>
                  <div>요약대기 {item.pending_count}건</div>
                  <div>실패/주의 {item.failed_count}건</div>
                  <div className="pt-1 text-[11px] text-slate-500">마지막 수집: {formatDateTime(item.last_collected_at)}</div>
                </div>
              </button>
            ))}
          </div>
        )}
      </SectionCard>

      <SectionCard title="최근 7일 수집 캘린더">
          {calendar.length === 0 ? (
            <p className="text-sm text-slate-500">최근 7일 수집 이력이 없습니다.</p>
          ) : (
            <div className="grid grid-cols-1 gap-2 md:grid-cols-2 xl:grid-cols-7">
              {calendar.map((day) => (
                <button
                  type="button"
                  key={day.date}
                  onClick={() => navigate("/collection-runs")}
                  className="rounded-lg border border-slate-200 bg-slate-50 p-3 text-left transition-colors hover:bg-white"
                >
                  <div className="text-xs font-semibold text-slate-800">{day.date}</div>
                  <div className="mt-2 flex flex-wrap gap-1 text-[11px]">
                    <StatusBadge label={`뉴 ${day.news_count}`} tone="blue" />
                    <StatusBadge label={`공 ${day.disclosure_count}`} tone="slate" />
                    <StatusBadge label={`유 ${day.youtube_count}`} tone="amber" />
                    <StatusBadge label={`텔 ${day.telegram_count}`} tone="emerald" />
                    {day.failed_count > 0 ? <StatusBadge label={`실패 ${day.failed_count}`} tone="rose" /> : null}
                  </div>
                </button>
              ))}
            </div>
          )}
      </SectionCard>

      <SectionCard title="오늘의 투자 검토 후보 Top 5">
          {!dashboard?.candidates_top5?.length ? (
            <p className="text-sm text-slate-500">오늘 검토 우선 후보가 없습니다.</p>
          ) : (
            <div className="grid grid-cols-1 gap-2 md:grid-cols-2 xl:grid-cols-5">
              {dashboard.candidates_top5.map((item, idx) => (
                <button
                  key={`${item.source}-${idx}-${item.collected_at}`}
                  type="button"
                  className="h-full min-h-[148px] rounded-md border border-slate-200 px-3 py-2 text-left transition-colors hover:bg-slate-50"
                  onClick={() => navigate(item.target_url)}
                >
                  <div className="mb-1 flex items-center gap-2">
                    <span className="text-xs font-semibold text-slate-500">{idx + 1}</span>
                    <StatusBadge label={SOURCE_LABEL[item.source]} tone={item.source === "telegram" ? "emerald" : item.source === "news" ? "blue" : "slate"} />
                    <span className="text-xs text-slate-500">점수 {item.score}</span>
                  </div>
                  <p className="line-clamp-2 text-sm font-medium text-slate-900">{item.title}</p>
                  <p className="mt-1 text-xs text-slate-600">태그: {item.tag || "-"} · 이벤트: {item.event_type || "-"}</p>
                  <p className="text-xs text-slate-500">사유: {item.reason}</p>
                </button>
              ))}
            </div>
          )}
      </SectionCard>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-3">
        <SectionCard title="최근 수집 피드" className="xl:col-span-2">
          <div className="border-b border-slate-200">
            <nav className="flex flex-wrap items-center gap-6">
              {(["news", "disclosure", "youtube", "telegram"] as FeedTab[]).map((tab) => (
                <button
                  key={tab}
                  type="button"
                  className={`border-b-2 bg-transparent pb-3 text-sm transition-colors duration-150 ${
                    feedTab === tab
                      ? "border-slate-900 font-semibold text-slate-900"
                      : "border-transparent font-medium text-slate-500 hover:text-slate-900"
                  }`}
                  onClick={() => setFeedTab(tab)}
                >
                  {SOURCE_LABEL[tab]}
                </button>
              ))}
            </nav>
          </div>

          <div className="mt-3">
            {feedItems.length === 0 ? (
              <p className="text-sm text-slate-500">오늘 수집된 {SOURCE_LABEL[feedTab]}가 없습니다.</p>
            ) : (
              <div className="space-y-2">
                {feedItems.map((item, idx) => (
                  <button
                    key={`${item.source}-${idx}-${item.collected_at}`}
                    type="button"
                    className="flex w-full items-start gap-3 rounded-lg border border-slate-200 px-3 py-2 text-left transition-colors hover:bg-slate-50"
                    onClick={() => navigate(item.target_url)}
                  >
                    <StatusBadge label={SOURCE_LABEL[item.source]} tone={item.source === "telegram" ? "emerald" : item.source === "news" ? "blue" : item.source === "disclosure" ? "slate" : "amber"} />
                    <div className="min-w-0 flex-1">
                      <div className="truncate text-sm font-medium text-slate-900">{item.title}</div>
                      <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-slate-500">
                        <span>{formatDateTime(item.collected_at)}</span>
                        <span>·</span>
                        <span>{summarizeStatusLabel(item.ai_status)}</span>
                        {item.score != null ? <><span>·</span><span>점수 {item.score}</span></> : null}
                        {item.event_type ? <><span>·</span><span>{item.event_type}</span></> : null}
                      </div>
                    </div>
                  </button>
                ))}
              </div>
            )}
          </div>
        </SectionCard>

        <SectionCard title="소스 교차 등장 키워드">
          {!dashboard?.cross_keywords?.length ? (
            <p className="text-sm text-slate-500">오늘 2개 이상 소스에서 반복된 키워드가 없습니다.</p>
          ) : (
            <div className="space-y-3">
              {dashboard.cross_keywords.map((row) => {
                const max = Math.max(...dashboard.cross_keywords.map((x) => x.total), 1);
                const width = Math.max(12, Math.round((row.total / max) * 100));
                const sourceCount = Object.keys(row.sourceCounts).length;
                return (
                  <div key={row.keyword} className="space-y-1">
                    <div className="flex items-center justify-between">
                      <p className="text-sm font-semibold text-slate-900">{row.keyword}</p>
                      <span className="text-xs text-slate-500">총 {row.total}건 / {sourceCount}개 소스</span>
                    </div>
                    <div className="h-2 w-full rounded bg-slate-100">
                      <div className="h-2 rounded bg-slate-700" style={{ width: `${width}%` }} />
                    </div>
                    <div className="flex flex-wrap gap-1 text-[11px]">
                      {(["news", "disclosure", "youtube", "telegram"] as SourceKey[]).map((src) =>
                        row.sourceCounts[src] ? (
                          <StatusBadge key={`${row.keyword}-${src}`} label={`${SOURCE_LABEL[src]} ${row.sourceCounts[src]}`} tone={src === "telegram" ? "emerald" : src === "news" ? "blue" : src === "youtube" ? "amber" : "slate"} />
                        ) : null,
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </SectionCard>
      </div>
    </div>
  );
}

export default DashboardPage;
