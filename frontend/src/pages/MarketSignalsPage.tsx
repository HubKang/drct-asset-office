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
  MarketSignalModelProfile,
  MarketSignalOverview,
  MarketSignalRuleTemplate,
} from "@/types/marketSignal";

type MainTab = "today" | "signals" | "phenomena" | "studio" | "learning";
type SignalSubTab = "single" | "composite";
type StudioSubTab = "simple" | "templates" | "gpt" | "advanced";
type OperationStatus = "ALL" | "NOT_REGISTERED" | "DRAFT" | "ACTIVE" | "INACTIVE" | "DATA_INSUFFICIENT";
type ValidationFilter = "ALL" | "UNVALIDATED" | "NEEDS_REVISION" | "VALIDATED" | "ACTIVATION_READY";

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
  TREND_RESUMED: "추세 재개",
  DATA_INSUFFICIENT: "데이터 부족",
  NOT_EVALUATED: "미평가",
  CANDIDATE: "시작 조건",
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
  ["false_break_window", "False Break 확인 기간"],
  ["reversal_persistence", "반전 확인 기간"],
] as const;

const ROLES: MarketSignalCondition["condition_role"][] = ["TRIGGER", "REQUIRED", "CONFIRM", "CONTEXT", "OPPOSING", "INVALIDATION"];
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

