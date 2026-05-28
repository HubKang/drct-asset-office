# DrCT Asset Office 폴더 구조 및 역할 정리

이 문서는 `drct-asset-office` 루트 기준으로 현재 프로젝트의 폴더 구조와 각 영역의 역할을 빠르게 파악하기 위한 아키텍처 요약이다.

## 1) 루트(Top-level) 구조

- `.venv/`: Python 가상환경
- `backend/`: FastAPI 기반 백엔드 서버
- `frontend/`: Vite + React + TypeScript 프론트엔드
- `db/`: SQLite DB 파일 저장 위치(운영 데이터)
- `data/`: 업로드 파일/정적 데이터(예: 매매일지 이미지)
- `data_cache/`: 수집/가공 중간 캐시 데이터
- `docs/`: 설계/정책/로드맵/운영 문서
- `scripts/`: 점검/운영 보조 스크립트
- `knowledge/`: 도메인 지식/참고 자료
- `prompts/`: 프롬프트 관련 자산
- `marcap/`: 시가총액/시장 데이터 관련 자산
- `agents/`: 에이전트 작업 관련 자산
- `.cache/`, `.mpltcache/`: 실행 캐시

루트 주요 파일:

- `README.md`: 프로젝트 개요/실행 가이드
- `requirements.txt`: 백엔드 Python 의존성
- `init_db.py`: DB 초기화/세팅 스크립트
- `restart_servers.bat`: 로컬 서버 재시작 보조
- `.env`, `.env.example`: 환경변수
- `PROJECT_PLAN.md`, `PROJECT_SNAPSHOT.md`: 진행 계획/스냅샷

---

## 2) 백엔드 아키텍처 (`backend/`)

`backend/`는 전형적인 레이어드 구조를 따른다.

- `app/main.py`
  - FastAPI 앱 엔트리
  - 라우터 등록 및 앱 부팅

- `app/api/`
  - HTTP 엔드포인트 레이어
  - 요청/응답 입출력 처리, 서비스 호출
  - 예: `routes_trade_journals.py`

- `app/schemas/`
  - Pydantic 스키마
  - API request/response 타입 계약

- `app/services/`
  - 비즈니스 로직 중심 레이어
  - 여러 repository를 조합해 도메인 처리
  - GPT 패키지 생성/집계/검증 로직 위치

- `app/repositories/`
  - DB 접근 레이어
  - 쿼리/CRUD 캡슐화

- `app/entities/`
  - SQLAlchemy 모델(테이블 매핑)

- `app/core/`
  - 공통 인프라(설정, DB 세션, 로깅 등)

- `app/clients/`, `app/providers/`
  - 외부 API/데이터 소스 연동

- `app/collectors/`
  - 수집 파이프라인/크롤링/적재 로직

- `app/sql/`
  - SQL 자산 및 마이그레이션 관련 리소스

- `app/utils/`
  - 공통 유틸리티

- `tests/`
  - 백엔드 테스트

요약 흐름:

`API(routes) -> Service -> Repository -> Entity(DB)`

---

## 3) 프론트엔드 아키텍처 (`frontend/`)

`frontend/`는 React 기반 계층 분리를 사용한다.

- `src/main.tsx`, `src/App.tsx`
  - 프론트 앱 엔트리/루트 컴포넌트

- `src/pages/`
  - 화면 단위 페이지
  - 예: 매매일지/매매달력/매매기법 화면

- `src/components/`
  - 재사용 UI 컴포넌트

- `src/layouts/`
  - 공통 레이아웃

- `src/router/`
  - 라우팅 설정

- `src/services/`
  - API 호출 계층
  - `services/api/tradeJournalApiRepository.ts` 등

- `src/types/`
  - 프론트 타입 정의(API DTO 포함)

- `src/utils/`
  - 프론트 유틸 함수

- `src/index.css`
  - 전역 스타일

`dist/`는 빌드 산출물, `node_modules/`는 의존성 폴더다.

---

## 4) 데이터/파일 저장 경로

- DB: `db/drct_asset.sqlite3` (환경설정에 따라 참조)
- 매매일지 이미지: `data/trade_journal_images/YYYY/MM/DD/`
- 정적 이미지 URL: `/static/...` 경로로 서빙

즉, 메타데이터는 DB에, 실제 파일은 `data/`에 저장하는 분리 전략이다.

---

## 5) 문서/운영 체계

- `docs/`
  - 아키텍처, 데이터모델, 운영룰, 단계별 계획 문서 집약
  - 예: `architecture.md`, `data_model.md`, `operating_rules.md`

- `scripts/`
  - 상태 점검(예: `check_db_health.py`) 같은 운영 스크립트

문서-코드-운영 스크립트가 분리되어 있어, 변경 이력 관리와 인수인계가 쉬운 구조다.

---

## 6) 빠른 점검 포인트 (신규 작업 시작 시)

1. `scripts/check_db_health.py`로 DB 상태 확인
2. `backend/app/api` -> `services` -> `repositories` 순으로 영향 범위 파악
3. `frontend/src/pages` + `services/api` + `types`를 세트로 수정
4. 이미지/정적파일 변경 시 `data/` 경로 정책 준수
5. `docs/` 내 관련 설계 문서와 일치 여부 확인

---

## 7) 구조 평가 요약

- 장점
  - 백엔드/프론트 역할 분리가 명확함
  - 서비스 레이어 중심으로 기능 확장이 용이함
  - GPT 패키지 기능(단건/월간/기법/실패패턴) 추가에 유리한 구조

- 주의점
  - 일부 화면/서비스 파일이 커지기 쉬우므로 기능별 분리 리팩터링 타이밍 관리 필요
  - 운영 캐시/산출물(`dist`, `__pycache__`, 캐시 폴더)과 소스 변경을 커밋 시 구분 필요

