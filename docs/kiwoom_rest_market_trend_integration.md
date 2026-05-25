# Kiwoom REST Market Trend Integration (27-C)

## 목적
- 키움 조건검색(WebSocket) 실연동 결과를 DrCT 시장 트랜드 후보 저장 흐름에 연결한다.
- 프론트는 DrCT Backend만 호출하고, 키움 API 호출은 kiwoom-rest-agent가 담당한다.

## 보안 원칙
- APP KEY/SECRET/TOKEN/계좌번호 원문 출력 금지
- 프론트엔드에서 키움 API 직접 호출 금지
- 주문 API 미구현(조회 전용)

## 종목코드 표준화
- 최종 저장코드: 6자리 숫자 `stock_code`
- 원본코드 보존: `stock_code_raw`
- 규칙:
1. 공백 제거
2. `_AL/_KS/_KQ` 등 접미사 제거
3. `A005930` 형태는 `A` 제거
4. 첫 6자리 숫자 사용
5. 실패 시 빈 문자열

## WebSocket 조건검색 구현
- 클라이언트: `kiwoom-rest-agent/app/ws_client.py`
- 조건목록: `run_condition_list.py` (trnm=`CNSRLST`, api_id=`ka10171`)
- 조건결과: `run_condition_once.py` (trnm=`CNSRREQ`, api_id=`ka10172`)
- raw/normalized 파일 저장 후 옵션(`--send-drct`)으로 DrCT 전송

## Agent -> DrCT 전송 구조
- 조건목록 동기화: `POST /external/kiwoom/conditions/sync`
- 조건결과 저장: `POST /external/kiwoom/conditions/{condition_seq}/results`
- 수급 이벤트 후보 저장: `POST /external/kiwoom/market-events`

## 저장 정책
- `kiwoom_condition_searches`: source+condition_seq upsert
- `kiwoom_condition_result_items`: condition_seq+stock_code+같은 날짜 기준 최신 upsert
- `market_trend_events`: 사용자가 선택 저장한 종목만 반영, 수동 테마/메모/상태 보존

## 화면 통합 구조
- `시장 트랜드 분석` > `키움 조건검색 수급 이벤트`
- 왼쪽: 저장된 조건식 목록 조회
- 오른쪽: 저장된 조건검색 결과 조회 + 선택 종목 수급 이벤트 후보 저장

## 정리 방향
- stock_loop/pykiwoom은 삭제하지 않고 유지
- 27-D에서 ka10028/거래대금상위 기반 후보 확장 검토

## 27-C-2 WebSocket LOGIN ACK 순서 고정 결과 (2026-05-21)
- 100013 원인 분석:
1. 기존 `login_mode=header` 경로에서 LOGIN 전문 없이 `CNSRLST`가 먼저 전송됨
2. 서버는 `로그인 인증이 들어오기 전에 다른 전문이 들어왔습니다 (100013)`로 응답
3. 결론: 네트워크 문제가 아니라 `LOGIN -> ACK -> CNSRLST` 순서 위반

- LOGIN 전문 선행 규칙:
1. 기본 조합을 `header_mode=auth-only`, `login_mode=message-token`으로 변경
2. WebSocket 연결 후 `{"trnm":"LOGIN","token":"{token}"}` 전송
3. LOGIN ACK(`trnm=LOGIN`) 수신/성공 확인 전에는 `CNSRLST` 전송 금지

- LOGIN ACK 응답 구조(성공 샘플):
1. `trnm`: `LOGIN`
2. `return_code`: `0`
3. `return_msg`: `""` (빈 문자열)
4. `sor_yn`: `"Y"`

- CNSRLST 응답 구조(성공 샘플):
1. `trnm`: `CNSRLST`
2. `return_code`: `0`
3. `return_msg`: `""`
4. `data`: `[[condition_seq, condition_name], ...]`

- 조건검색 목록 normalize 예시:
1. `{"condition_seq":"1","condition_name":"01. 500억+10%이상","source":"kiwoom_rest"}`
2. `{"condition_seq":"10","condition_name":"Signal_추세","source":"kiwoom_rest"}`

- 매트릭스 결과 요약:
1. 성공: `auth-only + message-token`, `none + message-token`, `full + message-token`
2. 실패: `auth-only + message-bearer` (LOGIN ACK `return_code=805004`, 토큰 형식 불일치)
3. 실패: `full + header` (LOGIN ACK 미수신 timeout)

