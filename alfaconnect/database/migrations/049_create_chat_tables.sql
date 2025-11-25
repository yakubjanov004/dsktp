-- Migration: Create chat system tables
-- Date: 2025-01-15
-- Description: Creates tables for chat system (chats, messages, chat_assignment_log)
-- Rules:
--   - 1 client = 1 active chat (partial unique constraint)
--   - Inactive chat must have operator_id = NULL
--   - Messages are immutable (no update/delete)
--   - Operator assignment history is logged

BEGIN;

-- Drop existing types if they exist (for clean migration)
-- WARNING: CASCADE will drop all dependent columns, constraints, and triggers.
-- For production upgrades of existing systems, use ALTER TYPE ... ADD VALUE instead.
DROP TYPE IF EXISTS public.chat_status CASCADE;
-- Note: message_type is not used in this schema, so dropping it is safe
-- DROP TYPE IF EXISTS public.message_type CASCADE;  -- Not needed, commented out
DROP TYPE IF EXISTS public.sender_type CASCADE;

-- Create chat status enum (only active and inactive)
CREATE TYPE chat_status AS ENUM ('active', 'inactive');

-- Create sender type enum for tracking who sent the message
CREATE TYPE sender_type AS ENUM ('client', 'operator', 'system');

-- Create sequence for chats (must be before table)
CREATE SEQUENCE IF NOT EXISTS public.chats_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

-- Create chats table
CREATE TABLE IF NOT EXISTS public.chats (
    id bigint NOT NULL DEFAULT nextval('public.chats_id_seq'::regclass),
    client_id bigint NOT NULL,
    operator_id bigint,
    status chat_status DEFAULT 'active' NOT NULL,
    last_activity_at timestamp with time zone DEFAULT now() NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT chats_pkey PRIMARY KEY (id),
    CONSTRAINT chats_client_id_fkey FOREIGN KEY (client_id) REFERENCES public.users(id) ON DELETE RESTRICT,
    CONSTRAINT chats_operator_id_fkey FOREIGN KEY (operator_id) REFERENCES public.users(id) ON DELETE SET NULL,
    -- Critical rule: inactive chat must have operator_id = NULL
    CONSTRAINT chats_inactive_operator_null CHECK (
        (status = 'inactive' AND operator_id IS NULL) OR
        (status = 'active')
    )
);

ALTER SEQUENCE public.chats_id_seq OWNED BY public.chats.id;

-- Create sequence for messages (must be before table)
CREATE SEQUENCE IF NOT EXISTS public.messages_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

-- Create messages table (immutable journal)
CREATE TABLE IF NOT EXISTS public.messages (
    id bigint NOT NULL DEFAULT nextval('public.messages_id_seq'::regclass),
    chat_id bigint NOT NULL,
    sender_type sender_type NOT NULL,
    sender_id bigint,  -- NULL for system messages, user ID for client/operator
    operator_id bigint,  -- Operator ID when sender_type = 'operator', NULL otherwise
    message_text text NOT NULL,
    attachments jsonb,  -- File attachments or additional data
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT messages_pkey PRIMARY KEY (id),
    -- RESTRICT prevents chat deletion if messages exist (immutable journal policy)
    CONSTRAINT messages_chat_id_fkey FOREIGN KEY (chat_id) REFERENCES public.chats(id) ON DELETE RESTRICT,
    CONSTRAINT messages_sender_id_fkey FOREIGN KEY (sender_id) REFERENCES public.users(id) ON DELETE SET NULL,
    CONSTRAINT messages_operator_id_fkey FOREIGN KEY (operator_id) REFERENCES public.users(id) ON DELETE SET NULL,
    -- Critical rule: operator_id must be set when sender_type = 'operator', and NULL otherwise
    CONSTRAINT messages_operator_consistency CHECK (
        (sender_type = 'operator' AND operator_id IS NOT NULL AND sender_id = operator_id) OR
        (sender_type != 'operator' AND operator_id IS NULL)
    ),
    -- Critical rule: sender_id must be NOT NULL for client/operator, NULL for system
    CONSTRAINT messages_sender_id_consistency CHECK (
        (sender_type IN ('client', 'operator') AND sender_id IS NOT NULL) OR
        (sender_type = 'system' AND sender_id IS NULL)
    )
);

