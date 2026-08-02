# 시장테마 가격·수급 수집 1.1단계: 라우트 및 pilot 검증

## 404 원인과 최종 URL

저장소 코드의 FastAPI OpenAPI에는 신규 라우트가 정상 등록되어 있었고 프런트 호출 경로도 일치했다. 오류 당시 `http://127.0.0.1:8000/openapi.json`을 직접 조회한 결과 실행 중인 서버에는 `returns-and-flows` 라우트가 없었다. 백엔드 프로세스가 1단계 변경 전 코드를 계속 실행한 것이 `{"detail":"Not Found"}` 응답의 직접 원인이다.

애플리케이션에는 전역 `/api` prefix가 없고 `routes_external_kiwoom.router`가 `main.py`에 추가 prefix 없이 포함된다. 프런트는 `VITE_API_BASE_URL`(기본값 `http://127.0.0.1:8000`) 뒤에 아래 경로를 붙인다.

- 작업 생성: `POST /external/kiwoom/market-themes/returns-and-flows/jobs`
- 작업 조회: `GET /external/kiwoom/market-themes/returns-and-flows/jobs/{job_id}`
- 동기 호환 API: `POST /external/kiwoom/market-themes/returns-and-flows/refresh`

Vite proxy/rewrite는 사용하지 않는다. 따라서 개발·운영 환경 모두 `VITE_API_BASE_URL`이 실제 FastAPI 서버를 가리켜야 하며, 백엔드 코드 변경 후 서버를 재시작해야 한다.

## 작업 생성과 polling

작업 생성 응답은 `job_id`, `status`, `message`, `requested_at`을 반환한다. 상태 응답에는 기존 호환 필드와 함께 현재 단계/한글 단계명, 대상·완료·실패 종목 수, 단계별 집계, 시작·종료 시각, 오류 및 실패 목록을 명시적으로 반환한다.

프런트는 POST가 성공하기 전에는 “작업을 요청하고 있습니다”만 표시한다. `job_id` 확인 후 1초 polling을 시작하며 `COMPLETED`, `PARTIAL`, `FAILED`, 404 또는 화면 해제 시 중단한다. 404·409·서버/네트워크 오류는 원시 FastAPI 문자열 대신 한국어 안내로 변환한다.

## pilot 사용 방법

기본 요청은 `mode=FULL`이며 기존처럼 전체 활성 테마 연결 고유 종목을 처리한다. 관리용 API 호출에서만 `PILOT`을 지정한다. pilot 대상은 반드시 현재 활성 테마 연결 종목이어야 하며 최대 20개로 제한된다.

```json
{
  "scope": "all_active",
  "mode": "PILOT",
  "pilot_stock_codes": ["005930", "000660"],
  "max_stocks": 2
}
```

종목코드 대신 `pilot_stock_ids`를 사용할 수 있다. 특정 종목을 지정하지 않고 `max_stocks`만 주면 활성 연결 고유 종목의 안정적인 조회 순서에서 앞의 N개를 처리한다. 결과의 `collection_mode`와 `processed_stock_codes`로 실제 대상을 확인한다.

## 부분 upsert

`stock_investor_flows`는 `(stock_id, flow_date)` 한 행을 공유한다. 모든 개인·외국인·기관·프로그램 필드는 새 값이 `NULL`일 때 기존 값을 유지하도록 upsert한다. 다음 두 순서를 모두 격리 DB 테스트로 확인했다.

1. ka10059 투자자 저장 후 ka90013 프로그램 저장
2. ka90013 프로그램 저장 후 ka10059 투자자 저장

수량과 금액이 모두 보존되고 동일 날짜에는 한 행만 남는다. 미수집 값은 0으로 변환하지 않는다.

## 운영 검증 순서

1. 서버 재시작 후 `/openapi.json`에서 신규 3개 경로 확인
2. mock 처리로 POST/GET/404/409 계약 확인
3. 실제 Kiwoom 1개 종목 pilot
4. KOSPI·KOSDAQ·관심종목을 포함한 3개 pilot
5. 10개 pilot을 두 번 실행해 overlap/upsert, 호출 제한, 부분 실패, DB 증가량 확인
6. 결과 검토 후 사용자 판단으로 전체 수집 실행

Codex 검증에서는 실제 Kiwoom pilot이나 전체 145개 수집을 자동 실행하지 않는다.

## 제한사항

작업 레지스트리와 잠금은 단일 프로세스 메모리에 있다. 서버 reload 또는 재시작 시 완료되지 않은 상태 정보가 사라지며, 다중 worker에서는 POST와 GET이 서로 다른 프로세스로 전달될 수 있다. 현재는 단일 worker로 운영하고 향후 DB 또는 Redis 기반 작업 상태로 전환해야 한다.
