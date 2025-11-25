-- Migration 048: Cleanup Material Tables
-- Date: 2025-01-21
-- Description: 
--   1. Remove is_approved from material_issued (not needed)
--   2. Add material_unit to materials table
--   3. Remove is_approved and request_type from material_and_technician (not needed)

-- ==================== 1. REMOVE is_approved FROM material_issued ====================
-- is_approved is not needed in material_issued because materials are already approved when issued
ALTER TABLE material_issued 
DROP COLUMN IF EXISTS is_approved;

COMMENT ON TABLE material_issued IS 'Material issued records - simplified without is_approved';

-- ==================== 2. ADD material_unit TO materials ====================
-- Add material_unit column to materials table for tracking unit of measurement
ALTER TABLE materials 
ADD COLUMN IF NOT EXISTS material_unit TEXT DEFAULT 'dona';

COMMENT ON COLUMN materials.material_unit IS 'Unit of measurement for the material (dona, metr, litr, kg, etc.)';

-- Update existing materials with default 'dona' if material_unit is NULL
UPDATE materials 
SET material_unit = 'dona' 
WHERE material_unit IS NULL;

-- ==================== 3. REMOVE is_approved AND request_type FROM material_and_technician ====================
-- is_approved is not needed - materials are tracked by application_number
-- request_type is not needed - can be determined from application_number prefix (CONN-, TECH-, STAFF-)
ALTER TABLE material_and_technician 
DROP COLUMN IF EXISTS is_approved,
DROP COLUMN IF EXISTS request_type;

COMMENT ON TABLE material_and_technician IS 'Material and technician tracking - tracks materials issued to technicians with application_number, issued_by, and issued_at';
COMMENT ON COLUMN material_and_technician.application_number IS 'Application number identifies which order - request type can be determined from prefix (CONN-, TECH-, STAFF-)';

