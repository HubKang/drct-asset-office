# DrCT 종목 시그널 Phase 5-C

## 목적과 화면 구조

Phase 5-C는 검색식의 정의·Version 관리와 런타임 분석·학습 연구를 한 화면에서 명확히 분리한다. 상단 `검색식 정의`는 “무엇을 찾는 검색식인가”에만 답하고, 하단 `선택 검색식 분석 & 학습`은 현재 탐지와 학습 정합성에 답한다.

- 상단: 약 29:71 비율의 검색식 목록과 선택 검색식 정의, 최대 높이 430px
- 하단: `현재 탐지`, `학습 준비`, `검증 결과`, `사례 분석` 네 Sub Tab
- 기본 Sub Tab: `학습 준비`
- 긴 HTS 원문: 전체보기 Modal
- 한국어 조건 검토: 자동 변환 Modal, 내부 기술 구조는 접기
- 긴 사례 목록: 선택된 Sub Tab의 Panel 내부 Scroll

검색식 목록은 이름, lifecycle, Current Version, 검색조건 상태, Marker 수와 한 줄 학습 상태만 표시한다. SUCCESS/FAILURE와 상세 준비 수치는 하단으로 이동했다. Marker 연결도 검색식 정의가 아닌 학습 Dataset 구성 요소이므로 `학습 준비`로 이동했다.

## Progressive Disclosure

학습 준비는 `검색식 준비 → 학습 사례 → 데이터 검증` 세 단계와 `마커 → 연결 사례 → 복기 완료 → 평가 가능 → 검색조건 일치 → Feature 준비` Funnel로 단순화했다. Rule Match가 0이면 복기 Coverage와 검색조건 일치만 우선 표시하며 Feature/D+20은 안내 문구로 대체한다. Rule Match가 생긴 경우에만 기본·확장 Feature를 추가 표시한다.

검증 결과도 Rule Match가 0이면 빈 표를 길게 노출하지 않고 학습 준비 또는 불일치 분석으로 이동하는 Action을 제공한다. 현재 탐지 0건은 오류가 아니라 해당 기준일의 정상 결과이므로 중립 Empty State로 표시한다.

## Rule mismatch 분석

`GET /drct-stock-signals/searches/{id}/rule-mismatch-summary`는 선택 Version의 `RULE_NO_MATCH` 사례를 Marker D0에서 다시 평가해 Atomic Condition별 PASS, FAIL, 데이터 부족과 FAIL 비율을 런타임 집계한다. FAIL 비율은 `FAIL / 전체 불일치 사례`이며 높은 순으로 정렬된다. 이는 조건의 실패 빈도이지 최종 Rule 실패의 단일 인과 원인을 뜻하지 않는다.

현재 Boolean 식에서 추출할 수 있는 괄호 안 AND Branch도 기존 3상태 Boolean evaluator로 집계한다. Condition 행을 선택하면 기존 training-cases API의 `rule_status`와 `condition_code` Filter로 해당 FAIL 사례만 조회한다. 사례를 선택하면 Phase 3 Diagnose를 `analysis_date = Marker D0`로 재사용해 한국어 조건, 실제 값, 기준, 충족/미충족/데이터 부족을 보여준다.

## 이평조정 v3 실제 결과

전체 Rule No Match는 33건, Rule Data Incomplete는 4건이다.

| 조건 | evaluated | pass | fail | incomplete | fail rate |
|---|---:|---:|---:|---:|---:|
| C | 33 | 8 | 9 | 16 | 27.3% |
| D | 33 | 16 | 10 | 7 | 30.3% |
| E | 33 | 19 | 14 | 0 | 42.4% |
| F | 33 | 6 | 27 | 0 | 81.8% |
| H | 33 | 11 | 22 | 0 | 66.7% |
| I | 33 | 6 | 27 | 0 | 81.8% |
| J | 33 | 8 | 25 | 0 | 75.8% |
| K | 33 | 13 | 20 | 0 | 60.6% |
| L | 33 | 5 | 0 | 28 | 0.0% |

Branch 통과 결과:

- `E AND F`: 0 / 33
- `H AND I`: 2 / 33
- `J AND K`: 0 / 33

F와 I가 각각 81.8%로 가장 높은 실패 빈도를 보인다. 동시에 C/D/L에는 이동평균 이력 부족이 있고, 세 OR Branch 중 두 Branch는 통과 사례가 없다. 이 통계만으로 자동 변환 의미, Marker D0와 실제 포착 시점 차이, Marker 의미와 전체 검색식 의미의 차이 중 하나를 원인으로 단정하지 않는다.

## API와 저장 정책

