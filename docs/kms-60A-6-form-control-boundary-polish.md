# KMS 등록/수정 Form 입력항목 경계선 강화

## 작업 목적

KMS 지식글 등록/수정 화면에서 제목, 카테고리, 중요도, 학습 상태, 요약, 본문, 태그, 참고 URL 입력 영역이 평상시에도 명확한 입력 박스로 보이도록 form control 스타일을 강화했다.

## 현재 문제점

- input/select/textarea의 기본 경계가 약해 배경과 섞여 보였다.
- focus 상태에서는 식별되지만 평상시 입력 가능 영역인지 알아보기 어려웠다.
- Rich Editor는 toolbar와 본문은 구분되지만 전체 입력 박스의 위계가 약했다.
- 등록 화면과 수정 drawer에서 동일한 입력 UI 기준이 필요했다.

## Form Control 공통 스타일 기준

- KMS 전용 `.kms-form-control`에 명확한 흰색 배경, 회색 border, 8px radius, focus ring을 적용했다.
- hover 시 border를 살짝 진하게 변경해 입력 가능한 영역임을 드러냈다.
- disabled/readOnly 상태는 옅은 회색 배경과 muted text로 구분했다.
- placeholder 색상을 흐리게 정리했다.

## 등록 화면/수정 Drawer 공통 적용

- `.kms-form-section`의 배경과 border를 조정해 섹션 카드와 입력칸의 위계를 분리했다.
- `.kms-form-field`에 내부 border/background/padding을 적용해 label과 control이 하나의 field로 보이도록 했다.
- focus-within 상태에서 field 단위의 focus ring이 표시되도록 했다.
- 기존 등록 화면, 수정 drawer, 상세 수정 화면은 같은 KMS form class를 사용하므로 동일 스타일이 적용된다.

## Rich Editor 경계 강화

- `.kms-editor-shell`의 border를 더 명확하게 조정했다.
- hover/focus-within 상태를 추가해 본문 입력 중인 영역을 쉽게 식별하도록 했다.
- toolbar와 content 사이 divider 색상을 보강했다.
- 기존 selection 안정화, resetKey, undo/redo, 표, 이미지 기능 로직은 변경하지 않았다.

## 기존 기능 영향 여부

- 게시글 등록/수정/조회 로직은 변경하지 않았다.
- KMS Rich Editor의 기능 로직은 변경하지 않고 CSS만 보강했다.
- 기존 게시글 데이터와 저장 형식은 변경하지 않았다.

## Backend/DB 변경 여부

- backend 변경 없음.
- DB 구조 변경 없음.

## 남은 이슈

- 브라우저별 기본 select 화살표 렌더링 차이는 남을 수 있다.
- 추후 KMS 전용 디자인 토큰이 정리되면 form 색상 값을 변수화할 수 있다.
