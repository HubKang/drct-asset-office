# DrCT에셋 SQLite DB I/O 재발 방지 점검 문서

작성일: 2026-05-12  
대상 폴더: `D:\21. Codex\04. DrCT에셋\drct-asset-office`

## 1) Git 추적 및 히스토리 점검
실행/확인:
- `git status --short`
- `git ls-files | findstr sqlite`
- `git ls-files | findstr ".env"`
- `git log --all -- db/drct_asset.sqlite3`

결과:
- 현재 `git status --short`에는 DB 파일이 나타나지 않음
- `git ls-files | findstr sqlite` 결과 없음 (현재 tracked sqlite 파일 없음)
- `git ls-files | findstr ".env"` 결과: `.env.example`, `frontend/.env.example`만 tracked
- `git log --all -- db/drct_asset.sqlite3` 이력 존재
  - `Delete db/drct_asset.sqlite3` 커밋 이력 확인
  - 과거에는 DB 파일이 커밋 범위에 포함된 적 있었음

해석:
- 현재는 DB 파일 추적이 해제되었지만, 과거 히스토리에는 남아 있음
- 과거 히스토리는 당장 rewrite하지 않고 보안/운영 리스크로 기록

## 2) .gitignore 점검
현재 반영:
- `.env`, `backend/.env`, `frontend/.env`
- `db/*.sqlite3`, `db/*.sqlite3-journal`, `db/*.sqlite3-wal`, `db/*.sqlite3-shm`
- `*.sqlite3`, `*.sqlite3-journal`, `*.sqlite3-wal`, `*.sqlite3-shm`

조치:
- 누락되어 있던 `-wal`, `-shm` 패턴을 보강 완료

## 3) DB 파일 상태 점검
대상: `db/drct_asset.sqlite3`

확인 결과:
- 파일 존재: `True`
- 파일 크기: `920,576 bytes`
- read-only 속성: 없음(`Archive`)
- `drct_asset.sqlite3-journal`: 없음
- `drct_asset.sqlite3-wal`: 있음
- `drct_asset.sqlite3-shm`: 있음
- 권한(`icacls`): 현재 사용자/Authenticated Users 쓰기 권한 존재

무결성/카운트:
- `PRAGMA integrity_check = ok`
- `stocks=2550`
- `watchlist=0`
- `news_items=28`
- `disclosures=40`
- `collection_runs=21`
- `classification_rules=262`

## 4) 프로세스 잠금 점검
`tasklist`는 현재 권한 문제로 `Access denied`가 발생해, `Get-Process`로 대체 점검.

확인 결과:
- 점검 시점에 `python/uvicorn/dbeaver/sqlite` 프로세스는 관찰되지 않음
- Codex 앱 프로세스는 상주

주의:
- SQLite는 파일 DB라서 DB Browser/DBeaver/VS Code 확장/백엔드 동시 접근 시 잠금 리스크가 높음
- 수집 API 실행 시 DB GUI 도구를 반드시 닫고 실행 권장

## 5) hot journal 원인 분석
### 어제 증상
- `*.sqlite3-journal` 잔존
- 삭제/이동 `Access denied`
- 조회 시 `disk I/O error`
- recover DB로 복사해도 유사 증상 전이
- Git 작업 중 DB 파일 modify/delete 충돌

### 가능성 높은 원인 순위
1. **동시 접근 + 비정상 종료로 rollback journal(hot journal) 잔존**
2. **Git 작업트리에 DB 파일이 섞이면서 삭제/복원/충돌 반복**
3. **외부 프로그램(DB GUI/확장/보안툴)의 파일 핸들 점유**

재발 가능성:
- 운영 규칙 없이 PC1/PC2 오가며 DB 파일 직접 다루면 재발 가능성 높음

## 6) SQLAlchemy engine 설정 점검
파일: `backend/app/core/database.py`

현재 상태:
- `DATABASE_URL` 사용
- `check_same_thread=False`
- `timeout` 적용
- 연결 시 PRAGMA 적용:
  - `foreign_keys=ON`
  - `journal_mode` (환경값, 기본 WAL)
  - `synchronous` (환경값, 기본 NORMAL)
  - `busy_timeout` (환경값, 기본 10000ms)
  - `temp_store=MEMORY`
