# DrCT 통합 이미지 파일 관리 체계

## 목적

DrCT의 이미지 첨부 방식을 공통 규칙으로 통일한다. 60-I-1 단계에서는 기존 화면 동작을 즉시 전환하지 않고, 신규 업로드부터 사용할 수 있는 공통 저장 서비스, 메타데이터 테이블, API 기반을 구축한다.

## 기본 원칙

- 사용자가 이미지를 업로드하면 DrCT 프로젝트의 `data` 하위 폴더에 복사 저장한다.
- DB에는 원본 파일명, 저장 파일명, 상대 경로, 접근 URL, MIME, 크기, 소유 정보 등 메타데이터를 저장한다.
- 이미지 삭제 API는 물리 파일을 먼저 삭제하고, 이후 DB 메타데이터를 삭제한다.
- 기존 DB 데이터와 기존 이미지 파일은 이번 단계에서 이동하거나 삭제하지 않는다.
- 향후 화면은 동일한 공통 API와 저장 규칙을 사용하도록 단계적으로 전환한다.

## 도메인별 저장 폴더

| domain | 저장 폴더 |
| --- | --- |
| `trade_journal` | `data/trade_journal_images` |
| `trade_method` | `data/trade_method_images` |
| `stock_tracking` | `data/stock_tracking_images` |
| `kms` | `data/kms_images` |

상세 폴더는 연도와 월까지만 생성한다.

```text
data/{domain_folder}/{yyyy}/{mm}/{stored_file_name}
```

예시:

```text
data/kms_images/2026/07/chart_sample_20260706001.jpg
data/trade_method_images/2026/07/20day_rebound_20260706002.png
```

## 저장 파일명 규칙

저장 파일명은 사용자가 선택한 원본 파일명을 기반으로 생성한다.

```text
{sanitized_base_name}_{YYYYMMDD}{NNN}.{ext}
```

정제 규칙:

- 확장자는 원본 확장자를 유지한다.
- 공백은 `_`로 바꾼다.
- Windows 금지 문자 `\ / : * ? " < > |`는 제거 또는 `_` 처리한다.
- 연속 `_`는 하나로 축약한다.
- 앞뒤 `_`, `.`, 공백은 제거한다.
- 파일명이 비면 `image`를 사용한다.
- 기본 파일명은 최대 80자로 자른다.

일련번호 규칙:

- `YYYYMMDDNNN` 형식이다.
- 같은 domain과 같은 날짜 기준으로 `001`부터 증가한다.
- DB의 `app_images.stored_file_name`과 실제 저장 폴더의 파일명을 함께 확인한다.
- 최종 저장 전 파일 존재 여부를 다시 확인해 충돌을 피한다.

## 공통 DB 메타데이터

신규 테이블: `app_images`

주요 필드:

- `id`
- `domain`
- `owner_type`
- `owner_id`
- `original_file_name`
- `stored_file_name`
- `relative_path`
- `file_url`
- `file_ext`
- `mime_type`
- `file_size`
- `width`, `height`
- `sort_order`
- `description`
- `is_active`
- `created_at`, `updated_at`

이번 단계에서는 기존 화면별 이미지 테이블을 마이그레이션하지 않는다.

## 공통 Backend 서비스

파일: `backend/app/services/image_file_service.py`

역할:

- domain별 저장 루트 결정
- 연도/월 폴더 생성
- 원본 파일명 정제
- 날짜 기반 일련번호 채번
- 이미지 파일 저장
- `app_images` 메타데이터 저장
- 이미지 목록 조회
- 이미지 삭제 시 물리 파일과 DB row 삭제

허용 조건:

- 확장자: `jpg`, `jpeg`, `png`, `gif`, `webp`
- MIME: `image/jpeg`, `image/png`, `image/gif`, `image/webp`
- 파일 크기: 최대 10MB

## 공통 API

### 업로드

```http
POST /images/upload
```

`multipart/form-data` 필드:

- `file`: 이미지 파일
- `domain`: `trade_journal`, `trade_method`, `stock_tracking`, `kms`
- `owner_type`: 선택
- `owner_id`: 선택
- `description`: 선택
- `sort_order`: 선택

### 목록 조회

```http
GET /images?domain=kms&owner_type=kms_post&owner_id=1
```

필터는 모두 선택이다.

### 삭제

```http
DELETE /images/{image_id}
```

동작:

1. DB에서 이미지 메타데이터 조회
2. `data` 하위 경로인지 확인
3. 물리 파일 삭제
4. DB row 삭제
5. 파일이 이미 없으면 `file_missing=true`로 보고하고 DB 삭제는 진행

## 정적 파일 URL

현재 FastAPI는 `data` 폴더를 `/static`으로 마운트한다.

```text
relative_path: data/kms_images/2026/07/sample_20260706001.jpg
file_url: /static/kms_images/2026/07/sample_20260706001.jpg
```

프론트엔드는 `appConfig.apiBaseUrl + file_url` 형태로 이미지를 표시할 수 있다.

## Frontend 공통 클라이언트

파일:

- `frontend/src/types/image.ts`
- `frontend/src/services/api/imageApiRepository.ts`

제공 기능:

- `uploadImage(payload)`
- `listImages(params)`
- `deleteImage(imageId)`

60-I-1에서는 화면에 연결하지 않는다.

## .gitignore 정책

사용자 업로드 이미지 파일은 git에 올리지 않는다.

제외 대상:

- `data/kms_images/**`
- `data/stock_tracking_images/**`
- `data/trade_journal_images/**`
- `data/trade_method_images/**`

단, 폴더 구조 유지를 위해 각 루트의 `.gitkeep`은 추적할 수 있게 예외 처리한다.

## 이번 단계 제외 범위

- KMS Rich Editor 업로드 버튼 연결
- 매매기법 이미지 업로드 전환
- 매매일지 이미지 업로드 전환
- 종목 트래킹 이미지 업로드 전환
- 기존 이미지 파일/DB 경로 마이그레이션
- KMS 본문 HTML에서 제거된 이미지의 자동 orphan 정리

## 후속 단계

- 60-I-2: KMS Rich Editor 이미지 업로드 연결
- 60-I-3: 매매기법 이미지 업로드/삭제 공통 API 전환
- 60-I-4: 매매일지 이미지 업로드/삭제 공통 API 전환
- 60-I-5: 종목 트래킹 이미지 업로드/삭제 공통 API 전환
- 60-I-6: 기존 이미지 마이그레이션 검토 및 정리 도구 설계
