CREATE TABLE IF NOT EXISTS drct_signal_search_rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    search_version_id INTEGER NOT NULL UNIQUE,
    schema_version INTEGER NOT NULL DEFAULT 1,
    rule_json TEXT NOT NULL,
    validation_status TEXT NOT NULL DEFAULT 'DRAFT'
        CHECK(validation_status IN ('DRAFT','VALID','INVALID')),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(search_version_id) REFERENCES drct_signal_search_versions(id) ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS idx_drct_signal_rules_version
    ON drct_signal_search_rules(search_version_id);
