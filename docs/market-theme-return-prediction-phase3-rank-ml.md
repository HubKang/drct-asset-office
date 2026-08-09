# 테마등락예측 Phase3 — 순위 목적 ML

## 목적과 운영 원칙

Phase3는 절대 등락률 회귀뿐 아니라 다음 대상일의 테마 간 상대 순위를 학습한다. 공식 예측은 계속 `RULE_V1`, `is_official=true`이며 ML은 하나의 수동 선택 Shadow만 운영한다. 후보 학습, Gate PASS, `ELIGIBLE_FOR_REVIEW`는 공식 승격을 의미하지 않는다.

Feature matrix, validation 행, fold별 샘플과 예측 원문은 메모리에서만 사용한다. DB에는 모델 Registry와 운영 판단에 필요한 집계 지표만 저장한다.

## Metric audit

Phase2의 P@5 약 70%와 NDCG@5 약 0.56~0.58은 초기 구간에 평가 가능 테마가 2~4개뿐인 날짜가 많았는데도 `min(K, group_size)`를 분모로 사용하고 NDCG를 계산한 영향으로 과대평가됐다.

`THEME_RETURN_METRIC_V2` 정책은 다음과 같다.

- 실제·예측 순위, Precision, Spearman, NDCG는 각 `target_date` 내부에서만 계산한다.
- P@K의 분모는 항상 K이며 평가 가능 테마가 K개 미만인 날짜는 P@K에서 제외한다.
- 날짜별 지표를 먼저 계산하고 유효 날짜의 단순 평균을 사용한다.
- RULE, ML, BASELINE은 같은 `target_date × theme_id` 교집합으로 평가한다.
- 등락률 동률은 `theme_id` 오름차순으로 결정한다.
- 평균 순위오차는 `abs(predicted_rank - actual_rank)`의 공통 표본 평균이다.
- 기존 Phase2 Registry 값은 수정하지 않고 Metric V2 신규 후보만 별도 저장한다.

실제 DB 재평가 기준 비교값은 다음과 같다.

| 기준 | MAE | P@5 | Spearman | NDCG@5 | 평균 순위오차 |
|---|---:|---:|---:|---:|---:|
| BASELINE | 7.3663 | 18.67% | -0.0104 | 0.1384 | 8.5787 |
| RULE | 5.3529 | 16.00% | -0.0446 | 0.1091 | 8.4750 |

## Target V2

- `RAW_RETURN`: 대상일 `avg_change_rate`.
- `RESIDUAL_RETURN`: 대상일 등락률 - 기준일 등락률. 추론 등락률은 기준일 등락률 + 예측 residual이다.
- `RANK_PERCENTILE`: 대상일별 내림차순 순위의 0~1 percentile. 가장 강한 테마가 1이다.
- `TOP5_CLASSIFICATION`: 대상일별 실제 Top5 여부. Top20% label도 같은 날짜 안에서 생성한다.
- `RANK_ENSEMBLE`: rank percentile, Top5 probability, residual-return rank의 고정 후보 조합이다.

Feature 생성과 label 생성은 분리한다. 모든 feature는 `base_date` 이하 자료로 먼저 생성하고, 그 다음 `target_date` actual을 붙인다.

## Feature V2

`THEME_RETURN_FEATURE_V1`의 이름과 의미를 그대로 유지하고 `THEME_RETURN_FEATURE_V2`를 추가했다.

- 기준일 횡단면 percentile: 3/5/10일 수익률, 외국인·기관·합산·프로그램 수급, 확산, 유동성, 집중도 역수
- 변화량: 3일-10일 수익률, 1일-5일 수익률, 3일-5일 수급, 확산·유동성 단기 변화
- 해석 가능한 interaction 5개
- 동일 기준일의 전체 테마 평균 대비 수익률·수급·유동성 상대값

