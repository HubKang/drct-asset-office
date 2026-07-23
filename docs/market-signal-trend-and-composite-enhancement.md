# Market Signal Trend And Composite Enhancement

## Scope

This enhancement keeps Economic Flow Management and scenario diagnosis out of scope. The market signal layer now prepares three objective layers that can later be handed off to Economic Flow Management:

- `단일 지표 시그널`: one indicator's trend, channel, break, 일시 이탈 후 복귀 (FALSE_BREAK), reversal, or resumed trend state.
- `복합 지표 시그널`: trigger, confirm, context, opposing, and invalidation evidence across indicators.
- `객관적 현상`: an observed phenomenon result built from single and composite signal evidence.

Legacy internal values such as `ATOMIC` and `COMPOSITE` remain compatible. New user-facing labels use `SINGLE_INDICATOR`, `COMPOSITE_INDICATOR`, and `PHENOMENON`.

## DB Backup

Before the migration work, the SQLite database was backed up as:

`db/drct_asset.sqlite3.backup-20260718-1841-signal-trend-composite`

No existing signal definitions, conditions, evaluations, or collected indicator data were deleted or reset.

## Schema Additions

The market signal schema now adds:

- `market_signal_trend_models`
- `market_signal_evidence_sources`
- `market_signal_episodes`
- `market_signal_episode_outcomes`
- `market_signal_user_reviews`
- `market_signal_rule_experiments`

`market_signal_definitions` keeps its rule operating status (`DRAFT`, `ACTIVE`, `INACTIVE`, `ARCHIVED`) separate from evaluation status. Additional fields support relation type, confirmation windows, evidence groups, and duplicate evidence caps.

`market_signal_conditions` supports relation/evidence-group metadata while keeping existing condition rows compatible.

## 단일 지표 시그널

Single indicator diagnostics use regression-channel trend analysis on data available at or before the observation date. The engine computes:

- regression slope
- normalized slope
- R-squared consistency
- short and medium slopes
- moving-average alignment
- recent up/down ratio
- trend duration
- channel center, upper band, lower band, and channel position
- break candidate and confirmed break
- 일시 이탈 후 복귀 (`FALSE_BREAK`), reversal confirmation, and trend resumed states

Supported transform enums now include `TREND_STATE`, `REGRESSION_SLOPE`, `NORMALIZED_SLOPE`, `TREND_STRENGTH`, `TREND_DURATION`, `CHANNEL_POSITION`, `TREND_BREAK_UP`, `TREND_BREAK_DOWN`, `BREAK_CONFIRMED_UP`, `BREAK_CONFIRMED_DOWN`, `FALSE_BREAK_UP`, `FALSE_BREAK_DOWN`, `REVERSAL_CONFIRMED_UP`, `REVERSAL_CONFIRMED_DOWN`, `TREND_RESUMED_UP`, and `TREND_RESUMED_DOWN`.

## 복합 지표 시그널

Composite diagnostics keep existing conditions but interpret `REQUIRED` as a trigger-compatible role for the new UI. New role semantics are:

- `TRIGGER`
- `CONFIRM`
- `CONTEXT`
- `OPPOSING`
- `INVALIDATION`
- `REQUIRED` retained for compatibility

The composite API reports trigger, confirm, context, opposing, invalidation counts, relation type, confirmation window, minimum confirm count, duplicate evidence groups, and false-start status.

## 객관적 현상

Phenomenon evaluation wraps the composite signal result into an objective phenomenon state:

- observed facts
- rule interpretation
- GPT auxiliary diagnosis placeholder
- uncertainty

GPT diagnosis remains auxiliary only. It cannot change DrCT score/state, activate rules, overwrite rules, or return probabilities or buy/sell advice.

## API Additions

New endpoints:

- `GET /market-signals/single-indicator`
- `GET /market-signals/single-indicator/{id}`
- `POST /market-signals/single-indicator/{id}/evaluate`
- `POST /market-signals/single-indicator/{id}/simulate`
- `GET /market-signals/single-indicator/{id}/trend-chart`
- `GET /market-signals/composite`
- `GET /market-signals/composite/{id}`
- `POST /market-signals/composite/{id}/evaluate`
- `POST /market-signals/composite/{id}/simulate`
- `GET /market-signals/phenomena`
- `GET /market-signals/phenomena/{id}`
- `POST /market-signals/phenomena/{id}/evaluate`
- `GET /market-signals/phenomena/{id}/episodes`
- `POST /market-signals/phenomena/{id}/gpt-diagnosis`
- `GET /market-signals/events/today`
- `GET/POST /market-signals/evidence-sources`
- `GET/POST /market-signals/rule-experiments`
- `POST /market-signals/rule-experiments/{id}/approve`
- `POST /market-signals/rule-experiments/{id}/reject`
- `POST /market-signals/user-reviews`

