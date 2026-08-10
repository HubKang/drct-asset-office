import assert from "node:assert/strict";
import test from "node:test";
import {
  buildBreadthIndexSeries, buildCumulativeSeries, buildStrengthIndexSeries,
  calculateAdaptiveYAxisDomain, calculateMad, calculateMedian, getStablePaletteColor, normalizeThemeFlowSeries, sortByLatestCumulative,
} from "../src/utils/themeFlowNormalization.ts";

const points = (values: Array<number | null>) => values.map((rawValue, index) => ({ date: `2026-08-${String(index + 1).padStart(2, "0")}`, rawValue }));

test("median supports odd and even value counts without mutating input", () => {
  const source = [4, 1, 3, 2];
  assert.equal(calculateMedian(source), 2.5);
  assert.deepEqual(source, [4, 1, 3, 2]);
  assert.equal(calculateMedian([3, 1, 2]), 2);
});

test("MAD and robust z-score are calculated per time series", () => {
  const values = [-100, -50, 0, 50, 100];
  assert.equal(calculateMad(values), 50);
  const result = normalizeThemeFlowSeries(points(values));
  assert.equal(result.method, "ROBUST_Z");
  assert.ok(Math.abs(result.points[4].normalizedValue! - 1.349) < 1e-12);
});

test("MAD zero falls back to the population standard deviation", () => {
  const result = normalizeThemeFlowSeries(points([100, 100, 100, 120, 150]));
  assert.equal(result.method, "STANDARD_Z");
  assert.ok(result.standardDeviation! > 0);
  assert.ok(result.points[4].normalizedValue! > result.points[3].normalizedValue!);
});

test("constant values become zero after both MAD and standard deviation are zero", () => {
  const result = normalizeThemeFlowSeries(points([10, 10, 10]));
  assert.equal(result.method, "CONSTANT");
  assert.deepEqual(result.points.map((point) => point.normalizedValue), [0, 0, 0]);
});

test("null is excluded from statistics and remains null", () => {
  const result = normalizeThemeFlowSeries(points([-100, null, 0, 50, 100]));
  assert.equal(result.points[1].normalizedValue, null);
  assert.equal(result.points[0].rawValue, -100);
});

test("all-null and single-value series are insufficient instead of producing a score", () => {
  for (const values of [[null, null], [null, 100, null]] as Array<Array<number | null>>) {
    const result = normalizeThemeFlowSeries(points(values));
    assert.equal(result.method, "INSUFFICIENT");
    assert.ok(result.points.every((point) => point.normalizedValue == null));
  }
});

test("strength uses a 100-based compound index", () => {
  const source = [10, 10, -5, 8];
  const result = buildStrengthIndexSeries(source);
  assert.deepEqual(result.map((value) => Number(value!.toFixed(3))), [110, 121, 114.95, 124.146]);
  assert.deepEqual(source, [10, 10, -5, 8]);
});

test("strength null breaks the path but preserves the previous index", () => {
  assert.deepEqual(buildStrengthIndexSeries([10, null, 5]).map((value) => value == null ? null : Number(value.toFixed(2))), [110, null, 115.5]);
});

test("breadth compounds contribution relative to neutral 50 percent", () => {
  const result = buildBreadthIndexSeries([60, 60, 40, 70]);
  assert.deepEqual(result.map((value) => Number(value!.toFixed(2))), [110, 121, 108.9, 130.68]);
  assert.deepEqual(buildBreadthIndexSeries([50, 50]), [100, 100]);
});

test("breadth null and invalid values break the path while preserving state", () => {
  assert.deepEqual(buildBreadthIndexSeries([60, null, 70]).map((value) => value == null ? null : Number(value.toFixed(2))), [110, null, 132]);
  assert.deepEqual(buildBreadthIndexSeries([60, 120, 60]).map((value) => value == null ? null : Number(value.toFixed(2))), [110, null, 121]);
});

test("amount and daily normalized scores use a simple cumulative sum", () => {
  assert.deepEqual(buildCumulativeSeries([300, -100, 500, 200]), [300, 200, 700, 900]);
  assert.deepEqual(buildCumulativeSeries([1.2, null, -0.2]), [1.2, null, 1]);
});

test("adaptive axis keeps large index maxima close to the data", () => {
  const domain = calculateAdaptiveYAxisDomain({ values: [100, 4560], baseline: 100 });
  assert.equal(domain.max, 5000);
  assert.ok(domain.ticks.includes(1000));
});

test("adaptive axis avoids a coarse 1000 maximum for a 642 peak", () => {
  const domain = calculateAdaptiveYAxisDomain({ values: [2, 100, 642], baseline: 100 });
  assert.equal(domain.min, 0);
  assert.equal(domain.max, 700);
  assert.equal(domain.step, 100);
});

test("adaptive axis stays dense for a small range and includes its baseline", () => {
  const domain = calculateAdaptiveYAxisDomain({ values: [98, 99, 100, 101, 102], baseline: 100 });
  assert.deepEqual({ min: domain.min, max: domain.max, step: domain.step }, { min: 97, max: 103, step: 1 });
  assert.ok(domain.min <= 100 && domain.max >= 100);
});

test("adaptive amount axis includes zero and both signed extrema", () => {
  const domain = calculateAdaptiveYAxisDomain({ values: [-500, 200, 1500], baseline: 0 });
  assert.ok(domain.min <= -500);
  assert.ok(domain.max >= 1500);
  assert.ok(domain.ticks.includes(0));
});

test("adaptive axis handles constant, null and non-finite inputs", () => {
  const domain = calculateAdaptiveYAxisDomain({ values: [100, null, Number.NaN, Number.POSITIVE_INFINITY], baseline: 100 });
  assert.deepEqual({ min: domain.min, max: domain.max }, { min: 90, max: 110 });
});

test("legend sorts latest cumulative values descending, stably, with null last", () => {
  const source = [
    { id: "A", latest: 300 }, { id: "B", latest: 500 }, { id: "C", latest: 300 }, { id: "D", latest: null },
  ];
  assert.deepEqual(sortByLatestCumulative(source).map((item) => item.id), ["B", "A", "C", "D"]);
  assert.deepEqual(source.map((item) => item.id), ["A", "B", "C", "D"]);
});

test("theme identity keeps the same color when display order changes", () => {
  const palette = ["blue", "green", "red"];
  const firstOrder = [12, 5, 9].map((id) => [id, getStablePaletteColor(id, palette)]);
  const secondOrder = [9, 12, 5].map((id) => [id, getStablePaletteColor(id, palette)]);
  assert.deepEqual(Object.fromEntries(firstOrder), Object.fromEntries(secondOrder));
});