결측은 0으로 강제하지 않고 fold 내부 median imputer가 처리한다. `data_coverage_rate < 0.70` 행은 모든 후보와 기준 모델에서 공통 제외한다.

## Walk-forward와 후보

124개 기준일, 1,176행, 36개 테마를 사용했다. 최초 40개 target date를 train으로 사용하고 이후 10~20개 날짜 단위의 expanding validation을 추가해 총 6개 fold를 만들었다. 모든 후보는 정확히 같은 fold와 행 순서를 사용한다.

비교 후보는 RAW Ridge/HGBR, Residual Ridge/HGBR, Rank Ridge/HGBR, Top5 Logistic/HGBC, Rank Ensemble이다. Logistic은 `class_weight=balanced`이며 초기 fold에 한 클래스만 존재하면 그 fold의 training prior를 반환한다. 외부 boosting, 자동 최적화와 자동 feature selection은 사용하지 않는다.

## Selection Gate

Gate A:

- NDCG@5 ≥ max(BASELINE, RULE) + 0.02
- P@5 ≥ max(BASELINE, RULE) - 0.02

Gate B:

- P@5 ≥ max(BASELINE, RULE) + 0.05
- NDCG@5 ≥ max(BASELINE, RULE)

공통 조건은 validation fold 절반 이상의 개선과 개선이 한 fold에 집중되지 않는 것이다. FAIL 모델은 `EXPERIMENTAL`로 저장되고 수동 Shadow 선택 API에서도 차단된다. 실제 실행에서는 9개 후보가 모두 FAIL이므로 기존 `ML-RIDGE-V1-20260808-02` Shadow를 유지했다.

## 실전 Gate, 공통 run, drift

RULE과 해당 Shadow model version의 method metrics가 모두 있는 run만 비교한다. 최근 5개는 추세, 최근 20개는 승격 검토, 전체는 누적 성과다.

- 공통 run < 20: `NOT_READY`
- 20개 이상이나 조건 미달: `OBSERVE`
- 최근 20개에서 ML NDCG와 P@5, 평균 순위오차가 RULE 조건을 충족하고 개선 날짜가 절반 이상이며 상위 3일에 개선이 70% 넘게 집중되지 않음: `ELIGIBLE_FOR_REVIEW`

Drift는 validation 대비 최근 20개 실전 NDCG 하락과 MAE 악화를 함께 본다. NDCG 0.05/0.10 하락 또는 MAE 10%/25% 악화를 WATCH/DEGRADED 기준으로 사용한다. 실전 표본이 없으면 WATCH이며 자동 재학습은 없다.

## Registry와 API

Registry 확장 필드는 `target_type`, `parent_model_version`, `selection_gate_status`, `selection_reason`, `shadow_selected_at`, `validation_improving_fold_count`, `metric_version`이다. 대형 JSON은 저장하지 않는다.

- `POST /market-themes/return-predictions/ml/train-rank-candidates`
- `POST /market-themes/return-predictions/ml/select-shadow`
- `GET /market-themes/return-predictions/ml/status`

수동 선택은 모델·artifact·Feature V2·Gate PASS를 확인하고 기존 Shadow를 RETIRED로 바꾼다. 일반 예측은 활성 Shadow 하나만 추론한다. Rank/Top5/Ensemble은 `predicted_change_rate=null`을 허용하고 `prediction_score`, `predicted_rank`, 선택적으로 `top5_probability`를 저장한다.

## 기존 run 보호와 Phase4 조건

2026-08-10 run id=1은 RULE 37개, 기존 Ridge ML 35개, revision 1을 그대로 유지한다. Phase3 연구 결과를 과거 공식 run에 삽입하거나 덮어쓰지 않는다.

Phase4 공식 RULE+ML 앙상블 검토는 최소 20개 공통 실전 run에서 `ELIGIBLE_FOR_REVIEW`가 확인되고 최근 구간 개선과 drift 안정성이 유지된 뒤 별도 승인으로만 진행한다.
