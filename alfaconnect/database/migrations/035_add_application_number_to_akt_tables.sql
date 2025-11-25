-- Migration 035: Add application_number to AKT tables
-- This migration adds application_number column to akt_documents and akt_ratings tables
-- and populates them with the correct application numbers from related orders

-- Add application_number column to akt_documents table
ALTER TABLE akt_documents 
ADD COLUMN IF NOT EXISTS application_number TEXT;

-- Add application_number column to akt_ratings table  
ALTER TABLE akt_ratings 
ADD COLUMN IF NOT EXISTS application_number TEXT;

-- Update akt_documents with application numbers from connection_orders
UPDATE akt_documents 
SET application_number = co.application_number
FROM connection_orders co 
WHERE akt_documents.request_id = co.id 
AND akt_documents.request_type = 'connection';

-- Update akt_documents with application numbers from technician_orders
UPDATE akt_documents 
SET application_number = tech_orders.application_number
FROM technician_orders tech_orders 
WHERE akt_documents.request_id = tech_orders.id 
AND akt_documents.request_type = 'technician';

-- Update akt_documents with application numbers from staff_orders
UPDATE akt_documents 
SET application_number = so.application_number
FROM staff_orders so 
WHERE akt_documents.request_id = so.id 
AND akt_documents.request_type = 'staff';

-- Update akt_ratings with application numbers from connection_orders
UPDATE akt_ratings 
SET application_number = co.application_number
FROM connection_orders co 
WHERE akt_ratings.request_id = co.id 
AND akt_ratings.request_type = 'connection';

-- Update akt_ratings with application numbers from technician_orders
UPDATE akt_ratings 
SET application_number = tech_orders.application_number
FROM technician_orders tech_orders 
WHERE akt_ratings.request_id = tech_orders.id 
AND akt_ratings.request_type = 'technician';

-- Update akt_ratings with application numbers from staff_orders
UPDATE akt_ratings 
SET application_number = so.application_number
FROM staff_orders so 
WHERE akt_ratings.request_id = so.id 
AND akt_ratings.request_type = 'staff';

-- Add comments to the new columns
COMMENT ON COLUMN akt_documents.application_number IS 'Application number from the related order (e.g., CONN-B2C-0001, TECH-B2C-0001)';
COMMENT ON COLUMN akt_ratings.application_number IS 'Application number from the related order (e.g., CONN-B2C-0001, TECH-B2C-0001)';

-- Add indexes for better performance
CREATE INDEX IF NOT EXISTS idx_akt_documents_application_number ON akt_documents(application_number);
CREATE INDEX IF NOT EXISTS idx_akt_ratings_application_number ON akt_ratings(application_number);
