# 복합 지표 시그널 운영 자동화

## 목적

복합 지표 시그널의 운영 상태와 현재 평가 상태를 분리하고, 검증된 초안만 운영할 수 있도록 수명주기를 고정한다. 단일 지표의 운영 평가가 완료되면 같은 관측일에 해당 지표를 참조하는 운영 중 복합 규칙을 자동 평가한다.

## 상태 체계

- 운영 상태: `DRAFT`(초안), `ACTIVE`(운영), `INACTIVE`/`ARCHIVED`(중지)
- 현재 판정: `WAITING`, `TRIGGERED`, `CONFIRMING`, `CONFIRMED`, `STRENGTHENING`, `WEAKENING`, `RELEASED`, `OPPOSED`, `INVALIDATED`, `DATA_INSUFFICIENT`, `ERROR`
- 화면은 항상 `운영 상태: …`와 `현재 판정: …`을 별도 배지로 표시한다.

## 운영 수명주기

1. 조건 확인
2. 초안 생성
3. 1년·3년·5년 과거 검증
4. 운영 활성화 승인

운영 활성화는 `DRAFT`이면서 검증 완료된 규칙에만 허용된다. 활성화 시 `BASELINE` 평가를 한 번 저장하되 상태 전환 이벤트는 만들지 않는다. 중지된 규칙은 바로 재활성화하지 않고 새 버전 초안을 만든 뒤 같은 절차를 거친다.

## 자동 평가 연결

- 활성 단일 지표가 `MANUAL` 또는 `PERIODIC` 평가를 새로 저장하면 변경된 `(item_type, item_code)`를 수집한다.
- 해당 코드를 조건으로 참조하는 `ACTIVE` 복합 규칙만 선택한다.
- `(signal_definition_id, rule_version, observation_date, evaluation_type=PERIODIC)` 단위로 중복을 방지한다.
- 상태가 실제로 달라졌을 때만 `market_signal_events`에 이벤트를 남긴다.
- `DRAFT`, `INACTIVE`, `ARCHIVED` 규칙은 자동 평가하지 않는다.

## 한글 표시 해석

`backend/app/services/market_signal_display_service.py`가 지표명, 모델명, 조건 역할, 조건 문장을 공통으로 해석한다. 이름은 `market_indexes`, `market_indicators`, `market_signal_model_profiles`의 값을 우선 사용하고, 공통 카탈로그를 거쳐 마지막에만 원본 코드를 사용한다. 내부 코드·연산자·임계값은 보존하며 화면에서는 툴팁의 기술 정보로 제공한다.

## 감사와 복구

`POST /market-signals/composite/audit`는 기본적으로 드라이런이다. 정의 수, 상태별 수, 평가 유형별 수, 한글명 누락, 운영 규칙의 기준 평가 누락을 보고한다. `{ "payload": { "apply": true } }`일 때만 운영 중 기준 평가 누락을 `REPAIR_BASELINE`으로 보완한다. 실행 전 DB 백업이 필수이며 규칙·평가·이벤트·버전은 삭제하지 않는다.

## 검증 기준

- 과거 검증 응답: 시작 조건 발생, 현상 확인, 확인율, 미확정 시작, 반대/무효화, 해제, 데이터 부족, 지속 기간, 최신 표본
- 운영 이력: `BASELINE`, `PERIODIC`, `MANUAL`, `REPAIR_BASELINE` 구분
- 반응형 화면: 1920×1080, 1440×900, 1280×800, 768×800
## 객관적 현상 전파

ACTIVE 복합 시그널의 LIVE 평가 저장 후 객관적 현상 집계가 자동 갱신된다. DRAFT는 참고 preview만 제공하고 INACTIVE는 자동 평가에서 제외한다. 상세 정책은 [market-objective-phenomena.md](market-objective-phenomena.md)를 따른다.
