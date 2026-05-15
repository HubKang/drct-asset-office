# Stage 18 Market Metrics Source Review

## Purpose
- Review candidate data sources for trading value, market capitalization, listed shares, market segmentation, and market ranking
- Prepare a future data path for leader-stock screening and theme liquidity impact analysis
- Keep this stage at probe-and-design level only, without production collector or DB changes

## Background: Why trading_value Is Currently Excluded
- Current daily price collection uses the PyKRX adjusted OHLCV path
- That path does not provide stable `trading_value` in the current operating flow
- As a result:
  - `GET /stock-prices/{stock_id}/summary` excludes trading-value-based fields
  - `StockPricesPage` excludes trading value from the operating summary view
- A separate market-metrics source is needed for liquidity and ranking data

## Environment Check
- DB health: `integrity_check=('ok',)`
- `requirements.txt` currently includes `pykrx` only among the reviewed candidates
- Installed versions in the local `.venv`:
  - `pykrx=1.2.8`
  - `FinanceDataReader=NOT_INSTALLED`
  - `marcap=NOT_INSTALLED`

## Probe Scope
- Target date: `20260512`
- DB latest trade date: `2026-05-12`
- Target stocks:
  - `000020` / `A000020` / `stock_id=10010`
  - `454910` / `A454910` / `stock_id=10803`

## PyKRX market_cap Validation

### Functions Found
- `get_market_cap`
- `get_market_cap_by_date`
- `get_market_cap_by_ticker`

### Intended Columns From Package Source
The local `pykrx` package source documents the following intended outputs.

- `get_market_cap_by_date(fromdate, todate, ticker)`
  - intended fields:
    - `시가총액`
    - `거래량`
    - `거래대금`
    - `상장주식수`
- `get_market_cap_by_ticker(date)`
  - intended fields:
    - `종가`
    - `시가총액`
    - `거래량`
    - `거래대금`
    - `상장주식수`
  - intended use:
    - full-market daily snapshot
    - direct ticker filtering after one market-wide fetch

### Local Probe Result
- The probe discovered the functions successfully.
- Actual data retrieval failed in this environment.
- Observed runtime symptoms:
  - `KRX 로그인 실패: KRX_ID 또는 KRX_PW 환경 변수가 설정되지 않았습니다.`
  - `Expecting value: line 1 column 1 (char 0)`
  - `get_market_cap` and `get_market_cap_by_date` returned empty DataFrames
  - `get_market_cap_by_ticker` raised a `KeyError` because expected columns were missing after the failed upstream response

### Interpretation
- PyKRX clearly has an intended path for:
  - trading value
  - market cap
  - trading volume
  - listed shares
  - full-market daily snapshots
- However, the current local environment is not reliable enough to treat the path as production-ready without more validation.
- The failure shape suggests:
  - KRX response dependency
  - possible authentication / anti-bot / format instability
  - lower operational stability than the current adjusted OHLCV path

### Suitability Judgment
- Good on paper for market-metrics completeness
- Risky as the sole production source for a stable daily market-metrics collector unless the KRX access path is first stabilized

## marcap Validation

### Local Installation Status
- Not installed locally

### Local Probe Status
- No runtime probe was performed because the package is not installed

### Package/Repository Evidence
Official repository documentation describes `marcap` as a daily Korean market-cap dataset covering 1995-05-02 to current data, updated daily. The documented columns include:

- `Rank`
- `Code`
- `Name`
- `Open`
- `High`
- `Low`
- `Close`
- `Volume`
- `Amount`  (trading value)
- `Marcap`  (market capitalization)
- `Stocks`  (listed shares)
- `MarketId`
- `Market`
- `Dept`

### Practical Characteristics
- Strong fit for:
  - market-wide ranking
  - trading-value ranking
  - listed-shares and market-cap enrichment
  - market segmentation
- Data shape already looks close to a `stock_daily_market_metrics` table
- A likely usage model is batch-style full-market daily ingestion with later filtering for watchlist stocks

### Installation Proposal Only
- Candidate approach:
  - `pip install git+https://github.com/FinanceData/marcap.git`
  - or vendor/clone-based usage as documented by the upstream repository

### Suitability Judgment
- Best structural fit for daily market-metrics and ranking use cases
- Strong candidate for a dedicated `market_metrics` collector if the team accepts an extra dependency or repo-based dataset workflow

## FinanceDataReader Validation

### Local Installation Status
- Not installed locally

### Local Probe Status
- No runtime probe was performed because the package is not installed

### Package/Documentation Evidence
Official documentation shows:

- `fdr.DataReader('005930', ...)`
  - standard domestic price columns:
    - `Open`
    - `High`
    - `Low`
    - `Close`
    - `Volume`
    - `Change`
- The package also documents `StockListing('KRX-MARCAP')`
  - indicating market-cap-oriented listing support
- For normal stock price reads, trading value is not the primary documented output

### Practical Characteristics
- Good as:
  - price backup source
  - listing/reference helper
  - optional supplemental metadata source
- Less convincing as the primary market-metrics source for:
  - full-market ranking
  - robust trading-value batch collection

### Installation Proposal Only
- Candidate approach:
  - `pip install finance-datareader`