ALTER SEQUENCE public.messages_id_seq OWNED BY public.messages.id;

-- Create sequence for chat_assignment_log (must be before table)
CREATE SEQUENCE IF NOT EXISTS public.chat_assignment_log_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

-- Create chat_assignment_log table (assignment history)
CREATE TABLE IF NOT EXISTS public.chat_assignment_log (
    id bigint NOT NULL DEFAULT nextval('public.chat_assignment_log_id_seq'::regclass),
    chat_id bigint NOT NULL,
    operator_id bigint NOT NULL,
    assigned_by bigint,  -- Who assigned (CCS or system user)
    assigned_at timestamp with time zone DEFAULT now() NOT NULL,
    unassigned_at timestamp with time zone,  -- When operator was unassigned (reassigned or chat inactive)
    CONSTRAINT chat_assignment_log_pkey PRIMARY KEY (id),
    CONSTRAINT chat_assignment_log_chat_id_fkey FOREIGN KEY (chat_id) REFERENCES public.chats(id) ON DELETE CASCADE,
    CONSTRAINT chat_assignment_log_operator_id_fkey FOREIGN KEY (operator_id) REFERENCES public.users(id) ON DELETE SET NULL,
    CONSTRAINT chat_assignment_log_assigned_by_fkey FOREIGN KEY (assigned_by) REFERENCES public.users(id) ON DELETE SET NULL
);

-- Partial unique constraint: one open assignment per chat (race-safe)
CREATE UNIQUE INDEX IF NOT EXISTS ux_chat_assignment_log_chat_open
    ON public.chat_assignment_log(chat_id)
    WHERE unassigned_at IS NULL;

ALTER SEQUENCE public.chat_assignment_log_id_seq OWNED BY public.chat_assignment_log.id;

-- ============================================
-- INDEXES FOR PERFORMANCE
-- ============================================

-- Basic indexes for chats
CREATE INDEX IF NOT EXISTS idx_chats_client_id ON public.chats(client_id);
CREATE INDEX IF NOT EXISTS idx_chats_operator_id ON public.chats(operator_id);
CREATE INDEX IF NOT EXISTS idx_chats_status ON public.chats(status);
CREATE INDEX IF NOT EXISTS idx_chats_last_activity_at ON public.chats(last_activity_at);

-- Unique partial index: 1 client = 1 active chat
CREATE UNIQUE INDEX IF NOT EXISTS ux_chats_client_active
    ON public.chats(client_id)
    WHERE status = 'active';

-- Index for operator active chats (for CCO dashboard)
CREATE INDEX IF NOT EXISTS ix_chats_operator_active
    ON public.chats(operator_id, last_activity_at DESC, id DESC)
    WHERE status = 'active';

-- Index for CCS inbox (unassigned active chats)
CREATE INDEX IF NOT EXISTS ix_chats_unassigned_active
    ON public.chats(last_activity_at DESC, id DESC)
    WHERE status = 'active' AND operator_id IS NULL;

