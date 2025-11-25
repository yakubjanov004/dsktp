-- Migration 041: Rollback application_number refactoring
-- This migration provides rollback procedures in case the refactoring needs to be undone
-- WARNING: This will restore old column structure but keep application_number for compatibility

-- Create backup tables before rollback
CREATE TABLE IF NOT EXISTS material_requests_backup AS 
SELECT * FROM material_requests;

CREATE TABLE IF NOT EXISTS akt_documents_backup AS 
SELECT * FROM akt_documents;

CREATE TABLE IF NOT EXISTS akt_ratings_backup AS 
SELECT * FROM akt_ratings;

-- Add comments for backup tables
COMMENT ON TABLE material_requests_backup IS 'Backup of material_requests before rollback - created during migration 041';
COMMENT ON TABLE akt_documents_backup IS 'Backup of akt_documents before rollback - created during migration 041';
COMMENT ON TABLE akt_ratings_backup IS 'Backup of akt_ratings before rollback - created during migration 041';

-- Restore old columns to material_requests if they don't exist
DO $$
BEGIN
    -- Add applications_id column back
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name = 'material_requests' 
                   AND column_name = 'applications_id') THEN
        ALTER TABLE material_requests ADD COLUMN applications_id BIGINT;
    END IF;
    
    -- Add connection_order_id column back
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name = 'material_requests' 
                   AND column_name = 'connection_order_id') THEN
        ALTER TABLE material_requests ADD COLUMN connection_order_id BIGINT;
    END IF;
    
    -- Add technician_order_id column back
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name = 'material_requests' 
                   AND column_name = 'technician_order_id') THEN
        ALTER TABLE material_requests ADD COLUMN technician_order_id BIGINT;
    END IF;
    
    -- Add staff_order_id column back
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name = 'material_requests' 
                   AND column_name = 'staff_order_id') THEN
        ALTER TABLE material_requests ADD COLUMN staff_order_id BIGINT;
    END IF;
END $$;

-- Restore old columns to akt_documents if they don't exist
DO $$
BEGIN
    -- Add request_id column back
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name = 'akt_documents' 
                   AND column_name = 'request_id') THEN
        ALTER TABLE akt_documents ADD COLUMN request_id INTEGER;
    END IF;
    
    -- Add request_type column back
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name = 'akt_documents' 
                   AND column_name = 'request_type') THEN
        ALTER TABLE akt_documents ADD COLUMN request_type VARCHAR(20);
    END IF;
END $$;

-- Restore old columns to akt_ratings if they don't exist
DO $$
BEGIN
    -- Add request_id column back
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name = 'akt_ratings' 
                   AND column_name = 'request_id') THEN
        ALTER TABLE akt_ratings ADD COLUMN request_id INTEGER;
    END IF;
    
    -- Add request_type column back
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name = 'akt_ratings' 
                   AND column_name = 'request_type') THEN
        ALTER TABLE akt_ratings ADD COLUMN request_type VARCHAR(20);
    END IF;
END $$;

-- Populate old columns from application_number relationships
-- This is a best-effort restoration - some data might not be perfectly restored

-- Restore material_requests old columns
UPDATE material_requests 
SET connection_order_id = co.id
FROM connection_orders co 
WHERE material_requests.application_number = co.application_number;

UPDATE material_requests 
SET technician_order_id = to.id
FROM technician_orders to 
WHERE material_requests.application_number = to.application_number;

UPDATE material_requests 
SET staff_order_id = so.id
FROM staff_orders so 
WHERE material_requests.application_number = so.application_number;

-- Set applications_id to the appropriate order ID
UPDATE material_requests 
SET applications_id = COALESCE(connection_order_id, technician_order_id, staff_order_id);

-- Restore akt_documents old columns
UPDATE akt_documents 
SET request_id = co.id, request_type = 'connection'
FROM connection_orders co 
WHERE akt_documents.application_number = co.application_number;

