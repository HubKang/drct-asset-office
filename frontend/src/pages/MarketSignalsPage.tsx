import { useEffect, useMemo, useState } from "react";
import PageHeader from "@/components/common/PageHeader";
import SectionCard from "@/components/common/SectionCard";
import { repositories } from "@/services";
import { MARKET_INDICATOR_GROUPS, matchesMarketIndicatorGroup, type MarketIndicatorGroupCode } from "@/utils/marketIndicatorGroups";
import type {
  MarketSignalCatalogItem,
  MarketSignalCatalogResponse,
  MarketSignalCondition,
  MarketSignalDefinition,
  MarketSignalIndicatorCatalogItem,
  MarketSignalEvaluationHistory,
  MarketSignalModelProfile,
  MarketSignalOverview,
  MarketSignalRuleTemplate,
} from "@/types/marketSignal";

type MainTab = "today" | "signals" | "phenomena" | "studio" | "learning";
type SignalSubTab = "single" | "composite";
type StudioSubTab = "simple" | "templates" | "gpt" | "advanced";
type OperationStatus = "ALL" | "NOT_REGISTERED" | "DRAFT" | "ACTIVE" | "INACTIVE" | "DATA_INSUFFICIENT";
type ValidationFilter = "ALL" | "UNVALIDATED" | "NEEDS_REVISION" | "VALIDATED" | "ACTIVATION_READY";
type HistoryFilter = "ALL" | "TRANSITION" | "TREND_WEAKENING" | "BREAK_CANDIDATE" | "BREAK_CONFIRMED" | "FALSE_BREAK" | "REVERSAL_CONFIRMED" | "ERROR";

const STATUS_LABELS: Record<string, string> = {
  DRAFT: "초안",
  ACTIVE: "운영",
  INACTIVE: "중지",
  WATCH: "시작 조건",
  CONFIRMED: "확인",
  ACTIVE_EVAL: "확인",
  STRENGTHENING: "강화",
  WEAKENING: "약화",
  TREND_INTACT: "추세 유지",
  TREND_WEAKENING: "추세 약화",
  BREAK_CANDIDATE: "추세 이탈 후보",
  BREAK_CONFIRMED: "추세 이탈 확인",
  REVERSAL_CONFIRMED: "반전 확인",
  FALSE_BREAK: "일시 이탈 후 복귀",
  TREND_RESUMED: "기존 추세 재개",
  SIDEWAYS: "횡보",
  ERROR: "평가 오류",
  UP_TREND: "상승 추세",
  DOWN_TREND: "하락 추세",
  UNSTABLE: "불안정",
  INSUFFICIENT_DATA: "데이터 부족",
  DATA_INSUFFICIENT: "데이터 부족",
  NOT_EVALUATED: "미평가",
  CANDIDATE: "확인 진행",
  OBSERVED: "징후 관찰",
  CONFIRMING: "확인 진행",
  RELEASED: "현상 해제",
  OPPOSED: "반대 근거 우세",
  INVALIDATED: "무효화",
  SIGNAL_AVAILABLE: "생성 가능",
  SIGNAL_NOT_REGISTERED: "미등록",
  SIGNAL_DRAFT: "초안",
  SIGNAL_ACTIVE: "운영",
  REVIEW_REQUIRED: "검토 필요",
  EXCLUDED: "제외",
  SIGNAL_READY: "데이터 준비 완료",
  UNVALIDATED: "미검증",
  NEEDS_REVISION: "수정 필요",
  VALIDATED: "검증 완료",
  ACTIVATION_READY: "활성화 준비",
};

const SIGNAL_READINESS_FILTERS = [
  ["ALL", "전체"],
  ["NOT_REGISTERED", "미등록"],
  ["DRAFT", "초안"],
  ["ACTIVE", "운영"],
  ["INACTIVE", "중지"],
  ["DATA_INSUFFICIENT", "데이터 부족"],
] satisfies [OperationStatus, string][];

const VALIDATION_FILTERS = [
  ["ALL", "전체"],
  ["UNVALIDATED", "미검증"],
  ["NEEDS_REVISION", "수정 필요"],
  ["VALIDATED", "검증 완료"],
  ["ACTIVATION_READY", "활성화 준비"],
] satisfies [ValidationFilter, string][];

const STAGE_STEPS = ["1차 추세 확인", "2차 초안 생성", "3차 과거 검증", "4차 운영 활성화"] as const;
const PREVIEW_PERIODS = ["1M", "3M", "6M", "1Y", "3Y", "ALL"] as const;
const PREVIEW_SETTING_FIELDS = [
  ["short_window", "단기 관찰 기간"],
  ["medium_window", "중기 관찰 기간"],
  ["trend_window", "추세 분석 기간"],
  ["channel_multiplier", "채널 배수"],
  ["minimum_break_persistence", "추세 이탈 확인 기간"],
  ["false_break_window", "일시 이탈 후 복귀 확인 기간"],
  ["reversal_persistence", "반전 확인 기간"],
] as const;

const ROLES: MarketSignalCondition["condition_role"][] = ["TRIGGER", "REQUIRED", "CONFIRM", "CONTEXT", "OPPOSING", "INVALIDATION"];
const ROLE_LABELS: Record<string, string> = { TRIGGER: "시작 조건", REQUIRED: "시작 조건", CONFIRM: "지지 확인", CONTEXT: "배경 조건", OPPOSING: "반대 근거", INVALIDATION: "무효화 조건" };
const TRANSFORMS = ["RAW_VALUE", "SLOPE", "TURN_UP", "TURN_DOWN", "TREND_STATE", "TREND_STRENGTH", "CHANNEL_POSITION", "BREAK_CONFIRMED_UP", "BREAK_CONFIRMED_DOWN", "FALSE_BREAK_UP", "FALSE_BREAK_DOWN"];
const OPERATORS = [">", ">=", "<", "<=", "=", "!=", "=="];

function label(value: unknown) {
  return STATUS_LABELS[String(value ?? "").toUpperCase()] ?? String(value ?? "-");
}

function num(value: unknown, digits = 2) {
  if (typeof value !== "number" || Number.isNaN(value)) return "-";
  return Math.abs(value) >= 100 ? value.toLocaleString(undefined, { maximumFractionDigits: digits }) : value.toFixed(digits);
}

function cardClass(status: unknown) {
  return `market-signal-insight-card status-${String(status ?? "unknown").toLowerCase()}`;
}

function Sparkline({ points, markers }: { points?: Record<string, unknown>[]; markers?: string[] }) {
  const data = (points ?? []).filter((point) => typeof point.x === "number" && typeof point.y === "number");
  if (!data.length) return <div className="market-signal-sparkline-empty">데이터 부족</div>;
  const path = data.map((point, idx) => `${idx === 0 ? "M" : "L"} ${Number(point.x) * 100} ${Number(point.y) * 42 + 4}`).join(" ");
  return (
    <div className="market-signal-sparkline" title={(markers ?? []).join(", ") || "최근 흐름"}>
      <svg viewBox="0 0 100 50" preserveAspectRatio="none" aria-hidden="true">
        <line x1="0" x2="100" y1="25" y2="25" />
        <path d={path} />
        <circle cx={Number(data[data.length - 1].x) * 100} cy={Number(data[data.length - 1].y) * 42 + 4} r="2.4" />
      </svg>
      {markers?.length ? <span>{markers[0]}</span> : null}
    </div>
  );
}

function TrendPreviewChart({ rows, period, eventRows }: { rows?: Record<string, unknown>[]; period?: Record<string, unknown>; eventRows?: Record<string, unknown>[] }) {
  const data = (rows ?? []).filter((row) => typeof row.value === "number");
  if (!data.length) return <div className="market-signal-drawer-empty">차트 데이터가 없습니다.</div>;
  const values = data.flatMap((row) => [row.value, row.center, row.upper, row.lower].filter((value): value is number => typeof value === "number"));
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = Math.max(max - min, 1e-9);
  const x = (idx: number) => data.length <= 1 ? 4 : 4 + (idx / (data.length - 1)) * 92;
  const y = (value: unknown) => typeof value === "number" ? 94 - ((value - min) / range) * 84 : null;
  const linePath = (key: "value" | "center" | "upper" | "lower") => {
    let started = false;
    return data.map((row, idx) => {
      const pointY = y(row[key]);
      if (pointY === null) return "";
      const command = started ? "L" : "M";
      started = true;
      return `${command} ${x(idx)} ${pointY}`;
    }).filter(Boolean).join(" ");
  };
  const analysisStartIndex = data.findIndex((row) => typeof row.center === "number");
  const hasAnalysis = analysisStartIndex >= 0;
  const usesFullDisplay = Boolean(period?.trend_analysis_uses_full_display) || analysisStartIndex === 0;
  const analysisStartX = hasAnalysis ? x(analysisStartIndex) : null;
  const analysisCount = Number(period?.trend_analysis_observation_count || 0);
  const analysisLabelLeft = `${Math.min(Math.max(usesFullDisplay ? 5 : analysisStartX ?? 5, 5), 74)}%`;
  const analysisLabelText = usesFullDisplay ? "표시 구간 전체를 회귀·채널 분석에 사용" : "회귀·채널 분석 시작";
  const analysisLabelSubText = usesFullDisplay ? "" : `최근 ${analysisCount || data.length - analysisStartIndex}개 관측값`;
  const latest = data[data.length - 1];
  const latestDate = String(latest.date ?? period?.display_range_end ?? "");
  const latestValue = typeof latest.value === "number" ? latest.value.toLocaleString("ko-KR", { maximumFractionDigits: 4 }) : "-";
  return (
    <div className="market-signal-drawer-chart">
      <svg viewBox="0 0 100 100" preserveAspectRatio="none" aria-label="임시 추세 분석 차트">
        {hasAnalysis ? (
          <rect className="analysis-region" x={usesFullDisplay ? 4 : analysisStartX ?? 4} y="4" width={96 - (usesFullDisplay ? 4 : analysisStartX ?? 4)} height="90" vectorEffect="non-scaling-stroke" />
        ) : null}
        {hasAnalysis && !usesFullDisplay && analysisStartX !== null ? (
          <>
            <line className="analysis-start" x1={analysisStartX} x2={analysisStartX} y1="4" y2="94" vectorEffect="non-scaling-stroke" />
          </>
        ) : null}
        <path className="channel upper" d={linePath("upper")} vectorEffect="non-scaling-stroke" />
        <path className="channel lower" d={linePath("lower")} vectorEffect="non-scaling-stroke" />
        <path className="trend" d={linePath("center")} vectorEffect="non-scaling-stroke" />
        <path className="raw" d={linePath("value")} vectorEffect="non-scaling-stroke" />
        {(eventRows ?? []).filter((event) => event.is_state_transition).map((event, markerIndex) => {
          const pointIndex = data.findIndex((row) => String(row.date) === String(event.observation_date));
          if (pointIndex < 0) return null;
          const markerX = x(pointIndex);
          const markerY = y(data[pointIndex].value) ?? 50;
          const state = String(event.current_state ?? "").toLowerCase();
          if (state === "break_candidate") return <polygon key={`${String(event.id)}-${markerIndex}`} className={`history-marker ${state}`} points={`${markerX},${markerY - 2.2} ${markerX - 1.9},${markerY + 1.8} ${markerX + 1.9},${markerY + 1.8}`} vectorEffect="non-scaling-stroke"><title>{String(event.display_name)}</title></polygon>;
          if (state === "reversal_confirmed") return <polygon key={`${String(event.id)}-${markerIndex}`} className={`history-marker ${state}`} points={`${markerX},${markerY - 2.2} ${markerX - 2.2},${markerY} ${markerX},${markerY + 2.2} ${markerX + 2.2},${markerY}`} vectorEffect="non-scaling-stroke"><title>{String(event.display_name)}</title></polygon>;
          return <circle key={`${String(event.id)}-${markerIndex}`} className={`history-marker ${state}`} cx={markerX} cy={markerY} r="1.8" vectorEffect="non-scaling-stroke"><title>{String(event.display_name)}</title></circle>;
        })}
        <circle className="current-marker" cx={x(data.length - 1)} cy={y(latest.value) ?? 50} r="1.4" vectorEffect="non-scaling-stroke">
          <title>현재값 {latestDate} · {latestValue}</title>
        </circle>
      </svg>
      {hasAnalysis ? (
        <div className="market-signal-analysis-label" style={{ left: analysisLabelLeft }}>
          <strong>{analysisLabelText}</strong>
          {analysisLabelSubText ? <span>{analysisLabelSubText}</span> : null}
        </div>
      ) : null}
      <div className="market-signal-drawer-chart-legend">
        <span className="raw">실제 지표선</span>
        <span className="trend">임시 회귀 추세선</span>
        <span className="channel">추세 채널</span>
        <span className="analysis">회귀·채널 분석 구간</span>
        <span className="current">현재값</span>
      </div>
    </div>
  );
}

function PreviewPeriodInfo({ period }: { period?: Record<string, unknown> }) {
  const displayStart = String(period?.display_range_start ?? period?.range_start ?? "-");
  const displayEnd = String(period?.display_range_end ?? period?.range_end ?? "-");
  const analysisStart = String(period?.trend_analysis_start ?? "-");
  const analysisEnd = String(period?.trend_analysis_end ?? "-");
  const analysisCount = Number(period?.trend_analysis_observation_count ?? 0);

  return (
    <div className="market-signal-period-info">
      <div>
        <span>표시 구간</span>
        <strong>{String(period?.actual_period_description ?? "-")}</strong>
        <strong className="market-signal-period-dates">{displayStart} ~ {displayEnd}</strong>
      </div>
      <div>
        <span>회귀·채널 분석 구간</span>
        <strong>{analysisCount > 0 ? "최근 " + analysisCount + "개 관측값" : "회귀·채널 분석 데이터 부족"}</strong>
        <strong className="market-signal-period-dates">{analysisStart} ~ {analysisEnd}</strong>
      </div>
    </div>
  );
}

function StatusPair({ rule, evalStatus }: { rule?: unknown; evalStatus?: unknown }) {
  return (
    <div className="market-signal-status-pair">
      <span>{label(rule)}</span>
      <strong>{label(evalStatus)}</strong>
    </div>
  );
}

type SignalMoreAction = {
  label: string;
  onClick: () => void;
  disabled?: boolean;
  danger?: boolean;
  title?: string;
};

