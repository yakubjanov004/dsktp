-- Migration: Add application_number to material_issued table
-- Date: 2025-01-15
-- Description: Add application_number field to material_issued for easier tracking

-- Add application_number column to material_issued
ALTER TABLE material_issued 
ADD COLUMN IF NOT EXISTS application_number VARCHAR(50);

-- Add comment for application_number
COMMENT ON COLUMN material_issued.application_number IS 'Application number from the original order (connection, technician, or staff)';

-- Update existing records with application_number
UPDATE material_issued 
SET application_number = (
    SELECT co.application_number 
    FROM connection_orders co 
    WHERE co.id = material_issued.connection_order_id
)
WHERE connection_order_id IS NOT NULL AND application_number IS NULL;

UPDATE material_issued 
SET application_number = (
    SELECT to2.application_number 
    FROM technician_orders to2 
    WHERE to2.id = material_issued.technician_order_id
)
WHERE technician_order_id IS NOT NULL AND application_number IS NULL;

UPDATE material_issued 
SET application_number = (
    SELECT so.application_number 
    FROM staff_orders so 
    WHERE so.id = material_issued.staff_order_id
)
WHERE staff_order_id IS NOT NULL AND application_number IS NULL;
