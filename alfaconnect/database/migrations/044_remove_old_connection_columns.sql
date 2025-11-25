-- Migration: Remove deprecated columns from connections table
-- Date: 2025-01-20
-- Description: Remove old connection_id, technician_id, staff_id columns
--             as they are no longer needed after migration to application_number

-- Drop old columns
ALTER TABLE public.connections DROP COLUMN IF EXISTS connection_id;
ALTER TABLE public.connections DROP COLUMN IF EXISTS technician_id;
ALTER TABLE public.connections DROP COLUMN IF EXISTS staff_id;

-- Log the operation
DO $$
BEGIN
    RAISE NOTICE 'Successfully removed deprecated columns (connection_id, technician_id, staff_id) from connections table';
END $$;

