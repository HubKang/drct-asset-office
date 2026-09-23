const KST_OFFSET_MS = 9 * 60 * 60 * 1000;

function twoDigits(value: number): string {
  return String(value).padStart(2, "0");
}

export function formatDaumChartTimestamp(now: Date = new Date()): string {
  const kst = new Date(now.getTime() + KST_OFFSET_MS);
  return [
    kst.getUTCFullYear(),
    twoDigits(kst.getUTCMonth() + 1),
    twoDigits(kst.getUTCDate()),
    twoDigits(kst.getUTCHours()),
    twoDigits(kst.getUTCMinutes()),
  ].join("");
}

export function buildDaumIntradayChartUrl(stockCode: string, timestamp: string): string {
  const code = stockCode.trim();
  if (!/^\d{6}$/.test(code)) return "";
  return `https://t1.daumcdn.net/media/finance/chart/kr/daumstock/d/A${code}.png?t=${timestamp}`;
}
