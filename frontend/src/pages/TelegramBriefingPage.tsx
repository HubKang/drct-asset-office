import { FormEvent, Fragment, useEffect, useMemo, useState } from "react";
import PageHeader from "@/components/common/PageHeader";
import SectionCard from "@/components/common/SectionCard";
import { repositories } from "@/services";
import type { TelegramAuthStatus, TelegramItem, TelegramSource, TelegramSourceConnectionTest } from "@/types/telegram";

const tabs = ["채널 관리", "수집/메시지 목록"] as const;
const PAGE_SIZE = 20;

const summaryStatusLabelMap: Record<string, string> = {
  pending: "요약대기",
  summarized: "요약완료",
  failed: "요약실패",
  skipped: "요약제외",
};

const sentimentLabelMap: Record<string, string> = {
  positive: "긍정",
  neutral: "중립",
  negative: "부정",
  unknown: "미확인",
};

const riskLabelMap: Record<string, string> = {
  low: "낮음",
  medium: "보통",
  high: "높음",
  unknown: "미확인",
};

const messageTypeLabelMap: Record<string, string> = {
  stock_news: "종목뉴스",
  economic_news: "경제뉴스",
  theme_issue: "테마이슈",
  market_commentary: "시장논평",
  policy_issue: "정책이슈",
  disclosure_like: "공시유사",
  risk_issue: "리스크이슈",
  investment_opinion: "투자의견",
  channel_notice: "채널공지",
  advertisement: "광고",
  instruction_acknowledgment: "지시응답",
  unknown: "미분류",
};

function labelOf(map: Record<string, string>, value?: string | null) {
  const key = (value || "unknown").trim().toLowerCase();
  return map[key] || "미확인";
}

function parseJsonArray(value?: string | null): string[] {
  if (!value) return [];
  try {
    const parsed = JSON.parse(value);
    return Array.isArray(parsed) ? parsed.map((v) => String(v)).filter((v) => v.trim().length > 0) : [];
  } catch {
    return [];
  }
}

function isFallbackSummary(summaryText?: string | null, keyPoints?: string[]) {
  const text = (summaryText || "").trim();
  if (!text) return true;
  if (text === "확인 필요: 원문 기반 추가 검토가 필요합니다.") return true;
  if (text.startsWith("확인 필요:")) return true;
  if ((keyPoints || []).length === 1 && (keyPoints || [])[0] === "확인 필요") return true;
  return false;
}

function getDisplaySummaryText(item: TelegramItem): string {
  const raw = (item.summary_text || "").trim();
  if (!raw) return "";
  if (raw.startsWith("{") && raw.endsWith("}")) {
    try {
      const parsed = JSON.parse(raw) as Record<string, unknown>;
      const nested = String(parsed.summary_text || parsed.summary || "").trim();
      return nested || "요약 표시 형식 오류입니다. 재요약해 주세요.";
    } catch {
      return "요약 표시 형식 오류입니다. 재요약해 주세요.";
    }
  }
  return raw;
}

function stripUrls(text: string): string {
  return text.replace(/https?:\/\/\S+/gi, " ").replace(/\s+/g, " ").trim();
}

function isUrlOnlyText(text?: string | null): boolean {
  if (!text) return true;
  const noUrl = stripUrls(text);
  return noUrl.length < 20;
}

function isGenericTelegramTitle(title?: string | null): boolean {
  if (!title) return true;
  const normalized = title.replace(/\s+/g, "").toLowerCase();
  const genericPatterns = [
    "주식급등일보",
    "급등테마",
    "대장주탐색기",
    "koreanstocks",
    "telegram",
    "t.me",
    "naver",
    "네이버뉴스",
    "번개맞은뉴스",
    "faststocknews",
    "채널보기",
    "telegram:contact",
  ];
  return genericPatterns.some((pattern) => normalized.includes(pattern));
}

function getTelegramDisplayContent(item: TelegramItem): string {
  const title = (item.item_title || "").trim();
  const message = (item.message_text || "").trim();
  const url = (item.normalized_url || item.item_url || "").trim();
  const hasValidTitle = !!title && !isGenericTelegramTitle(title);
  const messageIsUrlOnly = isUrlOnlyText(message);

  // 주식급등일보 복구 핵심: 본문이 충분하면 본문 우선
  if (message && !messageIsUrlOnly) {
    return message.slice(0, 140);
  }

  // URL-only라면 유효한 제목 사용
  if (hasValidTitle) {
    return title;
  }

  if (message && !messageIsUrlOnly) {
    return message.slice(0, 140);
  }

  if (messageIsUrlOnly || url) {
    return "기사 제목 확인 필요";
  }

  return "내용 확인 필요";
}

function hasMeaningfulMessageType(value?: string | null): boolean {
  const v = (value || "").trim().toLowerCase();
  if (!v) return false;
  return !["unknown", "미확인", "미분류"].includes(v);
}