- DrCT sync 결과:
1. `--send-drct` 성공 경로에서 실행 검증
2. 현재 환경은 `DRCT_API_ENABLED=false`라 실제 POST는 스킵됨
3. 실패 상태/빈 목록에서 sync 금지 규칙은 유지

- 다음 단계(ka10172):
1. 동일한 LOGIN ACK 선행 구조를 `CNSRREQ(ka10172)`에도 공통 적용
2. 조건식별 `condition_seq/condition_name` 단건/배치 실행기 분리
3. 응답 표준화(`stock_code`, `stock_code_raw`, `detected_at`) 고정 후 DrCT 결과 적재 검증

## 27-C-3 ka10172 조건검색 일반조회 결과 (2026-05-21)
- 구현 결과:
1. `run_condition_once.py`를 ka10172 실실행 스크립트로 보완
2. 기본값은 `header_mode=auth-only`, `login_mode=message-token`
3. `LOGIN -> ACK -> CNSRLST(warmup) -> CNSRREQ` 순서로 요청
4. `PING` 수신 시 동일 메시지 echo 처리로 세션 유지

- ka10172 요청 전문:
1. `{"trnm":"CNSRREQ","seq":"{condition_seq}","search_type":"0","stex_tp":"K","cont_yn":"N","next_key":""}`
2. `condition_name`은 요청에는 선택 필드로 포함 가능, 저장용 메타로도 유지

- ka10172 응답 raw 구조(실측):
1. `trnm`: `CNSRREQ`
2. `return_code`: `0`
3. `seq`, `cont_yn`, `next_key`
4. `data`: LIST[DICT], 주요 키 예시
: `9001`(종목코드), `302`(종목명), `10`(현재가), `12`(등락률), `13`(거래량)

- normalized 구조:
1. `condition_seq`, `condition_name`
2. `stock_code`(6자리 표준화), `stock_code_raw`
3. `stock_name`, `current_price`, `change_rate`, `intraday_change_rate`, `volume`, `trading_value`
4. `detected_at`, `source=kiwoom_rest`, `source_api=ka10172`, `raw_json`

- DrCT 전송 결과:
1. `condition_seq=1` 저장: `saved_count=35`, `skipped_count=0`
2. `condition_seq=10` 저장: `saved_count=11`, `skipped_count=0`
3. 실패 상태에서는 전송 금지, `item_count=0`이면 전송 스킵

- 조건식 결과 저장 정책 확인:
1. Backend `/external/kiwoom/conditions/{condition_seq}/results`는 `stock_code` 6자리 정규화 재적용
2. `stock_code_raw` 보존
3. `condition_seq + stock_code + detected_at(일자)` 기준 update/insert 처리
4. 조건검색 결과 저장은 `market_trend_events` 자동 반영 없이 별도 관리

- 운영 메모:
1. ka10172는 동일 접속에서 `CNSRLST` 선행(warmup) 후 `CNSRREQ`가 안정적으로 응답됨
2. 병렬 실행 시 websocket 충돌 가능성이 있어 단건 순차 실행 권장

## 27-C-4 단위 보정/검증 결과 (2026-05-21)
- ka10172 필드 단위 보정 규칙:
1. `current_price(10)`: 부호 제거 후 양수 정수 저장
2. `change_rate(12)`: 원문이 `10840` 형태로 오므로 `1000`으로 나눠 `%` 단위 저장
3. `change_rate_raw`: 원문 문자열을 별도 보존
4. `volume(13)`: 음수 금지 정수 저장
5. `trading_value`: ka10172에서 명확 필드 미확인 시 `null` 유지, 원문은 `raw_json` 보존

- change_rate 보정 전/후 예시:
1. `000011110` -> `11.11`
2. `000029940` -> `29.94`
3. legacy `5210.0` -> `5.21` (DB 보정 1건 적용)

- mapper/backend 보정:
1. agent mapper에서 ka10172 응답에 `clean_rate_from_milli_percent` 적용
2. backend 저장 시 방어 규칙 `if abs(change_rate) > 100: change_rate /= 1000`
3. backend 저장 시 `current_price` abs, `volume` non-negative int 보정

- stock_code 정비 dry-run:
1. 대상: `stock_code LIKE '%_%' OR LENGTH(stock_code)<>6`
2. 결과: `target_count=51`, `recoverable_count=51`, `unrecoverable_count=0`
3. `--apply`는 사용자 승인 전 미실행

