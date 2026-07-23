# Market Signal Stage Based Operation UX

## Goal

The single-indicator signal screen now presents the workflow as an operational sequence:

1. 추세 확인
2. 초안 생성
3. 과거 검증
4. 운영 활성화

Economic Flow Management and scenario diagnosis remain out of scope.

## Official Status Terms

User-facing operation status terms:

- 미등록
- 초안
- 운영
- 중지
- 데이터 부족

Database enum compatibility remains:

- `DRAFT` -> 초안
- `ACTIVE` -> 운영
- `INACTIVE` -> 중지
- `NOT_REGISTERED` -> 미등록
- `DATA_INSUFFICIENT` -> 데이터 부족

Do not use `검토 중` or `운영 중` as top-level status labels.

## Draft Validation Status

Draft validation is separate from operation status:

- 미검증
- 수정 필요
- 검증 완료
- 활성화 준비

The screen shows validation state only for draft cards.

## Card Roles

미등록 카드:

- 추세를 확인할 지표
- Shows raw sparkline when data exists
- Actions: `1차 추세 확인`, `2차 시그널 초안 생성`

초안 카드:

- 룰을 검증할 시그널
- Actions: `상세 분석`, `3차 과거 검증`, `4차 운영 활성화`
- Activation is disabled until validation is complete or activation-ready

운영 카드:

- 자동 평가 중인 시그널
- Actions: `운영 상세`, `평가 이력`, `새 버전 초안`, `운영 중지`
- No draft creation action is shown

중지 카드:

- 이력은 유지하되 운영하지 않는 시그널
- Actions: `평가 이력`, `새 버전 초안`

데이터 부족 카드:

- Indicates the indicator does not meet the minimum observation count
- Draft creation is disabled

## 1차 추세 확인 Drawer

Preview opens a drawer rather than a top notice. The drawer contains:

- Basic metadata
- Raw series
- Temporary regression trend line
- Upper/lower trend channel
- DrCT temporary trend judgement
- Plain-language explanation
- Recommended model configuration

Preview does not save signal definitions, evaluations, events, or episodes.

### Chart Range And Temporary Settings

The preview API accepts `period` and non-persistent `configuration` overrides.

Default periods:

- daily: `3M`
- weekly: `1Y`
- monthly: `3Y`

`3M` and other non-ALL periods are calendar ranges, not a fixed number of rows. The response returns:

- `requested_period`
- `actual_period_type`
- `actual_period_description`
- `range_start`
- `range_end`
- `observation_count`

The chart itself uses the currently applied trend analysis window, so chart point count can be smaller than the total observation count in the selected period.

Temporary setting overrides are recalculated through preview only and are not saved until the user creates a draft.

## 2차 시그널 초안 생성

Draft creation opens a confirmation modal. Created rules stay as `DRAFT`; they are never activated automatically.

Bulk creation is renamed to `선택 시그널 초안 생성` and confirms before execution.

## 3차 과거 검증

The draft card action runs the existing single-indicator simulation API with a default 3-year period, then records:

- `validation_status = VALIDATED`
- `validation_period_years`
- `validation_completed_at`
- `validation_summary_json`
- `activation_ready = 1`

This is a first operational hook. More detailed validation dashboards can be added later.

## 4차 운영 활성화

Activation requires completed validation or activation-ready state. It stores:

- `activated_at`
- `activation_reason`

Activation runs a current evaluation after status change.

## New Version and Stop

`새 버전 초안` clones the current rule into a new DRAFT version instead of overwriting the active rule.

`운영 중지` changes status to `INACTIVE` and stores:

- `deactivated_at`
- `deactivation_reason`

Historical evaluations and events are retained.

## Automatic Evaluation Pipeline

The target pipeline is:

source collection -> derived recalculation -> changed item detection -> ACTIVE single signal evaluation -> composite signal evaluation -> phenomenon evaluation.

This pass adds activation-time evaluation and status metadata. Full changed-indicator-triggered automatic evaluation after market data refresh remains a follow-up backend job.


## 운영 평가 이력

운영 활성화 이후 BASELINE·PERIODIC·MANUAL 평가와 상태 전환 이벤트 정책은 [운영 시그널 평가 이력](./market-signal-evaluation-history.md)을 따른다. 사용자 표시는 FALSE_BREAK를 ‘일시 이탈 후 복귀’로 통일한다.

## 2026-07-22 복합 시그널 운영 자동화 반영

- 복합 시그널 운영 상태와 현재 판정을 별도 필드·배지로 분리했다.
- 검증된 DRAFT만 활성화하며, 활성화 시 이벤트 없는 BASELINE 평가를 저장한다.
- 활성 단일 지표 평가 뒤 관련 ACTIVE 복합 규칙을 관측일별 PERIODIC 평가로 자동 연결한다.
- 지표·모델·조건 역할·조건 문장은 공통 한글 표시 서비스에서 생성한다.
- 상세 설계와 감사 절차는 `docs/market-composite-signal-operation.md`를 따른다.