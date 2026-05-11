# DrCT에셋 PC2 신규 개발 환경 세팅 및 Git 운영 가이드

이 문서는 새로운 PC 환경에서 `DrCT에셋(drct-asset-office)` 프로젝트를 GitHub에서 내려받아 개발을 이어가고, 개발 작업이 끝난 뒤 변경된 소스를 다시 GitHub에 올리는 절차를 정리한 문서입니다.

---

## 1. 전제 조건

새 PC에는 아래 프로그램이 설치되어 있어야 합니다.

```cmd
git --version
python --version
node --version
npm --version
```

필요 프로그램:

- Git
- Python 3.11 이상 권장
- Node.js LTS 버전
- VS Code 또는 Cursor
- LM Studio
- GitHub 계정 접근 권한

---

## 2. GitHub에서 프로젝트 내려받기

작업할 상위 폴더로 이동합니다.

```cmd
cd "D:\21. Codex\04. DrCT에셋"
```

GitHub 저장소를 clone 합니다.

```cmd
git clone https://github.com/HubKang/drct-asset-office.git
```

프로젝트 폴더로 이동합니다.

```cmd
cd "D:\21. Codex\04. DrCT에셋\drct-asset-office"
```

정상 clone 여부를 확인합니다.

```cmd
git status
```

정상이라면 다음과 유사한 메시지가 나옵니다.

```text
On branch main
Your branch is up to date with 'origin/main'.
```

만약 아래 오류가 나오면 현재 폴더가 Git 저장소가 아닌 것입니다.

```text
fatal: not a git repository (or any of the parent directories): .git
```

이 경우 `drct-asset-office` 폴더 안으로 이동했는지 확인합니다.

```cmd
cd "D:\21. Codex\04. DrCT에셋\drct-asset-office"
git status
```

---

## 3. Git 안전 디렉터리 오류 해결

다음 오류가 발생할 수 있습니다.

```text
fatal: detected dubious ownership in repository
```

이 경우 아래 명령을 실행합니다.

```cmd
git config --global --add safe.directory "D:/21. Codex/04. DrCT에셋/drct-asset-office"
```

그 후 다시 확인합니다.

```cmd
git status
```

---

## 4. .env 파일 생성

`.env` 파일은 API 키가 들어가므로 GitHub에 올리지 않습니다.  
대신 `.env.example`을 복사해서 새 PC에서 직접 `.env`를 만듭니다.

프로젝트 루트에서 실행합니다.

```cmd
copy .env.example .env
```

`.env` 파일을 엽니다.

```cmd
notepad .env
```

아래 항목들을 실제 값으로 입력합니다.

```env
# Naver News API
NAVER_CLIENT_ID=
NAVER_CLIENT_SECRET=

# DART API
DART_API_KEY=

# KRX Stock Master API
KRX_API_SERVICE_KEY=
KRX_API_BASE_URL=https://apis.data.go.kr/1160100/service/GetKrxListedInfoService/getItemInfo
KRX_API_KEY_MODE=encoded
KRX_API_TIMEOUT_SECONDS=15
KRX_API_MAX_PAGES=10

# LM Studio
LMSTUDIO_BASE_URL=http://127.0.0.1:1234/v1
LMSTUDIO_MODEL=google/gemma-4-e2b
```

현재 KRX API는 Encoding 키로 정상 테스트되었으므로 `KRX_API_SERVICE_KEY`에는 공공데이터포털의 Encoding 키를 우선 입력합니다.

---

## 5. .gitignore 확인

`.env`, SQLite DB, node_modules, 빌드 결과물이 GitHub에 올라가지 않도록 `.gitignore`를 확인합니다.

```cmd
type .gitignore
```

최소한 아래 항목이 포함되어 있어야 합니다.

```gitignore
.env
backend/.env
frontend/.env

db/*.sqlite3
*.sqlite3

node_modules/
frontend/node_modules/
dist/
frontend/dist/

.venv/
venv/
__pycache__/
*.pyc

data/raw/
reports/
```

`.gitignore`가 없거나 수정이 필요하면 다음 명령으로 엽니다.

```cmd
notepad .gitignore
```

---

## 6. 백엔드 Python 환경 구성

프로젝트 루트에서 가상환경을 만듭니다.

```cmd
python -m venv .venv
```

가상환경을 실행합니다.

```cmd
.venv\Scripts\activate
```