function SignalMoreMenu({ actions, label: menuLabel = "기타 관리" }: { actions: SignalMoreAction[]; label?: string }) {
  if (!actions.length) return null;
  return (
    <details className="market-signal-more-menu">
      <summary aria-label={menuLabel} aria-haspopup="menu" title={menuLabel}>•••</summary>
      <div role="menu">
        {actions.map((action) => (
          <button
            key={action.label}
            className={action.danger ? "danger" : ""}
            type="button"
            role="menuitem"
            disabled={action.disabled}
            title={action.title}
            onClick={(event) => {
              action.onClick();
              event.currentTarget.closest("details")?.removeAttribute("open");
            }}
          >
            {action.label}
          </button>
        ))}
      </div>
    </details>
  );
}
function EvidenceSummary({ title, count, items }: { title: string; count?: string; items?: Record<string, unknown>[] }) {
  return (
    <div className="market-signal-evidence-block">
      <div><strong>{title}</strong><span>{count ?? `${items?.length ?? 0}개`}</span></div>
      {items?.length ? (
        <ul>
          {items.slice(0, 3).map((item, idx) => (
            <li key={`${String(item.item_code)}-${idx}`} title={`${String(item.item_code ?? "")} ${String(item.transform_type ?? "")}`}>
              {String(item.fact_text ?? item.display_text ?? item.item_display_name ?? item.item_code ?? "-")}
            </li>
          ))}
        </ul>
      ) : <p>없음</p>}
    </div>
  );
}

function emptyCondition(order: number, catalog: MarketSignalIndicatorCatalogItem[]): MarketSignalCondition {
  const firstReady = catalog.find((item) => item.classification === "AVAILABLE") ?? catalog[0];
  return {
    condition_group: "A",
    condition_role: "TRIGGER",
    item_type: "INDICATOR",
    item_code: firstReady?.code ?? "US_VIX",
    transform_type: "TREND_STATE",
    window_size: 20,
    comparison_operator: "!=",
    threshold_type: "ABSOLUTE",
    threshold_value: 0,
    threshold_secondary: null,
    weight: 10,
    is_required: true,
    sort_order: order,
  };
}

function cloneSignal(signal: MarketSignalDefinition): MarketSignalDefinition {
  return { ...signal, conditions: signal.conditions.map((condition, idx) => ({ ...condition, sort_order: idx + 1 })) };
}

function signalItemKey(item: Pick<MarketSignalCatalogItem, "item_type" | "item_code">) {
  return `${item.item_type}:${item.item_code}`;
}

function operationStatus(catalogItem: MarketSignalCatalogItem, existing?: Record<string, unknown>): OperationStatus {
  if (catalogItem.readiness === "DATA_INSUFFICIENT" || catalogItem.signal_readiness === "DATA_INSUFFICIENT") return "DATA_INSUFFICIENT";
  const status = String(existing?.rule_status ?? "").toUpperCase();
  if (status === "ACTIVE") return "ACTIVE";
  if (status === "DRAFT") return "DRAFT";
  if (status === "INACTIVE" || status === "ARCHIVED") return "INACTIVE";
  if (catalogItem.signal_readiness === "SIGNAL_ACTIVE") return "ACTIVE";
  if (catalogItem.signal_readiness === "SIGNAL_DRAFT") return "DRAFT";
  return "NOT_REGISTERED";
}

function operationLabel(status: OperationStatus) {
  return {
    ALL: "전체",
    NOT_REGISTERED: "미등록",
    DRAFT: "초안",
    ACTIVE: "운영",
    INACTIVE: "중지",
    DATA_INSUFFICIENT: "데이터 부족",
  }[status];
}

function validationLabel(value: unknown) {
  return label(String(value ?? "UNVALIDATED"));
}

function validationStatusOf(existing?: Record<string, unknown>): ValidationFilter {
  if (Boolean(existing?.activation_ready)) return "ACTIVATION_READY";
  const status = String(existing?.validation_status ?? "UNVALIDATED").toUpperCase();
  if (status === "NEEDS_REVISION" || status === "VALIDATED" || status === "ACTIVATION_READY") return status as ValidationFilter;
  return "UNVALIDATED";
}

function previewConfigFrom(value: unknown): Record<string, number> {
  const source = (value ?? {}) as Record<string, unknown>;
  return Object.fromEntries(PREVIEW_SETTING_FIELDS.map(([key]) => [key, Number(source[key] ?? 0)]));
}

function validatePreviewConfig(config: Record<string, number>, dataCount: number) {
  if ((config.short_window ?? 0) < 2) return "단기 관찰 기간은 2 이상이어야 합니다.";
  if ((config.medium_window ?? 0) < (config.short_window ?? 0)) return "중기 관찰 기간은 단기 관찰 기간보다 크거나 같아야 합니다.";
  if ((config.trend_window ?? 0) < 5) return "추세 분석 기간은 5 이상이어야 합니다.";
  if (dataCount > 0 && (config.trend_window ?? 0) > dataCount) return "추세 분석 기간은 현재 관측값 수보다 클 수 없습니다.";
  if ((config.channel_multiplier ?? 0) < 0.5 || (config.channel_multiplier ?? 0) > 5) return "채널 배수는 0.5 이상 5.0 이하로 입력해 주세요.";
  if ((config.minimum_break_persistence ?? 0) < 1 || (config.minimum_break_persistence ?? 0) > (config.trend_window ?? 0)) return "추세 이탈 확인 기간은 1 이상, 추세 분석 기간 이하이어야 합니다.";
  if ((config.false_break_window ?? 0) < 1) return "일시 이탈 후 복귀 확인 기간은 1 이상이어야 합니다.";
  if ((config.reversal_persistence ?? 0) < 1) return "반전 확인 기간은 1 이상이어야 합니다.";
  return "";
}

function defaultPreviewPeriod(frequency?: string | null) {
  const value = String(frequency ?? "DAILY").toUpperCase();
  if (value === "MONTHLY") return "3Y";
  if (value === "WEEKLY") return "1Y";
  return "3M";
}