function TrendPreviewChart({ rows, period }: { rows?: Record<string, unknown>[]; period?: Record<string, unknown> }) {
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

function StatusPair({ rule, evalStatus }: { rule?: unknown; evalStatus?: unknown }) {
  return (
    <div className="market-signal-status-pair">
      <span>{label(rule)}</span>
      <strong>{label(evalStatus)}</strong>
    </div>
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
              {String(item.item_code ?? "-")}
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
  if ((config.false_break_window ?? 0) < 1) return "False Break 확인 기간은 1 이상이어야 합니다.";
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
  const [singleReadinessFilter, setSingleReadinessFilter] = useState<OperationStatus>("ALL");
  const [validationFilter, setValidationFilter] = useState<ValidationFilter>("ALL");
  const [singleProfileFilter, setSingleProfileFilter] = useState("ALL");
  const [singleSearch, setSingleSearch] = useState("");
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
  const [activationItem, setActivationItem] = useState<Record<string, unknown> | null>(null);
  const [deactivationItem, setDeactivationItem] = useState<Record<string, unknown> | null>(null);
  const [versionItem, setVersionItem] = useState<Record<string, unknown> | null>(null);
  const [modalReason, setModalReason] = useState("");
  const [gptGoal, setGptGoal] = useState("미국 금리 상승이 성장주 상대강도 약화로 이어지는 시점을 찾고 싶다.");
  const [gptPrompt, setGptPrompt] = useState("");
  const [notice, setNotice] = useState("");
  const [loading, setLoading] = useState(false);

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

  const activateSignal = async () => {
    if (!activationItem) return;
    await repositories.marketSignals.activateWithApproval(Number(activationItem.signal_definition_id), { reason: modalReason });
    setActivationItem(null);
    setModalReason("");
    setNotice(`${String(activationItem.item_name ?? activationItem.item_code)} 시그널을 운영 활성화했습니다.`);
    await load();
  };

  const deactivateSignal = async () => {
    if (!deactivationItem) return;
    await repositories.marketSignals.deactivateWithReason(Number(deactivationItem.signal_definition_id), { reason: modalReason });
    setDeactivationItem(null);
    setModalReason("");
    setNotice(`${String(deactivationItem.item_name ?? deactivationItem.item_code)} 시그널을 중지했습니다.`);
    await load();
  };

  const cloneVersion = async () => {
    if (!versionItem) return;
    await repositories.marketSignals.cloneVersion(Number(versionItem.signal_definition_id), { reason: modalReason || "새 버전 초안 생성" });
    setVersionItem(null);
    setModalReason("");
    setNotice(`${String(versionItem.item_name ?? versionItem.item_code)} 새 버전 초안을 생성했습니다.`);
    await load();
  };

  const createGptDesignPrompt = async () => {
    const result = await repositories.marketSignals.gptDesign({ goal_text: gptGoal });
    setGptPrompt(String(result.item.prompt ?? ""));
    setNotice(`GPT 간편 설계 준비: ${String(result.item.validation_status ?? "PROMPT_READY")}`);
  };

  const singleCards = overview?.single_indicator_signals ?? [];
  const compositeCards = overview?.composite_indicator_signals ?? [];
  const phenomenonCards = overview?.objective_phenomena ?? [];
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

      <section className="market-signal-stage-guide" aria-label="단일 지표 시그널 운영 단계">
        {STAGE_STEPS.map((step, idx) => (
          <span key={step} className={draftPreview ? (idx === 0 ? "active" : "") : ""}>
            <b>{idx + 1}</b>{step.replace(/^\d차\s*/, "")}
          </span>
        ))}
      </section>

      <section className="market-signal-summary-grid">
        <div><span>추세 이탈 후보</span><strong>{overview?.summary.trend_break_candidate ?? 0}</strong></div>
        <div><span>추세 이탈 확인</span><strong>{overview?.summary.trend_break_confirmed ?? 0}</strong></div>
        <div><span>반전 확인</span><strong>{overview?.summary.reversal_confirmed ?? 0}</strong></div>
        <div><span>False Break</span><strong>{overview?.summary.false_break ?? 0}</strong></div>
        <div><span>데이터 부족</span><strong>{overview?.summary.data_insufficient ?? 0}</strong></div>
      </section>

      <div className="market-signal-tabs" role="tablist">
        {[
          ["today", "오늘의 전환"],
          ["signals", "시그널"],
          ["phenomena", "객관적 현상"],
          ["studio", "룰 스튜디오"],
          ["learning", "평가·학습"],
        ].map(([key, text]) => (
          <button key={key} className={mainTab === key ? "active" : ""} type="button" onClick={() => setMainTab(key as MainTab)}>{text}</button>
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
          <div className="market-signal-subtabs">
            <button className={signalTab === "single" ? "active" : ""} type="button" onClick={() => setSignalTab("single")}>단일 지표 시그널</button>
            <button className={signalTab === "composite" ? "active" : ""} type="button" onClick={() => setSignalTab("composite")}>복합 지표 시그널</button>
          </div>
          {signalTab === "single" ? (
            <>
              <section className="market-signal-filter-row">
                <div className="market-signal-filter-summary">
                  <strong>{filteredSignalCatalog.length} / {signalCatalog.total_count}개</strong>
                  <span>선택 {selectedDraftKeys.length}개</span>
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
                    <button key={value} className={singleReadinessFilter === value ? "active" : ""} type="button" role="tab" aria-selected={singleReadinessFilter === value} onClick={() => {
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
                          <span title={opStatus === "NOT_REGISTERED" ? "단일 지표 시그널 미등록" : undefined}>{operationLabel(opStatus)}</span>
                          {opStatus === "DRAFT" ? <span>{validationLabel(validationStatus)}</span> : null}
                          <strong>{existing ? `현재 판정: ${String(existing.status_label ?? label(existing.evaluation_status))}` : label(catalogItem.readiness)}</strong>
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
                            <button className="btn btn-secondary" type="button" onClick={() => previewSingleDraft(catalogItem)}>1차 추세 확인</button>
                            <button className="btn btn-primary" type="button" disabled={!canCreate} onClick={() => setDraftConfirmItem(catalogItem)}>2차 시그널 초안 생성</button>
                          </>
                        ) : null}
                        {opStatus === "DRAFT" && existing ? (
                          <>
                            <button className="btn btn-secondary" type="button" onClick={() => previewSingleDraft(catalogItem)}>상세 분석</button>
                            <button className="btn btn-secondary" type="button" onClick={() => runValidation(existing, 3)}>3차 과거 검증</button>
                            <button className="btn btn-primary" type="button" disabled={!["VALIDATED", "ACTIVATION_READY"].includes(validationStatus) && !existing.activation_ready} onClick={() => { setActivationItem(existing); setModalReason(""); }}>4차 운영 활성화</button>
                          </>
                        ) : null}
                        {opStatus === "ACTIVE" && existing ? (
                          <>
                            <button className="btn btn-secondary" type="button" onClick={() => previewSingleDraft(catalogItem)}>운영 상세</button>
                            <button className="btn btn-secondary" type="button" onClick={() => setNotice("평가 이력은 상세 API로 조회 가능합니다.")}>평가 이력</button>
                            <button className="btn btn-secondary" type="button" onClick={() => { setVersionItem(existing); setModalReason(""); }}>새 버전 초안</button>
                            <button className="btn btn-secondary" type="button" onClick={() => { setDeactivationItem(existing); setModalReason(""); }}>운영 중지</button>
                          </>
                        ) : null}
                        {opStatus === "INACTIVE" && existing ? (
                          <>
                            <button className="btn btn-secondary" type="button" onClick={() => setNotice("평가 이력은 상세 API로 조회 가능합니다.")}>평가 이력</button>
                            <button className="btn btn-secondary" type="button" onClick={() => { setVersionItem(existing); setModalReason(""); }}>새 버전 초안</button>
                          </>
                        ) : null}
                      </div>
                      <p className="market-signal-next-check">{opStatus === "NOT_REGISTERED" ? "그래프와 추천 분석 기준을 확인한 뒤 시그널 초안 생성 여부를 결정하세요." : opStatus === "DRAFT" ? "과거 데이터에서 추세 이탈과 False Break 판정이 적절한지 확인하세요." : opStatus === "ACTIVE" ? "지표 갱신 후 자동으로 평가되고 있습니다." : existing ? ((existing.next_checks as string[]) ?? [])[0] : catalogItem.recommended_profile_reason}</p>
                    </article>
                  );
                })}
              </section>
            </>
          ) : (
            <section className="market-signal-card-grid">
              {compositeCards.map((item) => (
                <article key={String(item.id)} className={cardClass(item.evaluation_status)}>
                  <header><div><strong>{String(item.signal_name)}</strong><small>{String(item.signal_code)}</small></div><StatusPair rule={item.rule_status_label} evalStatus={item.status_label} /></header>
                  <div className="market-signal-card-body">
                    <div className="market-signal-card-reading"><b>{String(item.number_label ?? "-")}</b><span>{String(item.trigger_summary)} · {String(item.confirm_summary)}</span></div>
                    <Sparkline points={item.sparkline as Record<string, unknown>[]} />
                  </div>
                  <footer><span>{String(item.trigger_summary)}</span><span>{String(item.confirm_summary)}</span><span>{String(item.opposing_summary)}</span></footer>
                  <div className="market-signal-mini-timeline">{((item.timeline as Record<string, unknown>[]) ?? []).slice(0, 4).map((row, idx) => <span key={idx}>{String(row.label)} {String(row.item_code ?? "")}</span>)}</div>
                </article>
              ))}
            </section>
          )}
        </>
      ) : null}

      {mainTab === "phenomena" ? (
        <section className="market-signal-card-grid">
          {phenomenonCards.map((item) => (
            <article key={String(item.id)} className={cardClass(item.evaluation_status)}>
              <header><div><strong>{String(item.phenomenon_name ?? item.phenomenon_code)}</strong><small>{String(item.phenomenon_code)}</small></div><StatusPair rule={item.rule_status_label} evalStatus={item.status_label} /></header>
              <div className="market-signal-phenomenon-reading"><b>{String(item.number_label ?? "-")}</b><p>{String(item.plain_judgement ?? "")}</p></div>
              <div className="market-signal-evidence-grid">
                <EvidenceSummary title="시작 조건" count={String(item.start_condition_summary ?? "")} items={item.trigger_evidence as Record<string, unknown>[]} />
                <EvidenceSummary title="지속 확인" count={String(item.confirm_condition_summary ?? "")} items={item.confirm_evidence as Record<string, unknown>[]} />
                <EvidenceSummary title="반대 근거" items={item.opposing_evidence as Record<string, unknown>[]} />
                <EvidenceSummary title="데이터 부족" items={item.missing_conditions as Record<string, unknown>[]} />
              </div>
              <p className="market-signal-next-check">{((item.next_checks as string[]) ?? [])[0]}</p>
            </article>
          ))}
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

      {draftPreview ? (
        <div className="market-signal-drawer-backdrop" role="presentation" onClick={closePreviewDrawer}>
          <aside className="market-signal-analysis-drawer" role="dialog" aria-modal="true" aria-label="1차 추세 확인" onClick={(event) => event.stopPropagation()}>
            <header>
              <div><span>1차 추세 확인</span><strong>{String((draftPreview.catalog as Record<string, unknown> | undefined)?.item_name ?? "-")}</strong></div>
              <button className="btn btn-secondary" type="button" onClick={closePreviewDrawer}>닫기</button>
            </header>
            <section className="market-signal-period-bar">
              <div className="market-signal-period-info">
                <div>
                  <span>표시 구간</span>
                  <strong>
                    {String((draftPreview.period as Record<string, unknown> | undefined)?.actual_period_description ?? "-")}
                    {" · "}
                    {String((draftPreview.period as Record<string, unknown> | undefined)?.display_range_start ?? (draftPreview.period as Record<string, unknown> | undefined)?.range_start ?? "-")}
                    {" ~ "}
                    {String((draftPreview.period as Record<string, unknown> | undefined)?.display_range_end ?? (draftPreview.period as Record<string, unknown> | undefined)?.range_end ?? "-")}
                  </strong>
                </div>
                <div>
                  <span>회귀·채널 분석 구간</span>
                  <strong>{String((draftPreview.period as Record<string, unknown> | undefined)?.trend_analysis_period_description ?? "회귀·채널 분석 데이터 부족")}</strong>
                </div>
              </div>
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

      {activationItem || deactivationItem || versionItem ? (
        <div className="market-signal-modal-backdrop" role="presentation">
          <section className="market-signal-confirm-modal" role="dialog" aria-modal="true" aria-label="운영 상태 변경">
            <h3>{activationItem ? "운영 활성화" : deactivationItem ? "운영 중지" : "새 버전 초안"}</h3>
            <p>{String((activationItem ?? deactivationItem ?? versionItem)?.item_name ?? "-")}</p>
            <label><span>사유</span><textarea className="input-control" value={modalReason} onChange={(event) => setModalReason(event.target.value)} /></label>
            <p>{activationItem ? "운영 활성화 후 지표 데이터가 갱신될 때마다 이 룰이 자동 평가됩니다." : deactivationItem ? "중지 후 과거 평가와 이벤트는 유지되며 운영 입력에서는 제외됩니다." : "현재 운영 설정을 직접 덮어쓰지 않고 새 DRAFT 버전으로 복제합니다."}</p>
            <footer>
              <button className="btn btn-secondary" type="button" onClick={() => { setActivationItem(null); setDeactivationItem(null); setVersionItem(null); setModalReason(""); }}>취소</button>
              <button className="btn btn-primary" type="button" onClick={activationItem ? activateSignal : deactivationItem ? deactivateSignal : cloneVersion}>{activationItem ? "운영 활성화" : deactivationItem ? "운영 중지" : "새 버전 초안 생성"}</button>
            </footer>
          </section>
        </div>
      ) : null}
    </div>
  );
}

export default MarketSignalsPage;
