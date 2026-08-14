export const THEME_RETURN_HEATMAP_COLORS = [
  "#2563EB", "#60A5FA", "#93C5FD", "#DBEAFE", "#E5E7EB",
  "#FEE2E2", "#FCA5A5", "#F87171", "#DC2626",
] as const;

const NEAR_ZERO_NEGATIVE_COLOR = "#EFF6FF";
const NEAR_ZERO_POSITIVE_COLOR = "#FFF1F2";

export const getThemeReturnHeatmapColor = (rate: number | null | undefined): string => {
  if (rate == null || Number.isNaN(Number(rate))) return "#F8FAFC";
  const value = Number(rate);
  if (value <= -20) return THEME_RETURN_HEATMAP_COLORS[0];
  if (value <= -15) return THEME_RETURN_HEATMAP_COLORS[1];
  if (value <= -10) return THEME_RETURN_HEATMAP_COLORS[2];
  if (value <= -5) return THEME_RETURN_HEATMAP_COLORS[3];
  if (value < 0) return NEAR_ZERO_NEGATIVE_COLOR;
  if (value === 0) return THEME_RETURN_HEATMAP_COLORS[4];
  if (value < 5) return NEAR_ZERO_POSITIVE_COLOR;
  if (value < 10) return THEME_RETURN_HEATMAP_COLORS[5];
  if (value < 15) return THEME_RETURN_HEATMAP_COLORS[6];
  if (value < 20) return THEME_RETURN_HEATMAP_COLORS[7];
  return THEME_RETURN_HEATMAP_COLORS[8];
};

export const getThemeReturnTextColor = (rate: number | null | undefined): string => {
  if (rate == null) return "#64748B";
  const value = Number(rate);
  if (value <= -10 || value >= 15) return "#FFFFFF";
  if (value < 0) return "#1D4ED8";
  if (value > 0) return "#B91C1C";
  return "#334155";
};
