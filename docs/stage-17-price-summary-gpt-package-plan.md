# Stage 17 Price Summary GPT Package Plan

## Purpose
- Reuse the stock price summary API as factual grounding data for the GPT advisory package
- Keep the payload focused on observable market facts rather than investment conclusions
- Make later joins with news, disclosures, themes, and liquidity signals easier

## Primary Source
- API: `GET /stock-prices/{stock_id}/summary`
- Default source rule: `source='pykrx'`
- Role in GPT package:
  - one stock summary block
  - factual support data only
  - reusable across advisory prompts and report templates

## Fields To Include
- `stock_id`
- `stock_code`
- `stock_name`
- `latest_trade_date`
- `latest_close_price`
- `latest_ma5`
- `latest_ma20`
- `latest_ma60`
- `recent_5d_change_rate`
- `avg_volume_20d`
- `high_52w`
- `high_52w_date`
- `price_position_vs_52w_high`
- `price_count`
- `min_trade_date`
- `max_trade_date`
- `source`

## Fields To Exclude
- any `trading_value` field
- any generated buy or sell recommendation text
- any direct investment conclusion

## Recommended GPT Expression Style
- Use factual sentences
- Avoid imperative or persuasive language
- Explicitly state when data is missing or insufficient

## Example Factual Expressions
- `The latest trade date is 2026-05-12 and the latest close is 5,860 KRW.`
- `The latest MA5, MA20, and MA60 are 5,874, 5,973, and 6,044.83.`
- `The recent 5-trading-day change rate is -2.33%.`
- `The 52-week high is 7,140 on 2025-07-11, and the current price is 82.07% of that level.`
- `Price history is available from 2024-05-13 to 2026-05-12 with 485 rows.`
- `If a field is missing, state that the current price summary does not have enough source data for that metric.`

## Delivery Shape For GPT Package
- Suggested object key: `price_summary`
- Suggested example:

```json
{
  "price_summary": {
    "stock_id": 10010,
    "stock_code": "A000020",
    "stock_name": "동화약품",
    "latest_trade_date": "2026-05-12",
    "latest_close_price": 5860.0,
    "latest_ma5": 5874.0,
    "latest_ma20": 5973.0,
    "latest_ma60": 6044.8333,
    "recent_5d_change_rate": -2.3333,
    "avg_volume_20d": 82976.25,
    "high_52w": 7140.0,
    "high_52w_date": "2025-07-11",
    "price_position_vs_52w_high": 82.0728,
    "price_count": 485,
    "min_trade_date": "2024-05-13",
    "max_trade_date": "2026-05-12",
    "source": "pykrx"
  }
}
```

## Future Combination Structure
- `price_summary`
  - compact factual market summary
- `news_summary`
  - recent company and sector news facts
- `disclosure_summary`
  - filing facts and key events
- `theme_summary`
  - sector, industry, and theme tags
- `liquidity_summary`
  - later extension if `trading_value` or alternate liquidity data becomes reliable

## Data Sufficiency Notes
- `trading_value` is excluded because the current PyKRX adjusted path does not provide stable source values
- Long-horizon moving averages beyond MA60 can be added later if the advisory package needs them
- If a stock has too few rows, the GPT package should say which metrics are unavailable instead of guessing

## Implementation Recommendation
1. Reuse the summary API response directly instead of recreating SQL inside prompt assembly.
2. Keep the GPT package builder responsible only for formatting and combination, not recalculation.
3. Add source metadata so future multi-source comparison remains possible without schema churn.