-- Indexes for messages
CREATE INDEX IF NOT EXISTS idx_messages_chat_id_created_at ON public.messages(chat_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_messages_sender_id ON public.messages(sender_id);
CREATE INDEX IF NOT EXISTS idx_messages_operator_id ON public.messages(operator_id);

-- Indexes for chat_assignment_log
CREATE INDEX IF NOT EXISTS idx_chat_assignment_log_chat_id_assigned_at ON public.chat_assignment_log(chat_id, assigned_at DESC);
CREATE INDEX IF NOT EXISTS idx_chat_assignment_log_operator_id ON public.chat_assignment_log(operator_id);
-- Composite index for finding active assignments (reassign/close queries)
CREATE INDEX IF NOT EXISTS idx_chat_assignment_log_chat_id_unassigned_at ON public.chat_assignment_log(chat_id, unassigned_at) WHERE unassigned_at IS NULL;

-- ============================================
-- FUNCTIONS AND TRIGGERS
-- ============================================

-- Function: Ensure operator_id is NULL when chat becomes inactive
CREATE OR REPLACE FUNCTION public.enforce_inactive_operator_null()
RETURNS TRIGGER AS $$
BEGIN
    -- If status changed to inactive, set operator_id to NULL
    -- Note: Log closing is handled by log_operator_assignment() AFTER trigger to avoid duplicate updates
    IF NEW.status = 'inactive' AND NEW.operator_id IS NOT NULL THEN
        NEW.operator_id := NULL;
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Function: Auto-update updated_at on any chat update
CREATE OR REPLACE FUNCTION public.update_chats_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at := now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Triggers on chats table (executed in creation order)
-- t01: Enforce inactive operator null rule (must run first to set operator_id = NULL)
CREATE TRIGGER t01_enforce_inactive_operator_null
    BEFORE UPDATE OF status, operator_id ON public.chats
    FOR EACH ROW
    EXECUTE FUNCTION public.enforce_inactive_operator_null();

-- t02: Auto-update updated_at on any chat update
CREATE TRIGGER t02_update_chats_updated_at
    BEFORE UPDATE ON public.chats
    FOR EACH ROW
    EXECUTE FUNCTION public.update_chats_updated_at();

-- Function: Update chat last_activity_at and reactivate if needed when message is added
CREATE OR REPLACE FUNCTION public.update_chat_activity_on_message()
RETURNS TRIGGER AS $$
BEGIN
    -- Only client and operator messages reactivate chat; system messages do not
    IF NEW.sender_type IN ('client', 'operator') THEN
        UPDATE public.chats
        SET last_activity_at = now(),
            updated_at = now(),
            status = 'active'  -- Reactivate if inactive
        WHERE id = NEW.chat_id;
    ELSE
        -- System messages only update last_activity_at, but don't reactivate
        UPDATE public.chats
        SET last_activity_at = now(),
            updated_at = now()
        WHERE id = NEW.chat_id;
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger: After insert on messages to update chat activity
CREATE TRIGGER t03_update_chat_activity_on_message
    AFTER INSERT ON public.messages
    FOR EACH ROW
    EXECUTE FUNCTION public.update_chat_activity_on_message();

-- Function: Log operator assignment
CREATE OR REPLACE FUNCTION public.log_operator_assignment()
RETURNS TRIGGER AS $$
BEGIN
    -- If operator_id changed from NULL to a value (new assignment)
    IF OLD.operator_id IS NULL AND NEW.operator_id IS NOT NULL THEN
        INSERT INTO public.chat_assignment_log (chat_id, operator_id, assigned_by, assigned_at)
        VALUES (NEW.id, NEW.operator_id, NULL, now());  -- assigned_by can be set by application
    END IF;
    
    -- If operator_id changed from one value to another (reassignment)
    IF OLD.operator_id IS NOT NULL 
       AND NEW.operator_id IS NOT NULL 
       AND OLD.operator_id IS DISTINCT FROM NEW.operator_id THEN
        -- Close old assignment
        UPDATE public.chat_assignment_log
        SET unassigned_at = now()
        WHERE chat_id = NEW.id
          AND operator_id = OLD.operator_id
          AND unassigned_at IS NULL;
        
        -- Create new assignment
        INSERT INTO public.chat_assignment_log (chat_id, operator_id, assigned_by, assigned_at)
        VALUES (NEW.id, NEW.operator_id, NULL, now());
    END IF;
    
    -- If operator_id changed from a value to NULL (unassignment, but status should be inactive)
    IF OLD.operator_id IS NOT NULL AND NEW.operator_id IS NULL THEN
        UPDATE public.chat_assignment_log
        SET unassigned_at = now()
        WHERE chat_id = NEW.id
          AND operator_id = OLD.operator_id
          AND unassigned_at IS NULL;
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger: After update on chats to log operator assignment changes
CREATE TRIGGER t04_log_operator_assignment
    AFTER UPDATE OF operator_id ON public.chats
    FOR EACH ROW
    WHEN (OLD.operator_id IS DISTINCT FROM NEW.operator_id)
    EXECUTE FUNCTION public.log_operator_assignment();

-- Function: Prevent update/delete on messages (immutable journal)
CREATE OR REPLACE FUNCTION public.prevent_message_modification()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'UPDATE' THEN
        RAISE EXCEPTION 'Messages are immutable. Updates are not allowed.';
    ELSIF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'Messages are immutable. Deletes are not allowed.';
    END IF;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

-- Trigger: Prevent update/delete on messages (immutable journal)
CREATE TRIGGER t05_prevent_message_modification
    BEFORE UPDATE OR DELETE ON public.messages
    FOR EACH ROW
    EXECUTE FUNCTION public.prevent_message_modification();

-- Function: Prevent chat deletion (immutable journal policy: chats should not be deleted)
CREATE OR REPLACE FUNCTION public.prevent_chat_deletion()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'Chats cannot be deleted. Use status = inactive instead.';
END;
$$ LANGUAGE plpgsql;

-- Trigger: Prevent chat deletion (chats should be marked inactive, not deleted)
CREATE TRIGGER t06_prevent_chat_deletion
    BEFORE DELETE ON public.chats
    FOR EACH ROW
    EXECUTE FUNCTION public.prevent_chat_deletion();

-- Function: Automatically mark inactive chats (called periodically, e.g., by cron)
CREATE OR REPLACE FUNCTION public.mark_inactive_chats_auto()
RETURNS integer AS $$
DECLARE
    affected_count integer;
BEGIN
    -- Mark chats as inactive if inactive for 1 hour or more
    -- This will trigger enforce_inactive_operator_null to set operator_id = NULL
    UPDATE public.chats
    SET status = 'inactive',
        updated_at = now()
    WHERE status = 'active'
      AND last_activity_at < now() - interval '1 hour';
    
    GET DIAGNOSTICS affected_count = ROW_COUNT;
    RETURN affected_count;
END;
$$ LANGUAGE plpgsql;

-- ============================================
-- COMMENTS
-- ============================================

COMMENT ON TABLE public.chats IS 'Chat sessions between clients and operators. Rule: 1 client = 1 active chat. Inactive chats must have operator_id = NULL.';
COMMENT ON TABLE public.messages IS 'Messages in chat sessions. Immutable journal: no updates or deletes allowed.';
COMMENT ON TABLE public.chat_assignment_log IS 'History of operator assignments to chats. Tracks when operators were assigned and unassigned. Rule: one open assignment per chat (partial unique constraint).';

COMMENT ON COLUMN public.chats.client_id IS 'Client user ID (users.id). One active chat per client.';
COMMENT ON COLUMN public.chats.operator_id IS 'Assigned operator user ID (users.id). Must be NULL when status = inactive.';
COMMENT ON COLUMN public.chats.status IS 'Chat status: active or inactive. Default: active.';
COMMENT ON COLUMN public.chats.last_activity_at IS 'Last activity timestamp (message or interaction). Updated when messages are added.';

COMMENT ON COLUMN public.messages.sender_type IS 'Type of sender: client, operator, or system.';
COMMENT ON COLUMN public.messages.sender_id IS 'Sender user ID (users.id). NOT NULL for client/operator messages, NULL for system messages.';
COMMENT ON COLUMN public.messages.operator_id IS 'Operator ID when sender_type = operator. Must match sender_id. NULL for client and system messages.';
COMMENT ON COLUMN public.messages.message_text IS 'Message text content. Required.';
COMMENT ON COLUMN public.messages.attachments IS 'File attachments or additional data in JSONB format.';

COMMENT ON COLUMN public.chat_assignment_log.operator_id IS 'Assigned operator user ID.';
COMMENT ON COLUMN public.chat_assignment_log.assigned_by IS 'User ID who assigned the operator (CCS or system). Can be NULL.';
COMMENT ON COLUMN public.chat_assignment_log.assigned_at IS 'When operator was assigned.';
COMMENT ON COLUMN public.chat_assignment_log.unassigned_at IS 'When operator was unassigned (reassigned or chat became inactive). NULL if still assigned.';

COMMENT ON FUNCTION public.enforce_inactive_operator_null() IS 'Ensures operator_id is NULL when chat status becomes inactive. Log closing is handled by log_operator_assignment().';
COMMENT ON FUNCTION public.update_chats_updated_at() IS 'Automatically updates updated_at column on any chat update.';
COMMENT ON FUNCTION public.update_chat_activity_on_message() IS 'Updates chat last_activity_at. Reactivates chat only for client/operator messages (not system messages).';
COMMENT ON FUNCTION public.log_operator_assignment() IS 'Logs operator assignment changes to chat_assignment_log table. Handles all assignment/unassignment scenarios.';
COMMENT ON FUNCTION public.prevent_message_modification() IS 'Prevents updates and deletes on messages table (immutable journal).';
COMMENT ON FUNCTION public.prevent_chat_deletion() IS 'Prevents chat deletion. Chats should be marked inactive instead of being deleted (immutable journal policy).';
COMMENT ON FUNCTION public.mark_inactive_chats_auto() IS 'Automatically marks chats as inactive if they have been inactive for 1 hour or more. Should be called periodically (e.g., by cron job).';

-- ============================================
-- PERMISSIONS (Production Security)
-- ============================================

-- Note: These GRANT/REVOKE statements should be executed by a database administrator
-- with appropriate privileges. Adjust role names according to your setup.
-- 
-- Example roles:
--   - app_role: Application database role (read/write for normal operations)
--   - migration_role: Role for running migrations (full privileges)
--   - readonly_role: Read-only role for reporting/analytics

-- Revoke UPDATE and DELETE on messages table (immutable journal policy)
-- App role should only have INSERT and SELECT
-- REVOKE UPDATE, DELETE ON public.messages FROM app_role;
-- GRANT INSERT, SELECT ON public.messages TO app_role;

-- Revoke DELETE on chats table (chats should be marked inactive, not deleted)
-- App role should have SELECT, INSERT, UPDATE but not DELETE
-- REVOKE DELETE ON public.chats FROM app_role;
-- GRANT SELECT, INSERT, UPDATE ON public.chats TO app_role;

-- Grant appropriate permissions on chat_assignment_log (read/write for app)
-- GRANT SELECT, INSERT, UPDATE ON public.chat_assignment_log TO app_role;

-- Grant SELECT on sequences (for INSERT operations)
-- GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO app_role;

-- Note: For production, also consider:
--   1. Row-level security (RLS) policies if multi-tenant
--   2. Separate roles for different application components
--   3. Audit logging for sensitive operations
--   4. Regular review of permissions

-- ============================================
-- API LAYER NOTES (for developers)
-- ============================================

-- Race-safe operator assignment pattern (use in API code):
--   UPDATE chats 
--   SET operator_id = :operator_id 
--   WHERE id = :chat_id 
--     AND operator_id IS NULL 
--     AND status = 'active';
--   
--   If affected_rows = 0, return 409 Conflict (chat already assigned)
--   This works together with ux_chat_assignment_log_chat_open constraint

COMMIT;