- 세션 라이프사이클: `get_db()`에서 `finally: db.close()`

WAL 장단점:
- 장점: rollback journal hot 상태 반복 가능성 완화, 읽기/쓰기 동시성 개선
- 단점: `-wal`, `-shm` 파일이 상시 생김(반드시 gitignore 필요)

## 7) Session/Transaction 처리 점검
기본 구조:
- 요청 단위 세션 생성/종료는 안전하게 구현

잠재 위험 지점:
- 수집 API처럼 외부 I/O가 긴 요청에서 트랜잭션 경계가 길어질 수 있음
- 루프 내 다중 commit이 예외 중간 발생 시 상태 일관성에 부담 가능
- `collection_runs`가 running으로 남는 케이스 방지 점검 필요

권장 원칙:
1. 외부 API 호출 중 DB 트랜잭션 장시간 유지 금지
2. 수집/변환 후 짧은 저장 트랜잭션으로 분리
3. 예외 시 명시 rollback + 상태 업데이트(failed/partial)
4. 세션 close는 finally에서 보장

## 8) init_db.py 근본 점검
파일: `scripts/init_db.py`

개선 완료:
- 하드코딩 경로 제거
- `.env`의 `DATABASE_URL` 기준 동작
- resolved sqlite path 출력
- SQLite 설정 출력 (`journal_mode/synchronous/busy_timeout`)
- `CREATE IF NOT EXISTS`/안전 ALTER 방식 유지
- 데이터 삭제 로직 없음

## 9) DB 무결성 점검 스크립트
신규 추가:
- `scripts/check_db_health.py`

기능:
- `DATABASE_URL` 읽기
- 실제 sqlite 경로 출력
- 파일/저널(wal/shm) 존재 확인
- `PRAGMA integrity_check`
- 주요 테이블 count 출력

실행:
```bash
python scripts/check_db_health.py
```

## 10) DB 운영 규칙 (재발 방지)
1. SQLite DB 파일은 Git으로 공유/커밋하지 않는다.
2. PC1/PC2 간 DB 이동은 Git이 아니라 수동 백업/복사로 수행한다.
3. 작업 시작 전에 `python scripts/check_db_health.py` 실행한다.
4. 수집 API 실행 전 DBeaver/DB Browser/VSCode SQLite 확장을 종료한다.
5. FastAPI/uvicorn 중복 실행을 금지한다(단일 writer 원칙).
6. `.env`는 로컬 전용이며 Git 제외를 유지한다.
7. `-journal`, `-wal`, `-shm` 파일은 잠금 상태 확인 후 처리한다.
8. `init_db.py`는 반드시 `DATABASE_URL` 대상 DB에만 실행한다.
9. Git pull/rebase 전 `git ls-files | findstr sqlite`로 추적 여부 점검한다.
10. 장애 발생 시: 프로세스 정리 -> health check -> 필요 시 immutable 백업 덤프 순으로 대응한다.

## 11) 오늘 개발 시작 전 최종 확인 (체크)
- [x] `git status --short`에 DB 파일 없음
- [x] `.gitignore` sqlite 제외 규칙 있음(inkl. wal/shm)
- [x] `integrity_check=ok`
- [x] 현재 journal 파일 없음
- [x] `init_db.py`가 `DATABASE_URL` 기준 동작
- [ ] FastAPI 주요 API 조회 전체 재확인(오늘 점검에서는 DB/설정 중심 수행)
- [x] collection_runs 테이블 조회 정상
- [ ] 뉴스/공시/관심종목 화면 회귀 UI 전체 재확인 필요

---

## 완료 보고 템플릿 기준 매핑
1. 원인 1순위: 동시 접근/비정상 종료 + hot journal 잔존  
2~3순위: Git 작업트리에 DB 파일 혼입, 외부 프로그램 핸들 점유  
3. 경로 차이 문제가 아닌 이유: 상대경로 `sqlite:///./db/...`로 동일 구조 사용  
4. Git DB 포함 문제: 과거 이력 존재, 현재는 제외 상태  
5. hot journal 원인: 비정상 종료/동시 접근/파일 잠금  
6. Windows 잠금 가능성: 높음(과거 Access denied 다수)
