# DrCT에셋 개발 요약 인수인계 (2026-05-21)

## 1) 전체 진행 요약
- 27단계: Kiwoom REST/WebSocket 연동 기반 구축 완료
  - `ka10171` 조건검색 목록조회 성공
  - `ka10172` 조건검색 일반조회 성공
  - LOGIN → ACK → 요청 순서 이슈(100013) 해결
- 28-A ~ 28-E: 시장 트랜드 분석 화면 운영형 UI/UX 정리 및 실사용 흐름 안정화
  - 조건검색 수급 이벤트 탭
  - 일별 테마 수급 흐름 탭

## 2) 핵심 아키텍처 전환 (중요)
### 기존
- 조건검색 결과 조회 시 DB(`kiwoom_condition_result_items`)에 누적 저장

### 현재(28-C 이후)
- **조건검색 결과 조회는 비저장 preview**
- 화면에서 조회한 결과는 상태(state)에만 존재
- 사용자가 체크한 종목만 `market_trend_events`로 저장
- `kiwoom_condition_result_items`는 legacy/cache/debug 용도로 유지

## 3) 현재 동작 플로우
1. 조건식 선택
2. `POST /external/kiwoom/conditions/{condition_seq}/preview` 호출(비저장)
3. 결과 테이블 표시 및 정렬/체크
4. 선택 종목만 `POST /external/kiwoom/market-events` 저장
5. 하단 저장 후보 목록에서 메모/삭제/테마 연결 관리
6. 일별 테마 수급 흐름 탭에서 카드 집계/상세 차트 확인

## 4) 백엔드 주요 API 상태
### 조건검색
- `GET /external/kiwoom/conditions`
- `POST /external/kiwoom/conditions/{condition_seq}/preview`  ← 운영 기본
- `POST /external/kiwoom/conditions/{condition_seq}/results` (legacy)
- `GET /external/kiwoom/conditions/{condition_seq}/results` (legacy)

### 수급 이벤트 후보
- `POST /external/kiwoom/market-events`
- `GET /external/kiwoom/market-events?trade_date=YYYY-MM-DD`
- `PATCH /external/kiwoom/market-events/{event_id}`
- `DELETE /external/kiwoom/market-events/{event_id}` (soft delete)

### 다중 테마 연결
- `GET /external/kiwoom/market-events/{event_id}/themes`
- `POST /external/kiwoom/market-events/{event_id}/themes`
- `DELETE /external/kiwoom/market-events/{event_id}/themes/{link_id}`

### 일별 테마 수급 흐름 (28-D)
- `GET /external/kiwoom/theme-flow/daily?trade_date=YYYY-MM-DD`
- `GET /external/kiwoom/theme-flow/daily/{market_theme_id}/stocks?trade_date=YYYY-MM-DD`

## 5) 에이전트(kiwoom-rest-agent) 상태
- `run_condition_once.py`에 `--json-output` 추가
- 백엔드는 subprocess(`shell=False`, timeout 적용)로 agent 실행 후 JSON summary 파싱
- `--send-drct` 없이 실행 시 DB 저장 없음(비저장 preview 지원)

## 6) 프론트엔드 주요 완료 사항
### 조건검색 수급 이벤트 탭
- 목록 row 클릭 선택, 정렬
- 결과 테이블 정렬(등락률/거래량/거래대금(추정) 포함)
- 결과 체크 후 저장
- 숫자 컬럼 우측 정렬
- 거래대금(추정) 억 단위 표시

### 저장된 수급 이벤트 후보 패널
- 날짜 input + 조회 버튼
- 메모 저장, row 삭제
- 다중 테마 추가/해제
- 최근 UI 정리:
  - `미연결` 텍스트 제거
  - 테마 선택 위 공백 제거
  - 메모 저장/삭제 버튼 가로 배치

### 일별 테마 수급 흐름 탭
- 상단 테마 카드(종목수/이벤트수/평균·최고 등락률/대표 종목)
- 카드 클릭 시 하단 상세 종목
- 네이버 차트(1주/3개월/1년)
- 이미지 로딩 실패 시 대체 박스
- 이미지 클릭 확대(2.5배), 재클릭 닫기

## 7) DB/데이터 정책
- `market_trend_events`: 운영 저장 핵심 테이블
- `market_trend_event_theme_links`: event-테마 다중 연결 테이블
- soft delete 정책 사용(`is_active`, `deleted_at`)
- 테마 추가는 대체가 아닌 누적 연결

## 8) 확인된 검증 포인트
- preview 반복 조회 시 `kiwoom_condition_result_items` count 변화 없음
- 선택 저장 시 `market_trend_events`만 upsert
- 다중 테마 연결 시 중복 생성 없이 재활성/갱신
- build/compileall/db_health 최근 성공

## 9) 남은/주의 이슈
- 일부 과거 데이터/문자열 인코딩 깨짐 흔적 존재(legacy 데이터)
- 브라우저 수동 E2E 최종 체감 검증은 별도 1회 권장
- 신규 테마 생성 후 즉시 연결 UI는 현재 제거된 상태(기존 테마 연결 중심)

## 10) 금지/운영 원칙 유지 사항
- 주문 API 미구현
- 자동 매수/매도/추천 표현 금지
- APP KEY/SECRET/TOKEN 원문 미노출
- 프론트에서 키움 직접 호출 금지(백엔드/agent 경유)
- `stock_loop`, `pykiwoom` 삭제 없음

## 11) 다음 채팅창에서 바로 시작 추천 순서
1. backend 재기동 후 `/external/kiwoom/theme-flow/daily` 및 `/stocks` 실호출 점검
2. 브라우저 수동 E2E 체크리스트 1회 실행
3. 필요 시 UI 미세조정(간격/문구/로딩 상태)
4. 인코딩 깨짐 데이터 정리 정책 수립(선택)
