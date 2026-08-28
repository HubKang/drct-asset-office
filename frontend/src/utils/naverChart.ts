export type NaverStockCandlePeriod = "day" | "week" | "month";
export type NaverTraderChartType = "foreign" | "institution";
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

const naverChartSessionSidcode = createNaverChartSidcode();

/**
 * 화면 사이를 이동해도 같은 차트 URL을 유지해 브라우저 HTTP 캐시를 재사용합니다.
 * 이미지 파일이나 응답 본문을 애플리케이션/DB에 저장하지 않습니다.
 */
export function getNaverChartSessionSidcode(): number {
  return naverChartSessionSidcode;
}

export function buildNaverStockCandleChartUrl(
  stockCode: string | number | null | undefined,
  period: NaverStockCandlePeriod,
  sidcode: string | number,
): string {
  const normalizedCode = normalizeNaverStockCode(stockCode);
  return `https://ssl.pstatic.net/imgfinance/chart/item/candle/${period}/${normalizedCode}.png?sidcode=${sidcode}`;
}

export function buildNaverStockAnalysisUrl(
  stockCode: string | number | null | undefined,
): string {
  const normalizedCode = normalizeNaverStockCode(stockCode);
  if (!normalizedCode) return "";
  return `https://finance.naver.com/item/coinfo.naver?code=${normalizedCode}`;
}

export function buildNaverTraderChartUrl(
  type: NaverTraderChartType,
  stockCode: string | number | null | undefined,
): string {
  const normalizedCode = normalizeNaverStockCode(stockCode);
  const prefix = type === "foreign" ? "F" : "I";
  return `https://ssl.pstatic.net/imgfinance/chart/trader/month3/${prefix}_${normalizedCode}.png`;
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
