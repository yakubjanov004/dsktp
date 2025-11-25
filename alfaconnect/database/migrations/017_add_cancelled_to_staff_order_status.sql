-- Migration: Add 'cancelled' to staff_order_status enum
-- Date: 2025-10-06
-- Description: Adds the missing 'cancelled' status to staff_order_status enum

-- Add 'cancelled' to the existing staff_order_status enum
ALTER TYPE public.staff_order_status ADD VALUE IF NOT EXISTS 'cancelled';

-- Verify the enum values
DO $$
DECLARE
    enum_values text[];
BEGIN
    SELECT array_agg(enumlabel ORDER BY enumsortorder) 
    INTO enum_values
    FROM pg_enum e
    JOIN pg_type t ON e.enumtypid = t.oid
    WHERE t.typname = 'staff_order_status';
    
    RAISE NOTICE 'Current staff_order_status values: %', array_to_string(enum_values, ', ');
END $$;