Existing MVP endpoints remain available.

## UI

The `지표 신호 관리` page now uses seven tabs:

- `오늘의 전환`
- `단일 지표 시그널`
- `복합 지표 시그널`
- `객관적 현상`
- `룰 설계·검증`
- `GPT 진단`
- `평가·학습`

The rule editor continues to support condition editing, preview, simulation, and save. The new tabs expose the layered structure without implementing Economic Flow Management.

### Card And Studio UX Follow-Up

The screen was further simplified into five main work areas:

- `오늘의 전환`
- `시그널`
  - `단일 지표 시그널`
  - `복합 지표 시그널`
- `객관적 현상`
- `룰 스튜디오`
  - direct/simple design
  - template library
  - GPT design
  - advanced condition editing
- `평가·학습`

Cards now avoid large unexplained numbers. Values are shown with semantic labels such as current value, trend strength, channel position, phenomenon fulfillment, and next checks. Single-indicator cards include compact sparkline points from the overview API. Composite and phenomenon cards separate trigger/start conditions, continuing confirmations, opposing evidence, and missing data.

The batch endpoint `GET /market-signals/overview` returns card summaries, latest evaluation status, sparkline points, recent event summaries, next checks, and rule templates in one request. Detailed charts remain separate and can be loaded only after a card is opened.

Status visualization uses a subdued left state line and status badges instead of strong full-card color fills:

- `TREND_INTACT`: trend maintained
- `TREND_WEAKENING`: trend weakening
- `BREAK_CANDIDATE`: trend break candidate
- `BREAK_CONFIRMED`: trend break confirmed
- `REVERSAL_CONFIRMED`: reversal confirmed
- `FALSE_BREAK`: temporary break and return
- `DATA_INSUFFICIENT`: insufficient data

## Rule Template Library

The enhancement adds `market_signal_rule_templates` with idempotent seed data. Templates are not activated automatically. They can be copied into a new `DRAFT` signal definition for review and editing.

Seeded templates currently cover:

- rate and growth-stock pressure
- risk-on/risk-off signals
- inflation and reflation signals
- employment and cycle signals
- dollar and FX context
- Korea market and semiconductor context

GPT-assisted design remains a prompt/validation workflow. GPT proposals can become only DRAFT rules after DrCT validation; they never become ACTIVE automatically.

## Current Initial Templates

The initial objective phenomenon candidates are based on the existing four DRAFT rules:

- `US_REAL_RATE_GROWTH_PRESSURE`
- `RISK_ON_TO_RISK_OFF_TURN`
- `DISINFLATION_TO_REFLATION_TURN`
- `US_EMPLOYMENT_STABLE_TO_WEAKENING`
# 2026-07-18: 전체 지표 시그널 적용 범위 확대

시장 신호 관리는 이제 `market_indexes`와 `market_indicators`를 합친 공통 카탈로그를 사용한다. 단일 지표 시그널 화면은 기존에 등록된 추세 모델 카드만 보여주지 않고, 국내 지수/업종/환율/금리/물가·경기/원자재/파생 지표까지 포함한 전체 후보를 표시하며 미등록 지표는 DRAFT 생성 대상으로 노출한다.

세부 정책과 API 목록은 [market-signal-all-indicator-coverage.md](market-signal-all-indicator-coverage.md)에 기록한다.


## 운영 평가 이력

운영 활성화 이후 BASELINE·PERIODIC·MANUAL 평가와 상태 전환 이벤트 정책은 [운영 시그널 평가 이력](./market-signal-evaluation-history.md)을 따른다. 사용자 표시는 FALSE_BREAK를 ‘일시 이탈 후 복귀’로 통일한다.

## 2026-07-22 복합 시그널 운영 자동화 반영

- 복합 시그널 운영 상태와 현재 판정을 별도 필드·배지로 분리했다.
- 검증된 DRAFT만 활성화하며, 활성화 시 이벤트 없는 BASELINE 평가를 저장한다.
- 활성 단일 지표 평가 뒤 관련 ACTIVE 복합 규칙을 관측일별 PERIODIC 평가로 자동 연결한다.
- 지표·모델·조건 역할·조건 문장은 공통 한글 표시 서비스에서 생성한다.
- 상세 설계와 감사 절차는 `docs/market-composite-signal-operation.md`를 따른다.
## 객관적 현상 해석 계층 보강

객관적 현상은 더 이상 복합 룰 카드를 반복하지 않는다. 원천 복합 평가를 참조하면서 관찰 근거·반대 근거·데이터 부족·다음 확인을 분리한다. 상세 정책은 [market-objective-phenomena.md](market-objective-phenomena.md)를 따른다.
