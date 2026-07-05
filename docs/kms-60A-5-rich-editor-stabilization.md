# 60-A-5 KMS Rich Editor 안정화 및 지식게시판 편집 UX 보정

## 작업 목적

KMS 지식글 수정 drawer 안에서 Tiptap Rich Editor의 커서 이동, toolbar focus, 표 편집 UX를 안정화했다. 사용자가 이미지 위쪽이나 표 주변에서 입력할 때 커서가 문서 끝 또는 이미지 아래로 이동하는 문제를 줄이고, 표 편집 버튼과 compact table 스타일을 추가했다.

## 사용자 확인 문제

- 이미지 위쪽에서 입력하다가 커서가 이미지 아래로 이동했다.
- toolbar 버튼 클릭 후 selection이 유지되지 않았다.
- 표가 본문 대비 크게 보였다.
- 표 삭제 기능이 없었다.
- “번호” 버튼명이 모호했다.
- 다시실행 버튼이 항상 눌리는 것처럼 보였고 동작 여부가 불명확했다.

## 커서 이동 원인 분석

기존 `KmsRichEditor`는 `value`가 변경될 때마다 `editor.commands.setContent()`를 다시 실행할 수 있는 구조였다. 에디터 입력 시 parent state가 바뀌고, 그 값이 다시 editor content로 들어오면 Tiptap selection이 초기화되거나 문서 끝으로 이동할 수 있다.

## setContent 반복 호출 여부 점검 결과

- `useEditor({ content })`는 초기 렌더링에만 사용한다.
- `resetKey` prop을 추가해 게시글 변경 또는 편집 대상 변경 시에만 `setContent()`를 실행한다.
- 같은 게시글을 입력 중일 때 parent state가 바뀌어도 `setContent()`가 반복 호출되지 않는다.
- editor가 focused 상태일 때는 외부 content 동기화를 수행하지 않는다.

## toolbar focus/selection 보정 내용

- 모든 toolbar 버튼에 `type="button"`을 유지했다.
- toolbar 버튼 `onMouseDown`에서 `event.preventDefault()`를 적용해 버튼 클릭이 editor selection을 빼앗지 않도록 했다.
- 명령 실행 시 `focus('end')` 또는 끝 selection 강제 이동을 사용하지 않았다.
- 명령 후 별도 `editor.commands.focus()`를 다시 호출하지 않도록 정리했다.

## 번호목록 버튼 명칭 변경 내용

- 기존 `번호` 버튼을 `번호목록`으로 변경했다.
- tooltip에 “순서 있는 목록을 켜거나 끕니다.” 설명을 추가했다.
- 기능은 `toggleOrderedList()`로 유지했다.

## redo 수정 내용

- `실행취소` 버튼은 `editor.can().undo()` 기준으로 활성화한다.
- `다시실행` 버튼은 `editor.can().redo()` 기준으로 활성화한다.
- 되돌릴/다시 실행할 내역이 없으면 disabled 처리한다.

## 표 크기/표 삭제/행열 편집 개선 내용

- editor와 상세 렌더링 표를 compact 스타일로 조정했다.
- `table-layout: fixed`, `font-size: 13px`, `line-height: 1.45`, cell padding `6px 8px`를 적용했다.
- toolbar에 `열-`, `행-`, `표삭제` 버튼을 추가했다.
- 표 안에 selection이 있을 때만 행/열/표 편집 버튼이 활성화된다.

## 이미지 삽입 후 cursor 처리 내용

- 이미지 삽입은 현재 커서 위치에서 수행한다.
- 삽입 후 `createParagraphNear()`를 실행해 이미지 다음 편집 위치를 자연스럽게 만든다.
- 일반 toolbar 클릭이나 일반 입력 중에는 selection을 이미지 아래로 강제 이동하지 않는다.

## Tiptap 유지 판단

이번 단계에서는 Tiptap을 유지했다. 문제의 핵심이 에디터 자체보다 React controlled 동기화와 toolbar focus 처리 방식에 있었고, `resetKey`, `onMouseDown preventDefault`, 표/undo/redo 명령 보강으로 해결 가능하다고 판단했다.

## 오픈소스 에디터 대안 비교

- CKEditor 5: 문서형 WYSIWYG 완성도가 높고 표/이미지 기능이 강하다. 단, 라이선스와 플러그인 정책 확인이 필요하다.
- TinyMCE: 전통적인 WYSIWYG UX가 강하고 기능 구성이 빠르다. 고급 기능과 배포 정책 확인이 필요하다.
- Toast UI Editor: Markdown/WYSIWYG 병행에 적합하지만 HTML 문서 편집 경험은 상대적으로 제한적이다.
- Quill: 가벼운 Delta 기반 에디터지만 표와 문서형 이미지 편집은 확장이 필요하다.

## Python 사용 가능 영역과 부적합 영역

브라우저 selection, contenteditable, toolbar focus 문제는 frontend editor 코드에서 해결해야 하므로 Python은 적합하지 않다. Python/FastAPI는 후속 이미지 업로드, 첨부 관리, HTML export, 검색용 content_text 생성에 적합하다.

## 남은 이슈

- 실제 브라우저에서 이미지 위 연속 입력, 표 삭제, redo 동작은 수동 확인이 필요하다.
- Tiptap의 table resizing UX는 기본 확장 수준이므로, 더 정교한 표 편집 경험이 필요하면 별도 table UI 또는 에디터 교체 검토가 필요하다.
