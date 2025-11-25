-- Migration 032: Remove unused columns from material_requests table
-- This migration removes columns that are not being used

-- Remove description column (not used in material_requests)
ALTER TABLE material_requests DROP COLUMN IF EXISTS description;

-- Add comment explaining the cleanup
COMMENT ON TABLE material_requests IS 'Material requests table - stores technician material selections with proper order tracking';
