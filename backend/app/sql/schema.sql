-- Datetime storage standard: YYYY-MM-DD HH:MM:SS (TEXT)\nPRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS stocks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    stock_code TEXT NOT NULL UNIQUE,
    stock_name TEXT NOT NULL,
    market TEXT,
    sector TEXT,
    industry TEXT,
    isin_code TEXT,
    corp_name TEXT,
    corp_reg_no TEXT,
    last_synced_at TEXT,
    source TEXT,
    security_type TEXT,
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
    ai_summary TEXT,
    ai_sentiment TEXT,
    ai_importance_score INTEGER DEFAULT 0,
    ai_tags TEXT,
    ai_processed_at TEXT,
    ai_summary_error TEXT,
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
    ai_summary TEXT,
    ai_importance_score INTEGER DEFAULT 0,
    ai_tags TEXT,
    ai_risk_level TEXT,
    ai_event_type TEXT,
    ai_processed_at TEXT,
    ai_summary_error TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (stock_id) REFERENCES stocks(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS stock_daily_prices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    stock_id INTEGER NOT NULL,
    trade_date TEXT NOT NULL,
    open_price REAL,
    high_price REAL,
    low_price REAL,
    close_price REAL,
    change_price REAL,
    change_rate REAL,
    volume INTEGER,
    trading_value INTEGER,
    ma5 REAL,
    ma10 REAL,
    ma20 REAL,
    ma60 REAL,
    ma120 REAL,
    ma240 REAL,
    source TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (stock_id) REFERENCES stocks(id) ON DELETE CASCADE
);


