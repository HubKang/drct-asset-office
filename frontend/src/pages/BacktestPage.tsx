import { KeyboardEvent, useEffect, useMemo, useRef, useState } from "react";
import { Play, Plus, Save, Search, Trash2, X } from "lucide-react";
import PageHeader from "@/components/common/PageHeader";
import SectionCard from "@/components/common/SectionCard";
import { repositories } from "@/services";
import type {
  BacktestConditionField,
  BacktestEquityPoint,
  BacktestOperator,
  BacktestRule,
  BacktestRuleInput,
  BacktestRun,
  BacktestRunDetail,
  BacktestStock,
  BuyConditionRow,
  SellConditionRow,
} from "@/types/backtest";
import type { TradeMethod } from "@/types/tradeJournal";

type BacktestTab = "settings" | "run";

type RuleForm = {
  rule_name: string;
  description: string;
  trade_method_id: string;
  buyConditions: BuyConditionRow[];
  sellConditions: SellConditionRow[];
  positionBasis: "cash" | "total_asset" | "fixed_amount" | "fixed_quantity";
  positionPercent: number;
  feeRate: number;
  slippageRate: number;
};

const fallbackFields: BacktestConditionField[] = [
  { field_key: "open_price", label: "시가", source_table: "stock_daily_prices", source_column: "open_price", data_type: "number", category: "가격", is_active: true, sort_order: 10 },
  { field_key: "high_price", label: "고가", source_table: "stock_daily_prices", source_column: "high_price", data_type: "number", category: "가격", is_active: true, sort_order: 20 },
  { field_key: "low_price", label: "저가", source_table: "stock_daily_prices", source_column: "low_price", data_type: "number", category: "가격", is_active: true, sort_order: 30 },
  { field_key: "close_price", label: "종가", source_table: "stock_daily_prices", source_column: "close_price", data_type: "number", category: "가격", is_active: true, sort_order: 40 },
  { field_key: "volume", label: "거래량", source_table: "stock_daily_prices", source_column: "volume", data_type: "number", category: "거래", is_active: true, sort_order: 50 },
  { field_key: "trading_value", label: "거래대금", source_table: "stock_daily_prices", source_column: "trading_value", data_type: "number", category: "거래", is_active: true, sort_order: 60 },
];

const operatorOptions: BacktestOperator[] = [">", ">=", "<", "<=", "=="];

const buyTypeLabels: Record<BuyConditionRow["condition_type"], string> = {
  field_value_compare: "필드 값 비교",
  field_vs_field: "필드 간 비교",
  field_vs_indicator: "이동평균 비교",
  field_vs_average_multiplier: "평균 배수 비교",
  candle_pattern: "캔들/패턴",
};

const sellTypeLabels: Record<SellConditionRow["condition_type"], string> = {
  take_profit_pct: "익절",
  stop_loss_pct: "손절",
  close_below_ma: "이평 하향 이탈",
  max_holding_days: "최대 보유일",
};

const patternLabels: Record<NonNullable<BuyConditionRow["pattern"]>, string> = {
  bullish_candle: "양봉",
  bearish_candle: "음봉",
  close_above_previous_high: "종가가 전일 고가 돌파",
  close_above_recent_high: "종가가 최근 N일 고가 돌파",
  close_below_recent_low: "종가가 최근 N일 저가 이탈",
};

const makeId = (prefix: string) => `${prefix}_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`;

const fmtNumber = (value?: number | null, digits = 0): string => {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "-";
  return Number(value).toLocaleString("ko-KR", { maximumFractionDigits: digits });
};

const fmtWon = (value?: number | null): string => (value === null || value === undefined ? "-" : `${fmtNumber(value)}원`);

const fmtPct = (value?: number | null): string => {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "-";
  const sign = Number(value) > 0 ? "+" : "";
  return `${sign}${Number(value).toFixed(2)}%`;
};

const profitClass = (value?: number | null): string => {
  const amount = Number(value || 0);
  if (amount > 0) return "backtest-positive";
  if (amount < 0) return "backtest-negative";
  return "";
};

const exitReasonLabel = (value?: string | null): string => {
  if (value === "stop_loss") return "손절";
  if (value === "take_profit") return "익절";
  if (value === "close_below_ma") return "이평 하향 이탈";
  if (value === "max_holding_days") return "최대 보유일";
  if (value === "open_position") return "미청산";
  return "-";
};

const addYears = (dateText: string, years: number): string => {
  const date = new Date(`${dateText}T00:00:00`);
  if (Number.isNaN(date.getTime())) return dateText;
  date.setFullYear(date.getFullYear() + years);
  return date.toISOString().slice(0, 10);
};

const defaultStartDateForStock = (stock: BacktestStock): string => {
  if (!stock.last_price_date) return stock.first_price_date || "";
  const twoYearsAgo = addYears(stock.last_price_date, -2);
  if (!stock.first_price_date) return twoYearsAgo;
  return stock.first_price_date > twoYearsAgo ? stock.first_price_date : twoYearsAgo;
};

const fieldLabel = (fields: BacktestConditionField[], fieldKey?: string) =>
  fields.find((field) => field.field_key === fieldKey)?.label || fieldKey || "-";

