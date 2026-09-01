# DrCT 종목 시그널 Phase 5-B 완료 보고

1. 구현 내용: HTS 텍스트의 결정론 변환 Preview, 한국어 검토·보완, Schema v2 저장, 현재 종목 탐지를 연결했다.
2. HTS Import 전체 Workflow: 현재 참조식 또는 붙여넣기 → 자동 변환 → Required 조건 검토 → VALID 확인 → 새 Version 저장 → 현재 종목 탐지 순서다.
3. Parser 구조: `DrctHtsImportService`의 독립 Template 함수 Registry가 정규화된 원문을 유형별로 처리한다. Preview는 DB에 저장하지 않는다.
4. Rule Schema 변경 여부: 한 소스 조건이 여러 Predicate를 가질 수 있는 Schema v2를 추가했다. 새 Table은 없다.
5. v1 / v2 호환 방식: Validator, durable allow-list, lookback 계산, Evaluator가 schema version을 분기한다. v1 의미는 유지했다.
6. 지원 HTS Condition 유형: 시가총액, 가격 범위, 이평 배열·추세·비교·돌파·이격, 가격 연쇄 비교, 가격 등락률, 가격/이평 비교, 기간 내 등락률·거래대금이다.
7. 한국어 Condition UI: 일반 화면에는 한국어 제목·설명·상태·실제값만 표시하고 내부 Type/Operator는 `기술 상세 보기`에만 둔다.
8. NEEDS_CONFIRMATION 처리: 관계, 누락 가격 종류, 거래대금 임계값을 선택/입력한 뒤 서버에서 전체를 다시 결정론 변환한다.
9. UNSUPPORTED 처리: 원문을 보존하고 Required이면 저장을 차단한다. 임의 추정하지 않는다.
10. Boolean Expression 처리: A/B/C 코드를 보존하고 AND/OR/괄호를 RPN으로 검증한다. 3상태 평가에서 결정 가능한 AND/OR 결과를 데이터 부족이 가리지 않는다.
11. Search Version 저장 방식: `READY`와 `VALID`를 모두 확인한 후 기존 Version을 보존하고 새 Current Version에 allow-list Rule JSON만 저장한다. 기본 메모는 `HTS 참조식 DrCT 자동 변환`이다.
12. 기존 3개 검색식 Parser 실제 결과:
    - 쌍바닥 추세 전환 패턴: 전체 14, 자동 12, 확인 2, 미지원 0, Required 미완성으로 NEEDS_REVIEW. Required E 보완 시 READY/VALID.
    - 이평조정_5선, 10선, 20선, 60선: 전체 11, 자동 8, 확인 3, 미지원 0, NEEDS_REVIEW. F/I/K 보완 시 READY/VALID.
    - Dr.CT 눌림목: 전체 8, 자동 7, 확인 1, 미지원 0, NEEDS_REVIEW. C 보완 시 READY/VALID.
13. 확인 필요 실제 원문: 쌍바닥 E의 마지막 가격 종류, 미사용 J의 잘린 이평 관계, 이평조정 F/I/K의 잘린 이평 관계, 눌림목 C의 잘린 거래대금 임계값이다.
14. 현재 종목 탐지 방식: 기존 Rule Preview 실행 경로를 재사용하고 기본 응답은 검색식 포착 종목만 노출한다.
15. 분석 기준일 결정 방식: 활성 국내 테마 Universe 각 종목의 최신 완료 거래일 중 공통으로 안전한 최소 날짜를 사용한다.
16. 현재 Universe 수: 검증 시점 활성 국내 테마 연결 고유 종목 196개다.
17. Runtime 탐지 성능: 임시 보완 Rule smoke test 기준 128ms였다. 이 값은 환경과 데이터량에 따라 달라진다.
18. 주요 SQL Query 수: 비저장 Runtime smoke test 4개였다.
19. Kiwoom API 미사용 확인: Parser와 현재 탐지 경로에서 Kiwoom API 및 HTS 검색 결과를 호출하지 않는다.
20. 탐지 결과 비저장 확인: 실행 전후 `drct_signal_search_rules` 0 → 0이며 탐지 상세/차트 시리즈를 저장하지 않았다.
21. 신규 DB Table 여부: 없음.
22. Backend Test: Phase 5-B 전용 46개 통과.
23. 기존 DrCT 회귀 Test: 관련 전체 103개 통과(Phase 5-B 46개 포함).
24. Frontend Build: TypeScript 및 Vite production build 통과. 기존 malformed selector 및 chunk size 경고는 남아 있다.
25. git diff --check: 공백 오류 없음. 기존 줄바꿈 경고와 권한 제한된 pytest 임시 캐시 경고만 확인됐다.
26. 1920px / 900px UI 확인: 너비 1920, 높이 900, 가로 overflow 없음. 모달 내부 스크롤, 검토 상태, 보완 후 READY, 저장 버튼 활성화를 확인했다.
27. 기존 기능 영향 여부: 기존 Kiwoom 검색, 테마, 매매훈련, 마커, 복기, 가격/지표, Phase 4/5 흐름은 변경하지 않았다.
28. 다음 사용자 작업: 이평조정 검색식에서 실제 HTS 원문을 확인하여 F/I/K 관계를 보완하고 VALID Rule 저장 → 현재 종목 탐지 → 포착 결과 육안 점검 → 마커 연결 → Phase 5 Validation Report 순으로 진행한다.

## 데이터 보존 준수

- Parser Preview, 변환 중간 상태, 현재 탐지 결과, 종목별 진단, 시세 Series는 저장하지 않는다.
- 저장 시 Rule JSON은 명시적 durable-field allow-list를 통과한다.
- 실제 검색식 Rule은 자동 생성하거나 자동 저장하지 않았다.
