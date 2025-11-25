-- Migration 029: Add UNIQUE constraint to material_requests table
-- This prevents duplicate material selections and improves performance

-- Ensure no duplicate entries exist first (PostgreSQL compatible syntax)
DELETE FROM material_requests 
WHERE id IN (
    SELECT a.id FROM material_requests a
    INNER JOIN material_requests b ON 
        a.user_id = b.user_id 
        AND a.applications_id = b.applications_id 
        AND a.material_id = b.material_id
        AND a.id > b.id
);

-- Add UNIQUE constraint to prevent duplicate material selections
ALTER TABLE material_requests 
ADD CONSTRAINT uq_material_requests_user_app_material 
UNIQUE (user_id, applications_id, material_id);

-- Add index for better performance on pending usage queries
CREATE INDEX IF NOT EXISTS idx_material_requests_pending 
ON material_requests(user_id, material_id, applications_id)
WHERE source_type = 'technician_stock';

-- Add comment explaining the constraint
COMMENT ON CONSTRAINT uq_material_requests_user_app_material ON material_requests 
IS 'Prevents duplicate material selections for the same technician and order';