const defaultBuyCondition = (): BuyConditionRow => ({
  id: makeId("buy"),
  condition_type: "field_vs_indicator",
  left: { type: "field", field: "close_price", label: "종가" },
  operator: ">",
  right: { type: "moving_average", field: "close_price", period: 20, label: "20일 종가 이동평균" },
});

const defaultBuyConditions = (): BuyConditionRow[] => [
  defaultBuyCondition(),
  {
    id: makeId("buy"),
    condition_type: "field_vs_average_multiplier",
    left: { type: "field", field: "volume", label: "거래량" },
    operator: ">",
    right: { type: "average_multiplier", field: "volume", period: 20, multiplier: 1.5, label: "20일 평균 거래량의 1.5배" },
  },
  { id: makeId("buy"), condition_type: "candle_pattern", pattern: "bullish_candle" },
];

const defaultSellCondition = (): SellConditionRow => ({ id: makeId("sell"), condition_type: "stop_loss_pct", value: 5 });

const defaultSellConditions = (): SellConditionRow[] => [
  { id: makeId("sell"), condition_type: "take_profit_pct", value: 10 },
  { id: makeId("sell"), condition_type: "stop_loss_pct", value: 5 },
  { id: makeId("sell"), condition_type: "close_below_ma", field: "close_price", period: 20 },
  { id: makeId("sell"), condition_type: "max_holding_days", value: 20 },
];

const defaultRuleForm = (): RuleForm => ({
  rule_name: "",
  description: "",
  trade_method_id: "",
  buyConditions: defaultBuyConditions(),
  sellConditions: defaultSellConditions(),
  positionBasis: "cash",
  positionPercent: 30,
  feeRate: 0.00015,
  slippageRate: 0,
});

function buyConditionLabel(row: BuyConditionRow, fields: BacktestConditionField[]): string {
  const leftLabel = fieldLabel(fields, row.left?.field);
  if (row.condition_type === "field_value_compare") return `${leftLabel} ${row.operator || ">"} ${fmtNumber(row.value)}`;
  if (row.condition_type === "field_vs_field") return `${leftLabel} ${row.operator || ">"} ${fieldLabel(fields, row.right?.field)}`;
  if (row.condition_type === "field_vs_indicator") return `${leftLabel} ${row.operator || ">"} ${row.right?.period || 20}일 ${fieldLabel(fields, row.right?.field)} 이동평균`;
  if (row.condition_type === "field_vs_average_multiplier") return `${leftLabel} ${row.operator || ">"} ${row.right?.period || 20}일 평균 ${fieldLabel(fields, row.right?.field)}의 ${row.right?.multiplier || 1}배`;
  if (row.condition_type === "candle_pattern") {
    const base = patternLabels[row.pattern || "bullish_candle"];
    if (row.pattern === "close_above_recent_high" || row.pattern === "close_below_recent_low") return `${base} (${row.period || 20}일)`;
    return base;
  }
  return "기타 조건";
}

function sellConditionLabel(row: SellConditionRow): string {
  if (row.condition_type === "take_profit_pct") return `매수가 대비 ${row.value ?? 10}% 상승 시 익절`;
  if (row.condition_type === "stop_loss_pct") return `매수가 대비 ${row.value ?? 5}% 하락 시 손절`;
  if (row.condition_type === "close_below_ma") return `종가가 ${row.period ?? 20}일 이동평균 아래로 이탈`;
  if (row.condition_type === "max_holding_days") return `${row.value ?? 20}거래일 보유 후 청산`;
  return "기타 청산조건";
}

function normalizeBuyConditions(rule: BacktestRule | null): BuyConditionRow[] {
  const raw = rule?.buy_conditions_json?.conditions;
  if (!raw?.length) return defaultBuyConditions();
  return raw.map((condition, idx) => {
    const item = condition as Record<string, any>;
    if (item.condition_type) return { ...item, id: String(item.id || makeId("buy")) } as BuyConditionRow;
    if (item.type === "close_above_ma" || item.type === "close_below_ma") {
      return {
        id: `legacy_buy_${idx}`,
        condition_type: "field_vs_indicator",
        left: { type: "field", field: "close_price", label: "종가" },
        operator: item.type === "close_above_ma" ? ">" : "<",
        right: { type: "moving_average", field: "close_price", period: Number(item.period || 20) },
      };
    }
    if (item.type === "volume_above_average") {
      return {
        id: `legacy_buy_${idx}`,
        condition_type: "field_vs_average_multiplier",
        left: { type: "field", field: "volume", label: "거래량" },
        operator: ">",
        right: { type: "average_multiplier", field: "volume", period: Number(item.period || 20), multiplier: Number(item.multiplier || 1.5) },
      };
    }
    if (item.type === "bullish_candle" || item.type === "close_above_previous_high" || item.type === "close_above_recent_high") {
      return { id: `legacy_buy_${idx}`, condition_type: "candle_pattern", pattern: item.type, period: Number(item.period || 20) };
    }
    return { id: `legacy_buy_${idx}`, condition_type: "candle_pattern", pattern: "bullish_candle", label: "기존 조건 형식을 해석하지 못했습니다." };
  });
}

