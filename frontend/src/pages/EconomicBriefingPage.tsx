import { useEffect, useMemo, useRef, useState } from "react";
import PageHeader from "@/components/common/PageHeader";
import SectionCard from "@/components/common/SectionCard";
import { repositories } from "@/services";
import type { BriefingSource, BriefingSourceStatus, BriefingVideo, BriefingSummaryDetailResponse } from "@/types/economicBriefing";

type Tab = "sources" | "videos";
type SourceFilter = "all" | "manual" | `source:${number}`;
type RegisterType = "playlist" | "video";
type SummaryProgressState = {
  startedAtMs: number;
  durationSeconds: number;
  progress: number;
  status: "running" | "success" | "failed";
};
type RefreshStatusResult = {
  metadataChecked: number;
  transcriptChecked: number;
  statusSkipped: number;
  failed: number;
  failedReasons: Record<string, number>;
};

const STATUS_REFRESH_RECENT_HOURS = 24;
const TRANSCRIPT_RETRY_COOLDOWN_MINUTES = 60;
const TRANSCRIPT_RATE_LIMIT_COOLDOWN_MINUTES = 360;

const toErr = (e: unknown, fallback: string) => (e instanceof Error && e.message ? e.message : fallback);
const extractPlaylistIdFromUrl = (value: string): string | null => {
  try {
    const u = new URL(value.trim());
    const list = u.searchParams.get("list");
    return list && list.trim() ? list.trim() : null;
  } catch {
    return null;
  }
};
const formatDuration = (seconds: number | null | undefined) => {
  if (seconds == null || Number.isNaN(seconds)) return "-";
  const total = Math.max(0, Math.floor(seconds));
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = total % 60;
  return h > 0
    ? `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`
    : `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
};
const formatElapsed = (seconds: number | null | undefined) => {
  if (!seconds || seconds <= 0) return "-";
  const total = Math.floor(seconds);
  const m = Math.floor(total / 60);
  const s = total % 60;
  return `${m}분 ${s}초`;
};
const formatDate = (value: string | null) => {
  if (!value) return "-";
  const m = value.match(/^(\d{4}-\d{2}-\d{2})/);
  return m ? m[1] : value.slice(0, 10);
};
const mapTranscriptStatus = (v: string | null | undefined) => {
  if (!v || v === "unknown") return "미확인";
  if (v === "available") return "가능";
  if (v === "unavailable") return "없음";
  if (v === "failed") return "실패";
  return "미확인";
};
const mapAnalysisStatus = (v: string | null | undefined) => {
  if (!v || v === "unknown" || v === "pending") return "대기";
  if (v === "summarized") return "요약완료";
  if (v === "partial_failed") return "부분실패";
  if (v === "failed") return "실패";
  return "미확인";
};
const parseDateMs = (value: string | null | undefined) => {
  if (!value) return null;
  const ms = Date.parse(value.replace(" ", "T"));
  return Number.isFinite(ms) ? ms : null;
};
const isRecentWithinMinutes = (value: string | null | undefined, minutes: number) => {
  const ms = parseDateMs(value);
  if (ms == null) return false;
  return Date.now() - ms < minutes * 60 * 1000;
};
const isRecentWithinHours = (value: string | null | undefined, hours: number) => isRecentWithinMinutes(value, hours * 60);
const hasBlockedTranscriptError = (message: string | null | undefined) => {
  const src = (message || "").toLowerCase();
  return src.includes("ipblocked")
    || src.includes("transcriptfetcherror")
    || src.includes("429")
    || src.includes("too many requests")
    || src.includes("rate_limited")
    || src.includes("yt_dlp_rate_limited")
    || src.includes("all_providers_rate_limited")
    || src.includes("access_limited");
};
const isRateLimitedTranscriptError = (message: string | null | undefined) => {
  const src = (message || "").toLowerCase();
  return src.includes("429")
    || src.includes("too many requests")
    || src.includes("rate_limited")
    || src.includes("yt_dlp_rate_limited")
    || src.includes("all_providers_rate_limited");
};
type TranscriptIssueType = "access_limited" | "unavailable" | "fetch_failed" | "summary_failed" | "none";
const getTranscriptIssueType = (message: string | null | undefined): TranscriptIssueType => {
  const src = (message || "").toLowerCase();
  if (!src.trim()) return "none";
  if (src.includes("yt_dlp_runtime_missing")) return "fetch_failed";
  if (src.includes("yt_dlp_rate_limited") || src.includes("all_providers_rate_limited") || src.includes("rate_limited")) return "access_limited";
  if (src.includes("yt_dlp_not_installed") || src.includes("all_providers_failed")) return "fetch_failed";
  if (src.includes("ipblocked") || src.includes("429") || src.includes("rate") || src.includes("blocked") || src.includes("접근 제한")) return "access_limited";
  if (src.includes("notranscriptfound") || src.includes("transcriptsdisabled") || src.includes("no transcript") || src.includes("자막 없음") || src.includes("자막이 비활성")) return "unavailable";
  if (src.includes("transcriptfetcherror") || src.includes("자막 조회") || src.includes("transcript fetch failed")) return "fetch_failed";
  if (src.includes("llm") || src.includes("empty content") || src.includes("json") || src.includes("model")) return "summary_failed";
  return "fetch_failed";
};
const getTranscriptIssueLabel = (message: string | null | undefined) => {
  const src = (message || "").toLowerCase();
  if (src.includes("yt_dlp_rate_limited") || src.includes("all_providers_rate_limited") || src.includes("rate_limited")) return "YouTube 요청 제한";
  if (src.includes("yt_dlp_runtime_missing")) return "자막 수집 실행환경 부족";
  if (src.includes("yt_dlp_not_installed")) return "자막 수집 경로 미완성";
  if (src.includes("all_providers_failed")) return "자막 수집 실패";
  const issue = getTranscriptIssueType(message);
  if (issue === "access_limited") return "자막 접근 제한";
  if (issue === "unavailable") return "자막 없음";
  if (issue === "summary_failed") return "요약 생성 실패";
  if (issue === "fetch_failed") return "자막 조회 실패";
  return "";
};
const getTranscriptIssueHelpText = (message: string | null | undefined) => {
  const src = (message || "").toLowerCase();
  if (src.includes("yt_dlp_rate_limited") || src.includes("all_providers_rate_limited") || src.includes("rate_limited")) return "YouTube에서 자막 요청이 일시적으로 제한되었습니다. 반복 시도하면 제한이 길어질 수 있어 대기 후 재시도를 권장합니다.";
  if (src.includes("yt_dlp_runtime_missing")) return "yt-dlp 실행에 필요한 JavaScript runtime이 없어 대체 자막 수집을 수행할 수 없습니다.";
  if (src.includes("yt_dlp_not_installed")) return "기본 자막 API가 차단되었고 yt-dlp 대체 경로가 설치되어 있지 않습니다.";
  if (src.includes("all_providers_failed")) return "기본/대체 자막 수집 경로가 모두 실패했습니다. 네트워크/환경을 확인해 주세요.";
  const issue = getTranscriptIssueType(message);
  if (issue === "access_limited") return "현재 네트워크에서 YouTube 자막 접근이 제한되었습니다. 잠시 후 다시 시도하거나 네트워크 환경을 바꿔 확인해 주세요.";
  if (issue === "unavailable") return "이 영상은 제공되는 자막이 없어 요약할 수 없습니다.";
  if (issue === "summary_failed") return "자막은 확인되었지만 AI 요약 생성 중 문제가 발생했습니다.";
  if (issue === "fetch_failed") return "자막 조회 중 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.";
  return "";
};
const compactErrorMessage = (message: string | null | undefined) => {
  const label = getTranscriptIssueLabel(message);
  if (label) return label;
  if (!message) return "";
  return message.length > 28 ? `${message.slice(0, 28)}...` : message;
};
const mapAnalysisStatusLabel = (analysisStatus: string | null | undefined, errorMessage: string | null | undefined) => {
  const normalized = (analysisStatus || "").toLowerCase();
  if (!normalized || normalized === "unknown" || normalized === "pending") return "대기";
  if (normalized === "summarized" || normalized === "completed") return "요약완료";
  if (normalized === "partial_failed") return "부분실패";
  if (normalized === "failed") {
    const issue = getTranscriptIssueType(errorMessage);
    if (issue === "access_limited" || issue === "unavailable" || issue === "fetch_failed") return "자막 실패";
    return "요약 실패";
  }
  return "미확인";
};
const getTranscriptCooldownMinutes = (message: string | null | undefined) =>
  isRateLimitedTranscriptError(message) ? TRANSCRIPT_RATE_LIMIT_COOLDOWN_MINUTES : TRANSCRIPT_RETRY_COOLDOWN_MINUTES;
const parseMaybeJson = (text: string): unknown | null => {
  const src = text.trim();
  if (!src) return null;
  try {
    return JSON.parse(src);
  } catch {
    return null;
  }
};
const extractJsonBlocks = (text: string): unknown[] => {
  const src = text.trim();
  if (!src) return [];
  const direct = parseMaybeJson(src);
  if (direct) return [direct];

  const blocks: unknown[] = [];
  let depth = 0;
  let start = -1;
  for (let i = 0; i < src.length; i += 1) {
    const ch = src[i];
    if (ch === "{") {
      if (depth === 0) start = i;
      depth += 1;
    } else if (ch === "}") {
      if (depth > 0) depth -= 1;
      if (depth === 0 && start >= 0) {
        const candidate = src.slice(start, i + 1);
        const parsed = parseMaybeJson(candidate);
        if (parsed) blocks.push(parsed);
        start = -1;
      }
    }
  }
  return blocks;
};
const pickStringArray = (value: unknown): string[] => {
  if (!value) return [];
  if (Array.isArray(value)) return value.filter((x): x is string => typeof x === "string").map((x) => x.trim()).filter(Boolean);
  if (typeof value === "string") {
    const parsed = parseMaybeJson(value);
    if (Array.isArray(parsed)) return parsed.filter((x): x is string => typeof x === "string").map((x) => x.trim()).filter(Boolean);
  }
  return [];
};
const pickTopicArray = (value: unknown): Array<{ topic_name: string; summary: string }> => {
  if (!Array.isArray(value)) return [];
  return value
    .filter((t) => t && typeof t === "object")
    .map((t) => {
      const item = t as { topic_name?: unknown; summary?: unknown };
      return {
        topic_name: typeof item.topic_name === "string" ? item.topic_name.trim() : "",
        summary: typeof item.summary === "string" ? item.summary.trim() : "",
      };
    })
    .filter((t) => t.topic_name || t.summary);
};
const extractQuotedField = (text: string, field: string): string => {
  const regex = new RegExp(`"${field}"\\s*:\\s*"([^"]*)"`, "g");
  const matches = [...text.matchAll(regex)];
  if (matches.length === 0) return "";
  return matches.map((m) => m[1]?.trim() ?? "").filter(Boolean).join("\n\n");
};
const normalizeSummaryForDisplay = (summary: BriefingSummaryDetailResponse["summary"]) => {
  const fallback = {
    summaryText: summary?.summary_text?.trim() || "저장된 요약이 없습니다.",
    keyPoints: summary?.key_points ?? [],
    topics: summary?.topics ?? [],
    themeMentions: summary?.theme_mentions ?? [],
    stockMentions: summary?.stock_mentions ?? [],
    riskPoints: summary?.risk_points ?? [],
  };
  if (!summary) return fallback;

  const text = summary.summary_text ?? "";
  const blocks = extractJsonBlocks(text);
  if (blocks.length === 0) {
    if (text.includes("\"chunk_summary\"") || text.includes("\"overall_summary\"")) {
      const extracted = extractQuotedField(text, "overall_summary") || extractQuotedField(text, "chunk_summary");
      return {
        summaryText: extracted || fallback.summaryText,
        keyPoints: fallback.keyPoints,
        topics: fallback.topics,
        themeMentions: fallback.themeMentions,
        stockMentions: fallback.stockMentions,
        riskPoints: fallback.riskPoints,
      };
    }
    return fallback;
  }

  const summaryTexts: string[] = [];
  const keyPoints = [...fallback.keyPoints];
  const topics = [...fallback.topics];
  const themeMentions = [...fallback.themeMentions];
  const stockMentions = [...fallback.stockMentions];
  const riskPoints = [...fallback.riskPoints];

  for (const item of blocks) {
    if (!item || typeof item !== "object") continue;
    const data = item as {
      overall_summary?: unknown;
      chunk_summary?: unknown;
      key_points?: unknown;
      topics?: unknown;
      theme_mentions?: unknown;
      stock_mentions?: unknown;
      risk_points?: unknown;
    };
    const s =
      (typeof data.overall_summary === "string" && data.overall_summary.trim()) ||
      (typeof data.chunk_summary === "string" && data.chunk_summary.trim()) ||
      "";
    if (s) summaryTexts.push(s);
    keyPoints.push(...pickStringArray(data.key_points));
    topics.push(...pickTopicArray(data.topics));
    themeMentions.push(...pickStringArray(data.theme_mentions));
    stockMentions.push(...pickStringArray(data.stock_mentions));
    riskPoints.push(...pickStringArray(data.risk_points));
  }

  return {
    summaryText: summaryTexts.length > 0 ? Array.from(new Set(summaryTexts)).join("\n\n") : fallback.summaryText,
    keyPoints: Array.from(new Set(keyPoints)).filter(Boolean),
    topics: topics.filter((t, i, arr) => arr.findIndex((x) => x.topic_name === t.topic_name && x.summary === t.summary) === i),
    themeMentions: Array.from(new Set(themeMentions)).filter(Boolean),
    stockMentions: Array.from(new Set(stockMentions)).filter(Boolean),
    riskPoints: Array.from(new Set(riskPoints)).filter(Boolean),
  };
};

