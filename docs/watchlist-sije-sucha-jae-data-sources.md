# 관심 종목 시재수차재 데이터 수집 주체

이 문서는 시재수차재 평가 화면에서 사용하는 데이터 원천과 저장 위치를 정리한다. 원칙은 실제 수집 데이터만 표시/평가하고, 미수집 데이터는 임의 생성하지 않는 것이다.

## 공통 원칙

- API 원문 전체와 `raw_json`은 저장하지 않는다.
- 화면과 평가에는 정규화된 컬럼으로 저장한 값만 사용한다.
- 미수집 값과 실제 0은 구분한다.
- 결산연도, 분기, 보고서 코드 등 기간 근거가 없으면 연도별·분기별 행을 만들지 않는다.
- 파생 계산값은 `source_method` 또는 `calculation_method`로 계산 근거를 남긴다.
- 모든 평가는 매수/매도 추천이 아닌 관찰용 평가다.

## 시장 탭

수집 주체:
- Kiwoom/시장지표 수집 서비스
- 국내/미국 지수, 환율, 금리, 원자재 지표 수집 서비스

저장 위치:
- `market_indexes`
- `market_index_daily_prices`
- 시장지표 관련 테이블

사용 factor:
- 국내 지수 흐름
- 시장 체감/폭
- 시장 유동성
- 미국 시장 흐름
- 외부 위험

정책:
- 지표가 없으면 해당 factor를 제외하거나 일부 데이터 평가로 처리한다.
- 임의 시장지표를 생성하지 않는다.

## 재료 탭

수집 주체:
- 뉴스 수집 서비스
- DART/OpenDART 공시 수집 서비스
- 시장 테마 관리와 테마 흐름 분석

저장 위치:
- `news_items`
- `disclosures`
- `market_themes`
- `market_theme_stocks`
- `market_theme_daily_returns`

사용 factor:
- 뉴스 재료 강도
- 공시 재료 강도
- 테마 연결도
- 재료 최근성
- 재료 지속성

정책:
- GPT 생성 해석은 원천 데이터로 저장하지 않는다.
- 실제 저장된 뉴스, 공시, 테마만 평가에 사용한다.

## 수급 탭

수집 주체:
- Kiwoom `ka10059`: 외국인·기관 순매매 수량/금액
- Kiwoom `ka90013`: 프로그램 순매매 수량/금액
- Kiwoom `ka10008`: 외국인 보유수량/보유율

저장 위치:
- `stock_investor_flows`

사용 factor:
- 투자주체별 수급
- 외국인 수급
- 기관 수급
- 프로그램 수급

정책:
- `derived_price_flow`는 투자주체별 수급처럼 표시하지 않는다.
- `ka10008` 보유율은 외국인 순매매로 대체하지 않는다.
- 실제 순매매 원천 데이터가 없으면 그래프와 점수 반영을 하지 않는다.

## 차트 탭

수집 주체:
- 일봉 가격 수집 서비스
- 기술지표 계산 서비스

저장 위치:
- `stock_daily_prices`
- `stock_daily_technical_indicators`

사용 factor:
- 60일선 추세
- 20일선 눌림/근접도
- 과열 이격 위험
- 최근 5일 상승률 위험
- 거래대금 동반 여부

정책:
- 실제 가격 데이터와 계산 가능한 기술지표만 사용한다.
- 이동평균이나 이격률을 임의 생성하지 않는다.

## 재무 탭

수집 주체:
- Kiwoom `ka10001`: PER, PBR, EPS, BPS, ROE, 시가총액, 상장주식수 등 현재 재무 스냅샷
- OpenDART `corpCode.xml`: 종목코드와 `corp_code` 매핑
- OpenDART `fnlttSinglAcntAll`: 연도별/분기별 재무제표
- OpenDART `hyslrSttus`: 최대주주 현황
- OpenDART `majorstock`: 주요주주/대량보유 보고 1차 수집
- Kiwoom `ka10008`: 외국인 보유율 재사용

저장 위치:
- `stock_financial_snapshots`
- `stock_external_identifiers`
- `stock_financial_statements`
- `stock_shareholder_snapshots`
- `stock_shareholder_changes`
- `stock_investor_flows`

사용 factor:
- 성장성
- 수익성
- 안정성
- 밸류에이션 부담
- 주주·지분 안정성

OpenDART 정책:
- 필요한 계정과목만 정규화해 저장한다.
- 원문 JSON/XML 전체는 저장하지 않는다.
- 연결 재무제표(CFS)를 우선 사용하고 없으면 개별 재무제표(OFS)를 사용한다.
- 누적 분기값을 단일 분기값으로 변환하면 `calculation_method = DART_CUMULATIVE_DIFF`로 저장한다.
- Kiwoom 스냅샷에 부채비율이 없고 OpenDART 부채총계/자본총계가 있으면 `OPENDART_LIABILITIES_EQUITY_RATIO` 계산값을 응답과 평가에 사용한다.
- 변환 근거가 부족하면 분기 행을 생성하지 않는다.
- PER은 수집값이 있으면 그대로 사용한다.
- PER이 없고 EPS가 0 이하이면 `적자 PER`으로 표시하고 밸류에이션 긍정 점수에는 반영하지 않는다.
- PER이 없고 EPS와 현재가가 모두 양수이면 `CURRENT_PRICE_EPS_PER` 계산값을 표시한다.

## API 역할 구분

- `ka10001`: 현재 재무 스냅샷과 밸류에이션 판단 보조
- `ka10008`: 외국인 보유율, 주주·지분 요약 보조
- `ka10059`: 외국인·기관 순매매 원천
- `ka90013`: 프로그램 순매매 원천
- OpenDART `fnlttSinglAcntAll`: 기간별 실적과 안정성 판단 원천
- OpenDART 주주 관련 API: 최대주주/주요주주 보강 원천
