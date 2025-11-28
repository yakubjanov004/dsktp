-- Migration: Create message_reactions table
-- Date: 2025-01-15
-- Description: Creates table for message reactions (emoji reactions on messages)
-- Rules:
--   - One user can have one reaction per message (unique constraint)
--   - Reactions are stored with emoji string
--   - Cascade delete when message is deleted

BEGIN;

-- Create sequence for message_reactions (must be before table)
CREATE SEQUENCE IF NOT EXISTS public.message_reactions_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

-- Create message_reactions table
CREATE TABLE IF NOT EXISTS public.message_reactions (
    id bigint NOT NULL DEFAULT nextval('public.message_reactions_id_seq'::regclass),
    message_id bigint NOT NULL,
    user_id bigint NOT NULL,
    emoji varchar(10) NOT NULL,  -- Emoji string (e.g., "👍", "❤️", "😂")
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT message_reactions_pkey PRIMARY KEY (id),
    CONSTRAINT message_reactions_message_id_fkey FOREIGN KEY (message_id) REFERENCES public.messages(id) ON DELETE CASCADE,
    CONSTRAINT message_reactions_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE,
    -- One user can have one reaction per message (can change emoji, but only one at a time)
    CONSTRAINT message_reactions_unique_user_message UNIQUE (message_id, user_id)
);

ALTER SEQUENCE public.message_reactions_id_seq OWNED BY public.message_reactions.id;

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_message_reactions_message_id ON public.message_reactions(message_id);
CREATE INDEX IF NOT EXISTS idx_message_reactions_user_id ON public.message_reactions(user_id);
CREATE INDEX IF NOT EXISTS idx_message_reactions_emoji ON public.message_reactions(emoji);

-- Comments
COMMENT ON TABLE public.message_reactions IS 'Emoji reactions on messages. One reaction per user per message.';
COMMENT ON COLUMN public.message_reactions.message_id IS 'Message ID (foreign key to messages.id)';
COMMENT ON COLUMN public.message_reactions.user_id IS 'User ID who added the reaction (foreign key to users.id)';
COMMENT ON COLUMN public.message_reactions.emoji IS 'Emoji string (e.g., "👍", "❤️", "😂")';
COMMENT ON COLUMN public.message_reactions.created_at IS 'When the reaction was added';

COMMIT;