### Suitability Judgment
- Better as a secondary or supplemental source than as the main market-metrics collector

## Data Source Comparison

| Source | Install burden | Trading value | Market cap | Listed shares | Market field | Full-market rank | Watchlist focus | Batch market run | Speed/shape | Stability | DrCT fit |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|---|---|
| PyKRX market_cap | low if already using `pykrx` | yes in intended API | yes | yes | indirect | possible | good | possible | API-style | currently unstable in local probe | medium |
| marcap | extra dependency or dataset repo | yes (`Amount`) | yes (`Marcap`) | yes (`Stocks`) | yes (`Market`) | yes (`Rank`) | acceptable | very good | dataset-style | likely high for ranking workloads | high |
| FinanceDataReader | extra dependency | not primary for normal price read | partial via listings | partial via listings | listings support | limited compared to marcap | good for selective reads | weaker than marcap | reader/listing mix | medium | medium-low as primary market-metrics source |

## Recommended Source Strategy

### Recommendation
- Primary candidate: `marcap`
- Secondary fallback / validation source: `pykrx` market-cap functions
- Optional supplemental source: `FinanceDataReader`

### Reasoning
- `marcap` is the best shape for:
  - trading value
  - market cap
  - listed shares
  - market segmentation
  - full-market rank and percentile calculations
- PyKRX market-cap APIs are attractive because `pykrx` is already installed, but the local probe failed and therefore do not yet justify production adoption as the sole market-metrics source
- FinanceDataReader looks more useful as a support source than as the main liquidity/ranking source

## Recommended Collection Structure

### Direction
- Keep `stock_daily_prices` focused on price-series storage
- Add a separate market-metrics path for liquidity and ranking data
- Treat market metrics as a parallel dataset, not a forced extension of the existing price collector

### Why
- The data cadence and source profile differ
- Ranking fields are naturally market-wide
- A dedicated table is easier to reason about than overloading `stock_daily_prices`

## Recommended DB Design

### Option A
- Add only `trading_value` back into `stock_daily_prices`

### Option B
- Create `stock_daily_market_metrics`

### Recommended Option
- Option B: `stock_daily_market_metrics`

### Proposed Table
- `stock_daily_market_metrics`

### Suggested Columns
- `id`
- `stock_id`
- `trade_date`
- `market`
- `close_price`
- `market_cap`
- `listed_shares`
- `trading_volume`
- `trading_value`
- `market_rank`
- `source`
- `created_at`
- `updated_at`

### Suggested Uniqueness
- unique on:
  - `stock_id`
  - `trade_date`
  - `source`

### Notes
- `stock_daily_prices.trading_value` may later be backfilled or synchronized secondarily
- The canonical liquidity/ranking dataset should still live in `stock_daily_market_metrics`

## Liquidity / Market Metrics Design

### Stock-level Metrics
- `trading_value`
- `avg_trading_value_5d`
- `avg_trading_value_20d`
- `trading_value_ratio_20d`
- `is_trading_value_over_50b`
- `trading_value_sum_5d`
- `trading_value_sum_20d`
- `volume_ratio_20d`
- `market_cap`
- `trading_value_to_market_cap_ratio`

### Market / Ranking Metrics
- `market_trading_value_rank`
- `market_trading_value_percentile`
- `watchlist_trading_value_rank`
- `watchlist_trading_value_percentile`

### Packaging Direction
- Future GPT package block candidates:
  - `liquidity_summary`
  - or `market_metrics_summary`

### Rules
- Facts only
- No buy/sell recommendation text
- No "strong buy", "sell risk", or similar labels

## GPT Package Connection Direction
- `price_summary`
  - factual price context
- `market_metrics_summary`
  - liquidity, market-cap, and ranking context
- `news_summary`
  - recent news facts
- `disclosure_summary`
  - filing/event facts
- `theme_summary`
  - theme and sector tags

This composition keeps liquidity/ranking logic separate from price-series logic while still allowing one merged GPT advisory payload later.

## Prototype Script
- Added:
  - `scripts/prototypes/market_metrics_source_probe.py`
- Scope:
  - check installed package versions
  - read latest local `pykrx` trade date
  - enumerate PyKRX market-cap functions
  - probe selected tickers and a full-market daily request
- Restrictions:
  - does not modify DB
  - does not modify API
  - does not modify production collectors

## Implementation Proposal
1. Validate `marcap` installation and one-day sample load in an isolated spike.
2. If acceptable, design `stock_daily_market_metrics` migration and repository layer.
3. Build a batch collector for one trade date across the market, then filter/join to local `stock_id`.
4. Add ranking and rolling-liquidity derivation logic after raw storage is stable.
5. Expose a future `market_metrics_summary` block for GPT package composition.

## Risks and Mitigations
- Risk: PyKRX market-cap endpoints may be unstable or environment-sensitive
  - Mitigation: do not make them the sole source until repeated successful probes are confirmed
- Risk: `marcap` introduces an additional dependency or data-delivery workflow
  - Mitigation: keep it in a dedicated collector path and avoid coupling it to price collection
- Risk: finance-source schemas may drift
  - Mitigation: store raw-source metadata and keep market-metrics ingestion isolated from summary APIs
