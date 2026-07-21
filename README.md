# DrCT Asset Office

개인 투자 리서치, 시장 데이터 수집, 지식 관리, 가상 매매훈련을 한곳에서 수행하는 로컬 우선(local-first) 웹 애플리케이션입니다.

> 기준일: 2026-07-21
> 상세 구조: [DrCT_ARCHITECTURE.md](./DrCT_ARCHITECTURE.md)
> 화면 설계 원칙: [DESIGN.md](./DESIGN.md)

## 제품 범위

- 종목, 관심종목, 일봉, 수급, 재무, 공시, 뉴스 관리
- 시장지표, 지수, 시그널, 테마 및 시장 흐름 분석
- Kiwoom REST 조건검색과 시세 조회
- 경제·Telegram 브리핑 및 KMS 지식 관리
- 근거 패키지와 GPT/로컬 LLM 분석 지원
- 매매기법, 매매일지, 리뷰, 백테스트, 패턴 연구
- 계좌 기반 다종목 가상 매매훈련과 리스크 계획 관리

실제 증권계좌 주문은 수행하지 않습니다. 매매훈련의 매수·매도는 애플리케이션 내부의 가상 체결이며, Kiwoom 주문 API는 기본 설정에서 차단됩니다.

## 핵심 원칙

1. **명시적 수집**: 외부 데이터 수집은 사용자의 POST 요청 또는 화면 버튼 동작으로 시작합니다. 조회용 GET 요청은 외부 API를 호출하지 않습니다.
2. **원시 응답 비저장**: API 원시 응답은 DB에 저장하지 않습니다. 수집 계층에서 검증·정규화한 도메인 값만 저장합니다.
3. **출처 추적**: 분석 결과는 가능한 범위에서 원문, 수집시각, 기준일과 연결합니다.
4. **로컬 우선**: 기본 DB는 SQLite이며 프런트엔드, 백엔드, LM Studio를 로컬에서 실행할 수 있습니다.
5. **훈련과 실거래 분리**: 주문 실행 기능은 가상 훈련 상태만 변경하며 실제 중개 주문 경로와 분리합니다.

## 기술 스택

| 영역 | 기술 |
| --- | --- |
| Backend | Python, FastAPI, Pydantic, SQLAlchemy |
| Frontend | React 18, TypeScript, Vite, React Router |
| UI | CSS, Tailwind 유틸리티, Lucide React, Tiptap |
| Database | SQLite (WAL mode) |
| AI | LM Studio OpenAI-compatible API, 프롬프트·근거 패키지 |
| External data | Kiwoom REST, OpenDART, Naver, KRX/data.go.kr, BOK ECOS, KOSIS, FRED, YouTube, Telegram 등 |

## 구조 요약

```text
Browser -> React pages/components -> frontend services/repositories
        -> FastAPI routers -> services -> repositories/entities -> SQLite

External APIs -> providers/clients/collectors -> validation + normalization
```

```text
backend/app/
  api/           HTTP 라우터와 요청 경계
  schemas/       Pydantic 요청·응답 계약
  services/      유스케이스와 도메인 규칙
  repositories/  영속성 접근
  entities/      SQLAlchemy 모델
  providers/     외부 데이터 제공자 어댑터
  collectors/    수집·정규화 흐름
  clients/       외부 HTTP/SDK 클라이언트
  core/          설정, DB, 로깅, 공통 런타임
  llm/           LLM 연동

frontend/src/
  router/        경로 레지스트리와 라우팅
  pages/         업무 화면
  components/    재사용 UI
  services/      API/mock 저장소 조합
  api/           공통 HTTP 클라이언트
  types/         화면·API 타입
  layouts/       애플리케이션 레이아웃
```

## 주요 업무 영역

| 영역 | 주요 기능 |
| --- | --- |
| 종목 관리 | 종목 마스터, 관심종목, 일봉, 수급, 재무, 추적 |
| 정보 수집 | 뉴스, 공시, 수집 이력, 분류 규칙 |
| 시장 분석 | 지수, 기술지표, 시장 시그널, 테마, 트렌드 |
| 지식·브리핑 | 경제 브리핑, Telegram 브리핑, KMS 게시물 |
| 투자 자문 | 분석 근거 묶음, 프롬프트 템플릿, 자문 패키지 |
| 매매 연구 | 기법, 일지, 캘린더, 리뷰, 백테스트, 패턴 연구 |
| 매매훈련 | 훈련계좌, 다종목 세션, 가상 주문, 리스크 계획·개정·행동 이력 |
| 시스템 | 스키마 설명, 분석지표 설정, 아키텍처 정책 화면 |

