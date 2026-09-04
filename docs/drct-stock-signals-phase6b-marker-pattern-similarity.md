# DrCT 종목 시그널 Phase 6-B — Marker Pattern Signature + Pattern Similarity V1

## 목적과 의미

Phase 6-B는 현재 또는 특정 Marker 사례가 과거의 같은 Marker 사례들과 얼마나 비슷한지를 계산한다. 결과 이름은 `패턴 유사도`이며 성공확률, 상승확률, 매수확률 또는 추천확률이 아니다. 임의 Threshold와 자동 필터는 적용하지 않는다.

Pattern Dataset은 `S + F + 미판정` 전체다. S/F는 사용자가 기록한 Marker 모양의 품질이 아니라 사후 복기 Metadata이므로 Signature 생성, 거리, LOO 계산에서 동일하게 취급한다. Quality Model은 Phase 6-C의 별도 모델로 유지한다.

## 버전과 Feature Profile

- Feature Schema: V1
- Marker Pattern Signature: V1
- Pattern Similarity Algorithm: V1
- Primary: CORE 16 Feature
- SHADOW: ENRICHED 20 Feature
- CORE와 ENRICHED 점수는 결합하지 않는다.
- 검색식 Reference, Rule Match, D+5/D+10/D+20, MFE/MAE는 입력 Feature나 Weight로 사용하지 않는다.
- Shape Feature는 이번 버전에 추가하지 않았다.

## Signature와 Robust Scale

Marker와 Profile별 Ready 사례에서 각 Feature의 `median`, `Q1`, `Q3`, `IQR`, `MAD`, `min`, `max`, `valid_count`를 계산한다.

Scale 우선순위는 다음과 같다.

1. `IQR > 1e-9`: `scale = IQR`
2. IQR가 0에 가깝고 `MAD > 1e-9`: `scale = 1.4826 × MAD`
3. IQR와 MAD가 모두 0에 가까움: `CONSTANT_FEATURE`

Constant Feature는 Signature와 UI에는 남기지만 거리 계산에서는 제외한다. 임의의 `scale = 1`을 넣지 않으며 결측값을 0이나 평균으로 대체하지 않는다.

## 거리와 유사도

Feature 거리에는 같은 가중치를 적용한다.

```text
d_i = min(abs(x_i - median_i) / robust_scale_i, 3.0)
D = median(d_1 ... d_n)
Pattern Similarity = 100 / (1 + D)
```

응답에는 Pattern Distance와 Pattern Similarity를 함께 제공한다. Similarity V1의 의미를 향후 다른 산식으로 바꾸지 않고, 변경이 필요하면 알고리즘 버전을 올린다.

## Leave-One-Out 검증

Ready 사례가 N건이면 각 사례를 한 번씩 제외하고 나머지 N-1건으로 Signature를 다시 만든다. 제외 사례는 Median, IQR, MAD 계산에 참여하지 않는다. 각 LOO 결과에서 `min`, `P10`, `P25`, `median`, `P75`, `P90`, `max`, `IQR`을 런타임 집계하며 실제 n을 함께 반환한다.

학습 상태는 선택 Profile의 Ready 사례 수로 구분한다.

- 0~2: `INSUFFICIENT` / 사례 부족 — Signature Preview만 가능, LOO 비활성
- 3~4: `EXPERIMENTAL` / 초기 실험 — LOO는 참고용
- 5 이상: `TESTABLE` / 유사도 검증 가능 — 운영 적용 가능을 뜻하지 않음

## API

- `GET /drct-stock-signals/marker-learning/{marker_id}/pattern-signature?feature_profile=CORE`
- `POST /drct-stock-signals/marker-learning/{marker_id}/similarity-validation`
- `GET /drct-stock-signals/marker-learning/{marker_id}/similarity-cases/{event_id}?feature_profile=CORE`

기본 Signature/LOO 목록 응답에는 사례별 16/20개 Feature Distance를 넣지 않는다. 사례 상세 요청에서만 Pattern 차이가 큰 Top 5 Feature를 결정론적으로 계산한다.

