-- Migration: Update tariff system
-- Date: 2025-01-15
-- Description: 
-- 1. Save old tariff IDs and update connection_orders
-- 2. Delete old "Hammasi birga" tariffs  
-- 3. Add new tariff plans (B2C, BizNET-Pro, Tijorat)
-- 4. Fill NULL tarif_id for old connection_orders

-- Complete migration in one DO block
DO $$
DECLARE
    b2c_new_tariff_id BIGINT;
    b2b_new_tariff_id BIGINT;
    old_tariff_ids BIGINT[];
    updated_count INTEGER;
BEGIN
    -- Step 1: Get old tariff IDs BEFORE deleting
    SELECT array_agg(id) INTO old_tariff_ids 
    FROM public.tarif 
    WHERE name IN ('Hammasi birga 4', 'Hammasi birga 3+', 'Hammasi birga 3', 'Hammasi birga 2', 'Xammasi Birga 2');
    
    RAISE NOTICE 'Found old tariff IDs: %', old_tariff_ids;
    
    -- Step 2: Insert new B2C Plans (only if not exists)
    INSERT INTO public.tarif (name, created_at, updated_at)
    SELECT 'Oddiy-20', NOW(), NOW()
    WHERE NOT EXISTS (SELECT 1 FROM public.tarif WHERE name = 'Oddiy-20');
    
    INSERT INTO public.tarif (name, created_at, updated_at)
    SELECT 'Oddiy-50', NOW(), NOW()
    WHERE NOT EXISTS (SELECT 1 FROM public.tarif WHERE name = 'Oddiy-50');
    
    INSERT INTO public.tarif (name, created_at, updated_at)
    SELECT 'Oddiy-100', NOW(), NOW()
    WHERE NOT EXISTS (SELECT 1 FROM public.tarif WHERE name = 'Oddiy-100');
    
    INSERT INTO public.tarif (name, created_at, updated_at)
    SELECT 'XIT-200', NOW(), NOW()
    WHERE NOT EXISTS (SELECT 1 FROM public.tarif WHERE name = 'XIT-200');
    
    INSERT INTO public.tarif (name, created_at, updated_at)
    SELECT 'VIP-500', NOW(), NOW()
    WHERE NOT EXISTS (SELECT 1 FROM public.tarif WHERE name = 'VIP-500');
    
    INSERT INTO public.tarif (name, created_at, updated_at)
    SELECT 'PREMIUM', NOW(), NOW()
    WHERE NOT EXISTS (SELECT 1 FROM public.tarif WHERE name = 'PREMIUM');
    
    -- Step 3: Insert new BizNET-Pro Plans (only if not exists)
    INSERT INTO public.tarif (name, created_at, updated_at)
    SELECT 'BizNET-Pro-1', NOW(), NOW()
    WHERE NOT EXISTS (SELECT 1 FROM public.tarif WHERE name = 'BizNET-Pro-1');
    
    INSERT INTO public.tarif (name, created_at, updated_at)
    SELECT 'BizNET-Pro-2', NOW(), NOW()
    WHERE NOT EXISTS (SELECT 1 FROM public.tarif WHERE name = 'BizNET-Pro-2');
    
    INSERT INTO public.tarif (name, created_at, updated_at)
    SELECT 'BizNET-Pro-3', NOW(), NOW()
    WHERE NOT EXISTS (SELECT 1 FROM public.tarif WHERE name = 'BizNET-Pro-3');
    
    INSERT INTO public.tarif (name, created_at, updated_at)
    SELECT 'BizNET-Pro-4', NOW(), NOW()
    WHERE NOT EXISTS (SELECT 1 FROM public.tarif WHERE name = 'BizNET-Pro-4');
    
    INSERT INTO public.tarif (name, created_at, updated_at)
    SELECT 'BizNET-Pro-5', NOW(), NOW()
    WHERE NOT EXISTS (SELECT 1 FROM public.tarif WHERE name = 'BizNET-Pro-5');
    
    INSERT INTO public.tarif (name, created_at, updated_at)
    SELECT 'BizNET-Pro-6', NOW(), NOW()
    WHERE NOT EXISTS (SELECT 1 FROM public.tarif WHERE name = 'BizNET-Pro-6');
    
    INSERT INTO public.tarif (name, created_at, updated_at)
    SELECT 'BizNET-Pro-7+', NOW(), NOW()
    WHERE NOT EXISTS (SELECT 1 FROM public.tarif WHERE name = 'BizNET-Pro-7+');
    
    -- Step 4: Insert new Tijorat Plans (only if not exists)
    INSERT INTO public.tarif (name, created_at, updated_at)
    SELECT 'Tijorat-1', NOW(), NOW()
    WHERE NOT EXISTS (SELECT 1 FROM public.tarif WHERE name = 'Tijorat-1');
    
    INSERT INTO public.tarif (name, created_at, updated_at)
    SELECT 'Tijorat-2', NOW(), NOW()
    WHERE NOT EXISTS (SELECT 1 FROM public.tarif WHERE name = 'Tijorat-2');
    
    INSERT INTO public.tarif (name, created_at, updated_at)
    SELECT 'Tijorat-3', NOW(), NOW()
    WHERE NOT EXISTS (SELECT 1 FROM public.tarif WHERE name = 'Tijorat-3');
    
    INSERT INTO public.tarif (name, created_at, updated_at)
    SELECT 'Tijorat-4', NOW(), NOW()
    WHERE NOT EXISTS (SELECT 1 FROM public.tarif WHERE name = 'Tijorat-4');
    
    INSERT INTO public.tarif (name, created_at, updated_at)
    SELECT 'Tijorat-5', NOW(), NOW()
    WHERE NOT EXISTS (SELECT 1 FROM public.tarif WHERE name = 'Tijorat-5');
    
    INSERT INTO public.tarif (name, created_at, updated_at)
    SELECT 'Tijorat-100', NOW(), NOW()
    WHERE NOT EXISTS (SELECT 1 FROM public.tarif WHERE name = 'Tijorat-100');
    
    INSERT INTO public.tarif (name, created_at, updated_at)
    SELECT 'Tijorat-300', NOW(), NOW()
    WHERE NOT EXISTS (SELECT 1 FROM public.tarif WHERE name = 'Tijorat-300');
    
    INSERT INTO public.tarif (name, created_at, updated_at)
    SELECT 'Tijorat-500', NOW(), NOW()
    WHERE NOT EXISTS (SELECT 1 FROM public.tarif WHERE name = 'Tijorat-500');
    
    INSERT INTO public.tarif (name, created_at, updated_at)
    SELECT 'Tijorat-1000', NOW(), NOW()
    WHERE NOT EXISTS (SELECT 1 FROM public.tarif WHERE name = 'Tijorat-1000');
    
    RAISE NOTICE 'Inserted new tariff plans';
    
    -- Step 5: Get new tariff IDs
    SELECT id INTO b2c_new_tariff_id FROM public.tarif WHERE name = 'Oddiy-20' LIMIT 1;
    SELECT id INTO b2b_new_tariff_id FROM public.tarif WHERE name = 'BizNET-Pro-1' LIMIT 1;
    
    RAISE NOTICE 'B2C new tariff ID: %, B2B new tariff ID: %', b2c_new_tariff_id, b2b_new_tariff_id;
    
    -- Step 6: Update old tariff IDs in B2C connection_orders
    IF b2c_new_tariff_id IS NOT NULL AND old_tariff_ids IS NOT NULL THEN
        UPDATE public.connection_orders 
        SET tarif_id = b2c_new_tariff_id
        WHERE tarif_id = ANY(old_tariff_ids)
        AND (business_type = 'B2C' OR business_type IS NULL);
        
        GET DIAGNOSTICS updated_count = ROW_COUNT;
        RAISE NOTICE 'Updated % B2C orders with new tariff', updated_count;
    END IF;
    
    -- Step 7: Update old tariff IDs in B2B connection_orders
    IF b2b_new_tariff_id IS NOT NULL AND old_tariff_ids IS NOT NULL THEN
        UPDATE public.connection_orders 
        SET tarif_id = b2b_new_tariff_id
        WHERE tarif_id = ANY(old_tariff_ids)
        AND business_type = 'B2B';
        
        GET DIAGNOSTICS updated_count = ROW_COUNT;
        RAISE NOTICE 'Updated % B2B orders with new tariff', updated_count;
    END IF;
    
    -- Step 8: Update NULL tarif_id for B2C connection_orders
    IF b2c_new_tariff_id IS NOT NULL THEN
        UPDATE public.connection_orders 
        SET tarif_id = b2c_new_tariff_id
        WHERE tarif_id IS NULL 
        AND (business_type = 'B2C' OR business_type IS NULL);
        
        GET DIAGNOSTICS updated_count = ROW_COUNT;
        RAISE NOTICE 'Updated % NULL tarif_id for B2C orders', updated_count;
    END IF;
    
    -- Step 9: Update NULL tarif_id for B2B connection_orders
    IF b2b_new_tariff_id IS NOT NULL THEN
        UPDATE public.connection_orders 
        SET tarif_id = b2b_new_tariff_id
        WHERE tarif_id IS NULL 
        AND business_type = 'B2B';
        
        GET DIAGNOSTICS updated_count = ROW_COUNT;
        RAISE NOTICE 'Updated % NULL tarif_id for B2B orders', updated_count;
    END IF;
    
    -- Step 9.5: Update old tariff IDs in staff_orders (B2C)
    IF b2c_new_tariff_id IS NOT NULL AND old_tariff_ids IS NOT NULL THEN
        UPDATE public.staff_orders 
        SET tarif_id = b2c_new_tariff_id
        WHERE tarif_id = ANY(old_tariff_ids)
        AND (business_type = 'B2C' OR business_type IS NULL)
        AND type_of_zayavka = 'connection';
        
        GET DIAGNOSTICS updated_count = ROW_COUNT;
        RAISE NOTICE 'Updated % B2C staff orders with new tariff', updated_count;
    END IF;
    
    -- Step 9.6: Update old tariff IDs in staff_orders (B2B)
    IF b2b_new_tariff_id IS NOT NULL AND old_tariff_ids IS NOT NULL THEN
        UPDATE public.staff_orders 
        SET tarif_id = b2b_new_tariff_id
        WHERE tarif_id = ANY(old_tariff_ids)
        AND business_type = 'B2B'
        AND type_of_zayavka = 'connection';
        
        GET DIAGNOSTICS updated_count = ROW_COUNT;
        RAISE NOTICE 'Updated % B2B staff orders with new tariff', updated_count;
    END IF;
    
    -- Step 9.7: Update NULL tarif_id for staff_orders (B2C)
    IF b2c_new_tariff_id IS NOT NULL THEN
        UPDATE public.staff_orders 
        SET tarif_id = b2c_new_tariff_id
        WHERE tarif_id IS NULL 
        AND (business_type = 'B2C' OR business_type IS NULL)
        AND type_of_zayavka = 'connection';
        
        GET DIAGNOSTICS updated_count = ROW_COUNT;
        RAISE NOTICE 'Updated % NULL tarif_id for B2C staff orders', updated_count;
    END IF;
    
    -- Step 9.8: Update NULL tarif_id for staff_orders (B2B)
    IF b2b_new_tariff_id IS NOT NULL THEN
        UPDATE public.staff_orders 
        SET tarif_id = b2b_new_tariff_id
        WHERE tarif_id IS NULL 
        AND business_type = 'B2B'
        AND type_of_zayavka = 'connection';
        
        GET DIAGNOSTICS updated_count = ROW_COUNT;
        RAISE NOTICE 'Updated % NULL tarif_id for B2B staff orders', updated_count;
    END IF;
    
    -- Step 10: Now delete old tariffs
    DELETE FROM public.tarif 
    WHERE name IN (
        'Hammasi birga 4',
        'Hammasi birga 3+',
        'Hammasi birga 3',
        'Hammasi birga 2',
        'Xammasi Birga 2'
    );
    
    GET DIAGNOSTICS updated_count = ROW_COUNT;
    RAISE NOTICE 'Deleted % old tariff plans', updated_count;
    
    -- Step 11: Remove unused 'picture' column from tarif table
    IF EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_schema = 'public' 
        AND table_name = 'tarif' 
        AND column_name = 'picture'
    ) THEN
        ALTER TABLE public.tarif DROP COLUMN picture;
        RAISE NOTICE 'Removed unused picture column from tarif table';
    ELSE
        RAISE NOTICE 'picture column does not exist, skipping';
    END IF;
    
    RAISE NOTICE 'Migration completed successfully';
END $$;