-- Migration: Create staff_order_status enum type
-- Date: 2025-09-30
-- Description: Creates the missing staff_order_status enum type that is referenced in staff_orders table

DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_type t JOIN pg_namespace n ON n.oid=t.typnamespace
                 WHERE t.typname='staff_order_status' AND n.nspname='public') THEN
    CREATE TYPE public.staff_order_status AS ENUM (
      'in_call_center',
      'in_manager', 
      'in_controller',
      'in_technician',
      'in_warehouse',
      'completed',
      'cancelled'
    );
    
    RAISE NOTICE 'Created staff_order_status enum type';
  ELSE
    RAISE NOTICE 'staff_order_status enum type already exists';
  END IF;
END $$;