## 빠른 시작

### 1. 환경 준비

```powershell
Copy-Item .env.example .env
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

실제 API 키와 계좌 정보는 커밋하지 않습니다.

### 2. DB 초기화 및 백엔드 실행

```powershell
.venv\Scripts\python.exe scripts/init_db.py
.venv\Scripts\python.exe -m uvicorn backend.app.main:app --reload
```

- API: `http://127.0.0.1:8000`
- OpenAPI: `http://127.0.0.1:8000/docs`
- Health: `http://127.0.0.1:8000/health`

애플리케이션 시작 시 런타임 스키마와 기본 데이터를 점검합니다. 신규 환경은 먼저 `scripts/init_db.py`를 실행하는 것을 권장합니다.

### 3. 프런트엔드 실행

```powershell
Set-Location frontend
npm install
npm run dev
```

- Web: `http://127.0.0.1:5173`
- 기본 API URL: `http://127.0.0.1:8000`

```dotenv
VITE_APP_NAME=DrCT에셋
VITE_DATA_SOURCE=api
VITE_API_BASE_URL=http://127.0.0.1:8000
```

`VITE_DATA_SOURCE=mock`은 일부 개발용 저장소에만 적용되며, 업무 도메인에 따라 API 저장소가 항상 사용될 수 있습니다.

## 주요 환경 설정

| 설정 | 의미 | 기본 방향 |
| --- | --- | --- |
| `DATABASE_URL` | SQLAlchemy DB URL | `sqlite:///./db/drct_asset.sqlite3` |
| `KIWOOM_REST_ENABLED` | Kiwoom REST 활성화 | `false` |
| `KIWOOM_REST_USE_MOCK` | Kiwoom 모의 서버 사용 | `true` |
| `KIWOOM_REST_BLOCK_ORDER_API` | 실제 주문 API 차단 | `true` |
| `KIWOOM_REST_LOG_RAW_PREVIEW` | 원시 응답 미리보기 로그 | `false` |
| `LMSTUDIO_BASE_URL` | 로컬 LLM 엔드포인트 | `http://127.0.0.1:1234/v1` |
| `TELEGRAM_ENABLED` | Telegram 수집 활성화 | `false` |
| `YOUTUBE_API_ENABLED` | YouTube API 활성화 | `false` |

전체 설정은 [.env.example](./.env.example)을 기준으로 확인합니다.

## 검증

```powershell
python -m pytest backend/tests -q
python -m compileall backend/app
Set-Location frontend
npm run build
```

백엔드 테스트는 API, 시장 시그널, 종목 요약, 관심종목, 스키마 설명, 매매훈련 리스크 계산·주문 경고·행동 이력 등을 다룹니다.

## 데이터 및 보안

- `.env`, API 키, Telegram 세션, 계좌 식별자는 저장소에 커밋하지 않습니다.
- DB에는 수집 후 정규화된 업무 데이터만 저장하며 API 응답 전체나 원시 필드 묶음은 보관하지 않습니다.
- 문제 분석용 로그에도 비밀키와 원시 응답 본문을 남기지 않습니다.
- 외부 API 장애 시 기존 저장 데이터를 조회할 수 있어야 하며 조회 화면이 자동 재수집을 유발해서는 안 됩니다.
- SQLite는 단일 사용자 로컬 실행을 전제로 합니다. 다중 인스턴스 운영 전에는 DB와 마이그레이션 전략을 재검토해야 합니다.

## 문서

- [DESIGN.md](./DESIGN.md): 화면 구조, 시각 언어, 차트와 모달 설계 규칙
- [DrCT_ARCHITECTURE.md](./DrCT_ARCHITECTURE.md): 계층 구조, 데이터 흐름, 도메인 구성, 확장 원칙
- [.env.example](./.env.example): 외부 연동 및 런타임 설정 예시
