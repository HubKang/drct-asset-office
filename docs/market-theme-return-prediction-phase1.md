# 테마등락예측 1단계 — 규칙 기반 예측·검증 MVP

## 목적과 조사 결과

전일까지 저장된 가격·수급 데이터로 사용자가 선택한 대상일의 테마등락률과 순위를 예측하고, 같은 대상일의 실측값이 수집되면 예측 오차와 기준 모델 대비 효과를 검증한다. 공식 방법은 `RULE`, 버전은 `RULE_V1`이다.

현재 DB의 `market_theme_daily_returns.avg_change_rate`가 테마등락률이다. 연결 종목 중 `data_status='success'`이고 `change_rate`가 있는 종목만 단순평균하며, 가중평균하지 않는다. 결측 종목은 평균에서 제외하고 `failed_stock_count`에 반영한다. 거래대금은 유효 종목 합계다. 예측 서비스는 이 집계와 `market_theme_stock_daily_returns`, `stock_investor_flows`, 현재 활성 테마·종목 연결을 일괄 조회하며 외부 API를 호출하지 않는다.

## 날짜 정책

- `data_cutoff_date`: `avg_change_rate`가 있는 가장 최근 `return_date`로 자동 산정한다.
- `target_date`: 사용자가 선택하며 기준일보다 이후인 평일이어야 한다.
- 기본 대상일: 기준일 다음 날, 토·일이면 다음 월요일이다. 공휴일은 자동 판정하지 않는다.
- 실측 연결은 오직 `target_date = return_date`와 `theme_id`로 수행한다.
- 실측이 이미 있거나 `EVALUATED`인 대상일은 다시 예측할 수 없다.

## DB와 Upsert

- `market_theme_return_prediction_runs`: 대상일·단계·기간 기준 실행 메타데이터와 수정 횟수
- `market_theme_return_prediction_items`: 테마별 구조화된 점수, 예측, 실측, Gap과 기준 모델 효과
- `market_theme_return_prediction_metrics`: run별 집계 검증 지표
- `market_theme_return_prediction_rule_sets`, `market_theme_return_prediction_rule_parameters`: 버전과 숫자 파라미터

실행 유일키는 `(target_date, prediction_stage, prediction_horizon)`이다. 재예측은 `revision_count`를 늘리고 최초 시각을 유지한다. 항목과 지표는 각각 `(run_id, theme_id, prediction_method)`, `run_id`로 Upsert한다. 계산 완료 후 한 트랜잭션으로 저장하며 원본 응답·피처 JSON·차트 시계열은 저장하거나 API로 노출하지 않는다.

## RULE_V1 계산

구성 점수는 같은 기준일의 활성 테마 횡단면 백분위(0~100)를 사용한다.

- 가격: 기준일, 최근 3·5일 평균, 최근 10일 일평균 모멘텀, 3일 가속도의 평균 후 백분위
- 수급: 최근 5개 저장일의 외국인+기관 순매수와 프로그램 순매수 25%를 기준일 거래대금으로 나눈 값의 백분위
- 확산: 기준일 상승 종목 비율과 최근 수급 순유입 종목 비율의 평균 후 백분위
- 결합: 가격·수급 백분위의 방향 일치도와 동반 강도를 결합
- 유동성: 기준일 거래대금/최근 5일 평균 거래대금의 백분위
- 시장환경: 안정적인 연결 데이터가 없는 V1에서는 중립값 50
- 감점: +5% 초과 과열, 단일 종목 거래대금 집중, 최소 수집률 미달, 가격 상승·수급 이탈

결측 구성값은 0으로 바꾸지 않는다. 존재하는 구성값의 가중치만 다시 정규화한다. 기준일 가격 수집률이 `MIN_DATA_COVERAGE` 미만이면 예상값은 표시할 수 있지만 공식 순위에서는 제외하고 `NOT_EVALUABLE`로 표시한다.

```text
weighted_score = sum(component_score × component_weight) / sum(available_weight)
total_score = weighted_score + penalty_score
signal = clamp((total_score - 50) / 50, -1, +1)
predicted_change_rate = clamp(
  recent_theme_mean + signal × recent_cross_section_volatility × PREDICTION_SCALE + PREDICTION_BIAS,
  PREDICTION_MIN,
  PREDICTION_MAX
)
```

`recent_theme_mean`은 최근 최대 20개 실측일에 저장된 테마등락률 전체 평균, `recent_cross_section_volatility`는 날짜별 테마 횡단면 표준편차의 평균이다. 동률은 예상 등락률, prediction score, 테마명, theme_id 순으로 확정해 재현 가능한 순위를 만든다.

## 검증

- `signed_gap = actual - predicted` (양수 과소예측, 음수 과대예측)
- `absolute_gap = abs(actual - predicted)`
- `rank_gap = actual_rank - predicted_rank`
- 방향 적중은 기본 ±0.5% 중립 구간을 포함한 부호 일치로 계산한다.
- 기준 모델은 `predicted = base_change_rate`다.
- `prediction_effect = baseline_absolute_error - absolute_gap`이다.

집계 지표는 MAE, RMSE, 평균 signed Gap, 평균 순위오차, Top1, Precision@3/5/10, 방향 적중률, Spearman, NDCG@5, 기준 MAE, MAE 개선폭, 기준 Precision@5, 개선 테마 수다. 실측이 없으면 값을 만들지 않고 run만 `WAITING_ACTUAL`로 바꾼다.

## 화면과 D+1

테마등락추이 히트맵은 실제 데이터의 최근 29개 날짜와 D+1 예측 한 열로 총 30열을 유지한다. D+1은 기준일과 일치하는 가장 최근 비취소 run을 사용하며, 점선 경계·낮은 배경 알파·선명한 텍스트를 적용한다. 헤더 클릭은 높은 순 → 낮은 순 → 기본 순으로 순환하고 결측은 항상 아래다.

`테마등락예측` 탭은 기준일/대상일, 그룹·검색·표시 수, 규칙 버전, 수정 횟수와 상태를 보여준다. 그래프는 0축에서 시작하는 옅은 예측 막대 위에 진한 기준일 막대를 겹치며, 검증 후 실측은 세로 마커로 표시한다. 목록은 예측 전 구성 점수와 완전성을, 검증 후 Gap·기준 오차·효과·방향 적중을 표시한다. 조회는 `AbortController`로 이전 요청을 취소하고 최신 응답만 반영한다.

## 설정 개선 안내

검증 응답에서 최대 4개를 일시 계산한다. 낮은 완전성, 과대·과소 편향, 낮은 Top5 분리력, 순위 대비 과도한 예측 스케일을 진단하며 현재 설정·제안 범위·예상 영향을 반환한다. DB에 JSON으로 저장하거나 자동 적용하지 않는다. 단일 날짜 결과는 설정 변경의 근거가 아니라 관찰 신호로 취급한다.

## API

- `GET /market-themes/return-predictions/latest`
- `GET /market-themes/return-predictions?target_date=YYYY-MM-DD`
- `POST /market-themes/return-predictions/predict`
- `POST /market-themes/return-predictions/validate`
- `GET /external/kiwoom/market-themes/returns/range` — 실측과 기준일 일치 D+1 묶음 반환

## 제외 범위와 확장

거래일 캘린더, ML/GPT, 자동 파라미터 변경, 장중 예측, 알림은 제외한다. 이후 그림자 ML 모델은 같은 run 아래 `prediction_method`, `model_version`, `is_official=false` 항목으로 병렬 저장할 수 있다. 공식 전환 시 run의 `official_method`와 항목의 `is_official`만 명시적으로 관리한다.
