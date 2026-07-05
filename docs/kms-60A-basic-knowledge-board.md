# 60-A DrCT KMS MVP 구축

## 작업 목적

주식과 자본시장 공부 내용을 DrCT 내부에 장기적으로 축적, 정리, 탐색하기 위한 KMS MVP를 추가했다. 이번 단계는 지식 게시글, 카테고리, 태그 정규화, 태그 기반 검색, KMS 홈 대시보드 구성을 중심으로 한다.

## 신규 메뉴 구조

- DrCT KMS
  - KMS 홈: `/kms`
  - 지식 게시판: `/kms/posts`
  - 지식글 상세: `/kms/posts/:postId`
  - KMS 설정: `/kms/settings`

기존 매매관리, 시스템 메뉴 구조는 변경하지 않았다.

## 신규 테이블 구조

- `kms_categories`: KMS 카테고리 트리 관리
- `kms_posts`: KMS 지식 게시글 관리
- `kms_tags`: 태그 마스터 및 사용 횟수 관리
- `kms_post_tags`: 게시글-태그 N:M 연결

테이블은 `CREATE TABLE IF NOT EXISTS` 방식으로 비파괴 생성되며, 기본 대분류는 `INSERT OR IGNORE`로 중복 생성을 방지한다.

## API 목록

- `GET /kms/home/summary`
- `GET /kms/categories`
- `POST /kms/categories`
- `PUT /kms/categories/{category_id}`
- `DELETE /kms/categories/{category_id}`
- `GET /kms/posts`
- `GET /kms/posts/{post_id}`
- `POST /kms/posts`
- `PUT /kms/posts/{post_id}`
- `DELETE /kms/posts/{post_id}`
- `GET /kms/tags`
- `GET /kms/posts/search-by-tags`

삭제 API는 실제 삭제가 아니라 `is_active=false` 처리한다.

## KMS 홈 구성

- 전체 지식글, 복습 필요, 실전 적용 후보, 핵심 지식, 최근 7일 작성/수정 요약 카드
- 인기 태그 기반 통합 검색
- AND/OR 태그 검색
- 대분류 카테고리 카드
- 최근 작성/수정 지식
- 복습 필요 및 실전 적용 후보 지식

## 대분류 카드 요약 기준

각 카테고리 카드는 전체 글 수, 핵심 글 수, 복습 필요 글 수, 실전 적용 후보 수, 최근 7일 작성/수정 수, 대표 태그, 마지막 수정일을 표시한다.

## 태그 검색 구조

태그 검색은 `kms_tags`, `kms_post_tags`를 기반으로 수행한다.

- AND: 선택된 태그를 모두 포함한 게시글
- OR: 선택된 태그 중 하나 이상 포함한 게시글

## 태그 정규화 구조

게시글 저장/수정 시 태그는 다음 규칙으로 정규화된다.

- 쉼표 기반 입력 허용
- 앞쪽 `#` 제거
- trim 처리
- 빈 태그 제거
- 중복 태그 제거
- 기존 태그 재사용
- 신규 태그 자동 생성
- `kms_post_tags` 연결 갱신
- `use_count` 재계산

## 기존 기능 영향 여부

기존 DB 삭제, 기존 테이블 삭제, 기존 화면 삭제는 수행하지 않았다. KMS 신규 테이블과 신규 라우트만 추가했다. `TradeTrainingPage.tsx`는 변경하지 않았다.

## 향후 확장 방향

- 지식맵 화면
- 관련 게시글 연결
- 매매기법 연결
- 매매훈련 복기 연결
- GPT 지식 정리 요청문 생성
- 마인드맵 가져오기 보조 기능
