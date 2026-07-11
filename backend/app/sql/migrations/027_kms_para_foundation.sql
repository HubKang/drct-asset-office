CREATE TABLE IF NOT EXISTS kms_setting_groups (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    group_code TEXT NOT NULL UNIQUE,
    group_name TEXT NOT NULL,
    description TEXT,
    sort_order INTEGER NOT NULL DEFAULT 100,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS kms_setting_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    group_id INTEGER NOT NULL,
    item_code TEXT NOT NULL,
    item_name TEXT NOT NULL,
    description TEXT,
    color TEXT,
    icon TEXT,
    sort_order INTEGER NOT NULL DEFAULT 100,
    is_default INTEGER NOT NULL DEFAULT 0,
    is_system INTEGER NOT NULL DEFAULT 0,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (group_id) REFERENCES kms_setting_groups(id) ON DELETE CASCADE
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_kms_setting_items_group_code
ON kms_setting_items(group_id, item_code);

CREATE INDEX IF NOT EXISTS idx_kms_setting_items_group_sort
ON kms_setting_items(group_id, is_active, sort_order);

CREATE TABLE IF NOT EXISTS kms_knowledge_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    legacy_post_id INTEGER UNIQUE,
    legacy_source_type TEXT,
    legacy_source_id INTEGER,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    content_format TEXT NOT NULL DEFAULT 'HTML',
    one_line_conclusion TEXT,
    summary TEXT,
    para_type_id INTEGER,
    category_id INTEGER,
    status_id INTEGER,
    importance_id INTEGER,
    usage_context_id INTEGER,
    source_type_id INTEGER,
    source_url TEXT,
    source_title TEXT,
    ai_extract_status TEXT NOT NULL DEFAULT 'PENDING',
    embedding_status TEXT NOT NULL DEFAULT 'PENDING',
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (legacy_post_id) REFERENCES kms_posts(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_kms_knowledge_items_filters
ON kms_knowledge_items(para_type_id, category_id, status_id, importance_id, is_active);

CREATE UNIQUE INDEX IF NOT EXISTS ux_kms_knowledge_items_legacy_source
ON kms_knowledge_items(legacy_source_type, legacy_source_id);

CREATE TABLE IF NOT EXISTS kms_knowledge_extractions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    knowledge_item_id INTEGER NOT NULL,
    extraction_type TEXT NOT NULL,
    extraction_text TEXT NOT NULL,
    source TEXT NOT NULL DEFAULT 'USER',
    model_name TEXT,
    confidence_score REAL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (knowledge_item_id) REFERENCES kms_knowledge_items(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS kms_knowledge_item_tags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    knowledge_item_id INTEGER NOT NULL,
    tag_id INTEGER NOT NULL,
    weight REAL NOT NULL DEFAULT 1.0,
    source TEXT NOT NULL DEFAULT 'USER',
    is_confirmed INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    UNIQUE (knowledge_item_id, tag_id),
    FOREIGN KEY (knowledge_item_id) REFERENCES kms_knowledge_items(id) ON DELETE CASCADE,
    FOREIGN KEY (tag_id) REFERENCES kms_tags(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_kms_knowledge_item_tags_tag_id
ON kms_knowledge_item_tags(tag_id);
