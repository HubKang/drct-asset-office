# 59-C ECOS 물가/경기 지표 매핑 및 수집 결과

## 대상 지표

| indicator_code | 지표명 | 카테고리 | 주기 | 차트 | 기준선 |
| --- | --- | --- | --- | --- | --- |
| CPI | 소비자물가지수 | INFLATION / CPI | MONTHLY | BAR_LINE | - |
| PPI | 생산자물가지수 | INFLATION / PPI | MONTHLY | BAR_LINE | - |
| CSI | 소비자심리지수 | ECONOMY / SENTIMENT | MONTHLY | LINE_WITH_BASELINE | 100 |
| BSI_MANUFACTURING | 제조업 BSI | ECONOMY / BSI | MONTHLY | LINE_WITH_BASELINE | 100 |

## 반영 내용

- `ECOS_DISCOVERY_TARGETS`에 CPI, PPI, CSI, BSI_MANUFACTURING 탐색 설정을 추가했다.
- ECOS `StatisticTableList` 탐색을 첫 1000건 한정에서 `total_count` 기반 페이지 순회 방식으로 확장했다.
- 월간 지표 후보 테스트 기간을 90일이 아니라 최근 약 5년으로 적용하도록 수정했다.
- 월간 ECOS `TIME` 값은 저장 시 `value_date=YYYY-MM-01`, `period_label=YYYY-MM` 형식으로 정리한다.
- 수집값 저장 시 `mom_pct`, `yoy_pct` 컬럼과 `latest_mom_pct`, `latest_yoy_pct` 갱신 경로를 연결했다.
- 메인 화면의 상단 비교 그룹에는 물가/경기 버튼을 추가하지 않았다. 59-C 범위는 관리 도구의 General Mapping 후보 탐색/테스트 기반이다.

## 후보 판단 정책

| indicator_code | 우선 후보 | 감점/보류 조건 |
| --- | --- | --- |
| CPI | 소비자물가지수, 총지수, 전국, 월간 | 생활물가, 신선식품, 품목별, 전월/전년 변화율 항목 |
| PPI | 생산자물가지수, 총지수, 기본분류, 월간 | 수출입물가, 원재료/중간재/최종재 세부 항목 |
| CSI | 소비자심리지수 자체 항목, 소비자동향, 종합, 월간 | 기대인플레이션, 생활형편/소비지출 전망 등 세부 항목 |
| BSI_MANUFACTURING | 제조업, 업황, BSI, 월간 | 비제조업, 전망, 대기업/중소기업 세부 항목 |

## 실행 상태

- 로컬 샌드박스에서 ECOS API 호출 시 네트워크 연결이 거부되어 실제 후보 테스트, 매핑 저장, 활성화, 1차 수집은 완료하지 못했다.
- 외부 네트워크 허용 재시도도 시스템 사용량 제한으로 승인되지 않았다.
- 따라서 CPI/PPI/CSI/BSI_MANUFACTURING 매핑은 기존처럼 `WAITING` 상태를 유지해야 하며, 검증 성공 전 자동 활성화하지 않는다.

## 다음 실행 절차

1. 네트워크가 허용된 환경에서 아래 요청을 실행한다.

```json
{
  "indicator_codes": ["CPI", "PPI", "CSI", "BSI_MANUFACTURING"],
  "top_table_count": 5,
  "max_item_count": 300
}
```

2. 각 지표별 상위 후보를 `/market-indicators-data/{indicator_code}/provider-mapping/test-candidate`로 테스트한다.
3. `SUCCESS` 후보만 provider mapping에 저장하고 `/provider-mapping/test`를 저장 모드로 통과시킨다.
4. 검증된 매핑만 활성화한 뒤 최근 5년 범위로 수집한다.
5. 실패 지표는 `WAITING` 또는 `ERROR` 상태와 실패 사유를 유지한다.

## 보안

- `.env`의 ECOS API 키는 코드, 문서, raw payload에 기록하지 않는다.
- ECOS raw row 저장 시 `API_KEY`, `AUTH_KEY`, `KEY` 필드는 제거한다.
