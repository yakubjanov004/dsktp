-- Migration 030: Improve material requests persistence
-- This migration ensures material requests are properly saved and recovered

-- Add default value for source_type column
ALTER TABLE material_requests 
ALTER COLUMN source_type SET DEFAULT 'warehouse';

-- Add check constraint to ensure source_type has valid values
ALTER TABLE material_requests 
ADD CONSTRAINT chk_material_requests_source_type 
CHECK (source_type IN ('warehouse', 'technician_stock'));

-- Add index for better performance on source_type queries
CREATE INDEX IF NOT EXISTS idx_material_requests_source_type 
ON material_requests(source_type);

-- Add index for recovery queries
CREATE INDEX IF NOT EXISTS idx_material_requests_recovery 
ON material_requests(user_id, applications_id, source_type, created_at);

-- Add comment explaining the source_type column
COMMENT ON COLUMN material_requests.source_type 
IS 'Source of material: warehouse (from warehouse) or technician_stock (from technician inventory)';
