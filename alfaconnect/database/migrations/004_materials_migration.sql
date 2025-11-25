-- Migration 004: Materials Migration
-- This migration handles alterations to materials and material_requests tables

-- Remove columns from material_requests table that don't exist in models.py
ALTER TABLE material_requests DROP COLUMN IF EXISTS status;
ALTER TABLE material_requests DROP COLUMN IF EXISTS requested_at;
ALTER TABLE material_requests DROP COLUMN IF EXISTS approved_at;
ALTER TABLE material_requests DROP COLUMN IF EXISTS approved_by;

-- Add material_id column to material_requests table to match models.py
ALTER TABLE material_requests ADD COLUMN IF NOT EXISTS material_id INTEGER;

-- Add foreign key constraint for material_id
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.table_constraints 
        WHERE constraint_name = 'fk_material_requests_material_id' 
        AND table_name = 'material_requests'
    ) THEN
        ALTER TABLE material_requests ADD CONSTRAINT fk_material_requests_material_id 
            FOREIGN KEY (material_id) REFERENCES materials(id);
    END IF;
END $$;

-- Add new status value to connection_order_status ENUM
ALTER TYPE connection_order_status ADD VALUE IF NOT EXISTS 'between_controller_technician';

-- Add new status value to technician_order_status ENUM
ALTER TYPE technician_order_status ADD VALUE IF NOT EXISTS 'between_controller_technician';
