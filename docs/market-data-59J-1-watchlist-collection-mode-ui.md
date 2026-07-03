# 59-J-1 Watchlist Collection Mode UI

## Purpose

59-I-1 through 59-I-4 added incremental collection and batch persistence for stock, tracking, and market index data. The watchlist screen still exposed a single price/market metrics refresh button, so users could not explicitly choose normal incremental refresh versus full refresh.

This step clarifies the watchlist collection mode UI without changing backend collection logic.

## UI Changes

The previous single price refresh action is split into two actions:

- `최근7일수집`: default operational refresh
- `전체수집`: secondary full refresh action

The UI also shows a short help text explaining that recent collection uses a 7 calendar-day overlap from the latest collected date, while full refresh re-requests the whole configured period and upserts without deleting existing rows.

## API Payloads

`최근7일수집` calls `stock-prices/collect/selected` with:

```json
{
  "force_full_refresh": false,
  "overlap_days": 7
}
```

`전체수집` calls the same endpoint after confirmation with:

```json
{
  "force_full_refresh": true,
  "overlap_days": 7
}
```

Both modes keep the existing market metrics refresh call after the price collection call.

## Full Refresh Confirmation

Clicking `전체수집` opens a confirmation modal. Canceling closes the modal without calling the API. Confirming runs the full refresh request.

The modal explains:

- the full period is requested again and upserted
- existing data is not deleted
- the operation can take longer
- normal refresh should use `최근7일수집`

## Completion Message

The completion message now includes the selected mode, the request range when available, and saved row count. Partial failures in price or market metrics collection are still surfaced.

## Scope Exclusions

This change does not modify:

- backend collection logic
- stock-tracking screen
- market-indexes screen
- market-themes screen
- `TradeTrainingPage.tsx`
- existing DB rows