- 재수집 결과:
1. `condition_seq=1` -> `item_count=38`, DrCT `saved_count=38`, `skipped_count=0`
2. `condition_seq=10` -> `item_count=10`, DrCT `saved_count=10`, `skipped_count=0`

- DB 검증:
1. 최신 `condition_seq in (1,10)` 데이터는 `stock_code` 6자리, `change_rate` 퍼센트 단위 저장 확인
2. `ABS(change_rate) > 100` -> `0건` 확인
3. 비정상 `stock_code`는 legacy 누적 `51건` 존재(모두 복구 가능, 미적용 상태)

- 화면 E2E 검증 상태:
1. backend API 및 DB 기준으로 오른쪽 패널 데이터 소스는 정상
2. 브라우저 자동화 런타임(`playwright`) 부재로 UI 클릭 기반 자동 E2E는 이번 세션에서 미완료
3. 프론트 빌드(`frontend/npm run build`) 성공으로 렌더링 빌드 무결성은 확인

## 27-C-5 stock_code 정비 적용 및 최종 점검 (2026-05-21)
- stock_code 정비 결과:
1. 정비 전 dry-run: `target_count=51`, `recoverable_count=51`, `unrecoverable_count=0`
2. `--apply` 실행: `updated_count=51`
3. 검증 쿼리 보정: `LIKE '%_%'`는 `_` 와일드카드 문제로 `instr(stock_code, '_') > 0` 기준 사용
4. 정비 후 abnormal_count: `0`

- change_rate 이상값 재검증:
1. `ABS(change_rate) > 100` 1건(legacy ka10172) 발견
2. ka10172 방어 보정으로 `/1000` 적용
3. 재검증 결과: `0건`

- 최신 재수집/동기화:
1. `run_condition_list.py --send-drct`: `condition_count=120`, sync `updated_count=120`, `total_count=120`
2. `run_condition_once.py --condition-seq 1 --send-drct`: `item_count=39`, `saved_count=39`, `skipped_count=0`
3. `run_condition_once.py --condition-seq 10 --send-drct`: `item_count=12`, `saved_count=12`, `skipped_count=0`
4. 최신 결과의 `stock_code` 6자리/`change_rate` 퍼센트 단위 확인

- Backend API 검증:
1. `GET /external/kiwoom/conditions` -> 200, `items=120`
2. `GET /external/kiwoom/conditions/1/results` -> 200, 샘플 `change_rate=10.3`, `stock_code=005380`
3. `GET /external/kiwoom/conditions/10/results` -> 200, 샘플 `change_rate=9.89`, `stock_code=061970`
4. `POST /external/kiwoom/market-events` -> 200, `saved_count=2`, `unmatched_count=0`

- 화면 E2E 상태:
1. backend/frontend 서버 및 API 응답은 정상
2. 자동 UI 브라우저 검증은 런타임 의존성(playwright) 부재로 재현 불가
3. 대체로 API/DB 저장 경로와 프런트 빌드 성공으로 기능 경로를 교차 검증함

## 28-A 시장 트랜드 화면 UI/UX 운영 안정화 (2026-05-21)
- 조건검색 목록 패널 개선:
1. `조건검색 목록 새로고침` 버튼 활성/유지
2. 안내 문구 추가: 원천 갱신은 `kiwoom-rest-agent` 실행 후 반영
3. `선택/활성/동기화 시각` 컬럼 제거
4. row 클릭으로 조건식 선택 (선택 행 강조)
5. 상단 좌우 레이아웃을 `420px + 1fr`로 조정

- 조건검색 결과 패널 개선:
1. 선택 조건식 아래 버튼 가로 배치
: `조건검색 결과 조회`, `선택 종목 수급 이벤트 후보 저장`
2. `원본코드`, `시가 대비 상승률`, `수집시각` 컬럼 제거
3. 핵심 컬럼만 유지
: 체크, 종목코드, 종목명, 현재가, 등락률, 거래량, 거래대금

- 저장된 수급 이벤트 후보 패널 개선:
1. 상단 2패널 아래 전체 폭으로 분리 배치
2. 표시 컬럼 정리
: 기준일, 종목코드, 종목명, 시장, 등락률, 테마 상태, 메모, 관리
3. `시가 대비 상승률` 표현 제거, `등락률`로 통일

