# Market Theme Return Trend Line Chart

## Purpose

Add a line-chart view to the Market Theme Management > Theme Return Trend tab while keeping the existing 30-day heatmap as the default view.

## Heatmap Preservation

- The heatmap remains the default view.
- Existing heatmap markup, color scale, date headers, cell values, API call, and backend calculation are unchanged.
- The new line chart is rendered only when the user selects `선그래프`.

## View Selection UI

- Added a compact segmented control next to the refresh button.
- Options:
  - `히트맵`
  - `선그래프`
- Default state is `히트맵`.

## Data Basis

- The line chart uses the same `trendData.themes` and `trendDates` already used by the heatmap.
- No extra API call is made for the line chart.
- Each line series is built from `theme.daily_returns[].avg_change_rate`.
- The line chart removes dates that have no finite return data across all themes, so weekends and holidays do not create visual x-axis gaps.
- Heatmap dates and cells are not filtered by this rule.

## Axes

- X-axis: trading dates with drawable return data from the same heatmap response.
- Y-axis: daily theme return rate in percent.
- Y-axis defaults to `-30%` through `+30%`.
- If visible data exceeds the default bounds, the axis expands outward to the nearest 10% step.
- Y-axis ticks are shown every 10%, and the 0% reference line is emphasized.
- Line-chart axis labels use chart-only classes and a smaller muted 9px font so labels do not compete with the plotted lines.
- X-axis labels are limited to roughly 5-7 evenly spaced trading dates, including the first and last date when possible.

## Missing Data

- Missing heatmap cells are treated as `null` in the line chart.
- Null values are skipped.
- Null gaps split the SVG path so the line does not connect across missing dates.
- If no trading-date data exists, the chart shows an empty state message.

## Legend And Hover

- The legend is displayed in a compact 260px column on desktop and below the chart on narrow screens.
- The legend column uses the same height as the SVG chart, while the scrollable legend list is inset by the same top and bottom values as the SVG plot margin.
- This aligns the legend scroll area to the plot area, from the top grid line to the bottom grid line, without letting it overlap the chart title or description.
- Legend items show theme name, 30-day cumulative return, and latest daily return.
- Legend items are compact, single-line entries with reduced padding and muted metadata.
- Hovering a line highlights the matching legend item and mutes other lines.
- Hovering a legend item highlights the matching line and mutes other lines.
- Default line stroke and opacity are reduced, while the hovered line uses a stronger stroke and full opacity.
- The heatmap color-scale legend is shown only in heatmap mode.

## Scope

- Backend changed: no
- Database changed: no
- API changed: no
- Theme return refresh/query logic changed: no
- `TradeTrainingPage.tsx` changed: no

## Remaining Notes

- The chart uses a local SVG implementation and does not add a chart package.
- Tooltip-by-date is not included in this iteration.
