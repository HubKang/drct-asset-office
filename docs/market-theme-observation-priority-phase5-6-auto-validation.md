# Phase5.6 관찰순위 계산 선행 자동검증

## 목적

관찰순위 계산을 시작할 때 종료된 최근 거래일의 기존 관찰 스냅샷을 실제 테마등락률로 먼저 검증한다. 검증 결과는 Phase5.5 스칼라 테이블에 Upsert하고 Diagnostics를 갱신한 뒤 새로운 D+1 관찰순위를 계산한다.

## 일일 workflow

CURRENT 선택 순서는 자동검증 commit → 현재 DB 시장지표 재조회 → D+1 Feature/관찰순위 계산 → CURRENT 스냅샷 Upsert다.

REFRESHED 선택 순서는 자동검증 commit → 전체 시장지표 갱신과 후속 신호평가 → `expire_all` → D+1 Feature/관찰순위 계산 → REFRESHED 스냅샷 Upsert다. 검증은 반드시 시장지표 갱신 전에 수행한다.

자동검증과 D+1 계산은 하나의 transaction으로 묶지 않는다. 검증이 성공한 뒤 D+1 계산이 실패해도 검증 결과는 유지된다. 검증 예외는 `AUTO_VALIDATION_FAILED`로 응답하고 D+1 계산을 차단하지 않는다.

## latest_actual_trade_date와 completeness

시스템의 오늘 날짜는 사용하지 않는다. `market_theme_daily_returns`를 날짜별로 묶어 실제값이 10개 이상이고 활성 leaf 테마 대비 coverage가 50% 이상인 가장 최근 거래일을 `latest_actual_trade_date`로 선택한다.

현재 저장 구조에는 테마등락률 전체수집 완료 run 테이블이 없으므로 수집 완료 상태 대신 날짜별 실제값 개수와 Quality Gate를 사용한다. 단순 `MAX(return_date)`는 부분 수집 날짜가 선택될 수 있어 사용하지 않는다.

## 자동검증과 Catch-up

`latest_actual_trade_date` 이하에서 실제값이 존재하는 관찰 스냅샷 중 다음 조건을 만족하는 날짜를 최대 20개까지 오래된 순으로 검증한다.

- 아직 `EVALUATED`가 아닌 sample이 존재
- 실제 테마등락률의 `updated_at`이 sample의 `evaluated_at`보다 최신

CURRENT만 있으면 CURRENT만, REFRESHED만 있으면 REFRESHED만, 둘 다 있으면 두 모드를 같은 Phase5.5 공식으로 검증한다. 동일 키 Upsert를 사용하므로 반복 실행해도 row가 증가하지 않으며 수정된 실측은 재검증된다.

## 정상 상태와 오류 정책

- `AUTO_VALIDATION_WAITING_ACTUAL`: 완결성 Gate를 통과한 실측일 없음
- `AUTO_VALIDATION_SKIPPED_NO_OBSERVATION`: 최신 실측일에 비교할 관찰 스냅샷 없음
- `AUTO_VALIDATION_UP_TO_DATE`: 최신 실측 기준 검증 완료 상태
- `SUCCESS`: pending 또는 수정 실측 검증 완료
- `AUTO_VALIDATION_FAILED`: ValidationService 예외

WAITING, SKIPPED, INSUFFICIENT_UNIVERSE 및 FAILED 모두 신규 D+1 계산을 막지 않는다. 가짜 실제값이나 validation row를 만들지 않으며 기존 검증 row도 삭제하지 않는다.

## API와 화면

기존 `POST /market-themes/observation-priorities/calculate` 요청은 그대로 유지한다. 응답에 다음 optional summary만 추가한다.

- `pre_validation_status`
- `pre_validation_target_date`
- `pre_validation_modes`
- `pre_validation_quality_status`
- `pre_validation_message`
- `diagnostic_status`

상세 테마별 결과는 calculate 응답에 포함하지 않는다. 계산 완료 후 화면은 Diagnostics API를 다시 호출해 품질 검증일과 RULE·시장보정·ML 상태를 즉시 갱신한다.

기존 수동 검증 버튼은 `재검증`으로 유지한다. 재검증은 선택일 검증만 수행하며 시장지표 갱신이나 D+1 계산을 호출하지 않는다.

## 저장 및 회귀 보호

신규 DB 테이블이나 migration은 없다. 기존 Phase5.5 validation samples/metrics만 사용한다. 실제 순위, Top20, Gap, Hit, 일별 metrics와 시장보정 효과만 저장하며 시장지표·종목가격·수급 snapshot, Feature/분석 JSON, 원천 JSON, 학습 CSV는 저장하지 않는다.

Diagnostics의 개선 메시지는 사용자 알림 전용이다. RULE, 가중치, 상태분류, ML 학습, Shadow 교체 또는 모델 승격을 자동 수행하지 않는다. 기존 data cutoff, 시장지표 as-of, D+1 히트맵, 실측 열 및 Phase1~5.5 저장 구조는 변경하지 않는다.
