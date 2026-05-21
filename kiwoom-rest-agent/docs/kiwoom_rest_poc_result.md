# Kiwoom REST PoC Result (27-A)

## 1) 테스트 일시
- 작성 시각: 2026-05-21 (KST)

## 2) 사용 환경
- Agent 경로: `kiwoom-rest-agent/`
- Python: 로컬 실행 환경
- REST 환경: `KIWOOM_REST_ENV` 값 기반(prod/mock)

## 3) base_url
- `KIWOOM_REST_ENV=prod` -> `https://api.kiwoom.com`
- `KIWOOM_REST_ENV=mock` -> `https://mockapi.kiwoom.com`

## 4) 토큰 발급 결과
- 실행 스크립트: `run_token_test.py`
- 결과: 성공/실패 (실행 로그 참조)
- 보안: token 마스킹 저장/출력

## 5) 계좌번호 조회 결과
- 실행 스크립트: `run_account_test.py`
- 결과: 성공/실패 (실행 로그 참조)
- 보안: 계좌번호 마스킹 저장/출력

## 6) 조건검색 목록조회 검토 결과
- 대상: ka10171
- 판단: WebSocket 기반으로 분리 검토 필요 (27-B)

## 7) 조건검색 일반조회 검토 결과
- 대상: ka10172
- 판단: WebSocket 기반 여부/요청 필드 확정 필요 (27-B)

## 8) 시가대비등락률 API 호출 결과
- 대상: ka10028
- 실행 스크립트: `run_intraday_change_rank.py`
- raw 저장: `data/raw/ka10028_raw_*.json`
- normalized 저장: `data/normalized/ka10028_normalized_*.json`

## 9) 응답 샘플 요약
- stock_code, stock_name, current_price, open_price, high_price, low_price
- intraday_change_rate(시가대비등락률), day_change_rate, strength

## 10) DrCT 시장 트렌드 연동 가능성
- 조건검색 또는 시세 랭크 응답을 `market_trend_events` 후보 입력으로 변환 가능
- 27-A는 미연동 PoC이며, 후속 단계에서 DrCT API 연동 필요

## 11) 후속 단계 제안
1. 27-B: 조건검색 WebSocket 핸드셰이크/목록조회/일반조회 구현
2. 응답 표준화 고도화(거래대금 보강 API 결합)
3. DrCT ingestion endpoint 연결(조회 전용)

## 보안 메모
- APP KEY/SECRET/TOKEN/계좌번호 원문 문서 기록 금지
- 주문 API 호출 차단 유지
