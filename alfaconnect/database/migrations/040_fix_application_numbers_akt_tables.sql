-- Migration 040: Fix application_number values in AKT tables
-- This migration properly maps existing request_id relationships to correct application numbers

-- Add application_number column to akt_documents if it doesn't exist
ALTER TABLE akt_documents 
ADD COLUMN IF NOT EXISTS application_number TEXT;

-- Add application_number column to akt_ratings if it doesn't exist
ALTER TABLE akt_ratings 
ADD COLUMN IF NOT EXISTS application_number TEXT;

-- Update akt_documents with application numbers from connection_orders
UPDATE akt_documents 
SET application_number = co.application_number
FROM connection_orders co 
WHERE akt_documents.request_id = co.id 
AND akt_documents.request_type = 'connection'
AND (akt_documents.application_number IS NULL OR akt_documents.application_number LIKE 'UNKNOWN-%');

-- Update akt_documents with application numbers from technician_orders
UPDATE akt_documents 
SET application_number = tech_orders.application_number
FROM technician_orders tech_orders 
WHERE akt_documents.request_id = tech_orders.id 
AND akt_documents.request_type = 'technician'
AND (akt_documents.application_number IS NULL OR akt_documents.application_number LIKE 'UNKNOWN-%');

-- Update akt_documents with application numbers from staff_orders
UPDATE akt_documents 
SET application_number = so.application_number
FROM staff_orders so 
WHERE akt_documents.request_id = so.id 
AND akt_documents.request_type = 'staff'
AND (akt_documents.application_number IS NULL OR akt_documents.application_number LIKE 'UNKNOWN-%');

-- Update akt_ratings with application numbers from connection_orders
UPDATE akt_ratings 
SET application_number = co.application_number
FROM connection_orders co 
WHERE akt_ratings.request_id = co.id 
AND akt_ratings.request_type = 'connection'
AND (akt_ratings.application_number IS NULL OR akt_ratings.application_number LIKE 'UNKNOWN-%');

-- Update akt_ratings with application numbers from technician_orders
UPDATE akt_ratings 
SET application_number = tech_orders.application_number
FROM technician_orders tech_orders 
WHERE akt_ratings.request_id = tech_orders.id 
AND akt_ratings.request_type = 'technician'
AND (akt_ratings.application_number IS NULL OR akt_ratings.application_number LIKE 'UNKNOWN-%');

-- Update akt_ratings with application numbers from staff_orders
UPDATE akt_ratings 
SET application_number = so.application_number
FROM staff_orders so 
WHERE akt_ratings.request_id = so.id 
AND akt_ratings.request_type = 'staff'
AND (akt_ratings.application_number IS NULL OR akt_ratings.application_number LIKE 'UNKNOWN-%');

-- Handle any remaining NULL or UNKNOWN values by mapping to real application numbers
-- These should be very few, but we'll map them to the actual order tables
UPDATE akt_documents 
SET application_number = COALESCE(
    (SELECT co.application_number FROM connection_orders co WHERE co.id = akt_documents.request_id AND akt_documents.request_type = 'connection'),
    (SELECT tech_orders.application_number FROM technician_orders tech_orders WHERE tech_orders.id = akt_documents.request_id AND akt_documents.request_type = 'technician'),
    (SELECT so.application_number FROM staff_orders so WHERE so.id = akt_documents.request_id AND akt_documents.request_type = 'staff')
)
WHERE application_number IS NULL OR application_number LIKE 'UNKNOWN-%';

UPDATE akt_ratings 
SET application_number = COALESCE(
    (SELECT co.application_number FROM connection_orders co WHERE co.id = akt_ratings.request_id AND akt_ratings.request_type = 'connection'),
    (SELECT tech_orders.application_number FROM technician_orders tech_orders WHERE tech_orders.id = akt_ratings.request_id AND akt_ratings.request_type = 'technician'),
    (SELECT so.application_number FROM staff_orders so WHERE so.id = akt_ratings.request_id AND akt_ratings.request_type = 'staff')
)
WHERE application_number IS NULL OR application_number LIKE 'UNKNOWN-%';

-- Make application_number NOT NULL
ALTER TABLE akt_documents 
ALTER COLUMN application_number SET NOT NULL;

ALTER TABLE akt_ratings 
ALTER COLUMN application_number SET NOT NULL;

-- Add indexes for better performance
CREATE INDEX IF NOT EXISTS idx_akt_documents_application_number ON akt_documents(application_number);
CREATE INDEX IF NOT EXISTS idx_akt_ratings_application_number ON akt_ratings(application_number);

-- Add comments
COMMENT ON COLUMN akt_documents.application_number IS 'Application number that identifies which order this AKT document belongs to - fixed from UNKNOWN values';
COMMENT ON COLUMN akt_ratings.application_number IS 'Application number that identifies which order this AKT rating belongs to - fixed from UNKNOWN values';
