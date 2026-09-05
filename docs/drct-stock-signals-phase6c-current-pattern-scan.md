# DrCT 종목 시그널 Phase 6-C — Current Marker Pattern Scan

## 목적

Phase 6-C는 국내 활성 테마 연결종목의 최신 완료 차트를 과거 성공(S) Marker 패턴과 비교해 검증용 패턴 후보를 찾는다. 결과의 `current_pattern_similarity`는 성공확률이나 매수확률이 아니라 현재 CORE Feature와 S-only Marker Signature의 유사도다.

## Runtime pipeline

1. 활성 `THEME`과 활성 종목의 연결을 조회하고 `stock_id`로 중복 제거한다. 여러 테마명은 유지한다.
2. Universe가 공통으로 사용할 최신 완료 거래일을 결정한다.
3. 기준일 이하의 S Marker Event 중 manual `EXCLUDE`가 아닌 사례만 읽는다.
4. Universe와 학습사례에 필요한 가격 이력을 한 번에 Bulk 조회한다.
5. 기존 CORE Feature V1 16개, Robust Signature V1, LOO V1을 재사용한다.
6. CORE-ready S 사례가 5건 이상이고 LOO 분포가 생성되는 Marker만 Scan한다.
7. 현재 종목 Feature는 종목당 한 번 계산해 모든 eligible Marker에 재사용한다.
8. Marker별 P25 이상인 종목·Marker pair만 후보로 반환하고 종목 중심으로 묶는다.

## 계산 정책

- Feature distance: `abs(current - marker_median) / robust_scale`, 최대 3.0.
- Aggregate distance: 활성 Feature distance의 중앙값.
- Current similarity: `100 / (1 + aggregate_distance)`.
- Signature scale은 기존 `IQR → MAD → CONSTANT 제외` 정책을 유지한다.
- 학습 화면의 LOO 중앙값은 과거 S 사례끼리의 일관성이다. 종목 시그널의 Current similarity는 현재 종목과 전체 S Signature의 유사도이므로 서로 다른 값이다.
- 후보 Threshold는 Marker별 LOO P25이며 DB 설정으로 저장하지 않는 Candidate Policy V1 상수다.
- `P75 이상 = 매우 유사`, `Median 이상 = 높은 유사`, `P25 이상 = 유사`다.
- 동일 종목의 복수 Marker 후보를 모두 유지한다. 정렬은 Band, Marker-relative empirical percentile, similarity, 종목명 순이다.

## 독립성과 보존 정책

- Search Rule, Search Version, 관련 검색식은 조회하거나 계산에 사용하지 않는다.
- F, 미판정, D+5/10/20, MFE, MAE, Logistic은 조회하거나 계산에 사용하지 않는다.
- Scan 결과, Current similarity, Candidate band, Current Feature Matrix, Ranking은 DB·localStorage·sessionStorage·IndexedDB에 저장하지 않는다.
- API는 명시적인 aggregate 필드와 상위 차이 5개만 반환하며 16개 Feature 전체를 노출하지 않는다.
- Historical debug에서는 가격과 Marker Event 모두 `analysis_date` 이하로 제한한다. 수동 Decision의 당시 시점까지 완전 재현하는 Backtest Engine은 이 단계의 범위가 아니다.

## API와 SQL

- `POST /drct-stock-signals/marker-signals/scan`
- `GET /drct-stock-signals/marker-signals/{stock_id}/{marker_id}/detail?analysis_date=YYYY-MM-DD`
- 정상 Scan은 Universe, 공통 기준일, S-only Marker Event/Decision, 가격 이력의 고정 4 Query를 사용한다.
- 운영 DB Acceptance 기준 199종목, eligible Marker 4개에서 전체 Scan은 약 0.43초였으며 Signature 0.32초, Current Feature 0.04초, Similarity 0.02초였다. 환경과 데이터량에 따라 달라진다.

## 다음 Phase 조사

Phase 6-D에서는 Marker별 CORE-ready S/F 수와 균형, S/F Prototype 및 Logistic 최소 표본, Current Candidate의 S/F 상대거리, Pattern Similarity와 Quality Score의 분리 표시를 검토한다. Phase 6-C의 Marker-only 결과는 비교 가능한 Baseline으로 유지하며 Quality나 검색식 Reference를 이 점수에 혼합하지 않는다.
