-- Migration: Add message forwarding support
-- Date: 2025-01-16
-- Description: Adds columns to messages table for forwarding functionality

BEGIN;

-- Add forwarding columns to messages table
ALTER TABLE public.messages
ADD COLUMN IF NOT EXISTS forwarded_from_message_id bigint,
ADD COLUMN IF NOT EXISTS forwarded_from_chat_id bigint,
ADD COLUMN IF NOT EXISTS forwarded_from_user_id bigint;

-- Add foreign key constraint for forwarded message (if not exists)
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint 
        WHERE conname = 'messages_forwarded_from_message_id_fkey'
    ) THEN
        ALTER TABLE public.messages
        ADD CONSTRAINT messages_forwarded_from_message_id_fkey 
        FOREIGN KEY (forwarded_from_message_id) 
        REFERENCES public.messages(id) 
        ON DELETE SET NULL;
    END IF;
END $$;

-- Add foreign key constraint for forwarded from user (if not exists)
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint 
        WHERE conname = 'messages_forwarded_from_user_id_fkey'
    ) THEN
        ALTER TABLE public.messages
        ADD CONSTRAINT messages_forwarded_from_user_id_fkey 
        FOREIGN KEY (forwarded_from_user_id) 
        REFERENCES public.users(id) 
        ON DELETE SET NULL;
    END IF;
END $$;

-- Add index for faster lookups
CREATE INDEX IF NOT EXISTS idx_messages_forwarded_from_message_id 
ON public.messages(forwarded_from_message_id) 
WHERE forwarded_from_message_id IS NOT NULL;

COMMENT ON COLUMN public.messages.forwarded_from_message_id IS 'Original message ID if this message was forwarded. NULL for regular messages.';
COMMENT ON COLUMN public.messages.forwarded_from_chat_id IS 'Original chat ID where the message was forwarded from. NULL for regular messages.';
COMMENT ON COLUMN public.messages.forwarded_from_user_id IS 'Original sender user ID of the forwarded message. NULL for regular messages.';

COMMIT;

