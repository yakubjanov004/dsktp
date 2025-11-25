-- Migration: Add missing values to staff_order_status enum
-- Date: 2025-10-06
-- Description: Adds missing enum values for staff_order_status

-- Add missing enum values
ALTER TYPE public.staff_order_status ADD VALUE IF NOT EXISTS 'in_progress';
ALTER TYPE public.staff_order_status ADD VALUE IF NOT EXISTS 'assigned_to_technician';
ALTER TYPE public.staff_order_status ADD VALUE IF NOT EXISTS 'in_junior_manager';

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
