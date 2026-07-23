# Market Signal Management MVP

## Purpose

Market signal management detects transition points in collected market indicators. It focuses less on whether a value is high or low and more on whether direction, momentum, persistence, or confirmation across indicators is changing.

The DrCT structure is:

- Phenomenon: what changed in the indicators
- Process: why the change may matter economically
- Result: what future market condition should be watched

## Data Model

The MVP adds:

- `market_signal_definitions`
- `market_signal_conditions`
- `market_signal_evaluations`
- `market_signal_events`
- `market_signal_versions`

Definitions store rule metadata and the phenomenon/process/result text templates. Conditions store item, transform, threshold, role, and weight. Evaluations store DrCT-calculated evidence, opposing evidence, missing data, score, state, and data quality. Events are recorded only when a meaningful state transition occurs. Versions preserve rule snapshots when a rule is saved or seeded.

No external API raw JSON is stored in these signal tables.

## Transform Set

Supported transforms are constrained to known enum values:

- RAW_VALUE
- CHANGE
- CHANGE_RATE
- MOM
- YOY
- MOVING_AVERAGE
- MA_CROSS_UP
- MA_CROSS_DOWN
- SLOPE
- TREND_DIRECTION
- TURN_UP
- TURN_DOWN
- ACCELERATING_UP
- DECELERATING_UP
- ACCELERATING_DOWN
- DECELERATING_DOWN
- Z_SCORE
- PERCENTILE
- DISTANCE_FROM_MA
- N_PERIOD_HIGH
- N_PERIOD_LOW
- CONSECUTIVE_UP
- CONSECUTIVE_DOWN
- PERSISTENCE
- SPREAD
- RATIO
- RELATIVE_STRENGTH
- CORRELATION
- DIVERGENCE

Some relationship transforms are MVP-compatible pass-throughs when the relationship has already been materialized as a derived indicator.

## Scoring And State

Condition roles:

- REQUIRED: all required conditions must pass for a strong active state
- CONFIRM: increases score and confidence
- OPPOSING: subtracts from score or weakens the signal

Default state bands:

- 0-39: INACTIVE
- 40-59: WATCH
- 60+: ACTIVE

If the score is active and the previous saved score changes materially, the state can become STRENGTHENING or WEAKENING. Missing data lowers `data_quality_score`; when it falls below the rule minimum, the result is DATA_INSUFFICIENT.

## Initial Draft Signals

The MVP seeds four DRAFT rules:

- `US_REAL_RATE_GROWTH_PRESSURE`
- `RISK_ON_TO_RISK_OFF_TURN`
- `DISINFLATION_TO_REFLATION_TURN`
- `US_EMPLOYMENT_STABLE_TO_WEAKENING`

They are not automatically activated. The user can inspect conditions and activate them from the UI.

## API

Implemented endpoints:

- `GET /market-signals`
- `GET /market-signals/{id}`
- `POST /market-signals`
- `PUT /market-signals/{id}`
- `POST /market-signals/{id}/activate`
- `POST /market-signals/{id}/deactivate`
- `POST /market-signals/{id}/archive`
- `POST /market-signals/evaluate`
- `GET /market-signals/{id}/evaluations`
- `GET /market-signals/events`
- `POST /market-signals/{id}/simulate`
- `POST /market-signals/gpt-rule-draft`

### Completion Additions

- `GET /market-signals/indicator-catalog`
  - Returns indicator provider, frequency, data count, first/latest value date, readiness, GPT classification, and supported transforms.
- `POST /market-signals/condition-preview`
  - Evaluates one draft condition against the latest available observation date and returns current transform value and pass/fail.
- `POST /market-signals/{id}/simulate`
  - Now includes occurrence count, average/median/max persistence, condition pass counts, required satisfaction count, confirm contribution count, opposing penalty count, data-insufficient periods, and frequency/rarity/duplicate warnings.
  - Also returns current/sensitive/balanced/conservative variant summaries, condition contribution summaries, and recent transition points for chart/UI display.
- `POST /market-signals/gpt-rule-draft`
  - Prompt catalog now includes readiness, data count, first/latest dates, provider, frequency, classification, and supported transforms.
  - Validation rejects unknown item codes, unsupported transforms, non-signal-ready indicators, and transforms that need more data.

