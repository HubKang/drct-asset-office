# 59-G-2 시장 지표 관리 화면 시장환경 해석 compact UI 개선

## 배경

시장 지표 관리 화면의 시장환경 해석 카드가 9개 모두 기본 노출되면서 차트와 지표 선택 영역이 아래로 밀렸다. 해석은 참고 정보이므로 기본 화면에서는 핵심 환경만 빠르게 확인하고, 필요한 경우 전체 해석을 펼쳐보도록 정리했다.

## 변경 내용

- 기본 상태는 compact 요약형으로 표시한다.
- 기본 상태에서는 `summarizeMarketEnvironmentInsights()`가 선별한 최대 4개 카드만 표시한다.
- compact 카드에서는 카테고리, tone badge, headline, evidence chip 일부만 표시한다.
- 관점별 설명과 긴 description은 `전체 해석 보기`를 눌렀을 때만 표시한다.
- 펼친 상태에서는 기존 9개 해석 카드 전체와 perspectives를 확인할 수 있다.
- 버튼은 `전체 해석 보기` / `해석 접기`로 토글된다.

## 핵심 카드 선별 기준

`buildMarketEnvironmentInsights()` 판단 결과는 변경하지 않는다. `summarizeMarketEnvironmentInsights()`는 결과 배열을 다음 우선순위로 정렬해 compact 표시용 카드만 선택한다.

1. tone 우선순위: risk, caution, positive, neutral
2. 도메인 우선순위: 주식시장 흐름, 환율 환경, 금리 환경, 미국시장 흐름, 글로벌 반도체 심리, 미국 금리 환경, 물가 환경, 경기 심리, 위험회피 흐름
3. 같은 우선순위에서는 제목 기준 정렬

## 영향 범위

- frontend/src/pages/MarketIndexesPage.tsx
- frontend/src/utils/marketEnvironmentRules.ts
- frontend/src/index.css

백엔드, provider, 시장 지표 수집 로직, DB 구조, TradeTrainingPage는 변경하지 않는다.