function normalizeSellConditions(rule: BacktestRule | null): SellConditionRow[] {
  const sell = rule?.sell_conditions_json;
  if (!sell) return defaultSellConditions();
  if (sell.conditions?.length) return sell.conditions.map((condition) => ({ ...condition, id: condition.id || makeId("sell") }));
  const rows: SellConditionRow[] = [];
  if (sell.take_profit_pct !== undefined) rows.push({ id: makeId("sell"), condition_type: "take_profit_pct", value: Number(sell.take_profit_pct) });
  if (sell.stop_loss_pct !== undefined) rows.push({ id: makeId("sell"), condition_type: "stop_loss_pct", value: Number(sell.stop_loss_pct) });
  if (sell.exit_on_close_below_ma?.enabled) rows.push({ id: makeId("sell"), condition_type: "close_below_ma", field: "close_price", period: Number(sell.exit_on_close_below_ma.period || 20) });
  if (sell.max_holding_days !== undefined) rows.push({ id: makeId("sell"), condition_type: "max_holding_days", value: Number(sell.max_holding_days) });
  return rows.length ? rows : defaultSellConditions();
}

function buildPayload(form: RuleForm, fields: BacktestConditionField[]): BacktestRuleInput {
  return {
    rule_name: form.rule_name.trim(),
    description: form.description.trim() || null,
    trade_method_id: form.trade_method_id ? Number(form.trade_method_id) : null,
    buy_conditions_json: {
      operator: "AND",
      conditions: form.buyConditions.map((condition) => ({
        ...condition,
        left: condition.left ? { ...condition.left, label: fieldLabel(fields, condition.left.field) } : undefined,
        right: condition.right
          ? {
              ...condition.right,
              label:
                condition.right.type === "moving_average"
                  ? `${condition.right.period || 20}일 ${fieldLabel(fields, condition.right.field)} 이동평균`
                  : condition.right.type === "average_multiplier"
                    ? `${condition.right.period || 20}일 평균 ${fieldLabel(fields, condition.right.field)}의 ${condition.right.multiplier || 1}배`
                    : fieldLabel(fields, condition.right.field),
            }
          : undefined,
        label: buyConditionLabel(condition, fields),
      })),
    },
    sell_conditions_json: {
      operator: "OR",
      conditions: form.sellConditions.map((condition) => ({ ...condition, label: sellConditionLabel(condition) })),
    },
    position_rule_json: { basis: form.positionBasis, percent: Number(form.positionPercent) || 30 },
    fee_rate: Number(form.feeRate) || 0,
    slippage_rate: Number(form.slippageRate) || 0,
  };
}

function formFromRule(rule: BacktestRule | null): RuleForm {
  if (!rule) return defaultRuleForm();
  return {
    rule_name: rule.rule_name || "",
    description: rule.description || "",
    trade_method_id: rule.trade_method_id ? String(rule.trade_method_id) : "",
    buyConditions: normalizeBuyConditions(rule),
    sellConditions: normalizeSellConditions(rule),
    positionBasis: (rule.position_rule_json?.basis as RuleForm["positionBasis"]) || "cash",
    positionPercent: Number(rule.position_rule_json?.percent ?? 30),
    feeRate: Number(rule.fee_rate ?? 0.00015),
    slippageRate: Number(rule.slippage_rate ?? 0),
  };
}

function EquityChart({ points }: { points: BacktestEquityPoint[] }) {
  const width = 760;
  const height = 180;
  const pad = { top: 16, right: 16, bottom: 24, left: 54 };
  const values = points.map((point) => Number(point.total_asset || 0)).filter((value) => value > 0);
  if (values.length < 2) return <div className="backtest-empty-chart">자산곡선 데이터가 부족합니다.</div>;
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = Math.max(1, max - min);
  const xAt = (idx: number) => pad.left + (idx / Math.max(1, points.length - 1)) * (width - pad.left - pad.right);
  const yAt = (value: number) => pad.top + ((max - value) / span) * (height - pad.top - pad.bottom);
  const d = points.map((point, idx) => `${idx === 0 ? "M" : "L"} ${xAt(idx)} ${yAt(Number(point.total_asset || 0))}`).join(" ");
  return (
    <svg className="backtest-equity-chart" viewBox={`0 0 ${width} ${height}`} role="img" aria-label="백테스트 자산곡선">
      <rect x="0" y="0" width={width} height={height} rx="8" fill="#fff" />
      {[0, 0.5, 1].map((rate) => {
        const y = pad.top + (height - pad.top - pad.bottom) * rate;
        const value = max - span * rate;
        return (
          <g key={rate}>
            <line x1={pad.left} x2={width - pad.right} y1={y} y2={y} stroke="#e2e8f0" />
            <text x={8} y={y + 4} fontSize="11" fill="#64748b">{fmtNumber(value)}</text>
          </g>
        );
      })}
      <path d={d} fill="none" stroke="#2563eb" strokeWidth="2" />
    </svg>
  );
}

