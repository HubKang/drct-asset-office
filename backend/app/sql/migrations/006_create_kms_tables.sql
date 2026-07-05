CREATE TABLE IF NOT EXISTS kms_categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    parent_id INTEGER,
    name TEXT NOT NULL,
    description TEXT,
    sort_order INTEGER NOT NULL DEFAULT 100,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (parent_id) REFERENCES kms_categories(id) ON DELETE SET NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_kms_categories_parent_name
ON kms_categories(COALESCE(parent_id, -1), name);

CREATE INDEX IF NOT EXISTS idx_kms_categories_active_sort
ON kms_categories(is_active, sort_order);

CREATE TABLE IF NOT EXISTS kms_posts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    summary TEXT,
    content TEXT NOT NULL,
    source_url TEXT,
    importance TEXT NOT NULL DEFAULT '보통',
    learning_status TEXT NOT NULL DEFAULT '미정리',
    is_pinned INTEGER NOT NULL DEFAULT 0,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (category_id) REFERENCES kms_categories(id) ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS idx_kms_posts_category_active
ON kms_posts(category_id, is_active, updated_at);

CREATE INDEX IF NOT EXISTS idx_kms_posts_status_importance
ON kms_posts(learning_status, importance);

CREATE TABLE IF NOT EXISTS kms_tags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    description TEXT,
    use_count INTEGER NOT NULL DEFAULT 0,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_kms_tags_active_count
ON kms_tags(is_active, use_count DESC, name);

CREATE TABLE IF NOT EXISTS kms_post_tags (
    post_id INTEGER NOT NULL,
    tag_id INTEGER NOT NULL,
    PRIMARY KEY (post_id, tag_id),
    FOREIGN KEY (post_id) REFERENCES kms_posts(id) ON DELETE CASCADE,
    FOREIGN KEY (tag_id) REFERENCES kms_tags(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_kms_post_tags_tag_id
ON kms_post_tags(tag_id);

INSERT OR IGNORE INTO kms_categories (parent_id, name, description, sort_order, is_active, created_at, updated_at)
VALUES
(NULL, '시장', NULL, 10, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
(NULL, '재료', NULL, 20, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
(NULL, '수급', NULL, 30, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
(NULL, '차트', NULL, 40, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
(NULL, '재무', NULL, 50, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
(NULL, '기법', NULL, 60, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
(NULL, '심리', NULL, 70, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
(NULL, '리스크', NULL, 80, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
(NULL, '복기', NULL, 90, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
(NULL, '자료', NULL, 100, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP);