UPDATE akt_documents 
SET request_id = to.id, request_type = 'technician'
FROM technician_orders to 
WHERE akt_documents.application_number = to.application_number
AND request_id IS NULL;

UPDATE akt_documents 
SET request_id = so.id, request_type = 'staff'
FROM staff_orders so 
WHERE akt_documents.application_number = so.application_number
AND request_id IS NULL;

-- Restore akt_ratings old columns
UPDATE akt_ratings 
SET request_id = co.id, request_type = 'connection'
FROM connection_orders co 
WHERE akt_ratings.application_number = co.application_number;

UPDATE akt_ratings 
SET request_id = to.id, request_type = 'technician'
FROM technician_orders to 
WHERE akt_ratings.application_number = to.application_number
AND request_id IS NULL;

UPDATE akt_ratings 
SET request_id = so.id, request_type = 'staff'
FROM staff_orders so 
WHERE akt_ratings.application_number = so.application_number
AND request_id IS NULL;

-- Restore old constraints and indexes
DO $$
BEGIN
    -- Restore material_requests unique constraint if it doesn't exist
    IF NOT EXISTS (SELECT 1 FROM information_schema.table_constraints 
                   WHERE table_name = 'material_requests' 
                   AND constraint_name = 'unique_material_requests_user_application') THEN
        ALTER TABLE material_requests 
        ADD CONSTRAINT unique_material_requests_user_application 
        UNIQUE (user_id, applications_id, material_id);
    END IF;
    
    -- Restore akt_documents unique constraint if it doesn't exist
    IF NOT EXISTS (SELECT 1 FROM information_schema.table_constraints 
                   WHERE table_name = 'akt_documents' 
                   AND constraint_name = 'unique_akt_document_request') THEN
        ALTER TABLE akt_documents 
        ADD CONSTRAINT unique_akt_document_request 
        UNIQUE (request_id, request_type);
    END IF;
    
    -- Restore akt_ratings unique constraint if it doesn't exist
    IF NOT EXISTS (SELECT 1 FROM information_schema.table_constraints 
                   WHERE table_name = 'akt_ratings' 
                   AND constraint_name = 'unique_akt_rating_request') THEN
        ALTER TABLE akt_ratings 
        ADD CONSTRAINT unique_akt_rating_request 
        UNIQUE (request_id, request_type);
    END IF;
END $$;

-- Restore old indexes
CREATE INDEX IF NOT EXISTS idx_material_requests_applications_id ON material_requests(applications_id);
CREATE INDEX IF NOT EXISTS idx_material_requests_connection_order_id ON material_requests(connection_order_id);
CREATE INDEX IF NOT EXISTS idx_material_requests_technician_order_id ON material_requests(technician_order_id);
CREATE INDEX IF NOT EXISTS idx_material_requests_staff_order_id ON material_requests(staff_order_id);

CREATE INDEX IF NOT EXISTS idx_akt_documents_request ON akt_documents(request_id, request_type);
CREATE INDEX IF NOT EXISTS idx_akt_ratings_request ON akt_ratings(request_id, request_type);

-- Update table comments to reflect rollback
COMMENT ON TABLE material_requests IS 'Material requests table - ROLLED BACK to use old ID columns alongside application_number';
COMMENT ON TABLE akt_documents IS 'AKT documents table - ROLLED BACK to use old request_id/request_type alongside application_number';
COMMENT ON TABLE akt_ratings IS 'AKT ratings table - ROLLED BACK to use old request_id/request_type alongside application_number';

-- Add rollback completion notice
DO $$
BEGIN
    RAISE NOTICE 'Rollback completed! Old column structure restored. Application_number columns kept for compatibility.';
    RAISE NOTICE 'Backup tables created: material_requests_backup, akt_documents_backup, akt_ratings_backup';
    RAISE NOTICE 'Please verify data integrity and update application code to use old patterns.';
END $$;
