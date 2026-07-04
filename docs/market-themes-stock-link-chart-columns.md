# 시장테마관리 종목 연결 목록 차트 컬럼

## 목적

시장테마관리 화면의 종목 연결 탭에서 연결 종목의 최근 가격 흐름을 바로 확인할 수 있도록 연결 종목 목록에 일봉, 주봉, 월봉 미니 차트 컬럼을 추가한다.

## 변경 범위

- 화면: 시장테마관리 > 종목 연결 탭 > 연결 종목 목록
- 프론트엔드 파일:
  - `frontend/src/pages/MarketThemesPage.tsx`
  - `frontend/src/index.css`
- 백엔드, DB 구조, 연결 저장/해제 로직, 테마등락률 갱신 로직은 변경하지 않는다.

## 컬럼 구성

변경 전:

- 종목
- 시장
- 대표
- 출처
- 신뢰도
- 상태
- 작업

변경 후:

- 종목
- 시장
- 대표
- 상태
- 일봉
- 주봉
- 월봉
- 작업

`출처`, `신뢰도` 데이터는 삭제하지 않고 연결 종목 목록의 화면 표시에서만 제외한다.

## 차트 URL

네이버 금융 캔들 차트 이미지를 사용한다.

- 일봉: `https://ssl.pstatic.net/imgfinance/chart/item/candle/day/{stockCode}.png?sidcode={sidcode}`
- 주봉: `https://ssl.pstatic.net/imgfinance/chart/item/candle/week/{stockCode}.png?sidcode={sidcode}`
- 월봉: `https://ssl.pstatic.net/imgfinance/chart/item/candle/month/{stockCode}.png?sidcode={sidcode}`

종목코드는 문자열로 처리하고 숫자가 아닌 문자를 제거한 뒤 마지막 6자리를 `padStart(6, "0")`로 보정한다. 따라서 `005930`처럼 앞자리 0이 필요한 종목코드를 유지한다.

## UI/성능 처리

- 차트 이미지는 `loading="lazy"`로 로드한다.
- `sidcode`는 선택 테마와 연결 종목 수가 바뀔 때만 갱신한다.
- 이미지 로딩 실패 시 깨진 이미지 대신 `차트 없음` fallback을 표시한다.
- 차트 컬럼 추가로 전체 폭이 넓어지므로 테이블 wrapper에 가로 스크롤을 허용한다.
- 텍스트 셀 padding과 대표 checkbox, 작업 버튼을 compact하게 조정한다.
