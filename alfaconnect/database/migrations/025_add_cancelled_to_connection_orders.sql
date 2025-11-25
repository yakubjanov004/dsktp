-- Migration: Add 'cancelled' status to connection_order_status and technician_order_status enums
-- Date: 2025-10-09
-- Description: Adds cancelled status to both connection and technician order enums for order cancellation functionality

BEGIN;

-- Add 'cancelled' to connection_order_status enum
ALTER TYPE public.connection_order_status ADD VALUE IF NOT EXISTS 'cancelled';

-- Add 'cancelled' to technician_order_status enum  
ALTER TYPE public.technician_order_status ADD VALUE IF NOT EXISTS 'cancelled';

COMMIT;
