CREATE TABLE IF NOT EXISTS conversations (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

ALTER TABLE events ADD COLUMN conversation_id TEXT;
CREATE INDEX IF NOT EXISTS idx_events_conversation ON events(conversation_id);
