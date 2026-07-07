# 60-I-2 KMS Rich Editor 공통 이미지 업로드 연동

## 목적

60-I-1에서 만든 공통 이미지 업로드 API를 KMS Rich Editor에 연결한다. 사용자가 에디터에서 이미지 파일을 선택하면 DrCT 내부 이미지 저장소에 복사 저장하고, 반환된 URL을 본문 `img` 태그로 삽입한다.

## 저장 경로

사용자 요청에 따라 KMS 이미지 저장 폴더는 다음으로 적용했다.

```text
data/kms_images/{yyyy}/{mm}/{stored_file_name}
```

공통 이미지 domain은 그대로 `kms`를 사용하지만, backend domain folder 매핑은 `kms -> kms_images`로 변경했다.

## UX

KMS Rich Editor toolbar에 이미지 업로드 버튼을 추가했다.

- 기존 `Image` 버튼: 기존 로컬 이미지 선택/참조 흐름 유지
- 신규 `Upload` 버튼: 공통 이미지 업로드 API 사용
- 파일 선택 input은 숨김 처리
- 허용 형식: png, jpg, jpeg, gif, webp
- 프론트 1차 크기 제한: 10MB
- 업로드 중 버튼 비활성화 및 `Uploading` 표시
- 실패 시 에디터 내부 오류 메시지 표시

## API 연동

호출 API:

```http
POST /images/upload
```

KMS에서 전달하는 값:

- `domain`: `kms`
- `owner_type`: `kms_post`
- `owner_id`: 수정 모드에서는 post id, 신규 등록 모드에서는 비움

응답의 `file_url`은 브라우저에서 바로 렌더링할 수 있도록 `appConfig.apiBaseUrl`을 붙여 에디터 본문에 삽입한다.

## 본문 삽입 방식

업로드 성공 시 다음 형태의 이미지를 삽입한다.

```html
<img src="{apiBaseUrl}/static/kms_images/yyyy/mm/file.png" alt="{original_file_name}" width="50%" style="width: 50%;">
```

이미지 삽입 후 `createParagraphNear()`를 호출해 다음 입력 위치를 만든다.

## 신규/수정 모드 owner_id 처리

- 신규 등록: 아직 post id가 없으므로 `owner_id` 없이 업로드한다.
- 수정/상세 수정: `owner_id`에 KMS post id를 전달한다.

신규 등록 중 업로드된 이미지에 저장 후 post id를 자동 연결하는 기능은 이번 단계에서 제외했다.

## 기존 기능 영향

- 기존 KMS 게시글 데이터는 수정하지 않았다.
- 기존 이미지 파일은 이동하거나 삭제하지 않았다.
- 기존 로컬 이미지 선택 기능은 유지했다.
- 매매기법, 매매일지, 종목 트래킹 이미지는 전환하지 않았다.
- `TradeTrainingPage.tsx`는 수정하지 않았다.

## 후속 과제

- 신규 등록 중 owner_id 없이 생성된 KMS 이미지와 저장된 post id 연결
- 본문에서 제거된 이미지 orphan 정리
- KMS 이미지 관리 화면 또는 정리 도구
- 매매기법/매매일지/종목 트래킹 이미지 업로드 공통 API 전환
## 60-I-4 update

- The toolbar now separates 이미지 URL and 이미지 업로드.
- 이미지 URL only inserts the typed URL as an img src and does not create a local DrCT file.
- 이미지 업로드 uploads a selected local image through POST /images/upload with domain=kms.
- Successful uploads show the returned relative_path so the user can verify data/kms_images/{yyyy}/{mm}/ storage.
- Failed uploads show an editor-level error message instead of only relying on console output.