function MarketSignalsPage() {
  const [overview, setOverview] = useState<MarketSignalOverview | null>(null);
  const [signals, setSignals] = useState<MarketSignalDefinition[]>([]);
  const [catalog, setCatalog] = useState<MarketSignalIndicatorCatalogItem[]>([]);
  const [signalCatalog, setSignalCatalog] = useState<MarketSignalCatalogResponse>({ items: [], summary: {}, total_count: 0 });
  const [modelProfiles, setModelProfiles] = useState<MarketSignalModelProfile[]>([]);
  const [templates, setTemplates] = useState<MarketSignalRuleTemplate[]>([]);
  const [templatesLoaded, setTemplatesLoaded] = useState(false);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [draft, setDraft] = useState<MarketSignalDefinition | null>(null);
  const [mainTab, setMainTab] = useState<MainTab>("today");
  const [signalTab, setSignalTab] = useState<SignalSubTab>("single");
  const [studioTab, setStudioTab] = useState<StudioSubTab>("simple");
  const [statusFilter, setStatusFilter] = useState("ALL");
  const [singleGroupFilter, setSingleGroupFilter] = useState<MarketIndicatorGroupCode>("ALL");
  const [singleReadinessFilter, setSingleReadinessFilter] = useState<OperationStatus>("ACTIVE");
  const [validationFilter, setValidationFilter] = useState<ValidationFilter>("ALL");
  const [singleProfileFilter, setSingleProfileFilter] = useState("ALL");
  const [singleSearch, setSingleSearch] = useState("");
  const [compositeStatusFilter, setCompositeStatusFilter] = useState<OperationStatus>("ALL");
  const [compositeValidationFilter, setCompositeValidationFilter] = useState<ValidationFilter>("ALL");
  const [compositeDetail, setCompositeDetail] = useState<Record<string, unknown> | null>(null);
  const [selectedDraftKeys, setSelectedDraftKeys] = useState<string[]>([]);
  const [draftPreview, setDraftPreview] = useState<Record<string, unknown> | null>(null);
  const [previewPeriod, setPreviewPeriod] = useState<string>("3M");
  const [isPreviewEditing, setIsPreviewEditing] = useState(false);
  const [previewConfig, setPreviewConfig] = useState<Record<string, number>>({});
  const [previewDefaultConfig, setPreviewDefaultConfig] = useState<Record<string, number>>({});
  const [previewConfigError, setPreviewConfigError] = useState("");
  const [hasPreviewUnsavedChanges, setHasPreviewUnsavedChanges] = useState(false);
  const [draftConfirmItem, setDraftConfirmItem] = useState<MarketSignalCatalogItem | null>(null);
  const [bulkConfirmOpen, setBulkConfirmOpen] = useState(false);
  const [validationResult, setValidationResult] = useState<Record<string, unknown> | null>(null);
  const [validationDialog, setValidationDialog] = useState<{ item: Record<string, unknown>; kind: SignalSubTab } | null>(null);
  const [activationItem, setActivationItem] = useState<Record<string, unknown> | null>(null);
  const [deactivationItem, setDeactivationItem] = useState<Record<string, unknown> | null>(null);
  const [versionItem, setVersionItem] = useState<Record<string, unknown> | null>(null);
  const [modalReason, setModalReason] = useState("");
  const [modalPurpose, setModalPurpose] = useState("");
  const [modalMemo, setModalMemo] = useState("");
  const [modalError, setModalError] = useState("");
  const [modalBusy, setModalBusy] = useState(false);
  const [gptGoal, setGptGoal] = useState("미국 금리 상승이 성장주 상대강도 약화로 이어지는 시점을 찾고 싶다.");
  const [gptPrompt, setGptPrompt] = useState("");
  const [notice, setNotice] = useState("");
  const [loading, setLoading] = useState(false);
  const [historyTarget, setHistoryTarget] = useState<Record<string, unknown> | null>(null);
  const [historyData, setHistoryData] = useState<MarketSignalEvaluationHistory | null>(null);
  const [historyFilter, setHistoryFilter] = useState<HistoryFilter>("ALL");
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historyError, setHistoryError] = useState("");
  const [phenomenonFilter, setPhenomenonFilter] = useState<"ALL" | "OFFICIAL" | "REFERENCE" | "FLOW" | "DATA_INSUFFICIENT">("ALL");
  const [phenomenonDetail, setPhenomenonDetail] = useState<Record<string, unknown> | null>(null);
  const [phenomenonHistory, setPhenomenonHistory] = useState<Record<string, unknown>[] | null>(null);
  const [phenomenonHistoryOpen, setPhenomenonHistoryOpen] = useState(false);
  const [phenomenonHistorySummary, setPhenomenonHistorySummary] = useState<Record<string, unknown> | null>(null);
  const [phenomenonFlowItem, setPhenomenonFlowItem] = useState<Record<string, unknown> | null>(null);
  const [phenomenonFlowForm, setPhenomenonFlowForm] = useState({ candidate_title: "", category: "", importance: "NORMAL", user_note: "", auto_update: true });
  const [phenomenonGptPrompt, setPhenomenonGptPrompt] = useState("");

  const catalogByCode = useMemo(() => new Map(catalog.map((item) => [item.code, item])), [catalog]);
  const filteredSignals = useMemo(() => statusFilter === "ALL" ? signals : signals.filter((item) => item.status === statusFilter), [signals, statusFilter]);

  const loadDetail = async (id: number) => {
    const detail = await repositories.marketSignals.get(id);
    setSelectedId(id);
    setDraft(cloneSignal(detail));
  };

  const loadTemplates = async () => {
    if (templatesLoaded) return;
    const templateData = await repositories.marketSignals.ruleTemplates();
    setTemplates(templateData.items);
    setTemplatesLoaded(true);
  };

  const load = async (nextSelectedId = selectedId) => {
    setLoading(true);
    try {
      const [overviewData, signalData, catalogData, signalCatalogData, profileData] = await Promise.all([
        repositories.marketSignals.overview(),
        repositories.marketSignals.list(),
        repositories.marketSignals.catalog(),
        repositories.marketSignals.signalCatalog(),
        repositories.marketSignals.modelProfiles(),
      ]);
      setOverview(overviewData);
      setSignals(signalData.items);
      setCatalog(catalogData.items);
      setSignalCatalog(signalCatalogData);
      setModelProfiles(profileData.items);
      const firstId = nextSelectedId ?? signalData.items[0]?.id ?? null;
      if (firstId) await loadDetail(firstId);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : String(error));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  useEffect(() => {
    if (singleReadinessFilter !== "DRAFT" && validationFilter !== "ALL") {
      setValidationFilter("ALL");
    }
  }, [singleReadinessFilter, validationFilter]);

  useEffect(() => {
    if (mainTab === "learning" || (mainTab === "studio" && studioTab === "templates")) {
      void loadTemplates();
    }
  }, [mainTab, studioTab, templatesLoaded]);

  const updateDraft = (patch: Partial<MarketSignalDefinition>) => setDraft((current) => current ? { ...current, ...patch } : current);
  const updateCondition = (idx: number, patch: Partial<MarketSignalCondition>) => {
    setDraft((current) => current ? { ...current, conditions: current.conditions.map((condition, conditionIdx) => conditionIdx === idx ? { ...condition, ...patch } : condition) } : current);
  };

  const saveDraft = async () => {
    if (!draft || !selectedId) return;
    const payload = {
      ...draft,
      conditions: draft.conditions.map((condition, idx) => ({ ...condition, sort_order: idx + 1, is_required: ["TRIGGER", "REQUIRED"].includes(condition.condition_role) })),
      change_reason: "Saved from rule studio",
    };
    const updated = await repositories.marketSignals.update(selectedId, payload);
    setDraft(cloneSignal(updated));
    setNotice("DRAFT 룰을 저장했습니다.");
    await load(updated.id);
  };

  const copyTemplate = async (template: MarketSignalRuleTemplate) => {
    const copied = await repositories.marketSignals.copyTemplate(template.id);
    setNotice(`${template.template_name} 템플릿을 DRAFT 룰로 복제했습니다.`);
    setStudioTab("advanced");
    await load(copied.id);
  };

  const previewSingleDraft = async (item: MarketSignalCatalogItem) => {
    try {
      const nextPeriod = defaultPreviewPeriod(item.frequency);
      setPreviewPeriod(nextPeriod);
      const result = await repositories.marketSignals.previewSingleIndicatorDraft({
        item_type: item.item_type,
        item_code: item.item_code,
        profile_code: item.recommended_profile_code,
        period: nextPeriod,
      });
      setDraftPreview(result.item);
      const config = previewConfigFrom(result.item.applied_configuration);
      setPreviewConfig(config);
      setPreviewDefaultConfig(config);
      setPreviewConfigError("");
      setIsPreviewEditing(false);
      setHasPreviewUnsavedChanges(false);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "운영 상세를 불러오지 못했습니다.");
    }
  };

  const createSingleDraft = async (item: MarketSignalCatalogItem) => {
    const previewCatalog = draftPreview?.catalog as MarketSignalCatalogItem | undefined;
    const configuration = previewCatalog?.item_type === item.item_type && previewCatalog?.item_code === item.item_code ? previewConfig : undefined;
    const result = await repositories.marketSignals.createSingleIndicatorDraft({
      item_type: item.item_type,
      item_code: item.item_code,
      profile_code: item.recommended_profile_code,
      configuration,
    });
    setDraftConfirmItem(null);
    setNotice(String(result.item.created ? `${item.item_name ?? item.item_code} 시그널 초안을 생성했습니다. 다음 단계로 과거 검증을 진행해 주세요.` : result.item.reason ?? "이미 등록된 시그널입니다."));
    await load();
  };

  const reanalyzePreview = async () => {
    const catalog = draftPreview?.catalog as MarketSignalCatalogItem | undefined;
    if (!catalog) return;
    const error = validatePreviewConfig(previewConfig, Number(catalog.data_count ?? 0));
    setPreviewConfigError(error);
    if (error) return;
    const result = await repositories.marketSignals.previewSingleIndicatorDraft({
      item_type: catalog.item_type,
      item_code: catalog.item_code,
      profile_code: String((draftPreview?.profile as Record<string, unknown> | undefined)?.profile_code ?? catalog.recommended_profile_code),
      period: previewPeriod,
      configuration: previewConfig,
    });
    setDraftPreview(result.item);
    setPreviewConfig(previewConfigFrom(result.item.applied_configuration));
    setIsPreviewEditing(false);
    setHasPreviewUnsavedChanges(true);
  };

  const closePreviewDrawer = () => {
    if (hasPreviewUnsavedChanges && !window.confirm("수정한 임시 설정이 저장되지 않았습니다. 닫으시겠습니까?")) return;
    setDraftPreview(null);
    setIsPreviewEditing(false);
    setHasPreviewUnsavedChanges(false);
    setPreviewConfigError("");
  };

  const fetchEvaluationHistory = async (target: Record<string, unknown>, filter: HistoryFilter = historyFilter) => {
    const signalId = Number(target.signal_definition_id ?? target.id);
    if (!signalId) return;
    setHistoryLoading(true);
    setHistoryError("");
    try {
      const data = await repositories.marketSignals.evaluationHistory(signalId, {
        event_only: filter === "TRANSITION",
        state: !["ALL", "TRANSITION"].includes(filter) ? filter : undefined,
        page_size: 50,
      });
      setHistoryData(data);
    } catch (error) {
      setHistoryError(error instanceof Error ? error.message : String(error));
    } finally {
      setHistoryLoading(false);
    }
  };

  const openEvaluationHistory = (target: Record<string, unknown>) => {
    setHistoryTarget(target);
    setHistoryData(null);
    setHistoryFilter("ALL");
    void fetchEvaluationHistory(target, "ALL");
  };

  const changeHistoryFilter = (filter: HistoryFilter) => {
    setHistoryFilter(filter);
    if (historyTarget) void fetchEvaluationHistory(historyTarget, filter);
  };

  const runManualEvaluation = async () => {
    if (!historyTarget) return;
    setHistoryLoading(true);
    try {
      if (String(historyTarget.card_type ?? historyTarget.signal_level).toUpperCase().includes("COMPOSITE")) {
        await repositories.marketSignals.evaluateComposite(Number(historyTarget.id), { save: true });
      } else {
        await repositories.marketSignals.evaluateNow(Number(historyTarget.signal_definition_id ?? historyTarget.id));
      }
      await fetchEvaluationHistory(historyTarget, historyFilter);
      await load();
    } catch (error) {
      setHistoryError(error instanceof Error ? error.message : String(error));
      setHistoryLoading(false);
    }
  };

  const repairHistoryBaseline = async () => {
    if (!historyTarget) return;
    setHistoryLoading(true);
    try {
      await repositories.marketSignals.repairBaseline(Number(historyTarget.signal_definition_id), true);
      await fetchEvaluationHistory(historyTarget, historyFilter);
    } catch (error) {
      setHistoryError(error instanceof Error ? error.message : String(error));
      setHistoryLoading(false);
    }
  };
  const toggleDraftCandidate = (item: MarketSignalCatalogItem) => {
    const key = signalItemKey(item);
    setSelectedDraftKeys((current) => current.includes(key) ? current.filter((value) => value !== key) : [...current, key]);
  };

  const createSelectedDrafts = async () => {
    const selectedItems = signalCatalog.items.filter((item) => selectedDraftKeys.includes(signalItemKey(item)));
    const result = await repositories.marketSignals.createSingleIndicatorDrafts(selectedItems.map((item) => ({
      item_type: item.item_type,
      item_code: item.item_code,
      profile_code: item.recommended_profile_code,
    })));
    setBulkConfirmOpen(false);
    setSelectedDraftKeys([]);
    setNotice(`${String(result.created_count ?? 0)}개의 시그널 초안을 생성했습니다. 다음 단계로 각 초안의 과거 검증을 진행해 주세요.`);
    await load();
  };

  const runValidation = async (item: Record<string, unknown>, years = 3) => {
    const modelId = Number(item.id);
    const signalId = Number(item.signal_definition_id);
    const simulation = await repositories.marketSignals.simulateSingleIndicator(modelId, years);
    const validation = await repositories.marketSignals.markValidationComplete(signalId, { validation_period_years: years, validation_summary: simulation });
    setValidationResult({ signal: validation.item, years, item_name: item.item_name, message: "검증 완료 처리했습니다. 운영 활성화를 진행할 수 있습니다." });
    setNotice(`${String(item.item_name ?? item.item_code)} 과거 검증을 완료 처리했습니다.`);
    await load();
  };

  const runCompositeValidation = async (item: Record<string, unknown>, years = 3) => {
    const signalId = Number(item.id ?? item.signal_definition_id);
    setLoading(true);
    try {
      const simulation = await repositories.marketSignals.simulateComposite(signalId, years);
      await repositories.marketSignals.markValidationComplete(signalId, { validation_period_years: years, validation_summary: simulation });
      setValidationResult({ signal: item, years, item_name: item.signal_name, message: `${years}년 과거 검증을 완료했습니다. 검증 결과를 확인한 뒤 운영을 활성화할 수 있습니다.` });
      setNotice(`${String(item.signal_name ?? item.signal_code)} 과거 검증을 완료했습니다.`);
      await load();
    } catch (error) {
      setNotice(error instanceof Error ? error.message : String(error));
    } finally {
      setLoading(false);
    }
  };

  const openPhenomenonDetail = async (item: Record<string, unknown>) => {
    try {
      const result = await repositories.marketSignals.phenomenon(Number(item.id));
      setPhenomenonGptPrompt("");
      setPhenomenonHistoryOpen(false);
      setPhenomenonDetail(result.item as unknown as Record<string, unknown>);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "현상 상세를 불러오지 못했습니다.");
    }
  };

  const openPhenomenonHistory = async (item: Record<string, unknown>) => {
    setPhenomenonDetail(item);
    setPhenomenonHistoryOpen(true);
    setPhenomenonHistory(null);
    setPhenomenonHistorySummary(null);
    try {
      const [history, summary] = await Promise.all([
        repositories.marketSignals.phenomenonEpisodes(Number(item.id)),
        repositories.marketSignals.phenomenonHistorySummary(Number(item.id)),
      ]);
      setPhenomenonHistory(history.items);
      setPhenomenonHistorySummary(summary.item);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "현상 평가 이력을 불러오지 못했습니다.");
    }
  };

  const preparePhenomenonFlowCandidate = (item: Record<string, unknown>) => {
    setPhenomenonFlowItem(item);
    setPhenomenonFlowForm({
      candidate_title: String(item.display_title ?? item.phenomenon_name ?? ""),
      category: String(item.category ?? ""),
      importance: String(item.importance ?? "NORMAL"),
      user_note: String(item.user_note ?? ""),
      auto_update: true,
    });
  };

  const savePhenomenonFlowCandidate = async () => {
    if (!phenomenonFlowItem) return;
    try {
      await repositories.marketSignals.addPhenomenonFlowCandidate(Number(phenomenonFlowItem.id), phenomenonFlowForm);
      setPhenomenonFlowItem(null);
      setNotice("경제 흐름 후보로 추가했습니다. 그래프는 생성하지 않았습니다.");
      await load();
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "경제 흐름 후보로 추가하지 못했습니다.");
    }
  };

  const removePhenomenonFlowCandidate = async (item: Record<string, unknown>) => {
    try {
      await repositories.marketSignals.removePhenomenonFlowCandidate(Number(item.id));
      setNotice("경제 흐름 후보에서 제거했습니다. 기존 이력은 유지됩니다.");
      await load();
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "경제 흐름 후보에서 제거하지 못했습니다.");
    }
  };

  const editPhenomenonMetadata = async (item: Record<string, unknown>) => {
    const displayTitle = window.prompt("현상 표시 제목", String(item.display_title ?? item.phenomenon_name ?? ""));
    if (displayTitle === null) return;
    const category = window.prompt("현상 분류", String(item.category ?? ""));
    if (category === null) return;
    try {
      await repositories.marketSignals.updatePhenomenon(Number(item.id), { display_title: displayTitle.trim(), category: category.trim() });
      setNotice("현상 표시 제목과 분류를 수정했습니다. 정량 상태와 근거는 변경하지 않았습니다.");
      await load();
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "현상 정보를 수정하지 못했습니다.");
    }
  };

  const createPhenomenonGptPrompt = async (item: Record<string, unknown>) => {
    try {
      const result = await repositories.marketSignals.gptPhenomenonDiagnosis(Number(item.id));
      setPhenomenonGptPrompt(String(result.item.prompt ?? ""));
      setPhenomenonHistoryOpen(false);
      setPhenomenonDetail(item);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "GPT 보조 진단 프롬프트를 만들지 못했습니다.");
    }
  };
  const openCompositeDetail = async (item: Record<string, unknown>) => {
    try {
      const detail = await repositories.marketSignals.compositeSignal(Number(item.id));
      setCompositeDetail({ ...item, ...detail.item });
    } catch (error) {
      setNotice(error instanceof Error ? error.message : String(error));
    }
  };

  const runCompositeEvaluation = async (item: Record<string, unknown>) => {
    try {
      await repositories.marketSignals.evaluateComposite(Number(item.id), { save: true });
      setNotice(`${String(item.signal_name ?? item.signal_code)} 복합 시그널을 재평가했습니다.`);
      await load();
    } catch (error) {
      setNotice(error instanceof Error ? error.message : String(error));
    }
  };

  const activateSignal = async () => {
    if (!activationItem) return;
    await repositories.marketSignals.activateWithApproval(Number(activationItem.signal_definition_id ?? activationItem.id), { reason: modalReason, purpose: modalPurpose, memo: modalMemo });
    setActivationItem(null);
    setModalReason("");
    setModalPurpose("");
    setModalMemo("");
    setNotice(`${String(activationItem.item_name ?? activationItem.signal_name ?? activationItem.item_code ?? activationItem.signal_code)} 시그널을 운영 활성화했습니다.`);
    await load();
  };

  const deactivateSignal = async () => {
    if (!deactivationItem) return;
    await repositories.marketSignals.deactivateWithReason(Number(deactivationItem.signal_definition_id ?? deactivationItem.id), { reason: modalReason });
    setDeactivationItem(null);
    setModalReason("");
    setNotice(`${String(deactivationItem.item_name ?? deactivationItem.signal_name ?? deactivationItem.item_code ?? deactivationItem.signal_code)} 시그널을 중지했습니다.`);
    await load();
  };

  const cloneVersion = async () => {
    if (!versionItem || modalBusy) return;
    setModalBusy(true);
    setModalError("");
    try {
      const result = await repositories.marketSignals.cloneVersion(Number(versionItem.signal_definition_id ?? versionItem.id), { reason: modalReason || "새 버전 초안 생성" });
      const alreadyExists = Boolean(result.item.already_exists);
      const createdSignal = result.item.signal as Record<string, unknown> | undefined;
      const version = String(createdSignal?.current_version ?? "-");
      setVersionItem(null);
      setModalReason("");
      setNotice(alreadyExists
        ? `${String(versionItem.item_name ?? versionItem.item_code)} v${version} 초안이 이미 있어 해당 초안을 표시합니다.`
        : `${String(versionItem.item_name ?? versionItem.item_code)} v${version} 새 버전 초안을 생성했습니다.`);
      await load();
    } catch (error) {
      setModalError(error instanceof Error ? error.message : "새 버전 초안을 생성하지 못했습니다.");
    } finally {
      setModalBusy(false);
    }
  };

  const createGptDesignPrompt = async () => {
    const result = await repositories.marketSignals.gptDesign({ goal_text: gptGoal });
    setGptPrompt(String(result.item.prompt ?? ""));
    setNotice(`GPT 간편 설계 준비: ${String(result.item.validation_status ?? "PROMPT_READY")}`);
  };

  const singleCards = overview?.single_indicator_signals ?? [];
  const compositeCards = overview?.composite_indicator_signals ?? [];
  const phenomenonCards = overview?.objective_phenomena ?? [];
  const filteredPhenomenonCards = useMemo(() => phenomenonCards.filter((item) => {
    if (phenomenonFilter === "OFFICIAL") return item.operation_grade === "OFFICIAL";
    if (phenomenonFilter === "REFERENCE") return item.operation_grade === "REFERENCE";
    if (phenomenonFilter === "FLOW") return Boolean(item.is_flow_candidate);
    if (phenomenonFilter === "DATA_INSUFFICIENT") return item.current_state === "DATA_INSUFFICIENT" || Number(item.missing_count ?? 0) > 0;
    return true;
  }), [phenomenonCards, phenomenonFilter]);
  const compositeOperationStatus = (item: Record<string, unknown>): OperationStatus => {
    const status = String(item.operation_status ?? item.rule_status ?? "DRAFT").toUpperCase();
    if (status === "ACTIVE") return "ACTIVE";
    if (status === "INACTIVE" || status === "ARCHIVED") return "INACTIVE";
    if (String(item.current_evaluation_state ?? item.evaluation_status).toUpperCase() === "DATA_INSUFFICIENT") return "DATA_INSUFFICIENT";
    return "DRAFT";
  };
  const compositeStatusCounts = useMemo(() => {
    const counts: Record<OperationStatus, number> = { ALL: compositeCards.length, NOT_REGISTERED: 0, DRAFT: 0, ACTIVE: 0, INACTIVE: 0, DATA_INSUFFICIENT: 0 };
    compositeCards.forEach((item) => { counts[compositeOperationStatus(item)] += 1; });
    return counts;
  }, [compositeCards]);
  const filteredCompositeCards = useMemo(() => compositeCards.filter((item) => {
    const operation = compositeOperationStatus(item);
    if (compositeStatusFilter !== "ALL" && operation !== compositeStatusFilter) return false;
    if (compositeStatusFilter === "DRAFT" && compositeValidationFilter !== "ALL") {
      const validation = Boolean(item.activation_ready) ? "ACTIVATION_READY" : String(item.validation_status ?? "UNVALIDATED").toUpperCase();
      return validation === compositeValidationFilter;
    }
    return true;
  }), [compositeCards, compositeStatusFilter, compositeValidationFilter]);
  const singleCardByItem = useMemo(() => {
    const map = new Map<string, Record<string, unknown>>();
    singleCards.forEach((item) => {
      const key = `${String(item.item_type ?? "INDICATOR")}:${String(item.item_code ?? "")}`;
      if (!map.has(key)) map.set(key, item);
    });
    return map;
  }, [singleCards]);
  const filteredSignalCatalog = useMemo(() => {
    const needle = singleSearch.trim().toUpperCase();
    return signalCatalog.items.filter((item) => {
      const existing = singleCardByItem.get(signalItemKey(item));
      const opStatus = operationStatus(item, existing);
      if (!matchesMarketIndicatorGroup(item, singleGroupFilter)) return false;
      if (singleReadinessFilter !== "ALL" && opStatus !== singleReadinessFilter) return false;
      if (singleReadinessFilter === "DRAFT" && validationFilter !== "ALL" && validationStatusOf(existing) !== validationFilter) return false;
      if (singleProfileFilter !== "ALL" && item.recommended_profile_code !== singleProfileFilter) return false;
      if (!needle) return true;
      return item.item_code.toUpperCase().includes(needle) || String(item.item_name ?? "").toUpperCase().includes(needle);
    });
  }, [signalCatalog.items, singleCardByItem, singleGroupFilter, singleReadinessFilter, validationFilter, singleProfileFilter, singleSearch]);
  const statusCounts = useMemo(() => {
    const counts: Record<OperationStatus, number> = { ALL: 0, NOT_REGISTERED: 0, DRAFT: 0, ACTIVE: 0, INACTIVE: 0, DATA_INSUFFICIENT: 0 };
    const needle = singleSearch.trim().toUpperCase();
    signalCatalog.items.forEach((item) => {
      const existing = singleCardByItem.get(signalItemKey(item));
      if (!matchesMarketIndicatorGroup(item, singleGroupFilter)) return;
      if (singleProfileFilter !== "ALL" && item.recommended_profile_code !== singleProfileFilter) return;
      if (needle && !item.item_code.toUpperCase().includes(needle) && !String(item.item_name ?? "").toUpperCase().includes(needle)) return;
      const opStatus = operationStatus(item, existing);
      counts.ALL += 1;
      counts[opStatus] += 1;
    });
    return counts;
  }, [signalCatalog.items, singleCardByItem, singleGroupFilter, singleProfileFilter, singleSearch]);

  const validationCounts = useMemo(() => {
    const counts: Record<ValidationFilter, number> = { ALL: 0, UNVALIDATED: 0, NEEDS_REVISION: 0, VALIDATED: 0, ACTIVATION_READY: 0 };
    const needle = singleSearch.trim().toUpperCase();
    signalCatalog.items.forEach((item) => {
      const existing = singleCardByItem.get(signalItemKey(item));
      if (operationStatus(item, existing) !== "DRAFT") return;
      if (!matchesMarketIndicatorGroup(item, singleGroupFilter)) return;
      if (singleProfileFilter !== "ALL" && item.recommended_profile_code !== singleProfileFilter) return;
      if (needle && !item.item_code.toUpperCase().includes(needle) && !String(item.item_name ?? "").toUpperCase().includes(needle)) return;
      const status = validationStatusOf(existing);
      counts.ALL += 1;
      counts[status] += 1;
    });
    return counts;
  }, [signalCatalog.items, singleCardByItem, singleGroupFilter, singleProfileFilter, singleSearch]);

  return (
    <div className="market-signals-page market-signals-page-v2 space-y-4">
      <PageHeader
        title="지표 신호 관리"
        description="수집된 지표의 추세를 확인하고, 시그널 초안을 과거 데이터로 검증한 뒤 운영합니다."
        action={<div className="market-signal-header-actions"><button className="btn btn-secondary" type="button" disabled={loading} onClick={() => load()}>새로고침</button></div>}
      />

      {notice ? <div className="inline-result inline-success">{notice}</div> : null}


      <div className="market-signal-tabs" role="tablist">
        {[
          ["today", "오늘의 전환"],
          ["signals", "시그널"],
          ["phenomena", "객관적 현상"],
          ["studio", "룰 스튜디오"],
          ["learning", "평가·학습"],
        ].map(([key, text]) => (
          <button key={key} className={mainTab === key ? "active" : ""} type="button" role="tab" aria-selected={mainTab === key} onClick={() => setMainTab(key as MainTab)}>{text}</button>
        ))}
      </div>

      {mainTab === "today" ? (
        <section className="market-signal-card-grid">
          {phenomenonCards.map((item) => (
            <article key={String(item.id)} className={cardClass(item.evaluation_status)}>
              <header><div><strong>{String(item.phenomenon_name ?? item.phenomenon_code)}</strong><small>{String(item.observation_date ?? overview?.observation_date ?? "-")}</small></div><StatusPair rule={item.rule_status_label} evalStatus={item.status_label} /></header>
              <div className="market-signal-card-body">
                <div className="market-signal-card-reading"><b>{String(item.number_label ?? "-")}</b><span>{String(item.plain_judgement ?? "")}</span></div>
                <Sparkline points={item.sparkline as Record<string, unknown>[] | undefined} />
              </div>
              <footer><span>{String(item.start_condition_summary ?? "시작 조건 -")}</span><span>{String(item.confirm_condition_summary ?? "지속 확인 -")}</span><span>{String(item.uncertainty_summary ?? "반대/부족 -")}</span></footer>
            </article>
          ))}
        </section>
      ) : null}

      {mainTab === "signals" ? (
        <>
          <div className="theme-view-mode-tabs market-theme-view-toggle" role="tablist" aria-label="지표 시그널 유형">
            <button className={`theme-view-mode-tab ${signalTab === "single" ? "active" : ""}`} type="button" role="tab" aria-selected={signalTab === "single"} onClick={() => setSignalTab("single")}>단일 지표 시그널</button>
            <button className={`theme-view-mode-tab ${signalTab === "composite" ? "active" : ""}`} type="button" role="tab" aria-selected={signalTab === "composite"} onClick={() => setSignalTab("composite")}>복합 지표 시그널</button>
          </div>
          <div className="market-signal-supporting-overview">
            <section className="market-signal-stage-guide" aria-label="시그널 운영 단계">
              {STAGE_STEPS.map((step, idx) => (
                <span key={step} className={draftPreview ? (idx === 0 ? "active" : "") : ""}>
                  <b>{idx + 1}</b>{step.replace(/^\d차\s*/, "")}
                </span>
              ))}
            </section>
            <section className="market-signal-summary-grid" aria-label="시그널 현황 요약">
              <div><span>추세 이탈 후보</span><strong>{overview?.summary.trend_break_candidate ?? 0}</strong></div>
              <div><span>추세 이탈 확인</span><strong>{overview?.summary.trend_break_confirmed ?? 0}</strong></div>
              <div><span>반전 확인</span><strong>{overview?.summary.reversal_confirmed ?? 0}</strong></div>
              <div><span>일시 이탈 후 복귀</span><strong>{overview?.summary.false_break ?? 0}</strong></div>
              <div><span>데이터 부족</span><strong>{overview?.summary.data_insufficient ?? 0}</strong></div>
            </section>
          </div>
          {signalTab === "single" ? (
            <>
              <section className="market-signal-filter-row">
                <div className="market-signal-filter-summary">
                  <strong>단일 지표 시그널 {filteredSignalCatalog.length}개</strong>
                  <span>운영 {statusCounts.ACTIVE} · 초안 {statusCounts.DRAFT} · 중지 {statusCounts.INACTIVE} · 선택 {selectedDraftKeys.length}</span>
                </div>
                <div className="market-index-filter-pills market-signal-group-tabs" role="tablist" aria-label="지표 그룹">
                  {MARKET_INDICATOR_GROUPS.map((group) => (
                    <button
                      key={group.code}
                      className={`market-index-filter-pill ${singleGroupFilter === group.code ? "active" : ""}`}
                      type="button"
                      role="tab"
                      aria-selected={singleGroupFilter === group.code}
                      onClick={() => setSingleGroupFilter(group.code)}
                    >
                      {group.label}
                    </button>
                  ))}
                </div>
                <div className="market-signal-status-tabs" role="tablist" aria-label="운영 상태">
                  <span>상태</span>
                  {SIGNAL_READINESS_FILTERS.map(([value, text]) => (
                    <button key={value} className={singleReadinessFilter === value ? "active" : ""} type="button" aria-pressed={singleReadinessFilter === value} onClick={() => {
                      setSingleReadinessFilter(value);
                      if (value !== "DRAFT") setValidationFilter("ALL");
                    }}>
                      {text} <em>{statusCounts[value]}</em>
                    </button>
                  ))}
                </div>
                {singleReadinessFilter === "DRAFT" ? (
                  <div className="market-signal-validation-panel" aria-label="초안 검증 단계">
                    <strong>초안 검증 단계</strong>
                    <div className="market-signal-validation-options" role="group" aria-label="초안 검증 상태">
                      {VALIDATION_FILTERS.map(([value, text]) => (
                        <button
                          key={value}
                          className={`market-signal-validation-option state-${value.toLowerCase()} ${validationFilter === value ? "active" : ""}`}
                          type="button"
                          aria-pressed={validationFilter === value}
                          onClick={() => setValidationFilter(value)}
                        >
                          <span className="dot" aria-hidden="true" />
                          <span>{text}</span>
                          <em>{validationCounts[value]}</em>
                        </button>
                      ))}
                    </div>
                  </div>
                ) : null}
                <div className="market-signal-filter-controls">
                  <select className="input-control" value={singleProfileFilter} onChange={(event) => setSingleProfileFilter(event.target.value)}>
                    <option value="ALL">전체 모델</option>
                    {modelProfiles.map((profile) => <option key={profile.profile_code} value={profile.profile_code}>{profile.profile_name}</option>)}
                  </select>
                  <input className="input-control" value={singleSearch} onChange={(event) => setSingleSearch(event.target.value)} placeholder="지표명·코드 검색" />
                  <button className="btn btn-secondary" type="button" disabled={!selectedDraftKeys.length} onClick={() => setBulkConfirmOpen(true)}>선택 시그널 초안 생성</button>
                </div>
              </section>
              {validationResult ? <section className="market-signal-preview-panel"><strong>{String(validationResult.item_name ?? "검증 결과")}</strong><span>{String(validationResult.years)}년 검증</span><span>{String(validationResult.message)}</span></section> : null}
              <section className="market-signal-card-grid">
                {filteredSignalCatalog.map((catalogItem) => {
                  const existing = singleCardByItem.get(signalItemKey(catalogItem));
                  const opStatus = operationStatus(catalogItem, existing);
                  const canCreate = opStatus === "NOT_REGISTERED";
                  const status = existing?.evaluation_status ?? opStatus;
                  const validationStatus = String(existing?.validation_status ?? "UNVALIDATED").toUpperCase();
                  return (
                    <article key={signalItemKey(catalogItem)} className={`${cardClass(status)} op-${opStatus.toLowerCase()}`}>
                      <header>
                        {opStatus === "NOT_REGISTERED" ? (
                          <label className="market-signal-card-select" title="시그널 초안 일괄 생성 대상">
                            <input type="checkbox" checked={selectedDraftKeys.includes(signalItemKey(catalogItem))} disabled={!canCreate} onChange={() => toggleDraftCandidate(catalogItem)} />
                          </label>
                        ) : null}
                        <div>
                          <strong title={String(catalogItem.item_name ?? catalogItem.item_code)}>{String(catalogItem.item_name ?? catalogItem.item_code)}</strong>
                          <small>{catalogItem.item_code} · {catalogItem.recommended_profile_code}</small>
                        </div>
                        <div className="market-signal-card-badges">
                          <span className="market-signal-operation-badge" title={opStatus === "NOT_REGISTERED" ? "단일 지표 시그널 미등록" : undefined}>{operationLabel(opStatus)}</span>
                          {opStatus === "DRAFT" ? <span className="market-signal-validation-badge">{validationLabel(validationStatus)}</span> : null}
                          <strong className="market-signal-assessment-badge">{existing ? `현재 판정: ${String(existing.status_label ?? label(existing.evaluation_status))}` : label(catalogItem.readiness)}</strong>
                        </div>
                      </header>
                      <div className="market-signal-card-body">
                        <div className="market-signal-card-reading">
                          <b>{String(existing?.number_label ?? num(catalogItem.latest_value))}</b>
                          <span>{existing ? `${String(existing.trend_label ?? "-")} · 지속 ${String((existing.diagnostic as Record<string, unknown> | undefined)?.trend_duration ?? "-")}개 관측` : `${label(catalogItem.readiness)} · 관측값 ${catalogItem.data_count.toLocaleString()}개`}</span>
                        </div>
                        {existing ? <Sparkline points={existing.sparkline as Record<string, unknown>[]} markers={existing.sparkline_markers as string[]} /> : <Sparkline points={catalogItem.sparkline ?? []} />}
                      </div>
                      <footer>
                        <span>{opStatus === "NOT_REGISTERED" ? "추세를 확인할 지표" : opStatus === "DRAFT" ? "룰을 검증할 시그널" : opStatus === "ACTIVE" ? "자동 평가 중인 시그널" : opStatus === "INACTIVE" ? "이력은 유지, 운영 제외" : "데이터 보강 필요"}</span>
                        <span>{catalogItem.frequency ?? "-"}</span>
                        <span>{catalogItem.latest_observation_date ?? "-"}</span>
                      </footer>
                      <div className="market-signal-card-actions">
                        {opStatus === "NOT_REGISTERED" || opStatus === "DATA_INSUFFICIENT" ? (
                          <>
                            <button className="btn btn-secondary market-signal-action-secondary" type="button" onClick={() => previewSingleDraft(catalogItem)}>1차 추세 확인</button>
                            <button className="btn btn-primary market-signal-action-primary" type="button" disabled={!canCreate} title={!canCreate ? "분석에 필요한 데이터가 부족합니다." : undefined} onClick={() => setDraftConfirmItem(catalogItem)}>2차 시그널 초안 생성</button>
                          </>
                        ) : null}
                        {opStatus === "DRAFT" && existing ? (
                          <>
                            <button className="btn btn-secondary market-signal-action-secondary" type="button" onClick={() => previewSingleDraft(catalogItem)}>상세 분석</button>
                            {["VALIDATED", "ACTIVATION_READY"].includes(validationStatus) || existing.activation_ready ? (
                              <button className="btn btn-primary market-signal-action-primary" type="button" onClick={() => { setActivationItem(existing); setModalReason(""); }}>4차 운영 활성화</button>
                            ) : (
                              <button className="btn btn-primary market-signal-action-primary" type="button" onClick={() => setValidationDialog({ item: existing, kind: "single" })}>3차 과거 검증</button>
                            )}
                            <SignalMoreMenu actions={["VALIDATED", "ACTIVATION_READY"].includes(validationStatus) || existing.activation_ready
                              ? [{ label: "과거 재검증", onClick: () => setValidationDialog({ item: existing, kind: "single" }) }]
                              : [{ label: "운영 활성화", disabled: true, title: "과거 검증을 완료해야 활성화할 수 있습니다.", onClick: () => undefined }]}
                            />
                          </>
                        ) : null}
                        {opStatus === "ACTIVE" && existing ? (
                          <>
                            <button className="btn btn-primary market-signal-action-primary" type="button" onClick={() => openEvaluationHistory(existing)}>평가 이력</button>
                            <button className="btn btn-secondary market-signal-action-secondary" type="button" onClick={() => previewSingleDraft(catalogItem)}>운영 상세</button>
                            <SignalMoreMenu actions={[
                              { label: "새 버전 초안", onClick: () => { setVersionItem(existing); setModalReason(""); setModalError(""); } },
                              { label: "운영 중지", danger: true, onClick: () => { setDeactivationItem(existing); setModalReason(""); } },
                            ]} />
                          </>
                        ) : null}
                        {opStatus === "INACTIVE" && existing ? (
                          <>
                            <button className="btn btn-primary market-signal-action-primary" type="button" onClick={() => openEvaluationHistory(existing)}>평가 이력</button>
                            <button className="btn btn-secondary market-signal-action-secondary" type="button" onClick={() => { setVersionItem(existing); setModalReason(""); setModalError(""); }}>새 버전 초안</button>
                          </>
                        ) : null}
                      </div>
                      {opStatus === "ACTIVE" && existing ? (
                        <div className="market-signal-operation-glance">
                          <span>최근 자동 평가 <b>{String(existing.latest_operation_evaluation_at ?? "기록 대기")}</b></span>
                          <span>{existing.latest_transition
                            ? <>최근 변화 <b>{label((existing.latest_transition as Record<string, unknown>).previous_state)} → {label((existing.latest_transition as Record<string, unknown>).new_state)}</b></>
                            : <>최근 변화 없음 <b>{label(existing.latest_operation_state ?? existing.evaluation_status)}</b></>}</span>
                          <span>상태 전환 {String(existing.live_transition_count ?? 0)}회 · 일시 이탈 후 복귀 {String(existing.live_false_break_count ?? 0)}회</span>
                        </div>
                      ) : null}
                      <p className="market-signal-next-check">{opStatus === "NOT_REGISTERED" ? "그래프와 추천 분석 기준을 확인한 뒤 시그널 초안 생성 여부를 결정하세요." : opStatus === "DRAFT" ? "과거 데이터에서 추세 이탈과 일시 이탈 후 복귀 판정이 적절한지 확인하세요." : opStatus === "ACTIVE" ? "지표 갱신 후 자동으로 평가되고 있습니다." : existing ? ((existing.next_checks as string[]) ?? [])[0] : catalogItem.recommended_profile_reason}</p>
                    </article>
                  );
                })}
              </section>
            </>
          ) : (
            <>
              <section className="market-signal-filter-row market-signal-composite-filter">
                <div className="market-signal-filter-summary"><strong>복합 지표 시그널 {filteredCompositeCards.length}개</strong><span>운영 {compositeStatusCounts.ACTIVE} · 초안 {compositeStatusCounts.DRAFT} · 중지 {compositeStatusCounts.INACTIVE}</span></div>
                <div className="market-signal-status-tabs" role="tablist" aria-label="복합 시그널 운영 상태">
                  <span>운영 상태</span>
                  {(["ALL", "DRAFT", "ACTIVE", "INACTIVE", "DATA_INSUFFICIENT"] as OperationStatus[]).map((value) => (
                    <button key={value} className={compositeStatusFilter === value ? "active" : ""} type="button" aria-pressed={compositeStatusFilter === value} onClick={() => {
                      setCompositeStatusFilter(value);
                      if (value !== "DRAFT") setCompositeValidationFilter("ALL");
                    }}>{operationLabel(value)} <em>{compositeStatusCounts[value]}</em></button>
                  ))}
                </div>
                {compositeStatusFilter === "DRAFT" ? (
                  <div className="market-signal-validation-panel">
                    <strong>초안 검증 단계</strong>
                    <div className="market-signal-validation-options">
                      {VALIDATION_FILTERS.map(([value, text]) => (
                        <button key={value} className={`market-signal-validation-option state-${value.toLowerCase()} ${compositeValidationFilter === value ? "active" : ""}`} type="button" aria-pressed={compositeValidationFilter === value} onClick={() => setCompositeValidationFilter(value)}>
                          <span className="dot" aria-hidden="true" /><span>{text}</span>
                        </button>
                      ))}
                    </div>
                  </div>
                ) : null}
              </section>
              <section className="market-signal-card-grid">
                {filteredCompositeCards.map((item) => {
                  const operation = compositeOperationStatus(item);
                  const validation = Boolean(item.activation_ready) ? "ACTIVATION_READY" : String(item.validation_status ?? "UNVALIDATED").toUpperCase();
                  const groups = (item.condition_groups ?? {}) as Record<string, Record<string, unknown>[]>;
                  return (
                    <article key={String(item.id)} className={`${cardClass(item.evaluation_status)} op-${operation.toLowerCase()}`}>
                      <header>
                        <div><strong title={String(item.signal_name)}>{String(item.signal_name)}</strong><small title={String(item.signal_code)}>{String(item.model_display_name ?? "조건 결합형")} · 룰 v{String(item.rule_version ?? 1)}</small></div>
                        <div className="market-signal-card-badges"><span className="market-signal-operation-badge">{String(item.operation_status_display_name ?? operationLabel(operation))}</span><strong className="market-signal-assessment-badge">현재 판정: {String(item.current_evaluation_display_name ?? item.status_label ?? label(item.evaluation_status))}</strong></div>
                      </header>
                      <div className="market-signal-card-body">
                        <div className="market-signal-card-reading"><b>{String(item.number_label ?? "-")}</b><span>{String(item.trigger_summary)} · {String(item.confirm_summary)}</span></div>
                        <Sparkline points={item.sparkline as Record<string, unknown>[]} />
                      </div>
                      <footer><span>{String(item.trigger_summary)}</span><span>{String(item.confirm_summary)}</span><span>{String(item.opposing_summary)}</span><span>{String(item.data_summary ?? "데이터 부족 0개")}</span></footer>
                      <div className="market-signal-mini-timeline">
                        {[...(groups.TRIGGER ?? []), ...(groups.CONFIRM ?? [])].slice(0, 3).map((row, idx) => <span key={idx} title={String(row.technical_text ?? "")}>{String(row.display_text ?? row.item_display_name ?? row.item_code ?? "-")}</span>)}
                        {[...(groups.TRIGGER ?? []), ...(groups.CONFIRM ?? [])].length > 3 ? <button type="button" onClick={() => openCompositeDetail(item)}>+{[...(groups.TRIGGER ?? []), ...(groups.CONFIRM ?? [])].length - 3}개 더 보기</button> : null}
                      </div>
                      <div className="market-signal-card-actions">
                        {operation === "DRAFT" ? (
                          <>
                            <button className="btn btn-secondary market-signal-action-secondary" type="button" onClick={() => openCompositeDetail(item)}>조건 상세</button>
                            {Boolean(item.activation_ready) || ["VALIDATED", "ACTIVATION_READY"].includes(validation) ? (
                              <button className="btn btn-primary market-signal-action-primary" type="button" onClick={() => { setActivationItem(item); setModalReason(""); }}>4차 운영 활성화</button>
                            ) : (
                              <button className="btn btn-primary market-signal-action-primary" type="button" onClick={() => setValidationDialog({ item, kind: "composite" })}>3차 과거 검증</button>
                            )}
                            <SignalMoreMenu actions={Boolean(item.activation_ready) || ["VALIDATED", "ACTIVATION_READY"].includes(validation)
                              ? [{ label: "과거 재검증", onClick: () => setValidationDialog({ item, kind: "composite" }) }]
                              : [{ label: "운영 활성화", disabled: true, title: "과거 검증을 완료해야 활성화할 수 있습니다.", onClick: () => undefined }]}
                            />
                          </>
                        ) : null}
                        {operation === "ACTIVE" ? (
                          <>
                            <button className="btn btn-primary market-signal-action-primary" type="button" onClick={() => openEvaluationHistory(item)}>평가 이력</button>
                            <button className="btn btn-secondary market-signal-action-secondary" type="button" onClick={() => openCompositeDetail(item)}>운영 상세</button>
                            <SignalMoreMenu actions={[
                              { label: "지금 재평가", onClick: () => runCompositeEvaluation(item) },
                              { label: "새 버전 초안", onClick: () => { setVersionItem(item); setModalReason(""); setModalError(""); } },
                              { label: "운영 중지", danger: true, onClick: () => { setDeactivationItem(item); setModalReason(""); } },
                            ]} />
                          </>
                        ) : null}
                        {operation === "INACTIVE" ? (
                          <>
                            <button className="btn btn-primary market-signal-action-primary" type="button" onClick={() => openEvaluationHistory(item)}>평가 이력</button>
                            <button className="btn btn-secondary market-signal-action-secondary" type="button" onClick={() => openCompositeDetail(item)}>운영 상세</button>
                            <SignalMoreMenu actions={[{ label: "새 버전 초안", onClick: () => { setVersionItem(item); setModalReason(""); setModalError(""); } }]} />
                          </>
                        ) : null}
                      </div>                      <p className="market-signal-next-check">{operation === "DRAFT" ? "과거 검증을 완료한 뒤 명시적으로 운영을 활성화하세요." : operation === "ACTIVE" ? "관련 단일 지표가 갱신되면 관측일별로 자동 평가됩니다." : "평가 이력은 유지되며 자동 평가 대상에서는 제외됩니다."}</p>
                    </article>
                  );
                })}
              </section>
            </>
          )}
        </>
      ) : null}

      {mainTab === "phenomena" ? (
        <section className="market-phenomena-workspace">
          <div className="market-phenomena-toolbar">
            <div><strong>현재 시장에서 관찰되는 현상</strong><span>복합 시그널의 조건 편집이 아니라 실제 관찰 결과를 해석합니다.</span></div>
            <div role="group" aria-label="객관적 현상 필터">
              {([
                ["ALL", "전체"], ["OFFICIAL", "정식 현상"], ["REFERENCE", "참고 현상"],
                ["FLOW", "흐름 후보"], ["DATA_INSUFFICIENT", "데이터 부족"],
              ] as const).map(([value, text]) => <button key={value} className={phenomenonFilter === value ? "active" : ""} type="button" onClick={() => setPhenomenonFilter(value)}>{text}</button>)}
            </div>
          </div>
          {!filteredPhenomenonCards.length ? <div className="market-signal-history-empty"><strong>조건에 맞는 객관적 현상이 없습니다.</strong><p>원천 복합 룰의 운영 상태 또는 데이터 준비도를 확인해 주세요.</p></div> : null}
          <div className="market-phenomena-grid">
            {filteredPhenomenonCards.map((item) => {
              const evidence = (item.observed_evidence as Record<string, unknown>[] | undefined) ?? [];
              const opposing = (item.opposing_evidence as Record<string, unknown>[] | undefined) ?? [];
              const missing = (item.missing_conditions as Record<string, unknown>[] | undefined) ?? [];
              const checks = (item.next_checks as string[] | undefined) ?? [];
              const isOfficial = item.operation_grade === "OFFICIAL";
              return (
                <article key={String(item.id)} className={`${cardClass(item.current_state)} market-phenomenon-card`}>
                  <header>
                    <div><small>객관적 현상</small><strong>{String(item.display_title ?? item.phenomenon_name ?? item.phenomenon_code)}</strong><span>원천 복합 시그널 · {String(item.source_title ?? "-")}</span></div>
                    <div className="market-phenomenon-badges"><span className={isOfficial ? "official" : "reference"}>{String(item.operation_grade_label ?? (isOfficial ? "정식 현상" : "참고 현상"))}</span><strong>{String(item.current_state_label ?? label(item.current_state))}</strong>{item.is_flow_candidate ? <em>경제 흐름 후보</em> : null}</div>
                  </header>
                  {!isOfficial ? <p className="market-phenomenon-reference-note">아직 운영 승인되지 않은 복합 시그널의 참고 결과입니다. 정식 전환 집계와 운영 흐름 입력에는 사용하지 않습니다.</p> : null}
                  <div className="market-phenomenon-reading">
                    <p>{String(item.easy_explanation ?? "")}</p>
                    <span title="현재 관찰 근거·지속 확인·반대 근거를 종합한 정량 점수입니다.">현상 확인도 <b>{String(item.phenomenon_score ?? 0)}점</b></span>
                  </div>
                  <div className="market-phenomenon-evidence-row">
                    <EvidenceSummary title="관찰 근거" count={`${evidence.length}개`} items={evidence} />
                    <EvidenceSummary title="반대 근거" count={`${opposing.length}개`} items={opposing} />
                    <EvidenceSummary title="데이터 부족" count={`${missing.length}개`} items={missing} />
                  </div>
                  <div className="market-phenomenon-next-checks"><strong>다음 확인</strong>{checks.length ? <ul>{checks.slice(0, 3).map((check) => <li key={check}>{check}</li>)}</ul> : <p>다음 평가에서 지속 여부를 확인합니다.</p>}</div>
                  <footer>
                    <span>최근 변화 · {String(item.recent_change ?? "-")}</span>
                    <div>
                      <button className="btn btn-secondary" type="button" onClick={() => openPhenomenonDetail(item)}>근거 상세</button>
                      <button className="btn btn-secondary" type="button" onClick={() => openPhenomenonHistory(item)}>평가 이력</button>
                      {Boolean(item.can_add_flow_candidate) ? <button className="btn btn-primary" type="button" onClick={() => preparePhenomenonFlowCandidate(item)}>경제 흐름에 추가</button> : null}
                      <SignalMoreMenu actions={[
                        { label: "GPT 보조 진단", onClick: () => void createPhenomenonGptPrompt(item) },
                        { label: "제목·분류 수정", onClick: () => void editPhenomenonMetadata(item) },
                        ...(item.is_flow_candidate ? [{ label: "흐름 후보에서 제거", onClick: () => void removePhenomenonFlowCandidate(item), danger: true }] : []),
                      ]} />
                    </div>
                  </footer>
                </article>
              );
            })}
          </div>
        </section>
      ) : null}
      {mainTab === "studio" ? (
        <section className="market-signal-rule-layout">
          <aside className="market-signal-rule-list">
            <div className="market-signal-subtabs vertical">
              {[
                ["simple", "직접 설계"],
                ["templates", "템플릿"],
                ["gpt", "GPT 설계"],
                ["advanced", "고급 설정"],
              ].map(([key, text]) => <button key={key} className={studioTab === key ? "active" : ""} type="button" onClick={() => setStudioTab(key as StudioSubTab)}>{text}</button>)}
            </div>
            {studioTab === "advanced" ? (
              <>
                <select className="input-control" value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}>
                  <option value="ALL">전체 상태</option><option value="DRAFT">DRAFT</option><option value="ACTIVE">ACTIVE</option><option value="INACTIVE">INACTIVE</option>
                </select>
                {filteredSignals.map((signal) => (
                  <button key={signal.id} className={selectedId === signal.id ? "active" : ""} type="button" onClick={() => loadDetail(signal.id)}>
                    <strong>{signal.signal_name}</strong><span>{signal.signal_code}</span><em>{signal.status} / {signal.horizon}</em>
                  </button>
                ))}
              </>
            ) : null}
          </aside>

          <SectionCard className="market-signal-rule-detail">
            {studioTab === "simple" ? (
              <div className="market-signal-simple-studio">
                <h3>무엇을 찾고 싶으세요?</h3>
                <textarea className="input-control" value={gptGoal} onChange={(event) => setGptGoal(event.target.value)} />
                <div className="market-signal-template-actions"><button className="btn btn-primary" type="button" onClick={() => setStudioTab("gpt")}>GPT로 초안 만들기</button><button className="btn btn-secondary" type="button" onClick={() => setStudioTab("templates")}>검증된 템플릿에서 시작</button></div>
              </div>
            ) : null}

            {studioTab === "templates" ? (
              <div className="market-signal-template-grid">
                {templates.map((template) => (
                  <article key={template.id} className="market-signal-template-card">
                    <header><strong>{template.template_name}</strong><span>{template.signal_level}</span></header>
                    <p>{template.description}</p>
                    <dl><dt>분류</dt><dd>{template.category}</dd><dt>준비도</dt><dd>{template.readiness_label}</dd><dt>최근 3년</dt><dd>{template.recent_3y_occurrence_count}회</dd><dt>근거</dt><dd>{template.evidence_grade}</dd></dl>
                    <footer><button className="btn btn-secondary" type="button">미리보기</button><button className="btn btn-primary" type="button" onClick={() => copyTemplate(template)}>새 룰로 복제</button></footer>
                  </article>
                ))}
              </div>
            ) : null}

            {studioTab === "gpt" ? (
              <div className="market-signal-gpt-panel">
                <label><span>자연어 입력</span><textarea className="input-control" value={gptGoal} onChange={(event) => setGptGoal(event.target.value)} /></label>
                <button className="btn btn-primary" type="button" onClick={createGptDesignPrompt}>GPT 설계 프롬프트 생성</button>
                {gptPrompt ? <pre>{gptPrompt}</pre> : null}
              </div>
            ) : null}

            {studioTab === "advanced" ? (
              draft ? (
                <>
                  <div className="market-signal-detail-head"><div><strong>{draft.signal_name}</strong><p>{draft.description}</p></div><button className="btn btn-primary" type="button" onClick={saveDraft}>DRAFT 저장</button></div>
                  <div className="market-signal-editor-grid">
                    <label><span>현상</span><textarea className="input-control" value={draft.phenomenon_template ?? ""} onChange={(event) => updateDraft({ phenomenon_template: event.target.value })} /></label>
                    <label><span>과정</span><textarea className="input-control" value={draft.process_template ?? ""} onChange={(event) => updateDraft({ process_template: event.target.value })} /></label>
                    <label><span>결과</span><textarea className="input-control" value={draft.result_template ?? ""} onChange={(event) => updateDraft({ result_template: event.target.value })} /></label>
                  </div>
                  <div className="market-signal-condition-table-wrap">
                    <table className="data-table compact-table">
                      <thead><tr><th>역할</th><th>지표</th><th>변환</th><th>기간</th><th>비교</th><th>기준</th><th>가중치</th><th></th></tr></thead>
                      <tbody>{draft.conditions.map((condition, idx) => (
                        <tr key={condition.id ?? idx}>
                          <td><select className="input-control" value={condition.condition_role} onChange={(event) => updateCondition(idx, { condition_role: event.target.value as MarketSignalCondition["condition_role"] })}>{ROLES.map((role) => <option key={role} value={role}>{role}</option>)}</select></td>
                          <td><select className="input-control" value={condition.item_code} onChange={(event) => updateCondition(idx, { item_code: event.target.value })}>{catalog.map((item) => <option key={item.code} value={item.code}>{item.name} ({item.code})</option>)}</select><small>{catalogByCode.get(condition.item_code)?.readiness ?? "-"}</small></td>
                          <td><select className="input-control" value={condition.transform_type} onChange={(event) => updateCondition(idx, { transform_type: event.target.value })}>{TRANSFORMS.map((transform) => <option key={transform} value={transform}>{transform}</option>)}</select></td>
                          <td><input className="input-control" type="number" value={condition.window_size} onChange={(event) => updateCondition(idx, { window_size: Number(event.target.value) })} /></td>
                          <td><select className="input-control" value={condition.comparison_operator} onChange={(event) => updateCondition(idx, { comparison_operator: event.target.value })}>{OPERATORS.map((operator) => <option key={operator} value={operator}>{operator}</option>)}</select></td>
                          <td><input className="input-control" type="number" value={condition.threshold_value ?? ""} onChange={(event) => updateCondition(idx, { threshold_value: event.target.value === "" ? null : Number(event.target.value) })} /></td>
                          <td><input className="input-control" type="number" value={condition.weight} onChange={(event) => updateCondition(idx, { weight: Number(event.target.value) })} /></td>
                          <td><button className="btn btn-secondary" type="button" onClick={() => updateDraft({ conditions: draft.conditions.filter((_, conditionIdx) => conditionIdx !== idx) })}>삭제</button></td>
                        </tr>
                      ))}</tbody>
                    </table>
                  </div>
                  <button className="btn btn-secondary" type="button" onClick={() => updateDraft({ conditions: [...draft.conditions, emptyCondition(draft.conditions.length + 1, catalog)] })}>조건 추가</button>
                </>
              ) : <div className="market-index-chart-empty">룰을 선택해 주세요.</div>
            ) : null}
          </SectionCard>
        </section>
      ) : null}

      {mainTab === "learning" ? (
        <section className="market-signal-card-grid">
          <SectionCard><h3>학습 요약</h3><dl className="market-signal-learning-grid"><dt>템플릿</dt><dd>{templates.length}개</dd><dt>템플릿 복제</dt><dd>{templates.reduce((sum, item) => sum + item.copied_count, 0)}회</dd><dt>오늘 이벤트</dt><dd>{overview?.today_events.length ?? 0}개</dd><dt>자동 ACTIVE</dt><dd>없음</dd></dl></SectionCard>
          <SectionCard><h3>역할 분리</h3><p>Codex는 엔진·API·화면·템플릿 seed를 구현합니다. GPT는 자연어 요구를 룰 JSON 후보와 경제적 근거로 바꾸며, DrCT 검증 후 DRAFT로만 저장됩니다.</p></SectionCard>
        </section>
      ) : null}

      {phenomenonDetail && !phenomenonHistoryOpen ? (
        <div className="market-signal-drawer-backdrop" role="presentation" onClick={() => setPhenomenonDetail(null)}>
          <aside className="market-signal-history-drawer market-phenomenon-drawer" role="dialog" aria-modal="true" aria-label="객관적 현상 근거 상세" onClick={(event) => event.stopPropagation()}>
            <header>
              <div><span>객관적 현상 · 근거 상세</span><strong>{String(phenomenonDetail.display_title ?? phenomenonDetail.phenomenon_name ?? "-")}</strong><small>{String(phenomenonDetail.operation_grade_label ?? "-")} · {String(phenomenonDetail.current_state_label ?? "-")}</small></div>
              <button className="btn btn-secondary" type="button" onClick={() => setPhenomenonDetail(null)}>닫기</button>
            </header>
            <div className="market-signal-history-body">
              <section className="market-signal-history-summary">
                <div><span>노출 등급</span><strong>{String(phenomenonDetail.operation_grade_label ?? "-")}</strong></div>
                <div><span>현재 상태</span><strong>{String(phenomenonDetail.current_state_label ?? "-")}</strong></div>
                <div><span>현상 확인도</span><strong>{String(phenomenonDetail.phenomenon_score ?? 0)}점</strong></div>
                <div><span>기준일</span><strong>{String(phenomenonDetail.observation_date ?? "-")}</strong></div>
              </section>
              <section className="market-phenomenon-drawer-reading"><h3>쉬운 설명</h3><p>{String(phenomenonDetail.easy_explanation ?? "-")}</p></section>
              <section className="market-phenomenon-source"><span>원천 복합 시그널</span><strong>{String(phenomenonDetail.source_title ?? "-")}</strong><small>{String(phenomenonDetail.source_operation_status_label ?? "-")} · 룰 v{String(phenomenonDetail.source_rule_version ?? 1)}</small></section>
              {([
                ["관찰 근거", phenomenonDetail.observed_evidence],
                ["반대 근거", phenomenonDetail.opposing_evidence],
                ["데이터 부족", phenomenonDetail.missing_conditions],
                ["무효화 조건", phenomenonDetail.invalidation_evidence],
              ] as [string, unknown][]).map(([title, value]) => {
                const rows = (value as Record<string, unknown>[] | undefined) ?? [];
                return <section className="market-phenomenon-detail-section" key={title}><h3>{title} <span>{rows.length}개</span></h3>{rows.length ? rows.map((row, idx) => <article key={`${String(row.condition_id)}-${idx}`}><header><strong>{String(row.fact_text ?? row.item_display_name ?? row.item_code ?? "-")}</strong><span>{String(row.latest_judgement ?? (row.missing ? "데이터 부족" : "충족"))}</span></header><dl><dt>지표</dt><dd>{String(row.item_display_name ?? row.item_code ?? "-")}</dd><dt>조건 역할</dt><dd>{String(row.condition_role_label ?? "-")}</dd><dt>데이터 품질</dt><dd>{String(row.data_quality ?? "-")}</dd><dt>기준일</dt><dd>{String(row.base_date ?? phenomenonDetail.observation_date ?? "-")}</dd></dl>{row.missing_reason ? <p>{String(row.missing_reason)}</p> : null}<details><summary>기술 조건</summary><code>{String(row.item_code ?? "-")} · {String(row.transform_type ?? "-")} {String(row.operator ?? "")} {String(row.threshold_value ?? "")}</code></details></article>) : <p>없음</p>}</section>;
              })}
              <section className="market-phenomenon-detail-section"><h3>다음 확인</h3><ul>{((phenomenonDetail.next_checks as string[] | undefined) ?? []).map((check) => <li key={check}>{check}</li>)}</ul></section>
              {phenomenonGptPrompt ? <section className="market-phenomenon-detail-section"><h3>GPT 보조 진단 프롬프트</h3><p>이 프롬프트는 DrCT 상태와 점수를 변경하지 않으며 사용자가 외부 결과를 검토하기 위한 용도입니다.</p><pre>{phenomenonGptPrompt}</pre></section> : null}
            </div>
            <footer><button className="btn btn-secondary" type="button" onClick={() => void createPhenomenonGptPrompt(phenomenonDetail)}>GPT 보조 진단</button><button className="btn btn-secondary" type="button" onClick={() => setPhenomenonDetail(null)}>닫기</button></footer>
          </aside>
        </div>
      ) : null}

      {phenomenonDetail && phenomenonHistoryOpen ? (
        <div className="market-signal-drawer-backdrop" role="presentation" onClick={() => { setPhenomenonDetail(null); setPhenomenonHistoryOpen(false); }}>
          <aside className="market-signal-history-drawer market-phenomenon-history-drawer" role="dialog" aria-modal="true" aria-label="객관적 현상 평가 이력" onClick={(event) => event.stopPropagation()}>
            <header><div><span>객관적 현상 · 평가 이력</span><strong>{String(phenomenonDetail.display_title ?? phenomenonDetail.phenomenon_name ?? "-")}</strong><small>원천 복합 평가 ID를 참조한 집계 이력</small></div><button className="btn btn-secondary" type="button" onClick={() => { setPhenomenonDetail(null); setPhenomenonHistoryOpen(false); }}>닫기</button></header>
            <div className="market-signal-history-body">
              <section className="market-signal-history-summary">
                <div><span>최초 평가</span><strong>{String(phenomenonHistorySummary?.first_evaluation_date ?? "-")}</strong></div>
                <div><span>마지막 평가</span><strong>{String(phenomenonHistorySummary?.last_evaluation_date ?? "-")}</strong></div>
                <div><span>누적 평가</span><strong>{String(phenomenonHistorySummary?.evaluation_count ?? 0)}회</strong></div>
                <div><span>상태 전환</span><strong>{String(phenomenonHistorySummary?.transition_count ?? 0)}회</strong></div>
                <div><span>현상 확인</span><strong>{String(phenomenonHistorySummary?.confirmed_count ?? 0)}회</strong></div>
                <div><span>현상 해제</span><strong>{String(phenomenonHistorySummary?.released_count ?? 0)}회</strong></div>
                <div><span>반대 우세</span><strong>{String(phenomenonHistorySummary?.opposed_count ?? 0)}회</strong></div>
                <div><span>데이터 부족</span><strong>{String(phenomenonHistorySummary?.data_insufficient_count ?? 0)}회</strong></div>
              </section>
              {phenomenonHistory === null ? <div className="market-signal-history-status">평가 이력을 불러오는 중입니다.</div> : phenomenonHistory.length ? <section className="market-signal-history-timeline">{phenomenonHistory.map((row) => <details key={String(row.id)} open={Boolean(row.is_state_transition)}><summary><div><strong>{String(row.observation_date ?? "-")}</strong><span>{String(row.evaluation_type ?? "-")} · 원천 평가 #{String(row.source_composite_evaluation_id ?? "-")}</span></div><div>{row.is_state_transition ? <><span>{label(row.previous_state)}</span><b>→</b></> : <span>상태 변화 없음</span>}<strong>{label(row.current_state)}</strong></div></summary><div className="market-signal-history-detail"><p>{String(row.easy_explanation ?? "-")}</p><dl><dt>관찰 근거</dt><dd>{String(row.evidence_count ?? 0)}개</dd><dt>반대 근거</dt><dd>{String(row.opposing_count ?? 0)}개</dd><dt>데이터 부족</dt><dd>{String(row.missing_count ?? 0)}개</dd><dt>현상 확인도</dt><dd>{String(row.phenomenon_score ?? 0)}점</dd></dl></div></details>)}</section> : <section className="market-signal-history-empty"><strong>저장된 LIVE 현상 평가 이력이 없습니다.</strong><p>참고 현상은 정식 이력을 생성하지 않습니다. 원천 복합 룰이 운영 활성화된 뒤 LIVE 평가가 생성되면 기록됩니다.</p></section>}
            </div>
            <footer><button className="btn btn-secondary" type="button" onClick={() => { setPhenomenonDetail(null); setPhenomenonHistoryOpen(false); }}>닫기</button></footer>
          </aside>
        </div>
      ) : null}
      {compositeDetail ? (
        <div className="market-signal-drawer-backdrop" role="presentation" onClick={() => setCompositeDetail(null)}>
          <aside className="market-signal-history-drawer market-signal-composite-drawer" role="dialog" aria-modal="true" aria-label="복합 시그널 운영 상세" onClick={(event) => event.stopPropagation()}>
            <header>
              <div><span>복합 시그널 운영 상세</span><strong>{String(compositeDetail.signal_name ?? "-")}</strong><small title={String(compositeDetail.signal_code ?? "")}>{String(compositeDetail.model_display_name ?? "조건 결합형")} · 룰 v{String(compositeDetail.current_version ?? compositeDetail.rule_version ?? 1)}</small></div>
              <button className="btn btn-secondary" type="button" onClick={() => setCompositeDetail(null)}>닫기</button>
            </header>
            <div className="market-signal-history-body">
              <section className="market-signal-history-summary">
                <div><span>운영 상태</span><strong>{String(compositeDetail.operation_status_display_name ?? label(compositeDetail.status))}</strong></div>
                <div><span>현재 판정</span><strong>{String(compositeDetail.current_evaluation_display_name ?? label(compositeDetail.current_evaluation_state))}</strong></div>
                <div><span>검증 상태</span><strong>{validationLabel(compositeDetail.validation_status)}</strong></div>
                <div><span>최근 평가</span><strong>{String((compositeDetail.latest_evaluation as Record<string, unknown> | undefined)?.observation_date ?? "기록 대기")}</strong></div>
              </section>
              {Object.entries(ROLE_LABELS).filter(([role]) => role !== "REQUIRED").map(([role, roleName]) => {
                const conditions = ((compositeDetail.conditions as Record<string, unknown>[] | undefined) ?? []).filter((condition) => {
                  const conditionRole = String(condition.condition_role ?? condition.role).toUpperCase();
                  return role === "TRIGGER" ? ["TRIGGER", "REQUIRED"].includes(conditionRole) : conditionRole === role;
                });
                if (!conditions.length) return null;
                return <section className="market-signal-drawer-section" key={role}><h3>{roleName}</h3><ul className="market-signal-condition-list">{conditions.map((condition, index) => <li key={`${role}-${index}`} title={String(condition.technical_text ?? "")}><strong>{String(condition.display_text ?? condition.item_display_name ?? condition.item_code)}</strong><span>{condition.passed === true ? "충족" : condition.missing === true ? "데이터 부족" : condition.passed === false ? "미충족" : "설정됨"}</span></li>)}</ul></section>;
              })}
            </div>
            <footer><button className="btn btn-secondary" type="button" onClick={() => setCompositeDetail(null)}>닫기</button></footer>
          </aside>
        </div>
      ) : null}

      {historyTarget ? (
        <div className="market-signal-drawer-backdrop" role="presentation" onClick={() => setHistoryTarget(null)}>
          <aside className="market-signal-history-drawer" role="dialog" aria-modal="true" aria-label="평가 이력" onClick={(event) => event.stopPropagation()}>
            <header>
              <div>
                <span>평가 이력</span>
                <strong>{String(historyTarget.item_name ?? historyTarget.signal_name ?? historyTarget.item_code ?? historyTarget.signal_code ?? "-")}</strong>
                <small><b>운영</b> · 룰 v{String(historyData?.signal.rule_version ?? historyTarget.current_version ?? 1)}</small>
              </div>
              <button className="btn btn-secondary" type="button" onClick={() => setHistoryTarget(null)}>닫기</button>
            </header>
            <div className="market-signal-history-body">
              {historyLoading && !historyData ? <div className="market-signal-history-status">평가 이력을 불러오는 중입니다.</div> : null}
              {historyError ? (
                <div className="market-signal-history-status error"><strong>평가 이력을 불러오지 못했습니다.</strong><p>{historyError}</p><button className="btn btn-secondary" type="button" onClick={() => fetchEvaluationHistory(historyTarget, historyFilter)}>다시 시도</button></div>
              ) : null}
              {historyData ? (
                <>
                  <section className="market-signal-history-summary">
                    {[
                      ["운영 시작일", String(historyData.operation_summary.activated_at ?? "-").slice(0, 10)],
                      ["마지막 평가", String(historyData.operation_summary.last_evaluated_at ?? "-")],
                      ["누적 평가", `${historyData.live_statistics.total_evaluation_count}회`],
                      ["상태 전환", `${historyData.live_statistics.transition_count}회`],
                      ["추세 이탈 후보", `${historyData.live_statistics.break_candidate_count}회`],
                      ["추세 이탈 확인", `${historyData.live_statistics.break_confirmed_count}회`],
                      ["일시 이탈 후 복귀", `${historyData.live_statistics.false_break_count}회`],
                      ["반전 확인", `${historyData.live_statistics.reversal_confirmed_count}회`],
                      ["평가 오류", `${historyData.live_statistics.error_count}회`],
                    ].map(([title, value]) => <div key={title}><span>{title}</span><strong>{value}</strong></div>)}
                  </section>

                  <section className="market-signal-history-compare">
                    <div><span>과거 검증 결과</span><strong>최근 {historyData.validation_statistics.period_years ?? "-"}년</strong><p>일시 이탈 후 복귀 {historyData.validation_statistics.false_break_count}회</p></div>
                    <div><span>운영 이후</span><strong>{String(historyData.operation_summary.activated_at ?? "-").slice(0, 10)} 이후</strong><p>일시 이탈 후 복귀 {historyData.live_statistics.false_break_count}회</p></div>
                  </section>

                  {historyData.chart.length ? (
                    <section className="market-signal-history-panel">
                      <div className="market-signal-history-heading"><h3>운영 이후 추세</h3><span>LIVE 평가 기준</span></div>
                      <TrendPreviewChart rows={historyData.chart} eventRows={historyData.evaluations} />
                    </section>
                  ) : null}

                  <section className="market-signal-history-toolbar">
                    <label><span>평가 필터</span><select className="input-control" value={historyFilter} onChange={(event) => changeHistoryFilter(event.target.value as HistoryFilter)}>
                      <option value="ALL">전체 평가</option>
                      <option value="TRANSITION">상태 전환만</option>
                      <option value="TREND_WEAKENING">추세 약화</option>
                      <option value="BREAK_CANDIDATE">추세 이탈 후보</option>
                      <option value="BREAK_CONFIRMED">추세 이탈 확인</option>
                      <option value="FALSE_BREAK">일시 이탈 후 복귀</option>
                      <option value="REVERSAL_CONFIRMED">반전 확인</option>
                      <option value="ERROR">평가 오류</option>
                    </select></label>
                    <span>{historyData.pagination.total}건</span>
                  </section>

                  {!historyData.evaluations.length ? (
                    <section className="market-signal-history-empty">
                      <h3>평가 이력</h3>
                      <strong>{historyData.baseline_status.exists ? "조건에 맞는 평가 이력이 없습니다." : "운영 시작 기준 평가가 아직 저장되지 않았습니다."}</strong>
                      <p>{historyData.live_statistics.total_evaluation_count === 0 ? "운영 활성화 이후 저장된 자동 평가 이력이 없습니다." : "선택한 필터에 해당하는 평가 이력이 없습니다."}</p>
                      <dl><dt>운영 시작일</dt><dd>{String(historyData.operation_summary.activated_at ?? "-").slice(0, 10)}</dd><dt>현재 기준 상태</dt><dd>{label(historyTarget.evaluation_status)}</dd></dl>
                      <p>다음 지표 갱신 후 자동 평가 결과가 기록됩니다.</p>
                      {historyData.baseline_status.repair_available ? <button className="btn btn-secondary" type="button" onClick={repairHistoryBaseline}>기준 평가 생성</button> : null}
                    </section>
                  ) : (
                    <section className="market-signal-history-timeline">
                      {historyData.evaluations.map((item) => (
                        <details key={item.id ?? `${item.observation_date}-${item.evaluation_type}`} className={`state-${item.current_state.toLowerCase()}`} open={item.is_state_transition || item.evaluation_type.includes("BASELINE")}>
                          <summary>
                            <div><strong>{item.observation_date}</strong><span>{item.evaluation_type_display_name} · {item.evaluated_at ?? "-"}</span></div>
                            <div>{item.is_state_transition ? <><span>{item.previous_display_name ?? "-"}</span><b>→</b></> : <span>상태 변화 없음</span>}<strong>{item.display_name}</strong></div>
                          </summary>
                          <div className="market-signal-history-detail">
                            <p>{item.easy_explanation ?? "판정 근거가 기록되지 않았습니다."}</p>
                            <dl>
                              <dt>현재 방향</dt><dd>{label(item.direction_state)}</dd>
                              <dt>현재값</dt><dd>{num(item.current_value)}</dd>
                              <dt>추세 강도</dt><dd>{num(item.trend_strength)}</dd>
                              <dt>채널 위치</dt><dd>{num(item.channel_position)}</dd>
                              <dt>지속기간</dt><dd>{item.duration_count ?? "-"}</dd>
                              <dt>R²</dt><dd>{num(item.r_squared)}</dd>
                              <dt>정규화 기울기</dt><dd>{num(item.normalized_slope)}</dd>
                              <dt>데이터 품질</dt><dd>{item.data_quality ?? "-"}</dd>
                              <dt>룰 버전</dt><dd>v{item.rule_version}</dd>
                              <dt>수집 실행</dt><dd>{item.collection_run_id ? `#${item.collection_run_id}` : "-"}</dd>
                            </dl>
                            {item.event_summary ? <p className="market-signal-history-event">연결 이벤트 · {item.event_summary}</p> : null}
                          </div>
                        </details>
                      ))}
                    </section>
                  )}

                  <section className="market-signal-history-help">
                    <h3>평가 이력이란?</h3><p>운영 활성화 이후 새로운 지표 데이터가 들어올 때마다 DrCT가 현재 추세 상태를 평가한 기록입니다.</p>
                    <h3>상태 전환이란?</h3><p>이전 평가와 현재 평가의 판정이 달라진 경우입니다.</p>
                    <h3>일시 이탈 후 복귀란?</h3><p>추세 채널을 벗어났지만 설정된 확인 기간 안에 기존 채널로 다시 들어온 상태입니다.</p>
                    <h3>과거 검증과 평가 이력의 차이</h3><p>과거 검증은 운영 전 시뮬레이션이며, 평가 이력은 운영 활성화 이후 실제 데이터로 수행한 기록입니다.</p>
                  </section>
                </>
              ) : null}
            </div>
            <footer>
              <button className="btn btn-secondary" type="button" disabled={String(historyTarget.rule_status).toUpperCase() !== "ACTIVE" || historyLoading} onClick={runManualEvaluation}>수동 재평가</button>
              <button className="btn btn-secondary" type="button" onClick={() => setHistoryTarget(null)}>닫기</button>
            </footer>
          </aside>
        </div>
      ) : null}
      {draftPreview ? (
        <div className="market-signal-drawer-backdrop" role="presentation" onClick={closePreviewDrawer}>
          <aside className="market-signal-analysis-drawer" role="dialog" aria-modal="true" aria-label="1차 추세 확인" onClick={(event) => event.stopPropagation()}>
            <header>
              <div><span>1차 추세 확인</span><strong>{String((draftPreview.catalog as Record<string, unknown> | undefined)?.item_name ?? "-")}</strong></div>
              <button className="btn btn-secondary" type="button" onClick={closePreviewDrawer}>닫기</button>
            </header>
            <section className="market-signal-period-bar">
              <PreviewPeriodInfo period={draftPreview.period as Record<string, unknown> | undefined} />
              <div className="market-signal-period-buttons" role="group" aria-label="차트 기간">
                {PREVIEW_PERIODS.map((period) => (
                  <button key={period} className={previewPeriod === period ? "active" : ""} type="button" onClick={async () => {
                    setPreviewPeriod(period);
                    const catalog = draftPreview.catalog as MarketSignalCatalogItem;
                    const result = await repositories.marketSignals.previewSingleIndicatorDraft({ item_type: catalog.item_type, item_code: catalog.item_code, profile_code: catalog.recommended_profile_code, period, configuration: previewConfig });
                    setDraftPreview(result.item);
                    setPreviewConfig(previewConfigFrom(result.item.applied_configuration));
                  }}>{period}</button>
                ))}
              </div>
            </section>
            <section className="market-signal-drawer-grid">
              <div><span>현재값</span><strong>{num((draftPreview.current_trend as Record<string, unknown> | undefined)?.latest_value)}</strong></div>
              <div><span>기준일</span><strong>{String((draftPreview.current_trend as Record<string, unknown> | undefined)?.observation_date ?? "-")}</strong></div>
              <div><span>Provider</span><strong>{String((draftPreview.catalog as Record<string, unknown> | undefined)?.provider ?? "-")}</strong></div>
              <div><span>주기</span><strong>{String((draftPreview.catalog as Record<string, unknown> | undefined)?.frequency ?? "-")}</strong></div>
              <div><span>관측값</span><strong>{String((draftPreview.catalog as Record<string, unknown> | undefined)?.data_count ?? 0)}개</strong></div>
              <div><span>추천 모델</span><strong>{String((draftPreview.profile as Record<string, unknown> | undefined)?.profile_name ?? "-")}</strong></div>
            </section>
            <TrendPreviewChart
              rows={(draftPreview.chart as Record<string, unknown>[] | undefined) ?? ((draftPreview.current_trend as Record<string, unknown> | undefined)?.series as Record<string, unknown>[] | undefined)}
              period={draftPreview.period as Record<string, unknown> | undefined}
            />
            <section className="market-signal-drawer-section">
              <h3>DrCT 임시 판정</h3>
              <dl className="market-signal-drawer-metrics">
                <dt>현재 방향</dt><dd>{label((draftPreview.current_trend as Record<string, unknown> | undefined)?.trend_state)}</dd>
                <dt>추세 건전성</dt><dd>{label((draftPreview.current_trend as Record<string, unknown> | undefined)?.trend_health)}</dd>
                <dt>추세 강도</dt><dd>{num((draftPreview.current_trend as Record<string, unknown> | undefined)?.trend_strength)}</dd>
                <dt>채널 위치</dt><dd>{num((draftPreview.current_trend as Record<string, unknown> | undefined)?.channel_position)}</dd>
                <dt>지속기간</dt><dd>{String((draftPreview.current_trend as Record<string, unknown> | undefined)?.trend_duration ?? "-")}</dd>
                <dt>R²</dt><dd>{num((draftPreview.current_trend as Record<string, unknown> | undefined)?.r_squared)}</dd>
                <dt>정규화 기울기</dt><dd>{num((draftPreview.current_trend as Record<string, unknown> | undefined)?.normalized_slope)}</dd>
              </dl>
            </section>
            <section className="market-signal-drawer-section">
              <h3>쉬운 설명</h3>
              <p>{String((draftPreview.plain_explanation as Record<string, unknown> | undefined)?.judgement ?? "-")}</p>
              <ul>{(((draftPreview.plain_explanation as Record<string, unknown> | undefined)?.reasons as string[] | undefined) ?? []).map((reason) => <li key={reason}>{reason}</li>)}</ul>
              <p>{String((draftPreview.plain_explanation as Record<string, unknown> | undefined)?.caution ?? "")}</p>
            </section>
            <section className="market-signal-drawer-section">
              <div className="market-signal-setting-head">
                <h3>추천 설정</h3>
                {hasPreviewUnsavedChanges ? <span>수정된 임시 설정 · 아직 시그널 초안으로 저장되지 않았습니다.</span> : null}
              </div>
              <dl className="market-signal-setting-grid">
                {PREVIEW_SETTING_FIELDS.map(([key, text]) => (
                  <div className="market-signal-setting-row" key={key} title={key}>
                    <dt>{text}</dt>
                    <dd>{isPreviewEditing ? <input className="input-control" type="number" step={key === "channel_multiplier" ? "0.1" : "1"} value={previewConfig[key] ?? 0} onChange={(event) => {
                      const next = { ...previewConfig, [key]: Number(event.target.value) };
                      setPreviewConfig(next);
                      setPreviewConfigError(validatePreviewConfig(next, Number((draftPreview.catalog as Record<string, unknown> | undefined)?.data_count ?? 0)));
                    }} /> : String(previewConfig[key] ?? "-")}</dd>
                  </div>
                ))}
              </dl>
              {previewConfigError ? <p className="market-signal-setting-error">{previewConfigError}</p> : null}
              {isPreviewEditing ? (
                <div className="market-signal-setting-actions">
                  <button className="btn btn-secondary" type="button" onClick={() => { setPreviewConfig(previewDefaultConfig); setPreviewConfigError(""); }}>기본값 복원</button>
                  <button className="btn btn-secondary" type="button" onClick={() => { setIsPreviewEditing(false); setPreviewConfig(previewConfigFrom(draftPreview.applied_configuration)); setPreviewConfigError(""); }}>취소</button>
                  <button className="btn btn-primary" type="button" disabled={Boolean(previewConfigError)} onClick={reanalyzePreview}>수정 설정으로 다시 분석</button>
                </div>
              ) : null}
            </section>
            <footer className="market-signal-drawer-footer">
              <div><button className="btn btn-secondary" type="button" onClick={() => setIsPreviewEditing(true)}>설정 조정</button></div>
              <div>
                <button className="btn btn-secondary" type="button" onClick={closePreviewDrawer}>닫기</button>
                <button className="btn btn-primary" type="button" title={previewConfigError || (draftPreview.existing_signal ? "이미 이 지표의 시그널 초안이 존재합니다." : !draftPreview["can_create_draft"] ? "분석에 필요한 데이터가 부족합니다." : "")} disabled={Boolean(previewConfigError) || Boolean((draftPreview.existing_signal as Record<string, unknown> | null | undefined)?.id) || !draftPreview["can_create_draft"]} onClick={() => setDraftConfirmItem(draftPreview.catalog as MarketSignalCatalogItem)}>2차 시그널 초안 생성</button>
              </div>
            </footer>
          </aside>
        </div>
      ) : null}

      {phenomenonFlowItem ? (
        <div className="market-signal-modal-backdrop" role="presentation" onClick={() => setPhenomenonFlowItem(null)}>
          <section className="market-signal-confirm-modal market-phenomenon-flow-modal" role="dialog" aria-modal="true" aria-label="경제 흐름 후보 추가" onClick={(event) => event.stopPropagation()}>
            <h3>경제 흐름 후보로 추가</h3>
            <dl><dt>현상</dt><dd>{String(phenomenonFlowItem.display_title ?? phenomenonFlowItem.phenomenon_name ?? "-")}</dd><dt>현재 상태</dt><dd>{String(phenomenonFlowItem.current_state_label ?? "-")}</dd><dt>용도</dt><dd>향후 경제 흐름 관리 화면에서 원인·과정·결과 노드와 연결할 수 있습니다.</dd></dl>
            <label><span>표시 제목</span><input className="input-control" value={phenomenonFlowForm.candidate_title} onChange={(event) => setPhenomenonFlowForm((current) => ({ ...current, candidate_title: event.target.value }))} /></label>
            <label><span>분류</span><input className="input-control" value={phenomenonFlowForm.category} onChange={(event) => setPhenomenonFlowForm((current) => ({ ...current, category: event.target.value }))} /></label>
            <label><span>중요도</span><select className="input-control" value={phenomenonFlowForm.importance} onChange={(event) => setPhenomenonFlowForm((current) => ({ ...current, importance: event.target.value }))}><option value="LOW">낮음</option><option value="NORMAL">보통</option><option value="HIGH">높음</option><option value="CORE">핵심</option></select></label>
            <label><span>메모</span><textarea className="input-control" value={phenomenonFlowForm.user_note} onChange={(event) => setPhenomenonFlowForm((current) => ({ ...current, user_note: event.target.value }))} /></label>
            <label className="market-phenomenon-checkbox"><input type="checkbox" checked={phenomenonFlowForm.auto_update} onChange={(event) => setPhenomenonFlowForm((current) => ({ ...current, auto_update: event.target.checked }))} /><span>후속 현상 평가로 후보 상태 자동 갱신</span></label>
            <p>이번 단계에서는 후보만 저장하며 경제 흐름 그래프를 생성하거나 확정하지 않습니다.</p>
            <footer><button className="btn btn-secondary" type="button" onClick={() => setPhenomenonFlowItem(null)}>취소</button><button className="btn btn-primary" type="button" disabled={!phenomenonFlowForm.candidate_title.trim()} onClick={savePhenomenonFlowCandidate}>후보로 추가</button></footer>
          </section>
        </div>
      ) : null}
      {draftConfirmItem ? (
        <div className="market-signal-modal-backdrop" role="presentation">
          <section className="market-signal-confirm-modal" role="dialog" aria-modal="true" aria-label="시그널 초안 생성 확인">
            <h3>{draftConfirmItem.item_name ?? draftConfirmItem.item_code} 단일 지표 시그널 초안을 생성합니다.</h3>
            <dl><dt>시그널명</dt><dd>{draftConfirmItem.item_name ?? draftConfirmItem.item_code} 추세 전환</dd><dt>모델</dt><dd>{draftConfirmItem.recommended_profile_code}</dd><dt>생성 상태</dt><dd>초안</dd></dl>
            <p>초안을 생성해도 운영 시그널로 활성화되지 않습니다. 과거 검증 후 별도로 운영 활성화해야 합니다.</p>
            <footer><button className="btn btn-secondary" type="button" onClick={() => setDraftConfirmItem(null)}>취소</button><button className="btn btn-primary" type="button" onClick={() => createSingleDraft(draftConfirmItem)}>시그널 초안 생성</button></footer>
          </section>
        </div>
      ) : null}

      {bulkConfirmOpen ? (
        <div className="market-signal-modal-backdrop" role="presentation">
          <section className="market-signal-confirm-modal" role="dialog" aria-modal="true" aria-label="선택 시그널 초안 생성 확인">
            <h3>선택한 {selectedDraftKeys.length}개 지표의 시그널 초안을 생성합니다.</h3>
            <p>미등록 상태이고 데이터가 준비된 지표만 생성됩니다. 이미 초안 또는 운영 상태인 지표는 제외됩니다.</p>
            <footer><button className="btn btn-secondary" type="button" onClick={() => setBulkConfirmOpen(false)}>취소</button><button className="btn btn-primary" type="button" onClick={createSelectedDrafts}>{selectedDraftKeys.length}개 시그널 초안 생성</button></footer>
          </section>
        </div>
      ) : null}

      {validationDialog ? (
        <div className="market-signal-modal-backdrop" role="presentation" onClick={() => setValidationDialog(null)}>
          <section className="market-signal-confirm-modal market-signal-validation-modal" role="dialog" aria-modal="true" aria-label="과거 검증 기간 선택" onClick={(event) => event.stopPropagation()}>
            <h3>과거 검증</h3>
            <p><strong>{String(validationDialog.item.item_name ?? validationDialog.item.signal_name ?? validationDialog.item.item_code ?? validationDialog.item.signal_code ?? "시그널")}</strong>의 검증 기간을 선택하세요.</p>
            <div className="market-signal-validation-years" role="group" aria-label="검증 기간">
              {[1, 3, 5].map((years) => (
                <button className={years === 3 ? "btn btn-primary" : "btn btn-secondary"} key={years} type="button" onClick={() => {
                  const target = validationDialog;
                  setValidationDialog(null);
                  if (target.kind === "single") void runValidation(target.item, years);
                  else void runCompositeValidation(target.item, years);
                }}>{years}년 검증</button>
              ))}
            </div>
            <p>검증 상세 표본은 실행 응답에서만 사용하며 운영에는 집계 결과만 저장됩니다.</p>
            <footer><button className="btn btn-secondary" type="button" onClick={() => setValidationDialog(null)}>닫기</button></footer>
          </section>
        </div>
      ) : null}
      {activationItem || deactivationItem || versionItem ? (
        <div className="market-signal-modal-backdrop" role="presentation">
          <section className="market-signal-confirm-modal" role="dialog" aria-modal="true" aria-label="운영 상태 변경">
            <h3>{activationItem ? "운영 활성화" : deactivationItem ? "운영 중지" : "새 버전 초안"}</h3>
            <p>{String((activationItem ?? deactivationItem ?? versionItem)?.item_name ?? "-")}</p>
            <label><span>사유</span><textarea className="input-control" value={modalReason} onChange={(event) => setModalReason(event.target.value)} /></label>
            {activationItem ? <><label><span>운영 목적</span><input className="input-control" value={modalPurpose} onChange={(event) => setModalPurpose(event.target.value)} /></label><label><span>메모</span><textarea className="input-control" value={modalMemo} onChange={(event) => setModalMemo(event.target.value)} /></label></> : null}
            <p>{activationItem ? "운영 활성화 후 지표 데이터가 갱신될 때마다 이 룰이 자동 평가됩니다." : deactivationItem ? "중지 후 과거 평가와 이벤트는 유지되며 운영 입력에서는 제외됩니다." : "현재 운영 설정을 직접 덮어쓰지 않고 새 DRAFT 버전으로 복제합니다."}</p>
            {modalError ? <p className="inline-result inline-error" role="alert">{modalError}</p> : null}
            <footer>
              <button className="btn btn-secondary" type="button" disabled={modalBusy} onClick={() => { setActivationItem(null); setDeactivationItem(null); setVersionItem(null); setModalReason(""); setModalPurpose(""); setModalMemo(""); setModalError(""); }}>취소</button>
              <button className="btn btn-primary" type="button" disabled={modalBusy} onClick={activationItem ? activateSignal : deactivationItem ? deactivateSignal : cloneVersion}>{modalBusy && versionItem ? "생성 중..." : activationItem ? "운영 활성화" : deactivationItem ? "운영 중지" : "새 버전 초안 생성"}</button>
            </footer>
          </section>
        </div>
      ) : null}
    </div>
  );
}

export default MarketSignalsPage;
