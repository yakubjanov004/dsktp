-- Migration 010: Add UNIQUE constraint to material_requests table
-- This fixes the ON CONFLICT issue for material requests UPSERT operations

-- Add UNIQUE constraint on (user_id, applications_id, material_id)
ALTER TABLE material_requests 
  ADD CONSTRAINT ux_material_requests_user_app_material UNIQUE (user_id, applications_id, material_id);

-- Set NOT NULL constraints (recommended)
ALTER TABLE material_requests 
  ALTER COLUMN user_id SET NOT NULL,
  ALTER COLUMN applications_id SET NOT NULL,
  ALTER COLUMN material_id SET NOT NULL;

-- Add comment for documentation
COMMENT ON CONSTRAINT ux_material_requests_user_app_material ON material_requests 
  IS 'Ensures unique combination of user_id, applications_id and material_id for UPSERT operations';