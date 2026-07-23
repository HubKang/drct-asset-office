import type { MarketThemeStock } from "../types/marketTheme";

export type SupplyCountSort = "default" | "desc" | "asc";

export function compareThemeStocksBySupplyCount(
  a: MarketThemeStock,
  b: MarketThemeStock,
  direction: Exclude<SupplyCountSort, "default">,
): number {
  const multiplier = direction === "desc" ? -1 : 1;
  const recentDifference = a.recent_30d_supply_day_count - b.recent_30d_supply_day_count;
  if (recentDifference !== 0) return recentDifference * multiplier;

  const totalDifference = a.supply_day_count - b.supply_day_count;
  if (totalDifference !== 0) return totalDifference * multiplier;

  const dateDifference = (a.last_supply_date ?? "").localeCompare(b.last_supply_date ?? "");
  if (dateDifference !== 0) return dateDifference * multiplier;

  return a.stock_name.localeCompare(b.stock_name, "ko-KR");
}