export type NaverStockCandlePeriod = "day" | "week" | "month";
export type NaverKoreaMarketCode = "KOSPI" | "KOSDAQ";
export type NaverWorldIndexCode = "DJI@DJI" | "NAS@IXIC" | "SPI@SPX";
export type NaverWorldIndexPeriod = "month3";
export type NaverMarketIndexCode = "CMDT_GC" | "FX_USDKRW" | "FX_USDX" | "OIL_CL";
export type NaverMarketIndexPeriod = "month3";

export function normalizeNaverStockCode(stockCode: string | number | null | undefined): string {
  const raw = String(stockCode ?? "").trim();
  const digits = raw.replace(/\D/g, "");
  if (!digits) return "";
  if (/^KR/i.test(raw) && digits.length >= 10 && digits.startsWith("7")) {
    return digits.slice(1, 7);
  }
  return digits.slice(-6).padStart(6, "0");
}

export function createNaverChartSidcode(): number {
  return Date.now();
}

export function buildNaverStockCandleChartUrl(
  stockCode: string | number | null | undefined,
  period: NaverStockCandlePeriod,
  sidcode: string | number,
): string {
  const normalizedCode = normalizeNaverStockCode(stockCode);
  return `https://ssl.pstatic.net/imgfinance/chart/item/candle/${period}/${normalizedCode}.png?sidcode=${sidcode}`;
}

export function buildNaverKoreaMarketChartUrl(market: NaverKoreaMarketCode, sidcode: string | number): string {
  return `https://ssl.pstatic.net/imgstock/chart3/day90/${market}.png?sidcode=${sidcode}`;
}

export function buildNaverWorldIndexChartUrl(
  code: NaverWorldIndexCode,
  period: NaverWorldIndexPeriod = "month3",
  sidcode?: string | number,
): string {
  const suffix = sidcode ? `?${sidcode}` : "";
  return `https://ssl.pstatic.net/imgfinance/chart/world/${period}/${code}.png${suffix}`;
}

export function buildNaverMarketIndexAreaChartUrl(
  code: NaverMarketIndexCode,
  period: NaverMarketIndexPeriod = "month3",
  sidcode?: string | number,
): string {
  const suffix = sidcode ? `?sidcode=${sidcode}` : "";
  return `https://ssl.pstatic.net/imgfinance/chart/marketindex/area/${period}/${code}.png${suffix}`;
}
