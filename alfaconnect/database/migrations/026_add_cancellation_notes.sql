-- Migration: Add cancellation_note column to order tables
-- Date: 2025-10-09
-- Description: Adds cancellation_note TEXT column to connection_orders, technician_orders, and staff_orders for storing cancellation reasons

BEGIN;

-- Add cancellation_note to connection_orders
ALTER TABLE public.connection_orders 
ADD COLUMN IF NOT EXISTS cancellation_note TEXT;

-- Add cancellation_note to technician_orders
ALTER TABLE public.technician_orders 
ADD COLUMN IF NOT EXISTS cancellation_note TEXT;

-- Add cancellation_note to staff_orders
ALTER TABLE public.staff_orders 
ADD COLUMN IF NOT EXISTS cancellation_note TEXT;

-- Add comments to the new columns
COMMENT ON COLUMN public.connection_orders.cancellation_note IS 'Reason for order cancellation';
COMMENT ON COLUMN public.technician_orders.cancellation_note IS 'Reason for order cancellation';
COMMENT ON COLUMN public.staff_orders.cancellation_note IS 'Reason for order cancellation';

COMMIT;