패키지를 설치합니다.

```cmd
pip install -r requirements.txt
```

만약 `requirements.txt`가 루트가 아니라 `backend` 폴더에 있다면 아래 명령을 사용합니다.

```cmd
pip install -r backend\requirements.txt
```

---

## 7. DB 초기화

SQLite DB는 GitHub에 올리지 않는 것을 원칙으로 합니다.  
새 PC에서는 DB를 새로 초기화합니다.

```cmd
mkdir db
python scripts/init_db.py
```

DB 파일 생성 여부를 확인합니다.

```cmd
dir db
```

예상 파일:

```text
drct_asset.sqlite3
```

기존 PC의 실제 데이터를 그대로 옮기고 싶다면 GitHub가 아니라 USB, 외장디스크, 개인 보안 저장소 등을 통해 아래 파일을 복사합니다.

```text
db/drct_asset.sqlite3
```

---

## 8. 백엔드 실행

프로젝트 루트에서 가상환경이 활성화된 상태로 실행합니다.

```cmd
uvicorn backend.app.main:app --reload
```

정상 실행 후 브라우저에서 확인합니다.

```text
http://127.0.0.1:8000/docs
```

FastAPI Swagger 화면이 보이면 백엔드가 정상 실행된 것입니다.

---

## 9. 프론트엔드 환경 구성

새 CMD 창을 열고 프론트엔드 폴더로 이동합니다.

```cmd
cd "D:\21. Codex\04. DrCT에셋\drct-asset-office\frontend"
```

패키지를 설치합니다.

```cmd
npm install
```

빌드를 확인합니다.

```cmd
npm run build
```

개발 서버를 실행합니다.

```cmd
npm run dev
```

브라우저에서 접속합니다.

```text
http://127.0.0.1:5173
```

---

## 10. LM Studio 설정

뉴스/공시 AI 요약을 사용하려면 PC2에서도 LM Studio를 실행해야 합니다.

LM Studio에서 Local Server를 실행합니다.

```text
Base URL: http://127.0.0.1:1234/v1
```

`.env` 설정과 일치해야 합니다.

```env
LMSTUDIO_BASE_URL=http://127.0.0.1:1234/v1
```

LM Studio에서 실제 로드한 모델명과 `.env`의 `LMSTUDIO_MODEL` 값도 맞춰야 합니다.

---

## 11. 초기 기능 확인 순서

### 11.1 백엔드 확인

```text
http://127.0.0.1:8000/docs
```

### 11.2 프론트 확인

```text
http://127.0.0.1:5173
```

### 11.3 종목관리 확인

종목관리 화면에서 다음 순서로 확인합니다.

1. `미리보기만 실행` 체크
2. `KRX 목록에 없는 기존 종목 비활성화` 해제
3. 동기화 대상은 `보통주`만 선택
4. 코스피 종목 갱신 실행
5. dry_run 결과 확인

정상 메시지 예:

```text
dry_run preview completed ...
```

결과가 적절하면 실제 반영합니다.

1. `미리보기만 실행` 해제
2. `KRX 목록에 없는 기존 종목 비활성화` 해제
3. 동기화 대상은 `보통주`만 선택
4. 코스피 종목 갱신 실행
5. 코스닥 종목도 동일하게 실행

처음 실제 반영할 때는 `KRX 목록에 없는 기존 종목 비활성화`를 켜지 않는 것이 안전합니다.

---

## 12. 개발 시작 전 Git 최신화

PC2에서 작업을 시작하기 전에는 항상 최신 소스를 받습니다.

```cmd
cd "D:\21. Codex\04. DrCT에셋\drct-asset-office"
git pull origin main
```

현재 상태를 확인합니다.

```cmd
git status
```

---

## 13. 개발 작업 후 GitHub에 올리기

개발이 끝나면 프로젝트 루트에서 아래 순서로 진행합니다.

### 13.1 변경 파일 확인

```cmd
git status --short
```

여기에서 `.env`, SQLite DB, `node_modules`, `dist`, `.venv` 등이 보이면 안 됩니다.

올라가면 안 되는 대표 파일:

```text
.env
backend/.env
frontend/.env
db/drct_asset.sqlite3
*.sqlite3
node_modules/
frontend/node_modules/
frontend/dist/
.venv/
```

### 13.2 변경 파일 추가

```cmd
git add .
```

다시 확인합니다.

```cmd
git status --short
```

