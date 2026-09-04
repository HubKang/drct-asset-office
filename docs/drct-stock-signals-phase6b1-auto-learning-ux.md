# DrCT 종목 시그널 Phase 6-B.1

## 사용자 화면

- 상위 탭은 `차트마커 학습 & 검색식 관리`, 내부 기본 화면은 `차트마커 학습`이다.
- 기본 화면은 성공 학습 사례, 실제 학습 사용 수, 검토 권장 수, 추천 준비 상태만 보여준다.
- 기술 정보는 `알고리즘 상세`, 원본 사례는 `전체 사례`에서 요청할 때만 조회한다.
- 검색식 화면의 `선택 검색식 분석 & 검증`은 제거했다. 검색식은 HTS 참조식, DrCT 실행 조건, Version, 관련 마커만 관리한다.

## Primary 학습 정책

추천용 Pattern Signature의 입력은 다음 조건을 모두 만족한 사례다.

1. 복기 결과가 `S`
2. `CORE` Feature가 `READY`
3. 수동 결정이 `EXCLUDE`가 아님

`F`는 알고리즘 상세의 실패 비교에만 사용하고 미판정은 학습하지 않는다. `INCLUDE`는 자동 포함 상태를 확정하고, `EXCLUDE`는 이후 Signature와 LOO 계산에서 제외한다.

Signature V1의 중앙값/IQR/MAD, 거리 상한 3, 거리 중앙값 집계, `100 / (1 + D)` 공식은 유지된다. 자동학습은 저장된 모델을 재훈련하는 작업이 아니라, 최신 S 사례로 런타임 Signature를 다시 계산하는 의미다.

## 검토 권장

- S-only CORE Ready 사례가 5건 이상일 때만 계산한다.
- 사례별 LOO Pattern Distance가 `Q3 + 1.5 × IQR`보다 큰 경우 검토를 권장한다.
- 검토 전 기본값은 자동 포함이다.
- 검토 결정만 `chart_marker_learning_decisions`에 저장한다.
- Feature, Signature, LOO, 유사도, Outlier 결과는 저장하지 않는다.

## 상태 경계

| 실제 학습 사용 S 사례 | 학습 상태 | 추천 상태 |
| --- | --- | --- |
| 0~2 | 사례 부족 | 사례 부족 |
| 3~4 | 초기 학습 | 초기 연구 |
| 5 이상 | 유사도 검증 가능 | 시그널 검증 가능 |

## API

- `GET /drct-stock-signals/marker-learning/{marker_id}/summary`
- `GET /drct-stock-signals/marker-learning/{marker_id}/review-cases`
- `GET /drct-stock-signals/marker-learning/{marker_id}/review-cases/{event_id}`
- `PUT /drct-stock-signals/marker-learning/{marker_id}/review-cases/{event_id}/decision`

기존 Signature, LOO, Outcome, 관련 검색식 API는 알고리즘 상세에서만 지연 호출한다.

## Marker Group 기반 선택 UX

- Marker Group을 기존 정렬 순서대로 Accordion으로 표시하고 한 번에 한 Group만 펼친다.
- 직전 선택 Marker가 있으면 해당 Group을 유지하며, 없으면 첫 활성 Group의 첫 학습 가능 Marker를 선택한다.
- Group 내부 Marker는 반응형 Grid로 표시한다. 1920px에서는 5열, 1440px에서는 4열, 900px에서는 2열이며 Marker 선택 영역에 가로 스크롤을 사용하지 않는다.
- Marker Card에는 이름, 성공 학습 수, 사용자용 학습 상태, 검토 필요 여부만 표시한다. 내부 상태명과 CORE/ENRICHED/F/미판정 정보는 기본 화면에서 숨긴다.
- 선택 Marker 요약은 하나의 Compact Strip으로 구성하고, 학습 현황은 자동학습 상태와 추천 준비·성공 패턴 일관성만 우선 노출한다.
- 검토 사례는 검토 탭 진입 시, Signature/LOO/Feature/Outcome/관련 검색식은 알고리즘 상세 진입 시 지연 조회한다.

`GET /drct-stock-signals/marker-learning/markers`는 Group 화면에 필요한 성공 학습 수, 학습 상태, 검토 수를 기존 Marker 목록과 함께 일괄 반환한다. 서버는 이벤트·결정·가격·지표를 일괄 조회해 Marker 수에 비례하는 상세 API 호출을 만들지 않는다. 이 UX 변경을 위한 신규 테이블이나 Migration은 없다.
