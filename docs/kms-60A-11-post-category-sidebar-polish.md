# 60-A-11 KMS 지식게시판 카테고리 사이드바 디자인 고도화

## 작업 목적
KMS 지식게시판 좌측 카테고리 목록을 단순 버튼 반복 형태에서 탐색 사이드바 형태로 개선해, 카테고리별 지식글 현황과 선택 상태를 더 명확하게 파악할 수 있도록 했다.

## 기존 카테고리 목록 문제점
- 카테고리 row가 단순 박스 반복처럼 보여 탐색 패널의 성격이 약했다.
- 카테고리명과 게시글 수만 표시되어 시각적 식별성이 부족했다.
- 선택 상태는 있었지만 전체적인 사이드바 완성도가 낮았다.
- 0건/1건 이상 카테고리 count badge의 위계가 약했다.

## 사이드바 구조 개선
- `kms-posts-category-panel`을 추가해 기존 필터 사이드바를 카테고리 탐색 패널로 보강했다.
- 상단에 제목과 설명을 배치했다.
- 전체 항목과 카테고리 목록 사이에 divider를 추가했다.
- 하단에는 KMS 설정 이동 안내 박스를 추가했다.

## 카테고리 row 디자인 기준
- 각 row는 dot, category name, count pill로 구성했다.
- 카테고리별 accent dot 색상을 다르게 부여해 식별성을 높였다.
- 선택 row는 배경, border, 좌측 accent bar, count badge로 명확히 구분했다.
- hover 시 border/background/shadow가 부드럽게 변하도록 했다.

## 게시글 수 badge 개선
- count는 오른쪽 pill badge로 표시한다.
- 0건은 muted tone, 1건 이상은 blue accent tone으로 구분한다.
- 선택 row에서는 count badge도 active tone으로 강화한다.

## 전체 항목 구분 방식
- 전체 row를 목록 최상단에 유지했다.
- 전체 row 아래 divider를 추가해 대분류 카테고리와 분리했다.
- 전체 row도 일반 카테고리와 동일한 row 구조를 쓰되 blue accent를 적용했다.

## 스크롤 UX 개선
- 카테고리 목록 내부에만 스크롤이 생기도록 `kms-posts-category-list`에 max-height와 thin scrollbar를 적용했다.
- row가 scrollbar와 붙지 않도록 padding-right를 추가했다.

## KMS 설정 이동 안내
- 사이드바 하단에 “카테고리는 KMS 설정에서 관리합니다.” 안내를 추가했다.
- `KMS 설정으로 이동` 버튼은 `/kms/settings`로 이동한다.

## Backend/DB 변경 여부
- Backend 변경 없음.
- DB 변경 없음.

## 기존 기능 영향 여부
- 카테고리 선택, 전체 선택, 게시글 필터 동작은 기존 `selectCategory` 흐름을 유지한다.
- 게시글 검색/필터/목록/상세 drawer 동작은 변경하지 않았다.

## 남은 이슈
- 실제 브라우저에서 0건/1건 이상 카테고리, hover, mobile width를 육안 확인하는 것이 좋다.