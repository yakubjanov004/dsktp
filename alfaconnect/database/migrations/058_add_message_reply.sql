-- Migration: Add message reply support
-- Date: 2025-01-18
-- Description: Adds reply_to_message_id column to messages table for message threading.

BEGIN;

-- Add reply_to_message_id column to messages table
ALTER TABLE public.messages
ADD COLUMN IF NOT EXISTS reply_to_message_id bigint REFERENCES public.messages(id) ON DELETE SET NULL;

-- Add index for performance
CREATE INDEX IF NOT EXISTS idx_messages_reply_to_message_id
    ON public.messages(reply_to_message_id);

COMMENT ON COLUMN public.messages.reply_to_message_id IS 'ID of the message this message is replying to';

COMMIT;

