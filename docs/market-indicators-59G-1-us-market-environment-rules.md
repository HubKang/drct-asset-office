# 59-G-1 US Market Environment Rules

## Purpose

This update connects FRED-based US market indicators to the market environment insight cards. The goal is to let the Market Indicators page interpret domestic market conditions together with global equity sentiment, semiconductor sentiment, and US rate pressure.

## Input Indicators

- US_NASDAQ: Nasdaq Composite
- US_SP500: S&P 500
- US_DOW: Dow Jones Industrial Average
- US_SOX: Philadelphia Semiconductor Index
- US_10Y: US 10-year Treasury yield
- US_2Y: US 2-year Treasury yield
- US_FED_FUNDS: Federal Funds Rate

## Added Insight Cards

### US Market Flow

- Uses NASDAQ 5-day change and S&P 500 5-day change as the main signals.
- If both are positive, the card presents a global risk appetite reference signal.
- If both are negative, the card presents a global equity sentiment caution signal.
- If DOW is firm while NASDAQ is weak, the card treats it as a split between value and growth flows.
- NASDAQ 20-day and S&P 500 20-day changes are shown as confirmation evidence.

### Global Semiconductor Sentiment

- Uses US_SOX 5-day change as the main signal.
- Above +3% is treated as improving global semiconductor sentiment.
- Below -3% is treated as a caution signal for domestic semiconductor theme liquidity.
- If NASDAQ and SOX diverge, the card asks the user to check whether broad tech and semiconductors are sending different signals.

### US Rate Environment

- Uses US_10Y 5-day change converted to bp.
- Above +10bp is treated as a possible discount-rate burden for growth stocks.
- Below -10bp is treated as rate-pressure relief, while still asking whether the move comes from growth concerns.
- Negative US_10Y minus US_2Y spread is shown as a yield-curve inversion caution.
- Fed Funds latest value and change are shown as evidence chips only.

## Missing Data Handling

- If a required US indicator has no values or cannot be parsed as a number, the relevant insight card falls back to a neutral missing-data state.
- Existing domestic market, FX/rate, inflation/economy, and risk-off cards are not changed by missing US data.

## Wording Policy

- No buy recommendation text was added.
- No sell recommendation text was added.
- The cards use reference-only language such as possibility, burden factor, relief factor, and confirmation needed.
