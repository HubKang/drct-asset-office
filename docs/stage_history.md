# Stage History

## Stage 21.8-5 완료
- 수집 이력 응답에 표시용 메타 필드 추가:
  - `collector_display_name`, `run_type`, `run_type_label`, `collector_group`, `collector_group_label`
- 공시/뉴스 Wrapper와 실제 Collector 실행을 구분 표시하도록 CollectionRunService 매핑 로직 추가
  - 예: `watchlist_selected_disclosure_collector` → `선택 공시 수집` / `선택 수집 작업`
  - 예: `dart_disclosure_collector` → `DART 공시 수집` / `외부 수집기`
  - 예: `watchlist_selected_news_collector` → `선택 뉴스 수집` / `선택 수집 작업`
  - 예: `naver_news_collector` → `네이버 뉴스 수집` / `외부 수집기`
- 수집 이력 화면 개선:
  - 목록 컬럼 `수집기명`을 `수집명`으로 전환하고 `실행유형` 컬럼 추가
  - 상세에서 `수집명`, `내부 수집기명`, `실행유형`, `그룹`을 함께 표시
  - 검색 placeholder를 사용자 친화 문구로 정리

## Stage 21.8-4 완료
- 관심종목 Pool 상태 정합성 개선: 좌측 전체 종목 검색이 `watchlist active/inactive` 전체 상태를 함께 반영하도록 수정
- 좌측 표기 정리: `종목상태`(stocks 기준) / `관심상태`(watchlist 기준)로 분리
- 관심상태 표시 기준 통일: `미등록`, `관심등록`, `관심비활성`
- 관심등록/관심비활성 종목은 좌측에서 추가 선택 불가 처리(중복 추가 혼선 방지)
- 우측 목록 상태 표기도 `관심등록` / `관심비활성`으로 통일
- 비활성화/다시 활성화/추가 이후 `refreshAll`로 좌우 목록 동시 갱신 유지

## Stage 21.8-3 완료
- 관심종목 Pool 화면에 `선택 시장지표 갱신` 버튼을 추가했습니다. (선택 캔들 수집 옆 배치)
- `POST /market-metrics/collect/selected` API를 추가해 선택 종목 기준 시장지표 갱신을 지원합니다.
- KIS 기반 시장지표 collector를 추가해 `stock_daily_market_metrics`에 `source='kis_api'`로 upsert 저장하도록 연결했습니다.
- 종목별 성공/실패 결과와 오류 유형(`env_missing`, `auth_failed`, `network_error` 등)을 응답으로 반환하도록 구현했습니다.
- 기존 `source=auto` 우선순위(`kis_api > krx_open_api > data_go_kr > marcap`) 흐름과 연동되도록 유지했습니다.

## Stage 21.8-3A 완료
- KIS 저장값 검증 결과 `market_cap=19594`가 원 단위가 아닌 값으로 저장된 이슈를 확인했습니다.
- KIS collector에서 `hts_avls`(억원 단위)를 원 단위로 정규화(`* 100_000_000`)하도록 보정했습니다.
- market metrics summary에 `date_gap_label`을 추가해 음수 gap(`-1일`)를 `시장지표가 1일 더 최신`처럼 사용자 친화적으로 표시하도록 개선했습니다.
- freshness 메시지 색상은 `freshness_status` 기반(normal/warning/stale/missing)으로 분기하도록 프론트 표시를 정합화했습니다.

## Stage 21.8-3B 완료
- 단위 기준을 확정했습니다: DB 저장은 원 단위, 화면 표시는 억 원 단위.
- 가격·캔들관리 시장지표 탭에서 거래대금/시가총액 표시를 억 원 단위로 통일했습니다.
- market metrics summary 및 GPT evidence package에 `trading_value_display`, `market_cap_display`, `unit_notes`를 추가해 단위 혼동을 줄였습니다.
- KIS `hts_avls`는 억 원 단위로 간주하여 DB에는 원 단위로 저장하도록 collector 기준을 유지했습니다.

