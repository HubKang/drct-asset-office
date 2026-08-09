# 테마등락예측 2단계 — ML 그림자 모델

## 목적과 운영 지위

Phase2는 과거 저장 데이터로 다음 실제 관측일의 `market_theme_daily_returns.avg_change_rate`를 학습하고 RULE 공식 예측과 ML 예측을 병렬 생성한다. ML은 항상 `prediction_method=ML`, `is_official=false`, 모델 상태 `SHADOW`이며 공식 RULE, D+1 히트맵, run 수정 횟수를 변경하지 않는다. 공식 승격은 Phase3의 별도 승인 대상으로 남긴다.

## 날짜·정답·누출 방지

실측 날짜를 오름차순 정렬해 `base_date[i] → actual_dates[i+1]`로 연결한다. 따라서 금요일→월요일, 공휴일 전후도 저장된 다음 실제 관측일에 자연스럽게 매핑하며 거래일 캘린더를 사용하지 않는다. label만 target_date의 `avg_change_rate`이고 모든 feature는 base_date 이하에서 계산한다.

평균, median imputation, missing indicator, scaling은 각 walk-forward fold의 training 구간에서만 `Pipeline.fit`된다. 랜덤 분할은 사용하지 않으며 같은 target_date의 모든 테마가 하나의 validation 날짜 그룹에 속한다.

## 과거 테마 연결 처리

`market_theme_stocks`에는 날짜별 연결 이력이 없으므로 현재 활성 연결을 과거에 소급하지 않는다. 가격 확산·거래대금 집중도·종목 수급 연결은 날짜별로 저장된 `market_theme_stock_daily_returns(theme_id, stock_id, return_date)` 스냅샷만 사용한다. 이 스냅샷이 없는 과거 feature는 null로 유지하며 모델 Pipeline에서 처리한다.

## Feature V1

버전은 `THEME_RETURN_FEATURE_V1`이다. 학습 행이나 feature JSON은 저장하지 않고 요청 시 메모리에서 생성한다.

- 구성: price, flow, breadth, alignment, liquidity, market environment, penalty, coverage
- 가격: 기준일, 3·5·10일 평균, 5·10일 변동성, 모멘텀 변화, 일별 횡단면 백분위
- 수급: 외국인·기관·합산·프로그램 강도, 합산 3·5일 평균, 가속도, 연속 방향, 주체 방향 일치
- 확산·집중: 가격 상승 비율, 합산 순매수 종목 비율, 상위 1·3개 종목 거래대금 집중도
- 기타: `calendar_gap_days`

결측은 0으로 변환하지 않는다. 기준일 `data_coverage_rate < 0.70` 행은 V1 학습과 추론에서 제외한다.

## 데이터 규모

현재 학습 결과:

- 원천 실측: 2024-06-04~2026-08-07, 530일, 2,471행, 38개 테마
- 학습 사용 기준일: 2026-02-03~2026-08-06
- distinct base dates: 124
- training rows: 1,176
- 사용 테마: 36
- coverage 기준 미달 제외: 1,228행
- 다음 관측일 label 없음 제외: 32행

최소 기준은 40일과 500행이다. 40~79일은 EXPERIMENTAL, 80일 이상은 일반 SHADOW 후보로 취급한다.

## 모델과 Walk-forward

- Ridge: median imputer + missing indicator + StandardScaler + Ridge(alpha=10)
- HGBR: median imputer + missing indicator + HistGradientBoostingRegressor(max_iter=200, learning_rate=0.05, max_depth=3, L2=1)
- 초기 training target dates 40개, 이후 10~20개 날짜 단위 validation을 추가하는 expanding window
- 현재 validation fold: 6개

선택 순서는 NDCG@5 내림차순, Precision@5 내림차순, MAE 오름차순이며 동률이면 Ridge를 우선한다.

## 실제 Walk-forward 결과

| 모델 | MAE | RMSE | 방향 | P@3 | P@5 | P@10 | Spearman | NDCG@5 | 평균 순위오차 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| BASELINE | 7.3663 | 9.5464 | 43.73% | 65.87% | 70.95% | 76.79% | -0.0104 | 0.5776 | 8.5787 |
| RULE | 5.3529 | 6.9301 | 39.21% | 65.08% | 70.00% | 77.86% | -0.0446 | 0.5614 | 8.4750 |
| RIDGE | 6.2282 | 8.1499 | 34.78% | 65.48% | 70.24% | 77.38% | 0.0042 | 0.5740 | 8.6428 |
| HGBR | 5.7692 | 7.3083 | 38.08% | 64.68% | 70.48% | 76.43% | -0.0680 | 0.5656 | 8.7710 |

Ridge는 ML 후보 중 NDCG@5가 가장 높아 선택됐다. MAE는 RULE보다 나쁘고 NDCG@5는 RULE보다 높으므로 공식 반영 근거가 없으며 SHADOW를 유지한다.

## Registry와 artifact

`market_theme_return_prediction_models`에는 모델 버전, 기간, 데이터 수, validation 집계 지표와 artifact 경로만 저장한다. artifact는 `backend/model_artifacts/theme_return_prediction/`에 joblib로 저장하고 Git에서 제외한다. 재학습은 새 버전을 만들며 기존 SHADOW를 RETIRED로 바꾼다.

현재 활성 모델:

- `ML-RIDGE-V1-20260808-02`
- feature `THEME_RETURN_FEATURE_V1`
- sklearn 1.9.0
- status `SHADOW`

## Shadow 추론과 격리

정상 예측은 RULE을 먼저 커밋한 다음 ML을 별도 시도한다. artifact 없음, 버전 불일치, 추론 오류가 발생해도 RULE 응답은 성공한다. Shadow 전용 API는 기존 run의 기준일을 사용하고 ML item만 Upsert하며 `revision_count`, 최초/최종 RULE 예측 시각과 공식 item을 수정하지 않는다. artifact는 모델 버전별 메모리 캐시를 사용하며 활성 버전이 바뀌면 재로드한다.

## 검증과 UI

기존 RULE metrics는 유지하고 `market_theme_return_prediction_method_metrics`에 BASELINE/RULE/ML별 집계값을 비파괴적으로 저장한다. ML item도 같은 실제값으로 Gap·순위·방향·기준 효과를 평가한다. 누적 비교는 ML과 RULE이 모두 있는 공통 run만 사용하며 5일 미만은 `실전 비교 데이터 부족`, 20일 이상은 `운영 승격 검토 가능` 상태만 표시한다.

화면 기본 카드·그래프·순위와 D+1은 계속 공식 RULE이다. 상단에 ML 상태와 수동 학습 버튼, 접힌 RULE/ML 비교표, 검증 후 BASELINE/RULE/ML 지표표를 추가한다. 학습 실패 시 기존 예측 화면을 유지한다.

## 재학습과 Phase3

자동 스케줄은 없다. 약 20거래일 추가 또는 월 1회 수동 재학습을 권장한다. 자동 승격·앙상블·GPT·딥러닝·외부 boosting 의존성은 제외한다. Phase3에서는 동일 실전 run이 최소 20일 이상 축적되고 ML의 순위와 오차 개선이 반복 확인된 뒤 RULE+ML 앙상블을 검토한다.