function EconomicBriefingPage() {
  const [tab, setTab] = useState<Tab>("videos");
  const [sources, setSources] = useState<BriefingSource[]>([]);
  const [videos, setVideos] = useState<BriefingVideo[]>([]);
  const [sourceStatusFilter, setSourceStatusFilter] = useState<BriefingSourceStatus>("all");
  const [videoSourceFilter, setVideoSourceFilter] = useState<SourceFilter>("all");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  const [registerType, setRegisterType] = useState<RegisterType>("playlist");
  const [registerUrl, setRegisterUrl] = useState("");
  const [registerName, setRegisterName] = useState("");
  const [manualSourceId, setManualSourceId] = useState<string>("");
  const [sourceFormOpen, setSourceFormOpen] = useState(false);

  const [summaryDetail, setSummaryDetail] = useState<BriefingSummaryDetailResponse | null>(null);
  const [selectedSummaryVideo, setSelectedSummaryVideo] = useState<BriefingVideo | null>(null);
  const [summaryLoading, setSummaryLoading] = useState(false);
  const [summaryError, setSummaryError] = useState("");
  const [summaryPanelOpen, setSummaryPanelOpen] = useState(false);
  const [currentPage, setCurrentPage] = useState(1);
  const normalizedSummary = useMemo(() => normalizeSummaryForDisplay(summaryDetail?.summary ?? null), [summaryDetail]);

  const [summaryProgressMap, setSummaryProgressMap] = useState<Record<string, SummaryProgressState>>({});
  const progressTimers = useRef<Record<string, number>>({});
  const [refreshingVideoStatuses, setRefreshingVideoStatuses] = useState(false);
  const [manualTranscriptCheckingMap, setManualTranscriptCheckingMap] = useState<Record<string, boolean>>({});

  const activeSources = useMemo(() => sources.filter((s) => s.is_active === 1), [sources]);
  const activePlaylistSources = useMemo(
    () => activeSources.filter((s) => s.source_type === "playlist"),
    [activeSources],
  );
  const pageSize = 10;
  const totalPages = Math.max(1, Math.ceil(videos.length / pageSize));
  const pagedVideos = useMemo(() => {
    const start = (currentPage - 1) * pageSize;
    return videos.slice(start, start + pageSize);
  }, [videos, currentPage]);

  const loadSources = async () => {
    try {
      const res = await repositories.economicBriefing.getBriefingSources({ status: sourceStatusFilter });
      setSources(res.items);
    } catch (e) {
      setError(toErr(e, "source 목록 조회에 실패했습니다."));
    }
  };

  const fetchVideosByFilter = async (filter?: SourceFilter): Promise<BriefingVideo[]> => {
    const selected = filter ?? videoSourceFilter;
    if (selected === "all") {
      const res = await repositories.economicBriefing.getBriefingVideos({ limit: 200 });
      return res.items;
    }
    if (selected === "manual") {
      const res = await repositories.economicBriefing.getBriefingVideos({ limit: 200, manual_only: true });
      return res.items;
    }
    const sourceId = Number(selected.replace("source:", ""));
    const res = await repositories.economicBriefing.getBriefingVideos({ limit: 200, source_id: sourceId });
    return res.items;
  };

  const loadVideos = async (filter?: SourceFilter) => {
    try {
      const items = await fetchVideosByFilter(filter);
      setVideos(items);
      setCurrentPage(1);
    } catch (e) {
      setError(toErr(e, "영상 목록 조회에 실패했습니다."));
    }
  };

  const shouldRefreshMetadata = (video: BriefingVideo) => {
    if (!video.title || !video.channel_name || !video.published_at || !video.duration_seconds) return true;
    return !isRecentWithinHours(video.updated_at, STATUS_REFRESH_RECENT_HOURS);
  };

  const accumulateReason = (bag: Record<string, number>, reason: string) => {
    bag[reason] = (bag[reason] || 0) + 1;
  };

  const refreshStatusesForVideos = async (items: BriefingVideo[]): Promise<RefreshStatusResult> => {
    const metadataTargets = items.filter(shouldRefreshMetadata);
    const metadataSet = new Set(metadataTargets.map((v) => v.video_id));
    const statusSkipped = items.filter((v) => !metadataSet.has(v.video_id)).length;

    let metadataChecked = 0;
    const transcriptChecked = 0;
    let failed = 0;
    const failedReasons: Record<string, number> = {};

    for (const video of metadataTargets) {
      try {
        const meta = await repositories.economicBriefing.refreshBriefingVideoMetadata(video.video_id);
        if (meta.success) metadataChecked += 1;
        else {
          failed += 1;
          accumulateReason(failedReasons, "metadata_failed");
        }
      } catch {
        failed += 1;
        accumulateReason(failedReasons, "metadata_failed");
      }
    }

    return { metadataChecked, transcriptChecked, statusSkipped, failed, failedReasons };
  };

  const refreshVideosFromYouTube = async () => {
    setError("");
    setMessage("");
    setRefreshingVideoStatuses(true);
    const selected = videoSourceFilter;
    try {
      let fetched = 0;
      let inserted = 0;
      let updated = 0;
      let skipped = 0;

      if (selected === "all") {
        const targets = activePlaylistSources;
        for (const s of targets) {
          const res = await repositories.economicBriefing.refreshBriefingSourceVideos(s.id, { max_results: 20 });
          fetched += res.fetched_count ?? 0;
          inserted += res.inserted_count ?? 0;
          updated += res.updated_count ?? 0;
          skipped += res.skipped_count ?? 0;
        }
      } else if (selected !== "manual") {
        const sourceId = Number(selected.replace("source:", ""));
        if (!Number.isFinite(sourceId)) {
          setError("유효한 source를 선택해 주세요.");
          return;
        }
        const source = sources.find((s) => s.id === sourceId);
        if (!source) {
          setError("선택한 source를 찾을 수 없습니다.");
          return;
        }
        if (source.source_type === "playlist") {
          const res = await repositories.economicBriefing.refreshBriefingSourceVideos(sourceId, { max_results: 20 });
          if (!res.success) {
            setError(res.message || "영상 새로고침에 실패했습니다.");
            return;
          }
          fetched += res.fetched_count ?? 0;
          inserted += res.inserted_count ?? 0;
          updated += res.updated_count ?? 0;
          skipped += res.skipped_count ?? 0;
        }
      }

      await loadSources();
      const refreshedItems = await fetchVideosByFilter(selected);
      const statusResult = await refreshStatusesForVideos(refreshedItems);
      await loadVideos(selected);
      const reasonSummary = Object.entries(statusResult.failedReasons)
        .map(([k, v]) => `${k} ${v}`)
        .join(", ");
      setMessage(
        `영상 목록을 새로 불러왔습니다. 목록 ${refreshedItems.length}건 · 소스갱신 fetched ${fetched}/inserted ${inserted}/updated ${updated}/skipped ${skipped} · 메타확인 ${statusResult.metadataChecked}건 · 자막확인 ${statusResult.transcriptChecked}건(자동확인 중단) · 건너뜀 ${statusResult.statusSkipped}건 · 실패 ${statusResult.failed}건${reasonSummary ? ` (${reasonSummary})` : ""}`,
      );
      if (statusResult.failed > 0) {
        setError("일부 영상 메타데이터 갱신에 실패했습니다. 잠시 후 다시 시도해 주세요.");
      }
    } catch (e) {
      setError(toErr(e, "영상 새로고침에 실패했습니다."));
    } finally {
      setRefreshingVideoStatuses(false);
    }
  };

  const isAnalysisCompleted = (status: string | null | undefined) => {
    const normalized = (status || "").toLowerCase();
    return normalized === "summarized" || normalized === "completed";
  };

  const isTranscriptCooldownActive = (video: BriefingVideo) =>
    hasBlockedTranscriptError(video.error_message)
      && isRecentWithinMinutes(video.transcript_checked_at, getTranscriptCooldownMinutes(video.error_message));

  const shouldShowTranscriptRetryButton = (video: BriefingVideo) => {
    if (isAnalysisCompleted(video.analysis_status)) return false;
    const transcriptStatus = (video.transcript_status || "unknown").toLowerCase();
    if (transcriptStatus === "available" || transcriptStatus === "unavailable") return false;
    if (transcriptStatus === "failed" || transcriptStatus === "error" || transcriptStatus === "unknown" || transcriptStatus === "pending" || transcriptStatus === "") {
      return true;
    }
    if (hasBlockedTranscriptError(video.error_message)) return true;
    return false;
  };

  const refreshSingleTranscript = async (video: BriefingVideo) => {
    const key = video.video_id;
    if (manualTranscriptCheckingMap[key]) return;
    setError("");
    setManualTranscriptCheckingMap((prev) => ({ ...prev, [key]: true }));
    try {
      const result = await repositories.economicBriefing.checkBriefingVideoTranscript(video.video_id);
      if (result.success) {
        setMessage("자막 상태를 확인했습니다.");
      } else {
        setError("자막 조회에 실패했습니다. 현재 네트워크에서 YouTube 자막 접근이 제한될 수 있습니다.");
      }
      await loadVideos(videoSourceFilter);
    } catch (e) {
      setError(toErr(e, "자막 조회에 실패했습니다. 현재 네트워크에서 YouTube 자막 접근이 제한될 수 있습니다."));
    } finally {
      setManualTranscriptCheckingMap((prev) => ({ ...prev, [key]: false }));
    }
  };

  const registerYouTubeUrl = async () => {
    if (!registerUrl.trim()) {
      setError("YouTube URL을 입력해 주세요.");
      return;
    }
    setError("");
    try {
      if (registerType === "playlist") {
        if (!extractPlaylistIdFromUrl(registerUrl)) {
          setError("재생목록으로 등록하려면 list가 포함된 YouTube 재생목록 URL을 입력해 주세요.");
          return;
        }
        const res = await repositories.economicBriefing.createBriefingSource({
          source_type: "playlist",
          source_name: registerName.trim() || "재생목록 source",
          source_url: registerUrl.trim(),
          channel_id: null,
          playlist_id: null,
          is_active: 1,
          is_default: 0,
        });
        setMessage(res.message);
        await loadSources();
      } else {
        const nextFilter: SourceFilter = "manual";
        const res = await repositories.economicBriefing.createManualBriefingVideo({
          video_url: registerUrl.trim(),
          source_id: null,
        });
        setMessage(res.message);
        setVideoSourceFilter(nextFilter);
        setTab("videos");
        await loadVideos(nextFilter);
      }
      setRegisterUrl("");
      setRegisterName("");
      setManualSourceId("");
      setSourceFormOpen(false);
    } catch (e) {
      setError(toErr(e, "URL 등록에 실패했습니다."));
    }
  };

  const deactivateSource = async (id: number) => {
    if (!window.confirm("이 source를 비활성화하시겠습니까? 기존 영상과 요약 데이터는 유지됩니다.")) return;
    try {
      const res = await repositories.economicBriefing.deactivateBriefingSource(id);
      setMessage(res.message);
      await loadSources();
    } catch (e) {
      setError(toErr(e, "source 비활성화에 실패했습니다."));
    }
  };

  const activateSource = async (id: number) => {
    if (!window.confirm("이 source를 다시 활성화하시겠습니까?")) return;
    try {
      const res = await repositories.economicBriefing.activateBriefingSource(id);
      setMessage(res.message);
      await loadSources();
    } catch (e) {
      setError(toErr(e, "source 활성화에 실패했습니다."));
    }
  };

  const deleteSource = async (id: number) => {
    if (!window.confirm("이 source를 삭제하시겠습니까? 연결 영상은 유지되고 source 연결만 해제됩니다.")) return;
    try {
      const res = await repositories.economicBriefing.deleteBriefingSource(id);
      setMessage(res.message);
      await loadSources();
      await loadVideos();
    } catch (e) {
      setError(toErr(e, "source 삭제에 실패했습니다."));
    }
  };

  const estimateSummaryProgress = (startedAtMs: number, durationSeconds?: number) => {
    const elapsedSeconds = (Date.now() - startedAtMs) / 1000;
    const hasDuration = Boolean(durationSeconds && durationSeconds > 0);
    const videoSeconds = hasDuration ? (durationSeconds as number) : 1200;
    const expectedSeconds = Math.max(240, videoSeconds * 0.8);
    const ratio = elapsedSeconds / expectedSeconds;

    // 1구간(0~70%): 빠르게 진행률 반영
    if (ratio <= 0.7) {
      const p = Math.floor((ratio / 0.7) * 75);
      return Math.max(1, Math.min(75, p));
    }

    // 2구간(70~100% 예상시간): 완만하게 증가
    if (ratio <= 1.0) {
      const p = 75 + Math.floor(((ratio - 0.7) / 0.3) * 14);
      return Math.max(75, Math.min(89, p));
    }

    // 예상시간 초과 구간: 오래 걸려도 95%에 너무 빨리 고정되지 않도록 천천히 증가
    const tailSeconds = expectedSeconds * (hasDuration ? 0.8 : 1.2);
    const tailRatio = Math.min(1, (elapsedSeconds - expectedSeconds) / Math.max(60, tailSeconds));
    const p = 90 + Math.floor(tailRatio * 5);
    return Math.max(90, Math.min(95, p));
  };

  const startProgress = (videoId: string, durationSeconds: number | null | undefined) => {
    const safeDuration = durationSeconds && durationSeconds > 0 ? durationSeconds : 600;
    const startedAtMs = Date.now();
    setSummaryProgressMap((prev) => ({
      ...prev,
      [videoId]: { startedAtMs, durationSeconds: safeDuration, progress: 1, status: "running" },
    }));
    const prevTimer = progressTimers.current[videoId];
    if (prevTimer) window.clearInterval(prevTimer);
    const timer = window.setInterval(() => {
      setSummaryProgressMap((prev) => {
        const current = prev[videoId];
        if (!current || current.status !== "running") return prev;
        const next = estimateSummaryProgress(current.startedAtMs, current.durationSeconds);
        return { ...prev, [videoId]: { ...current, progress: next } };
      });
    }, 3000);
    progressTimers.current[videoId] = timer;
  };

  const stopProgress = (videoId: string, done: boolean) => {
    const timer = progressTimers.current[videoId];
    if (timer) {
      window.clearInterval(timer);
      delete progressTimers.current[videoId];
    }
    setSummaryProgressMap((prev) => {
      const current = prev[videoId];
      if (!current) return prev;
      return {
        ...prev,
        [videoId]: {
          ...current,
          progress: done ? 100 : current.progress,
          status: done ? "success" : "failed",
        },
      };
    });
  };

  const summarizeVideo = async (video: BriefingVideo) => {
    let force = false;
    if (video.analysis_status === "summarized") {
      if (!window.confirm("이미 요약된 영상입니다. 다시 요약하시겠습니까?")) return;
      force = true;
    }
    startProgress(video.video_id, video.duration_seconds);
    try {
      const res = await repositories.economicBriefing.summarizeBriefingVideo(video.video_id, force);
      if (!res.success) {
        stopProgress(video.video_id, false);
        setError(res.message + (res.error ? ` (${res.error})` : ""));
        return;
      }
      stopProgress(video.video_id, true);
      setMessage(res.message || "요약완료");
      await loadVideos();
    } catch (e) {
      stopProgress(video.video_id, false);
      setError(toErr(e, "요약실행에 실패했습니다."));
    }
  };

  const openSummaryPanel = async (video: BriefingVideo) => {
    if (selectedSummaryVideo?.video_id === video.video_id && summaryPanelOpen) {
      setSummaryPanelOpen(false);
      setSelectedSummaryVideo(null);
      setSummaryDetail(null);
      setSummaryLoading(false);
      setSummaryError("");
      return;
    }
    setSelectedSummaryVideo(video);
    setSummaryPanelOpen(true);
    setSummaryLoading(true);
    setSummaryError("");
    try {
      const res = await repositories.economicBriefing.getBriefingVideoSummaries(video.video_id);
      setSummaryDetail(res);
    } catch (e) {
      setSummaryError(toErr(e, "요약 조회에 실패했습니다."));
      setSummaryDetail(null);
    } finally {
      setSummaryLoading(false);
    }
  };

  useEffect(() => {
    void loadSources();
    void loadVideos("all");
    return () => {
      Object.values(progressTimers.current).forEach((id) => window.clearInterval(id));
      progressTimers.current = {};
    };
  }, []);

  useEffect(() => {
    void loadSources();
  }, [sourceStatusFilter]);

  useEffect(() => {
    void loadVideos(videoSourceFilter);
  }, [videoSourceFilter]);

  useEffect(() => {
    if (currentPage > totalPages) {
      setCurrentPage(totalPages);
    }
  }, [currentPage, totalPages]);

  return (
    <div className="space-y-4">
      <PageHeader title="경제 브리핑" description="영상 메타데이터/요약 결과를 관리합니다. 자막 전문은 저장하지 않습니다." />
      {message ? <div className="inline-result">{message}</div> : null}
      {error ? <div className="inline-result inline-error">{error}</div> : null}

      <SectionCard title="">
        <div className="border-b border-slate-200">
          <nav className="flex flex-wrap items-center gap-6">
            <button
              type="button"
              className={`border-b-2 bg-transparent pb-3 text-sm transition-colors duration-150 ${
                tab === "videos"
                  ? "border-slate-900 font-semibold text-slate-900"
                  : "border-transparent font-medium text-slate-500 hover:text-slate-900"
              }`}
              onClick={() => setTab("videos")}
            >
              영상 수집/요약
            </button>
            <button
              type="button"
              className={`border-b-2 bg-transparent pb-3 text-sm transition-colors duration-150 ${
                tab === "sources"
                  ? "border-slate-900 font-semibold text-slate-900"
                  : "border-transparent font-medium text-slate-500 hover:text-slate-900"
              }`}
              onClick={() => setTab("sources")}
            >
              소스 관리
            </button>
          </nav>
        </div>
      </SectionCard>

      {tab === "sources" ? (
        <SectionCard title="소스 관리">
          <p className="text-sm text-muted mb-3">등록한 YouTube 채널/재생목록/단일 영상 URL을 관리합니다. 활성 소스만 수집 대상이 됩니다.</p>
          <div className="flex gap-2 items-center mb-3 flex-wrap">
            <button type="button" className={`btn ${sourceStatusFilter === "all" ? "btn-primary" : "btn-secondary"}`} onClick={() => setSourceStatusFilter("all")}>전체</button>
            <button type="button" className={`btn ${sourceStatusFilter === "active" ? "btn-primary" : "btn-secondary"}`} onClick={() => setSourceStatusFilter("active")}>활성</button>
            <button type="button" className={`btn ${sourceStatusFilter === "inactive" ? "btn-primary" : "btn-secondary"}`} onClick={() => setSourceStatusFilter("inactive")}>비활성</button>
            <button type="button" className="btn btn-secondary" onClick={() => setSourceFormOpen((v) => !v)}>
              {sourceFormOpen ? "등록 폼 닫기" : "+ 새 소스 등록"}
            </button>
          </div>

          {sourceFormOpen ? (
          <div className="border rounded p-3 mb-4">
            <div className="font-semibold mb-1">YouTube URL 등록</div>
            <p className="text-xs text-muted mb-2">재생목록 URL은 여러 영상을 가져올 source로 등록됩니다. 단일 영상 URL은 영상 1건만 등록됩니다.</p>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
              <select className="input-control" value={registerType} onChange={(e) => setRegisterType(e.target.value as RegisterType)}>
                <option value="playlist">재생목록으로 등록</option>
                <option value="video">단일 영상으로 등록</option>
              </select>
              <input className="input-control" placeholder="YouTube URL" value={registerUrl} onChange={(e) => setRegisterUrl(e.target.value)} />
              <input className="input-control" placeholder="이름(재생목록 등록 시 사용)" value={registerName} onChange={(e) => setRegisterName(e.target.value)} />
              {registerType === "video" ? (
                <div className="input-control flex items-center text-sm text-muted">단일 영상은 source 미지정(미분류)으로 1건 등록됩니다.</div>
              ) : (
                <select className="input-control" value={manualSourceId} onChange={(e) => setManualSourceId(e.target.value)}>
                  <option value="">source 미지정(미분류)</option>
                  {activePlaylistSources.map((s) => <option key={s.id} value={String(s.id)}>{s.source_name}</option>)}
                </select>
              )}
              <div className="flex gap-2">
                <button type="button" className="btn btn-primary" onClick={() => void registerYouTubeUrl()}>등록</button>
                <button type="button" className="btn btn-secondary" onClick={() => { setRegisterUrl(""); setRegisterName(""); setManualSourceId(""); }}>초기화</button>
                <button type="button" className="btn btn-secondary" onClick={() => setSourceFormOpen(false)}>닫기</button>
              </div>
            </div>
          </div>
          ) : null}

          <div className="table-shell overflow-auto">
            <table className="data-table compact-table">
              <thead><tr><th>유형</th><th>이름</th><th>source 분류</th><th>URL</th><th>상태</th><th>관리</th></tr></thead>
              <tbody>
                {sources.map((s) => (
                  <tr key={s.id}>
                    <td>{s.source_type}</td>
                    <td>{s.source_name}</td>
                    <td>{s.source_type === "playlist" ? "재생목록 source" : "채널 source"}</td>
                    <td className="max-w-[220px] truncate" title={s.source_url}>
                      <a href={s.source_url} target="_blank" rel="noreferrer" className="text-blue-700 hover:underline">YouTube 열기</a>
                    </td>
                    <td>{s.is_active ? "활성" : "비활성"}</td>
                    <td>
                      <div className="flex gap-1 flex-wrap">
                        {s.is_active ? (
                          <>
                            <button type="button" className="btn btn-secondary" onClick={() => void deactivateSource(s.id)}>비활성화</button>
                            <button type="button" className="btn btn-danger" onClick={() => void deleteSource(s.id)}>삭제</button>
                          </>
                        ) : (
                          <>
                            <button type="button" className="btn btn-secondary" onClick={() => void activateSource(s.id)}>활성화</button>
                            <button type="button" className="btn btn-danger" onClick={() => void deleteSource(s.id)}>삭제</button>
                          </>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </SectionCard>
      ) : null}

      {tab === "videos" ? (
        <SectionCard title="영상 수집/요약">
          <div className="flex gap-2 mb-3 items-center flex-wrap">
            <select className="input-control" value={videoSourceFilter} onChange={(e) => setVideoSourceFilter(e.target.value as SourceFilter)}>
              <option value="all">전체</option>
              <option value="manual">수동/미분류</option>
              {activePlaylistSources.map((s) => <option key={s.id} value={`source:${s.id}`}>{s.source_name}</option>)}
            </select>
            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => void refreshVideosFromYouTube()}
              disabled={refreshingVideoStatuses}
              title="영상 목록을 새로 불러옵니다. 자막 확인은 필요한 영상에서 개별 실행합니다."
            >
              {refreshingVideoStatuses ? "새로고침 중..." : "목록 새로고침"}
            </button>
          </div>
          <div className="table-shell overflow-auto">
            <table className="data-table compact-table economic-videos-table">
              <thead><tr><th className="eb-col-date">게시일</th><th className="eb-col-title">제목</th><th className="eb-col-channel">채널명</th><th className="eb-col-duration">길이</th><th className="eb-col-transcript">자막상태</th><th className="eb-col-analysis">분석상태</th><th className="eb-col-actions">관리</th></tr></thead>
              <tbody>
                {pagedVideos.map((v) => {
                  const progressState = summaryProgressMap[v.video_id];
                  const progress = progressState?.progress ?? 0;
                  const running = progressState?.status === "running";
                  const canViewSummary = v.summary_has_content === true;
                  const isSelectedSummary = summaryPanelOpen && selectedSummaryVideo?.video_id === v.video_id;
                  const showTranscriptRetry = shouldShowTranscriptRetryButton(v);
                  const transcriptCooldown = isTranscriptCooldownActive(v);
                  const manualTranscriptChecking = manualTranscriptCheckingMap[v.video_id] === true;
                  const transcriptIssueType = getTranscriptIssueType(v.error_message);
                  const summarizeDisabled = running
                    || (v.transcript_status || "").toLowerCase() === "unavailable"
                    || (transcriptCooldown && transcriptIssueType === "access_limited");
                  const summarizeTitle = (v.transcript_status || "").toLowerCase() === "unavailable"
                    ? "자막이 없어 요약할 수 없습니다."
                    : (transcriptCooldown && transcriptIssueType === "access_limited"
                      ? "자막 접근 제한 상태입니다. 잠시 후 다시 시도해 주세요."
                      : ((v.transcript_status || "").toLowerCase() !== "available"
                        ? "자막 상태가 불안정합니다. 먼저 자막 재확인을 권장합니다."
                        : undefined));
                  return (
                    <tr key={v.id}>
                      <td>{formatDate(v.published_at)}</td>
                      <td className="eb-col-title-cell" title={v.title}>{v.title}</td>
                      <td>{v.channel_name || "-"}</td>
                      <td>{formatDuration(v.duration_seconds)}</td>
                      <td>{mapTranscriptStatus(v.transcript_status)}</td>
                      <td>{mapAnalysisStatusLabel(v.analysis_status, v.error_message)}</td>
                      <td>
                        <div className="eb-action-group">
                          {showTranscriptRetry ? (
                            <button
                              type="button"
                              className="btn btn-secondary eb-action-btn"
                              disabled={manualTranscriptChecking || transcriptCooldown}
                              onClick={() => void refreshSingleTranscript(v)}
                              title={transcriptCooldown ? "요청 제한 상태입니다. 잠시 후 다시 시도하세요." : "해당 영상 1건의 자막 상태를 다시 확인합니다."}
                            >
                              {manualTranscriptChecking ? "확인 중..." : (transcriptCooldown ? "요청 제한 대기" : "자막 재확인")}
                            </button>
                          ) : null}
                          <button
                            type="button"
                            className="btn btn-primary eb-action-btn"
                            disabled={summarizeDisabled}
                            onClick={() => void summarizeVideo(v)}
                            title={summarizeTitle}
                          >
                            {running ? "요약중..." : (v.analysis_status === "failed" ? "재시도" : (v.analysis_status === "summarized" ? "재요약" : "요약실행"))}
                          </button>
                          <button
                            type="button"
                            className="btn btn-secondary eb-action-btn"
                            disabled={!canViewSummary}
                            onClick={() => void openSummaryPanel(v)}
                            title={canViewSummary ? (isSelectedSummary ? "닫기" : "요약보기") : "저장된 요약 내용이 없습니다."}
                          >
                            {isSelectedSummary ? "닫기" : "요약보기"}
                          </button>
                        </div>
                        {running ? (
                          <div className="text-xs mt-1">
                            {progress >= 90 ? `마무리 중 · 예상 ${progress}%` : `요약 처리 중 · 예상 ${progress}%`}
                          </div>
                        ) : null}
                        {progress === 100 ? <div className="text-xs mt-1 text-green-600">요약완료</div> : null}
                        {v.error_message ? (
                          <div
                            className="text-xs text-red-600 max-w-[260px] truncate"
                            title={`${getTranscriptIssueHelpText(v.error_message) || ""}${getTranscriptIssueHelpText(v.error_message) ? " | " : ""}${v.error_message}`}
                          >
                            {compactErrorMessage(v.error_message)}
                          </div>
                        ) : null}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <div className="flex items-center justify-between mt-3 text-sm">
            <div>총 {videos.length}건 · {currentPage}/{totalPages} 페이지</div>
            <div className="flex gap-2">
              <button
                type="button"
                className="btn btn-secondary px-2 py-1 text-xs"
                disabled={currentPage <= 1}
                onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
              >
                이전
              </button>
              <button
                type="button"
                className="btn btn-secondary px-2 py-1 text-xs"
                disabled={currentPage >= totalPages}
                onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
              >
                다음
              </button>
            </div>
          </div>

          {summaryPanelOpen && selectedSummaryVideo ? (
            <div
              className="fixed inset-0 z-50 bg-black/20"
              onClick={() => {
                setSummaryPanelOpen(false);
                setSelectedSummaryVideo(null);
                setSummaryDetail(null);
                setSummaryLoading(false);
                setSummaryError("");
              }}
            >
              <div
                className="absolute right-0 top-0 w-full max-w-2xl h-full overflow-auto bg-white shadow-xl p-4 border-l"
                onClick={(e) => e.stopPropagation()}
              >
                <div className="flex items-center justify-between mb-3">
                  <h3 className="font-semibold">선택 영상 요약</h3>
                  <button
                    type="button"
                    className="btn btn-secondary"
                    onClick={() => {
                      setSummaryPanelOpen(false);
                      setSelectedSummaryVideo(null);
                      setSummaryDetail(null);
                      setSummaryLoading(false);
                      setSummaryError("");
                    }}
                  >
                    닫기
                  </button>
                </div>
                <div className="text-sm mb-3">
                  <div>제목: {selectedSummaryVideo.title || "-"}</div>
                  <div>게시일: {formatDate(selectedSummaryVideo.published_at || null)}</div>
                  <div>채널명: {selectedSummaryVideo.channel_name || "-"}</div>
                </div>
                {summaryLoading ? <div className="text-sm">요약을 불러오는 중입니다...</div> : null}
                {summaryError ? <div className="text-sm text-red-600">{summaryError}</div> : null}
                {!summaryLoading && !summaryError && !summaryDetail?.summary ? <div className="text-sm text-muted">저장된 요약이 없습니다.</div> : null}
                {!summaryLoading && summaryDetail && summaryDetail.has_content === false ? (
                  <div className="border rounded p-3 text-sm text-muted">
                    저장된 요약 내용이 없습니다. 요약 실행을 다시 진행해 주세요.
                  </div>
                ) : null}
                {!summaryLoading && summaryDetail?.summary && summaryDetail.has_content !== false ? (
                  <div className="space-y-3">
                    <div className="border rounded p-3">
                      <div className="font-semibold mb-1">전체 요약</div>
                      <div className="text-sm whitespace-pre-wrap">{normalizedSummary.summaryText}</div>
                      <div className="text-xs text-muted mt-2">
                        모델: {summaryDetail.summary.model_name || "-"} · 처리 시간: {formatElapsed(summaryDetail.summary.elapsed_seconds)} · chunk 수: {summaryDetail.summary.chunk_count ?? "-"}
                      </div>
                      <div className="text-xs text-muted mt-1">
                        품질 상태: {summaryDetail.summary.summary_quality_status ?? "-"} · 구조화: 핵심 {summaryDetail.summary.key_points_count ?? normalizedSummary.keyPoints.length}개 · 주제 {summaryDetail.summary.topic_summaries_count ?? normalizedSummary.topics.length}개 · 테마 {summaryDetail.summary.mentioned_themes_count ?? normalizedSummary.themeMentions.length}개 · 종목 {summaryDetail.summary.mentioned_stocks_count ?? normalizedSummary.stockMentions.length}개 · 리스크 {summaryDetail.summary.risk_points_count ?? normalizedSummary.riskPoints.length}개 · 재시도 {summaryDetail.summary.retry_count ?? 0}회
                      </div>
                      {summaryDetail.summary.summary_quality_status === "partial_failed" ? (
                        <div className="text-xs text-amber-700 mt-1">
                          구조화 요약 일부가 생성되지 않았습니다. 재요약을 권장합니다.
                        </div>
                      ) : null}
                      {summaryDetail.summary.summary_quality_message ? (
                        <div className="text-xs text-amber-700 mt-1">
                          품질 메시지: {summaryDetail.summary.summary_quality_message}
                        </div>
                      ) : null}
                    </div>
                    <div className="border rounded p-3">
                      <div className="font-semibold mb-1">핵심 포인트</div>
                      {normalizedSummary.keyPoints.length > 0 ? (
                        <ul className="text-sm list-disc pl-5">{normalizedSummary.keyPoints.map((x, i) => <li key={`${x}-${i}`}>{x}</li>)}</ul>
                      ) : <div className="text-sm text-muted">핵심 포인트가 없습니다.</div>}
                    </div>
                    <div className="border rounded p-3">
                      <div className="font-semibold mb-1">주제별 요약</div>
                      {normalizedSummary.topics.length > 0 ? (
                        <ul className="text-sm list-disc pl-5">{normalizedSummary.topics.map((t, idx) => <li key={`${t.topic_name}-${idx}`}>{t.topic_name}: {t.summary || "-"}</li>)}</ul>
                      ) : summaryDetail.topics.length > 0 ? (
                        <ul className="text-sm list-disc pl-5">{summaryDetail.topics.map((t) => <li key={t.id}>{t.topic_name}: {t.summary || "-"}</li>)}</ul>
                      ) : <div className="text-sm text-muted">주제별 요약이 없습니다.</div>}
                    </div>
                    <div className="border rounded p-3">
                      <div className="font-semibold mb-1">언급 테마</div>
                      <div className="text-sm">{normalizedSummary.themeMentions.join(", ") || "언급 테마가 없습니다."}</div>
                    </div>
                    <div className="border rounded p-3">
                      <div className="font-semibold mb-1">언급 종목</div>
                      <div className="text-sm">{normalizedSummary.stockMentions.join(", ") || "언급 종목이 없습니다."}</div>
                    </div>
                    <div className="border rounded p-3">
                      <div className="font-semibold mb-1">리스크 포인트</div>
                      {normalizedSummary.riskPoints.length > 0 ? (
                        <ul className="text-sm list-disc pl-5">{normalizedSummary.riskPoints.map((x, i) => <li key={`${x}-${i}`}>{x}</li>)}</ul>
                      ) : <div className="text-sm text-muted">리스크 포인트가 없습니다.</div>}
                    </div>
                  </div>
                ) : null}
              </div>
            </div>
          ) : null}
        </SectionCard>
      ) : null}
    </div>
  );
}

export default EconomicBriefingPage;
