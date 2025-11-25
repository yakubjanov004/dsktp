-- ==========================================================
-- Migration: Fix connections.staff_id foreign key
-- Author: ChatGPT
-- Date: 2025-09-17
-- Purpose: Point staff_id to staff_orders.id instead of users.id
-- ==========================================================

BEGIN;

-- 1️⃣ Eski constraintni olib tashlaymiz
DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM information_schema.table_constraints
        WHERE constraint_name = 'connections_staff_id_fkey'
          AND table_name = 'connections'
    ) THEN
        ALTER TABLE connections
        DROP CONSTRAINT connections_staff_id_fkey;
    END IF;
END$$;

-- 2️⃣ Yangi constraint qo‘shamiz (staff_orders.id ga bog‘lash)
ALTER TABLE connections
ADD CONSTRAINT connections_staff_id_fkey
    FOREIGN KEY (staff_id)
    REFERENCES staff_orders(id)
    ON DELETE CASCADE;

COMMIT;
