-- 047_normalize_staff_orders_region.sql
-- Normalize staff_orders.region values to canonical region codes.

WITH mapping AS (
    SELECT * FROM (VALUES
        (1,  'toshkent_city'),
        (2,  'toshkent_region'),
        (3,  'andijon'),
        (4,  'fergana'),
        (5,  'namangan'),
        (6,  'sirdaryo'),
        (7,  'jizzax'),
        (8,  'samarkand'),
        (9,  'bukhara'),
        (10, 'navoi'),
        (11, 'kashkadarya'),
        (12, 'surkhandarya'),
        (13, 'khorezm'),
        (14, 'karakalpakstan')
    ) AS m(region_id, region_code)
), normalized AS (
    SELECT
        so.id,
        lower(trim(so.region)) AS region_lower,
        CASE
            WHEN trim(so.region) ~ '^[0-9]+$'
                THEN trim(so.region)::int
            WHEN lower(trim(so.region)) ~ '^region[_\s-]*([0-9]+)$'
                THEN regexp_replace(lower(trim(so.region)), '^region[_\s-]*([0-9]+)$', '\1')::int
            ELSE NULL
        END AS region_id
    FROM staff_orders so
)
UPDATE staff_orders so
SET region = target.region_code
FROM (
    SELECT
        n.id,
        COALESCE(
            (SELECT m.region_code FROM mapping m WHERE m.region_id = n.region_id),
            CASE
                WHEN n.region_lower IN (SELECT region_code FROM mapping) THEN n.region_lower
                WHEN n.region_lower = '' THEN NULL
                ELSE n.region_lower
            END
        ) AS region_code
    FROM normalized n
) AS target
WHERE so.id = target.id
  AND (target.region_code IS DISTINCT FROM so.region);

-- Flatten technician_orders.description_ish to avoid embedded newlines and blanks
UPDATE technician_orders
SET description_ish = NULL
WHERE description_ish IS NOT NULL
  AND btrim(description_ish) = '';

UPDATE technician_orders
SET description_ish = btrim(
        regexp_replace(description_ish, E'[\r\n]+', ' ', 'g')
    )
WHERE description_ish ~ E'[\r\n]';

