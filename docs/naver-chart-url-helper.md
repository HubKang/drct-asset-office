# 네이버 차트 URL Helper

## 목적

여러 화면에서 반복되던 네이버 금융 차트 이미지 URL 생성 로직을 `frontend/src/utils/naverChart.ts`로 공통화한다. 종목코드 정규화, sidcode 생성, 국내 종목 캔들 차트 URL 형식을 한 곳에서 관리해 화면별 구현 차이를 줄인다.

## 공통 함수

- `normalizeNaverStockCode(stockCode)`
  - 숫자만 추출한다.
  - 일반 종목코드는 마지막 6자리를 사용하고 6자리 미만이면 앞에 `0`을 채운다.
  - `5930`, `A005930`, `005930`은 모두 `005930`으로 정규화한다.
  - 한국 ISIN 형태인 `KR7005930003`은 내부 종목코드 `005930`을 추출한다.
  - 값이 없거나 숫자가 없으면 빈 문자열을 반환한다.

- `createNaverChartSidcode()`
  - `Date.now()` 기반 sidcode를 반환한다.
  - 화면에서는 매 렌더마다 호출하지 않고 `useMemo` 또는 `useState`로 조회 조건 변경 시점에만 갱신한다.

- `buildNaverStockCandleChartUrl(stockCode, period, sidcode)`
  - 국내 종목 캔들 차트 URL을 생성한다.
  - 지원 period: `day`, `week`, `month`
  - URL: `https://ssl.pstatic.net/imgfinance/chart/item/candle/{period}/{stockCode}.png?sidcode={sidcode}`

- `buildNaverKoreaMarketChartUrl(market, sidcode)`
  - KOSPI/KOSDAQ 3개월 미니 차트 URL을 생성한다.
  - URL: `https://ssl.pstatic.net/imgstock/chart3/day90/{market}.png?sidcode={sidcode}`

## 향후 확장

이번 작업에서는 화면에 새 차트를 추가하지 않고 helper만 준비했다.

- `buildNaverWorldIndexChartUrl()`
  - 예: 다우지수 `DJI@DJI`, 나스닥 `NAS@IXIC`, S&P500 `SPI@SPX`
  - URL: `https://ssl.pstatic.net/imgfinance/chart/world/month3/{code}.png?{sidcode}`

- `buildNaverMarketIndexAreaChartUrl()`
  - 예: 달러 환율 `FX_USDKRW`, 달러 인덱스 `FX_USDX`, WTI `OIL_CL`
  - URL: `https://ssl.pstatic.net/imgfinance/chart/marketindex/area/month3/{code}.png?sidcode={sidcode}`

국제 금 예시는 이미지 URL이 아니라 네이버 상세 페이지 URL이므로, 실제 차트 이미지 표시가 필요할 때 별도 확인이 필요하다.

## 적용 화면

- 시장테마관리
  - 연결 종목 목록의 일봉, 주봉, 월봉 URL 생성에 `buildNaverStockCandleChartUrl` 사용
  - 연결 종목 코드 정규화에 `normalizeNaverStockCode` 사용

- 종목 관리
  - 종목 목록의 일봉, 주봉, 월봉 URL 생성에 `buildNaverStockCandleChartUrl` 사용
  - 종목코드 표시와 차트 URL 생성에 `normalizeNaverStockCode` 사용

- 시장수급분석
  - 선택 테마 상세 종목의 일봉, 주봉, 월봉 URL 생성에 `buildNaverStockCandleChartUrl` 사용
  - KOSPI/KOSDAQ 3개월 미니 차트 URL 생성에 `buildNaverKoreaMarketChartUrl` 사용

## 검증

- 기존 차트 표시 방식은 유지하고 URL 생성 위치만 공통 helper로 이동했다.
- backend, DB, 데이터 수집 로직, TradeTrainingPage는 변경하지 않는다.
