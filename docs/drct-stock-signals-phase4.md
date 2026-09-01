# DrCT 종목 시그널 Phase 4

## 범위와 원칙

Phase 4는 검색식 Version별 차트 패턴 학습 Dataset과 연구용 Baseline을 런타임에 생성한다. 최종 종목 추천, 운영 시그널 필터, Lifecycle 자동 변경, 확률 Calibration, Model Registry는 포함하지 않는다. Local LLM도 사용하지 않는다. 현재 핵심은 자연어 설명이 아니라 Dataset 품질, 시점 정합성, 누수 방지, SUCCESS/FAILURE 분리 가능성 검증이기 때문이다.

Feature Matrix, 종목별 Feature JSON, OHLCV Window, 분석 중간 결과, Prototype, Logistic 모델과 Metrics는 DB에 저장하지 않는다. 목록 API는 명시적인 집계 필드만 반환하고 Feature는 단일 사례 상세에서만 런타임으로 제공한다.

## Training Case와 Label

Dataset Key는 `(search_id, search_version_id)`이며 과거 Version과 현재 Version을 섞지 않는다. Training Case Key는 `(search_id, search_version_id, stock_id, marker_date)`다. 연결된 복수 Marker Event가 같은 종목과 D0를 가리키면 하나로 합치고 `source_marker_event_ids`는 요청 처리 중에만 유지한다.

Label 병합은 다음과 같다.

- SUCCESS + SUCCESS → SUCCESS
- FAILURE + FAILURE → FAILURE
- SUCCESS + FAILURE → CONFLICT
- SUCCESS + NULL → SUCCESS
- FAILURE + NULL → FAILURE
- NULL만 존재 → UNDECIDED

CONFLICT와 UNDECIDED는 Baseline에서 제외한다. Market Outcome으로 Human Label을 다시 만들지 않는다.

## D0 Rule 재검증과 Funnel

각 Case는 `analysis_date = marker_date`로 Search Version의 Structured Rule을 다시 평가한다. D0 이후 행은 Rule 조회에 전달하지 않는다. 상태는 `RULE_MATCH`, `RULE_NO_MATCH`, `RULE_DATA_INCOMPLETE`, `RULE_NOT_CONFIGURED`로 구분한다. Rule이 없거나 Marker Link가 없으면 각각 `RULE_NOT_CONFIGURED`, `NO_MARKER_LINK`로 Dataset 생성을 차단하며 자동 Rule 생성과 자동 Marker 연결은 하지 않는다.

화면과 API는 연결 이벤트, 복기 완료, 종목/일자 중복 제거, Rule 평가 가능, Rule Match, CORE/ENRICHED Ready, Baseline 가능 건수를 런타임 집계한다. 미판정, Label 충돌, Rule 불일치, Rule 데이터 부족, 가격봉 부족, 기술지표 부족도 별도 집계한다. Rule Match Rate는 `Rule Matched / Rule Evaluable`이며 분모가 0이면 NULL이다.

## Feature Schema V1

`feature_schema_version = 1`이며 모든 Feature는 먼저 `trade_date <= D0`로 자른 데이터에서 계산한다. 미래 행까지 계산한 뒤 slice하지 않는다. 누락값은 0이나 평균으로 대체하지 않는다.

CORE는 D0 포함 61거래봉을 요구하며 16개 Feature를 사용한다.

- `price_return_{5,10,20,60} = (D0 close / D-n close - 1) × 100`
- `drawdown_from_high_{20,60} = (D0 close / 기간 high 최대값 - 1) × 100`
- `position_in_range_{20,60} = (D0 close - 기간 low 최소값) / (기간 high 최대값 - 기간 low 최소값) × 100`
- `price_slope_{20,60}`: 각 close를 `close / D0 close × 100`으로 정규화한 뒤 거래봉 순서에 대한 단순 회귀 기울기
- `ma{5,10,20,60}_gap_pct = (D0 close / D0 MA - 1) × 100`
- `volume_vs_ma20 = D0 volume / 최근 20봉 volume 평균`
- `volume_5_20_ratio = 최근 5봉 volume 평균 / 최근 20봉 volume 평균`

ENRICHED는 CORE 16개에 다음 4개를 더한 20개다.

- `rsi14`
- `macd_histogram_pct = D0 macd_histogram / D0 close × 100`
- `bb_width`
- `atr14_ratio_to_close`

현재 기술지표 가용률과 Feature 수 상한을 고려해 변화량 및 중복 MA/MACD Feature는 V1에서 제외했다. CORE 필수값 누락은 `CORE_DATA_INCOMPLETE`, 기술지표 또는 ENRICHED 필수값 누락은 `ENRICHED_DATA_INCOMPLETE`다. ENRICHED가 불가해도 CORE가 준비되면 CORE Dataset에는 포함한다.

## Future Outcome

