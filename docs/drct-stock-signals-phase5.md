# DrCT 종목 시그널 Phase 5

## 목적

Model Registry를 먼저 만들면 잘못 구성된 Rule, 임의 Marker 연결, 낮은 데이터 가용률을 모델 문제로 오해할 수 있다. Phase 5는 사용자가 저장한 VALID Structured Rule과 직접 선택한 Marker Link만으로 실제 데이터를 처음부터 끝까지 통과시키고, 운영 모델로 승격하기 전에 데이터·Rule·Baseline 품질을 확인하는 단계다. Model Registry, ACTIVE Model, 종목 추천, 확률 Calibration, 운영 Signal 저장은 구현하지 않는다.

## Readiness와 사용자 설정

전체 Overview는 등록 검색식, Rule VALID, Marker 연결, Dataset Ready, Baseline 가능 수를 Runtime 집계한다. 검색식별 Checklist는 HTS 참조식, Rule VALID, Marker 연결, Reviewed Case, Rule Match Case, CORE Ready, ENRICHED Ready를 표시한다. Search Lifecycle과 연구 준비 상태는 독립적이다.

Rule Builder에서 사용자가 VALID Rule을 저장하고 Marker 연결 관리에서 Marker를 직접 선택해야 한다. HTS 원문의 잘린 조건을 추측하거나 이름 유사도로 Marker를 자동 연결하지 않는다. 미구성 검색식은 `NOT_READY`다.

연구 상태는 `NOT_READY`, `DATA_TOO_SMALL`, `RULE_REVIEW_NEEDED`, `BASELINE_TESTABLE`을 사용한다. Metrics만으로 `BASELINE_PROMISING` 또는 운영 승격을 자동 선언하지 않는다.

## Dataset 품질 Gate

모든 분모가 0이면 0%가 아니라 NULL이다.

- Reviewed Coverage = Reviewed Dedup Case / Linked Dedup Case
- Rule Match Rate = RULE_MATCH / Rule Evaluable
- CORE Coverage = CORE Ready / RULE_MATCH
- ENRICHED Coverage = ENRICHED Ready / RULE_MATCH
- D+20 Coverage = D+20 Available / Reviewed RULE_MATCH

Warning 상수는 Rule Match 70%, CORE 80%, ENRICHED 60%, D+20 70%다. 이는 자동 차단이나 모델 승인 기준이 아니라 점검 안내다. SUCCESS/FAILURE 최소 조건만 기존 Baseline 실행을 차단한다.

RULE_NO_MATCH는 실패 Condition과 함께 별도 사례로 반환한다. `RULE_DATA_INCOMPLETE`, CORE 누락, ENRICHED 누락도 Pattern 불일치와 섞지 않고 별도 목록으로 제공한다. 사례를 열면 기존 Case Detail의 Rule Diagnose, Feature, Outcome을 재사용한다.

## Label과 Outcome 비교

Label 분포는 Rule Match + 선택 Feature Profile Ready 사례의 SUCCESS/FAILURE 수와 “관찰된 SUCCESS 비율”을 표시한다. 이 비율은 예측 확률이 아니다.

SUCCESS와 FAILURE별 D+5, D+10, D+20, MFE20, MAE20의 평균·중앙값·표본 n을 계산하고 평균 차이도 제공한다. 최근 사례처럼 미래봉이 부족하면 해당 값은 NULL이며 n에서 제외한다. Outcome은 Feature 입력에 포함되지 않는다.

## Prototype Out-of-Sample 검증

날짜 오름차순 Expanding Validation을 사용한다. 이전 날짜의 SUCCESS가 5건 이상일 때만 Success median/IQR Prototype을 만들고 다음 날짜 Batch를 평가한다. 같은 D0 사례는 서로 Training에 들어가지 않는다. FAILURE가 이전 학습 구간에 5건 이상이면 기존 Failure Contrast를 적용한다. 결과 `prototype_score`는 Runtime 전용 “성공패턴 점수”이며 확률이 아니다.

## Logistic SHADOW 검증

기존 L2 Logistic Expanding Window를 재사용한다. 각 Training Window 안에서만 Scaling을 fit하고 다음 날짜 Batch에 `shadow_score`를 생성한다. Accuracy, Precision, Recall, ROC AUC, Brier Score는 계산 가능한 경우에만 제공하며 단일 Class 등 계산 불가능한 값은 NULL이다. Window별 coefficient 방향 전환 횟수도 연구 참고용으로 계산한다.

## Score Bucket과 관계 분석

Prototype과 Logistic SHADOW Score는 `0~59`, `60~69`, `70~79`, `80~89`, `90~100` Bucket으로 집계한다. 각 Bucket은 n, 관찰된 SUCCESS 비율, D+20 평균/중앙값, MFE 평균, MAE 평균을 제공한다. 이는 Out-of-Sample 관측 집계이며 Probability Calibration이 아니다.

두 방식 모두 평가된 동일 `(stock_id, D0)` 사례만 맞춰 Pearson과 Spearman 상관관계를 계산한다. 고득점 FAILURE와 저득점 SUCCESS는 “모델 불일치 사례”로 분리해 Feature 개선 후보로 사용한다.

## Feature 연구

선택 Profile의 Feature별 SUCCESS median, FAILURE median, 차이, 각 IQR을 제공한다. 전체 Feature Matrix는 응답하지 않는다. Dataset 내부에서 `|correlation| >= 0.90`인 Feature Pair를 최대 30개까지 연구 참고용으로 표시하지만 자동 제거하지 않으며 Feature Schema V1 의미도 변경하지 않는다.

## API와 재현성

- `GET /drct-stock-signals/searches/training-overview`
- `POST /drct-stock-signals/searches/{id}/validation-report`

Validation Report는 `search_id`, `search_version_id`, Version, Rule Schema, Feature Schema, Feature Profile, Dataset 최신 D0인 `data_cutoff`, UTC `generated_at`, Training/Evaluated Case 수를 포함한다. Cutoff 인자는 향후 추가할 수 있도록 Dataset Build와 분석 책임을 분리했다.

Dataset, Feature Matrix, Prototype/SHADOW Score, Outcome 비교, Bucket, Correlation, Coefficient, Metrics, 불일치 사례는 모두 Runtime 결과이며 DB에 저장하지 않는다.

## 현재 실데이터 결과와 다음 단계 Gate

2026-09-01 현재 운영 검색식 3개는 모두 v1, Structured Rule 미구성, Marker Link 0건이다. 따라서 Rule VALID 0, Marker 연결 0, Dataset Ready 0, Baseline 가능 0이며 모두 `NOT_READY`다. 각 Validation Report는 SQL 2회, 0~1ms 수준이고 전체 Overview는 SQL 7회다. 가짜 Dataset이나 자동 설정은 만들지 않았다.

Phase 6 Model Registry에 들어가려면 최소 한 검색식에서 VALID Rule, Marker Link, Reviewed SUCCESS/FAILURE가 연결되어 Dataset Ready가 되어야 한다. 이어서 Rule Match Rate, Outcome 구분, Prototype 또는 Logistic OOS 결과, Score Bucket과 Outcome 관계를 실제 값으로 확인해야 한다. 충족하지 못하면 Rule 개선, Marker 사례 추가 수집, Feature Schema V2 연구 중 하나를 먼저 선택한다.
