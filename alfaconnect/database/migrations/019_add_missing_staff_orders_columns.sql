-- Migration: Add missing columns to staff_orders table
-- This migration adds the missing fields that are defined in the Python StaffOrders model
-- but are missing from the database schema

-- Add jm_notes column (Junior Manager notes)
ALTER TABLE public.staff_orders 
ADD COLUMN IF NOT EXISTS jm_notes TEXT;

-- Add problem_description column (Problem description for technician orders)
ALTER TABLE public.staff_orders 
ADD COLUMN IF NOT EXISTS problem_description TEXT;

-- Add diagnostics column (Diagnostics results)
ALTER TABLE public.staff_orders 
ADD COLUMN IF NOT EXISTS diagnostics TEXT;

-- Add comments to the new columns
COMMENT ON COLUMN public.staff_orders.jm_notes IS 'Junior Manager notes and comments';
COMMENT ON COLUMN public.staff_orders.problem_description IS 'Detailed problem description for technician service orders';
COMMENT ON COLUMN public.staff_orders.diagnostics IS 'Diagnostics results and findings';

-- Verify the changes
SELECT column_name, data_type, is_nullable 
FROM information_schema.columns 
WHERE table_name = 'staff_orders' 
AND table_schema = 'public'
ORDER BY ordinal_position;
