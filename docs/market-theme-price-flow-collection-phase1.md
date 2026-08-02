# 시장테마 가격·수급 공통 수집 기반 1단계

## 목적과 범위

시장 테마 관리의 활성 테마에 현재 연결된 고유 종목을 대상으로 가격, 개인·외국인·기관 수급, 프로그램 수급을 공통 테이블에 수집한 뒤 기존 테마등락률을 갱신한다. 종목별 누적 수급 차트, 정규화 비교, 테마 수급 집계·분석 화면은 다음 단계 범위다.

## 기존 구조 조사 결과

- 시장 테마 화면: `frontend/src/pages/MarketThemesPage.tsx`
- 기존 테마등락률 API: `POST /external/kiwoom/market-themes/returns/refresh`
- 활성 테마 연결: `market_themes`와 `market_theme_stocks`; 연결은 `theme_id`, `stock_id`, `is_active`로 관리된다.
- 가격 공통 원천: `stock_daily_prices`; `(stock_id, trade_date)` 고유 인덱스와 upsert가 이미 있다.
- 가격 수집: `StockPriceService`와 `KiwoomRestMarketDataProvider`; 페이지 조기 종료와 날짜 범위 수집을 재사용한다.
- 이동평균 및 기술지표: `StockPriceService.recalculate_moving_averages`와 `TechnicalIndicatorService`를 재사용한다.
- 투자자·프로그램 공통 원천: `stock_investor_flows`; `(stock_id, flow_date)` 고유 인덱스와 upsert가 이미 있다.
- 투자자 수급: `StockInvestorFlowService`와 `KiwoomRestInvestorFlowProvider`의 ka10059를 재사용한다.
- 프로그램 수급: 같은 provider의 ka90013을 재사용하되 프로그램 필드는 투자자 합계와 분리한다.
- 토큰과 연속조회: 기존 `KiwoomRestClient`·`KiwoomAuthClient` 캐시 및 `cont-yn`/`next-key` 처리를 그대로 사용한다.
- 작업 이력: 기존 `collection_runs`를 사용하며 실패 상세 원문은 저장하지 않고 집계 메시지만 보존한다.

## DB의 비파괴 확장

`stock_investor_flows`에 다음 nullable 정수 컬럼을 런타임 스키마 보정으로 추가한다.

- `individual_buy_qty`, `individual_sell_qty`, `individual_net_qty`
- `individual_buy_amount`, `individual_sell_amount`, `individual_net_amount`

기존 행, 외국인·기관·프로그램 컬럼, 고유 인덱스는 변경하거나 삭제하지 않는다. 수량은 주, 금액은 원이다. ka10059 금액 응답의 백만원 단위는 저장 직전에 원으로 환산한다. 원천 API 응답 JSON은 저장하지 않으며 명시적 컬럼만 저장한다.

## 수집 대상

1. 요청 범위의 활성 일반 테마를 조회한다.
2. `market_theme_stocks.is_active=1`이고 종목 마스터가 활성인 연결만 조회한다.
3. 연결 목록을 `stock_id` 기준으로 중복 제거한다.
4. 동일 종목이 여러 테마에 있어도 가격과 수급 API는 한 번만 실행한다.

모든 활성 테마에서 연결 해제된 종목은 다음 실행 대상에서 제외한다. 기존 가격·기술지표·수급·테마 이력은 삭제하지 않는다. 다시 연결되면 저장된 데이터 종류별 최신일부터 이어서 수집한다.

## 최초·증분·재연결 정책

### 가격

- 데이터 없음: 실행일 기준 6개월 전의 같은 달력일에서 시작한다. 말일이 없는 달은 해당 월 말일을 사용한다.
- 기존 데이터 있음: 공통 가격 테이블의 최신일에서 7일 앞부터 overlap 수집한다.
- 같은 `(stock_id, trade_date)`는 update, 새 날짜는 insert다.
- 신규 상장·거래정지로 응답 행이 적거나 없어도 해당 종목의 기존 데이터는 유지한다.

### 투자자·프로그램 수급

- 투자자 최신일과 프로그램 최신일을 각각 조회한다.
- 둘 중 하나라도 없으면 최초 6개월 범위를 수집한다.
- 둘 다 있으면 더 오래된 최신일에서 7일 앞부터 수집한다.
- ka10059는 금액/수량과 순매수/매수/매도를 조합하여 개인·외국인·기관 값을 직접 수집한다. 개인 값을 잔차로 계산하지 않는다.
- ka90013 프로그램 값은 별도 컬럼에 저장하며 투자자 합계에 포함하지 않는다.
- 같은 `(stock_id, flow_date)`는 upsert한다.

