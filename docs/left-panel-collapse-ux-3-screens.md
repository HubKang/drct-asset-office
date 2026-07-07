# Left Panel Collapse UX - 3 Screens

## Purpose

Apply the left list panel collapse/expand UX used by the watchlist Sije/Sucha/Jae screen to these screens:

- Watchlist analysis: `frontend/src/pages/StockPricesPage.tsx`
- News management: `frontend/src/pages/NewsPage.tsx`
- Disclosure management: `frontend/src/pages/DisclosuresPage.tsx`

The plain watchlist operations screen, `frontend/src/pages/WatchlistPage.tsx`, is intentionally not part of this UX.

## Reference Pattern

- Reference screen: `frontend/src/pages/WatchlistSijeSuchaJaePage.tsx`
- Reference CSS: `.sije-layout`, `.sije-layout.collapsed`, `.sije-stock-list-panel`
- Pattern: reduce the left list area to a 56px rail and let the main content area expand.

## Applied Panels

- `StockPricesPage.tsx`: analysis stock list panel
- `NewsPage.tsx`: watchlist target list panel
- `DisclosuresPage.tsx`: watchlist target list panel

## Rail Labels

- Watchlist analysis: `분석종목`
- News management: `관심종목`
- Disclosure management: `관심종목`

## localStorage Keys

- `drct.watchlistAnalysis.leftPanelCollapsed`
- `drct.news.leftPanelCollapsed`
- `drct.disclosures.leftPanelCollapsed`

## Scope Notes

- Backend changed: no
- Database changed: no
- Existing API calls changed: no
- Existing search/filter/selection logic removed: no
- `TradeTrainingPage.tsx` changed: no
- `WatchlistPage.tsx` collapse UX: reverted

## Verification

- Run frontend build.
- Run `git diff --check`.
- Browser-check the three target screens and confirm the existing Sije/Sucha/Jae screen is unaffected.
