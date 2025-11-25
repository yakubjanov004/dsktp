-- Migration: Minimize material_issued table to essential fields only
-- Date: 2025-01-15
-- Description: Keep only essential fields for material_issued

-- Remove unnecessary columns
ALTER TABLE material_issued 
DROP COLUMN IF EXISTS notes,
DROP COLUMN IF EXISTS approved_by,
DROP COLUMN IF EXISTS approved_at,
DROP COLUMN IF EXISTS is_returned,
DROP COLUMN IF EXISTS returned_quantity,
DROP COLUMN IF EXISTS returned_at,
DROP COLUMN IF EXISTS returned_by,
DROP COLUMN IF EXISTS return_notes,
DROP COLUMN IF EXISTS created_at,
DROP COLUMN IF EXISTS updated_at;

-- Keep only essential fields:
-- id, material_id, quantity, price, total_price, issued_by, issued_at, 
-- material_name, material_unit, is_approved, application_number, request_type

-- Add comments for clarity
COMMENT ON TABLE material_issued IS 'Essential material tracking - simplified version';
COMMENT ON COLUMN material_issued.application_number IS 'Application number from original order';
COMMENT ON COLUMN material_issued.request_type IS 'Type: connection, technician, or staff';
COMMENT ON COLUMN material_issued.is_approved IS 'Whether warehouse approved this material';
