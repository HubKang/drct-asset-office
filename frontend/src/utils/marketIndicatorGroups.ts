export type MarketIndicatorGroupCode =
  | "ALL"
  | "STOCK_MARKET"
  | "SECTOR"
  | "GOLD_SPOT"
  | "RATE_FX"
  | "INFLATION_ECONOMY"
  | "US_MARKET"
  | "ENERGY_COMMODITY"
  | "DERIVED";

export type MarketIndicatorGroupItem = {
  item_type?: string | null;
  source?: string | null;
  source_kind?: string | null;
  item_code?: string | null;
  code?: string | null;
  index_code?: string | null;
  indicator_code?: string | null;
  category?: string | null;
  category_group?: string | null;
  country?: string | null;
  market?: string | null;
  provider?: string | null;
};

export const MARKET_INDICATOR_GROUPS: { code: MarketIndicatorGroupCode; label: string }[] = [
  { code: "ALL", label: "전체" },
  { code: "STOCK_MARKET", label: "주식시장" },
  { code: "SECTOR", label: "업종" },
  { code: "GOLD_SPOT", label: "금현물" },
  { code: "RATE_FX", label: "금리/환율" },
  { code: "INFLATION_ECONOMY", label: "물가/경기" },
  { code: "US_MARKET", label: "미국시장" },
  { code: "ENERGY_COMMODITY", label: "에너지/원자재" },
  { code: "DERIVED", label: "파생" },
];

const STOCK_MARKET_CODES = new Set(["KOSPI", "KOSDAQ", "KOSPI200", "KOSDAQ150", "KRX100"]);
const GOLD_SPOT_CODES = new Set(["GOLD_KRX"]);
const FX_CODES = new Set(["USD_KRW", "JPY_KRW", "CNY_KRW", "USD_KRW_VOLATILITY", "US_BROAD_DOLLAR"]);
const RATE_CODES = new Set([
  "BASE_RATE",
  "CALL_RATE",
  "KTB_3Y",
  "KTB_10Y",
  "US_10Y",
  "US_2Y",
  "US_FED_FUNDS",
  "US_REAL_10Y",
  "US_BREAKEVEN_10Y",
]);
const INFLATION_ECONOMY_CODES = new Set([
  "CPI",
  "PPI",
  "CSI",
  "BSI_MANUFACTURING",
  "US_CPI",
  "US_CORE_PCE",
  "US_INITIAL_CLAIMS",
  "US_NFCI",
]);
const US_MARKET_CODES = new Set(["US_NASDAQ", "US_SP500", "US_DOW", "US_SOX", "US_VIX"]);
const ENERGY_COMMODITY_CODES = new Set(["WTI"]);
const DERIVED_CODES = new Set([
  "US_10Y_2Y_SPREAD",
  "KR_10Y_3Y_SPREAD",
  "KR_REAL_POLICY_RATE",
  "US_REAL_POLICY_RATE",
  "USD_KRW_VOLATILITY",
  "NASDAQ_SP500_RELATIVE",
  "SOX_SP500_RELATIVE",
]);

export const getMarketIndicatorGroupCodeByLabel = (label: string): MarketIndicatorGroupCode | null =>
  MARKET_INDICATOR_GROUPS.find((group) => group.label === label)?.code ?? null;

export const getMarketIndicatorGroupLabel = (code: MarketIndicatorGroupCode) =>
  MARKET_INDICATOR_GROUPS.find((group) => group.code === code)?.label ?? code;

const getItemCode = (item: MarketIndicatorGroupItem) =>
  String(item.item_code ?? item.code ?? item.index_code ?? item.indicator_code ?? "").toUpperCase();

const isIndexLike = (item: MarketIndicatorGroupItem) => {
  const source = String(item.source ?? item.item_type ?? "").toUpperCase();
  return source === "MARKET_INDEX" || source === "INDEX";
};

export const getMarketIndicatorGroup = (item: MarketIndicatorGroupItem): MarketIndicatorGroupCode => {
  const code = getItemCode(item);
  const category = String(item.category ?? "").toUpperCase();
  const categoryText = String(item.category ?? "");
  const categoryGroup = String(item.category_group ?? "").toUpperCase();
  const provider = String(item.provider ?? "").toUpperCase();
  const sourceKind = String(item.source_kind ?? "").toUpperCase();

  if (DERIVED_CODES.has(code) || categoryGroup === "DERIVED" || category === "DERIVED" || provider === "DERIVED" || sourceKind === "DERIVED_INDICATOR") return "DERIVED";
  if (GOLD_SPOT_CODES.has(code) || categoryText.includes("금현물")) return "GOLD_SPOT";
  if (STOCK_MARKET_CODES.has(code) || categoryGroup === "DOMESTIC_STOCK_MARKET") return "STOCK_MARKET";
  if (categoryGroup === "DOMESTIC_SECTOR" || categoryText.includes("업종") || (isIndexLike(item) && (code.startsWith("KOSPI_") || code.startsWith("KOSDAQ_")))) return "SECTOR";
  if (FX_CODES.has(code) || RATE_CODES.has(code) || categoryGroup === "DOMESTIC_RATE" || category === "FX" || category === "RATE" || category === "GLOBAL_RATE") return "RATE_FX";
  if (INFLATION_ECONOMY_CODES.has(code) || categoryGroup === "INFLATION_ECONOMY" || ["INFLATION", "ECONOMY", "EMPLOYMENT_CONSUMPTION", "CREDIT_LIQUIDITY"].includes(category)) return "INFLATION_ECONOMY";
  if (US_MARKET_CODES.has(code) || categoryGroup === "US_MARKET") return "US_MARKET";
  if (ENERGY_COMMODITY_CODES.has(code) || categoryGroup === "ENERGY_COMMODITY" || category === "ENERGY" || category === "COMMODITY") return "ENERGY_COMMODITY";
  return "STOCK_MARKET";
};

export const matchesMarketIndicatorGroup = (item: MarketIndicatorGroupItem, groupCode: MarketIndicatorGroupCode) =>
  groupCode === "ALL" || getMarketIndicatorGroup(item) === groupCode;
