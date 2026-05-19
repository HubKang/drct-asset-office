# 23-1단계: 시장 트렌드 테마 수동 등록·종목 수동 매핑 및 자동 후보 확장 구조 설계

## 1. 목적 및 범위
- 본 문서는 시장 트렌드 분석의 기반이 되는 테마/종목 매핑 구조를 설계한다.
- 1차 목표는 수동 테마 등록, 수동 종목 매핑, N:M 관계 지원이다.
- 자동화는 즉시 반영이 아니라 후보 추천으로만 생성하고 사용자 승인 후 정식 반영한다.
- 본 단계는 설계 문서 작성 단계이며 기존 기능(가격·캔들관리, GPT 프롬프트 설정, 뉴스·공시 분류 등) 코드는 수정하지 않는다.

핵심 원칙:
- 시장 트렌드 분석은 자동 매수·매도 판단이 아니라, 시장에서 관심이 증가한 테마와 종목을 빠르게 찾기 위한 분석 우선순위 도구다.

## 2. 기능 개요
- 테마는 시장 내 관심 흐름을 묶는 분석 단위다.
- 종목은 복수 테마에 속할 수 있어야 하며(예: 방산+우주항공), 테마 역시 복수 종목을 가진다.
- 초기에는 수동 등록/수동 매핑으로 품질을 통제한다.
- 향후 뉴스·공시·텔레그램 기반 자동 후보 추천을 추가한다.
- 자동 등록은 금지하고 `후보 생성 -> 사용자 승인 -> 정식 매핑`으로 운영한다.

## 3. 데이터 모델 설계

### 3.1 market_themes (테마 마스터)
역할:
- 시장 테마/산업/사용자 정의 그룹 관리

컬럼 후보:
- id INTEGER PRIMARY KEY AUTOINCREMENT
- theme_name TEXT NOT NULL
- theme_code TEXT NOT NULL UNIQUE
- theme_type TEXT NOT NULL
- description TEXT
- keywords TEXT
- parent_theme_id INTEGER
- is_active INTEGER NOT NULL DEFAULT 1
- sort_order INTEGER NOT NULL DEFAULT 0
- created_at TEXT NOT NULL
- updated_at TEXT NOT NULL

theme_type 후보:
- industry
- theme
- custom
- telegram

설계 메모:
- keywords는 1차에서 JSON 문자열 또는 구분자 문자열로 저장한다.
- parent_theme_id로 상/하위 테마 계층을 유연하게 구성한다.
- 삭제보다 비활성(is_active=0) 우선.

예시 테마:
- AI, 반도체, 전력기기, 전력망, 변압기, 방산, 조선, 로봇, 바이오, 원전, 2차전지, 데이터센터, 우주항공, 화장품, 엔터, 자동차부품

### 3.2 market_theme_stocks (테마-종목 N:M 매핑)
역할:
- 테마와 stocks 종목 간 정식 매핑 관리

컬럼 후보:
- id INTEGER PRIMARY KEY AUTOINCREMENT
- theme_id INTEGER NOT NULL
- stock_id INTEGER NOT NULL
- mapping_source TEXT NOT NULL DEFAULT 'manual'
- confidence_score REAL
- is_primary INTEGER NOT NULL DEFAULT 0
- is_active INTEGER NOT NULL DEFAULT 1
- created_at TEXT NOT NULL
- updated_at TEXT NOT NULL

mapping_source 후보:
- manual
- keyword
- news
- disclosure
- telegram
- system

제약조건 후보:
- UNIQUE(theme_id, stock_id)
- FOREIGN KEY(theme_id) REFERENCES market_themes(id)
- FOREIGN KEY(stock_id) REFERENCES stocks(id)

설계 메모:
- 초기 운영은 mapping_source='manual' 중심.
- 자동 추천에서 승인된 경우에만 정식 매핑으로 추가.
- 대표 테마는 is_primary로 표시.

