-- Migration 038: Add application_number to material_and_technician table
-- This migration adds application_number to track which application the materials were used for

-- Add application_number column to material_and_technician table
ALTER TABLE material_and_technician 
ADD COLUMN IF NOT EXISTS application_number TEXT;

-- Add issued_by column to track who issued the materials
ALTER TABLE material_and_technician 
ADD COLUMN IF NOT EXISTS issued_by INTEGER;

-- Add issued_at column to track when materials were issued
ALTER TABLE material_and_technician 
ADD COLUMN IF NOT EXISTS issued_at TIMESTAMP WITH TIME ZONE DEFAULT NOW();

-- Add material_name column for easier reference
ALTER TABLE material_and_technician 
ADD COLUMN IF NOT EXISTS material_name TEXT;

-- Add material_unit column for reference
ALTER TABLE material_and_technician 
ADD COLUMN IF NOT EXISTS material_unit TEXT DEFAULT 'dona';

-- Add price and total_price columns for cost tracking
ALTER TABLE material_and_technician 
ADD COLUMN IF NOT EXISTS price DECIMAL(10,2) DEFAULT 0.0;

ALTER TABLE material_and_technician 
ADD COLUMN IF NOT EXISTS total_price DECIMAL(10,2) DEFAULT 0.0;

-- Add is_approved column to track approval status
ALTER TABLE material_and_technician 
ADD COLUMN IF NOT EXISTS is_approved BOOLEAN DEFAULT FALSE;

-- Add request_type column to identify the type of order
ALTER TABLE material_and_technician 
ADD COLUMN IF NOT EXISTS request_type TEXT DEFAULT 'technician';

-- Populate material_name from materials table
UPDATE material_and_technician 
SET material_name = m.name
FROM materials m 
WHERE material_and_technician.material_id = m.id;

-- Populate price from materials table
UPDATE material_and_technician 
SET price = m.price
FROM materials m 
WHERE material_and_technician.material_id = m.id;

-- Calculate total_price
UPDATE material_and_technician 
SET total_price = price * quantity;

-- Add comments to the new columns
COMMENT ON COLUMN material_and_technician.application_number IS 'Application number that identifies which order these materials were used for';
COMMENT ON COLUMN material_and_technician.issued_by IS 'User ID of who issued the materials';
COMMENT ON COLUMN material_and_technician.issued_at IS 'When the materials were issued';
COMMENT ON COLUMN material_and_technician.material_name IS 'Name of the material for easy reference';
COMMENT ON COLUMN material_and_technician.material_unit IS 'Unit of measurement for the material';
COMMENT ON COLUMN material_and_technician.price IS 'Price per unit of the material';
COMMENT ON COLUMN material_and_technician.total_price IS 'Total price (price * quantity)';
COMMENT ON COLUMN material_and_technician.is_approved IS 'Whether the material usage is approved';
COMMENT ON COLUMN material_and_technician.request_type IS 'Type of request (connection, technician, staff)';

-- Add indexes for better performance
CREATE INDEX IF NOT EXISTS idx_material_and_technician_application_number ON material_and_technician(application_number);
CREATE INDEX IF NOT EXISTS idx_material_and_technician_user_id ON material_and_technician(user_id);
CREATE INDEX IF NOT EXISTS idx_material_and_technician_material_id ON material_and_technician(material_id);

-- Update table comment
COMMENT ON TABLE material_and_technician IS 'Material and technician tracking table - tracks which materials were used by technicians for specific applications';
