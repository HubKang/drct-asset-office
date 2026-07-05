# 60-A-4 KMS 지식 등록 UX 개선 및 Rich HTML Editor 도입

## 작업 목적

KMS 지식 게시판의 등록/수정 폼을 섹션형 입력 구조로 개선하고, 본문 입력을 일반 textarea에서 Rich HTML Editor로 교체했다. 주식과 자본시장 학습 내용을 제목, 목록, 인용, 표, 링크, 이미지 등으로 구조화해 저장하고 상세 화면에서 HTML 형태로 읽을 수 있게 하는 것이 목적이다.

## 기존 문제점

- 제목, 요약, 본문, 태그, 참고 URL 입력 영역의 경계가 약했다.
- 등록 패널과 검색/필터 패널의 구분은 개선됐지만, 등록 폼 내부는 긴 단일 입력 영역처럼 보였다.
- 본문이 textarea 기반이라 표, 목록, 인용, 링크, 이미지 같은 학습 기록용 서식을 표현하기 어려웠다.
- 상세 화면은 본문을 plain text `pre`로 표시해 HTML 학습 노트를 읽기 좋게 렌더링할 수 없었다.

## 지식 등록 Form UI 개선 내용

등록/수정 폼을 다음 섹션으로 나눴다.

- 기본 정보: 제목, 카테고리, 중요도, 학습 상태
- 요약: 목록과 상세 상단에서 사용할 짧은 설명
- 본문 작성: Tiptap 기반 Rich HTML Editor
- 분류/참고 정보: 태그, 참고 URL, 고정 여부
- 작업 버튼: 저장, 취소 또는 비활성화

각 섹션은 카드형 경계선, 섹션 제목, 설명, 명확한 입력 필드 border/background/padding을 갖도록 구성했다.

## Rich Editor 선택 이유

지시문 기준에 따라 Tiptap을 사용했다. Tiptap은 React/TypeScript 환경에서 확장 단위가 명확하고, 링크/이미지/표 같은 기능을 점진적으로 추가하기 쉽다.

설치 패키지:

- `@tiptap/react`
- `@tiptap/starter-kit`
- `@tiptap/extension-link`
- `@tiptap/extension-image`
- `@tiptap/extension-table`
- `@tiptap/extension-table-row`
- `@tiptap/extension-table-cell`
- `@tiptap/extension-table-header`
- `@tiptap/extension-text-style`
- `@tiptap/extension-color`
- `@tiptap/extension-underline`
- `@tiptap/extension-placeholder`
- `dompurify`

## 지원 기능

- 문단
- 제목 1
- 제목 2
- 굵게
- 기울임
- 밑줄
- 글머리 목록
- 번호 목록
- 인용
- 링크 추가/해제
- 표 삽입
- 행 추가
- 열 추가
- 로컬 이미지 파일 첨부
- 실행 취소
- 다시 실행
- 줄바꿈 유지
- 상세 화면 HTML 렌더링

## 저장 구조 설명

이번 작업은 DB 구조를 변경하지 않았다. 현재 KMS API와 테이블의 `content` 필드를 그대로 사용해 sanitize된 HTML 문자열을 저장한다.

- `content`: sanitize된 HTML을 저장하는 호환 필드
- `content_format`: 프론트 payload에 `html`로 포함하지만, 현재 백엔드가 저장하지 않으면 무시된다.
- `content_html`: 프론트 payload에 sanitize된 HTML을 포함하지만, 현재 백엔드가 저장하지 않으면 무시된다.
- `content_json`: 이번 작업에서는 저장하지 않는다.
- `content_text`: 검색/미리보기용 plain text를 프론트 payload에 포함하지만, 현재 백엔드가 저장하지 않으면 무시된다.

백엔드가 아직 신규 필드를 반환하지 않는 상황에서도 화면은 기존 `content` fallback으로 동작한다.

## 이미지 첨부 구조

이번 1차 구현에서는 서버 업로드 API와 첨부 테이블을 만들지 않았다. 에디터의 이미지 버튼은 로컬 파일 선택창을 열고, 선택한 이미지를 Data URL로 본문 HTML에 삽입한다.

향후 확장 시 권장 구조:

- `kms_attachments` 테이블 추가
- `POST /kms/uploads/image` API 추가
- 서버 저장 파일 URL을 editor 이미지 `src`로 삽입
- 게시글 저장 후 nullable `post_id` 첨부를 게시글과 연결

## URL 자동 링크 정책

본문에 `https://...`, `http://...`, `www...` 형식의 URL을 일반 텍스트로 입력해도 상세 화면 렌더링 시 자동으로 링크로 변환한다. 기존에 에디터 링크 버튼으로 만든 링크는 그대로 유지한다.

## HTML sanitize 정책

상세 렌더링과 저장 전 처리에 DOMPurify를 사용한다.

허용 태그:

- `p`, `h1`, `h2`, `h3`
- `strong`, `em`, `u`
- `ul`, `ol`, `li`
- `blockquote`
- `table`, `thead`, `tbody`, `tr`, `th`, `td`
- `a`, `img`, `br`, `span`

허용 속성:

- `href`, `src`, `alt`, `title`, `target`, `rel`, `colspan`, `rowspan`

상세 화면은 sanitize된 HTML만 `dangerouslySetInnerHTML`로 렌더링한다.

## 기존 게시글 호환 정책

기존 plain text 본문은 에디터/상세 렌더링 시 HTML escape 후 줄바꿈을 `<br>`로 변환한다. 따라서 기존 게시글 본문이 HTML로 오인되어 깨지는 것을 줄이고, 새 HTML 본문과 같은 표시 컴포넌트를 사용할 수 있다.

## backend/DB 변경 여부

- backend 변경 없음
- DB migration 추가 없음
- 기존 KMS 테이블 삭제/초기화 없음
- 기존 게시글 데이터 손실 없음

## 남은 이슈

- 이미지 업로드 API와 첨부 테이블은 미구현이다.
- `content_json`, `content_html`, `content_text`의 영구 저장은 백엔드/DB 확장 작업이 필요하다.
- 현재 백엔드 본문 검색은 `content` HTML 문자열 대상으로 수행된다. 더 정확한 검색은 향후 `content_text` 저장 후 해당 컬럼 우선 검색으로 개선하는 것이 좋다.
- npm install 후 audit 경고가 보고되었다. 별도 보안 점검 작업에서 패키지 영향 범위를 확인해야 한다.

## 향후 확장 방향

- 이미지 파일 업로드
- 표 템플릿 삽입
- Markdown/PDF export
- 관련 지식 연결
- KMS 글 작성 템플릿
- GPT 요약/정리 요청문 생성
