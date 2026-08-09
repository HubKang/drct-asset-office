# Phase5.5 관찰결과 실전 Gap 축적 및 개선 알림

## 목적과 저장 정책

Phase5.5는 D+1 관찰순위와 실제 테마등락률 순위를 비교하는 장기 검증 기반이다. 검증 및 감사에 필요한 작은 스칼라 결과만 저장한다.

저장 항목은 대상일·테마·계산모드·RULE/모델/Metric 버전, 관찰 점수와 순위, 상태, 데이터 완전성, 실제 순위와 Top20 여부, 순위 오차와 signed gap, Top20 적중, 시장보정 전후 차이 및 일별 aggregate metric이다.

다음 데이터는 저장하지 않는다.

- 시장지표·가격·수급 원본 snapshot 또는 복제본
- Feature matrix/JSON, 분석 JSON, GPT 입출력
- 학습 CSV/DataFrame, fold별 raw prediction
- 실제 등락률 복제값과 재현 가능한 차트 series

실제 수익률은 `market_theme_daily_returns`를 실행 시점에 참조한다.

## CURRENT/REFRESHED 보존

관찰 계산 성공 직후 `market_theme_observation_validation_samples`에 최소 스냅샷을 Upsert한다. 키는 대상일, 테마, 계산모드, RULE 버전, 모델 버전이다. 따라서 공식 최신 관찰결과가 재계산으로 교체되어도 `CURRENT_MARKET_DATA`와 `REFRESHED_MARKET_DATA` 검증 스냅샷은 서로 덮어쓰지 않는다.

Phase5.5 적용 전에 공식 테이블에서 이미 덮어써진 결과는 추정 복원하지 않는다. 적용 이후 계산부터 정확히 축적한다.

## 실제 순위와 Gap

대상일의 `market_theme_daily_returns.avg_change_rate DESC, theme_id ASC`로 실제 순위를 결정한다. 평가 가능 테마 수의 `ceil(20%)`를 실제·관찰 Top20 크기로 사용한다.

- `rank_error = abs(actual_rank - observation_rank)`
- `rank_gap = actual_rank - observation_rank`
- `top20_hit = observation_top20 AND actual_top20`
- `refresh_score_delta = refreshed_score - current_score`
- `refresh_rank_improvement = current_rank - refreshed_rank`
- `refresh_effect = current_rank_error - refreshed_rank_error`

양의 `refresh_effect`는 시장보정 후 실제 순위에 가까워졌음을 뜻한다.

실제 데이터가 없으면 `WAITING_ACTUAL`로 안내하고 검증 metric이나 가짜 실제값을 생성하지 않는다.

## 일별 metrics와 Quality Gate

`market_theme_observation_validation_metrics`에는 모드·RULE/모델 버전별로 다음 스칼라만 저장한다.

- 전체/평가 가능 테마 수와 평가 coverage
- Precision/Recall/F1 Top20
- Precision@5, NDCG@5, Spearman, Mean Rank Error
- Top5 실제 Top20 수
- paired CURRENT/REFRESHED 개선·악화·동일 수와 평균 보정효과

평가 가능 테마 10개 미만 또는 coverage 50% 미만은 `INSUFFICIENT_UNIVERSE`이며 장기 판단에서 제외한다. Metric 버전은 `THEME_OBSERVATION_METRIC_V1`이다.

## 개선 알림과 안전장치

Diagnostics는 품질 충족 최근 5일·20일·전체를 집계한다. 품질일 10개 미만은 `INSUFFICIENT_DATA`, 10~19개는 `WATCH`다. 20개부터 최근 성능의 Precision Top20, NDCG@5, Mean Rank Error 저하를 확인해 `RULE_REVIEW_RECOMMENDED`를 알릴 수 있다.

CURRENT/REFRESHED paired 품질일이 20개 이상이고 보정효과가 비양수이거나 평균 순위오차가 악화되면 `MARKET_ADJUSTMENT_REVIEW`를 알린다. 마지막 관찰 ML 학습 후 품질 검증일이 20개 이상이면 `ML_RETRAIN_RECOMMENDED`를 알린다.

알림은 판단 보조만 수행한다. RULE·시장가중치·상태분류를 자동 수정하지 않으며 ML 학습, Shadow 교체, 공식 모델 승격을 자동 실행하지 않는다.

상태별 성능은 저장된 `status_code`, `actual_top20`, `actual_rank`, `rank_error`만 사용한다. 점수구간 성능은 저장된 관찰 점수를 80~100, 70~80, 60~70, 50~60, 0~50으로 동적 집계한다. 별도 분석 JSON은 저장하지 않는다.

## API와 화면

`GET /market-themes/observation-priorities/diagnostics`는 품질일 수, 최근 5/20/전체 CURRENT·REFRESHED 성능, paired 보정효과, 상태별·점수구간별 성능, 진단 상태와 사용자 메시지를 반환한다. 이 JSON은 응답 전용이며 DB에 저장하지 않는다.

관찰우선순위 화면은 실전검증 진단 카드에서 데이터 축적일, 최근 성능, 시장보정 비교, ML 재학습 검토 상태를 표시한다.

## DB 용량

하루 약 35~50개 테마 × 최대 2개 모드의 짧은 정형 row만 누적한다. TEXT는 버전·상태 식별자에 한정하고 JSON/BLOB·원천 snapshot을 두지 않는다. 대상일 재검증은 Upsert하므로 중복 row가 증가하지 않는다.