## Stage 21.8-2 완료
- market_metrics 조회 기본 source를 `auto`로 정렬하고 source 우선순위(`kis_api > krx_open_api > data_go_kr > marcap`)를 반영했습니다.
- market_metrics summary / GPT evidence package에 `date_gap_days`, `freshness_status`, `freshness_label`, `freshness_message`를 반영했습니다.
- 가격·캔들관리 화면과 GPT 근거 패키지 영역에서 시장지표 최신성 표시(기준일 차이, source, freshness message)를 강화했습니다.
- KRX Open API 재테스트 결과: 현재 실행 환경의 네트워크/프록시 경로 이슈로 외부 호출 확인이 실패했습니다.

## Stage 19 완료
- `GET /advisory/evidence-package/{stock_id}`에 뉴스·공시·Risk 블록 연결
- `include_news_disclosures_risk` 옵션 추가

## Stage 20 완료
- 유사 패턴 분석 고도화
- 유사도 가중치: 가격 50%, 이평선 위치 30%, 거래량 20%

## Stage 21 완료
- `technical_indicators_block` 추가
- RSI, MACD, 볼린저밴드, ATR, 이평선 이격도, 거래량 5/20 비율 반영

## Stage 21.5 완료
- `stock_daily_technical_indicators` 테이블 추가
- 가격 수집 후 기술적 지표 계산/저장 연동
- 수동 계산 API 추가: `POST /technical-indicators/calculate/stock/{stock_id}`
- GPT 자문 패키지에서 저장 지표 우선 사용
- 저장값 없을 때 `calculated_fallback` 유지

## Stage 21.6 완료
- 가격·캔들 조회 화면에 기술적 지표 컬럼 표시
- 가격 일봉 조회 API에 기술적 지표 LEFT JOIN 응답 확장
- 관심종목 Pool에 `기술적 지표 재계산` 버튼 추가
- 선택 종목 배치 재계산 API 추가: `POST /technical-indicators/calculate/selected`

## Stage 21.7-1 완료
- 데이터 기준일/품질 요약 블록(`data_freshness_block`) 추가
- 가격·캔들 화면에 데이터 기준 요약 표시 강화
- KRX Open API 테스트 스크립트 추가: `scripts/test_krx_open_api_market_metrics.py`
- KRX 테스트 결과:
  - 인증키 로딩: 확인됨(원문 미노출)
  - 호출 상태: 현재 실행 환경 프록시/네트워크 제약으로 KRX 서버 직접 호출 실패
  - 결론: 서비스 승인 여부 판단 전, 네트워크 경로 먼저 정상화 필요

## Stage 21.7-2 완료
- GPT 패키지에 `executive_summary_for_gpt` 추가
- GPT 옵션 영역을 그룹 단위로 정리
- `GPT 분석 요청문+JSON 복사` 기능 추가

## Stage 21.7-3A 완료
- 뉴스 관리 화면을 관심종목 List / 뉴스 목록 / 상세 분석 2:5:3 구조로 개편
- 뉴스 목록 컬럼 순서를 `AI처리, 종목명, 제목, 중요도, 감성, 출처, 발행일`로 정리
- 기존 종목 ID 검색 box를 제거하고, 관심종목 선택 기반 조회/수집 흐름으로 통합
- 관심종목 Pool에 GPT 사용 흐름 안내 문구 추가

## Stage 21.7-3A-수정 완료
- 뉴스 관리 화면 레이아웃을 가로 3단(2:5:3)에서 세로 3단(관심종목 List → 뉴스 목록 → 상세 분석)으로 재개편
- 관심종목 목록을 compact 형식으로 조정하고 목록 높이를 제한(`max-h`)하여 상단 영역 과점유를 완화
- 뉴스 목록은 중단에 배치하고 컬럼 순서(`AI처리, 종목명, 제목, 중요도, 감성, 출처, 발행일`)를 유지
- 상세 분석을 하단 전체 폭으로 배치해 선택 뉴스 분석 가독성 강화

