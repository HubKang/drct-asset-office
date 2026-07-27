# 월별 수급 TOP20 가격 데이터 준비도와 선택 수집

## 목적

월별 수급 테마(종목)의 TOP20 누적등락률 그래프에서 종목별 가격 준비 상태를 구분하고, 사용자가 명시적으로 요청할 때 부족 종목의 최소 가격 범위만 보완한다.

## 상태 코드

- `READY`: 시작 전 기준 종가와 기간 내 유효 종가 2개 이상이 있으며 거래일 커버리지가 50% 이상이다.
- `READY_WITH_FALLBACK`: 시작 전 기준 종가가 없어 기간 내 첫 종가를 0% 기준으로 사용한다.
- `PARTIAL`: 기준 종가와 2개 이상의 가격은 있으나 공통 거래일 커버리지가 50% 미만이다. 그래프는 결측 구간을 끊어서 표시한다.
- `NO_PRICE_DATA`: 기간 내 유효 종가가 없다.
- `NO_BASE_PRICE`: 기준 종가를 확보하지 못했고 기간 첫 종가도 사용할 수 없다.
- `INSUFFICIENT_OBSERVATIONS`: 기간 내 유효 종가가 1개뿐이다.

`READY`, `READY_WITH_FALLBACK`, `PARTIAL`은 그래프 표시 가능 상태이며 나머지 상태만 선택 수집 대상이다. 기존 `has_sufficient_price_data`는 호환을 위해 유지한다.

## 조회와 수집 경계

`GET /external/kiwoom/theme-flow/monthly/top-stock-return-trend`는 DB 읽기 전용이다. 외부 키움 API를 호출하지 않으며 TOP20 가격은 배치 조회한다. 그래프 시계열이나 외부 응답 JSON은 별도 저장하지 않는다.

사용자가 `부족 종목 가격 수집`을 누르면 `POST /external/kiwoom/theme-flow/monthly/top-stock-return-trend/collect-missing-prices`가 동일한 TOP20과 준비도를 서버에서 다시 계산한다. 클라이언트가 종목 ID를 임의 지정하지 않는다.

수집 범위는 `period_start_date - 15일`부터 `period_end_date`까지다. 키움 `ka10081` 기존 페이지 중단 로직과 `stock_daily_prices` upsert를 재사용하며 전체 상장 기간 backfill은 하지 않는다.

## 제외 작업

전용 `supply_top20_recent_range` 모드는 다음 작업을 실행하지 않는다.

- 기술지표·이동평균 재계산
- 시장지표, 재무, 투자자 수급 수집
- 관심종목 평가와 테마 등락률 갱신
- 기존 가격 또는 수급 이벤트 삭제

종목별 저장은 독립적으로 유지되어 일부 종목 실패가 성공 종목을 롤백하지 않는다. 중복 요청은 서버 잠금과 프런트 버튼 비활성화로 방지한다.

## 화면 갱신

수집 완료 후 TOP20 그래프 API만 다시 호출한다. 월간 달력, 히트맵, 트리맵은 재조회하지 않는다. 부분 실패 시 성공 종목은 즉시 선그래프에 반영되고 실패 종목은 세분화된 부족 상태와 사유를 유지한다.