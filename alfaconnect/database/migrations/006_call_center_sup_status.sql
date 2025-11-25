-- 0) Yangi enum qiymatini qo'shing (tranzaksiyasiz!)
ALTER TYPE public.connection_order_status
  ADD VALUE IF NOT EXISTS 'in_call_center_supervisor';

-- 1) Keyingi o'zgarishlarni tranzaksiya ichida qilamiz
BEGIN;

-- Eski qiymatlarni (agar bo'lsa) yangisiga ko'chirish
UPDATE public.staff_orders
SET status = 'in_call_center_supervisor'::public.connection_order_status
WHERE status IN (
  'in_manager'::public.connection_order_status,
  'in_junior_manager'::public.connection_order_status
);

-- Default qiymatni yangilash
ALTER TABLE public.staff_orders
  ALTER COLUMN status SET DEFAULT 'in_call_center_supervisor'::public.connection_order_status;

COMMIT;
