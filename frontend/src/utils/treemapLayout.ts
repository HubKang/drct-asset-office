export type TreemapLayoutInput = {
  id: string;
  value: number;
};

export type TreemapLayoutRect = {
  id: string;
  x: number;
  y: number;
  width: number;
  height: number;
  areaRatio: number;
};

type WorkingRect = Omit<TreemapLayoutRect, "id" | "areaRatio">;
type TreemapTextLevel = "none" | "tiny" | "small" | "medium" | "large" | "xlarge";

export type TreemapTextMetrics = {
  textLevel: TreemapTextLevel;
  titleLengthLevel: "short" | "normal" | "long" | "xlong";
  titleFontSize: number;
  titleLineClamp: number;
  showMeta: boolean;
  showSubtitle: boolean;
};

const normalizeTreemapItems = (items: TreemapLayoutInput[]) => {
  const positiveItems = items
    .map((item) => ({ id: item.id, value: Math.max(0, Number(item.value) || 0) }))
    .filter((item) => item.value > 0);
  const maxValue = positiveItems.reduce((max, item) => Math.max(max, item.value), 0);
  const minValue = maxValue > 0 ? maxValue * 0.018 : 1;
  return positiveItems
    .map((item) => ({ ...item, value: Math.max(item.value, minValue) }))
    .sort((a, b) => b.value - a.value || a.id.localeCompare(b.id));
};

const splitItems = (items: ReturnType<typeof normalizeTreemapItems>) => {
  const total = items.reduce((sum, item) => sum + item.value, 0);
  let running = 0;
  let splitIndex = 0;
  while (splitIndex < items.length - 1 && running + items[splitIndex].value <= total / 2) {
    running += items[splitIndex].value;
    splitIndex += 1;
  }
  if (splitIndex === 0) splitIndex = 1;
  return [items.slice(0, splitIndex), items.slice(splitIndex)] as const;
};

const layoutRecursive = (
  items: ReturnType<typeof normalizeTreemapItems>,
  rect: WorkingRect,
  totalValue: number,
  output: TreemapLayoutRect[],
) => {
  if (items.length === 0) return;
  if (items.length === 1) {
    output.push({ id: items[0].id, ...rect, areaRatio: totalValue > 0 ? items[0].value / totalValue : 0 });
    return;
  }

  const [first, second] = splitItems(items);
  const firstValue = first.reduce((sum, item) => sum + item.value, 0);
  const allValue = firstValue + second.reduce((sum, item) => sum + item.value, 0);
  const ratio = allValue > 0 ? firstValue / allValue : 0.5;

  if (rect.width >= rect.height) {
    const firstWidth = rect.width * ratio;
    layoutRecursive(first, { ...rect, width: firstWidth }, totalValue, output);
    layoutRecursive(second, { x: rect.x + firstWidth, y: rect.y, width: rect.width - firstWidth, height: rect.height }, totalValue, output);
  } else {
    const firstHeight = rect.height * ratio;
    layoutRecursive(first, { ...rect, height: firstHeight }, totalValue, output);
    layoutRecursive(second, { x: rect.x, y: rect.y + firstHeight, width: rect.width, height: rect.height - firstHeight }, totalValue, output);
  }
};

export const buildTreemapLayout = (items: TreemapLayoutInput[]): TreemapLayoutRect[] => {
  const normalized = normalizeTreemapItems(items);
  const totalValue = normalized.reduce((sum, item) => sum + item.value, 0);
  const output: TreemapLayoutRect[] = [];
  layoutRecursive(normalized, { x: 0, y: 0, width: 100, height: 100 }, totalValue, output);
  return output;
};

const clampNumber = (value: number, min: number, max: number) => Math.min(max, Math.max(min, value));

type TreemapTextVariant = "dashboard" | "marketTrend";

type TreemapTextMetricOptions = {
  variant?: TreemapTextVariant;
};

export const estimateTreemapTextLength = (text: string) => {
  return Array.from(text.trim()).reduce((sum, char) => {
    if (!char.trim()) return sum + 0.35;
    if (/[\uAC00-\uD7AF]/.test(char)) return sum + 1;
    if (/[A-Z]/.test(char)) return sum + 0.75;
    if (/[a-z0-9]/.test(char)) return sum + 0.65;
    return sum + 0.35;
  }, 0);
};

const getTitleLengthLevel = (title: string) => {
  const length = estimateTreemapTextLength(title);
  if (length <= 3.2) return "short";
  if (length <= 8.5) return "normal";
  if (length <= 13.5) return "long";
  return "xlong";
};

export const getTreemapTileTextLevel = (rect: TreemapLayoutRect | undefined): TreemapTextLevel => {
  if (!rect) return "none";
  const area = rect.width * rect.height;
  if (rect.width < 5.5 || rect.height < 4.2 || area < 42) return "tiny";
  if (rect.width < 10 || rect.height < 8 || area < 120) return "small";
  if (area < 320) return "medium";
  if (area < 700) return "large";
  return "xlarge";
};

const getBaseTitleSize = (level: TreemapTextLevel, area: number, variant: TreemapTextVariant) => {
  if (variant === "dashboard") {
    if (level === "xlarge") return area >= 1100 ? 34 : 30;
    if (level === "large") return area >= 520 ? 26 : 22;
    if (level === "medium") return area >= 220 ? 18 : 16;
    if (level === "small") return 13;
    return 11;
  }
  if (level === "xlarge") return area >= 1100 ? 40 : 34;
  if (level === "large") return area >= 520 ? 30 : 26;
  if (level === "medium") return area >= 220 ? 20 : 18;
  if (level === "small") return 14;
  return 12;
};

