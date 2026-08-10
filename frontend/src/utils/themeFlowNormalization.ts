export type ThemeFlowNormalizationPoint = {
  date: string;
  rawValue: number | null;
};

export type NormalizedThemeFlowPoint = ThemeFlowNormalizationPoint & {
  normalizedValue: number | null;
};

export type ThemeFlowNormalizationResult = {
  points: NormalizedThemeFlowPoint[];
  method: "ROBUST_Z" | "STANDARD_Z" | "CONSTANT" | "INSUFFICIENT";
  median: number | null;
  mad: number | null;
  mean: number | null;
  standardDeviation: number | null;
};

export type AdaptiveYAxisDomain = {
  min: number;
  max: number;
  step: number;
  ticks: number[];
};

const niceStep = (rawStep: number) => {
  if (!Number.isFinite(rawStep) || rawStep <= 0) return 1;
  const magnitude = 10 ** Math.floor(Math.log10(rawStep));
  const normalized = rawStep / magnitude;
  const factor = normalized <= 1.5 ? 1 : normalized <= 2.25 ? 2 : normalized <= 3.5 ? 2.5 : normalized <= 7 ? 5 : 10;
  return factor * magnitude;
};

const cleanNumber = (value: number) => Number(value.toPrecision(12));

export function calculateAdaptiveYAxisDomain({
  values,
  baseline,
  targetTicks = 7,
  paddingRatio = .06,
}: {
  values: Array<number | null>;
  baseline: number;
  targetTicks?: number;
  paddingRatio?: number;
}): AdaptiveYAxisDomain {
  const finite = values.filter((value): value is number => value != null && Number.isFinite(value));
  const safeBaseline = Number.isFinite(baseline) ? baseline : 0;
  let rawMin = Math.min(safeBaseline, ...finite);
  let rawMax = Math.max(safeBaseline, ...finite);
  const isConstant = rawMin === rawMax;
  const intervalTarget = Math.max(2, Math.round(targetTicks) - 1);

  if (isConstant) {
    const halfRange = Math.max(Math.abs(rawMin) * .1, 1);
    rawMin -= halfRange;
    rawMax += halfRange;
  } else {
    const padding = (rawMax - rawMin) * Math.max(0, paddingRatio);
    if (rawMin < safeBaseline) rawMin -= padding;
    if (rawMax > safeBaseline) rawMax += padding;
  }

  const step = niceStep((rawMax - rawMin) / intervalTarget);
  let min = Math.floor(rawMin / step) * step;
  const max = Math.ceil(rawMax / step) * step;
  if (!isConstant && safeBaseline === 100 && finite.length && Math.min(...finite) >= safeBaseline) {
    min = Math.max(0, Math.floor((safeBaseline - step) / step) * step);
  }
  if (safeBaseline === 100) min = Math.max(0, min);

  const safeMin = cleanNumber(min);
  const safeMax = cleanNumber(max === min ? min + step : max);
  const tickCount = Math.min(200, Math.max(2, Math.round((safeMax - safeMin) / step) + 1));
  return {
    min: safeMin,
    max: safeMax,
    step: cleanNumber(step),
    ticks: Array.from({ length: tickCount }, (_, index) => cleanNumber(safeMin + index * step)),
  };
}

export function sortByLatestCumulative<T extends { latest: number | null }>(items: T[]): T[] {
  return items.map((item, originalIndex) => ({ item, originalIndex })).sort((left, right) => {
    if (left.item.latest == null && right.item.latest == null) return left.originalIndex - right.originalIndex;
    if (left.item.latest == null) return 1;
    if (right.item.latest == null) return -1;
    return right.item.latest - left.item.latest || left.originalIndex - right.originalIndex;
  }).map(({ item }) => item);
}

export function getStablePaletteColor(identity: number, palette: string[]): string {
  if (!palette.length) return "transparent";
  const safeIdentity = Number.isFinite(identity) ? Math.trunc(identity) : 0;
  return palette[((safeIdentity % palette.length) + palette.length) % palette.length];
}

export function buildStrengthIndexSeries(values: Array<number | null>): Array<number | null> {
  let index = 100;
  return values.map((value) => {
    if (value == null || !Number.isFinite(value)) return null;
    index *= 1 + value / 100;
    return index;
  });
}

export function buildBreadthIndexSeries(values: Array<number | null>): Array<number | null> {
  let index = 100;
  return values.map((value) => {
    if (value == null || !Number.isFinite(value) || value < 0 || value > 100) return null;
    index *= 1 + (value - 50) / 100;
    return index;
  });
}

export function buildCumulativeSeries(values: Array<number | null>): Array<number | null> {
  let total = 0;
  return values.map((value) => {
    if (value == null || !Number.isFinite(value)) return null;
    total += value;
    return total;
  });
}

const finiteValues = (values: Array<number | null>) => values.filter((value): value is number => value != null && Number.isFinite(value));

export function calculateMedian(values: Array<number | null>): number | null {
  const sorted = finiteValues(values).slice().sort((left, right) => left - right);
  if (!sorted.length) return null;
  const middle = Math.floor(sorted.length / 2);
  return sorted.length % 2 ? sorted[middle] : (sorted[middle - 1] + sorted[middle]) / 2;
}

export function calculateMad(values: Array<number | null>, median = calculateMedian(values)): number | null {
  if (median == null) return null;
  return calculateMedian(finiteValues(values).map((value) => Math.abs(value - median)));
}

export function calculateStandardDeviation(values: Array<number | null>, mean?: number): number | null {
  const valid = finiteValues(values);
  if (!valid.length) return null;
  const center = mean ?? valid.reduce((sum, value) => sum + value, 0) / valid.length;
  return Math.sqrt(valid.reduce((sum, value) => sum + (value - center) ** 2, 0) / valid.length);
}

export function normalizeThemeFlowSeries(points: ThemeFlowNormalizationPoint[]): ThemeFlowNormalizationResult {
  const rawValues = points.map((point) => point.rawValue);
  const valid = finiteValues(rawValues);
  if (valid.length < 2) {
    return {
      points: points.map((point) => ({ ...point, normalizedValue: null })),
      method: "INSUFFICIENT", median: calculateMedian(valid), mad: null, mean: valid[0] ?? null, standardDeviation: null,
    };
  }

  const median = calculateMedian(valid)!;
  const mad = calculateMad(valid, median)!;
  if (mad > 0) {
    return {
      points: points.map((point) => ({
        ...point,
        normalizedValue: point.rawValue == null || !Number.isFinite(point.rawValue) ? null : .6745 * (point.rawValue - median) / mad,
      })),
      method: "ROBUST_Z", median, mad, mean: null, standardDeviation: null,
    };
  }

  const mean = valid.reduce((sum, value) => sum + value, 0) / valid.length;
  const standardDeviation = calculateStandardDeviation(valid, mean)!;
  if (standardDeviation > 0) {
    return {
      points: points.map((point) => ({
        ...point,
        normalizedValue: point.rawValue == null || !Number.isFinite(point.rawValue) ? null : (point.rawValue - mean) / standardDeviation,
      })),
      method: "STANDARD_Z", median, mad, mean, standardDeviation,
    };
  }

  return {
    points: points.map((point) => ({ ...point, normalizedValue: point.rawValue == null || !Number.isFinite(point.rawValue) ? null : 0 })),
    method: "CONSTANT", median, mad, mean, standardDeviation,
  };
}
