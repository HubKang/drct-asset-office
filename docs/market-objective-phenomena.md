# 객관적 현상 결과 해석 계층

## 목적과 계층

객관적 현상은 복합 룰을 편집하는 화면이 아니다. 단일 지표 시그널이 개별 전환을, 복합 지표 시그널이 관련 전환의 동시 발생을 판단한다면 객관적 현상은 그 결과를 사람이 이해할 수 있는 현재 시장의 관찰 사실로 정리한다. 향후 경제 흐름은 이 관찰 사실의 전달 경로를, 경제 시나리오는 흐름 지속 시 가능한 결과를 다룬다.

객관적 현상 화면에서는 Trigger·Confirm 편집, 가중치 변경, 룰 버전 변경, 운영 활성화·중지를 제공하지 않는다.

## 기존 구조 감사

기존 구현은 `market_signal_definitions`의 COMPOSITE 행을 객관적 현상 정의로 직접 사용했다. `/market-signals/overview`와 `/market-signals/phenomena`는 복합 조건을 매번 다시 계산했고, 현상명은 복합 시그널명과 같았다. 별도 정의·평가 테이블은 없었으며 `market_signal_episodes`가 단순 스냅샷 역할만 했다. 근거·반대 근거·데이터 부족은 복합 평가 결과의 JSON을 그대로 나눠 표시했고 다음 확인은 공통 문구였다.

이번 변경은 복합 정의와 평가를 원천으로 유지하면서 현상 표현과 집계 상태만 별도 관리한다. 복합 평가 상세를 복제 저장하지 않는다.

## 저장 구조

- `market_objective_phenomena`: 현상 코드, 원천 복합 시그널 ID, 표시 제목, 분류, 운영 등급, 현재 상태와 집계 카운트
- `market_objective_phenomenon_evaluations`: 원천 `market_signal_evaluations.id` 참조, 상태·점수·근거 개수·쉬운 설명만 저장
- `market_objective_phenomenon_flow_candidates`: 향후 경제 흐름 연결을 위한 후보 메타 정보

원천 evidence JSON이나 시계열·시뮬레이션 표본은 현상 테이블에 중복 저장하지 않는다. 현상 평가 중복 키는 `phenomenon_id + source_composite_evaluation_id + evaluation_type`이다.

## 정식 현상과 참고 현상

- 정식 현상(`OFFICIAL`): 원천 복합 룰이 ACTIVE이고 저장된 LIVE 평가가 있으며 필수 데이터 부족이 없는 경우
- 참고 현상(`REFERENCE`): DRAFT 룰의 현재 preview 또는 과거 검증 기반 결과
- INACTIVE 원천: 기본 목록에서 제외하며 명시적인 원천 상태 필터로만 조회
- 데이터 부족: 판단 보류 성격으로 표시하고 경제 흐름 후보 등록을 차단

참고 현상은 정식 오늘의 전환, LIVE 현상 이력, 경제 흐름 후보 자동 입력에 사용하지 않는다.

## 현상 상태

| 내부 상태 | 사용자 표시 |
|---|---|
| NOT_EVALUATED | 미평가 |
| OBSERVED | 징후 관찰 |
| CONFIRMING | 확인 진행 |
| CONFIRMED | 현상 확인 |
| WEAKENING | 현상 약화 |
| RELEASED | 현상 해제 |
| OPPOSED | 반대 근거 우세 |
| INVALIDATED | 무효화 |
| DATA_INSUFFICIENT | 데이터 부족 |
| ERROR | 평가 오류 |

운영 상태(초안·운영·중지)와 현상 상태는 서로 다른 배지로 표시한다.

## 제목과 사용자 편집

`source_title`은 원천 복합 시그널명을 보존하고 `display_title`은 관찰 사실 중심의 사용자 표시 제목으로 분리한다. 알려진 초기 4개 룰에는 비파괴적인 제목 제안을 적용했다. 사용자는 표시 제목, 분류, 태그, 메모, 중요도만 수정할 수 있다. 정량 점수, 현상 상태, 근거 판정, 원천 평가 결과는 PATCH API에서 거부한다.

## 관찰 근거·반대 근거·데이터 부족

