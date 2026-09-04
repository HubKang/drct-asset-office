# DrCT 종목 시그널 Phase 6-A

## 1. 변경 이유와 역할 분리

Search Rule은 수치 조건을 정확히 만족하는 종목을 찾는 기계적 탐지 도구다. Chart Marker는 사용자가 차트 형태를 보고 특정 패턴으로 판단한 Pattern Label이다. 사용자가 D+1/D+2를 본 뒤 Marker를 확정할 수 있으므로 Marker D0가 Search Rule을 만족해야 한다는 전제를 폐기했다.

- Search: 현재 종목 탐지와 Marker 사례 대비 차이를 연구하는 Reference
- Marker: Pattern Dataset의 최상위 기준
- Search ↔ Marker Link: 학습 Gate가 아닌 참고 관계
- Pattern Dataset: CORE Feature가 준비된 S + F + 미판정 사례
- Quality Dataset: CORE Feature가 준비된 S + F 사례

## 2. Marker Training Case

기본 키는 `(marker_id, stock_id, marker_date)`이며 실제 Event 식별을 위해 `chart_marker_event_id`를 유지한다. 운영 DB 조사 결과 이 조합의 중복 Event는 0건이며 DB Unique 제약도 존재한다. Event를 임의 삭제·병합하지 않는다. Marker Dataset Service는 Event 한 건을 Case 한 건으로 취급한다.

`MarkerTrainingCaseService`는 `marker_id`만 입력받아 Marker Event, D0 가격, CORE/ENRICHED Feature, Future Outcome을 런타임 구성한다. Search ID, Search Version, Rule Engine을 import하거나 호출하지 않는다.

## 3. S/F 코드 정책과 Migration

저장 Code는 `S`, `F`, `NULL`만 허용한다. 읽기 경계에서는 구버전 Fixture와 전환 중 데이터를 위해 `SUCCESS→S`, `FAILURE→F`를 정규화한다. 신규 API Write Schema는 legacy Code를 거부한다.

Migration 전 백업:

`db/backups/drct_asset_pre_phase6a_20260902.sqlite3`

| Code | 전 | 후 |
|---|---:|---:|
| SUCCESS → S | 92 | 92 |
| FAILURE → F | 42 | 42 |
| NULL | 13 | 13 |
| 합계 | 147 | 147 |

Event ID, Stock, Marker, Marker Date는 유지했고 `PRAGMA integrity_check` 결과는 `ok`다. SQLite Table을 재구성해 DB CHECK도 `S/F/NULL`만 허용한다. 신규 Table은 없다.

## 4. Feature와 Leakage 정책

기존 Feature Schema V1을 의미 변경 없이 재사용한다.

- CORE: 기존 16개
- ENRICHED: CORE + 기존 기술지표 4개, 총 20개
- Feature Cutoff: `trade_date <= Marker D0`
- D+1/D+2: Pattern Label 확정 과정에는 사용할 수 있으나 Feature에는 포함하지 않음
- D+5/D+10/D+20/MFE/MAE: Outcome으로만 분리
- 미래 가격을 극단값으로 변경해도 CORE Feature가 동일한지 자동 테스트

Feature Matrix, Pattern/Quality Dataset JSON, Outcome 분석, Signature, Model, Score는 DB에 저장하지 않는다.

## 5. Runtime API

- `GET /drct-stock-signals/marker-learning/markers`
- `GET /drct-stock-signals/marker-learning/{marker_id}/readiness`
- `POST /drct-stock-signals/marker-learning/{marker_id}/dataset-preview`
- `GET /drct-stock-signals/marker-learning/{marker_id}/cases?review_result=ALL|S|F|UNDECIDED`
- `GET /drct-stock-signals/marker-learning/{marker_id}/cases/{event_id}`
- `GET /drct-stock-signals/marker-learning/{marker_id}/outcomes`
- `GET /drct-stock-signals/marker-learning/{marker_id}/related-searches`

목록/준비 API는 Aggregate와 상태만 반환한다. 전체 Feature는 Case Detail에서만 반환한다.

## 6. 화면 구조

기존 상위 Tab 안에 Local Secondary Navigation을 추가했다.

- 검색식 관리: HTS, Version, 현재 탐지, Rule Diagnose와 mismatch 연구 유지
- 차트마커 학습: Marker Group/Marker 선택, Summary, 학습 준비, 사례, S/F 검증, 관련 검색식

Marker 학습 Checklist와 Funnel에는 Rule Match가 없다. 관련 검색식이 0개이거나 Rule이 미구성/INVALID/NO_MATCH여도 Dataset을 생성한다. Search 화면의 Marker 표현도 `연결 마커`에서 `관련 차트마커`로 바꿨다.

## 7. 운영 DB 실제 Marker 결과

| Marker | Event | S | F | 미판정 | D0 가격 | CORE | ENRICHED | D+20 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 이평조정 5선 | 17 | 4 | 12 | 1 | 17 | 13 | 10 | 16 |
| 이평조정 10선 | 9 | 4 | 5 | 0 | 9 | 7 | 5 | 8 |
| 이평조정 20선 | 10 | 7 | 3 | 0 | 10 | 6 | 6 | 10 |
| 이평조정 60선 | 2 | 2 | 0 | 0 | 2 | 2 | 1 | 2 |

Pattern Case 수는 각각 13, 7, 6, 2이며 Quality Case 수는 12, 7, 6, 2다. Quality Case는 Review S/F이면서 CORE가 준비된 사례만 포함하므로 단순 S+F Event 수와 다를 수 있다.

