# Phase5 시장지표 전체갱신 선택형 보정관찰

## 목적과 UX

`관찰순위 계산`은 즉시 실행하지 않고 시장지표 처리 방법을 묻는 모달을 연다. 사용자는 `현재 지표로 계산` 또는 `전체지표 갱신 후 계산`을 반드시 선택한다. 후자가 primary 동작이며 처리 중에는 중복 실행과 모달 닫기를 막는다.

## 실행 모드

- `CURRENT_MARKET_DATA`: 외부 수집 없이 DB의 현재 지표를 다시 읽고 전체 Observation Feature를 재산출한다.
- `REFRESHED_MARKET_DATA`: 기존 시장지표 화면과 동일한 `MarketDataCollectionService.collect(INCREMENTAL_ALL)`을 완료한 다음 DB를 다시 읽고 전체 Feature를 재산출한다.

전체갱신은 지수와 경제지표를 수집한 후 기존 시장 신호 평가 후속작업까지 수행한다. 관찰 서비스가 provider를 직접 호출하거나 수집 코드를 복제하지 않는다. 외부 수집 transaction과 관찰 결과 transaction은 분리되어 수집 성공 후 관찰 계산이 실패해도 수집 결과와 이전 관찰 결과가 유지된다.

## 실패와 부분 성공

- 전체갱신 `FAILED`: 관찰 계산을 실행하지 않고 기존 공식 결과를 유지한다.
- `PARTIAL_SUCCESS`: 성공 값은 새 값, 실패·대기 지표는 기존 DB값을 사용하고 run에 `PARTIAL`을 기록한다. 누락값은 0으로 바꾸지 않는다.
- 갱신 성공 후 관찰 실패: 갱신 run은 유지하고 이전 관찰 결과를 rollback으로 보호한다.
- `INCREMENTAL_ALL`은 프로세스 공통 non-blocking lock으로 중복 실행을 409 `MARKET_REFRESH_ALREADY_RUNNING`으로 차단한다.

## 최신성 및 as-of

과거 학습/검증 행은 기존처럼 기준일보다 엄격히 이전인 해외 지표만 사용한다. 운영 D+1 계산 행만 계산시각까지 실제 저장된 최신값을 사용할 수 있다. Feature Builder는 호출마다 DB를 다시 조회하므로 별도 메모리 cache가 없다.

`data_cutoff_date`는 계속 테마·종목 기준일이다. 시장 데이터는 별도 scalar metadata로 기록한다.

- `market_indicator_refreshed_at`: 전체갱신 완료 시각
- `market_indicator_data_asof_at`: Feature 계산에 사용한 시장 데이터 수집 기준시각
- `calculation_mode`, refresh 요청/상태, 변경·실패 건수, collection run id, revision

상세 수집 응답이나 Feature 행렬은 관찰 run에 복제하지 않는다.

## D+1 및 검증

D+1 열은 하나만 유지하고 마지막 성공 관찰 결과를 표시한다. 툴팁에 계산 모드, 테마·종목 기준일, 시장지표 갱신시각과 계산시각을 표시한다. 실적 검증 metrics는 해당 run의 `calculation_mode`와 연결되어 향후 모드별 Top20 Precision/NDCG 집계가 가능하다.

## 실제 운영 확인 (2026-08-08)

현재 지표 경로는 collection run 수가 증가하지 않았고 `CURRENT_MARKET_DATA / NOT_REQUESTED`로 계산됐다. 전체갱신 경로는 기존 collection run 35를 생성해 56개 대상 중 53개 성공, 3개 WAITING, 신규 14건·수정 29건을 저장하고 시장 신호 24개를 평가했다. 따라서 공식 관찰 run은 `REFRESHED_MARKET_DATA / PARTIAL`, 변경 43건, 실패 0건으로 기록됐다.

갱신 후 NASDAQ 최신일은 2026-08-06에서 2026-08-07, SOX는 2026-08-06에서 2026-08-07, 미국 10년물은 2026-08-05에서 2026-08-06으로 진전했다. 운영 Feature의 NASDAQ 1일 변화는 -0.0572%에서 +1.2990%, SOX는 +0.3315%에서 +2.5571%, 미국 10년물은 0%에서 +1.2959%로 바뀌었다. 시장환경 점수는 50.3589에서 52.8502로 변경됐고, 1위 2차전지 관찰점수는 86.6846에서 86.8092로 조정됐다.

## 제외 범위

RULE 가중치 변경, 신규 ML, 자동 승격, 앙상블, 뉴스/GPT, D+1 열 추가, 시장지표 원본 복제와 JSON 분석 저장은 포함하지 않는다.