const getTitleSizeBounds = (level: TreemapTextLevel, variant: TreemapTextVariant, titleLengthLevel: TreemapTextMetrics["titleLengthLevel"]) => {
  if (variant === "dashboard") {
    if (level === "xlarge") return titleLengthLevel === "short" ? [22, 36] : titleLengthLevel === "normal" ? [20, 34] : [18, 30];
    if (level === "large") return titleLengthLevel === "short" ? [18, 28] : [16, 26];
    if (level === "medium") return [13, 20];
    if (level === "small") return [10, 13];
    return [9, 11];
  }
  if (level === "xlarge") return titleLengthLevel === "xlong" ? [22, 36] : [24, 42];
  if (level === "large") return titleLengthLevel === "xlong" ? [17, 28] : [18, 32];
  if (level === "medium") return [14, 22];
  if (level === "small") return [11, 14];
  return [10, 12];
};

export const getTreemapTextMetrics = (rect: TreemapLayoutRect | undefined, title = "", options: TreemapTextMetricOptions = {}): TreemapTextMetrics => {
  const variant = options.variant ?? "marketTrend";
  const textLevel = getTreemapTileTextLevel(rect);
  const titleLengthLevel = getTitleLengthLevel(title);
  if (!rect || textLevel === "none") {
    return { textLevel, titleLengthLevel, titleFontSize: 0, titleLineClamp: 1, showMeta: false, showSubtitle: false };
  }

  const area = rect.width * rect.height;
  const textLength = Math.max(4, estimateTreemapTextLength(title));
  const baseSize = getBaseTitleSize(textLevel, area, variant);
  const allowTwoLines = textLevel !== "tiny" && textLevel !== "small" && rect.height >= (variant === "dashboard" ? 11 : 8);
  const titleLines = allowTwoLines ? 2 : 1;
  const widthFactor = variant === "dashboard" ? (titleLines === 2 ? 2.05 : 1.35) : (titleLines === 2 ? 2.55 : 1.55);
  const heightFactor = variant === "dashboard" ? (titleLines === 2 ? 2.45 : 4.7) : (titleLines === 2 ? 3.4 : 5.6);
  const widthLimit = (rect.width / textLength) * widthFactor;
  const heightLimit = rect.height * heightFactor;
  const lengthPenalty =
    titleLengthLevel === "xlong" ? (variant === "dashboard" ? 0.62 : 0.72) :
    titleLengthLevel === "long" ? (variant === "dashboard" ? 0.74 : 0.84) :
    titleLengthLevel === "normal" ? (variant === "dashboard" ? 0.92 : 1) :
    (variant === "dashboard" ? 1.04 : 1.1);
  const rawSize = Math.min(baseSize * lengthPenalty, widthLimit, heightLimit);
  const bounds = getTitleSizeBounds(textLevel, variant, titleLengthLevel);

  const titleFontSize = Math.round(clampNumber(rawSize, bounds[0], bounds[1]) * 10) / 10;
  const enoughRoomForMeta = rect.height >= (variant === "dashboard" ? 18 : 12) && rect.width >= (variant === "dashboard" ? 18 : 12);
  const titleConsumesTile = titleFontSize * titleLines >= rect.height * (variant === "dashboard" ? 2.6 : 3.4);
  const showMeta = enoughRoomForMeta && !titleConsumesTile && (textLevel === "large" || textLevel === "xlarge" || (textLevel === "medium" && titleLengthLevel === "short"));
  const showSubtitle = showMeta && (textLevel === "large" || textLevel === "xlarge") && titleLengthLevel !== "xlong";

  return { textLevel, titleLengthLevel, titleFontSize, titleLineClamp: titleLines, showMeta, showSubtitle };
};

export const getTreemapLabelClass = (rect: TreemapLayoutRect | undefined, title = "", options: TreemapTextMetricOptions = {}) => {
  const level = getTreemapTileTextLevel(rect);
  const metrics = getTreemapTextMetrics(rect, title, options);
  const densityClass = metrics.titleLengthLevel === "short" ? "title-short" : metrics.titleLengthLevel === "long" ? "title-long" : metrics.titleLengthLevel === "xlong" ? "title-xlong" : "title-normal";
  const metaClass = metrics.showMeta ? "label-meta" : "label-title-only";
  const subtitleClass = metrics.showSubtitle ? "label-subtitle" : "label-no-subtitle";
  const variantClass = `treemap-variant-${options.variant ?? "marketTrend"}`;
  if (level === "none") return `label-none treemap-tile--none ${densityClass} ${metaClass} ${subtitleClass} ${variantClass}`;
  if (level === "tiny") return `label-title treemap-tile--tiny ${densityClass} ${metaClass} ${subtitleClass} ${variantClass}`;
  if (level === "small") return `label-title treemap-tile--small ${densityClass} ${metaClass} ${subtitleClass} ${variantClass}`;
  if (level === "medium") return `label-compact treemap-tile--medium ${densityClass} ${metaClass} ${subtitleClass} ${variantClass}`;
  if (level === "large") return `label-full treemap-tile--large ${densityClass} ${metaClass} ${subtitleClass} ${variantClass}`;
  return `label-full treemap-tile--xlarge ${densityClass} ${metaClass} ${subtitleClass} ${variantClass}`;
};
