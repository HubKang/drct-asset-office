# 59-C / 59-C-RUN ECOS 물가·경기 지표 매핑 및 수집 결과

## 대상 지표

| indicator_code | 지표명 | 카테고리 | 주기 | 차트 | 기준선 |
| --- | --- | --- | --- | --- | --- |
| CPI | 소비자물가지수 | INFLATION / CPI | MONTHLY | BAR_LINE | - |
| PPI | 생산자물가지수 | INFLATION / PPI | MONTHLY | BAR_LINE | - |
| CSI | 소비자심리지수 | ECONOMY / SENTIMENT | MONTHLY | LINE_WITH_BASELINE | 100 |
| BSI_MANUFACTURING | 제조업 BSI | ECONOMY / BSI | MONTHLY | LINE_WITH_BASELINE | 100 |

## 59-C 구현 반영

- `ECOS_DISCOVERY_TARGETS`에 CPI, PPI, CSI, BSI_MANUFACTURING 탐색 설정을 추가했다.
- ECOS `StatisticTableList` 탐색을 첫 1000건 한정에서 `total_count` 기반 페이지 순회 방식으로 확장했다.
- 월간 지표 후보 테스트 기간을 90일이 아니라 최근 약 5년으로 적용하도록 수정했다.
- 월간 ECOS `TIME` 값은 저장 시 `value_date=YYYY-MM-01`, `period_label=YYYY-MM` 형식으로 정리한다.
- 수집값 저장 시 `mom_pct`, `yoy_pct` 컬럼과 `latest_mom_pct`, `latest_yoy_pct` 갱신 경로를 연결했다.
- ECOS 응답 `UNIT_NAME`이 비어 있는 경우 mapping의 `source_unit`을 fallback으로 저장한다.
- 메인 화면의 상단 비교 그룹에는 물가/경기 버튼을 추가하지 않았다.

## 59-C-RUN Provider 상태

| provider | configured | masked_key | status | 원문 key 노출 |
| --- | --- | --- | --- | --- |
| BOK_ECOS | true | YS2B************6ITC | CONFIGURED | 없음 |

## 확정 매핑

| indicator_code | stat_code | stat_name | cycle | item_code1 | item_name1 | item_code2 | item_name2 | test 결과 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| CPI | 901Y009 | 소비자물가지수 | M | 0 | 총지수 | - | - | SUCCESS / 65 rows |
| PPI | 404Y014 | 생산자물가지수(기본분류) | M | *AA | 총지수 | - | - | SUCCESS / 65 rows |
| CSI | 511Y002 | 소비자동향조사(전국, 월, 2008.9~) | M | FME | 소비자심리지수 | 99988 | 전체 | SUCCESS / 66 rows |
| BSI_MANUFACTURING | 512Y013 | 기업경기조사(실적) | M | C0000 | 제조업 | AA | 업황실적BSI | SUCCESS / 66 rows |

## 수집 결과

수집 범위: `2021-01-01` ~ `2026-07-01`

| indicator_code | collect status | saved_count | latest_value | latest_value_date | latest_mom_pct | latest_yoy_pct |
| --- | --- | ---: | ---: | --- | ---: | ---: |
| CPI | SUCCESS | 65 | 119.92 | 2026-05-01 | 0.4607522828 | 3.1392448611 |
| PPI | SUCCESS | 65 | 129.82 | 2026-05-01 | 0.8310679612 | 8.5088599131 |
| CSI | SUCCESS | 66 | 106.6 | 2026-06-01 | 0.4712535344 | -1.8416206262 |
| BSI_MANUFACTURING | SUCCESS | 66 | 79.0 | 2026-06-01 | -1.25 | 12.8571428571 |

## 저장값 확인

| indicator_code | value_date | period_label | value | change_value | change_pct | mom_pct | yoy_pct | source_unit |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| CPI | 2026-05-01 | 2026-05 | 119.92 | 0.55 | 0.4607522828 | 0.4607522828 | 3.1392448611 | 2020=100 |
| PPI | 2026-05-01 | 2026-05 | 129.82 | 1.07 | 0.8310679612 | 0.8310679612 | 8.5088599131 | 2020=100 |
| CSI | 2026-06-01 | 2026-06 | 106.6 | 0.5 | 0.4712535344 | 0.4712535344 | -1.8416206262 | INDEX |
| BSI_MANUFACTURING | 2026-06-01 | 2026-06 | 79.0 | -1.0 | -1.25 | -1.25 | 12.8571428571 | INDEX |

확인 결과:

- `value_date`는 월간 지표 기준 `YYYY-MM-01` 형식이다.
- `period_label`은 `YYYY-MM` 형식이다.
- `change_value`, `change_pct`, `mom_pct`, `yoy_pct`가 저장된다.
- `market_indicators.latest_value`, `latest_value_date`, `latest_mom_pct`, `latest_yoy_pct`가 갱신된다.
- `raw_payload_json` 최근 rows 검사에서 `BOK_ECOS_API_KEY`, `API_KEY`, `AUTH_KEY` 노출 없음.

## 보류/실패

- CPI/PPI/CSI/BSI_MANUFACTURING 모두 test -> activate -> collect 성공.
- 보류 지표 없음.

## 임시 파일 정리

정리 시도 대상:

- `.pycache_verify/`
- `backend/app/**/__pycache__/`

결과:

- 일부 pycache 파일은 Windows 권한 거부로 삭제되지 않았다.
- 기능에는 영향이 없으며, 남은 항목은 임시 bytecode/cache 파일이다.

## 영향 범위 확인

- 기존 환율·금리 지표 수집 로직은 그대로 유지된다.
- 기존 market_indexes 기능은 변경하지 않았다.
- `frontend/src/pages/TradeTrainingPage.tsx`는 변경하지 않았다.