- 테마 상태/메모 기록 기능:
1. 조회 API 추가: `GET /external/kiwoom/market-events?trade_date=...`
2. 수정 API 추가: `PATCH /external/kiwoom/market-events/{event_id}`
3. 프론트에서 `theme_status`, `user_memo` 편집 후 `기록 저장` 수행
4. 자동 수집 필드는 유지하고 수동 필드만 갱신

- 시각 포맷 원칙:
1. 화면 공통 포맷 함수 `formatDateTime` 추가
2. 포맷: `yyyy-mm-dd hh:mm:ss`
3. 값 없으면 `-`

- E2E 검증 결과:
1. backend API/DB 저장/프론트 빌드 기준 기능 경로 정상
2. `GET/PATCH /external/kiwoom/market-events` 실호출 성공
3. UI 클릭 자동 검증은 런타임(playwright) 부재로 미수행

## 28-B 수급 이벤트 후보 다중 테마 연결 및 사용성 보강 (2026-05-21)
- 조건검색 결과 패널:
1. 거래대금 컬럼을 `거래대금(추정)`으로 변경
2. 계산 규칙: `current_price * volume` (없으면 `trading_value`, 둘 다 없으면 `-`)
3. 컬럼 헤더 클릭 정렬 추가
: 종목코드, 종목명, 현재가, 등락률, 거래량, 거래대금(추정)
4. 정렬 후 체크 상태 유지 (`row key` 기반)

- 조건검색 목록 패널:
1. 컬럼 헤더 클릭 정렬 추가
: 조건식 번호(숫자), 조건식명(문자)
2. 정렬 후 선택된 조건식 유지

- 저장된 수급 이벤트 후보 패널:
1. 상단 필터에서 `기준일` 텍스트 라벨 제거 (날짜 입력 + 조회 버튼만 유지)
2. row 단위 삭제 추가
: `DELETE /external/kiwoom/market-events/{event_id}`
: soft delete (`is_active=0`, `deleted_at` 기록)
3. 메모 기록 저장 유지
: `PATCH /external/kiwoom/market-events/{event_id}`

- 다중 테마 연결 구조:
1. 신규 링크 테이블 도입
: `market_trend_event_theme_links`
: unique `(event_id, market_theme_id)`
: `is_active`, `deleted_at` 기반 soft delete
2. 기존 테마 유지 + 새 테마 추가 정책 적용
3. 중복 테마 추가 시 신규 insert 대신 재활성화/갱신

- 다중 테마 연결 API:
1. `GET /external/kiwoom/market-events/{event_id}/themes`
2. `POST /external/kiwoom/market-events/{event_id}/themes`
3. `DELETE /external/kiwoom/market-events/{event_id}/themes/{link_id}`

- 신규 테마 등록 후 연결:
1. 기존 `market-themes` 생성 API 재사용
2. 생성 직후 event theme link API로 추가 연결
3. 기존 연결 테마는 대체되지 않고 유지

- 검증:
1. `npm run build` 성공
2. `.venv\Scripts\python.exe -m compileall backend\app` 성공
3. `python scripts/check_db_health.py` 성공

## 28-C 조건검색 결과 비저장 preview 전환 (2026-05-21)
- 운영 정책 전환:
1. 조건검색 결과 조회는 장중 현황 확인용 `preview(비저장)`으로 전환
2. 조회 결과 전체는 DB(`kiwoom_condition_result_items`)에 저장하지 않음
3. 사용자가 체크해 저장한 종목만 `market_trend_events`에 저장

- Backend API:
1. `POST /external/kiwoom/conditions/{condition_seq}/preview` 추가
2. 내부적으로 `kiwoom-rest-agent/run_condition_once.py --json-output` 실행
3. `shell=False`, `timeout=90s` 적용
4. API 응답에는 민감정보/raw_messages 미포함

- Agent 실행:
1. `run_condition_once.py --json-output` 옵션 추가
2. 마지막 줄에 JSON summary 출력
3. `--send-drct` 없는 기본 실행은 DrCT DB 저장 없음

- Frontend 동작:
1. [조건검색 결과 조회] 버튼이 저장 조회 API 대신 preview API 호출
2. 성공 시 `조건검색 결과 N건을 조회했습니다. 저장할 종목을 선택하세요.`
3. 0건 시 `현재 조건검색 결과가 없습니다.`
4. 실패 시 Agent/키움 연결 점검 메시지 노출

- 데이터 저장 범위:
1. preview 반복 조회: `kiwoom_condition_result_items` count 변화 없음
2. 선택 저장 실행: `market_trend_events`만 저장/업데이트

