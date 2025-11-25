BEGIN;

-- 0) Diagnoz (ixtiyoriy): hozirgi statuslar qanday?
-- SELECT DISTINCT status FROM public.connection_orders;
-- SELECT DISTINCT status FROM public.technician_orders;

-- 1) Ma'lumotlarni xavfsiz map qilish:
-- connection_orders: ortiqcha ('new','in_diagnostics','in_repairs','in_warehouse') ni 'in_manager'ga
UPDATE public.connection_orders
SET status = 'in_manager'
WHERE status IN ('new','in_diagnostics','in_repairs','in_warehouse');

-- technician_orders: ortiqcha ('new','in_diagnostics','in_repairs','in_warehouse') ni 'in_technician'ga
UPDATE public.technician_orders
SET status = 'in_technician'
WHERE status IN ('new','in_diagnostics','in_repairs','in_warehouse');

-- 2) Agar status TEXT bo‘lsa: CHECK constraint’ni toraytirish
--   Eslatma: constraint nomlari loyihangizda boshqacha bo‘lishi mumkin – moslab almashtiring.

-- Connection Orders CHECK
ALTER TABLE public.connection_orders
  DROP CONSTRAINT IF EXISTS connection_orders_status_check,
  ADD  CONSTRAINT connection_orders_status_check
  CHECK (status IN (
    'in_manager',
    'in_junior_manager',
    'in_controller',
    'in_technician',
    'in_technician_work',
    'completed'
  ));

-- Technician Orders CHECK
ALTER TABLE public.technician_orders
  DROP CONSTRAINT IF EXISTS technician_orders_status_check,
  ADD  CONSTRAINT technician_orders_status_check
  CHECK (status IN (
    'in_controller',
    'in_technician',
    'in_technician_work',
    'completed'
  ));

COMMIT;
