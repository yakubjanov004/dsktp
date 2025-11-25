-- Migration: Create staff chat system tables
-- Date: 2025-01-15
-- Description: Creates tables for staff-to-staff chat system (staff_chats, staff_messages)
-- Rules:
--   - 1 active chat per (sender_id, receiver_id) pair (where is_group = false)
--   - Messages are immutable (no update/delete)
--   - Future-proof: is_group for group chats, read_by for seen functionality

BEGIN;

-- Create sequence for staff_chats (must be before table)
CREATE SEQUENCE IF NOT EXISTS public.staff_chats_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

-- Create staff_chats table
CREATE TABLE IF NOT EXISTS public.staff_chats (
    id bigint NOT NULL DEFAULT nextval('public.staff_chats_id_seq'::regclass),
    sender_id bigint NOT NULL,
    receiver_id bigint NOT NULL,
    status chat_status DEFAULT 'active' NOT NULL,
    is_group boolean DEFAULT false NOT NULL,
    last_activity_at timestamp with time zone DEFAULT now() NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT staff_chats_pkey PRIMARY KEY (id),
    CONSTRAINT staff_chats_sender_id_fkey FOREIGN KEY (sender_id) REFERENCES public.users(id) ON DELETE RESTRICT,
    CONSTRAINT staff_chats_receiver_id_fkey FOREIGN KEY (receiver_id) REFERENCES public.users(id) ON DELETE RESTRICT,
    -- Prevent self-chat
    CONSTRAINT staff_chats_no_self_chat CHECK (sender_id != receiver_id),
    -- Unique constraint: 1 active chat per (sender_id, receiver_id) pair (where is_group = false)
    CONSTRAINT staff_chats_unique_pair UNIQUE (sender_id, receiver_id, status) 
        DEFERRABLE INITIALLY DEFERRED
);

ALTER SEQUENCE public.staff_chats_id_seq OWNED BY public.staff_chats.id;

-- Create partial unique index for active chats (1 active chat per pair)
CREATE UNIQUE INDEX IF NOT EXISTS ux_staff_chats_active_pair
    ON public.staff_chats(sender_id, receiver_id)
    WHERE status = 'active' AND is_group = false;

-- Create sequence for staff_messages (must be before table)
CREATE SEQUENCE IF NOT EXISTS public.staff_messages_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

-- Create staff_messages table (immutable journal)
CREATE TABLE IF NOT EXISTS public.staff_messages (
    id bigint NOT NULL DEFAULT nextval('public.staff_messages_id_seq'::regclass),
    chat_id bigint NOT NULL,
    sender_id bigint NOT NULL,
    message_text text NOT NULL,
    attachments jsonb,
    read_by jsonb DEFAULT '{}'::jsonb,  -- Future: {"user_id": "timestamp"} for seen functionality
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT staff_messages_pkey PRIMARY KEY (id),
    -- RESTRICT prevents chat deletion if messages exist (immutable journal policy)
    CONSTRAINT staff_messages_chat_id_fkey FOREIGN KEY (chat_id) REFERENCES public.staff_chats(id) ON DELETE RESTRICT,
    CONSTRAINT staff_messages_sender_id_fkey FOREIGN KEY (sender_id) REFERENCES public.users(id) ON DELETE SET NULL
);

ALTER SEQUENCE public.staff_messages_id_seq OWNED BY public.staff_messages.id;

-- ============================================
-- INDEXES FOR PERFORMANCE
-- ============================================

-- Basic indexes for staff_chats
CREATE INDEX IF NOT EXISTS idx_staff_chats_sender_id ON public.staff_chats(sender_id);
CREATE INDEX IF NOT EXISTS idx_staff_chats_receiver_id ON public.staff_chats(receiver_id);
CREATE INDEX IF NOT EXISTS idx_staff_chats_status ON public.staff_chats(status);
CREATE INDEX IF NOT EXISTS idx_staff_chats_last_activity_at ON public.staff_chats(last_activity_at);

-- Composite index for finding user's chats (both as sender and receiver)
CREATE INDEX IF NOT EXISTS idx_staff_chats_user_active
    ON public.staff_chats(sender_id, receiver_id, last_activity_at DESC, id DESC)
    WHERE status = 'active';

-- Index for finding chats where user is receiver
CREATE INDEX IF NOT EXISTS idx_staff_chats_receiver_active
    ON public.staff_chats(receiver_id, last_activity_at DESC, id DESC)
    WHERE status = 'active';