### 3.3 market_theme_stock_candidates (자동 후보 저장)
역할:
- 뉴스/공시/텔레그램/키워드 기반 추천 후보를 승인 대기 상태로 저장

컬럼 후보:
- id INTEGER PRIMARY KEY AUTOINCREMENT
- theme_id INTEGER NOT NULL
- stock_id INTEGER NOT NULL
- candidate_source TEXT NOT NULL
- confidence_score REAL
- matched_keywords TEXT
- evidence_count INTEGER NOT NULL DEFAULT 1
- evidence_summary TEXT
- status TEXT NOT NULL DEFAULT 'pending'
- review_memo TEXT
- created_at TEXT NOT NULL
- updated_at TEXT NOT NULL

candidate_source 후보:
- keyword
- news
- disclosure
- telegram
- system

status 후보:
- pending
- approved
- rejected
- ignored

제약조건 후보:
- UNIQUE(theme_id, stock_id, candidate_source)
- FOREIGN KEY(theme_id) REFERENCES market_themes(id)
- FOREIGN KEY(stock_id) REFERENCES stocks(id)

설계 메모:
- 중복 후보는 새 row를 계속 쌓기보다 evidence_count/updated_at 갱신 방식 권장.
- approved 시 정식 매핑 테이블로 승격 반영.

## 4. keywords 설계
- 1차 저장 방식: market_themes.keywords (TEXT)
- 권장 포맷: JSON 배열 문자열
  - 예: ["전력기기","변압기","송전","배전","전력망","HVDC","초고압","변전소","전선"]
- 향후 확장: market_theme_keywords 별도 테이블 분리

키워드 예시:
- 전력기기: 전력기기, 변압기, 송전, 배전, 전력망, HVDC, 초고압, 변전소, 전선
- 방산: 방산, 방위산업, 무기체계, 미사일, 장갑차, K9, 국방, 수출계약
- AI: AI, 인공지능, 생성형AI, 데이터센터, GPU, LLM, AI반도체
- 바이오: 바이오, 임상, 신약, FDA, 품목허가, 항암제, 치료제

## 5. 수동 -> 자동 확장 단계

### 5.1 1단계: 수동 테마 등록
- 저장: market_themes
- 사용자 직접 생성/수정/비활성

### 5.2 2단계: 수동 종목 매핑
- 저장: market_theme_stocks
- mapping_source='manual'

### 5.3 3단계: 자동 후보 추천
- 저장: market_theme_stock_candidates
- status='pending'

### 5.4 4단계: 사용자 승인/거절
- 승인:
  - candidates.status='approved'
  - market_theme_stocks에 정식 매핑 upsert
  - mapping_source는 추천 출처(news/disclosure/telegram/keyword)
- 거절: candidates.status='rejected'
- 보류: pending 유지 또는 ignored

### 5.5 5단계: 품질 개선 루프
- 승인율/거절율 기반 키워드 보정
- 출처별 신뢰도 가중치 튜닝
- 종목별 반복 추천 패턴 기반 confidence 보정

## 6. 자동 후보 생성 로직(후속 구현용 설계)

입력 데이터:
- 뉴스: news_items.title, ai_summary, ai_tags, ai_sentiment, ai_importance_score
- 공시: disclosures.disclosure_title, ai_summary, ai_event_type, ai_risk_level, ai_importance_score
- 텔레그램(향후): telegram_messages.message_text, telegram_theme_mentions.matched_keywords

기본 흐름:
1. 활성 테마(market_themes.is_active=1)와 keywords 로드
2. 뉴스/공시/텔레그램 텍스트에서 키워드 매칭
3. 매칭된 종목 stock_id 도출
4. 이미 정식 매핑(theme_id, stock_id) 존재 여부 확인
5. 미존재 시 candidates에 pending upsert
6. 동일 후보 반복 발견 시 evidence_count/confidence_score 증가

