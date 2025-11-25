-- 045_staff_orders_cleanup_and_roles.sql
-- 1. Drop media and problem_description columns
ALTER TABLE public.staff_orders DROP COLUMN IF EXISTS media;
ALTER TABLE public.staff_orders DROP COLUMN IF EXISTS problem_description;

-- 2. Update 'created_by_role' based on user roles (for each row)
-- Eslatma: Bu yerda users.id va users.role mavjud, staff_orders.user_id orqali aniqlanadi.
UPDATE public.staff_orders so
SET created_by_role = COALESCE(u.role)
FROM public.users u
WHERE u.id = so.user_id;

-- Agar users jadvalidan topilmasa, 'unknown' qilib qoldiradi.
-- If you want to make sure all created_by_role are filled, run this after:
UPDATE public.staff_orders
SET created_by_role = 'unknown'
WHERE created_by_role IS NULL OR created_by_role = '';

-- 3. staff_orders jadvalidan jm_notes ustunini olib tashlash
ALTER TABLE public.staff_orders DROP COLUMN IF EXISTS jm_notes;

-- END OF MIGRATION
