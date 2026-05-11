-- Datetime storage standard: YYYY-MM-DD HH:MM:SS (TEXT)\nPRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS stocks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    stock_code TEXT NOT NULL UNIQUE,
    stock_name TEXT NOT NULL,
    market TEXT,
    sector TEXT,
    industry TEXT,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS watchlist (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    stock_id INTEGER NOT NULL,
    status TEXT NOT NULL,
    interest_reason TEXT,
    entry_condition TEXT,
    exit_condition TEXT,
    risk_note TEXT,
    is_active INTEGER NOT NULL DEFAULT 1,
    registered_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (stock_id) REFERENCES stocks(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS news_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    stock_id INTEGER,
    title TEXT NOT NULL,
    source TEXT,
    url TEXT UNIQUE,
    published_at TEXT,
    collected_at TEXT NOT NULL,
    raw_text_path TEXT,
    summary TEXT,
    sentiment TEXT,
    importance_score INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    FOREIGN KEY (stock_id) REFERENCES stocks(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS disclosures (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    stock_id INTEGER NOT NULL,
    dart_receipt_no TEXT UNIQUE,
    disclosure_title TEXT NOT NULL,
    disclosure_type TEXT,
    disclosed_at TEXT,
    url TEXT,
    raw_text_path TEXT,
    summary TEXT,
    importance_score INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    FOREIGN KEY (stock_id) REFERENCES stocks(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS price_daily (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    stock_id INTEGER NOT NULL,
    trade_date TEXT NOT NULL,
    open_price REAL,
    high_price REAL,
    low_price REAL,
    close_price REAL,
    volume INTEGER,
    trading_value REAL,
    change_rate REAL,
    created_at TEXT NOT NULL,
    UNIQUE (stock_id, trade_date),
    FOREIGN KEY (stock_id) REFERENCES stocks(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS research_reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    stock_id INTEGER,
    report_type TEXT NOT NULL,
    title TEXT NOT NULL,
    report_date TEXT NOT NULL,
    summary TEXT,
    markdown_path TEXT NOT NULL,
    generated_by TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (stock_id) REFERENCES stocks(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS gpt_advisories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    stock_id INTEGER,
    source_report_id INTEGER,
    prompt_path TEXT NOT NULL,
    response_path TEXT,
    advisory_summary TEXT,
    final_opinion TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (stock_id) REFERENCES stocks(id) ON DELETE SET NULL,
    FOREIGN KEY (source_report_id) REFERENCES research_reports(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS investment_decisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    stock_id INTEGER NOT NULL,
    decision_date TEXT NOT NULL,
    decision_type TEXT NOT NULL,
    reason TEXT,
    expected_scenario TEXT,
    invalidation_condition TEXT,
    stop_loss_condition TEXT,
    review_date TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (stock_id) REFERENCES stocks(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS risk_reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    stock_id INTEGER NOT NULL,
    report_id INTEGER,
    risk_level TEXT,
    risk_summary TEXT,
    buy_prohibited_reason TEXT,
    stop_loss_condition TEXT,
    position_size_suggestion TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (stock_id) REFERENCES stocks(id) ON DELETE CASCADE,
    FOREIGN KEY (report_id) REFERENCES research_reports(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS trade_reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    stock_id INTEGER NOT NULL,
    decision_id INTEGER,
    review_date TEXT NOT NULL,
    result_summary TEXT,
    what_was_right TEXT,
    what_was_wrong TEXT,
    lesson_learned TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (stock_id) REFERENCES stocks(id) ON DELETE CASCADE,
    FOREIGN KEY (decision_id) REFERENCES investment_decisions(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS collection_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    collector_name TEXT NOT NULL,
    target TEXT,
    status TEXT NOT NULL,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    message TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS schema_comments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    table_name TEXT NOT NULL,
    column_name TEXT,
    comment_ko TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE (table_name, column_name)
);

CREATE INDEX IF NOT EXISTS idx_stocks_stock_code ON stocks(stock_code);
CREATE INDEX IF NOT EXISTS idx_watchlist_stock_id ON watchlist(stock_id);
CREATE INDEX IF NOT EXISTS idx_news_items_stock_id ON news_items(stock_id);
CREATE INDEX IF NOT EXISTS idx_news_items_published_at ON news_items(published_at);
CREATE INDEX IF NOT EXISTS idx_disclosures_stock_id ON disclosures(stock_id);
CREATE INDEX IF NOT EXISTS idx_disclosures_disclosed_at ON disclosures(disclosed_at);
CREATE INDEX IF NOT EXISTS idx_price_daily_stock_date ON price_daily(stock_id, trade_date);
CREATE INDEX IF NOT EXISTS idx_research_reports_stock_id ON research_reports(stock_id);
CREATE INDEX IF NOT EXISTS idx_investment_decisions_stock_id ON investment_decisions(stock_id);
CREATE INDEX IF NOT EXISTS idx_collection_runs_collector_name ON collection_runs(collector_name);

INSERT OR IGNORE INTO schema_comments (table_name, column_name, comment_ko, created_at) VALUES
('stocks', NULL, '종목 마스터 정보', CURRENT_TIMESTAMP),
('watchlist', NULL, '관심종목 관리 정보', CURRENT_TIMESTAMP),
('news_items', NULL, '뉴스 수집 및 요약 정보', CURRENT_TIMESTAMP),
('disclosures', NULL, '공시 수집 및 요약 정보', CURRENT_TIMESTAMP),
('price_daily', NULL, '일별 시세 정보', CURRENT_TIMESTAMP),
('research_reports', NULL, '리서치 보고서 메타정보', CURRENT_TIMESTAMP),
('gpt_advisories', NULL, 'GPT 자문 결과 정보', CURRENT_TIMESTAMP),
('investment_decisions', NULL, '투자 의사결정 기록', CURRENT_TIMESTAMP),
('risk_reviews', NULL, '리스크 점검 기록', CURRENT_TIMESTAMP),
('trade_reviews', NULL, '매매 복기 기록', CURRENT_TIMESTAMP),
('collection_runs', NULL, '수집 작업 실행 이력', CURRENT_TIMESTAMP),
('schema_comments', NULL, '테이블/컬럼 한글 설명 메타데이터', CURRENT_TIMESTAMP);

INSERT OR IGNORE INTO schema_comments (table_name, column_name, comment_ko, created_at) VALUES
('stocks', 'id', '종목 PK', CURRENT_TIMESTAMP),
('stocks', 'stock_code', '종목 코드', CURRENT_TIMESTAMP),
('stocks', 'stock_name', '종목명', CURRENT_TIMESTAMP),
('stocks', 'market', '시장 구분', CURRENT_TIMESTAMP),
('stocks', 'sector', '섹터', CURRENT_TIMESTAMP),
('stocks', 'industry', '업종', CURRENT_TIMESTAMP),
('stocks', 'is_active', '활성 여부(1:활성, 0:비활성)', CURRENT_TIMESTAMP),
('stocks', 'created_at', '생성 시각(YYYY-MM-DD HH:MM:SS TEXT)', CURRENT_TIMESTAMP),
('stocks', 'updated_at', '수정 시각(YYYY-MM-DD HH:MM:SS TEXT)', CURRENT_TIMESTAMP),
('watchlist', 'id', '관심종목 PK', CURRENT_TIMESTAMP),
('watchlist', 'stock_id', '종목 FK', CURRENT_TIMESTAMP),
('watchlist', 'status', '관심 상태', CURRENT_TIMESTAMP),
('watchlist', 'interest_reason', '관심 사유', CURRENT_TIMESTAMP),
('watchlist', 'entry_condition', '진입 조건', CURRENT_TIMESTAMP),
('watchlist', 'exit_condition', '이탈 조건', CURRENT_TIMESTAMP),
('watchlist', 'risk_note', '리스크 메모', CURRENT_TIMESTAMP),
('watchlist', 'is_active', '활성 여부(1:활성, 0:비활성)', CURRENT_TIMESTAMP),
('watchlist', 'registered_at', '등록 시각(YYYY-MM-DD HH:MM:SS TEXT)', CURRENT_TIMESTAMP),
('watchlist', 'updated_at', '수정 시각(YYYY-MM-DD HH:MM:SS TEXT)', CURRENT_TIMESTAMP),
('news_items', 'id', '뉴스 PK', CURRENT_TIMESTAMP),
('news_items', 'stock_id', '종목 FK(선택)', CURRENT_TIMESTAMP),
('news_items', 'title', '뉴스 제목', CURRENT_TIMESTAMP),
('news_items', 'source', '뉴스 출처', CURRENT_TIMESTAMP),
('news_items', 'url', '뉴스 URL', CURRENT_TIMESTAMP),
('news_items', 'published_at', '기사 게시 시각(YYYY-MM-DD HH:MM:SS TEXT)', CURRENT_TIMESTAMP),
('news_items', 'collected_at', '수집 시각(YYYY-MM-DD HH:MM:SS TEXT)', CURRENT_TIMESTAMP),
('news_items', 'raw_text_path', '원문 파일 경로', CURRENT_TIMESTAMP),
('news_items', 'summary', '요약 내용', CURRENT_TIMESTAMP),
('news_items', 'sentiment', '감성 분류', CURRENT_TIMESTAMP),
('news_items', 'importance_score', '중요도 점수', CURRENT_TIMESTAMP),
('news_items', 'created_at', '생성 시각(YYYY-MM-DD HH:MM:SS TEXT)', CURRENT_TIMESTAMP),
('disclosures', 'id', '공시 PK', CURRENT_TIMESTAMP),
('disclosures', 'stock_id', '종목 FK', CURRENT_TIMESTAMP),
('disclosures', 'dart_receipt_no', 'DART 접수번호', CURRENT_TIMESTAMP),
('disclosures', 'disclosure_title', '공시 제목', CURRENT_TIMESTAMP),
('disclosures', 'disclosure_type', '공시 유형', CURRENT_TIMESTAMP),
('disclosures', 'disclosed_at', '공시 시각(YYYY-MM-DD HH:MM:SS TEXT)', CURRENT_TIMESTAMP),
('disclosures', 'url', '공시 URL', CURRENT_TIMESTAMP),
('disclosures', 'raw_text_path', '원문 파일 경로', CURRENT_TIMESTAMP),
('disclosures', 'summary', '요약 내용', CURRENT_TIMESTAMP),
('disclosures', 'importance_score', '중요도 점수', CURRENT_TIMESTAMP),
('disclosures', 'created_at', '생성 시각(YYYY-MM-DD HH:MM:SS TEXT)', CURRENT_TIMESTAMP),
('price_daily', 'id', '일별시세 PK', CURRENT_TIMESTAMP),
('price_daily', 'stock_id', '종목 FK', CURRENT_TIMESTAMP),
('price_daily', 'trade_date', '거래일(YYYY-MM-DD)', CURRENT_TIMESTAMP),
('price_daily', 'open_price', '시가', CURRENT_TIMESTAMP),
('price_daily', 'high_price', '고가', CURRENT_TIMESTAMP),
('price_daily', 'low_price', '저가', CURRENT_TIMESTAMP),
('price_daily', 'close_price', '종가', CURRENT_TIMESTAMP),
('price_daily', 'volume', '거래량', CURRENT_TIMESTAMP),
('price_daily', 'trading_value', '거래대금', CURRENT_TIMESTAMP),
('price_daily', 'change_rate', '등락률', CURRENT_TIMESTAMP),
('price_daily', 'created_at', '생성 시각(YYYY-MM-DD HH:MM:SS TEXT)', CURRENT_TIMESTAMP),
('research_reports', 'id', '리서치 보고서 PK', CURRENT_TIMESTAMP),
('research_reports', 'stock_id', '종목 FK(선택)', CURRENT_TIMESTAMP),
('research_reports', 'report_type', '보고서 유형', CURRENT_TIMESTAMP),
('research_reports', 'title', '보고서 제목', CURRENT_TIMESTAMP),
('research_reports', 'report_date', '보고서 기준일(YYYY-MM-DD HH:MM:SS TEXT)', CURRENT_TIMESTAMP),
('research_reports', 'summary', '요약 내용', CURRENT_TIMESTAMP),
('research_reports', 'markdown_path', '마크다운 파일 경로', CURRENT_TIMESTAMP),
('research_reports', 'generated_by', '생성 주체', CURRENT_TIMESTAMP),
('research_reports', 'created_at', '생성 시각(YYYY-MM-DD HH:MM:SS TEXT)', CURRENT_TIMESTAMP),
('gpt_advisories', 'id', 'GPT 자문 PK', CURRENT_TIMESTAMP),
('gpt_advisories', 'stock_id', '종목 FK(선택)', CURRENT_TIMESTAMP),
('gpt_advisories', 'source_report_id', '원본 보고서 FK(선택)', CURRENT_TIMESTAMP),
('gpt_advisories', 'prompt_path', '프롬프트 파일 경로', CURRENT_TIMESTAMP),
('gpt_advisories', 'response_path', '응답 파일 경로', CURRENT_TIMESTAMP),
('gpt_advisories', 'advisory_summary', '자문 요약', CURRENT_TIMESTAMP),
('gpt_advisories', 'final_opinion', '최종 의견', CURRENT_TIMESTAMP),
('gpt_advisories', 'created_at', '생성 시각(YYYY-MM-DD HH:MM:SS TEXT)', CURRENT_TIMESTAMP),
('investment_decisions', 'id', '투자결정 PK', CURRENT_TIMESTAMP),
('investment_decisions', 'stock_id', '종목 FK', CURRENT_TIMESTAMP),
('investment_decisions', 'decision_date', '결정일(YYYY-MM-DD HH:MM:SS TEXT)', CURRENT_TIMESTAMP),
('investment_decisions', 'decision_type', '결정 유형(매수/매도/관망 등)', CURRENT_TIMESTAMP),
('investment_decisions', 'reason', '결정 사유', CURRENT_TIMESTAMP),
('investment_decisions', 'expected_scenario', '기대 시나리오', CURRENT_TIMESTAMP),
('investment_decisions', 'invalidation_condition', '무효화 조건', CURRENT_TIMESTAMP),
('investment_decisions', 'stop_loss_condition', '손절 조건', CURRENT_TIMESTAMP),
('investment_decisions', 'review_date', '재검토일(YYYY-MM-DD HH:MM:SS TEXT)', CURRENT_TIMESTAMP),
('investment_decisions', 'created_at', '생성 시각(YYYY-MM-DD HH:MM:SS TEXT)', CURRENT_TIMESTAMP),
('risk_reviews', 'id', '리스크 점검 PK', CURRENT_TIMESTAMP),
('risk_reviews', 'stock_id', '종목 FK', CURRENT_TIMESTAMP),
('risk_reviews', 'report_id', '연결 보고서 FK(선택)', CURRENT_TIMESTAMP),
('risk_reviews', 'risk_level', '리스크 수준', CURRENT_TIMESTAMP),
('risk_reviews', 'risk_summary', '리스크 요약', CURRENT_TIMESTAMP),
('risk_reviews', 'buy_prohibited_reason', '매수 금지 사유', CURRENT_TIMESTAMP),
('risk_reviews', 'stop_loss_condition', '손절 조건', CURRENT_TIMESTAMP),
('risk_reviews', 'position_size_suggestion', '비중 제안', CURRENT_TIMESTAMP),
('risk_reviews', 'created_at', '생성 시각(YYYY-MM-DD HH:MM:SS TEXT)', CURRENT_TIMESTAMP),
('trade_reviews', 'id', '매매복기 PK', CURRENT_TIMESTAMP),
('trade_reviews', 'stock_id', '종목 FK', CURRENT_TIMESTAMP),
('trade_reviews', 'decision_id', '투자결정 FK(선택)', CURRENT_TIMESTAMP),
('trade_reviews', 'review_date', '복기일(YYYY-MM-DD HH:MM:SS TEXT)', CURRENT_TIMESTAMP),
('trade_reviews', 'result_summary', '결과 요약', CURRENT_TIMESTAMP),
('trade_reviews', 'what_was_right', '잘한 점', CURRENT_TIMESTAMP),
('trade_reviews', 'what_was_wrong', '아쉬운 점', CURRENT_TIMESTAMP),
('trade_reviews', 'lesson_learned', '교훈', CURRENT_TIMESTAMP),
('trade_reviews', 'created_at', '생성 시각(YYYY-MM-DD HH:MM:SS TEXT)', CURRENT_TIMESTAMP),
('collection_runs', 'id', '수집실행 PK', CURRENT_TIMESTAMP),
('collection_runs', 'collector_name', '수집기 이름', CURRENT_TIMESTAMP),
('collection_runs', 'target', '수집 대상', CURRENT_TIMESTAMP),
('collection_runs', 'status', '실행 상태', CURRENT_TIMESTAMP),
('collection_runs', 'started_at', '시작 시각(YYYY-MM-DD HH:MM:SS TEXT)', CURRENT_TIMESTAMP),
('collection_runs', 'finished_at', '종료 시각(YYYY-MM-DD HH:MM:SS TEXT)', CURRENT_TIMESTAMP),
('collection_runs', 'message', '실행 메시지', CURRENT_TIMESTAMP),
('collection_runs', 'created_at', '생성 시각(YYYY-MM-DD HH:MM:SS TEXT)', CURRENT_TIMESTAMP),
('schema_comments', 'id', '스키마 코멘트 PK', CURRENT_TIMESTAMP),
('schema_comments', 'table_name', '설명 대상 테이블명', CURRENT_TIMESTAMP),
('schema_comments', 'column_name', '설명 대상 컬럼명(NULL이면 테이블 설명)', CURRENT_TIMESTAMP),
('schema_comments', 'comment_ko', '한글 설명', CURRENT_TIMESTAMP),
('schema_comments', 'created_at', '등록 시각(YYYY-MM-DD HH:MM:SS TEXT)', CURRENT_TIMESTAMP);