관찰 근거에는 실제 충족된 조건만 표시한다. 반대 근거에는 OPPOSING 또는 INVALIDATION 중 실제 발생한 조건만 표시한다. 데이터 부족에는 관측값 부재·최신성 부족 등 평가 불가능 항목과 사유를 표시한다. 카드에는 최대 3개를 요약하고 상세 Drawer에서 한글 지표명, 조건 역할, 최신 판정, 기준일, 데이터 품질과 접힌 기술 조건을 확인한다.

## 다음 확인

우선순위는 미충족 시작·확인 조건, 무효화 조건, 반대 근거, 지속성 확인, 데이터 갱신이다. 카드에서는 최대 3개만 표시한다.

## 평가 이력과 자동 전파

ACTIVE COMPOSITE의 LIVE 평가가 저장되면 연결된 정식 현상 집계를 같은 트랜잭션에서 갱신한다. 현상 이력은 원천 복합 평가 ID를 참조한다. 상태가 바뀐 경우에만 `PHENOMENON_*` 이벤트를 생성해 오늘의 전환 조회 기반으로 사용한다. DRAFT는 화면 preview만 제공하고 LIVE 현상 이력과 이벤트를 생성하지 않는다. INACTIVE는 자동 평가에서 제외하고 기존 이력을 보존한다.

## 경제 흐름 후보

정식 현상이며 상태가 징후 관찰·확인 진행·현상 확인·현상 약화이고 필수 데이터 부족이 없을 때만 CANDIDATE를 등록할 수 있다. 이번 단계는 후보 등록과 REMOVED 전환만 구현한다. 경제 흐름 그래프나 노드는 생성하지 않는다.

## GPT 보조 진단

GPT 입력은 표시 제목, 현재 상태, 관찰·반대·부족 근거, 다음 확인, 최근 변화와 DrCT 점수로 제한한다. 결과는 전달 경로, 대안 가설, 반대 시나리오, 추가 확인 지표, 파급 가능성과 한계만 제안한다. GPT는 상태·점수·룰·조건·운영 여부를 변경하거나 투자 추천을 할 수 없다. 현재 구현은 prompt 생성 방식이며 원천 평가에 저장하지 않는다.

## API

- `GET /market-signals/phenomena`
- `GET /market-signals/phenomena/overview`
- `GET /market-signals/phenomena/{id}`
- `PATCH /market-signals/phenomena/{id}`
- `POST /market-signals/phenomena/{id}/evaluate-now`
- `GET /market-signals/phenomena/{id}/evaluation-history`
- `GET /market-signals/phenomena/{id}/evaluation-history/summary`
- `POST /market-signals/phenomena/{id}/flow-candidate`
- `POST /market-signals/phenomena/{id}/flow-candidate/remove`
- `GET /market-signals/phenomena/{id}/gpt-diagnosis-prompt`
- `POST /market-signals/phenomena/repair`

목록 필터는 `grade`, `state`, `category`, `flow_candidate`, `source_status`, `search`를 지원한다.

## 기존 데이터 보완

`POST /market-signals/phenomena/repair`의 `payload.apply`로 dry-run과 idempotent apply를 구분한다. 기존 복합 룰마다 현상 정의를 INSERT OR IGNORE로 연결하고 사용자 확정 제목은 덮어쓰지 않는다. 기존 평가·이벤트·버전·episode를 삭제하지 않는다.

2026-07-23 최종 감사 기준 실제 DB 현황: 총 10개 현상 정의와 10개 원천 복합 룰, DRAFT 원천 9개, INACTIVE 원천 1개, ACTIVE 원천 0개, preview 기준 현상 확인 2개, 정식 현상 0개, 참고 현상 10개, 데이터 부족 0개, 표시 제목 중복 4개, 원천 룰명과 동일한 제목 6개다. 알려진 초기 4개 룰의 제목 제안을 적용했다.

## 제한

- 경제 흐름 노드·그래프 편집은 후속 작업이다.
- GPT API 직접 호출과 보조 진단 결과 저장은 구현하지 않았다.
- 기존 DRAFT 룰은 참고 preview이므로 정식 평가 이력이 없다.
- viewport 자동 스크린샷 검증은 별도 브라우저 실행 환경에서 수행해야 한다.