-- Indexes for staff_messages
CREATE INDEX IF NOT EXISTS idx_staff_messages_chat_id_created_at ON public.staff_messages(chat_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_staff_messages_sender_id ON public.staff_messages(sender_id);

-- ============================================
-- FUNCTIONS AND TRIGGERS
-- ============================================

-- Function: Auto-update updated_at on any staff_chat update
CREATE OR REPLACE FUNCTION public.update_staff_chats_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at := now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger: Auto-update updated_at on any staff_chat update
CREATE TRIGGER t01_update_staff_chats_updated_at
    BEFORE UPDATE ON public.staff_chats
    FOR EACH ROW
    EXECUTE FUNCTION public.update_staff_chats_updated_at();

-- Function: Update staff_chat last_activity_at when message is added
CREATE OR REPLACE FUNCTION public.update_staff_chat_activity_on_message()
RETURNS TRIGGER AS $$
BEGIN
    UPDATE public.staff_chats
    SET last_activity_at = now(),
        updated_at = now(),
        status = 'active'  -- Reactivate if inactive
    WHERE id = NEW.chat_id;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger: After insert on staff_messages to update chat activity
CREATE TRIGGER t02_update_staff_chat_activity_on_message
    AFTER INSERT ON public.staff_messages
    FOR EACH ROW
    EXECUTE FUNCTION public.update_staff_chat_activity_on_message();

-- Function: Prevent update/delete on staff_messages (immutable journal)
CREATE OR REPLACE FUNCTION public.prevent_staff_message_modification()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'UPDATE' THEN
        RAISE EXCEPTION 'Staff messages are immutable. Updates are not allowed.';
    ELSIF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'Staff messages are immutable. Deletes are not allowed.';
    END IF;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

-- Trigger: Prevent update/delete on staff_messages (immutable journal)
CREATE TRIGGER t03_prevent_staff_message_modification
    BEFORE UPDATE OR DELETE ON public.staff_messages
    FOR EACH ROW
    EXECUTE FUNCTION public.prevent_staff_message_modification();

-- Function: Prevent staff_chat deletion (immutable journal policy: chats should not be deleted)
CREATE OR REPLACE FUNCTION public.prevent_staff_chat_deletion()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'Staff chats cannot be deleted. Use status = inactive instead.';
END;
$$ LANGUAGE plpgsql;

-- Trigger: Prevent staff_chat deletion (chats should be marked inactive, not deleted)
CREATE TRIGGER t04_prevent_staff_chat_deletion
    BEFORE DELETE ON public.staff_chats
    FOR EACH ROW
    EXECUTE FUNCTION public.prevent_staff_chat_deletion();

-- ============================================
-- COMMENTS
-- ============================================

COMMENT ON TABLE public.staff_chats IS 'Chat sessions between staff members (operators and supervisors). Rule: 1 active chat per (sender_id, receiver_id) pair (where is_group = false).';
COMMENT ON TABLE public.staff_messages IS 'Messages in staff chat sessions. Immutable journal: no updates or deletes allowed.';

COMMENT ON COLUMN public.staff_chats.sender_id IS 'Staff member who started the chat (users.id).';
COMMENT ON COLUMN public.staff_chats.receiver_id IS 'Staff member who receives the chat (users.id).';
COMMENT ON COLUMN public.staff_chats.status IS 'Chat status: active or inactive. Default: active.';
COMMENT ON COLUMN public.staff_chats.is_group IS 'Whether this is a group chat (future feature). Default: false.';
COMMENT ON COLUMN public.staff_chats.last_activity_at IS 'Last activity timestamp (message or interaction). Updated when messages are added.';

COMMENT ON COLUMN public.staff_messages.sender_id IS 'Staff member who sent the message (users.id).';
COMMENT ON COLUMN public.staff_messages.message_text IS 'Message text content. Required.';
COMMENT ON COLUMN public.staff_messages.attachments IS 'File attachments or additional data in JSONB format.';
COMMENT ON COLUMN public.staff_messages.read_by IS 'JSONB object tracking who read the message: {"user_id": "timestamp"}. Future: seen functionality.';

COMMENT ON FUNCTION public.update_staff_chats_updated_at() IS 'Automatically updates updated_at column on any staff_chat update.';
COMMENT ON FUNCTION public.update_staff_chat_activity_on_message() IS 'Updates staff_chat last_activity_at. Reactivates chat if inactive.';
COMMENT ON FUNCTION public.prevent_staff_message_modification() IS 'Prevents updates and deletes on staff_messages table (immutable journal).';
COMMENT ON FUNCTION public.prevent_staff_chat_deletion() IS 'Prevents staff_chat deletion. Chats should be marked inactive instead of being deleted (immutable journal policy).';

COMMIT;