CREATE TABLE IF NOT EXISTS stock_investor_flows (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    stock_id INTEGER NOT NULL,
    stock_code TEXT NOT NULL,
    flow_date TEXT NOT NULL,
    foreign_buy_qty INTEGER,
    foreign_sell_qty INTEGER,
    foreign_net_qty INTEGER,
    foreign_buy_amount INTEGER,
    foreign_sell_amount INTEGER,
    foreign_net_amount INTEGER,
    foreign_holding_qty INTEGER,
    foreign_holding_ratio REAL,
    institution_buy_qty INTEGER,
    institution_sell_qty INTEGER,
    institution_net_qty INTEGER,
    institution_buy_amount INTEGER,
    institution_sell_amount INTEGER,
    institution_net_amount INTEGER,
    financial_investment_net_qty INTEGER,
    insurance_net_qty INTEGER,
    investment_trust_net_qty INTEGER,
    bank_net_qty INTEGER,
    other_finance_net_qty INTEGER,
    pension_fund_net_qty INTEGER,
    private_fund_net_qty INTEGER,
    other_corporation_net_qty INTEGER,
    program_buy_qty INTEGER,
    program_sell_qty INTEGER,
    program_net_qty INTEGER,
    program_buy_amount INTEGER,
    program_sell_amount INTEGER,
    program_net_amount INTEGER,
    program_arbitrage_net_qty INTEGER,
    program_non_arbitrage_net_qty INTEGER,
    source TEXT NOT NULL DEFAULT 'derived_price_flow',
    data_source_type TEXT NOT NULL DEFAULT 'DERIVED_PRICE_FLOW',
    source_method TEXT NOT NULL DEFAULT 'derived_price_flow',
    is_real_investor_flow INTEGER NOT NULL DEFAULT 0,
    collection_status TEXT NOT NULL DEFAULT 'SUCCESS',
    raw_json TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (stock_id) REFERENCES stocks(id) ON DELETE CASCADE,
    UNIQUE (stock_id, flow_date)
);
CREATE TABLE IF NOT EXISTS stock_daily_market_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    stock_id INTEGER NOT NULL,
    trade_date TEXT NOT NULL,
    market TEXT,
    close_price REAL,
    market_cap INTEGER,
    listed_shares INTEGER,
    trading_volume INTEGER,
    trading_value INTEGER,
    market_cap_rank INTEGER,
    trading_value_rank INTEGER,
    market_trading_value_rank INTEGER,
    trading_value_percentile REAL,
    market_trading_value_percentile REAL,
    source TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (stock_id) REFERENCES stocks(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS stock_daily_technical_indicators (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    stock_id INTEGER NOT NULL,
    trade_date TEXT NOT NULL,
    rsi14 REAL,
    macd REAL,
    macd_signal REAL,
    macd_histogram REAL,
    bb_upper REAL,
    bb_middle REAL,
    bb_lower REAL,
    bb_width REAL,
    bb_close_position TEXT,
    atr14 REAL,
    atr14_ratio_to_close REAL,
    ma5_gap_pct REAL,
    ma10_gap_pct REAL,
    ma20_gap_pct REAL,
    ma60_gap_pct REAL,
    ma120_gap_pct REAL,
    ma240_gap_pct REAL,
    volume_ma5 REAL,
    volume_ma20 REAL,
    volume_5_20_ratio REAL,
    source TEXT NOT NULL DEFAULT 'calculated',
    calculation_version TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
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
    markdown_content TEXT,
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

CREATE TABLE IF NOT EXISTS analysis_source_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    report_id INTEGER NOT NULL,
    stock_id INTEGER NOT NULL,
    source_type TEXT NOT NULL,
    source_id INTEGER NOT NULL,
    used_stage TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (report_id) REFERENCES research_reports(id) ON DELETE CASCADE,
    FOREIGN KEY (stock_id) REFERENCES stocks(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS classification_rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    rule_group TEXT NOT NULL,
    target_type TEXT NOT NULL,
    rule_name TEXT NOT NULL,
    keywords TEXT NOT NULL,
    output_field TEXT NOT NULL,
    output_value TEXT NOT NULL,
    score_delta INTEGER DEFAULT 0,
    priority INTEGER DEFAULT 100,
    is_active INTEGER DEFAULT 1,
    description TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS gpt_prompt_templates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    prompt_key TEXT NOT NULL UNIQUE,
    prompt_name TEXT NOT NULL,
    prompt_type TEXT NOT NULL,
    description TEXT,
    template_text TEXT NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 1,
    is_default INTEGER NOT NULL DEFAULT 0,
    version INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS market_themes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    theme_name TEXT NOT NULL,
    theme_code TEXT NOT NULL UNIQUE,
    theme_type TEXT NOT NULL,
    theme_level TEXT NOT NULL DEFAULT 'THEME',
    description TEXT,
    keywords TEXT NOT NULL DEFAULT '[]',
    parent_theme_id INTEGER,
    is_supply_theme INTEGER NOT NULL DEFAULT 0,
    is_active INTEGER NOT NULL DEFAULT 1,
    sort_order INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (parent_theme_id) REFERENCES market_themes(id)
);

CREATE TABLE IF NOT EXISTS market_theme_stocks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    theme_id INTEGER NOT NULL,
    stock_id INTEGER NOT NULL,
    mapping_source TEXT NOT NULL DEFAULT 'manual',
    confidence_score REAL,
    is_primary INTEGER NOT NULL DEFAULT 0,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE (theme_id, stock_id),
    FOREIGN KEY (theme_id) REFERENCES market_themes(id) ON DELETE CASCADE,
    FOREIGN KEY (stock_id) REFERENCES stocks(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS market_theme_stock_candidates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    theme_id INTEGER NOT NULL,
    stock_id INTEGER NOT NULL,
    candidate_source TEXT NOT NULL,
    confidence_score REAL,
    matched_keywords TEXT,
    evidence_count INTEGER NOT NULL DEFAULT 1,
    evidence_summary TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    review_memo TEXT,
    reviewed_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE (theme_id, stock_id, candidate_source),
    FOREIGN KEY (theme_id) REFERENCES market_themes(id) ON DELETE CASCADE,
    FOREIGN KEY (stock_id) REFERENCES stocks(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS schema_comments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    table_name TEXT NOT NULL,
    column_name TEXT,
    comment_ko TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE (table_name, column_name)
);


CREATE TABLE IF NOT EXISTS watchlist_evaluation_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_date TEXT NOT NULL,
    run_type TEXT NOT NULL DEFAULT 'MANUAL',
    status TEXT NOT NULL DEFAULT 'SUCCESS',
    memo TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS watchlist_evaluation_scores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL,
    watchlist_stock_id INTEGER NOT NULL,
    stock_id INTEGER NOT NULL,
    evaluated_at TEXT NOT NULL,
    market_score REAL,
    material_score REAL,
    supply_score REAL,
    chart_score REAL,
    financial_score REAL,
    total_score REAL,
    market_status TEXT,
    material_status TEXT,
    supply_status TEXT,
    chart_status TEXT,
    financial_status TEXT,
    overall_status TEXT,
    data_confidence TEXT NOT NULL DEFAULT 'NOT_EVALUATED',
    risk_flags_json TEXT NOT NULL DEFAULT '[]',
    missing_data_json TEXT NOT NULL DEFAULT '[]',
    summary_text TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (run_id) REFERENCES watchlist_evaluation_runs(id) ON DELETE CASCADE,
    FOREIGN KEY (watchlist_stock_id) REFERENCES watchlist(id) ON DELETE CASCADE,
    FOREIGN KEY (stock_id) REFERENCES stocks(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS watchlist_evaluation_factors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    score_id INTEGER NOT NULL,
    category TEXT NOT NULL,
    factor_code TEXT NOT NULL,
    factor_name TEXT NOT NULL,
    raw_value TEXT,
    normalized_score REAL,
    weight REAL,
    contribution_score REAL,
    reason TEXT,
    source_table TEXT,
    source_date TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (score_id) REFERENCES watchlist_evaluation_scores(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_watchlist_evaluation_scores_watchlist ON watchlist_evaluation_scores(watchlist_stock_id, evaluated_at);
CREATE INDEX IF NOT EXISTS idx_watchlist_evaluation_scores_run ON watchlist_evaluation_scores(run_id);
CREATE INDEX IF NOT EXISTS idx_watchlist_evaluation_factors_score ON watchlist_evaluation_factors(score_id);
CREATE INDEX IF NOT EXISTS idx_stocks_stock_code ON stocks(stock_code);
CREATE INDEX IF NOT EXISTS idx_watchlist_stock_id ON watchlist(stock_id);
CREATE INDEX IF NOT EXISTS idx_news_items_stock_id ON news_items(stock_id);
CREATE INDEX IF NOT EXISTS idx_news_items_published_at ON news_items(published_at);
CREATE INDEX IF NOT EXISTS idx_disclosures_stock_id ON disclosures(stock_id);
CREATE INDEX IF NOT EXISTS idx_disclosures_disclosed_at ON disclosures(disclosed_at);
CREATE UNIQUE INDEX IF NOT EXISTS ux_stock_daily_prices_stock_date ON stock_daily_prices(stock_id, trade_date);
CREATE INDEX IF NOT EXISTS idx_stock_daily_prices_stock_id ON stock_daily_prices(stock_id);
CREATE INDEX IF NOT EXISTS idx_stock_daily_prices_stock_date ON stock_daily_prices(stock_id, trade_date);
CREATE INDEX IF NOT EXISTS idx_stock_investor_flows_stock_date ON stock_investor_flows(stock_id, flow_date);

CREATE TABLE IF NOT EXISTS kiwoom_condition_searches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    condition_seq TEXT NOT NULL,
    condition_name TEXT NOT NULL,
    source TEXT NOT NULL DEFAULT 'kiwoom_rest',
    is_active INTEGER NOT NULL DEFAULT 1,
    last_synced_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE (source, condition_seq)
);

CREATE TABLE IF NOT EXISTS kiwoom_condition_result_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    condition_id INTEGER,
    condition_seq TEXT NOT NULL,
    condition_name TEXT,
    stock_code TEXT NOT NULL,
    stock_code_raw TEXT,
    stock_name TEXT,
    current_price INTEGER,
    change_rate REAL,
    intraday_change_rate REAL,
    trading_value INTEGER,
    volume INTEGER,
    detected_at TEXT NOT NULL,
    source TEXT NOT NULL DEFAULT 'kiwoom_rest',
    source_api TEXT,
    raw_json TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (condition_id) REFERENCES kiwoom_condition_searches(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS daily_theme_flow_ranks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trade_date TEXT NOT NULL,
    market_theme_id INTEGER NOT NULL,
    auto_rank INTEGER,
    manual_rank INTEGER,
    final_rank INTEGER,
    rank_score REAL NOT NULL DEFAULT 0,
    rank_basis TEXT NOT NULL DEFAULT 'auto',
    user_memo TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE (trade_date, market_theme_id),
    FOREIGN KEY (market_theme_id) REFERENCES market_themes(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS briefing_sources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_type TEXT NOT NULL,
    source_name TEXT NOT NULL,
    source_url TEXT NOT NULL,
    channel_id TEXT,
    playlist_id TEXT,
    is_default INTEGER NOT NULL DEFAULT 0,
    is_active INTEGER NOT NULL DEFAULT 1,
    last_checked_at TEXT,
    deleted_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS briefing_videos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id INTEGER,
    video_id TEXT NOT NULL UNIQUE,
    video_url TEXT NOT NULL,
    title TEXT NOT NULL,
    channel_name TEXT,
    published_at TEXT,
    duration_seconds INTEGER,
    thumbnail_url TEXT,
    description_summary TEXT,
    transcript_status TEXT NOT NULL DEFAULT 'unknown',
    transcript_language TEXT,
    transcript_source TEXT,
    transcript_checked_at TEXT,
    transcript_text_length INTEGER,
    transcript_chunk_count INTEGER,
    analysis_status TEXT NOT NULL DEFAULT 'pending',
    last_analyzed_at TEXT,
    error_message TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (source_id) REFERENCES briefing_sources(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS briefing_summaries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    video_id INTEGER NOT NULL,
    summary_type TEXT NOT NULL,
    model_name TEXT,
    summary_text TEXT,
    key_points_json TEXT,
    topic_json TEXT,
    stock_mentions_json TEXT,
    theme_mentions_json TEXT,
    risk_points_json TEXT,
    elapsed_seconds INTEGER,
    chunk_count INTEGER,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (video_id) REFERENCES briefing_videos(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS briefing_topic_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    video_id INTEGER NOT NULL,
    topic_name TEXT NOT NULL,
    summary TEXT,
    importance_score INTEGER,
    related_themes_json TEXT,
    related_stocks_json TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (video_id) REFERENCES briefing_videos(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS briefing_theme_links (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    video_id INTEGER NOT NULL,
    market_theme_id INTEGER NOT NULL,
    link_reason TEXT,
    confidence_level TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE (video_id, market_theme_id),
    FOREIGN KEY (video_id) REFERENCES briefing_videos(id) ON DELETE CASCADE,
    FOREIGN KEY (market_theme_id) REFERENCES market_themes(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS briefing_summary_jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    video_id TEXT NOT NULL,
    status TEXT NOT NULL,
    progress_percent INTEGER NOT NULL DEFAULT 0,
    current_step TEXT,
    current_chunk INTEGER NOT NULL DEFAULT 0,
    total_chunks INTEGER NOT NULL DEFAULT 0,
    summary_id INTEGER,
    error_message TEXT,
    started_at TEXT,
    finished_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS telegram_sources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_name TEXT NOT NULL,
    channel_username TEXT NOT NULL,
    channel_title TEXT,
    source_type TEXT NOT NULL DEFAULT 'channel',
    description TEXT,
    is_active INTEGER NOT NULL DEFAULT 1,
    is_default INTEGER NOT NULL DEFAULT 0,
    is_deleted INTEGER NOT NULL DEFAULT 0,
    last_collected_message_id INTEGER,
    last_collected_at TEXT,
    memo TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT
);

CREATE TABLE IF NOT EXISTS telegram_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id INTEGER NOT NULL,
    telegram_message_id INTEGER NOT NULL,
    message_date TEXT NOT NULL,
    message_text TEXT,
    message_text_length INTEGER,
    item_title TEXT,
    item_url TEXT,
    normalized_url TEXT,
    publisher TEXT,
    message_type TEXT NOT NULL DEFAULT 'unknown',
    item_category TEXT NOT NULL DEFAULT '기타',
    summary_text TEXT,
    key_points_json TEXT,
    summary_error_message TEXT,
    tag TEXT,
    score INTEGER NOT NULL DEFAULT 50,
    sentiment TEXT NOT NULL DEFAULT 'neutral',
    risk_level TEXT NOT NULL DEFAULT 'unknown',
    event_type TEXT NOT NULL DEFAULT '기타',
    related_stock_code TEXT,
    related_stock_name TEXT,
    related_theme TEXT,
    llm_model TEXT,
    summary_status TEXT NOT NULL DEFAULT 'pending',
    summary_has_content INTEGER NOT NULL DEFAULT 0,
    analysis_status TEXT NOT NULL DEFAULT 'pending',
    collected_at TEXT NOT NULL,
    summarized_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT,
    FOREIGN KEY (source_id) REFERENCES telegram_sources(id)
);

CREATE TABLE IF NOT EXISTS telegram_daily_summaries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    summary_date TEXT NOT NULL,
    source_id INTEGER NOT NULL DEFAULT 0,
    item_count INTEGER NOT NULL DEFAULT 0,
    summary_text TEXT,
    key_points_json TEXT,
    theme_mentions_json TEXT,
    stock_mentions_json TEXT,
    risk_points_json TEXT,
    top_tags_json TEXT,
    top_event_types_json TEXT,
    message_type_stats_json TEXT,
    market_view TEXT,
    summary_has_content INTEGER NOT NULL DEFAULT 0,
    llm_model TEXT,
    elapsed_seconds INTEGER,
    created_at TEXT NOT NULL,
    updated_at TEXT,
    FOREIGN KEY (source_id) REFERENCES telegram_sources(id)
);

CREATE INDEX IF NOT EXISTS idx_kiwoom_condition_searches_source_seq ON kiwoom_condition_searches(source, condition_seq);
CREATE INDEX IF NOT EXISTS idx_kiwoom_condition_result_items_condition_seq ON kiwoom_condition_result_items(condition_seq);
CREATE INDEX IF NOT EXISTS idx_kiwoom_condition_result_items_stock_code ON kiwoom_condition_result_items(stock_code);
CREATE INDEX IF NOT EXISTS idx_kiwoom_condition_result_items_detected_at ON kiwoom_condition_result_items(detected_at);
CREATE INDEX IF NOT EXISTS idx_daily_theme_flow_ranks_trade_date ON daily_theme_flow_ranks(trade_date);
CREATE INDEX IF NOT EXISTS idx_daily_theme_flow_ranks_market_theme_id ON daily_theme_flow_ranks(market_theme_id);
CREATE INDEX IF NOT EXISTS idx_daily_theme_flow_ranks_final_rank ON daily_theme_flow_ranks(final_rank);
CREATE INDEX IF NOT EXISTS idx_briefing_sources_source_type ON briefing_sources(source_type);
CREATE INDEX IF NOT EXISTS idx_briefing_sources_playlist_id ON briefing_sources(playlist_id);
CREATE INDEX IF NOT EXISTS idx_briefing_sources_channel_id ON briefing_sources(channel_id);
CREATE INDEX IF NOT EXISTS idx_briefing_sources_is_active ON briefing_sources(is_active);
CREATE INDEX IF NOT EXISTS idx_briefing_videos_source_id ON briefing_videos(source_id);
CREATE INDEX IF NOT EXISTS idx_briefing_videos_video_id ON briefing_videos(video_id);
CREATE INDEX IF NOT EXISTS idx_briefing_videos_published_at ON briefing_videos(published_at);
CREATE INDEX IF NOT EXISTS idx_briefing_videos_analysis_status ON briefing_videos(analysis_status);
CREATE INDEX IF NOT EXISTS idx_briefing_videos_transcript_status ON briefing_videos(transcript_status);
CREATE INDEX IF NOT EXISTS idx_briefing_summaries_video_id ON briefing_summaries(video_id);
CREATE INDEX IF NOT EXISTS idx_briefing_summaries_summary_type ON briefing_summaries(summary_type);
CREATE INDEX IF NOT EXISTS idx_briefing_topic_items_video_id ON briefing_topic_items(video_id);
CREATE INDEX IF NOT EXISTS idx_briefing_topic_items_topic_name ON briefing_topic_items(topic_name);
CREATE INDEX IF NOT EXISTS idx_briefing_summary_jobs_video_id ON briefing_summary_jobs(video_id);
CREATE INDEX IF NOT EXISTS idx_briefing_summary_jobs_status ON briefing_summary_jobs(status);
CREATE UNIQUE INDEX IF NOT EXISTS ux_telegram_sources_channel_username ON telegram_sources(channel_username);
CREATE UNIQUE INDEX IF NOT EXISTS ux_telegram_items_source_msg ON telegram_items(source_id, telegram_message_id);
CREATE INDEX IF NOT EXISTS ix_telegram_items_message_date ON telegram_items(message_date);
CREATE INDEX IF NOT EXISTS ix_telegram_items_source_date ON telegram_items(source_id, message_date);
CREATE INDEX IF NOT EXISTS ix_telegram_items_message_type ON telegram_items(message_type);
CREATE INDEX IF NOT EXISTS ix_telegram_items_tag ON telegram_items(tag);
CREATE INDEX IF NOT EXISTS ix_telegram_items_normalized_url ON telegram_items(normalized_url);
CREATE UNIQUE INDEX IF NOT EXISTS ux_telegram_daily_summaries_date_source ON telegram_daily_summaries(summary_date, source_id);
CREATE INDEX IF NOT EXISTS idx_stock_daily_prices_stock_trade_date ON stock_daily_prices(stock_id, trade_date);
CREATE INDEX IF NOT EXISTS idx_stock_daily_prices_trade_date ON stock_daily_prices(trade_date);
CREATE UNIQUE INDEX IF NOT EXISTS ux_stock_daily_market_metrics_stock_date_source ON stock_daily_market_metrics(stock_id, trade_date, source);
CREATE UNIQUE INDEX IF NOT EXISTS ux_stock_daily_technical_indicators_stock_date ON stock_daily_technical_indicators(stock_id, trade_date);
CREATE INDEX IF NOT EXISTS idx_stock_daily_market_metrics_trade_date ON stock_daily_market_metrics(trade_date);
CREATE INDEX IF NOT EXISTS idx_stock_daily_market_metrics_stock_id ON stock_daily_market_metrics(stock_id);
CREATE INDEX IF NOT EXISTS idx_stock_daily_market_metrics_source ON stock_daily_market_metrics(source);
CREATE INDEX IF NOT EXISTS idx_stock_daily_market_metrics_trade_rank ON stock_daily_market_metrics(trade_date, trading_value_rank);
CREATE INDEX IF NOT EXISTS idx_stock_daily_market_metrics_trade_market_rank ON stock_daily_market_metrics(trade_date, market, market_trading_value_rank);
CREATE INDEX IF NOT EXISTS idx_stock_daily_market_metrics_stock_trade_source ON stock_daily_market_metrics(stock_id, trade_date, source);
CREATE INDEX IF NOT EXISTS idx_stock_daily_technical_indicators_stock_id ON stock_daily_technical_indicators(stock_id);
CREATE INDEX IF NOT EXISTS idx_stock_daily_technical_indicators_trade_date ON stock_daily_technical_indicators(trade_date);
CREATE INDEX IF NOT EXISTS idx_stock_daily_technical_indicators_stock_trade_date ON stock_daily_technical_indicators(stock_id, trade_date);
CREATE INDEX IF NOT EXISTS idx_stock_daily_technical_indicators_rsi14 ON stock_daily_technical_indicators(rsi14);
CREATE INDEX IF NOT EXISTS idx_stock_daily_technical_indicators_volume_ratio ON stock_daily_technical_indicators(volume_5_20_ratio);
CREATE INDEX IF NOT EXISTS idx_price_daily_stock_date ON price_daily(stock_id, trade_date);
CREATE INDEX IF NOT EXISTS idx_research_reports_stock_id ON research_reports(stock_id);
CREATE INDEX IF NOT EXISTS idx_investment_decisions_stock_id ON investment_decisions(stock_id);
CREATE INDEX IF NOT EXISTS idx_collection_runs_collector_name ON collection_runs(collector_name);
CREATE INDEX IF NOT EXISTS idx_analysis_source_items_stock_source ON analysis_source_items(stock_id, source_type, source_id);
CREATE INDEX IF NOT EXISTS idx_analysis_source_items_report ON analysis_source_items(report_id);
CREATE INDEX IF NOT EXISTS idx_classification_rules_target ON classification_rules(target_type, rule_group, is_active);
CREATE INDEX IF NOT EXISTS idx_classification_rules_priority ON classification_rules(priority);
CREATE INDEX IF NOT EXISTS idx_gpt_prompt_templates_prompt_type ON gpt_prompt_templates(prompt_type);
CREATE INDEX IF NOT EXISTS idx_market_themes_active_sort ON market_themes(is_active, sort_order);
CREATE INDEX IF NOT EXISTS idx_market_themes_type ON market_themes(theme_type);
CREATE INDEX IF NOT EXISTS idx_market_themes_level_parent ON market_themes(theme_level, parent_theme_id);
CREATE INDEX IF NOT EXISTS idx_market_themes_supply_active_sort ON market_themes(is_supply_theme, is_active, sort_order);
CREATE INDEX IF NOT EXISTS idx_market_theme_stocks_theme_active ON market_theme_stocks(theme_id, is_active);
CREATE INDEX IF NOT EXISTS idx_market_theme_stocks_stock_active ON market_theme_stocks(stock_id, is_active);
CREATE INDEX IF NOT EXISTS idx_market_theme_stock_candidates_status_updated ON market_theme_stock_candidates(status, updated_at);
CREATE INDEX IF NOT EXISTS idx_market_theme_stock_candidates_theme_stock ON market_theme_stock_candidates(theme_id, stock_id);

INSERT OR IGNORE INTO market_themes
(theme_name, theme_code, theme_type, theme_level, description, keywords, parent_theme_id, is_supply_theme, is_active, sort_order, created_at, updated_at)
VALUES
('AI', 'ai', 'theme', 'THEME', 'AI 관련 시장 테마', '["AI","인공지능","생성형AI","데이터센터","GPU","LLM","AI반도체"]', NULL, 0, 1, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
('반도체', 'semiconductor', 'theme', 'THEME', '반도체 관련 시장 테마', '["반도체","메모리","파운드리","HBM","시스템반도체","장비"]', NULL, 0, 1, 2, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
('전력기기', 'power_equipment', 'theme', 'THEME', '전력기기 관련 시장 테마', '["전력기기","변압기","송전","배전","전력망","HVDC","초고압","변전소","전선"]', NULL, 0, 1, 3, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
('전력망', 'power_grid', 'theme', 'THEME', '전력망 관련 시장 테마', '["전력망","송전망","배전망","변전","HVDC"]', NULL, 0, 1, 4, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
('변압기', 'transformer', 'theme', 'THEME', '변압기 관련 시장 테마', '["변압기","초고압","배전변압기","송전"]', NULL, 0, 1, 5, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
('방산', 'defense', 'theme', 'THEME', '방위산업 관련 시장 테마', '["방산","방위산업","무기체계","미사일","장갑차","K9","국방","수출계약"]', NULL, 0, 1, 6, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
('조선', 'shipbuilding', 'theme', 'THEME', '조선 관련 시장 테마', '["조선","선박","LNG선","해양플랜트"]', NULL, 0, 1, 7, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
('로봇', 'robot', 'theme', 'THEME', '로봇 관련 시장 테마', '["로봇","협동로봇","자동화","휴머노이드"]', NULL, 0, 1, 8, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
('바이오', 'bio', 'theme', 'THEME', '바이오 관련 시장 테마', '["바이오","임상","신약","FDA","품목허가","항암제","치료제"]', NULL, 0, 1, 9, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
('원전', 'nuclear_power', 'theme', 'THEME', '원전 관련 시장 테마', '["원전","원자력","SMR","원전수출"]', NULL, 0, 1, 10, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
('2차전지', 'secondary_battery', 'theme', 'THEME', '2차전지 관련 시장 테마', '["2차전지","배터리","양극재","음극재","전해질"]', NULL, 0, 1, 11, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
('데이터센터', 'data_center', 'theme', 'THEME', '데이터센터 관련 시장 테마', '["데이터센터","서버","전력수요","냉각"]', NULL, 0, 1, 12, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
('우주항공', 'aerospace', 'theme', 'THEME', '우주항공 관련 시장 테마', '["우주항공","위성","발사체","항공엔진"]', NULL, 0, 1, 13, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
('화장품', 'cosmetics', 'theme', 'THEME', '화장품 관련 시장 테마', '["화장품","K뷰티","면세","수출"]', NULL, 0, 1, 14, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
('엔터', 'entertainment', 'theme', 'THEME', '엔터테인먼트 관련 시장 테마', '["엔터","콘서트","음반","IP"]', NULL, 0, 1, 15, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
('자동차부품', 'auto_parts', 'theme', 'THEME', '자동차부품 관련 시장 테마', '["자동차부품","전장","모듈","완성차공급"]', NULL, 0, 1, 16, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP);

INSERT OR IGNORE INTO schema_comments (table_name, column_name, comment_ko, created_at) VALUES
('stocks', NULL, '종목 마스터 정보', CURRENT_TIMESTAMP),
('watchlist', NULL, '관심종목 관리 정보', CURRENT_TIMESTAMP),
('news_items', NULL, '뉴스 수집 및 요약 정보', CURRENT_TIMESTAMP),
('disclosures', NULL, '공시 수집 및 요약 정보', CURRENT_TIMESTAMP),
('stock_daily_prices', NULL, '관심종목 일봉/이동평균 데이터', CURRENT_TIMESTAMP),
('stock_daily_market_metrics', NULL, '시장지표 일별 데이터(거래대금/시가총액/순위)', CURRENT_TIMESTAMP),
('price_daily', NULL, '일별 시세 정보', CURRENT_TIMESTAMP),
('research_reports', NULL, '리서치 보고서 메타정보', CURRENT_TIMESTAMP),
('gpt_advisories', NULL, 'GPT 자문 결과 정보', CURRENT_TIMESTAMP),
('investment_decisions', NULL, '투자 의사결정 기록', CURRENT_TIMESTAMP),
('risk_reviews', NULL, '리스크 점검 기록', CURRENT_TIMESTAMP),
('trade_reviews', NULL, '매매 복기 기록', CURRENT_TIMESTAMP),
('collection_runs', NULL, '수집 작업 실행 이력', CURRENT_TIMESTAMP),
('analysis_source_items', NULL, '리포트 근거 자료 추적 정보', CURRENT_TIMESTAMP),
('schema_comments', NULL, '테이블/컬럼 한글 설명 메타데이터', CURRENT_TIMESTAMP);

INSERT OR IGNORE INTO schema_comments (table_name, column_name, comment_ko, created_at) VALUES
('stocks', 'id', '종목 PK', CURRENT_TIMESTAMP),
('stocks', 'stock_code', '종목 코드', CURRENT_TIMESTAMP),
('stocks', 'stock_name', '종목명', CURRENT_TIMESTAMP),
('stocks', 'market', '시장 구분', CURRENT_TIMESTAMP),
('stocks', 'sector', '섹터', CURRENT_TIMESTAMP),
('stocks', 'industry', '업종', CURRENT_TIMESTAMP),
('stocks', 'isin_code', 'ISIN 코드', CURRENT_TIMESTAMP),
('stocks', 'corp_name', '법인명', CURRENT_TIMESTAMP),
('stocks', 'corp_reg_no', '법인등록번호', CURRENT_TIMESTAMP),
('stocks', 'last_synced_at', '공식 마스터 동기화 시각(YYYY-MM-DD HH:MM:SS TEXT)', CURRENT_TIMESTAMP),
('stocks', 'source', '종목 데이터 출처', CURRENT_TIMESTAMP),
('stocks', 'security_type', '종목 유형(common_stock/preferred_stock/etf/etn/spac/reit/other)', CURRENT_TIMESTAMP),
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
('news_items', 'ai_summary', '로컬 LLM 기반 1건 요약', CURRENT_TIMESTAMP),
('news_items', 'ai_sentiment', 'AI 감성 분류(positive/neutral/negative)', CURRENT_TIMESTAMP),
('news_items', 'ai_importance_score', 'AI 중요도 점수(0~100)', CURRENT_TIMESTAMP),
('news_items', 'ai_tags', 'AI 태그 목록', CURRENT_TIMESTAMP),
('news_items', 'ai_processed_at', 'AI 처리 시각(YYYY-MM-DD HH:MM:SS TEXT)', CURRENT_TIMESTAMP),
('news_items', 'ai_summary_error', 'AI 요약 실패 메시지', CURRENT_TIMESTAMP),
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
('disclosures', 'ai_summary', '로컬 LLM 기반 공시 1건 요약', CURRENT_TIMESTAMP),
('disclosures', 'ai_importance_score', 'AI 중요도 점수(0~100)', CURRENT_TIMESTAMP),
('disclosures', 'ai_tags', 'AI 태그 목록', CURRENT_TIMESTAMP),
('disclosures', 'ai_risk_level', 'AI 리스크 수준(low/medium/high/unknown)', CURRENT_TIMESTAMP),
('disclosures', 'ai_event_type', 'AI 분류 이벤트 유형', CURRENT_TIMESTAMP),
('disclosures', 'ai_processed_at', 'AI 처리 시각(YYYY-MM-DD HH:MM:SS TEXT)', CURRENT_TIMESTAMP),
('disclosures', 'ai_summary_error', 'AI 요약 실패 메시지', CURRENT_TIMESTAMP),
('disclosures', 'created_at', '생성 시각(YYYY-MM-DD HH:MM:SS TEXT)', CURRENT_TIMESTAMP),
('stock_daily_prices', 'id', '일봉 PK', CURRENT_TIMESTAMP),
('stock_daily_prices', 'stock_id', '종목 FK', CURRENT_TIMESTAMP),
('stock_daily_prices', 'trade_date', '거래일(YYYY-MM-DD)', CURRENT_TIMESTAMP),
('stock_daily_prices', 'open_price', '시가', CURRENT_TIMESTAMP),
('stock_daily_prices', 'high_price', '고가', CURRENT_TIMESTAMP),
('stock_daily_prices', 'low_price', '저가', CURRENT_TIMESTAMP),
('stock_daily_prices', 'close_price', '종가', CURRENT_TIMESTAMP),
('stock_daily_prices', 'change_price', '전일대비 가격 변화', CURRENT_TIMESTAMP),
('stock_daily_prices', 'change_rate', '등락률(%)', CURRENT_TIMESTAMP),
('stock_daily_prices', 'volume', '거래량', CURRENT_TIMESTAMP),
('stock_daily_prices', 'trading_value', '거래대금', CURRENT_TIMESTAMP),
('stock_daily_prices', 'ma5', '5일 이동평균', CURRENT_TIMESTAMP),
('stock_daily_prices', 'ma10', '10일 이동평균', CURRENT_TIMESTAMP),
('stock_daily_prices', 'ma20', '20일 이동평균', CURRENT_TIMESTAMP),
('stock_daily_prices', 'ma60', '60일 이동평균', CURRENT_TIMESTAMP),
('stock_daily_prices', 'ma120', '120일 이동평균', CURRENT_TIMESTAMP),
('stock_daily_prices', 'ma240', '240일 이동평균', CURRENT_TIMESTAMP),
('stock_daily_prices', 'source', '데이터 소스(mock/증권사API)', CURRENT_TIMESTAMP),
('stock_daily_prices', 'created_at', '생성 시각(YYYY-MM-DD HH:MM:SS TEXT)', CURRENT_TIMESTAMP),
('stock_daily_prices', 'updated_at', '수정 시각(YYYY-MM-DD HH:MM:SS TEXT)', CURRENT_TIMESTAMP),
('stock_daily_market_metrics', 'id', '시장지표 PK', CURRENT_TIMESTAMP),
('stock_daily_market_metrics', 'stock_id', '종목 FK', CURRENT_TIMESTAMP),
('stock_daily_market_metrics', 'trade_date', '거래일(YYYY-MM-DD)', CURRENT_TIMESTAMP),
('stock_daily_market_metrics', 'market', '시장 구분', CURRENT_TIMESTAMP),
('stock_daily_market_metrics', 'close_price', '종가', CURRENT_TIMESTAMP),
('stock_daily_market_metrics', 'market_cap', '시가총액', CURRENT_TIMESTAMP),
('stock_daily_market_metrics', 'listed_shares', '상장주식수', CURRENT_TIMESTAMP),
('stock_daily_market_metrics', 'trading_volume', '거래량', CURRENT_TIMESTAMP),
('stock_daily_market_metrics', 'trading_value', '거래대금', CURRENT_TIMESTAMP),
('stock_daily_market_metrics', 'market_cap_rank', '시가총액 순위', CURRENT_TIMESTAMP),
('stock_daily_market_metrics', 'trading_value_rank', '전체 시장 거래대금 순위', CURRENT_TIMESTAMP),
('stock_daily_market_metrics', 'market_trading_value_rank', '시장 내 거래대금 순위', CURRENT_TIMESTAMP),
('stock_daily_market_metrics', 'trading_value_percentile', '전체 시장 거래대금 백분위', CURRENT_TIMESTAMP),
('stock_daily_market_metrics', 'market_trading_value_percentile', '시장 내 거래대금 백분위', CURRENT_TIMESTAMP),
('stock_daily_market_metrics', 'source', '데이터 소스(marcap)', CURRENT_TIMESTAMP),
('stock_daily_market_metrics', 'created_at', '생성 시각(YYYY-MM-DD HH:MM:SS TEXT)', CURRENT_TIMESTAMP),
('stock_daily_market_metrics', 'updated_at', '수정 시각(YYYY-MM-DD HH:MM:SS TEXT)', CURRENT_TIMESTAMP),
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
('research_reports', 'summary', '목록 표시용 짧은 요약', CURRENT_TIMESTAMP),
('research_reports', 'markdown_content', '마크다운 리포트 전문', CURRENT_TIMESTAMP),
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
('analysis_source_items', 'id', '리포트 근거 자료 PK', CURRENT_TIMESTAMP),
('analysis_source_items', 'report_id', '리서치 보고서 FK', CURRENT_TIMESTAMP),
('analysis_source_items', 'stock_id', '종목 FK', CURRENT_TIMESTAMP),
('analysis_source_items', 'source_type', '근거 자료 유형(news/disclosure)', CURRENT_TIMESTAMP),
('analysis_source_items', 'source_id', '근거 자료 원본 ID', CURRENT_TIMESTAMP),
('analysis_source_items', 'used_stage', '사용 단계(chunk_summary/final_briefing)', CURRENT_TIMESTAMP),
('analysis_source_items', 'created_at', '생성 시각(YYYY-MM-DD HH:MM:SS TEXT)', CURRENT_TIMESTAMP),
('schema_comments', 'id', '스키마 코멘트 PK', CURRENT_TIMESTAMP),
('schema_comments', 'table_name', '설명 대상 테이블명', CURRENT_TIMESTAMP),
('schema_comments', 'column_name', '설명 대상 컬럼명(NULL이면 테이블 설명)', CURRENT_TIMESTAMP),
('schema_comments', 'comment_ko', '한글 설명', CURRENT_TIMESTAMP),
('schema_comments', 'created_at', '등록 시각(YYYY-MM-DD HH:MM:SS TEXT)', CURRENT_TIMESTAMP);

INSERT OR IGNORE INTO classification_rules (
    rule_group, target_type, rule_name, keywords, output_field, output_value, score_delta, priority, is_active, description, created_at, updated_at
) VALUES
('tag','news','뉴스_반도체','반도체,hbm,d램,낸드,파운드리,메모리','ai_tags','반도체',10,10,1,'반도체 관련 뉴스 태그',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP),
('tag','news','뉴스_AI','ai,인공지능,데이터센터,gpu,npu','ai_tags','AI',10,20,1,'AI 관련 뉴스 태그',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP),
('tag','news','뉴스_실적','실적,영업이익,매출,어닝,흑자,적자','ai_tags','실적',20,30,1,'실적 관련 뉴스 태그',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP),
('tag','news','뉴스_수주','수주,계약,공급,납품','ai_tags','수주',20,40,1,'수주/계약 뉴스 태그',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP),
('tag','news','뉴스_투자','투자,증설,공장,캠퍼스,라인,설비','ai_tags','투자',15,50,1,'투자/증설 뉴스 태그',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP),
('tag','news','뉴스_신제품','출시,선보였다,앱,서비스,제품','ai_tags','신제품',5,60,1,'신제품 뉴스 태그',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP),
('tag','news','뉴스_지정학','전쟁,중동,호르무즈,중국,미국,관세','ai_tags','지정학',10,70,1,'지정학 이슈 태그',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP),
('tag','news','뉴스_리스크','위기,불확실,우려,하락,부진,차질','ai_tags','리스크',10,80,1,'리스크 뉴스 태그',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP),
('sentiment','news','뉴스_긍정','호조,증가,개선,성장,확대,수주,흑자,상회,기대,강세,상승','ai_sentiment','positive',0,20,1,'긍정 감성 규칙',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP),
('sentiment','news','뉴스_부정','하락,감소,부진,적자,차질,위기,리스크,우려,소송,제재,규제,손실,악화','ai_sentiment','negative',0,20,1,'부정 감성 규칙',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP),
('disclosure_event_type','disclosure','공시_지분변동','주식등의대량보유상황보고서,임원,주요주주,특정증권,소유상황,최대주주,주식변동,소유주식변동,소유주식변동신고서','ai_event_type','지분변동',10,30,1,'지분변동 공시 분류',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP),
('disclosure_event_type','disclosure','공시_실적','잠정실적,영업실적,매출액,손익구조,실적','ai_event_type','실적',20,20,1,'실적 공시 분류',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP),
('disclosure_event_type','disclosure','공시_계약','단일판매,공급계약,수주,계약체결','ai_event_type','계약',20,20,1,'계약 공시 분류',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP),
('disclosure_event_type','disclosure','공시_투자','신규시설투자,타법인출자,투자판단,시설투자','ai_event_type','투자',15,25,1,'투자 공시 분류',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP),
('disclosure_event_type','disclosure','공시_소송','소송,분쟁,판결,중재','ai_event_type','소송',25,10,1,'소송 공시 분류',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP),
('disclosure_event_type','disclosure','공시_자본','유상증자,무상증자,전환사채,신주인수권,사채','ai_event_type','자본',20,15,1,'자본 공시 분류',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP),
('disclosure_event_type','disclosure','공시_배당','배당,현금배당,주당배당금,결산배당,중간배당','ai_event_type','배당',10,35,1,'배당 공시 분류',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP),
('disclosure_event_type','disclosure','공시_자사주','자기주식,자사주,자기주식취득,자기주식처분,자사주신탁','ai_event_type','자사주',10,35,1,'자사주 공시 분류',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP),
('disclosure_event_type','disclosure','공시_주주총회','주주총회,정기주주총회,임시주주총회,의결권','ai_event_type','주주총회',5,40,1,'주주총회 공시 분류',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP),
('disclosure_risk_level','disclosure','공시_고위험','소송,제재,불성실공시,상장폐지,감사의견,관리종목,횡령,배임','ai_risk_level','high',20,10,1,'고위험 공시 분류',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP),
('disclosure_risk_level','disclosure','공시_중위험','유상증자,전환사채,대규모 투자,주요 계약 해지,지분변동','ai_risk_level','medium',10,20,1,'중위험 공시 분류',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP),
('disclosure_risk_level','disclosure','공시_저위험','배당,자사주,주주총회,임원 보유','ai_risk_level','low',0,30,1,'저위험 공시 분류',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP);




CREATE TABLE IF NOT EXISTS stock_financial_snapshots (
 id INTEGER PRIMARY KEY AUTOINCREMENT, stock_id INTEGER NOT NULL, stock_code TEXT NOT NULL,
 snapshot_date TEXT NOT NULL, source_type TEXT NOT NULL, source_method TEXT NOT NULL,
 current_price REAL, market_cap INTEGER, listed_shares INTEGER, per REAL, pbr REAL, eps REAL, bps REAL,
 roe REAL, debt_ratio REAL, reserve_ratio REAL, operating_margin REAL, net_margin REAL,
 created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
 UNIQUE(stock_id, snapshot_date, source_method), FOREIGN KEY(stock_id) REFERENCES stocks(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_stock_financial_snapshots_stock_date ON stock_financial_snapshots(stock_id, snapshot_date);
CREATE TABLE IF NOT EXISTS stock_financial_statements (
 id INTEGER PRIMARY KEY AUTOINCREMENT, stock_id INTEGER NOT NULL, stock_code TEXT NOT NULL,
 statement_type TEXT NOT NULL, fiscal_year INTEGER NOT NULL, fiscal_quarter INTEGER NOT NULL DEFAULT 0,
 period_label TEXT NOT NULL, period_end_date TEXT, source_type TEXT NOT NULL, source_method TEXT NOT NULL,
 revenue INTEGER, operating_profit INTEGER, net_income INTEGER, total_assets INTEGER, total_liabilities INTEGER,
 total_equity INTEGER, operating_cash_flow INTEGER, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
 UNIQUE(stock_id, statement_type, fiscal_year, fiscal_quarter, source_method), FOREIGN KEY(stock_id) REFERENCES stocks(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_stock_financial_statements_stock_period ON stock_financial_statements(stock_id, statement_type, fiscal_year, fiscal_quarter);


CREATE TABLE IF NOT EXISTS stock_external_identifiers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    stock_id INTEGER NOT NULL,
    stock_code TEXT NOT NULL,
    corp_code TEXT NOT NULL,
    corp_name TEXT,
    source_type TEXT NOT NULL,
    source_method TEXT NOT NULL,
    mapped_at TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(stock_code, source_type),
    FOREIGN KEY(stock_id) REFERENCES stocks(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_stock_external_identifiers_stock ON stock_external_identifiers(stock_id, source_type);

CREATE TABLE IF NOT EXISTS stock_shareholder_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    stock_id INTEGER NOT NULL,
    stock_code TEXT NOT NULL,
    snapshot_date TEXT NOT NULL,
    source_type TEXT NOT NULL,
    source_method TEXT NOT NULL,
    report_code TEXT,
    receipt_no TEXT,
    largest_shareholder_name TEXT,
    largest_shareholder_shares INTEGER,
    largest_shareholder_ratio REAL,
    major_shareholder_name TEXT,
    major_shareholder_shares INTEGER,
    major_shareholder_ratio REAL,
    ownership_change_flag INTEGER,
    notes TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(stock_id, snapshot_date, source_method),
    FOREIGN KEY(stock_id) REFERENCES stocks(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_stock_shareholder_snapshots_stock_date ON stock_shareholder_snapshots(stock_id, snapshot_date);

CREATE TABLE IF NOT EXISTS stock_shareholder_changes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    stock_id INTEGER NOT NULL,
    stock_code TEXT NOT NULL,
    report_date TEXT NOT NULL,
    source_type TEXT NOT NULL,
    source_method TEXT NOT NULL,
    report_type TEXT,
    receipt_no TEXT,
    reporter_name TEXT,
    shares INTEGER,
    ratio REAL,
    previous_ratio REAL,
    change_flag INTEGER,
    reason TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(stock_id, report_date, source_method, receipt_no),
    FOREIGN KEY(stock_id) REFERENCES stocks(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_stock_shareholder_changes_stock_date ON stock_shareholder_changes(stock_id, report_date);
