# 운영 시그널 평가 이력

## 목적과 범위

평가 이력은 운영 활성화 이후 새로운 지표 데이터로 단일 지표 시그널을 평가한 LIVE 기록이다. 과거 검증(`SIMULATED`) 결과와 운영 평가(`LIVE`)는 저장·화면·통계에서 분리한다. 경제 흐름 관리와 경제 시나리오 진단은 이 범위에 포함하지 않는다.

## 공식 사용자 용어

| 내부 상태 | 사용자 표시 |
| --- | --- |
| `TREND_INTACT`, `TREND_MAINTAINED` | 추세 유지 |
| `TREND_WEAKENING` | 추세 약화 |
| `BREAK_CANDIDATE` | 추세 이탈 후보 |
| `BREAK_CONFIRMED` | 추세 이탈 확인 |
| `FALSE_BREAK` | 일시 이탈 후 복귀 |
| `REVERSAL_CONFIRMED` | 반전 확인 |
| `TREND_RESUMED` | 기존 추세 재개 |
| `SIDEWAYS` | 횡보 |
| `DATA_INSUFFICIENT` | 데이터 부족 |
| `ERROR` | 평가 오류 |

일시 이탈 후 복귀는 추세 채널을 이탈했지만 설정된 확인 기간 안에 기존 추세 채널 내부로 다시 진입한 상태다. `추세 이탈 시도`는 공식 상태명이 아니며, 추세 이탈 후보의 도움말에서 초기 움직임을 설명할 때만 쓴다.

## 평가와 이벤트

- 평가 이력: 관측값을 기준으로 평가할 때마다 저장한다.
- 상태 전환 이벤트: 직전 LIVE 평가와 현재 평가의 상태가 다를 때만 저장한다.
- `DRAFT`: 운영 평가·이벤트·LIVE Episode를 만들지 않는다.
- `ACTIVE`: 변경된 원천 지표를 참조하는 단일 지표 룰만 자동 평가한다.
- `INACTIVE`: 자동 평가에서 제외하지만 과거 이력은 유지한다.

평가 중복 키는 `signal_definition_id + rule_version + observation_date + evaluation_type`이다. 같은 날짜에 기준 평가가 있으면 PERIODIC 평가는 기준 평가로 갈음해 건너뛴다. MANUAL도 같은 날짜·룰 버전에서 한 건만 허용한다.

## 평가 유형

- `BASELINE`: 신규 운영 활성화 직후의 운영 시작 기준 평가
- `PERIODIC`: 실제 지표 insert/update 후 실행되는 자동 평가
- `MANUAL`: 운영 화면에서 실행한 수동 재평가
- `REPAIR_BASELINE`: 기존 ACTIVE 룰의 누락 기준 평가 보완
- `LEGACY`: 스키마 확장 전 보존된 기존 평가. LIVE 운영 통계에는 합산하지 않는다.

기준 평가는 이전 운영 상태가 없으므로 전환 이벤트를 만들지 않는다.

## 자동 평가 파이프라인

시장 데이터 수집이 끝나면 insert/update가 한 건 이상인 `item_type + item_code`만 변경 집합에 넣는다. 이 집합을 참조하는 ACTIVE `market_signal_trend_models`를 조회해 최신 관측일을 평가한다. 평가 행은 항상 저장하고 상태가 바뀐 경우에만 `market_signal_events`를 생성한다. 수집 응답의 `signal_evaluation`에는 대상·성공·무변화·전환·오류·건너뜀·이벤트·일시 이탈 후 복귀 이벤트 수가 포함된다.

파생지표 재계산과 ACTIVE 복합 지표 재평가는 아직 이 파이프라인에 연결하지 않았다.

## 집계 기준

운영 이후 일시 이탈 후 복귀 횟수의 단일 source of truth는 다음 조건을 만족하는 이벤트 수다.

```sql
market_signal_events.is_live = 1
AND market_signal_events.new_state = 'FALSE_BREAK'
```

같은 상태가 다음 관측일까지 유지돼 평가 행이 두 건이어도 전환 이벤트는 한 건이므로 복귀 횟수는 한 번만 증가한다. 과거 검증 횟수는 `validation_summary_json.state_counts.FALSE_BREAK`에서 별도로 표시한다.

## API

- `GET /market-signals/{id}/evaluation-history`
- `GET /market-signals/{id}/evaluation-history/summary`
- `POST /market-signals/{id}/evaluate-now`
- `POST /market-signals/{id}/repair-baseline`
- `POST /market-signals/repair-baselines`

조회 필터는 `event_only`, `state`, `evaluation_type`, `date_from`, `date_to`, `page`, `page_size`를 지원한다. repair는 `payload.apply=false`일 때 dry-run, `true`일 때 적용하며 이미 기준 평가가 있으면 아무것도 추가하지 않는다.

## Drawer

평가 이력 버튼은 이력 수와 관계없이 Drawer를 연다. Drawer는 운영 요약, 과거 검증과 운영 통계 비교, LIVE 차트, 필터, 최신순 타임라인, empty/error 상태, 도움말, 수동 재평가를 제공한다. 상세 항목을 펼치면 계산값·룰 버전·수집 실행 참조를 확인할 수 있다.

## 기존 ACTIVE 룰 보완

2026-07-22 실제 DB dry-run에서 기준 평가 누락 ACTIVE 정의 6개를 확인했고, 백업 후 `REPAIR_BASELINE`을 생성했다. 두 번째 dry-run은 보완 대상 0개, 기준 평가 보유 6개로 확인돼 idempotent하다. 기존 LEGACY 평가 16건과 이벤트 3건은 유지했다.

## 남은 제한

- 자동 파이프라인은 현재 시장 데이터 통합 수집 서비스가 보고한 원천 INDEX/INDICATOR 변경만 처리한다.
- 파생지표 재계산 결과 전파와 복합 시그널 재평가는 후속 작업이다.
- LIVE 차트 이벤트 마커는 현재 조회 페이지의 상태 전환 평가를 기준으로 표시한다. 더 보기로 불러오지 않은 과거 이벤트는 차트 마커에도 나타나지 않는다.
## 2026-07-22 복합 시그널 운영 자동화 반영

- 복합 시그널 운영 상태와 현재 판정을 별도 필드·배지로 분리했다.
- 검증된 DRAFT만 활성화하며, 활성화 시 이벤트 없는 BASELINE 평가를 저장한다.
- 활성 단일 지표 평가 뒤 관련 ACTIVE 복합 규칙을 관측일별 PERIODIC 평가로 자동 연결한다.
- 지표·모델·조건 역할·조건 문장은 공통 한글 표시 서비스에서 생성한다.
- 상세 설계와 감사 절차는 `docs/market-composite-signal-operation.md`를 따른다.
## 객관적 현상 평가 이력

현상 이력은 원천 복합 평가 ID를 참조하고 상태·점수·근거 개수 집계만 저장한다. 상태 변화 시에만 PHENOMENON 이벤트를 생성하며 원천 evidence JSON을 중복 저장하지 않는다. 상세 정책은 [market-objective-phenomena.md](market-objective-phenomena.md)를 따른다.
