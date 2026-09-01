PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS drct_signal_searches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    search_key TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL UNIQUE,
    description TEXT,
    lifecycle_status TEXT NOT NULL DEFAULT 'REFERENCE'
        CHECK(lifecycle_status IN ('REFERENCE','LEARNING','SHADOW','ACTIVE','INACTIVE')),
    display_order INTEGER NOT NULL DEFAULT 100,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS drct_signal_search_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    search_id INTEGER NOT NULL,
    version_no INTEGER NOT NULL,
    hts_reference_conditions TEXT NOT NULL,
    hts_condition_expression TEXT NOT NULL,
    drct_rule_text TEXT,
    change_note TEXT,
    is_current INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(search_id, version_no),
    FOREIGN KEY(search_id) REFERENCES drct_signal_searches(id) ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS drct_signal_search_marker_links (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    search_id INTEGER NOT NULL,
    marker_definition_id INTEGER NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(search_id, marker_definition_id),
    FOREIGN KEY(search_id) REFERENCES drct_signal_searches(id) ON DELETE RESTRICT,
    FOREIGN KEY(marker_definition_id) REFERENCES chart_markers(id) ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS idx_drct_signal_searches_order ON drct_signal_searches(display_order, id);
CREATE INDEX IF NOT EXISTS idx_drct_signal_search_versions_search ON drct_signal_search_versions(search_id, version_no DESC);
CREATE UNIQUE INDEX IF NOT EXISTS uq_drct_signal_search_current_version ON drct_signal_search_versions(search_id) WHERE is_current=1;
CREATE INDEX IF NOT EXISTS idx_drct_signal_marker_links_marker ON drct_signal_search_marker_links(marker_definition_id, search_id);
