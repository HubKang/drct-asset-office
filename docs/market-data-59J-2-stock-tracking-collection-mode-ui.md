# 59-J-2 종목트래킹 수집 모드 UI 정리

## 배경

59-I-2에서 종목트래킹 가격 수집 API가 증분 수집과 전체 재수집을 구분할 수 있도록 정리되었다. 종목트래킹 화면의 기존 가격 갱신 버튼은 어떤 기간을 요청하는지 사용자가 알기 어려웠기 때문에 UI에서 수집 모드를 명확히 분리했다.

## 버튼 구성

- 목록 최근7일수집: 현재 목록의 수집 가능 트래킹 종목을 최근 7일 겹침 기준으로 수집한다.
- 선택 최근7일수집: 체크한 수집 가능 트래킹 종목만 최근 7일 겹침 기준으로 수집한다.
- 목록 전체수집: 현재 목록의 수집 가능 트래킹 종목을 전체 기간 기준으로 다시 수집한다.
- 선택 전체수집: 체크한 수집 가능 트래킹 종목만 전체 기간 기준으로 다시 수집한다.

## API payload 기준

최근7일수집 payload:

```json
{
  "item_ids": [1, 2, 3],
  "overlap_days": 7,
  "force_full_refresh": false
}
```

전체수집 payload:

```json
{
  "item_ids": [1, 2, 3],
  "overlap_days": 7,
  "force_full_refresh": true
}
```

## UI 원칙

- 4개 수집 버튼을 2x2로 노출하지 않는다.
- 전체수집은 드롭다운 메뉴로 숨겨 보조 기능처럼 보이게 한다.
- 버튼 아래에 긴 안내문을 추가하지 않고, 전체수집 버튼 title과 확인 모달에서 의미를 설명한다.

## 안전장치

- 전체수집 메뉴 항목은 바로 API를 호출하지 않고 확인 모달을 먼저 띄운다.
- 모달에서 취소하거나 닫으면 API를 호출하지 않는다.
- 선택 수집에서 체크한 종목이 없으면 API를 호출하지 않고 안내 메시지를 표시한다.
- 수집 완료 후 기존처럼 목록, 그룹, 선택 상세 차트/이미지를 재조회한다.

## 영향 범위

- frontend/src/pages/StockTrackingPage.tsx
- frontend/src/types/stockTracking.ts
- frontend/src/index.css

백엔드 로직, WatchlistPage, MarketIndexesPage, MarketThemesPage, TradeTrainingPage는 이 작업에서 변경하지 않는다.