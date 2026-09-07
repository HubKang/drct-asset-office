# DrCT 종목 시그널 Phase 7-A 성과 자동 축적

## 목적

현재 Candidate Policy, S-only Pattern Signature, Similarity와 Marker 학습 정책을 바꾸지 않고 실제 운영 화면에 표시된 시그널의 사후 움직임을 장기간 축적한다. 이 단계에서는 성공 기준이나 추천 알고리즘 개선안을 만들지 않는다.

## Signal Episode

Signal Episode는 `stock_id + marker_id` 단위다. 운영 Scan에서 처음 감지된 거래일을 `signal_date`, 마지막으로 계속 감지된 거래일을 `last_seen_date`로 기록한다. 연속된 운영 Scan에서 같은 Pair가 감지되면 기존 Episode만 갱신한다. 관측된 다음 Scan에서 후보가 아니면 `ended_date`로 닫고, 이후 다시 감지되면 새 Episode를 만든다. Scan하지 않은 날짜의 상태는 추정하지 않는다.

같은 날짜의 재실행은 기존 Episode를 재사용한다. 활성 Pair Partial Unique Index가 동시 중복도 방지한다. 한 종목에서 여러 Marker가 감지되면 Marker별 Episode를 각각 저장한다.

## 저장 필드와 보존 범위

`drct_stock_signal_events`에는 종목·Marker, Episode 날짜, D0 종가, 당시 유사도/구간, 알고리즘 Version, 개선안 포함 여부, 평가 상태와 D+5/10/20 및 최대 상승·하락만 저장한다.

다음 재현 가능한 상세 데이터는 저장하지 않는다.

- 전체 Scan/Universe JSON
- Feature Matrix 및 Signature JSON
- Similarity Vector
- Threshold Simulation과 SHADOW 전체 결과
- OHLC 차트 JSON
- 검색식 평가 결과

개선안은 운영에 적용하지 않는다. 실제 운영 후보가 당시 Shadow Policy에도 포함됐는지만 Boolean과 Version으로 보존하며 Improvement-only 후보는 저장하지 않는다.

## 사후 성과 정의

D0는 운영 Scan의 `analysis_date`, D0 가격은 같은 날짜의 `stock_daily_prices.close_price`다. D0 이후 저장된 거래일 Row를 날짜순으로 세어 5번째, 10번째, 20번째 종가 수익률을 계산한다. Calendar Day나 근사 가격을 사용하지 않는다.

- 5/10/20거래일 변화 = `(해당 종가 / D0 종가 - 1) × 100`
- 최대 상승 = D+1~D+20 최고가의 D0 종가 대비 변화
- 최대 하락 = D+1~D+20 최저가의 D0 종가 대비 변화

상태는 `PENDING`, `D5_READY`, `D10_READY`, `COMPLETE`다. D+20까지 종가·고가·저가가 준비된 경우에만 최대 상승·하락을 확정하고 완료 처리한다.

## 자동 갱신과 API

- 메인 화면: `POST /drct-stock-signals/marker-signals/scan-and-record`가 기존 순수 Scan 결과를 그대로 반환한 뒤 Episode를 Upsert한다.
- 연구/진단: 기존 `POST /marker-signals/scan` 및 Diagnostics 경로는 저장하지 않는다.
- 성과 탭: 최초 진입 시 `POST /performance/refresh`가 미완료 Episode만 평가한다.
- 조회: `GET /performance/summary`, `GET /performance/events`, `GET /performance/events/{id}`를 사용한다.

성과 평가는 외부 가격 API를 호출하지 않고 `stock_daily_prices`를 한 번에 Bulk 조회한다. 완료 Episode는 재계산하지 않는다.

## 운영 원칙

과거 Runtime Scan을 현재 데이터로 재생성하거나 Backfill하지 않는다. Migration은 빈 정형 테이블과 최소 Index만 만들며 실제 사용자 DB에 테스트 Event를 삽입하지 않는다. 검색식 성과 비교와 성공/실패 정의, 추천 기준 변경 및 자동 승격은 충분한 운영 데이터가 쌓일 때까지 보류한다.