- `kiwoom_condition_result_items` 지위:
legacy/cache/debug 용도로 유지(삭제하지 않음)

- 거래대금(추정) 규칙:
`estimated_trading_value = current_price * volume` (없으면 `-`)

- UX 구분:
1. 오른쪽 조건검색 결과: 임시 preview(비저장)
2. 하단 저장된 수급 이벤트 후보: DB 저장 대상

## 28-D 일별 테마 수급 흐름 카드/차트 화면 구현 (2026-05-21)
- 목적:
1. 조건검색 기반으로 저장된 수급 이벤트 후보를 `일별 테마 수급 흐름` 관점으로 조회
2. 상단 카드에서 테마별 집계, 하단에서 선택 테마 종목별 차트 참고 제공

- Backend API 추가:
1. `GET /external/kiwoom/theme-flow/daily?trade_date=YYYY-MM-DD`
2. `GET /external/kiwoom/theme-flow/daily/{market_theme_id}/stocks?trade_date=YYYY-MM-DD`

- 상단 테마 카드 집계 기준:
1. `market_trend_events` + `market_trend_event_theme_links` + `market_themes` 조인
2. 조건: `trade_date`, `detection_source='kiwoom_condition'`, `is_active=1`
3. 카드 값: `theme_name`, `stock_count(distinct)`, `event_count`, `avg_change_rate`, `max_change_rate`, `estimated_trading_value_sum`, `representative_stocks`

- 하단 상세 종목 기준:
1. 선택 테마 + 거래일 기준 종목 목록 반환
2. 종목코드 6자리 정규화
3. 같은 테마 내 동일 `stock_code` 중복 제거
4. 기본 정렬: 등락률 내림차순

- 네이버 차트 이미지 URL 규칙:
1. week: `https://ssl.pstatic.net/imgfinance/chart/item/area/week/{stock_code}.png?sidcode={Date.now}`
2. month3: `https://ssl.pstatic.net/imgfinance/chart/item/area/month3/{stock_code}.png?sidcode={Date.now}`
3. year: `https://ssl.pstatic.net/imgfinance/chart/item/area/year/{stock_code}.png?sidcode={Date.now}`

- 이미지 실패 처리:
1. `img onError` 처리
2. 실패 시 `차트 이미지 없음` 대체 박스 표시
3. `loading="lazy"` 적용

- 거래대금(추정) 합계 규칙:
1. `estimated_trading_value_sum`은 `market_trend_events.trading_value` 합계 사용
2. 저장 시 `trading_value`가 없으면 `current_price * volume` 추정값 저장

- 화면 UX:
1. 상단: 날짜 + 조회 + 테마 카드
2. 하단: 선택 테마 상세 종목(`테마명`, `종목명`, `1주일`, `3개월`, `1년`)
3. 빈 상태/로딩/에러 메시지 분리

- 향후 개선:
1. 테마 확산도(당일 신규 편입 비율)
2. 중복 조건 포착 수 표시
3. GPT 자문 패키지 연동 요약

## 28-E 시장 트랜드 분석 화면 실사용 흐름 점검 (2026-05-21)
- 점검 범위:
1. 조건검색 목록/preview 조회/선택 저장 흐름
2. 저장 후보 메모/삭제/테마 다중 연결
3. 일별 테마 수급 흐름 카드/상세 차트 API
4. DB 무결성/garbage 누적 방지

- preview 비저장 검증:
1. `kiwoom_condition_result_items` count: `55`
2. preview 3회 실행 후 count: `55` (변화 없음)
3. 정책 충족: 조회 전용, 비저장

- 수급 이벤트 후보 저장 검증:
1. preview 결과 2종목 저장 호출 시 `updated_count=2`, `unmatched_count=0`
2. 동일 재저장 시 `updated_count=2`로 upsert 동작 확인

- 저장 후보/테마 연결 검증:
1. 활성 event(`id=17`)에 `AI` + `전력` 계열 테마 연결 확인
2. 중복 `AI` 추가 시 link row 증식 없이 재활성/갱신 확인
3. 연결 해제 시 해당 링크만 비활성화, event 본문 유지 확인
4. 메모 patch 저장 후 재조회 유지 확인

- 일별 테마 흐름 검증:
1. 요약 API 결과 `summary_count=3`
2. 예시 상위 테마: `로봇` (stock_count=2, event_count=2)
3. 상세 API 결과 `detail_count=2`, 샘플 `066570 LG전자`

