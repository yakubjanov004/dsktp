-- 004_connection_rework.sql
BEGIN;

-- 1) Yangi ustunlar (agar hali qo'shilmagan bo'lsa): sender_status, recipient_status
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name='connections' AND column_name='sender_status'
    ) THEN
        ALTER TABLE connections ADD COLUMN sender_status TEXT;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name='connections' AND column_name='recipient_status'
    ) THEN
        ALTER TABLE connections ADD COLUMN recipient_status TEXT;
    END IF;
END $$;

-- 2) Indekslar (ixtiyoriy, lekin tavsiya etiladi)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_indexes
        WHERE schemaname='public' AND indexname='idx_connections_sender_id'
    ) THEN
        CREATE INDEX idx_connections_sender_id ON connections (sender_id);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_indexes
        WHERE schemaname='public' AND indexname='idx_connections_recipient_id'
    ) THEN
        CREATE INDEX idx_connections_recipient_id ON connections (recipient_id);
    END IF;
END $$;

-- 3) user_id ustunini KO'CHIRMASDAN olib tashlash
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name='connections' AND column_name='user_id'
    ) THEN
        ALTER TABLE connections DROP COLUMN user_id;
    END IF;
END $$;

COMMIT;
