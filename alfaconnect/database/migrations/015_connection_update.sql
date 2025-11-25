BEGIN;

-- 1) Eski FK’ni olib tashlash (nomi boshqacha bo‘lsa moslang)
ALTER TABLE connections
  DROP CONSTRAINT IF EXISTS connections_technician_id_fkey;

-- 2) Ma'lumotni tozalash:
-- technician_orders(id) da mavjud bo'lmagan technician_id larni NULL qilamiz
UPDATE connections c
SET technician_id = NULL
WHERE technician_id IS NOT NULL
  AND NOT EXISTS (
    SELECT 1
    FROM technician_orders t
    WHERE t.id = c.technician_id
  );

-- !!! E'TIBOR: staff_id dan HECH NIMA KO‘CHIRILMAYDI !!!

-- 3) Yangi FK: technician_id -> technician_orders(id)
ALTER TABLE connections
  ADD CONSTRAINT connections_technician_id_fkey
  FOREIGN KEY (technician_id)
  REFERENCES technician_orders(id)
  ON DELETE SET NULL
  ON UPDATE CASCADE;

-- 4) Indeks (agar yo'q bo'lsa)
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_indexes
    WHERE schemaname = 'public'
      AND indexname = 'idx_connections_technician_id'
  ) THEN
    CREATE INDEX idx_connections_technician_id ON connections(technician_id);
  END IF;
END $$;

COMMIT;
