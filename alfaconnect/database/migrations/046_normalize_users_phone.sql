-- 046_normalize_users_phone.sql
-- Normalize existing phone numbers to store exactly one leading plus sign.

WITH candidates AS (
    SELECT
        id,
        btrim(phone) AS trimmed_phone,
        regexp_replace(btrim(phone), '[^0-9]', '', 'g') AS digits
    FROM users
    WHERE phone IS NOT NULL
),
normalized AS (
    SELECT
        id,
        CASE
            WHEN digits = '' THEN NULL
            WHEN length(digits) = 9 THEN '+998' || digits
            WHEN length(digits) = 12 AND digits LIKE '998%' THEN '+' || digits
            ELSE '+' || digits
        END AS normalized_phone
    FROM candidates
)
UPDATE users u
SET phone = n.normalized_phone
FROM normalized n
WHERE u.id = n.id
  AND coalesce(u.phone, '') <> coalesce(n.normalized_phone, '');