function TelegramBriefingPage() {
  const [tab, setTab] = useState<(typeof tabs)[number]>("채널 관리");
  const [sources, setSources] = useState<TelegramSource[]>([]);
  const [items, setItems] = useState<TelegramItem[]>([]);
  const [totalCount, setTotalCount] = useState(0);
  const [currentPage, setCurrentPage] = useState(1);
  const [selectedItemIds, setSelectedItemIds] = useState<number[]>([]);
  const [selectedDetailItemId, setSelectedDetailItemId] = useState<number | null>(null);
  const [isSummarizingSelected, setIsSummarizingSelected] = useState(false);
  const [summarizingItemId, setSummarizingItemId] = useState<number | null>(null);
  const [isQuerying, setIsQuerying] = useState(false);
  const [isCollectingAll, setIsCollectingAll] = useState(false);
  const [isCollectingSelected, setIsCollectingSelected] = useState(false);
  const [isDeletingSelected, setIsDeletingSelected] = useState(false);
  const [isAddingSource, setIsAddingSource] = useState(false);
  const [sourceActionLoading, setSourceActionLoading] = useState<Record<string, boolean>>({});
  const [message, setMessage] = useState("");
  const [collectionMode, setCollectionMode] = useState("");
  const [collectionError, setCollectionError] = useState("");
  const [collectionDiagnostics, setCollectionDiagnostics] = useState<Record<string, boolean>>({});
  const [telegramAuthStatus, setTelegramAuthStatus] = useState<TelegramAuthStatus | null>(null);
  const [isAuthChecking, setIsAuthChecking] = useState(false);
  const [isAuthStarting, setIsAuthStarting] = useState(false);
  const [isAuthSubmitting, setIsAuthSubmitting] = useState(false);
  const [authModalOpen, setAuthModalOpen] = useState(false);
  const [authStage, setAuthStage] = useState<"code_required" | "password_required" | "success" | "failed">("code_required");
  const [authCode, setAuthCode] = useState("");
  const [authPassword, setAuthPassword] = useState("");
  const [authMessage, setAuthMessage] = useState("");
  const [connectionTests, setConnectionTests] = useState<Record<number, TelegramSourceConnectionTest>>({});
  const [channelInputs, setChannelInputs] = useState<Record<number, string>>({});
  const [targetDate, setTargetDate] = useState(new Date().toISOString().slice(0, 10));
  const [sourceId, setSourceId] = useState("0");

  const [newSourceName, setNewSourceName] = useState("");
  const [newChannel, setNewChannel] = useState("");
  const [newMemo, setNewMemo] = useState("");

  const totalPages = useMemo(() => Math.max(1, Math.ceil(totalCount / PAGE_SIZE)), [totalCount]);
  const allCurrentPageSelected = useMemo(() => items.length > 0 && items.every((it) => selectedItemIds.includes(it.id)), [items, selectedItemIds]);
  const selectedDetailItem = useMemo(
    () => items.find((it) => it.id === selectedDetailItemId) ?? null,
    [items, selectedDetailItemId]
  );

  const loadSources = async () => {
    const data = await repositories.telegram.listSources(false);
    setSources(data);
    setChannelInputs((prev) => {
      const next = { ...prev };
      data.forEach((s) => {
        if (!next[s.id]) next[s.id] = s.channel_username;
      });
      return next;
    });
  };

  const loadAuthStatus = async () => {
    setIsAuthChecking(true);
    try {
      const status = await repositories.telegram.getAuthStatus();
      setTelegramAuthStatus(status);
    } finally {
      setIsAuthChecking(false);
    }
  };

  const loadItems = async (opts?: { page?: number; source?: string; date?: string }) => {
    const page = opts?.page ?? currentPage;
    const selectedSource = opts?.source ?? sourceId;
    const selectedDate = opts?.date ?? targetDate;
    const data = await repositories.telegram.listItems({
      source_id: selectedSource === "0" ? undefined : selectedSource,
      date_from: selectedDate,
      date_to: selectedDate,
      limit: PAGE_SIZE,
      offset: (page - 1) * PAGE_SIZE,
    });
    setItems(data.items);
    setTotalCount(data.total_count);
  };

  useEffect(() => {
    const initialize = async () => {
      await loadSources();
      await loadAuthStatus();
      await loadItems({ page: 1, source: "0", date: targetDate });
    };
    void initialize();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const onAddSource = async (e: FormEvent) => {
    e.preventDefault();
    if (!newSourceName.trim() || !newChannel.trim()) return;
    setIsAddingSource(true);
    try {
      await repositories.telegram.createSource({
        source_name: newSourceName.trim(),
        channel_username: newChannel.trim(),
        memo: newMemo.trim() || undefined,
        is_active: true,
      });
      setNewSourceName("");
      setNewChannel("");
      setNewMemo("");
      await loadSources();
      setMessage("채널이 추가되었습니다.");
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : "채널 추가에 실패했습니다.";
      setMessage(`채널 추가 실패: ${errorMessage}`);
    } finally {
      setIsAddingSource(false);
    }
  };

  const onCollectSelected = async () => {
    if (sourceId === "0") return;
    setIsCollectingSelected(true);
    try {
      const result = await repositories.telegram.collectByDate({
        source_id: Number(sourceId),
        target_date: targetDate,
        summarize_new_items: false,
        include_notice: false,
        include_advertisement: false,
      });
      setCollectionMode(result.source_mode);
      setCollectionError(result.error_message || "");
      setCollectionDiagnostics(result.diagnostics || {});
      await loadAuthStatus();
      setCurrentPage(1);
      setSelectedDetailItemId(null);
      setSelectedItemIds([]);
      setMessage(
        result.success
          ? `수집완료(실수집): mode=${result.source_mode} / 조회 ${result.fetched_message_count} / 신규 ${result.new_item_count} / 중복 ${result.duplicate_count} / 요약성공 ${result.summarized_count}`
          : `수집실패: mode=${result.source_mode} / 조회 ${result.fetched_message_count} / 신규 ${result.new_item_count} / 중복 ${result.duplicate_count}`
      );
      await loadItems({ page: 1, source: sourceId, date: targetDate });
      await loadSources();
    } finally {
      setIsCollectingSelected(false);
    }
  };

  const onCollectAll = async () => {
    setIsCollectingAll(true);
    try {
      const result = await repositories.telegram.collectAllByDate({
        target_date: targetDate,
        summarize_new_items: false,
        include_notice: false,
        include_advertisement: false,
      });
      setCollectionMode(result.source_mode);
      setCollectionError(result.error_message || "");
      setCollectionDiagnostics(result.diagnostics || {});
      await loadAuthStatus();
      setSourceId("0");
      setCurrentPage(1);
      setSelectedDetailItemId(null);
      setSelectedItemIds([]);
      setMessage(
        result.success
          ? `전체수집(실수집): mode=${result.source_mode} / 채널 ${result.source_count} / 조회 ${result.fetched_message_count} / 신규 ${result.new_item_count} / 중복 ${result.duplicate_count}`
          : `전체수집 실패: mode=${result.source_mode} / 채널 ${result.source_count} / 조회 ${result.fetched_message_count} / 신규 ${result.new_item_count} / 중복 ${result.duplicate_count}`
      );
      await loadItems({ page: 1, source: "0", date: targetDate });
      await loadSources();
    } finally {
      setIsCollectingAll(false);
    }
  };

  const onQueryItems = async () => {
    setIsQuerying(true);
    try {
      setCurrentPage(1);
      setSelectedDetailItemId(null);
      setSelectedItemIds([]);
      await loadItems({ page: 1 });
    } finally {
      setIsQuerying(false);
    }
  };

  const onToggleSourceActive = async (source: TelegramSource) => {
    const nextIsActive = source.is_active ? false : true;
    const loadingKey = `toggle:${source.id}`;
    setSourceActionLoading((prev) => ({ ...prev, [loadingKey]: true }));
    try {
      await repositories.telegram.updateSource(source.id, { is_active: nextIsActive });
      await loadSources();
      setMessage(`${source.source_name} 채널이 ${nextIsActive ? "활성화" : "비활성화"}되었습니다.`);
    } finally {
      setSourceActionLoading((prev) => ({ ...prev, [loadingKey]: false }));
    }
  };

  const onTestConnection = async (source: TelegramSource) => {
    const loadingKey = `test:${source.id}`;
    setSourceActionLoading((prev) => ({ ...prev, [loadingKey]: true }));
    try {
      const result = await repositories.telegram.testSourceConnection(source.id);
      setConnectionTests((prev) => ({ ...prev, [source.id]: result }));
      setMessage(`[${source.source_name}] ${result.message}`);
    } finally {
      setSourceActionLoading((prev) => ({ ...prev, [loadingKey]: false }));
    }
  };

  const onSaveChannelUsername = async (source: TelegramSource) => {
    const value = (channelInputs[source.id] || "").trim();
    if (!value) return;
    const loadingKey = `save:${source.id}`;
    setSourceActionLoading((prev) => ({ ...prev, [loadingKey]: true }));
    try {
      await repositories.telegram.updateSource(source.id, { channel_username: value });
      await loadSources();
      setMessage(`${source.source_name} 채널 username이 저장되었습니다.`);
    } finally {
      setSourceActionLoading((prev) => ({ ...prev, [loadingKey]: false }));
    }
  };

  const onToggleSelectAllCurrentPage = () => {
    if (allCurrentPageSelected) {
      const currentIds = new Set(items.map((it) => it.id));
      setSelectedItemIds((prev) => prev.filter((id) => !currentIds.has(id)));
      return;
    }
    const merged = new Set<number>(selectedItemIds);
    items.forEach((it) => merged.add(it.id));
    setSelectedItemIds(Array.from(merged));
  };

  const onToggleItemSelect = (itemId: number) => {
    setSelectedItemIds((prev) => (prev.includes(itemId) ? prev.filter((id) => id !== itemId) : [...prev, itemId]));
  };

  const onSummarizeSelected = async () => {
    if (selectedItemIds.length === 0) return;
    setIsSummarizingSelected(true);
    let success = 0;
    let failed = 0;
    try {
      for (const itemId of selectedItemIds) {
        try {
          const result = await repositories.telegram.summarizeItem(itemId);
          setItems((prev) =>
            prev.map((it) =>
              it.id === itemId
                ? {
                    ...it,
                    summary_status: result.summary_status,
                    summary_has_content: result.summary_has_content,
                    summary_text: result.summary_text,
                    summary_error_message: result.summary_error_message ?? null,
                  }
                : it
            )
          );
          success += 1;
        } catch {
          setItems((prev) =>
            prev.map((it) =>
              it.id === itemId
                ? {
                    ...it,
                    summary_status: "failed",
                    summary_has_content: 0,
                    summary_error_message: it.summary_error_message || "SUMMARIZE_REQUEST_FAILED",
                  }
                : it
            )
          );
          failed += 1;
        }
      }
      await loadItems({ page: currentPage });
      setSelectedItemIds([]);
      setMessage(`선택 메시지 LLM 요약이 완료되었습니다. (성공 ${success} / 실패 ${failed})`);
    } finally {
      setIsSummarizingSelected(false);
    }
  };

  const onSummarizeOne = async (itemId: number) => {
    setSummarizingItemId(itemId);
    try {
      await repositories.telegram.summarizeItem(itemId);
      await loadItems({ page: currentPage });
      setSelectedDetailItemId(itemId);
      setMessage("메시지 요약이 완료되었습니다.");
      const existsInPage = items.some((it) => it.id === itemId);
      if (!existsInPage) {
        setSelectedDetailItemId(null);
      } else {
        setSelectedDetailItemId(itemId);
      }
    } finally {
      setSummarizingItemId(null);
    }
  };

  const onMovePage = async (nextPage: number) => {
    if (nextPage < 1 || nextPage > totalPages) return;
    setCurrentPage(nextPage);
    setSelectedDetailItemId(null);
    setSelectedItemIds([]);
    await loadItems({ page: nextPage });
  };

  const onToggleDetailPanel = (itemId: number) => {
    setSelectedDetailItemId((prev) => (prev === itemId ? null : itemId));
  };

  const onDeleteSelected = async () => {
    if (selectedItemIds.length === 0) return;
    const ok = window.confirm(`선택한 ${selectedItemIds.length}건을 삭제할까요? 삭제 후 복구할 수 없습니다.`);
    if (!ok) return;
    setIsDeletingSelected(true);
    try {
      const result = await repositories.telegram.deleteItems(selectedItemIds);
      setSelectedDetailItemId(null);
      setSelectedItemIds([]);

      const shouldMovePrev = items.length === result.deleted_count && currentPage > 1;
      const nextPage = shouldMovePrev ? currentPage - 1 : currentPage;
      setCurrentPage(nextPage);
      await loadItems({ page: nextPage });
      setMessage(`삭제 완료: 요청 ${result.requested_count}건 / 삭제 ${result.deleted_count}건`);
    } finally {
      setIsDeletingSelected(false);
    }
  };

  const canOpenAuthFlow = !telegramAuthStatus?.authorized || collectionMode === "not_connected" || collectionError.includes("AUTH_REQUIRED");

  const onStartTelegramAuth = async () => {
    setIsAuthStarting(true);
    try {
      const result = await repositories.telegram.startAuth();
      setAuthMessage(result.message || "");
      if (result.authorized) {
        setAuthStage("success");
        setAuthModalOpen(true);
        await loadAuthStatus();
        setMessage("Telegram 인증이 완료되었습니다. 이제 실제 채널 메시지를 수집할 수 있습니다.");
        return;
      }
      setAuthStage(result.auth_stage === "password_required" ? "password_required" : "code_required");
      setAuthModalOpen(true);
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : "Telegram 인증 시작에 실패했습니다.";
      setAuthStage("failed");
      setAuthMessage(errorMessage);
      setAuthModalOpen(true);
    } finally {
      setIsAuthStarting(false);
    }
  };

  const resetAuthInputs = () => {
    setAuthCode("");
    setAuthPassword("");
  };

  const closeAuthModal = () => {
    setAuthModalOpen(false);
    setAuthStage("code_required");
    setAuthMessage("");
    resetAuthInputs();
  };

  const onVerifyAuthCode = async () => {
    if (!authCode.trim()) return;
    setIsAuthSubmitting(true);
    try {
      const result = await repositories.telegram.verifyAuthCode(authCode.trim());
      setAuthMessage(result.message || "");
      if (result.success && result.authorized) {
        setAuthStage("success");
        resetAuthInputs();
        await loadAuthStatus();
        setMessage("Telegram 인증이 완료되었습니다. 이제 실제 채널 메시지를 수집할 수 있습니다.");
        return;
      }
      if (result.auth_stage === "password_required") {
        setAuthStage("password_required");
        return;
      }
      setAuthStage("failed");
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : "인증 코드 검증에 실패했습니다.";
      setAuthStage("failed");
      setAuthMessage(errorMessage);
    } finally {
      setIsAuthSubmitting(false);
    }
  };

  const onVerifyAuthPassword = async () => {
    if (!authPassword.trim()) return;
    setIsAuthSubmitting(true);
    try {
      const result = await repositories.telegram.verifyAuthPassword(authPassword.trim());
      setAuthMessage(result.message || "");
      if (result.success && result.authorized) {
        setAuthStage("success");
        resetAuthInputs();
        await loadAuthStatus();
        setMessage("Telegram 인증이 완료되었습니다. 이제 실제 채널 메시지를 수집할 수 있습니다.");
        return;
      }
      setAuthStage("failed");
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : "2FA 비밀번호 검증에 실패했습니다.";
      setAuthStage("failed");
      setAuthMessage(errorMessage);
    } finally {
      setIsAuthSubmitting(false);
    }
  };

  const aiActionLabel = (summaryStatus?: string | null) => {
    const key = (summaryStatus || "").toLowerCase();
    if (key === "summarized") return "재요약";
    if (key === "failed") return "재시도";
    return "요약";
  };

  const aiProcessLabel = (item: TelegramItem) => {
    const key = (item.summary_status || "").toLowerCase();
    const keyPoints = parseJsonArray(item.key_points_json);
    const fallback = isFallbackSummary(item.summary_text, keyPoints);
    if (key === "summarized" && Number(item.summary_has_content) === 1 && !fallback) return "AI완료";
    if (key === "pending") return "대기";
    if (key === "failed") return "실패";
    if (key === "skipped") return "제외";
    if (key === "summarized" && fallback) return "실패";
    return "미확인";
  };

  const aiProcessBadgeClass = (item: TelegramItem) => {
    const key = aiProcessLabel(item);
    if (key === "AI완료") return "bg-emerald-100 text-emerald-700";
    if (key === "실패") return "bg-rose-100 text-rose-700";
    if (key === "제외") return "bg-amber-100 text-amber-700";
    return "bg-slate-100 text-slate-700";
  };

  return (
    <div className="space-y-4">
      <PageHeader title="텔레그램 브리핑" description="텔레그램 채널 기반 투자 참고 메시지 수집/요약/조회" />
      <SectionCard title="">
        <div className="border-b border-slate-200">
          <nav className="flex flex-wrap items-center gap-6">
          {tabs.map((t) => (
              <button
                key={t}
                type="button"
                className={`border-b-2 bg-transparent pb-3 text-sm transition-colors duration-150 ${
                  tab === t
                    ? "border-slate-900 font-semibold text-slate-900"
                    : "border-transparent font-medium text-slate-500 hover:text-slate-900"
                }`}
                onClick={() => setTab(t)}
              >
                {t}
              </button>
          ))}
          </nav>
        </div>
      </SectionCard>

      {message ? <p className="text-sm text-emerald-700">{message}</p> : null}
      {collectionMode ? (
        <p className="text-sm text-slate-700">
          source_mode: <b>{collectionMode}</b>{" "}
          {collectionMode === "real"
            ? "실제 텔레그램 채널에서 수집된 결과입니다."
            : collectionMode === "mock"
              ? "개발용 mock 데이터 모드입니다. 실제 텔레그램 수집 결과가 아닙니다."
              : "Telegram 연결 실패로 실제 수집이 수행되지 않았습니다."}
        </p>
      ) : null}
      {collectionError ? <p className="text-sm text-rose-700">오류: {collectionError}</p> : null}
      {Object.keys(collectionDiagnostics).length > 0 ? (
        <p className="text-xs text-slate-600">
          diagnostics: api_id={String(!!collectionDiagnostics.has_api_id)} / api_hash={String(!!collectionDiagnostics.has_api_hash)} / session={String(!!collectionDiagnostics.has_session)} / channel_resolved={String(!!collectionDiagnostics.channel_resolved)}
        </p>
      ) : null}

      {tab === "채널 관리" ? (
        <SectionCard title="채널 관리">
          <form className="grid grid-cols-1 gap-2 md:grid-cols-4" onSubmit={onAddSource}>
            <input className="input-control" placeholder="채널명" value={newSourceName} onChange={(e) => setNewSourceName(e.target.value)} />
            <input className="input-control" placeholder="@username 또는 invite link" value={newChannel} onChange={(e) => setNewChannel(e.target.value)} />
            <input className="input-control" placeholder="메모" value={newMemo} onChange={(e) => setNewMemo(e.target.value)} />
            <button
              type="submit"
              className={`btn w-auto justify-self-start px-6 transition-all duration-150 active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-60 ${isAddingSource ? "bg-slate-900 text-white" : "btn-primary"}`}
              disabled={isAddingSource}
            >
              {isAddingSource ? "추가 중..." : "채널 추가"}
            </button>
          </form>
          <div className="table-shell mt-3">
            <table className="data-table min-w-[1300px]"><thead><tr><th>ID</th><th>채널명</th><th>username/link</th><th>활성</th><th>마지막 수집</th><th>메모</th><th>접근 테스트</th><th>관리</th></tr></thead><tbody>
              {sources.map((s) => (
                <tr key={s.id}>
                  <td>{s.id}</td><td>{s.source_name}</td>
                  <td>
                    <div className="flex gap-2">
                      <input className="input-control min-w-[220px]" value={channelInputs[s.id] || ""} onChange={(e) => setChannelInputs((prev) => ({ ...prev, [s.id]: e.target.value }))} />
                      <button
                        type="button"
                        className={`btn transition-all duration-150 active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-60 ${sourceActionLoading[`save:${s.id}`] ? "bg-slate-800 text-white" : "btn-secondary"}`}
                        onClick={() => void onSaveChannelUsername(s)}
                        disabled={!!sourceActionLoading[`save:${s.id}`]}
                      >
                        {sourceActionLoading[`save:${s.id}`] ? "저장 중..." : "저장"}
                      </button>
                    </div>
                  </td>
                  <td>{s.is_active ? "Y" : "N"}</td><td>{s.last_collected_at || "-"}</td><td>{s.memo || "-"}</td>
                  <td>
                    <div className="space-y-1">
                      <button
                        type="button"
                        className={`btn transition-all duration-150 active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-60 ${sourceActionLoading[`test:${s.id}`] ? "bg-slate-800 text-white" : "btn-secondary"}`}
                        onClick={() => void onTestConnection(s)}
                        disabled={!!sourceActionLoading[`test:${s.id}`]}
                      >
                        {sourceActionLoading[`test:${s.id}`] ? "테스트 중..." : "접근 테스트"}
                      </button>
                      {connectionTests[s.id] ? <p className="text-xs">{connectionTests[s.id].source_mode} / connected:{String(connectionTests[s.id].telegram_connected)} / session:{String(connectionTests[s.id].session_exists)} / access:{String(connectionTests[s.id].channel_accessible)}</p> : null}
                    </div>
                  </td>
                  <td className="space-x-2">
                    <button
                      type="button"
                      className={`btn transition-all duration-150 active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-60 ${sourceActionLoading[`toggle:${s.id}`] ? "bg-slate-800 text-white" : "btn-secondary"}`}
                      onClick={() => void onToggleSourceActive(s)}
                      disabled={!!sourceActionLoading[`toggle:${s.id}`]}
                    >
                      {sourceActionLoading[`toggle:${s.id}`] ? "처리 중..." : s.is_active ? "비활성화" : "활성화"}
                    </button>
                    <button
                      type="button"
                      className={`btn transition-all duration-150 active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-60 ${sourceActionLoading[`delete:${s.id}`] ? "bg-rose-700 text-white" : "btn-danger"}`}
                      onClick={async () => {
                        const key = `delete:${s.id}`;
                        setSourceActionLoading((prev) => ({ ...prev, [key]: true }));
                        try {
                          await repositories.telegram.deleteSource(s.id);
                          await loadSources();
                        } finally {
                          setSourceActionLoading((prev) => ({ ...prev, [key]: false }));
                        }
                      }}
                      disabled={!!sourceActionLoading[`delete:${s.id}`]}
                    >
                      {sourceActionLoading[`delete:${s.id}`] ? "삭제 중..." : "삭제"}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody></table>
          </div>
        </SectionCard>
      ) : null}

      {tab === "수집/메시지 목록" ? (
        <div className="space-y-4">
          <SectionCard title="수집 및 조회 조건">
            <div className="flex flex-nowrap items-center gap-2 overflow-x-auto">
              <input
                type="date"
                className="input-control !w-[150px] shrink-0"
                value={targetDate}
                onChange={(e) => {
                  setTargetDate(e.target.value);
                  setCurrentPage(1);
                }}
              />
              <select
                className="select-control !w-[170px] shrink-0"
                value={sourceId}
                onChange={(e) => {
                  setSourceId(e.target.value);
                  setCurrentPage(1);
                }}
              >
                <option value="0">전체 채널</option>
                {sources.map((s) => <option key={s.id} value={String(s.id)}>{s.source_name}</option>)}
              </select>
              <div className="flex flex-nowrap items-center gap-2">
                <button
                  type="button"
                  className={`btn w-auto shrink-0 whitespace-nowrap px-4 transition-all duration-150 active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-60 ${isQuerying ? "bg-slate-800 text-white" : "btn-secondary"}`}
                  onClick={() => void onQueryItems()}
                  disabled={isQuerying || isCollectingAll || isCollectingSelected || isDeletingSelected}
                >
                  {isQuerying ? "조회 중..." : "조회"}
                </button>
                <button
                  type="button"
                  className={`btn w-auto shrink-0 whitespace-nowrap px-4 transition-all duration-150 active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-60 ${isCollectingAll ? "bg-slate-800 text-white" : "btn-secondary"}`}
                  onClick={() => void onCollectAll()}
                  disabled={isCollectingAll || isCollectingSelected || isQuerying || isDeletingSelected}
                >
                  {isCollectingAll ? "전체 수집 중..." : "전체 활성 채널 수집"}
                </button>
                <button
                  type="button"
                  className={`btn w-auto shrink-0 whitespace-nowrap px-4 transition-all duration-150 active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-60 ${isCollectingSelected ? "bg-slate-900 text-white" : "btn-primary"}`}
                  onClick={() => void onCollectSelected()}
                  disabled={sourceId === "0" || isCollectingSelected || isCollectingAll || isQuerying || isDeletingSelected}
                >
                  {isCollectingSelected ? "수집 중..." : "선택 채널 수집"}
                </button>
                <button
                  type="button"
                  className={`btn w-auto shrink-0 whitespace-nowrap px-4 transition-all duration-150 active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-60 ${isAuthStarting ? "bg-slate-800 text-white" : "btn-secondary"}`}
                  onClick={() => void onStartTelegramAuth()}
                  disabled={isAuthStarting || isAuthChecking || isAuthSubmitting || !canOpenAuthFlow}
                >
                  {isAuthStarting ? "인증 시작 중..." : "Telegram 인증"}
                </button>
              </div>
            </div>
            <p className="mt-2 text-xs text-slate-600">수집이 완료되었습니다. 아래 수집 메시지 목록에서 상세 내용을 확인하세요.</p>
            {telegramAuthStatus ? (
              <p className="mt-1 text-xs text-slate-600">
                인증상태: authorized={String(telegramAuthStatus.authorized)} / session={String(telegramAuthStatus.has_session)} / mode={telegramAuthStatus.source_mode}
              </p>
            ) : null}
          </SectionCard>

          <SectionCard title="수집 메시지 목록">
            <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
              <p className="text-sm text-slate-700">총 {totalCount}건 | {currentPage} / {totalPages} 페이지 | 선택 {selectedItemIds.length}건</p>
              <div className="flex gap-2">
                <button type="button" className="btn btn-secondary" onClick={() => void onSummarizeSelected()} disabled={selectedItemIds.length === 0 || isSummarizingSelected}>
                  {isSummarizingSelected ? "요약 중..." : "선택 메시지 LLM 요약"}
                </button>
                <button
                  type="button"
                  className={`btn transition-all duration-150 active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-60 ${isDeletingSelected ? "bg-rose-700 text-white" : "btn-danger"}`}
                  onClick={() => void onDeleteSelected()}
                  disabled={selectedItemIds.length === 0 || isSummarizingSelected || isDeletingSelected || isQuerying || isCollectingAll || isCollectingSelected}
                >
                  {isDeletingSelected ? "삭제 중..." : "삭제"}
                </button>
              </div>
            </div>
            <div className={`grid grid-cols-1 gap-4 ${selectedDetailItem ? "xl:grid-cols-[minmax(0,1fr)_420px]" : ""}`}>
              <div className="min-w-0 overflow-x-auto">
                <div className="table-shell">
                <table className="data-table min-w-[1450px]">
                <thead>
                  <tr>
                    <th><input type="checkbox" checked={allCurrentPageSelected} onClick={(e) => e.stopPropagation()} onChange={onToggleSelectAllCurrentPage} /></th>
                    <th>AI처리</th><th>일자</th><th>채널</th><th>내용</th><th>태그</th><th>점수</th><th>감성</th><th>위험</th><th>이벤트</th>
                  </tr>
                </thead>
                <tbody>
                  {items.map((it) => {
                    const keyPoints = parseJsonArray(it.key_points_json);
                    const isSelected = selectedDetailItemId === it.id;
                    return (
                      <Fragment key={it.id}>
                        <tr
                          className={`cursor-pointer transition-colors duration-150 hover:bg-slate-50 ${isSelected ? "bg-blue-100/70" : ""}`}
                          onClick={() => onToggleDetailPanel(it.id)}
                        >
                          <td><input type="checkbox" checked={selectedItemIds.includes(it.id)} onClick={(e) => e.stopPropagation()} onChange={() => onToggleItemSelect(it.id)} /></td>
                          <td>
                            <div className="flex items-center gap-2 whitespace-nowrap">
                              <span className={`rounded-md px-2 py-1 text-xs ${aiProcessBadgeClass(it)}`}>{aiProcessLabel(it)}</span>
                                <button
                                  type="button"
                                  className={`btn px-2 py-1 text-xs transition-all duration-150 active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-60 ${summarizingItemId === it.id ? "bg-slate-800 text-white" : "btn-secondary"}`}
                                  disabled={summarizingItemId === it.id || isSummarizingSelected || isDeletingSelected}
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    void onSummarizeOne(it.id);
                                }}
                              >
                                {summarizingItemId === it.id ? "요약 중..." : aiActionLabel(it.summary_status)}
                              </button>
                            </div>
                          </td>
                          <td>{it.message_date}</td>
                          <td className="min-w-[110px]">{it.source_name}</td>
                          <td className="max-w-[640px]"><div className="cell-clamp-2">{getTelegramDisplayContent(it)}</div></td>
                          <td>{it.tag || "-"}</td>
                          <td>{it.score}</td>
                          <td>{labelOf(sentimentLabelMap, it.sentiment)}</td>
                          <td>{labelOf(riskLabelMap, it.risk_level)}</td>
                          <td>{it.event_type}</td>
                        </tr>
                      </Fragment>
                    );
                  })}
                </tbody>
                </table>
                </div>
              </div>

              {selectedDetailItem ? (
                <aside className="self-start rounded-xl border bg-white p-4 text-sm text-slate-700 xl:sticky xl:top-24 xl:max-h-[calc(100vh-140px)] xl:overflow-y-auto">
                  <div className="mb-3 flex items-center justify-between">
                    <p className="font-semibold text-slate-900">AI 요약 상세</p>
                    <button type="button" className="btn btn-secondary px-2 py-1 text-xs" onClick={() => setSelectedDetailItemId(null)}>닫기</button>
                  </div>
                  <p className="mb-2 text-xs">
                    일자: {selectedDetailItem.message_date} | 채널: {selectedDetailItem.source_name}
                    {hasMeaningfulMessageType(selectedDetailItem.message_type) ? ` | 유형: ${labelOf(messageTypeLabelMap, selectedDetailItem.message_type)}` : ""}
                  </p>
                  {!!selectedDetailItem.item_title && !isGenericTelegramTitle(selectedDetailItem.item_title) ? (
                    <p className="mb-2 rounded-md bg-slate-50 px-2 py-1 text-xs">
                      제목: {selectedDetailItem.item_title}
                    </p>
                  ) : null}
                  <p className="mb-3 text-xs">
                    상태: {aiProcessLabel(selectedDetailItem)} | 태그: {selectedDetailItem.tag || "-"} | 점수: {selectedDetailItem.score} | 감성: {labelOf(sentimentLabelMap, selectedDetailItem.sentiment)} | 위험: {labelOf(riskLabelMap, selectedDetailItem.risk_level)} | 이벤트: {selectedDetailItem.event_type}
                  </p>
                  <p className="mb-2 font-medium text-slate-900">AI 요약</p>
                  <p className="mb-3 whitespace-pre-wrap">
                    {(() => {
                      const keyPoints = parseJsonArray(selectedDetailItem.key_points_json);
                      const displaySummary = getDisplaySummaryText(selectedDetailItem);
                      if (selectedDetailItem.summary_status === "failed" || isFallbackSummary(displaySummary, keyPoints)) return "AI 요약에 실패했습니다. 재시도해 주세요.";
                      if (selectedDetailItem.summary_status === "pending") return "AI 요약 대기 상태입니다.";
                      return displaySummary || "아직 AI 요약이 완료되지 않았습니다.";
                    })()}
                  </p>
                  {selectedDetailItem.summary_status === "failed" && selectedDetailItem.summary_error_message ? (
                    <p className="mb-3 rounded-md bg-rose-50 px-2 py-1 text-xs text-rose-700">
                      실패 사유: {selectedDetailItem.summary_error_message}
                    </p>
                  ) : null}
                  <p className="mb-1 font-medium text-slate-900">핵심 포인트</p>
                  {(() => {
                    const keyPoints = parseJsonArray(selectedDetailItem.key_points_json);
                    return keyPoints.length > 0 ? (
                      <ul className="mb-3 list-disc pl-5">
                        {keyPoints.map((point, idx) => <li key={`${selectedDetailItem.id}-${idx}`}>{point}</li>)}
                      </ul>
                    ) : (
                      <p className="mb-3 text-xs text-slate-500">핵심 포인트 없음</p>
                    );
                  })()}
                  <p className="mb-1 font-medium text-slate-900">원문</p>
                  <pre className="mb-3 max-h-44 overflow-auto whitespace-pre-wrap rounded-md bg-slate-50 p-2 text-xs">{selectedDetailItem.message_text || "원문이 없습니다."}</pre>
                  {isUrlOnlyText(selectedDetailItem.message_text) && !selectedDetailItem.item_title ? (
                    <p className="mb-2 text-xs text-amber-700">기사 제목을 가져오지 못했습니다. 원문 링크를 확인해 주세요.</p>
                  ) : null}
                  {(selectedDetailItem.item_url || selectedDetailItem.normalized_url) ? (
                    <a
                      href={selectedDetailItem.item_url || selectedDetailItem.normalized_url || "#"}
                      target="_blank"
                      rel="noreferrer"
                      className="text-xs text-blue-600 underline"
                      onClick={(e) => e.stopPropagation()}
                    >
                      원문 링크 열기
                    </a>
                  ) : null}
                  <p className="mt-3 text-xs text-slate-500">텔레그램 정보는 비공식 참고자료이며, 공시/뉴스/가격 데이터와 교차 확인이 필요합니다.</p>
                </aside>
              ) : null}
            </div>
            <div className="mt-3 flex items-center justify-center gap-2">
              <button type="button" className="btn btn-secondary" onClick={() => void onMovePage(currentPage - 1)} disabled={currentPage <= 1}>이전</button>
              <span className="text-sm text-slate-700">{currentPage} / {totalPages}</span>
              <button type="button" className="btn btn-secondary" onClick={() => void onMovePage(currentPage + 1)} disabled={currentPage >= totalPages}>다음</button>
            </div>
          </SectionCard>
        </div>
      ) : null}

      {authModalOpen ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 p-4">
          <div className="w-full max-w-md rounded-xl bg-white p-4 shadow-xl">
            <div className="mb-3 flex items-center justify-between">
              <p className="text-base font-semibold text-slate-900">Telegram 인증</p>
              <button type="button" className="btn btn-secondary px-2 py-1 text-xs" onClick={closeAuthModal}>닫기</button>
            </div>
            <p className="mb-3 text-sm text-slate-700">{authMessage || "Telegram 인증을 진행해 주세요."}</p>

            {authStage === "code_required" ? (
              <div className="space-y-2">
                <input
                  className="input-control"
                  placeholder="인증 코드"
                  value={authCode}
                  onChange={(e) => setAuthCode(e.target.value)}
                />
                <button type="button" className="btn btn-primary w-full" disabled={isAuthSubmitting || !authCode.trim()} onClick={() => void onVerifyAuthCode()}>
                  {isAuthSubmitting ? "검증 중..." : "인증 완료"}
                </button>
              </div>
            ) : null}

            {authStage === "password_required" ? (
              <div className="space-y-2">
                <input
                  type="password"
                  className="input-control"
                  placeholder="2단계 인증 비밀번호"
                  value={authPassword}
                  onChange={(e) => setAuthPassword(e.target.value)}
                />
                <button type="button" className="btn btn-primary w-full" disabled={isAuthSubmitting || !authPassword.trim()} onClick={() => void onVerifyAuthPassword()}>
                  {isAuthSubmitting ? "검증 중..." : "비밀번호 인증"}
                </button>
              </div>
            ) : null}

            {authStage === "success" ? (
              <div className="space-y-2">
                <p className="rounded-md bg-emerald-50 px-3 py-2 text-sm text-emerald-700">Telegram 인증이 완료되었습니다.</p>
                <button type="button" className="btn btn-primary w-full" onClick={closeAuthModal}>확인</button>
              </div>
            ) : null}

            {authStage === "failed" ? (
              <div className="space-y-2">
                <p className="rounded-md bg-rose-50 px-3 py-2 text-sm text-rose-700">인증에 실패했습니다. 다시 시도해 주세요.</p>
                <button type="button" className="btn btn-secondary w-full" onClick={() => setAuthStage("code_required")}>코드 입력으로 돌아가기</button>
              </div>
            ) : null}
          </div>
        </div>
      ) : null}
    </div>
  );
}

export default TelegramBriefingPage;