## 기술지표 처리

가격 수집이 성공한 종목만 기존 이동평균과 기술지표 계산기를 실행한다. 수급 실패는 가격과 지표를 롤백하지 않으며, 지표 실패도 이미 커밋된 가격·수급을 롤백하지 않는다. 현재 계산기는 종목 단위 전체 보유 가격을 읽어 일관성을 맞추므로, 이번 단계에서는 변경 종목만 재계산하고 모든 종목을 일괄 재계산하지 않는다. 날짜 영향 구간만 쓰는 최적화는 후속 성능 개선 항목이다.

## 통합 API와 실행 상태

- 기존 API는 하위 호환을 위해 유지한다.
- 새 API: `POST /external/kiwoom/market-themes/returns-and-flows/refresh`
- 화면용 비동기 시작: `POST /external/kiwoom/market-themes/returns-and-flows/jobs`
- 진행 조회: `GET /external/kiwoom/market-themes/returns-and-flows/jobs/{job_id}`
- 실행 순서: 대상 확정 → 가격 → 기술지표 → 투자자/프로그램 수급 → 기존 테마등락률 집계
- 프로세스 내 non-blocking lock으로 실행 중 재요청을 `409 Conflict`로 차단한다.
- 실행 이력은 `collection_runs.collector_name=market_theme_price_flow_refresh`로 남긴다.
- 세부 진행률과 실패 상세는 프로세스 메모리에서만 잠시 유지하며 DB에 원문 JSON으로 저장하지 않는다.
- 상태는 응답에서 `COMPLETED`, `PARTIAL`, `FAILED`로 반환한다.
- 가격·지표·투자자·프로그램·테마 단계별 성공/실패 수, insert/update 수, 최신일과 실패 종목을 명시적 필드로 반환한다.
- 실패 상세는 요청 응답에서만 제공하고 DB 작업 이력에는 집계만 저장한다.

동기식 API는 직접 호출 호환용으로 유지하고 화면은 비동기 시작 후 진행 상태를 polling한다. 버튼은 요청 중 비활성화되고 현재 단계와 완료 종목 수를 표시한다. 프로세스 재시작을 넘는 분산 잠금은 도입하지 않았다.

## 프런트엔드

- 버튼명: `테마 등락률&수급 갱신`
- title에 대상, 수집 항목, 동일 날짜 upsert 정책을 안내한다.
- 실행 중 버튼을 비활성화하고 가격·지표·수급·테마 집계 단계 안내를 표시한다.
- 완료 시 연결 건수, 고유 종목 수, 단계별 성공 수, 기준일과 소요 시간을 표시한다.
- 기존 테마 관리·연결·추천·테마등락추이 조회 API는 유지한다.

## 성능과 안전

- 테마별 호출이 아니라 고유 `stock_id`별 순차 호출이다.
- 무제한 병렬 호출을 하지 않아 기존 키움 호출 안정성과 토큰 캐시를 유지한다.
- 종목 단위로 기존 repository가 커밋하며 한 종목 실패가 전체 정상 데이터를 롤백하지 않는다.
- 원천 응답, 차트 시계열, 실패 표본 JSON을 새로 보존하지 않는다.
- 연결 해제와 재연결 과정에서 과거 데이터를 삭제하지 않는다.

## 알려진 제한사항

- 백그라운드 실행 중 대상 종목 수와 키움 연속조회량에 따라 전체 완료 시간은 길 수 있다.
- 잠금은 단일 애플리케이션 프로세스 범위다. 다중 worker 배포 시 DB 기반 lease가 후속으로 필요하다.
- 실패 종목 전용 버튼은 추가하지 않았다. 같은 통합 갱신을 다시 실행하면 최신일+overlap 정책으로 실패 구간을 재시도한다.
- 기술지표는 변경 종목으로 범위를 제한하지만 종목 내부에서는 현재 전체 보유 이력을 재계산한다.

## 다음 단계

- 연결 종목 상세의 1M·3M·6M 누적 수급 그래프
- 개인·외국인·기관·프로그램 통합 차트
- 실질 수급·패턴 정규화 보기
- 종목메모 수급일 차트 마커
- 테마별 수급 집계 및 수급 주체 분석