## UI

`차트마커 학습 > 패턴 연구` 안에 다음 Sub Navigation을 제공한다.

- 패턴 기준: 상태, 사례 수, 버전, Active/Constant Feature, 한국어 Feature명과 중간 50% 범위
- 유사도 검증: LOO 설명, Compact Percentile Range, 낮은 유사도순 사례, S/F/미판정 Metadata, Top 차이 Feature 상세
- Feature 분포: Min–Q1–Median–Q3–Max Range UI

CORE와 ENRICHED SHADOW는 별도 전환한다. 유사도는 Blue/Neutral로 표시하고 S/F 배지는 별도 Green/Red Metadata로 표시한다.

## 운영 DB Acceptance 결과 (2026-09-02)

| Marker | Profile | Ready / 상태 | Active / Constant | LOO n | Min | P25 | Median | P75 | Max |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 이평조정 5선 | CORE | 13 / TESTABLE | 16 / 0 | 13 | 42.64 | 54.35 | 59.44 | 74.56 | 91.46 |
| 이평조정 5선 | ENRICHED | 10 / TESTABLE | 20 / 0 | 10 | 42.22 | 48.31 | 56.93 | 65.71 | 80.05 |
| 이평조정 10선 | CORE | 7 / TESTABLE | 16 / 0 | 7 | 44.25 | 47.75 | 55.79 | 64.22 | 74.81 |
| 이평조정 10선 | ENRICHED | 5 / TESTABLE | 20 / 0 | 5 | 41.05 | 51.85 | 53.40 | 59.50 | 66.78 |
| 이평조정 20선 | CORE | 6 / TESTABLE | 16 / 0 | 6 | 33.15 | 41.72 | 62.91 | 66.82 | 70.65 |
| 이평조정 20선 | ENRICHED | 6 / TESTABLE | 20 / 0 | 6 | 34.51 | 43.48 | 62.58 | 67.04 | 72.86 |
| 이평조정 60선 | CORE | 2 / INSUFFICIENT | 16 / 0 | 0 | - | - | - | - | - |
| 이평조정 60선 | ENRICHED | 1 / INSUFFICIENT | 0 / 20 | 0 | - | - | - | - | - |

네 Marker의 Dataset+CORE/ENRICHED 계산은 119.84ms였고 Marker별 Dataset 조회는 고정 5 SQL이다. 사례 수에 따른 SQL 증가는 없어 Case N+1이 발생하지 않는다. 활성 Marker 25개의 CORE Signature와 TESTABLE LOO를 순차 계산한 참고 측정은 337.04ms, TESTABLE Marker는 12개였다.

## 저장 정책

신규 DB Table과 Migration은 없다. Signature, Feature Matrix, Median/IQR/MAD, Similarity, LOO 사례/Percentile, Pattern Cohesion을 DB·브라우저 영구 Cache에 저장하지 않는다. API의 `storage_policy`는 `RUNTIME_ONLY`이며 요청 안에서 만든 Dataset만 메모리에서 재사용한다.

## Phase 6-C 준비 조사

실제 Ready 사례에서 S/F는 Signature에 영향을 주지 않았고 Metadata별 CORE LOO 평균은 다음과 같았다. 이는 품질 판정이 아니라 분포 관찰값이다.

- 5선: S 70.93, F 58.43, 미판정 74.56
- 10선: S 58.15, F 55.39
- 20선: S 59.06, F 48.08
- 60선: LOO 미실행

현재 기존 Logistic 최소조건(`S>=5`, `F>=5`, 총 15건)을 만족하는 Marker는 없다. S Prototype 최소 S 5건만 충족하는 Marker는 12, 13, 24, 28번이지만 F가 0건이어서 S/F Contrast나 Quality 판별에 사용할 수 없다. Phase 6-C는 Marker-only Baseline, 심한 S/F 불균형, Profile별 가용 수, OOS 검증을 먼저 다뤄야 하며 Pattern Similarity와 Quality Score를 별도 값으로 유지해야 한다.