- 보안 점검:
1. frontend 코드에 키움 직접 URL 호출 없음
2. 민감 토큰 원문은 마스킹 상태 유지
3. 주문 API 호출 없음

- 한계/남은 확인:
1. 본 세션은 브라우저 수동 클릭 E2E 자동화 미수행
2. 따라서 최종 UX 체감(버튼 동선/메시지/차트 로딩)은 실제 브라우저에서 1회 수동 점검 필요
3. 현재 UI에서는 신규 테마 생성 입력을 제거한 상태이므로 "신규 테마 등록 후 연결"은 제외됨(기존 테마 추가 연결만 제공)

## 29 월별 테마 수급 흐름 탭 구현 (2026-05-23)
- 29단계 방향 전환:
1. Kiwoom REST 순위 API 확장 대신 `월별 테마 수급 흐름` 탭 구현으로 변경
2. 조회 전용 집계 기능이며 주문/자동매매 기능은 추가하지 않음

- 목적:
1. 저장된 수급 이벤트 후보(`market_trend_events`)와 테마 연결(`market_trend_event_theme_links`)을 월간 관점으로 조회
2. 상단 달력에 일별 테마 순위, 하단에 월간 흐름 라인 그래프 제공

- 신규 API:
1. `GET /external/kiwoom/theme-flow/monthly/calendar?month=YYYY-MM`
2. `GET /external/kiwoom/theme-flow/monthly/trend?month=YYYY-MM`

- 월 기준 기간 규칙:
1. `start_date`: 기준월 1일
2. 현재 월 선택 시 `end_date`: 오늘(한국시간)까지
3. 과거 월 선택 시 `end_date`: 해당 월 말일

- 달력형 일별 테마 순위 집계 기준:
1. 조인: `market_trend_events` + `market_trend_event_theme_links` + `market_themes`
2. 필터: 기간, `detection_source in ('kiwoom_condition','kiwoom_rest')`, `is_active=1`, `deleted_at` 미삭제
3. 산출:
: `stock_count`, `event_count`, `avg_change_rate`, `max_change_rate`, `estimated_trading_value_sum`
4. 일별 정렬:
: `stock_count DESC` -> `event_count DESC` -> `estimated_trading_value_sum DESC` -> `avg_change_rate DESC`
5. rank는 날짜별 1부터 부여

- 라인 그래프 기준:
1. y축 기본값: `stock_count`
2. x축: `start_date ~ end_date` calendar day
3. tooltip/보조정보용 필드: `event_count`, `avg_change_rate`, `estimated_trading_value_sum`

- 빈 날짜 0값 처리:
1. backend에서 날짜 구간 전체를 생성
2. 해당 테마 데이터가 없는 날짜는 `value=0`으로 채워 연속성 유지

- 향후 개선:
1. 거래일 기준 x축 전환
2. y축 지표 전환(`event_count`/`estimated_trading_value_sum`/`avg_change_rate`)
3. 전월 대비 증감 지표
4. GPT 자문 패키지 연동

## 29-B 일별 순위 확정 + 월별 누적 점수 전환 (2026-05-23)
- 일별 자동 순위 기준:
1. `avg_change_rate DESC`
2. 동률 보조: `stock_count DESC` -> `event_count DESC` -> `estimated_trading_value_sum DESC`

- 수동 순위 수정:
1. 신규 테이블 `daily_theme_flow_ranks` 도입
2. `trade_date + market_theme_id` 유니크
3. `manual_rank` 저장 시 `final_rank=manual_rank`, 미설정 시 `final_rank=auto_rank`

- 최종 순위 산정:
1. `manual_rank` 우선
2. 없으면 `auto_rank`
3. `rank_basis`: `manual|auto`

- 순위 점수(시장 관심도 기록용):
1. 1위 10점
2. 2위 8점
3. 3위 6점
4. 4위 4점
5. 5위 2점
6. 6위 이하 1점

- 월별 그래프 y축 변경:
1. 기존 `stock_count`
2. 변경 `순위 가중 누적 점수`

- 누적 점수 예시:
1. 5/01 1위 -> +10 (누적 10)
2. 5/02 미등장 -> +0 (누적 10)
3. 5/03 3위 -> +5 (누적 15)

- 지표 성격:
1. 투자 신호가 아니라 `테마 관심도 기록` 목적

- 향후 개선:
1. 가중치 사용자 설정
2. 평균등락률/거래대금/종목수 혼합 점수
3. GPT 자문 패키지 연동
