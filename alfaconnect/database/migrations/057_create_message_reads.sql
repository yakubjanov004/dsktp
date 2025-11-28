-- Migration: Add message read receipts support
-- Date: 2025-01-17
-- Description: Creates message_reads table for detailed read receipt tracking.

BEGIN;

-- Create message_reads table
CREATE TABLE IF NOT EXISTS public.message_reads (
    id bigserial PRIMARY KEY,
    message_id bigint NOT NULL REFERENCES public.messages(id) ON DELETE CASCADE,
    user_id bigint NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    read_at timestamp with time zone NOT NULL DEFAULT now(),
    created_at timestamp with time zone NOT NULL DEFAULT now(),
    CONSTRAINT message_reads_message_user_unique UNIQUE (message_id, user_id)
);

-- Add indexes for performance
CREATE INDEX IF NOT EXISTS idx_message_reads_message_id 
    ON public.message_reads(message_id);

CREATE INDEX IF NOT EXISTS idx_message_reads_user_id 
    ON public.message_reads(user_id);

CREATE INDEX IF NOT EXISTS idx_message_reads_read_at 
    ON public.message_reads(read_at);

COMMENT ON TABLE public.message_reads IS 'Stores read receipts for messages';
COMMENT ON COLUMN public.message_reads.message_id IS 'Message that was read';
COMMENT ON COLUMN public.message_reads.user_id IS 'User who read the message';
COMMENT ON COLUMN public.message_reads.read_at IS 'Timestamp when message was read';

COMMIT;

