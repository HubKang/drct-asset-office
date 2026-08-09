# Phase5.7 테마관찰우선순위 UX 최종안

## 목적

기존 관찰순위 계산, 자동검증, CURRENT/REFRESHED, 시장지표 보정, Diagnostics 및 ML Shadow 동작을 유지하면서 다음 흐름으로 결과를 읽을 수 있게 한다.

1. 관찰순위와 실제 상대강도의 GAP 확인
2. 가격·수급·확산·기술·완전성 구조 비교
3. 기존 테마 상세 Drawer에서 연결종목과 차트 확인

## 화면 구성

1. 조회·계산 Toolbar와 실행 Metadata
2. 3열 compact 실전검증 진단
3. 데스크톱 한 줄의 Summary 카드 5개
4. `observation_rank ASC` 기준 D+1 Top10 GAP 그래프
5. Top10 테마 구조 비교 Radar 카드
6. 그래프 행 또는 Radar 카드 선택 시 기존 테마 상세 Drawer

기존 목록형 점수 테이블과 관찰 전용 상세 패널은 사용하지 않는다.

## 예측·실측 단위

- 예측값은 공식 실행의 `relative_strength_score`를 사용한다.
- 실측값은 실제 등락률을 직접 사용하지 않는다.
- 실측 상대강도는 같은 대상일의 평가가능 테마 수 `N`과 `actual_rank`로 조회 시 계산한다.

```text
actual_relative_strength = 100 × (N - actual_rank) / (N - 1)
relative_strength_gap = actual_relative_strength - relative_strength_score
```

- `N = 1`이면 유일한 1위를 100으로 처리한다.
- 순위 또는 유니버스 수가 없거나 범위를 벗어나면 실측 상대강도는 `null`이다.
- 실측 전에는 실제값을 0으로 대체하지 않고 `실측 대기`, GAP `-`로 표현한다.
- 계산값은 API response scalar로만 제공하며 DB에 저장하지 않는다.

## GAP 그래프

- Top10 선정과 순서는 항상 당시의 `observation_rank` 기준이다.
- 모든 행은 같은 0·25·50·75·100 축을 사용한다.
- 예측은 테두리 원, 실측은 회전된 사각형 marker로 구분해 색상에만 의존하지 않는다.
- 두 endpoint 사이만 하나의 GAP 구간으로 연결한다.
- 양수 GAP은 실측이 더 강한 경우, 음수 GAP은 실측이 더 약한 경우다.
- 행 전체는 마우스와 키보드로 선택할 수 있고 기존 상세 Drawer를 연다.
- Tooltip에는 예측 관찰점수, 실측 상대강도, GAP 및 존재하는 CURRENT/REFRESHED 점수만 표시한다.

## Radar 카드

- 축 순서는 상단부터 시계방향으로 가격, 수급, 확산, 기술, 완전성이다.
- 모든 축은 최대 100이며 25·50·75·100 grid를 공유한다.
- 완전성의 저장 비율은 표시 시에만 0~100으로 변환한다.
- 결측값을 0으로 대체하지 않는다. 하나라도 결측이면 polygon을 그리지 않고 데이터 부족을 표시한다.
- 중앙에는 테마명과 공식 관찰점수를 표시한다.
- 상단에는 순위와 상태, 하단에는 실측 상대강도와 GAP 또는 실측 대기를 표시한다.
- 카드 전체를 선택하면 기존 테마 상세 Drawer를 연다.

## 반응형

- 1920px: Radar 5열
- 1600px: Radar 4열
- 1366px: Radar 3열
- Summary 5개는 1366px 이상에서 한 줄을 유지한다.
- GAP 그래프는 페이지 가로 오버플로를 만들지 않으며 작은 화면에서는 그래프 컨테이너 내부만 스크롤한다.

## 저장 및 보호 범위

- DB migration 없음
- 신규 원천 데이터 및 JSON 저장 없음
- 기존 scalar 검증 샘플의 `actual_rank`, CURRENT/REFRESHED `observation_score`만 읽음
- 관찰순위 계산식, 자동검증, 시장지표 갱신, ML 및 상세 Drawer 데이터 조회는 변경하지 않음

