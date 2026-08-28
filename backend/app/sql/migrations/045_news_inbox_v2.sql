-- News Inbox V2 keeps article bodies and provider payloads transient.
ALTER TABLE news_items ADD COLUMN article_fingerprint TEXT;

CREATE INDEX IF NOT EXISTS ix_news_items_stock_fingerprint
ON news_items(stock_id, article_fingerprint)
WHERE article_fingerprint IS NOT NULL;

CREATE TABLE IF NOT EXISTS news_item_exclusions (
    target_date TEXT NOT NULL,
    stock_id INTEGER NOT NULL,
    article_fingerprint TEXT NOT NULL,
    PRIMARY KEY (target_date, stock_id, article_fingerprint)
);

UPDATE news_items SET source = NULL WHERE source = 'naver_news';
