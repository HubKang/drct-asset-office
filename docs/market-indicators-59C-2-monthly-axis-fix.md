# 59-C-2 물가/경기 월간 지표 x축 보정 결과

## 변경 파일
- frontend/src/pages/MarketIndexesPage.tsx
- frontend/src/types/marketIndex.ts
- frontend/src/index.css

## plotDate 계산 방식
- DB 저장값인 value_date와 period_label은 변경하지 않는다.
- 월간 지표는 period_label(YYYY-MM)을 우선 사용해 해당 월의 말일 YYYY-MM-DD를 렌더링용 plotDate로 계산한다.
- 일별 지표는 기존 value_date를 plotDate로 그대로 사용한다.
- 날짜 계산은 Date.UTC 기반으로 월말 일자를 구해 브라우저 timezone shift를 피한다.

## 개별 차트
- CPI/PPI/CSI/BSI 개별 라인 차트의 x좌표는 plotDate 기준으로 계산한다.
- x축 라벨은 기존처럼 period_label을 우선 표시해 월간 지표로 읽히도록 유지했다.
- CSI/BSI 기준선 표시는 기존 59-C-1 동작을 유지했다.

## 비교 차트
- 비교 차트 point에 plotDate, periodLabel, isCarryForward 렌더링 필드를 허용했다.
- MARKET_INDEX point는 date와 동일한 plotDate를 가진다.
- MARKET_INDICATOR 월간 point는 월말 plotDate를 가진다.
- x축 domain과 path 정렬은 plotDate 기준으로 계산한다.

## carry-forward
- 비교 차트에서만 월간 지표의 마지막 point가 전체 비교 기준 최신일보다 이전이면 표시용 point를 하나 추가한다.
- 추가 point는 DB 저장값이 아니며 isCarryForward=true로 표시한다.
- 화면에는 “월간 지표의 최신 발표값은 비교 기준일까지 표시용으로 연장됩니다.” 안내 문구를 표시한다.

## 영향 범위
- backend DB schema, 수집 로직, provider 로직은 변경하지 않았다.
- 기존 환율/금리 일별 라인 차트는 value_date 기준을 유지한다.
- 기존 시장/업종 캔들차트는 변경하지 않았다.
- TradeTrainingPage.tsx는 변경하지 않았다.