Outcome은 Feature와 분리하며 학습 입력에 사용하지 않는다.

- `D+n return = (D+n 거래봉 close / D0 close - 1) × 100`, n은 5, 10, 20
- `MFE20 = (D0 이후 20거래봉 high 최대값 / D0 close - 1) × 100`
- `MAE20 = (D0 이후 20거래봉 low 최소값 / D0 close - 1) × 100`

필요한 미래봉이 부족하면 해당 Outcome과 Coverage를 NULL/미가용으로 처리한다. SUCCESS와 FAILURE별 실제 평균과 Coverage를 별도로 반환한다.

## Baseline

Success Prototype은 SUCCESS가 5건 이상일 때 준비된다. SUCCESS 집합의 Feature별 median과 IQR로 `|x - median| / IQR` 거리를 구하고, IQR이 0인 Feature는 거리 결합에서 제외한다. 동일 가중치 평균 거리 `d`에 대해 `success_similarity = 100 / (1 + d)`다. FAILURE가 5건 이상이면 FAILURE 중심도 같은 방식으로 구해 `score = clamp(success_similarity + 0.25 × (success_similarity - failure_similarity), 0, 100)`으로 보정한다. 결과 명칭은 “성공패턴 점수”이며 확률이 아니다.

Logistic SHADOW는 SUCCESS 5건, FAILURE 5건, 전체 15건 이상일 때 L2 정규화 Logistic Regression을 실행한다. 별도 대형 의존성을 추가하지 않고 NumPy로 deterministic gradient descent를 구현했다. 날짜 오름차순 Expanding Window를 사용하며 같은 D0의 사례는 하나의 Test Batch로 묶는다. 각 Window의 평균과 표준편차는 Training 행에만 fit하고 Test Batch에는 transform만 한다. 초기 양쪽 Label 5건을 확보하기 전 사례는 `INITIAL_TRAINING_WINDOW`로 평가에서 제외한다.

평가가 가능하면 Accuracy, Precision, Recall, ROC AUC, Brier Score를 반환한다. 계산 불가능한 Metric은 0이 아니라 NULL이다. 화면에서는 “SHADOW Score”로만 부르며 상승 확률/성공 확률로 표현하지 않는다. Coefficient는 확정 중요도가 아니라 “성공/실패 구분에 기여한 Feature 후보”다.

AUTO Profile은 ENRICHED가 Logistic 최소 조건을 만족하면 ENRICHED, 아니면 CORE를 선택한다. 둘 다 부족하면 각 Baseline이 `INSUFFICIENT_DATA`를 반환한다.

## API

- `GET /drct-stock-signals/searches/{search_id}/training-readiness`
- `POST /drct-stock-signals/searches/{search_id}/training-dataset-preview`
- `GET /drct-stock-signals/searches/{search_id}/training-cases`
- `GET /drct-stock-signals/searches/{search_id}/training-cases/{stock_id}/{d0}`
- `POST /drct-stock-signals/searches/{search_id}/baseline-evaluate`

## 운영 데이터 확인과 성능

2026-09-01 확인 시 기존 3개 검색식은 모두 v1, Structured Rule 미구성, Marker Link 0건이다. 따라서 세 검색식 모두 실제 학습 가능 사례, Rule Match, CORE Ready, ENRICHED Ready가 0이고 Outcome 비교와 Baseline Metrics는 제공할 수 없다. 운영 데이터를 임의 변경하거나 가짜 수치를 만들지 않았다. 차단된 첫 검색식 Preview는 4ms, SQL 2회였다. 구성된 통합 Fixture의 전체 Preview는 SQL 7회 이하로 검증했다. 이벤트·가격·기술지표는 bulk 조회하고 Event별 N+1 조회를 하지 않는다.

## 다음 단계 조사

Model Registry의 최소 Metadata 후보는 `search_version_id`, `model_version`, `feature_schema_version`, `feature_profile`, `algorithm`, `training_cutoff`, `training_count`, `validation_metrics`, `status`다. 모델 Artifact는 SQLite Blob보다 배포 시 원자적 교체와 checksum 검증이 가능한 파일 저장소가 적합하며 DB에는 경로·checksum·Metadata만 두는 방안을 검토한다. Current Rule Preview 후보에는 Rule Match와 SHADOW Score를 분리해 런타임 결합하고, 최종 화면에서도 “Rule 충족”과 “연구 점수”를 별도 열로 표현해야 한다.

충분한 Out-of-Sample 결과가 누적되면 Score 60/70/80 이상 구간별 SUCCESS 비율·D+20·MFE·MAE, Prototype/Logistic Score 상관관계, 검색식별 Prototype/Logistic 가능 여부를 조사한다. Phase 5에서 Model Registry, Artifact 정책, ACTIVE Model 승인 흐름, Calibration 여부를 별도로 설계한다.
