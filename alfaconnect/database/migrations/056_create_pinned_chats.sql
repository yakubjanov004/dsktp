-- Migration: Add pinned chats support
-- Date: 2025-01-17
-- Description: Creates pinned_chats table for chat pinning functionality.

BEGIN;

-- Create pinned_chats table
CREATE TABLE IF NOT EXISTS public.pinned_chats (
    id bigserial PRIMARY KEY,
    user_id bigint NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    chat_id bigint NOT NULL REFERENCES public.chats(id) ON DELETE CASCADE,
    pinned_at timestamp with time zone NOT NULL DEFAULT now(),
    position integer NOT NULL DEFAULT 0,
    created_at timestamp with time zone NOT NULL DEFAULT now(),
    updated_at timestamp with time zone NOT NULL DEFAULT now(),
    CONSTRAINT pinned_chats_user_chat_unique UNIQUE (user_id, chat_id)
);

-- Add indexes for performance
CREATE INDEX IF NOT EXISTS idx_pinned_chats_user_id 
    ON public.pinned_chats(user_id);

CREATE INDEX IF NOT EXISTS idx_pinned_chats_chat_id 
    ON public.pinned_chats(chat_id);

CREATE INDEX IF NOT EXISTS idx_pinned_chats_user_position 
    ON public.pinned_chats(user_id, position);

COMMENT ON TABLE public.pinned_chats IS 'Stores pinned chats for each user';
COMMENT ON COLUMN public.pinned_chats.user_id IS 'User who pinned the chat';
COMMENT ON COLUMN public.pinned_chats.chat_id IS 'Chat that was pinned';
COMMENT ON COLUMN public.pinned_chats.pinned_at IS 'Timestamp when chat was pinned';
COMMENT ON COLUMN public.pinned_chats.position IS 'Sort order for pinned chats (lower = higher priority)';

COMMIT;

