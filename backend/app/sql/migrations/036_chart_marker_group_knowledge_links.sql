CREATE TABLE IF NOT EXISTS chart_marker_group_knowledge_links (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    marker_group_id INTEGER NOT NULL,
    knowledge_item_id INTEGER NOT NULL,
    sort_order INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(marker_group_id, knowledge_item_id),
    FOREIGN KEY(marker_group_id) REFERENCES chart_marker_groups(id) ON DELETE CASCADE,
    FOREIGN KEY(knowledge_item_id) REFERENCES kms_knowledge_items(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_chart_marker_group_knowledge_sort
ON chart_marker_group_knowledge_links(marker_group_id, sort_order, id);
