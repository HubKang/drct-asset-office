# 59-E ?몃━留?????고듃 ?ш린 諛??띿뒪???섎┝ 媛쒖꽑

## 蹂寃??뚯씪
- frontend/src/utils/treemapLayout.ts
- frontend/src/index.css

## 媛쒖꽑 ?댁슜
- ?몃━留?rect??width/height/area 湲곗??쇰줈 tiny/small/medium/large/xlarge ?띿뒪???덈꺼??怨꾩궛?쒕떎.
- 湲곗〈 label class? ?④퍡 treemap-tile--* class瑜?諛섑솚???쒖옣 ?섍툒 遺꾩꽍怨???쒕낫???몃━留듭씠 媛숈? ?띿뒪??洹쒖튃??怨듭쑀?쒕떎.
- ????쇱? ?쒕ぉ?????ш쾶 ?쒖떆?섍퀬, 以묎컙 ??쇱? ?쒕ぉ怨??듭떖 ?섏튂瑜??덉젙?곸쑝濡??쒖떆?쒕떎.
- ?묒? ??쇱? ?쒕ぉ ?꾩＜濡??쒖떆?섍퀬 蹂댁“?뺣낫瑜??④릿??
- ?쒓? ??쇰챸? word-break: keep-all, overflow-wrap: break-word, line-height 蹂댁젙?쇰줈 湲???⑥쐞 源⑥쭚??以꾩씤??

## ?ш린蹂?湲곗?
- tiny: ?쒕ぉ 12px, 蹂댁“?뺣낫 ?④?, 1以?- small: ?쒕ぉ 13~15px, 蹂댁“?뺣낫 ?④?, 理쒕? 2以?- medium: ?쒕ぉ 18~23px, ?먯닔/?깅씫瑜??쒖떆, ?섏쐞 ?뚮쭏 ?④?
- large: ?쒕ぉ 26~34px, 蹂댁“?뺣낫 ?쒖떆
- xlarge: ?쒕ぉ 34~46px, 蹂댁“?뺣낫 ?쒖떆

## ?곹뼢 踰붿쐞
- ?몃━留??곗씠???곗떇, ?됱긽, 硫댁쟻 怨꾩궛, hover/detail ?숈옉? 蹂寃쏀븯吏 ?딆븯??
## 59-E-1 title auto scaling adjustment

### Changed files
- frontend/src/utils/treemapLayout.ts
- frontend/src/pages/DashboardPage.tsx
- frontend/src/pages/MarketTrendsPage.tsx
- frontend/src/index.css

### Text metric logic
- Added estimateTreemapTextLength() with weighted length scoring: Hangul 1.0, uppercase 0.75, lowercase/number 0.65, space/symbol 0.35.
- Added getTreemapTextMetrics(rect, title) so title font size is calculated from tile width, height, area, title length, and line count.
- getTreemapLabelClass(rect, title) now adds title density classes and meta/subtitle visibility classes without changing treemap area, color, score, or data logic.

### Font-size bounds
- tiny: 10-12px, title only, 1 line.
- small: 11-14px, title only, 1 line.
- medium: 14-22px, up to 2 lines, meta shown only when the tile has enough height and the title is not extra long.
- large: 18-32px, up to 2 lines, meta can be shown.
- xlarge: 24-42px, up to 2 lines, meta can be shown.

### Rendering rules
- Dashboard and market-trends treemaps pass --tile-title-size and --tile-title-lines per tile.
- Long titles such as MLCC, AI/HBM, ESS, PCB, and CMO variants shrink automatically before clamping.
- Small tiles prioritize centered title text and hide subtitle/meta.
- Existing hover/detail behavior, tile area calculation, color scale, score/return calculation, and data fetching were not changed.
## 59-E-2 dashboard title scale recalibration

### Changed files
- frontend/src/utils/treemapLayout.ts
- frontend/src/pages/DashboardPage.tsx
- frontend/src/pages/MarketTrendsPage.tsx
- frontend/src/index.css
- docs/market-indicators-59E-treemap-tile-text.md

### Actual application check
- Dashboard tiles already received --tile-title-size and --tile-title-lines on the tile root.
- Existing selectors such as .theme-treemap-tile.treemap-tile--xlarge .theme-treemap-title and .theme-treemap-tile.large .theme-treemap-title had stronger specificity than the 59-E-1 generic variable selector.
- 59-E-2 adds equal-or-higher specificity selectors plus !important only for font-size and line-clamp so the calculated title size is the final applied value.

### Recalibrated font-size logic
- Added a variant option to getTreemapTextMetrics(): dashboard and marketTrend.
- Dashboard variant uses conservative caps: tiny 9-11px, small 10-13px, medium 13-20px, large up to 26-28px, xlarge usually 18-34px and short-title max 36px.
- MarketTrend variant keeps more generous bounds so the market-flow treemap remains visually rich.
- Long and extra-long dashboard titles now apply stronger penalties before width/height clamping.

### Line clamp and meta logic
- Dashboard tiles use 1 line for tiny/small or short-height tiles, and 2 lines only when tile height allows it.
- Meta/subtitle visibility is stricter on dashboard tiles: title readability wins over value text.
- Small dashboard tiles center the title and hide subtitle/meta.

### Existing logic impact
- Treemap layout, area, color, score, return, hover, detail, and data-fetch logic were not changed.
- TradeTrainingPage.tsx was not changed.

