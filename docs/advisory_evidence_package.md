# Advisory Evidence Package API

## Endpoint
- `GET /advisory/evidence-package/{stock_id}`

## 주요 Query 옵션
- `include_news_disclosures_risk` (default: `true`)
- `include_similar_patterns` (default: `false`)
- `include_technical_indicators` (default: `true`)
- `pattern_window` / `similar_case_limit` / `pattern_ma` / `search_trading_days`

## Stage 21.5 반영 내용
- `technical_indicators_block`는 저장 지표를 우선 사용합니다.
- 저장 지표가 있으면 `technical_indicators_block.source = "stored"` 입니다.
- 저장 지표가 없으면 실시간 계산 fallback을 사용하고 `source = "calculated_fallback"` 입니다.
- fallback 사용 시 `data_quality_notes`에 안내 문구를 남깁니다.

## Stage 21.6 반영 내용
- 가격 일봉 조회 응답에 기술적 지표 필드가 포함됩니다.
- 가격 데이터와 기술적 지표는 `stock_id + trade_date` 기준 LEFT JOIN 됩니다.
- 기술적 지표 미저장 일자는 지표 필드가 `null` 입니다.
- 화면에서는 `-` 로 표시합니다.

## Stage 21.7-1 반영 내용
- `data_freshness_block` 추가
- 포함 정보:
  - `package_generated_at`
  - 가격 기준일/source
  - 시장지표 기준일/source/stale
  - 기술적 지표 기준일/source/calculation_version
  - 뉴스·공시 기준 기간/건수
  - `overall_data_confidence` (high/medium/low)
- 목적:
  - 투자 판단 신호가 아니라 데이터 기준일/품질 상태 확인용 요약

## Stage 21.7-2 반영 내용
- `executive_summary_for_gpt` 블록 추가
- 주요 필드:
  - `summary_ko`
  - `key_points`
  - `analyst_focus_points`
  - `caution_points`
  - `data_confidence_level`
  - `generated_basis`
- 화면 사용성:
  - GPT 옵션 영역 그룹화(가격·기술 / 이벤트·리스크 / 고급)
  - `GPT 분석 요청문+JSON 복사` 기능 추가
- 주의:
  - GPT API 자동 호출 기능은 포함하지 않음
  - 투자 판단 자동화/목표가 제시는 포함하지 않음

## 신규 저장 테이블
- `stock_daily_technical_indicators`
- unique key: `(stock_id, trade_date)`
- 핵심 컬럼:
  - `rsi14`
  - `macd`, `macd_signal`, `macd_histogram`
  - `bb_upper`, `bb_middle`, `bb_lower`, `bb_width`, `bb_close_position`
  - `atr14`, `atr14_ratio_to_close`
  - `ma5_gap_pct` ~ `ma240_gap_pct`
  - `volume_ma5`, `volume_ma20`, `volume_5_20_ratio`
  - `source`, `calculation_version`

## 수동 계산 API
- `POST /technical-indicators/calculate/stock/{stock_id}`
- 응답:
  - `stock_id`
  - `calculated_count`
  - `saved_count`
  - `latest_trade_date`
  - `message`

## 주의 문구
- 기술적 지표는 투자 판단 보조 정보입니다.
- 자동 매수/매도 판단 자료가 아닙니다.
- 목표가 단정/확정 예측을 생성하지 않습니다.
- 최종 투자 판단은 사용자 책임입니다.
