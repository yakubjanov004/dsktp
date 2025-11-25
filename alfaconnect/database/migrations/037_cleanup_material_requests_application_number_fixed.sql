-- Migration 037: Cleanup material_requests to use application_number consistently (FIXED)
-- This migration ensures application_number is populated and removes redundant columns

-- First, let's check what columns actually exist and populate application_number
-- Update from connection_orders (if connection_order_id exists)
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.columns 
               WHERE table_name = 'material_requests' 
               AND column_name = 'connection_order_id') THEN
        UPDATE material_requests 
        SET application_number = co.application_number
        FROM connection_orders co 
        WHERE material_requests.connection_order_id = co.id 
        AND material_requests.application_number IS NULL;
    END IF;
END $$;

-- Update from technician_orders (if technician_order_id exists)
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.columns 
               WHERE table_name = 'material_requests' 
               AND column_name = 'technician_order_id') THEN
        UPDATE material_requests 
        SET application_number = tech_orders.application_number
        FROM technician_orders tech_orders 
        WHERE material_requests.technician_order_id = tech_orders.id 
        AND material_requests.application_number IS NULL;
    END IF;
END $$;

-- Update from staff_orders (if staff_order_id exists)
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.columns 
               WHERE table_name = 'material_requests' 
               AND column_name = 'staff_order_id') THEN
        UPDATE material_requests 
        SET application_number = so.application_number
        FROM staff_orders so 
        WHERE material_requests.staff_order_id = so.id 
        AND material_requests.application_number IS NULL;
    END IF;
END $$;

-- Handle any remaining NULL application_numbers with fallback
UPDATE material_requests 
SET application_number = 'UNKNOWN-' || id::text || '-' || COALESCE(request_type, 'unknown')
WHERE application_number IS NULL;

-- Make application_number NOT NULL
ALTER TABLE material_requests 
ALTER COLUMN application_number SET NOT NULL;

-- Remove the redundant ID columns if they exist
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.columns 
               WHERE table_name = 'material_requests' 
               AND column_name = 'applications_id') THEN
        ALTER TABLE material_requests DROP COLUMN applications_id;
    END IF;
    
    IF EXISTS (SELECT 1 FROM information_schema.columns 
               WHERE table_name = 'material_requests' 
               AND column_name = 'connection_order_id') THEN
        ALTER TABLE material_requests DROP COLUMN connection_order_id;
    END IF;
    
    IF EXISTS (SELECT 1 FROM information_schema.columns 
               WHERE table_name = 'material_requests' 
               AND column_name = 'technician_order_id') THEN
        ALTER TABLE material_requests DROP COLUMN technician_order_id;
    END IF;
    
    IF EXISTS (SELECT 1 FROM information_schema.columns 
               WHERE table_name = 'material_requests' 
               AND column_name = 'staff_order_id') THEN
        ALTER TABLE material_requests DROP COLUMN staff_order_id;
    END IF;
END $$;

-- Add index for better performance
CREATE INDEX IF NOT EXISTS idx_material_requests_application_number ON material_requests(application_number);

-- Add comment explaining the new structure
COMMENT ON TABLE material_requests IS 'Material requests table - stores material requests by application_number instead of separate order IDs';
COMMENT ON COLUMN material_requests.application_number IS 'Application number that identifies which order this material request belongs to (e.g., CONN-B2C-0001, TECH-B2C-0001)';
