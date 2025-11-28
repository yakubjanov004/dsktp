-- Migration: Add message editing support
-- Date: 2025-01-17
-- Description: Adds edited_at column to messages table for message editing functionality.

BEGIN;

-- Add edited_at column
ALTER TABLE public.messages
ADD COLUMN IF NOT EXISTS edited_at timestamp with time zone;

-- Add index for performance
CREATE INDEX IF NOT EXISTS idx_messages_edited_at
    ON public.messages(edited_at)
    WHERE edited_at IS NOT NULL;

COMMENT ON COLUMN public.messages.edited_at IS 'Timestamp when message was last edited. NULL if never edited.';

COMMIT;