신뢰도(초안):
- 키워드 일치 수, 최근성, 출처 가중치, ai_importance_score 등을 조합
- 점수는 투자판단이 아닌 "추천 후보 우선순위" 용도로만 사용

## 7. API 설계 후보

### 7.1 테마 API
- GET /market-themes
- GET /market-themes/{theme_id}
- POST /market-themes
- PUT /market-themes/{theme_id}
- PATCH /market-themes/{theme_id}/deactivate

### 7.2 테마-종목 매핑 API
- GET /market-themes/{theme_id}/stocks
- POST /market-themes/{theme_id}/stocks
- PATCH /market-theme-stocks/{mapping_id}
- PATCH /market-theme-stocks/{mapping_id}/deactivate

### 7.3 자동 후보 API (후속 구현)
- GET /market-theme-stock-candidates
- POST /market-theme-stock-candidates/generate
- POST /market-theme-stock-candidates/{candidate_id}/approve
- POST /market-theme-stock-candidates/{candidate_id}/reject
- POST /market-theme-stock-candidates/{candidate_id}/ignore

운영 원칙:
- 자동 후보는 정식 매핑 아님
- 승인 액션만 정식 매핑 반영

## 8. 화면 설계 후보

화면명:
- 시장 테마 관리

영역:
- 테마 목록
- 테마 등록/수정
- 키워드 관리
- 테마별 연결 종목
- 종목 검색/추가
- 자동 추천 후보 목록(승인/거절/보류)

### 8.1 테마 목록 컬럼
- 테마명
- 유형
- 키워드 수
- 연결 종목 수
- 활성 여부
- 정렬 순서
- 수정/상세

### 8.2 테마 상세
- 기본정보
- 키워드
- 연결 종목
- 자동 추천 후보
- 최근 뉴스 수
- 최근 공시 수

### 8.3 연결 종목 컬럼
- 종목명
- 종목코드
- 대표 테마 여부
- 매핑 출처
- 신뢰도
- 활성 여부
- 비활성/삭제

### 8.4 자동 후보 컬럼
- 추천 종목
- 추천 테마
- 후보 출처
- 신뢰도
- 매칭 키워드
- 근거 수
- 근거 요약
- 상태
- 승인/거절/보류

## 9. 제약조건 및 무결성
- market_themes.theme_code UNIQUE
- market_theme_stocks UNIQUE(theme_id, stock_id)
- market_theme_stock_candidates UNIQUE(theme_id, stock_id, candidate_source)
- FK 적용은 기존 SQLite 운영 규칙/마이그레이션 정책과 일치시켜 점진 반영

권장 인덱스:
- market_themes(is_active, sort_order)
- market_theme_stocks(theme_id, is_active)
- market_theme_stocks(stock_id, is_active)
- market_theme_stock_candidates(status, updated_at)
- market_theme_stock_candidates(theme_id, stock_id)

## 10. 예시 매핑
- HD현대일렉트릭: 전력기기, 변압기, 전력망
- 한화에어로스페이스: 방산, 우주항공, 항공엔진
- 두산에너빌리티: 원전, 전력, 플랜트

## 11. 비기능/운영 정책
- 자동 매수/매도, 목표가, 확정 상승, 수익률 예측 기능/문구는 배제
- 테마 강도는 분석 우선순위 참고값으로만 사용
- 사용자 승인 없는 자동 정식 매핑 금지
- 이력 추적을 위해 상태 변경(approved/rejected/ignored) 타임스탬프 기록 권장

## 12. 후속 구현 제안(23-2 이후)
1. DB 마이그레이션: market_themes, market_theme_stocks, market_theme_stock_candidates
2. 테마/매핑 CRUD API 구현
3. 시장 테마 관리 화면 MVP 구현(수동 등록·수동 매핑)
4. 후보 생성 배치(job) 초안 구현(뉴스/공시 키워드)
5. 승인 워크플로우 구현 및 후보->정식 매핑 반영
6. 테마별 집계 API(거래대금, 평균 등락률, 뉴스/공시 건수)
