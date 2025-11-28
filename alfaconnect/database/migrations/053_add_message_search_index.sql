-- Migration: Add full-text search index for messages
-- Date: 2025-01-16
-- Description: Adds GIN index for full-text search on message_text column

BEGIN;

-- Create GIN index for full-text search on message_text
-- This enables fast text search using PostgreSQL's to_tsvector and ts_query
CREATE INDEX IF NOT EXISTS idx_messages_message_text_gin 
ON public.messages 
USING gin(to_tsvector('simple', message_text));

-- Also create a regular index on chat_id for faster filtering
-- (This might already exist, but we ensure it's there)
CREATE INDEX IF NOT EXISTS idx_messages_chat_id 
ON public.messages(chat_id);

-- Composite index for chat_id + created_at (for search results ordering)
CREATE INDEX IF NOT EXISTS idx_messages_chat_id_created_at 
ON public.messages(chat_id, created_at DESC);

COMMENT ON INDEX idx_messages_message_text_gin IS 'GIN index for full-text search on message_text column';
COMMENT ON INDEX idx_messages_chat_id IS 'Index on chat_id for faster message filtering';
COMMENT ON INDEX idx_messages_chat_id_created_at IS 'Composite index for chat messages ordered by created_at';

COMMIT;

