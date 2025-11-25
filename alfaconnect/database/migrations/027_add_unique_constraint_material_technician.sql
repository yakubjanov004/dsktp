-- Migration 027: Add UNIQUE constraint to material_and_technician table
-- This fixes the ON CONFLICT issue for UPSERT operations

-- Add UNIQUE constraint on (user_id, material_id)
ALTER TABLE material_and_technician 
  ADD CONSTRAINT ux_mat_tech_user_material UNIQUE (user_id, material_id);

-- Set NOT NULL constraints (recommended)
ALTER TABLE material_and_technician 
  ALTER COLUMN user_id SET NOT NULL,
  ALTER COLUMN material_id SET NOT NULL;

-- Add comment for documentation
COMMENT ON CONSTRAINT ux_mat_tech_user_material ON material_and_technician 
  IS 'Ensures unique combination of user_id and material_id for UPSERT operations';
