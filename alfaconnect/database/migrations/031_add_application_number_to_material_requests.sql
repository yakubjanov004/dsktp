-- Migration 031: Add application_number column to material_requests table
-- This allows storing the full application number (e.g., CONN-B2C-1001) for better tracking

-- Add application_number column
ALTER TABLE material_requests 
ADD COLUMN IF NOT EXISTS application_number VARCHAR(50);

-- Add index for better performance on application_number queries
CREATE INDEX IF NOT EXISTS idx_material_requests_application_number 
ON material_requests(application_number);

-- Add comment explaining the column
COMMENT ON COLUMN material_requests.application_number 
IS 'Full application number (e.g., CONN-B2C-1001, TECH-B2B-0001) for better tracking';