## Stage 21.7-3A-수정(재조정) 완료
- 사용자 스케치 기준으로 뉴스 관리 화면을 가로 3패널(관심 종목 / 뉴스 목록 / 뉴스 상세) 구조로 재구성
- 데스크톱 레이아웃을 `1.1fr 2.7fr 1.4fr`로 조정해 가운데 뉴스 목록 패널을 가장 넓게 배치
- 관심 종목 패널에 검색조건/수집옵션/실행 버튼을 통합하고 목록은 패널 내부 스크롤로 유지
- 뉴스 상세 패널을 오른쪽 고정 분석 영역 형태로 정리하고 내부 스크롤을 적용

## Stage 21.7-3A 재기획 완료
- 뉴스 관리 화면의 고정 3패널 구조를 폐기하고 탭 기반 UX로 재구성
- 상단에 뉴스 상태 요약 카드(전체/AI처리/AI미처리/중요뉴스/선택종목) 추가
- `관심종목 기준 수집` 탭과 `뉴스 목록 검토` 탭을 분리해 작업 목적을 명확화
- 뉴스 상세를 고정 패널 대신 오른쪽 슬라이드 drawer로 전환
- 종목 ID/offset 입력은 제거 상태를 유지하고, 목록 컬럼 순서(`AI처리, 종목명, 제목, 중요도, 감성, 출처, 발행일`)를 유지

## Stage 21.7-3A 재기획(단일 워크벤치) 완료
- 상태요약 영역과 탭 분리 구조를 제거하고, 관심종목 기반 단일 워크벤치 화면으로 개편
- 상단 액션바(종목 검색, 수집/AI 처리 버튼, 수집 옵션) + 본문 2열(좌 관심종목, 우 뉴스목록) 구조 적용
- 관심종목 선택 시 해당 종목 뉴스가 자동 조회되도록 흐름 단순화
- 뉴스목록 검색 필드를 제거하고, 종목 ID/offset 입력을 제거
- 뉴스 상세는 고정 패널 대신 Drawer 방식으로 유지

## Next
- Stage 22: 오늘의 시장 트렌드 화면
## Stage 21.7-4A 완료
- 공시관리 화면을 뉴스관리 화면과 동일한 좌우 패널형 워크벤치 UX로 개편
- 상단 제목 카드 + 단일 행 액션바 + 본문 3:7(관심종목:공시목록) + 우측 Drawer 구조 적용
- 관심종목 선택 시 공시목록 자동 조회, 관심종목 checkbox와 row 클릭 역할 분리
- 공시목록 검색 필드/종목 ID 입력/offset 입력 제거
- 공시목록 컬럼 순서 확정: AI처리, 종목명, 공시제목, 이벤트, 리스크, 중요도, 공시일
- 공시 row 클릭 기반 상세 Drawer 적용(원문 링크, AI 요약, 이벤트/리스크/중요도 표시)
## Stage 21.8-1 완료
- 가격·캔들관리 화면에서 가격 요약/시장지표 요약을 탭 구조로 정리(기본 탭: 가격 요약)
- GPT 자문 패키지 옵션 문구 정리: `시나리오 질문 포함` → `GPT 분석 질문 포함`
- 원시 캔들 옵션 통합: `최근 일봉 포함 범위` 단일 선택으로 매핑(`include_raw_candles`, `recent_candle_limit`)
- 투자 관점 기본값을 `스윙(swing)`으로 변경, 선택지는 `스윙/중장기`로 정리
- 뉴스/공시/Risk 포함 옵션 설명 강화: Risk는 뉴스·공시 AI 처리 및 분류 규칙 결과임을 명시
- GPT자문패키지 화면과 가격·캔들관리 화면의 API/역할 중복 여부를 코드 기준으로 검토
