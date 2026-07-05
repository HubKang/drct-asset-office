# 종목 관리 화면 차트 컬럼 추가

## 목적

종목 관리 화면에서 종목 마스터 목록을 검색/필터링하면서 각 종목의 일봉, 주봉, 월봉 흐름을 빠르게 확인할 수 있도록 네이버 금융 캔들 차트 컬럼을 추가한다.

## 변경 범위

- 화면: 종목 관리
- 프론트엔드 파일:
  - `frontend/src/pages/StocksPage.tsx`
  - `frontend/src/index.css`
- 백엔드, DB 구조, KRX 목록 재구축 로직, 시장테마관리, 시장수급분석, TradeTrainingPage는 변경하지 않는다.

## 테이블 컬럼

변경 전 표시 컬럼:

- ID
- 종목코드
- 종목명
- 시장
- 종목유형
- 섹터
- 업종
- ISIN
- 활성
- 마지막 동기화
- 작업

변경 후 표시 컬럼:

- 종목코드
- 종목명
- 시장
- 종목유형
- 활성
- 일봉
- 주봉
- 월봉
- 작업

ID, 섹터, 업종, ISIN, 마지막 동기화는 화면 테이블 표시에서만 제외하며 데이터 자체는 삭제하지 않는다.

## 차트 URL

네이버 금융 캔들 차트 이미지를 사용한다.

- 일봉: `https://ssl.pstatic.net/imgfinance/chart/item/candle/day/{stockCode}.png?sidcode={sidcode}`
- 주봉: `https://ssl.pstatic.net/imgfinance/chart/item/candle/week/{stockCode}.png?sidcode={sidcode}`
- 월봉: `https://ssl.pstatic.net/imgfinance/chart/item/candle/month/{stockCode}.png?sidcode={sidcode}`

종목코드는 숫자만 추출한 뒤 마지막 6자리를 `padStart(6, "0")`로 보정해 앞자리 0을 유지한다.

## UI 처리

- 차트 이미지는 `loading="lazy"`로 로드한다.
- 차트 로딩 실패 시 `차트 없음` fallback을 표시한다.
- 테이블 차트 이미지는 `277px x 140px` 크기로 표시한다.
- 차트 이미지를 클릭하면 확대 모달을 표시하고, 모달 배경 또는 확대 이미지를 클릭하면 닫는다.
- 테이블은 전용 wrapper에 `overflow-x: auto`를 적용해 차트 컬럼 추가로 인한 폭 증가를 처리한다.
- 상단 종목유형 카드에는 유형별 활성 종목 수와 해당 유형의 최신 `last_synced_at` 값을 표시한다.
- 작업 컬럼에는 `활성` 또는 `비활성` 토글 버튼만 표시한다.