## 8. Phase 6-B 사전 조사

- 활성 Marker: 25개
- Event 보유 Marker: 22개
- 전체 Event: 147개
- 현재 Runtime Dataset 전 Marker 일괄 구성 측정: 약 237ms(개발 PC, 모델 연산 제외)
- D-20~D0 가격 Shape 가용: 5선 16/17, 10선 9/9, 20선 10/10, 60선 2/2
- 같은 기간 MA5/10/20/60 Shape 가용: 5선 10/17, 10선 6/9, 20선 6/10, 60선 1/2
- 같은 기간 거래량 Shape 가용: 5선 16/17, 10선 9/9, 20선 10/10, 60선 2/2
- 네 Marker의 현재 CORE Ready Dataset에서 IQR=0 Feature: 모두 0개

Phase 6-B에서는 Marker별 Median/IQR 기반 Signature, 소표본 Marker 처리, Leave-One-Out 또는 Time-based OOS, 학습 분포 기반 Threshold를 설계한다. 이번 Phase에서는 Pattern Score, Signature, Threshold, Universe Scan을 구현하지 않았다. 기존 Prototype의 Feature 표준화·Median/IQR·시간순 OOS 유틸리티는 재사용 후보이나 호출 연결은 하지 않았다.

## 9. 완료 보고

1. 구현 내용: Marker 중심 Runtime Dataset, S/F 표준화, 신규 Workspace를 구현했다.
2. 학습 방향 변경: Search Rule Gate에서 Marker Pattern/Quality Dataset으로 전환했다.
3. Marker Training Case 정의: Marker Event 단위이며 Event ID를 유지한다.
4. Pattern Label: Marker가 기록된 사실이며 S/F/미판정을 모두 포함한다.
5. Quality Label: 복기 S/F이며 미판정은 제외한다.
6. S/F Code 변경: 저장 Code를 S/F/NULL로 표준화했다.
7. Migration 방식: 백업 후 Transactional Table rebuild와 UPDATE 정규화를 수행했다.
8. Migration 전/후 Count: 92/42/13이 동일하게 보존됐다.
9. 신규 저장 Validation: S/F/NULL 외 Pydantic 및 DB CHECK에서 차단한다.
10. 기존 차트마커 화면 회귀: 성공/실패 한글 UI, 필터, 집계, 복기 API를 유지한다.
11. Marker Dataset 생성 방식: marker_id로 Event·D0 과거 가격·지표·Outcome을 bulk 구성한다.
12. Search Rule Gate 제거: 신규 Service는 Search/Rule parameter와 호출이 없다.
13. MarkerTrainingCaseService 구조: Catalog, Build, Summary, Cases, Detail, Outcomes, Reference 책임을 분리했다.
14. CORE Feature 재사용: Schema V1 16개를 그대로 사용한다.
15. ENRICHED Feature 재사용: Schema V1 20개를 그대로 사용한다.
16. D0 Cutoff 정책: D0 포함 과거 데이터만 Feature에 입력한다.
17. D+1/D+2 Leakage 방지: 미래값 변경 불변성 테스트를 추가했다.
18. Future Outcome: D+5/10/20/MFE/MAE를 Feature와 분리해 계산한다.
19. Search ↔ Marker Link 새 의미: 관련 검색식 Reference다.
20. 신규/변경 API: Marker Learning API 7개와 기존 Chart Marker S/F Write를 변경했다.
21. 화면 구조 변경: 검색식 관리/차트마커 학습 Secondary Navigation을 추가했다.
22. 검색식 관리 영역: 기존 기능을 유지하고 학습 표현을 검증/Reference로 정리했다.
23. 차트마커 학습 영역: Group/Marker 선택과 네 연구 Sub Tab을 제공한다.
24. Marker 학습 Readiness: Marker, D0, CORE, ENRICHED, S/F, Outcome만 사용한다.
25. Marker 사례 화면: 전체/S/F/미판정 Filter와 상세 Feature/Outcome Modal을 제공한다.
26. S/F Outcome 화면: 평균, Median, n, 평균 차이를 제공한다.
27. 관련 검색식 UI: 0건이어도 정상 Dataset 안내를 표시한다.
28. 이평조정 5선 실제 데이터: 위 표의 17/4/12/1/13/10/16이다.
29. 이평조정 10선 실제 데이터: 9/4/5/0/7/5/8이다.
30. 이평조정 20선 실제 데이터: 10/7/3/0/6/6/10이다.
31. 이평조정 60선 실제 데이터: 2/2/0/0/2/1/2다.
32. 신규 DB Table 여부: 없다.
33. Feature Matrix 비저장 확인: 전후 Table Count 테스트로 확인했다.
34. Backend Test: 신규 S/F, 독립성, 누수, Filter, Outcome 테스트를 포함한다.
35. DrCT 전체 회귀 Test: 관련 138개가 통과했다.
36. Frontend Build: TypeScript/Vite production build가 통과했다.
37. git diff --check: 오류 없이 통과했다.
38. 1920×900: 가로 Overflow 없음.
39. 1440px: 가로 Overflow 없음.
40. 900px: 반응형 전환 및 가로 Overflow 없음.
41. 기존 기능 영향: Search/HTS/Rule/현재 탐지/Marker 기록·복기 계산 의미를 유지했다.
42. 기존 경고: 기존 손상 CSS selector와 bundle size, React Router future flag 경고만 유지된다.