function BacktestPage() {
  const nameInputRef = useRef<HTMLInputElement | null>(null);
  const [activeTab, setActiveTab] = useState<BacktestTab>("settings");
  const [conditionFields, setConditionFields] = useState<BacktestConditionField[]>(fallbackFields);
  const [rules, setRules] = useState<BacktestRule[]>([]);
  const [runs, setRuns] = useState<BacktestRun[]>([]);
  const [methods, setMethods] = useState<TradeMethod[]>([]);
  const [stocks, setStocks] = useState<BacktestStock[]>([]);
  const [selectedRuleId, setSelectedRuleId] = useState<number | null>(null);
  const [selectedStockCode, setSelectedStockCode] = useState("");
  const [selectedRunId, setSelectedRunId] = useState<number | null>(null);
  const [stockKeyword, setStockKeyword] = useState("");
  const [stockSearchMessage, setStockSearchMessage] = useState("종목을 선택하면 수집된 가격 기간이 자동 입력됩니다.");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [initialCash, setInitialCash] = useState(10_000_000);
  const [form, setForm] = useState<RuleForm>(defaultRuleForm());
  const [editingRuleId, setEditingRuleId] = useState<number | null>(null);
  const [detail, setDetail] = useState<BacktestRunDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [searchingStocks, setSearchingStocks] = useState(false);
  const [running, setRunning] = useState(false);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  const selectedRule = useMemo(() => rules.find((item) => item.id === selectedRuleId) || null, [rules, selectedRuleId]);
  const selectedStock = useMemo(() => stocks.find((item) => item.stock_code === selectedStockCode) || null, [stocks, selectedStockCode]);
  const selectedBuyCount = selectedRule ? normalizeBuyConditions(selectedRule).length : form.buyConditions.length;
  const selectedSellCount = selectedRule ? normalizeSellConditions(selectedRule).length : form.sellConditions.length;
  const selectedPercent = selectedRule ? selectedRule.position_rule_json?.percent ?? 30 : form.positionPercent;

  const loadRules = async () => {
    const result = await repositories.backtest.fetchRules();
    const rows = result.items || [];
    setRules(rows);
    if (!selectedRuleId && rows[0]) {
      setSelectedRuleId(rows[0].id);
      setEditingRuleId(rows[0].id);
      setForm(formFromRule(rows[0]));
    }
  };

  const loadRuns = async () => {
    const result = await repositories.backtest.fetchRuns({ limit: 20 });
    setRuns(result.items || []);
  };

  const loadConditionFields = async () => {
    try {
      const result = await repositories.backtest.fetchConditionFields();
      if (result.items?.length) setConditionFields(result.items);
    } catch {
      setConditionFields(fallbackFields);
      setMessage("조건 필드를 불러오지 못해 기본 필드로 표시합니다.");
    }
  };

  const selectStock = (stock: BacktestStock) => {
    setSelectedStockCode(stock.stock_code);
    setStartDate(defaultStartDateForStock(stock));
    setEndDate(stock.last_price_date || "");
    setStockSearchMessage(`가격 데이터 수집 기간: ${stock.first_price_date || "-"} ~ ${stock.last_price_date || "-"} / ${stock.price_count.toLocaleString("ko-KR")}건`);
  };

  const loadStocks = async (keyword = "", options?: { requireKeyword?: boolean }) => {
    const normalized = keyword.trim();
    if (options?.requireKeyword && !normalized) {
      setStockSearchMessage("검색어를 입력해 주세요.");
      return;
    }
    setSearchingStocks(true);
    setError("");
    try {
      const result = await repositories.backtest.fetchStocks({ keyword: normalized || undefined, limit: 30 });
      const rows = result.items || [];
      setStocks(rows);
      if (rows.length === 0) {
        setSelectedStockCode("");
        setStockSearchMessage("가격 데이터가 있는 종목을 찾지 못했습니다. 먼저 관심종목 Data분석 화면에서 가격 데이터를 수집해 주세요.");
      } else if (rows.length === 1) {
        selectStock(rows[0]);
        setStockSearchMessage(`1건의 종목을 찾았습니다. 가격 데이터 수집 기간: ${rows[0].first_price_date || "-"} ~ ${rows[0].last_price_date || "-"} / ${rows[0].price_count.toLocaleString("ko-KR")}건`);
      } else {
        setStockSearchMessage(`${rows.length}건의 종목을 찾았습니다. 종목을 선택하면 수집된 가격 기간이 자동 입력됩니다.`);
      }
    } catch (e) {
      setStockSearchMessage(e instanceof Error ? e.message : "종목 검색에 실패했습니다.");
    } finally {
      setSearchingStocks(false);
    }
  };

  const loadInitial = async () => {
    setLoading(true);
    setError("");
    try {
      const [methodRows] = await Promise.all([
        repositories.tradeJournals.listTradeMethods({ is_active: 1 }),
        loadConditionFields(),
        loadRules(),
        loadRuns(),
        loadStocks(),
      ]);
      setMethods(methodRows || []);
    } catch (e) {
      setError(e instanceof Error ? e.message : "백테스트 화면 초기화에 실패했습니다.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadInitial();
  }, []);

  const startCreate = () => {
    setSelectedRuleId(null);
    setEditingRuleId(null);
    setForm(defaultRuleForm());
    setMessage("");
    setError("");
    requestAnimationFrame(() => nameInputRef.current?.focus());
  };

  const startEdit = (rule: BacktestRule) => {
    setEditingRuleId(rule.id);
    setSelectedRuleId(rule.id);
    setForm(formFromRule(rule));
    setMessage("");
    setError("");
  };

  const saveRule = async () => {
    setMessage("");
    setError("");
    const payload = buildPayload(form, conditionFields);
    if (!payload.rule_name) return setError("매매기준명을 입력해 주세요.");
    if (!form.buyConditions.length) return setError("매수조건을 1개 이상 추가해 주세요.");
    if (!form.sellConditions.length) return setError("매도조건을 1개 이상 추가해 주세요.");
    setSaving(true);
    try {
      const saved = editingRuleId
        ? await repositories.backtest.updateRule(editingRuleId, payload)
        : await repositories.backtest.createRule(payload);
      setSelectedRuleId(saved.id);
      setEditingRuleId(saved.id);
      setForm(formFromRule(saved));
      await loadRules();
      setMessage("매매기준이 저장되었습니다.");
    } catch (e) {
      setError(e instanceof Error ? e.message : "매매기준 저장에 실패했습니다.");
    } finally {
      setSaving(false);
    }
  };

  const deleteRule = async () => {
    if (!editingRuleId) return;
    const confirmed = window.confirm("이 매매기준을 삭제하시겠습니까? 기존 백테스트 이력 보존을 위해 목록에서만 숨깁니다.");
    if (!confirmed) return;
    setSaving(true);
    setError("");
    try {
      await repositories.backtest.deleteRule(editingRuleId);
      await loadRules();
      setSelectedRuleId(null);
      setEditingRuleId(null);
      setForm(defaultRuleForm());
      setMessage("매매기준이 삭제되었습니다.");
    } catch (e) {
      setError(e instanceof Error ? e.message : "매매기준 삭제에 실패했습니다.");
    } finally {
      setSaving(false);
    }
  };

  const runBacktest = async () => {
    setMessage("");
    setError("");
    if (!selectedRuleId) return setError("매매기준을 선택해 주세요.");
    if (!selectedStockCode) return setError("백테스트할 종목을 선택해 주세요.");
    setRunning(true);
    try {
      const result = await repositories.backtest.run({
        rule_id: selectedRuleId,
        stock_code: selectedStockCode,
        start_date: startDate || null,
        end_date: endDate || null,
        initial_cash: Number(initialCash) || 10_000_000,
      });
      const detailResult = await repositories.backtest.fetchRun(result.run_id);
      setDetail(detailResult);
      setSelectedRunId(result.run_id);
      await loadRuns();
      setMessage("백테스트 실행이 완료되었습니다.");
    } catch (e) {
      setError(e instanceof Error ? e.message : "백테스트 실행에 실패했습니다.");
    } finally {
      setRunning(false);
    }
  };

  const loadRunDetail = async (run: BacktestRun) => {
    setSelectedRunId(run.id);
    setSelectedRuleId(run.rule_id);
    setSelectedStockCode(run.stock_code);
    setStartDate(run.start_date);
    setEndDate(run.end_date);
    setInitialCash(Number(run.initial_cash || 10_000_000));
    setError("");
    try {
      setDetail(await repositories.backtest.fetchRun(run.id));
    } catch (e) {
      setError(e instanceof Error ? e.message : "백테스트 상세 조회에 실패했습니다.");
    }
  };

  const addBuyCondition = () => setForm((prev) => ({ ...prev, buyConditions: [...prev.buyConditions, defaultBuyCondition()] }));
  const addSellCondition = () => setForm((prev) => ({ ...prev, sellConditions: [...prev.sellConditions, defaultSellCondition()] }));
  const removeBuyCondition = (id: string) => setForm((prev) => ({ ...prev, buyConditions: prev.buyConditions.filter((row) => row.id !== id) }));
  const removeSellCondition = (id: string) => setForm((prev) => ({ ...prev, sellConditions: prev.sellConditions.filter((row) => row.id !== id) }));
  const updateBuyCondition = (id: string, patch: Partial<BuyConditionRow>) =>
    setForm((prev) => ({ ...prev, buyConditions: prev.buyConditions.map((row) => (row.id === id ? { ...row, ...patch } : row)) }));
  const updateSellCondition = (id: string, patch: Partial<SellConditionRow>) =>
    setForm((prev) => ({ ...prev, sellConditions: prev.sellConditions.map((row) => (row.id === id ? { ...row, ...patch } : row)) }));

  const changeBuyType = (id: string, type: BuyConditionRow["condition_type"]) => {
    const base = defaultBuyCondition();
    const next: BuyConditionRow =
      type === "field_value_compare"
        ? { id, condition_type: type, left: { type: "field", field: "close_price" }, operator: ">", value: 0 }
        : type === "field_vs_field"
          ? { id, condition_type: type, left: { type: "field", field: "close_price" }, operator: ">", right: { type: "field", field: "open_price" } }
          : type === "field_vs_average_multiplier"
            ? { id, condition_type: type, left: { type: "field", field: "volume" }, operator: ">", right: { type: "average_multiplier", field: "volume", period: 20, multiplier: 1.5 } }
            : type === "candle_pattern"
              ? { id, condition_type: type, pattern: "bullish_candle" }
              : { ...base, id };
    updateBuyCondition(id, next);
  };

  const onStockKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === "Enter") void loadStocks(stockKeyword, { requireKeyword: true });
  };

  const renderBuyRow = (row: BuyConditionRow, index: number) => {
    const fieldOptions = conditionFields.map((field) => <option key={field.field_key} value={field.field_key}>{field.label}</option>);
    return (
      <div className="backtest-condition-row" key={row.id}>
        <span className="backtest-condition-index">{index + 1}</span>
        <select className="backtest-condition-type" value={row.condition_type} onChange={(event) => changeBuyType(row.id, event.target.value as BuyConditionRow["condition_type"])}>
          {Object.entries(buyTypeLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
        </select>
        {row.condition_type === "candle_pattern" ? (
          <>
            <select className="backtest-condition-field" value={row.pattern || "bullish_candle"} onChange={(event) => updateBuyCondition(row.id, { pattern: event.target.value as BuyConditionRow["pattern"] })}>
              {Object.entries(patternLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
            </select>
            {(row.pattern === "close_above_recent_high" || row.pattern === "close_below_recent_low") && (
              <input className="backtest-condition-period" type="number" min={2} value={row.period || 20} onChange={(event) => updateBuyCondition(row.id, { period: Number(event.target.value) || 20 })} />
            )}
          </>
        ) : (
          <>
            <select className="backtest-condition-field" value={row.left?.field || "close_price"} onChange={(event) => updateBuyCondition(row.id, { left: { type: "field", field: event.target.value } })}>
              {fieldOptions}
            </select>
            <select className="backtest-condition-operator" value={row.operator || ">"} onChange={(event) => updateBuyCondition(row.id, { operator: event.target.value as BacktestOperator })}>
              {operatorOptions.map((operator) => <option key={operator} value={operator}>{operator}</option>)}
            </select>
            {row.condition_type === "field_value_compare" && (
              <input className="backtest-condition-value" type="number" value={row.value ?? 0} onChange={(event) => updateBuyCondition(row.id, { value: Number(event.target.value) })} />
            )}
            {row.condition_type === "field_vs_field" && (
              <select className="backtest-condition-field" value={row.right?.field || "open_price"} onChange={(event) => updateBuyCondition(row.id, { right: { type: "field", field: event.target.value } })}>
                {fieldOptions}
              </select>
            )}
            {row.condition_type === "field_vs_indicator" && (
              <>
                <input className="backtest-condition-period" type="number" min={2} value={row.right?.period || 20} onChange={(event) => updateBuyCondition(row.id, { right: { type: "moving_average", field: row.right?.field || "close_price", period: Number(event.target.value) || 20 } })} />
                <select className="backtest-condition-field" value={row.right?.field || "close_price"} onChange={(event) => updateBuyCondition(row.id, { right: { type: "moving_average", field: event.target.value, period: row.right?.period || 20 } })}>
                  {fieldOptions}
                </select>
              </>
            )}
            {row.condition_type === "field_vs_average_multiplier" && (
              <>
                <input className="backtest-condition-period" type="number" min={2} value={row.right?.period || 20} onChange={(event) => updateBuyCondition(row.id, { right: { ...row.right, type: "average_multiplier", period: Number(event.target.value) || 20 } })} />
                <input className="backtest-condition-value" type="number" min={0.1} step={0.1} value={row.right?.multiplier || 1} onChange={(event) => updateBuyCondition(row.id, { right: { ...row.right, type: "average_multiplier", multiplier: Number(event.target.value) || 1 } })} />
              </>
            )}
          </>
        )}
        <span className="backtest-condition-label">{buyConditionLabel(row, conditionFields)}</span>
        <button className="backtest-icon-button" type="button" onClick={() => removeBuyCondition(row.id)} aria-label="매수조건 삭제"><X size={16} /></button>
      </div>
    );
  };

  const renderSellRow = (row: SellConditionRow, index: number) => (
    <div className="backtest-condition-row" key={row.id}>
      <span className="backtest-condition-index">{index + 1}</span>
      <select className="backtest-condition-type" value={row.condition_type} onChange={(event) => updateSellCondition(row.id, { condition_type: event.target.value as SellConditionRow["condition_type"] })}>
        {Object.entries(sellTypeLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
      </select>
      {(row.condition_type === "take_profit_pct" || row.condition_type === "stop_loss_pct" || row.condition_type === "max_holding_days") && (
        <input className="backtest-condition-value" type="number" value={row.value ?? (row.condition_type === "take_profit_pct" ? 10 : row.condition_type === "stop_loss_pct" ? 5 : 20)} onChange={(event) => updateSellCondition(row.id, { value: Number(event.target.value) })} />
      )}
      {row.condition_type === "close_below_ma" && (
        <input className="backtest-condition-period" type="number" min={2} value={row.period || 20} onChange={(event) => updateSellCondition(row.id, { field: "close_price", period: Number(event.target.value) || 20 })} />
      )}
      <span className="backtest-condition-label">{sellConditionLabel(row)}</span>
      <button className="backtest-icon-button" type="button" onClick={() => removeSellCondition(row.id)} aria-label="매도조건 삭제"><X size={16} /></button>
    </div>
  );

  return (
    <div className="page page-backtest">
      <PageHeader title="매매기준 백테스트" description="조건형 매매기준을 만들고 수집된 일봉 데이터로 검증합니다." />

      <div className="backtest-tabs" role="tablist" aria-label="백테스트 탭">
        <button className={`backtest-tab-button ${activeTab === "settings" ? "active" : ""}`} type="button" onClick={() => setActiveTab("settings")}>매매기준 설정</button>
        <button className={`backtest-tab-button ${activeTab === "run" ? "active" : ""}`} type="button" onClick={() => setActiveTab("run")}>백테스트</button>
      </div>

      {message && <div className="backtest-alert success">{message}</div>}
      {error && <div className="backtest-alert error">{error}</div>}

      {activeTab === "settings" && (
        <div className="backtest-tab-panel backtest-settings-layout">
          <SectionCard title="매매기준 목록">
            <button className="primary-button" type="button" onClick={startCreate}><Plus size={16} />새 기준</button>
            <div className="backtest-rule-list">
              {rules.map((rule) => (
                <button key={rule.id} className={`backtest-rule-item ${editingRuleId === rule.id ? "selected" : ""}`} type="button" onClick={() => startEdit(rule)}>
                  <strong>{rule.rule_name}</strong>
                  <span>{normalizeBuyConditions(rule).length}개 매수조건 / {normalizeSellConditions(rule).length}개 매도조건</span>
                  <small>진입비중 {rule.position_rule_json?.percent ?? 30}%</small>
                </button>
              ))}
              {!rules.length && <p className="backtest-empty-text">저장된 매매기준이 없습니다.</p>}
            </div>
          </SectionCard>

          <SectionCard title={editingRuleId ? "매매기준 편집" : "새 매매기준"}>
            <div className="backtest-editor-grid">
              <label>매매기준명<input ref={nameInputRef} value={form.rule_name} onChange={(event) => setForm((prev) => ({ ...prev, rule_name: event.target.value }))} /></label>
              <label>매매일지 방법<select value={form.trade_method_id} onChange={(event) => setForm((prev) => ({ ...prev, trade_method_id: event.target.value }))}><option value="">연결 안 함</option>{methods.map((method) => <option key={method.id} value={method.id}>{method.method_name}</option>)}</select></label>
              <label className="backtest-wide">설명<textarea value={form.description} rows={2} onChange={(event) => setForm((prev) => ({ ...prev, description: event.target.value }))} /></label>
            </div>

            <div className="backtest-rule-builder-card">
              <div className="backtest-builder-head">
                <div><h3>매수조건</h3><p>모든 조건이 만족될 때 매수합니다.</p></div>
                <button className="secondary-button" type="button" onClick={addBuyCondition}><Plus size={16} />조건 추가</button>
              </div>
              <div className="backtest-condition-stack">{form.buyConditions.map(renderBuyRow)}</div>
            </div>

            <div className="backtest-rule-builder-card">
              <div className="backtest-builder-head">
                <div><h3>매도조건</h3><p>조건 중 하나가 만족되면 청산합니다.</p></div>
                <button className="secondary-button" type="button" onClick={addSellCondition}><Plus size={16} />청산조건 추가</button>
              </div>
              <div className="backtest-condition-stack">{form.sellConditions.map(renderSellRow)}</div>
            </div>

            <div className="backtest-position-card">
              <label>진입 기준<select value={form.positionBasis} onChange={(event) => setForm((prev) => ({ ...prev, positionBasis: event.target.value as RuleForm["positionBasis"] }))}><option value="cash">현금 기준</option><option value="total_asset">총자산 기준</option><option value="fixed_amount">고정금액</option><option value="fixed_quantity">고정수량</option></select></label>
              <label>진입비중<input type="number" min={1} max={100} value={form.positionPercent} onChange={(event) => setForm((prev) => ({ ...prev, positionPercent: Number(event.target.value) }))} /></label>
              <label>수수료율<input type="number" step={0.00001} value={form.feeRate} onChange={(event) => setForm((prev) => ({ ...prev, feeRate: Number(event.target.value) }))} /></label>
              <label>슬리피지율<input type="number" step={0.00001} value={form.slippageRate} onChange={(event) => setForm((prev) => ({ ...prev, slippageRate: Number(event.target.value) }))} /></label>
            </div>

            <div className="backtest-editor-actions">
              <button className="primary-button" type="button" onClick={saveRule} disabled={saving}><Save size={16} />{saving ? "저장 중" : "저장"}</button>
              {editingRuleId && <button className="danger-button" type="button" onClick={deleteRule} disabled={saving}><Trash2 size={16} />삭제</button>}
            </div>
          </SectionCard>
        </div>
      )}

      {activeTab === "run" && (
        <div className="backtest-tab-panel backtest-run-layout">
          <SectionCard title="최근 실행 이력">
            <div className="backtest-run-list">
              {runs.map((run) => (
                <button key={run.id} className={`backtest-run-item ${selectedRunId === run.id ? "selected" : ""}`} type="button" onClick={() => void loadRunDetail(run)}>
                  <strong>{run.rule_name || `Rule #${run.rule_id}`}</strong>
                  <span>{run.stock_name || run.stock_code} / {run.start_date} ~ {run.end_date}</span>
                  <small className={profitClass(run.total_profit)}>{fmtPct(run.total_return_rate)} / {fmtWon(run.total_profit)}</small>
                </button>
              ))}
              {!runs.length && <p className="backtest-empty-text">최근 실행 이력이 없습니다.</p>}
            </div>
          </SectionCard>

          <div className="backtest-run-main-panel">
            <SectionCard title="실행 설정">
              <div className="backtest-selected-rule-summary">
                <strong>{selectedRule?.rule_name || "매매기준을 선택해 주세요"}</strong>
                <span>매수 {selectedBuyCount}개 / 매도 {selectedSellCount}개 / 진입비중 {selectedPercent}%</span>
              </div>
              <div className="backtest-run-form">
                <label>매매기준<select value={selectedRuleId ?? ""} onChange={(event) => setSelectedRuleId(event.target.value ? Number(event.target.value) : null)}><option value="">선택</option>{rules.map((rule) => <option key={rule.id} value={rule.id}>{rule.rule_name}</option>)}</select></label>
                <label>종목 검색<div className="backtest-search-row"><input value={stockKeyword} onChange={(event) => setStockKeyword(event.target.value)} onKeyDown={onStockKeyDown} placeholder="종목명 또는 코드" /><button type="button" onClick={() => void loadStocks(stockKeyword, { requireKeyword: true })} disabled={searchingStocks}><Search size={16} /></button></div></label>
                <label>종목<select value={selectedStockCode} onChange={(event) => { const stock = stocks.find((item) => item.stock_code === event.target.value); if (stock) selectStock(stock); else setSelectedStockCode(""); }}><option value="">선택</option>{stocks.map((stock) => <option key={stock.stock_code} value={stock.stock_code}>{stock.stock_name} ({stock.stock_code})</option>)}</select></label>
                <label>시작일<input type="date" value={startDate} onChange={(event) => setStartDate(event.target.value)} /></label>
                <label>종료일<input type="date" value={endDate} onChange={(event) => setEndDate(event.target.value)} /></label>
                <label>초기자금<input type="number" min={1} value={initialCash} onChange={(event) => setInitialCash(Number(event.target.value))} /></label>
              </div>
              <p className="backtest-row-text">{stockSearchMessage}{selectedStock ? ` / 선택: ${selectedStock.stock_name}` : ""}</p>
              <button className="primary-button" type="button" onClick={runBacktest} disabled={running || loading}><Play size={16} />{running ? "실행 중" : "백테스트 실행"}</button>
            </SectionCard>

            <SectionCard title="백테스트 결과">
              {detail ? (
                <>
                  <div className="backtest-kpi-grid">
                    <div><span>최종자산</span><strong>{fmtWon(detail.summary.final_asset)}</strong></div>
                    <div><span>총손익</span><strong className={profitClass(detail.summary.total_profit)}>{fmtWon(detail.summary.total_profit)}</strong></div>
                    <div><span>수익률</span><strong className={profitClass(detail.summary.total_return_rate)}>{fmtPct(detail.summary.total_return_rate)}</strong></div>
                    <div><span>최대낙폭</span><strong>{fmtPct(detail.summary.max_drawdown)}</strong></div>
                    <div><span>거래수</span><strong>{fmtNumber(detail.summary.trade_count)}</strong></div>
                    <div><span>승률</span><strong>{fmtPct(detail.summary.win_rate)}</strong></div>
                  </div>
                  <EquityChart points={detail.equity_curve} />
                  <div className="backtest-table-shell">
                    <table className="backtest-table">
                      <thead><tr><th>매수일</th><th>매도일</th><th>매수가</th><th>매도가</th><th>수량</th><th>손익</th><th>수익률</th><th>사유</th></tr></thead>
                      <tbody>
                        {detail.trades.map((trade) => (
                          <tr key={trade.id}>
                            <td>{trade.buy_date}</td><td>{trade.sell_date || "-"}</td><td>{fmtNumber(trade.buy_price)}</td><td>{fmtNumber(trade.sell_price)}</td><td>{fmtNumber(trade.quantity)}</td>
                            <td className={profitClass(trade.profit)}>{fmtWon(trade.profit)}</td><td className={profitClass(trade.profit_rate)}>{fmtPct(trade.profit_rate)}</td><td>{exitReasonLabel(trade.exit_reason)}</td>
                          </tr>
                        ))}
                        {!detail.trades.length && <tr><td colSpan={8}>거래 내역이 없습니다.</td></tr>}
                      </tbody>
                    </table>
                  </div>
                </>
              ) : (
                <p className="backtest-empty-text">실행 이력을 선택하거나 백테스트를 실행하면 결과가 표시됩니다.</p>
              )}
            </SectionCard>
          </div>
        </div>
      )}
    </div>
  );
}

export default BacktestPage;
