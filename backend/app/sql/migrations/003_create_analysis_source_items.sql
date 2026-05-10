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

CREATE INDEX IF NOT EXISTS idx_analysis_source_items_stock_source
ON analysis_source_items(stock_id, source_type, source_id);

CREATE INDEX IF NOT EXISTS idx_analysis_source_items_report
ON analysis_source_items(report_id);