- 신규: `GET /drct-stock-signals/searches/{id}/rule-mismatch-summary`
- 확장: `GET /drct-stock-signals/searches/{id}/training-cases`의 `rule_status`, `condition_code`, `label` Filter
- 확장: training case 응답의 allow-list 기반 `failed_conditions`
- 저장하지 않음: mismatch summary, Condition/Branch 통계, Filter 결과, 현재 탐지, 검증·시뮬레이션 상세
- 신규 DB Table 및 migration 없음

## 완료 검증 보고

1. 구현 내용: 상·하단 UX 재구성과 런타임 Rule mismatch Drill-down을 구현했다.
2. 화면 전체 구조 변경: 정의 영역과 분석·학습 영역을 분리했다.
3. 상단 검색식 정의 구성: 간소화 목록, compact header, HTS 요약, DrCT 실행 상태와 관리 Action으로 구성했다.
4. 하단 분석 & 학습 Sub Tab: 현재 탐지, 학습 준비, 검증 결과, 사례 분석 네 Tab을 구현했다.
5. Typography 변경: 주요 본문 12~13px, Sub Tab/Card 14px, Section 16px, Metric 18~20px 기준으로 정리했다.
6. 영어 Enum / 용어 정리: 일반 UI를 검색조건 일치, 데이터 부족, 기본/확장 Feature, 기본모델 검증 등 한국어 중심으로 변경했다.
7. HTS 참조식 표시 방식: 조건 수와 최종 식만 기본 노출하고 원문은 Modal에 표시한다.
8. 현재 종목 탐지 UX: 런타임 실행, compact metrics, 0건 중립 Empty State를 제공한다.
9. 학습 준비 UX: 세 단계 Checklist, 간소화 Funnel, Marker 연결, 불일치 Action을 한 화면에 배치했다.
10. Progressive Coverage 표시: Rule Match 0에서는 두 핵심 Coverage만 표시한다.
11. Rule mismatch Backend 구현: 기존 Dataset/Rule evaluator를 재사용하는 런타임 집계를 추가했다.
12. Condition별 Fail Summary 구조: code, label, evaluated/pass/fail/incomplete, fail_rate 구조다.
13. 이평조정 v3 실제 Condition 결과: 위 표와 같다.
14. OR Branch 분석 구현 여부: 구현했으며 E∧F 0/33, H∧I 2/33, J∧K 0/33이다.
15. Rule No Match 실제 사례 수: 33건이다.
16. Rule Data Incomplete 실제 사례 수: 4건이다.
17. 가장 Fail 비율이 높은 Condition: F와 I, 각 81.8%다.
18. Condition Filter Drill-down: Condition 행 선택 시 해당 조건 FAIL 사례만 표시한다.
19. Case Diagnose 재사용 방식: Marker D0를 analysis date로 Phase 3 Diagnose를 호출한다.
20. 신규/변경 API: mismatch summary 신규 1개, training-cases Filter 확장이다.
21. 저장 데이터 변경 여부: 없다.
22. 신규 DB Table 여부: 없다.
23. Backend Test: Phase 5-C 및 관련 테스트를 통과했다.
24. DrCT 관련 전체 회귀 Test: 지정된 Rule/Signal/Dataset/HTS 관련 116개가 통과했다.
25. Frontend Build: TypeScript 및 Vite production build가 통과했다.
26. git diff --check: 오류 없이 통과했다(LF/CRLF 안내만 존재).
27. 1920x900 검증: 가로 넘침 없이 상단 compact 및 하단 Tab 전환을 확인했다.
28. 1440px 검증: 가로 넘침이 없다.
29. 900px 검증: 1열 반응형 전환과 가로 넘침 없음을 확인했다.
30. 전체 페이지 Scroll 개선 결과: 정의 높이를 제한하고 한 Sub Tab만 렌더링하며 긴 목록은 Panel 내부 Scroll로 제한했다.
31. 기존 기능 영향 여부: 기존 HTS Parser, Rule Schema, Feature/모델 계산 의미와 타 메뉴는 변경하지 않았다.
32. 기존 경고: 기존 손상 CSS selector와 큰 bundle, React Router future flag 경고만 확인됐다.
33. Rule Match 0% 데이터 기반 해석: F/I 실패가 높고 OR Branch 통과가 매우 적으며 C/D/L에는 이력 부족이 함께 존재한다. 인과는 단정하지 않는다.
34. 다음 사용자 확인 사항: F/I/K의 자동 변환 의미, Marker D0와 실제 검색식 포착 시점, 연결 Marker가 전체 검색식을 의미하는지 사례별로 검토한다. 수정 후 Validation Report를 다시 실행하고 Phase 6 진입을 판단한다.

