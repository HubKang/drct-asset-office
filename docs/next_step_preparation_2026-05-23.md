# Next Step Preparation (2026-05-23)

## 목적
- `DEVELOPMENT_HANDOFF_SUMMARY_2026-05-21.md` 기준 현재 안정화 상태를 확인하고, 다음 개발 사이클을 시작하기 위한 실행 준비를 완료한다.

## 현재 상태 요약
- 조건검색은 **비저장 preview**가 운영 기본 경로다.
- 저장은 사용자가 선택한 종목만 `market_trend_events`로 수행한다.
- 일별 테마 수급 흐름 API/화면은 구현 완료 상태이며, 실호출 및 체감 E2E 검증 1회가 권장된다.
- 운영 원칙(주문 API 미구현, 자동매매 표현 금지, 키 직접노출 금지)은 유지되어야 한다.

## 즉시 실행 순서 (권장)
1. 백엔드/프론트 재기동
2. `theme-flow` API 실호출 점검
3. 브라우저 수동 E2E 체크리스트 1회 수행
4. 발견 이슈 우선순위 분류(P1/P2/P3)
5. 필요한 UI 미세조정 또는 인코딩 정리 정책 수립

## 실행 체크리스트

### A. 서버 상태 확인
- 백엔드 기동 후 헬스체크 확인
- 프론트 기동 후 시장 트랜드 분석 화면 진입 확인
- 인증/토큰 관련 오류 로그 미발생 확인

### B. API 스모크 테스트
- `GET /external/kiwoom/theme-flow/daily?trade_date=YYYY-MM-DD`
  - 정상: 테마 카드 집계 데이터 반환
  - 비정상: 빈 배열/5xx 시 백엔드 로그 확인
- `GET /external/kiwoom/theme-flow/daily/{market_theme_id}/stocks?trade_date=YYYY-MM-DD`
  - 정상: 선택 테마 상세 종목 반환
  - 비정상: `market_theme_id` 유효성 및 DB 데이터 확인
- `POST /external/kiwoom/conditions/{condition_seq}/preview`
  - 정상: 결과 미리보기 반환, DB 누적 저장 없음
- `POST /external/kiwoom/market-events`
  - 정상: 체크 종목만 저장/upsert

### C. 수동 E2E 시나리오
1. 조건식 선택 후 preview 조회
2. 결과 정렬(등락률/거래량/거래대금) 확인
3. 2개 이상 종목 체크 후 저장
4. 저장 후보 패널에서 메모 저장/삭제 확인
5. 동일 이벤트에 다중 테마 연결/해제 확인
6. 일별 테마 탭에서 카드 클릭 -> 상세 종목 로딩 확인
7. 네이버 차트 로딩 실패 fallback/확대 동작 확인

### D. 데이터 정책 검증
- preview 반복 호출 시 `kiwoom_condition_result_items` 증가 없음 확인
- 저장 시 `market_trend_events`만 반영되는지 확인
- soft delete(`is_active`, `deleted_at`) 정상 반영 확인
- 테마 링크 중복 생성 없이 재활성 처리 확인

## 완료 기준 (Definition of Done)
- API 스모크 테스트 전 항목 통과
- 수동 E2E 시나리오 전 항목 통과
- P1 이슈 0건
- 발견된 P2/P3는 이슈 목록에 재현 절차와 영향 범위 기록

## 다음 개발 태스크 후보
1. 로딩/에러 상태 메시지 문구 정교화 (사용자 체감 개선)
2. 인코딩 깨짐 legacy 데이터 정리 정책 문서화
3. 수동 E2E 체크리스트를 간단한 테스트 스크립트로 반자동화

