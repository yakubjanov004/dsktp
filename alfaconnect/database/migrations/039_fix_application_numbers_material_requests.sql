-- Migration 039: Fix application_number values in material_requests table
-- This migration properly maps existing ID relationships to REAL application numbers from order tables

-- Check if columns exist before updating
DO $$
BEGIN
    -- Update application_number from connection_orders where connection_order_id exists
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'material_requests' AND column_name = 'connection_order_id') THEN
        UPDATE material_requests 
        SET application_number = co.application_number
        FROM connection_orders co 
        WHERE material_requests.connection_order_id = co.id 
        AND (material_requests.application_number IS NULL OR material_requests.application_number LIKE 'UNKNOWN-%');
    END IF;

    -- Update application_number from technician_orders where technician_order_id exists
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'material_requests' AND column_name = 'technician_order_id') THEN
        UPDATE material_requests 
        SET application_number = tech_orders.application_number
        FROM technician_orders tech_orders 
        WHERE material_requests.technician_order_id = tech_orders.id 
        AND (material_requests.application_number IS NULL OR material_requests.application_number LIKE 'UNKNOWN-%');
    END IF;

    -- Update application_number from staff_orders where staff_order_id exists
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'material_requests' AND column_name = 'staff_order_id') THEN
        UPDATE material_requests 
        SET application_number = so.application_number
        FROM staff_orders so 
        WHERE material_requests.staff_order_id = so.id 
        AND (material_requests.application_number IS NULL OR material_requests.application_number LIKE 'UNKNOWN-%');
    END IF;

    -- For records that still don't have proper application numbers, we need to find them by applications_id
    -- This maps the applications_id to the actual order tables
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'material_requests' AND column_name = 'applications_id') THEN
        UPDATE material_requests 
        SET application_number = co.application_number
        FROM connection_orders co 
        WHERE material_requests.applications_id = co.id 
        AND material_requests.application_number IS NULL;

        UPDATE material_requests 
        SET application_number = tech_orders.application_number
        FROM technician_orders tech_orders 
        WHERE material_requests.applications_id = tech_orders.id 
        AND material_requests.application_number IS NULL;

        UPDATE material_requests 
        SET application_number = so.application_number
        FROM staff_orders so 
        WHERE material_requests.applications_id = so.id 
        AND material_requests.application_number IS NULL;
    END IF;
END $$;

-- Make application_number NOT NULL to ensure data integrity
ALTER TABLE material_requests 
ALTER COLUMN application_number SET NOT NULL;

-- Add a comment explaining the fix
COMMENT ON COLUMN material_requests.application_number IS 'Application number that identifies which order this material request belongs to - mapped to REAL application numbers from order tables';
