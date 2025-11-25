-- Migration: Add missing media column to staff_orders table
-- Date: 2025-10-21
-- Description: Adds the missing media column to the existing staff_orders table

BEGIN;

-- Add missing media column if it doesn't exist
ALTER TABLE public.staff_orders 
ADD COLUMN IF NOT EXISTS media TEXT;

-- Add foreign key constraints (will be skipped if they already exist)
-- Note: These constraints may already exist, so errors are expected and can be ignored

-- Add indexes for better performance
CREATE INDEX IF NOT EXISTS idx_staff_orders_user_id ON public.staff_orders(user_id);
CREATE INDEX IF NOT EXISTS idx_staff_orders_status ON public.staff_orders(status);
CREATE INDEX IF NOT EXISTS idx_staff_orders_application_number ON public.staff_orders(application_number);
CREATE INDEX IF NOT EXISTS idx_staff_orders_created_at ON public.staff_orders(created_at);
CREATE INDEX IF NOT EXISTS idx_staff_orders_is_active ON public.staff_orders(is_active);

-- Add comment for the new media column
COMMENT ON COLUMN public.staff_orders.media IS 'Media files (photos, videos, documents)';

COMMIT;
