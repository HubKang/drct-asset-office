# DrCT 종목 시그널 Phase 6-C.1 — Signal UX 및 성능 개선

## 범위와 불변 조건

Phase 6-C.1은 현재 종목 시그널의 표시 밀도와 상세 Drawer 응답성을 개선한다. Universe, 공통 기준일, S-only Signature, CORE Feature V1 16개, Robust Signature V1, LOO P25 후보 기준, 유사도 계산식과 Marker-relative 정렬은 Phase 6-C와 동일하다. Search Rule, F 사례, Outcome 계열 지표는 계산에 사용하지 않으며 Scan·상세·차트 결과는 DB나 브라우저 영구 저장소에 저장하지 않는다.

운영 데이터 재검증 결과는 기준일 `2026-09-04`, Universe 199개, 평가 가능 187개, 불완전 12개, eligible Marker 4개, 후보 종목 142개, 후보 pair 224개다. 전체 Scan은 SQL 4회이며 측정값은 약 449ms였다.

## 후보 목록 UX

- 후보 패널을 바깥쪽 2열 카드 그리드로 구성했다. 넓은 화면의 카드 내부 비율은 종목/테마/감지 Marker/대표 유사도/유사 수준을 `17:20:37:11:15`로 배치한다.
- 1280px 이하에서도 2열을 유지하면서 각 카드를 2단으로 재배치한다. 620px 이하에서만 1열로 전환한다.
- 카드 높이는 넓은 화면 58px이며, 좁은 카드형 화면은 최소 112px이다. 실제 900px viewport에서는 내용 줄바꿈을 포함해 132px로 표시됐다.
- 감지 Marker는 Primary Marker 한 개와 `+N`으로 단순화한다. `+N`의 tooltip 및 접근성 이름에는 나머지 Marker와 유사도를 제공한다.
- Primary Marker는 서버가 제공하는 Marker-relative 정렬의 첫 항목이며 Marker 그룹 색상을 점으로 표시한다. 대표 유사도와 유사 수준도 Primary Marker 기준이다.
- 별도 화살표 열을 제거했다. 카드 전체를 마우스로 클릭하거나 포커스 후 Enter/Space를 눌러 Drawer를 연다.
- 마커 그룹과 종목명/종목코드 검색은 클라이언트 필터로 즉시 적용된다.
- 전체 분석 시간과 SQL 횟수는 평상시에는 `ⓘ 분석정보` tooltip에만 표시한다.

## 상세 Drawer 및 요청 정책

Drawer shell, 종목명, 코드, 테마, 선택 Marker와 Scan 응답에 이미 포함된 대표 유사도·유사 수준은 클릭 직후 표시한다. Marker 상세와 차트는 서로 독립적으로 병렬 요청하며 각각 전용 skeleton을 사용한다. 차트 영역 높이를 고정해 늦게 도착해도 레이아웃이 흔들리지 않는다.

상세 API는 전체 199종목 Scan을 다시 실행하지 않는다. 선택 종목/Marker 메타데이터, S-only 학습 사례, 필요한 종목 가격만 조회하는 SQL 3회 경로로 분리했다. 차트 API는 `after=0`인 현재 Drawer 요청에서 D0와 이전 60봉을 SQL 1회로 조회하며 Marker event overlay는 별도 SQL 1회다.

React 메모리 cache와 in-flight Promise cache를 각각 상세(`analysisDate:stockId:markerId`)와 차트(`analysisDate:stockId:60:0`)에 적용했다. 동일 요청은 합쳐지고 최신 요청만 화면 상태를 갱신한다. 같은 종목에서 Marker를 바꿀 때는 상세만 전환하며 OHLCV 차트와 event overlay를 다시 요청하거나 remount하지 않는다. cache는 새로고침 시 사라지며 localStorage, sessionStorage, IndexedDB는 사용하지 않는다.

## 성능 측정

동일 PC의 로컬 개발 서버와 운영 SQLite를 사용했다. Browser 값에는 자동화 입력의 약 0.3초 제어 지연이 포함되므로 API/서비스 시간과 함께 해석한다.

| 종목 | 개선 전 cold 완료 | 개선 후 cold 완료 | 개선 후 warm 완료 | 개선 후 Detail service |
|---|---:|---:|---:|---:|
| LG에너지솔루션 | 1,605ms | 424ms | 388ms | 20.2ms |
| JW중외제약 | 1,368ms | 389ms | 365ms | 19.3ms |
| KB금융 | 1,466ms | 378ms | 369ms | 17.2ms |

개선 전 직접 HTTP 측정에서 Detail은 LG에너지솔루션 1,336ms, JW중외제약 562ms, KB금융 537ms였고 Chart는 각각 24ms, 12ms, 13ms였다. 병목은 차트가 아니라 Detail API의 전체 Universe 재스캔이었다. 개선 후 전용 Detail service는 세 종목 모두 약 17~21ms, SQL 3회로 확인됐다.

## 검증 체크리스트

- Phase 6-C 및 Chart Marker 집중 테스트: 29개 통과.
- 전체 Backend: 502개 통과, 기존 데이터/테스트 fixture 관련 15개 실패. 이번 변경 범위의 신규 실패는 없다.
- Frontend TypeScript/Vite production build: 통과.
- Python `compileall`: 통과.
- 1920px/1440px/900px Browser 확인: 모두 2열, 가로 overflow 없음. Enter/Space 열기 및 Marker 전환 시 차트 DOM 유지 확인.
- Browser console: runtime error 없음. 기존 React Router v7 future flag warning 2개만 확인.
- 운영 Scan 집계와 계산 정책: 유지.
- DB schema 및 영구 저장 동작: 변경 없음.
- 기존 경고: 깨진 legacy CSS selector 7개와 500kB 초과 bundle 경고가 유지된다.