The rule editor UI supports inline condition add/delete/edit, condition preview, editable phenomenon/process/result templates, simulation, and save through `PUT /market-signals/{id}`.

### Initial Signal Simulation Results

After source backfill and derived recalculation, the initial four DRAFT rules can be simulated over multi-year windows without changing their status.

| Signal | 3Y sample | 3Y active | 3Y avg persistence | 3Y avg score | Latest state |
| --- | ---: | ---: | ---: | ---: | --- |
| US_REAL_RATE_GROWTH_PRESSURE | 777 | 83 | 3.77 | 32.13 | WATCH |
| RISK_ON_TO_RISK_OFF_TURN | 777 | 74 | 1.85 | 34.16 | WATCH |
| DISINFLATION_TO_REFLATION_TURN | 764 | 238 | 5.29 | 53.51 | WATCH |
| US_EMPLOYMENT_STABLE_TO_WEAKENING | 662 | 51 | 3.92 | 30.32 | INACTIVE |

Rule review observations:

- `DISINFLATION_TO_REFLATION_TURN` is the most active of the initial rules. WTI and inflation expectation conditions should be reviewed carefully before activation to avoid over-triggering.
- `RISK_ON_TO_RISK_OFF_TURN` tends to stay in WATCH rather than ACTIVE. This is useful for monitoring, but confirmation thresholds may need a sharper risk-off gate.
- `US_REAL_RATE_GROWTH_PRESSURE` also stays mostly WATCH. Real-rate slope and relative-strength conditions appear to overlap, so duplicate momentum pressure should be reviewed.
- `US_EMPLOYMENT_STABLE_TO_WEAKENING` is comparatively conservative. A four-week moving average transform for claims is a likely next candidate before activation review.

No initial rule was auto-activated.

## UI

The new route is:

`/market-indexes/signals`

The menu is nested under Market Indicator Management. The screen includes:

- Today transition cards
- Rule list/detail view
- Evaluation history
- GPT rule design helper

Economic Flow Management and Economic Scenario Diagnosis are registered as follow-up placeholder routes.

## GPT Helper

The GPT helper currently supports a prompt-copy workflow and JSON validation workflow. It sends only indicator catalog metadata and supported transform enums, not raw API payloads.

GPT is constrained to suggest rule drafts. DrCT validates item codes and transform enums before a result can become a draft rule.

## Known Limits

- The MVP does not yet provide a full inline condition editor.
- Backtest simulation reports signal occurrence statistics only; it does not calculate future market returns.
- Direct GPT API invocation is not wired yet. The prompt-copy and paste-validate workflow is operational.
- Several new FRED indicators are registered but not all have collected values in the current DB, so some seeded signals evaluate as DATA_INSUFFICIENT until collection is completed.

## Next Link

The next layer, Economic Flow Management, should compose multiple signal states into broader economic flow regimes and scenario diagnostics.

## Trend And Composite Enhancement

The next enhancement keeps Economic Flow Management deferred and upgrades this screen into three user-facing layers:

- `단일 지표 시그널`
- `복합 지표 시그널`
- `객관적 현상`

The implementation adds non-destructive trend/composite/phenomenon structures, including `market_signal_trend_models`, evidence sources, episodes, episode outcomes, user reviews, and rule experiments. Existing signal definitions and conditions remain compatible.

The single-indicator layer evaluates regression-channel trend state, normalized slope, trend strength, channel position, break candidate/confirmed states, 일시 이탈 후 복귀 (`FALSE_BREAK`), reversal confirmation, and trend resumed states using only data up to the observation date.

The composite layer separates trigger, confirm, context, opposing, and invalidation evidence while keeping `REQUIRED` compatible with trigger semantics.

The phenomenon layer packages observed facts, rule interpretation, GPT auxiliary diagnosis boundaries, uncertainty, missing conditions, next checks, and episode history. GPT diagnosis is prompt-only/auxiliary and cannot change DrCT state, score, rule activation, or existing rules.

See `docs/market-signal-trend-and-composite-enhancement.md` for the endpoint and schema details.
