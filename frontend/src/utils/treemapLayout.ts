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

export const getTreemapLabelClass = (rect: TreemapLayoutRect | undefined) => {
  if (!rect) return "label-none";
  const area = rect.width * rect.height;
  if (rect.width < 5.5 || rect.height < 5.5 || area < 55) return "label-none";
  if (rect.width < 10 || rect.height < 9 || area < 130) return "label-title";
  if (rect.width < 18 || rect.height < 13 || area < 260) return "label-compact";
  return "label-full";
};
