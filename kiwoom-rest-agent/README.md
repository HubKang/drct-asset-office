# Kiwoom REST Agent PoC (27-A)

## 목적
- DrCT 본체와 분리된 조회 전용 Kiwoom REST PoC를 구성합니다.
- 검증 범위: 토큰 발급, 인증 확인(계좌조회), 조건검색 API 방식 검토, 시가대비등락률(ka10028) 수신 및 정규화.
- 주문/신용주문 API는 차단합니다.

## 설치
```bash
cd kiwoom-rest-agent
pip install -r requirements.txt
copy .env.example .env
```

## .env 작성
- `.env.example`을 복사해 `.env`를 만든 뒤 아래를 채웁니다.
  - `KIWOOM_REST_APP_KEY`
  - `KIWOOM_REST_SECRET_KEY`
- `KIWOOM_REST_ENV=prod|mock`로 대상 환경을 고를 수 있습니다.

### .env 지원 위치/우선순위
1. `kiwoom-rest-agent/.env` (우선)
2. 프로젝트 루트 `.env` (`drct-asset-office/.env`)

즉, Agent 전용 `.env`가 있으면 우선 사용하고, 없으면 프로젝트 루트 `.env`를 사용합니다.

프로젝트 루트 `.env` 예시:
```env
KIWOOM_REST_ENV=prod
KIWOOM_REST_BASE_URL=https://api.kiwoom.com
KIWOOM_REST_MOCK_BASE_URL=https://mockapi.kiwoom.com
KIWOOM_REST_APP_KEY=your_app_key
KIWOOM_REST_SECRET_KEY=your_secret_key
KIWOOM_REST_TIMEOUT_SECONDS=10
DRCT_API_BASE_URL=http://localhost:8000
DRCT_API_ENABLED=false
```

## 실행 순서
```bash
python run_token_test.py
python run_account_test.py
python run_intraday_change_rank.py
python run_condition_list.py
python run_condition_once.py --condition-seq 001
```

## 조건검색 API 관련
- 27-C에서는 WebSocket 기반 조건검색 목록/결과 조회를 PoC 구현했습니다.
- 수집 결과를 DrCT API로 전송하려면 `--send-drct` 옵션과 `DRCT_API_ENABLED=true`를 사용합니다.

예시:
```bash
python run_condition_list.py --send-drct
python run_condition_once.py --condition-seq 001 --send-drct
```

## 저장 경로
- raw 응답: `data/raw/`
- 정규화 응답: `data/normalized/`
- 로그: `data/logs/`

## 보안 원칙
- APP KEY/SECRET/TOKEN 하드코딩 금지
- 토큰/헤더/계좌번호 로그 마스킹
- 주문 API 차단: `kt10000~kt10009` 일부 주요 주문 계열

## DrCT 본체 연동 상태
- 이번 단계는 DrCT 본체 미연동 PoC입니다.
- backend/frontend/DB 스키마 변경 없이 외부 데이터 수집 가능성만 검증합니다.
