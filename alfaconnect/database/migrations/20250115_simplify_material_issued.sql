-- Migration: Simplify material_issued table
-- Date: 2025-01-15
-- Description: Remove unnecessary columns since we have application_number

-- Remove unnecessary columns from material_issued
ALTER TABLE material_issued 
DROP COLUMN IF EXISTS connection_order_id,
DROP COLUMN IF EXISTS technician_order_id,
DROP COLUMN IF EXISTS staff_order_id;

-- Add request_type column for easier filtering
ALTER TABLE material_issued 
ADD COLUMN IF NOT EXISTS request_type VARCHAR(20) DEFAULT 'connection';

-- Update request_type based on application_number pattern or existing data
-- This is a one-time update to set the correct request_type
UPDATE material_issued 
SET request_type = 'connection'
WHERE application_number LIKE 'CONN-%' OR application_number ~ '^[0-9]+$';

UPDATE material_issued 
SET request_type = 'technician'
WHERE application_number LIKE 'TECH-%';

UPDATE material_issued 
SET request_type = 'staff'
WHERE application_number LIKE 'STAFF-%';

-- Add comment
COMMENT ON COLUMN material_issued.request_type IS 'Type of request: connection, technician, or staff';
COMMENT ON COLUMN material_issued.application_number IS 'Application number from the original order';