### 13.3 커밋 생성

커밋 메시지는 작업 내용을 짧고 명확하게 작성합니다.

예시:

```cmd
git commit -m "Update stock management UI and sync workflow"
```

종목관리 작업 예시:

```cmd
git commit -m "Improve KRX stock master sync and stock list pagination"
```

GPT 자문 패키지 작업 예시:

```cmd
git commit -m "Enhance advisory package templates and UI"
```

### 13.4 GitHub에 push

```cmd
git push origin main
```

처음 push하는 경우라면 아래 명령을 사용할 수 있습니다.

```cmd
git push -u origin main
```

---

## 14. Git 사용자 정보 오류 해결

커밋 시 아래 오류가 나올 수 있습니다.

```text
Author identity unknown
Please tell me who you are.
```

이 경우 Git 사용자 정보를 설정합니다.

```cmd
git config --global user.name "HubKang"
git config --global user.email "본인_GitHub_이메일"
```

GitHub 이메일을 공개하고 싶지 않다면 GitHub의 noreply 이메일을 사용할 수 있습니다.

설정 확인:

```cmd
git config --global user.name
git config --global user.email
```

그 후 다시 커밋합니다.

```cmd
git commit -m "Add commit message"
```

---

## 15. Push 전 보안 체크

GitHub에 올리기 전 반드시 아래를 확인합니다.

```cmd
git status --short
```

다음 파일이 포함되어 있으면 중단합니다.

```text
.env
*.sqlite3
node_modules
dist
.venv
```

이미 Git 추적에 들어간 경우에는 추적에서 제거합니다.

```cmd
git rm --cached .env
git rm --cached backend/.env
git rm --cached frontend/.env
git rm --cached db/drct_asset.sqlite3
```

파일은 삭제되지 않고 Git 추적에서만 제거됩니다.

---

## 16. PC1과 PC2를 오가며 개발할 때의 기본 흐름

### PC2에서 작업 시작

```cmd
git pull origin main
```

### PC2에서 작업 완료 후

```cmd
git add .
git commit -m "작업 내용 요약"
git push origin main
```

### PC1에서 이어서 작업할 때

```cmd
git pull origin main
```

이 순서를 지키면 PC1과 PC2의 소스 차이를 줄일 수 있습니다.

---

## 17. 자주 발생하는 오류

### 17.1 현재 폴더가 Git 저장소가 아님

오류:

```text
fatal: not a git repository (or any of the parent directories): .git
```

해결:

```cmd
cd "D:\21. Codex\04. DrCT에셋\drct-asset-office"
git status
```

### 17.2 main 브랜치가 없음

오류:

```text
error: src refspec main does not match any
```

원인:

- 아직 커밋이 없음
- 브랜치명이 main이 아님

해결:

```cmd
git add .
git commit -m "Initial commit"
git branch -M main
git push -u origin main
```

### 17.3 Git 사용자 정보 없음

오류:

```text
Author identity unknown
```

해결:

```cmd
git config --global user.name "HubKang"
git config --global user.email "본인_GitHub_이메일"
```

### 17.4 safe.directory 오류

오류:

```text
fatal: detected dubious ownership in repository
```

해결:

```cmd
git config --global --add safe.directory "D:/21. Codex/04. DrCT에셋/drct-asset-office"
```

---

## 18. 추천 작업 규칙

1. 작업 시작 전 `git pull origin main`
2. 작업 완료 후 `npm run build`
3. 백엔드 변경 시 FastAPI 실행 확인
4. DB 구조 변경 시 `scripts/init_db.py` 확인
5. `.env`와 DB 파일은 GitHub에 올리지 않기
6. 커밋 메시지는 작업 단위별로 명확히 작성
7. PC를 바꿔 작업하기 전에는 반드시 push/pull 확인

---

## 19. 빠른 실행 명령 요약

### 백엔드 실행

```cmd
cd "D:\21. Codex\04. DrCT에셋\drct-asset-office"
.venv\Scripts\activate
uvicorn backend.app.main:app --reload
```

### 프론트엔드 실행

```cmd
cd "D:\21. Codex\04. DrCT에셋\drct-asset-office\frontend"
npm run dev
```

### 개발 후 GitHub 업로드

```cmd
cd "D:\21. Codex\04. DrCT에셋\drct-asset-office"
git status --short
git add .
git commit -m "작업 내용 요약"
git push origin main
```
