-- Migration 036: Make application_number required in AKT tables
-- This migration makes application_number NOT NULL and adds constraints

-- First, let's check if there are any NULL application_numbers and fix them
-- This should not happen if the previous migration worked correctly, but just in case
UPDATE akt_documents 
SET application_number = 'UNKNOWN-' || request_id::text || '-' || request_type
WHERE application_number IS NULL;

UPDATE akt_ratings 
SET application_number = 'UNKNOWN-' || request_id::text || '-' || request_type
WHERE application_number IS NULL;

-- Make application_number NOT NULL
ALTER TABLE akt_documents 
ALTER COLUMN application_number SET NOT NULL;

ALTER TABLE akt_ratings 
ALTER COLUMN application_number SET NOT NULL;

-- Add unique constraint to prevent duplicate application numbers in akt_documents
-- (one application can have multiple AKT documents, but we want to track them properly)
ALTER TABLE akt_documents 
ADD CONSTRAINT unique_akt_document_per_application 
UNIQUE (application_number, request_type);

-- Add comments explaining the constraints
COMMENT ON CONSTRAINT unique_akt_document_per_application ON akt_documents 
IS 'Ensures each application can have only one AKT document per request type';

-- Update table comments
COMMENT ON TABLE akt_documents IS 'AKT documents table - stores official work completion documents with application numbers';
COMMENT ON TABLE akt_ratings IS 'AKT ratings table - stores client ratings for completed work with application numbers';
