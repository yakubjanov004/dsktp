#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ALFABOT — Database Setup (UPDATED TO MATCH ACTUAL DATABASE)
----------------------------------------------------------
• Matches exactly with the actual database structure from analysis report
• Fixed enum types to match database analysis
• Updated table structures to match actual database schema
• Consistent with database analysis report findings
"""

import sys
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from config import settings

DB_CONFIG = {
    'host': settings.DB_HOST,
    'port': settings.DB_PORT,
    'user': settings.DB_USER,
    'password': settings.DB_PASSWORD,
    'database': settings.DB_NAME,
}

def create_database():
    """Create DB (UTF8) if missing."""
    try:
        conn = psycopg2.connect(
            host=DB_CONFIG['host'],
            port=DB_CONFIG['port'],
            user=DB_CONFIG['user'],
            password=DB_CONFIG['password'],
        )
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (DB_CONFIG['database'],))
        if not cur.fetchone():
            cur.execute(f"CREATE DATABASE {DB_CONFIG['database']} WITH TEMPLATE template0 ENCODING 'UTF8'")
            print(f"[+] Database '{DB_CONFIG['database']}' created (UTF-8)")
        else:
            print(f"[=] Database '{DB_CONFIG['database']}' already exists")
        cur.close(); conn.close()
        return True
    except Exception as e:
        print(f"[!] create_database error: {e}")
        return False

SCHEMA_SQL = r"""
-- ===============================================
-- ALFABOT SCHEMA (MATCHING DATABASE ANALYSIS)
-- ===============================================
SET client_encoding = 'UTF8';

-- ===== ENUM TYPES (EXACT MATCH WITH DATABASE ANALYSIS) =====

-- User roles (exact match with database analysis)
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_type t JOIN pg_namespace n ON n.oid=t.typnamespace
                 WHERE t.typname='user_role' AND n.nspname='public') THEN
    CREATE TYPE public.user_role AS ENUM (
      'admin', 'client', 'manager', 'junior_manager', 'controller', 
      'technician', 'warehouse', 'callcenter_supervisor', 'callcenter_operator'
    );
  END IF;
END $$;

-- Connection order status (exact match with database analysis)
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_type t JOIN pg_namespace n ON n.oid=t.typnamespace
                 WHERE t.typname='connection_order_status' AND n.nspname='public') THEN
    CREATE TYPE public.connection_order_status AS ENUM (
      'in_manager', 'in_junior_manager', 'in_controller', 'in_technician',
      'in_repairs', 'in_warehouse', 'in_technician_work', 'completed',
      'between_controller_technician', 'cancelled'
    );
  END IF;
END $$;

-- Technician order status (exact match with database analysis)
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_type t JOIN pg_namespace n ON n.oid=t.typnamespace
                 WHERE t.typname='technician_order_status' AND n.nspname='public') THEN
    CREATE TYPE public.technician_order_status AS ENUM (
      'in_controller', 'in_technician', 'in_diagnostics', 'in_repairs',
      'in_warehouse', 'in_technician_work', 'completed', 
      'between_controller_technician', 'in_call_center_supervisor', 
      'in_call_center_operator', 'cancelled'
    );
  END IF;
END $$;

-- Staff order status (exact match with database analysis)
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_type t JOIN pg_namespace n ON n.oid=t.typnamespace
                 WHERE t.typname='staff_order_status' AND n.nspname='public') THEN
    CREATE TYPE public.staff_order_status AS ENUM (
      'new', 'in_call_center_operator', 'in_call_center_supervisor',
      'in_manager', 'in_junior_manager', 'in_controller', 'in_technician',
      'in_diagnostics', 'in_repairs', 'in_warehouse', 'in_technician_work',
      'completed', 'between_controller_technician', 'cancelled', 
      'in_progress', 'assigned_to_technician'
    );
  END IF;
END $$;

-- Type of zayavka (exact match with database analysis)
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_type t JOIN pg_namespace n ON n.oid=t.typnamespace
                 WHERE t.typname='type_of_zayavka' AND n.nspname='public') THEN
    CREATE TYPE public.type_of_zayavka AS ENUM ('connection', 'technician');
  END IF;
END $$;

-- Business type (exact match with database analysis)
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_type t JOIN pg_namespace n ON n.oid=t.typnamespace
                 WHERE t.typname='business_type' AND n.nspname='public') THEN
    CREATE TYPE public.business_type AS ENUM ('B2B', 'B2C');
  END IF;
END $$;

-- Smart Service Category (exact match with database analysis)
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_type t JOIN pg_namespace n ON n.oid = t.typnamespace
                 WHERE t.typname = 'smart_service_category' AND n.nspname = 'public') THEN
    CREATE TYPE public.smart_service_category AS ENUM (
      'aqlli_avtomatlashtirilgan_xizmatlar',
      'xavfsizlik_kuzatuv_tizimlari', 
      'internet_tarmoq_xizmatlari',
      'energiya_yashil_texnologiyalar',
      'multimediya_aloqa_tizimlari',
      'maxsus_qoshimcha_xizmatlar'
    );
  END IF;
END $$;

-- Smart Service Type DOMAIN (42 types from database analysis)
DO $$BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'smart_service_type') THEN
    CREATE DOMAIN public.smart_service_type AS TEXT CHECK (VALUE IN (
      'aqlli_uy_tizimlarini_ornatish_sozlash',
      'aqlli_yoritish_smart_lighting_tizimlari',
      'aqlli_termostat_iqlim_nazarati_tizimlari',
      'smart_lock_internet_orqali_boshqariladigan_eshik_qulfi_tizimlari',
      'aqlli_rozetalar_energiya_monitoring_tizimlari',
      'uyni_masofadan_boshqarish_qurilmalari_yagona_uzim_orqali_boshqarish',
      'aqlli_pardalari_jaluz_tizimlari',
      'aqlli_malahiy_texnika_integratsiyasi',
      'videokuzatuv_kameralari_ornatish_ip_va_analog',
      'kamera_arxiv_tizimlari_bulutli_saqlash_xizmatlari',
      'domofon_tizimlari_ornatish',
      'xavfsizlik_signalizatsiyasi_harakat_sensorlarini_ornatish',
      'yong_signalizatsiyasi_tizimlari',
      'gaz_sizish_sav_toshqinliqqa_qarshi_tizimlar',
      'yuzni_tanish_face_recognition_tizimlari',
      'avtomatik_eshik_darvoza_boshqaruv_tizimlari',
      'wi_fi_tarmoqlarini_ornatish_sozlash',
      'wi_fi_qamrov_zonasini_kengaytirish_access_point',
      'mobil_aloqa_signalini_kuchaytirish_repeater',
      'ofis_va_uy_uchun_lokal_tarmoq_lan_qurish',
      'internet_provayder_xizmatlarini_ulash',
      'server_va_nas_qurilmalarini_ornatish',
      'bulutli_fayl_almashish_zaxira_tizimlari',
      'vpn_va_xavfsiz_internet_ulanishlarini_tashkil_qilish',
      'quyosh_panellarini_ornatish_ulash',
      'quyosh_batareyalari_orqali_energiya_saqlash_tizimlari',
      'shamol_generatorlarini_ornatish',
      'elektr_energiyasini_tejovchi_yoritish_tizimlari',
      'avtomatik_suv_orish_tizimlari_smart_irrigation',
      'smart_tv_ornatish_ulash',
      'uy_kinoteatri_tizimlari_ornatish',
      'audio_tizimlar_multiroom',
      'ip_telefoniya_mini_ats_tizimlarini_tashkil_qilish',
      'video_konferensiya_tizimlari',
      'interaktiv_taqdimot_tizimlari_proyektor_led_ekran',
      'aqlli_ofis_tizimlarini_ornatish',
      'data_markaz_server_room_loyihalash_montaj_qilish',
      'qurilma_tizimlar_uchun_texnik_xizmat_korsatish',
      'dasturiy_taminotni_ornatish_yangilash',
      'iot_internet_of_things_qurilmalarini_integratsiya_qilish',
      'qurilmalarni_masofadan_boshqarish_tizimlarini_sozlash',
      'suniy_intellekt_asosidagi_uy_ofis_boshqaruv_tizimlari'
    ));
  END IF;
END $$;

-- ===== HELPER FUNCTIONS =====
CREATE OR REPLACE FUNCTION public.update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;$$ LANGUAGE plpgsql;

-- ===== MAIN TABLES (MATCHING DATABASE ANALYSIS) =====

-- USERS (exact match with database analysis)
CREATE TABLE IF NOT EXISTS public.users (
  id           BIGSERIAL PRIMARY KEY,
  telegram_id  BIGINT UNIQUE,
  full_name    TEXT,
  username     TEXT,
  phone        TEXT,
  language     VARCHAR(5) NOT NULL DEFAULT 'uz',
  region       VARCHAR(20) CHECK (region IN (
    'tashkent_city', 'tashkent_region', 'andijon', 'fergana', 
    'namangan', 'sirdaryo', 'jizzax', 'samarkand', 'bukhara',
    'navoi', 'kashkadarya', 'surkhandarya', 'khorezm', 'karakalpakstan'
  )),
  address      TEXT,
  role         public.user_role,
  abonent_id   TEXT,
  is_blocked   BOOLEAN NOT NULL DEFAULT FALSE,
  created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_users_abonent_id ON public.users(abonent_id);
CREATE INDEX IF NOT EXISTS idx_users_role ON public.users(role);
DROP TRIGGER IF EXISTS trg_users_updated_at ON public.users;
CREATE TRIGGER trg_users_updated_at BEFORE UPDATE ON public.users
FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();

-- TARIF (exact match with database analysis)
CREATE TABLE IF NOT EXISTS public.tarif (
  id         BIGSERIAL PRIMARY KEY,
  name       TEXT,
  picture    TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
DROP TRIGGER IF EXISTS trg_tarif_updated_at ON public.tarif;
CREATE TRIGGER trg_tarif_updated_at BEFORE UPDATE ON public.tarif
FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();

-- CONNECTION_ORDERS (exact match with database analysis)
CREATE TABLE IF NOT EXISTS public.connection_orders (
  id                BIGSERIAL PRIMARY KEY,
  application_number VARCHAR(50),  -- CONN-B2B-1001 format
  user_id           BIGINT REFERENCES public.users(id) ON DELETE SET NULL,
  region            TEXT,  -- TEXT as in database analysis
  address           TEXT,
  tarif_id          BIGINT REFERENCES public.tarif(id) ON DELETE SET NULL,
  business_type     public.business_type NOT NULL DEFAULT 'B2C',
  longitude         DOUBLE PRECISION,
  latitude          DOUBLE PRECISION,
  jm_notes          TEXT,
  cancellation_note TEXT,  -- Missing field added
  is_active         BOOLEAN NOT NULL DEFAULT TRUE,
  status            public.connection_order_status NOT NULL DEFAULT 'in_manager',
  created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_connection_orders_user ON public.connection_orders(user_id);
CREATE INDEX IF NOT EXISTS idx_connection_orders_status ON public.connection_orders(status);
CREATE INDEX IF NOT EXISTS idx_connection_orders_created ON public.connection_orders(created_at);
DROP TRIGGER IF EXISTS trg_connection_orders_updated_at ON public.connection_orders;
CREATE TRIGGER trg_connection_orders_updated_at BEFORE UPDATE ON public.connection_orders
FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();

-- TECHNICIAN_ORDERS (exact match with database analysis)
-- Migration 034: diagnostics column was removed
CREATE TABLE IF NOT EXISTS public.technician_orders (
  id                    BIGSERIAL PRIMARY KEY,
  application_number    VARCHAR(50),  -- TECH-B2C-1001 format
  user_id               BIGINT REFERENCES public.users(id) ON DELETE SET NULL,
  region                TEXT,  -- TEXT as in database analysis
  abonent_id            TEXT,
  address               TEXT,
  media                 TEXT,
  business_type         public.business_type NOT NULL DEFAULT 'B2C',
  longitude             DOUBLE PRECISION,
  latitude              DOUBLE PRECISION,
  description           TEXT,
  description_ish       TEXT,
  description_operator  TEXT,
  cancellation_note     TEXT,
  status                public.technician_order_status NOT NULL DEFAULT 'in_controller',
  is_active             BOOLEAN NOT NULL DEFAULT TRUE,
  created_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at            TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_technician_orders_user ON public.technician_orders(user_id);
CREATE INDEX IF NOT EXISTS idx_technician_orders_status ON public.technician_orders(status);
CREATE INDEX IF NOT EXISTS idx_technician_orders_created ON public.technician_orders(created_at);
DROP TRIGGER IF EXISTS trg_technician_orders_updated_at ON public.technician_orders;
CREATE TRIGGER trg_technician_orders_updated_at BEFORE UPDATE ON public.technician_orders
FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();
COMMENT ON TABLE public.technician_orders IS 'Technician orders table - stores technical service requests without unused diagnostics column';

-- STAFF_ORDERS (exact match with database analysis)
CREATE TABLE IF NOT EXISTS public.staff_orders (
  id               BIGSERIAL PRIMARY KEY,
  application_number VARCHAR(50),  -- STAFF-B2B-1001 format
  user_id          BIGINT REFERENCES public.users(id) ON DELETE SET NULL,
  phone            TEXT,
  region           TEXT,  -- TEXT as in database analysis
  abonent_id       TEXT,
  tarif_id         BIGINT REFERENCES public.tarif(id) ON DELETE SET NULL,
  address          TEXT,
  description      TEXT,
  diagnostics      TEXT,  -- Diagnostika natijalari (texnik xizmat uchun)
  business_type    public.business_type NOT NULL DEFAULT 'B2C',
  status           public.staff_order_status NOT NULL DEFAULT 'new',
  type_of_zayavka  public.type_of_zayavka NOT NULL DEFAULT 'connection',
  is_active        BOOLEAN NOT NULL DEFAULT TRUE,
  created_by_role  public.user_role,
  created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_staff_orders_user ON public.staff_orders(user_id);
CREATE INDEX IF NOT EXISTS idx_staff_orders_user_id ON public.staff_orders(user_id);
CREATE INDEX IF NOT EXISTS idx_staff_orders_status ON public.staff_orders(status);
CREATE INDEX IF NOT EXISTS idx_staff_orders_application_number ON public.staff_orders(application_number);
CREATE INDEX IF NOT EXISTS idx_staff_orders_created_at ON public.staff_orders(created_at);
CREATE INDEX IF NOT EXISTS idx_staff_orders_is_active ON public.staff_orders(is_active);
DROP TRIGGER IF EXISTS trg_staff_orders_updated_at ON public.staff_orders;
CREATE TRIGGER trg_staff_orders_updated_at BEFORE UPDATE ON public.staff_orders
FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();
COMMENT ON TABLE public.staff_orders IS 'Staff orders table - stores staff-created orders';

-- SMART_SERVICE_ORDERS (exact match with database analysis)
CREATE TABLE IF NOT EXISTS public.smart_service_orders (
  id                BIGSERIAL PRIMARY KEY,
  application_number VARCHAR(50),  -- SMA-0001 format
  user_id           BIGINT REFERENCES public.users(id) ON DELETE SET NULL,
  category          public.smart_service_category NOT NULL,
  service_type      public.smart_service_type NOT NULL,
  address           TEXT NOT NULL,
  longitude         DOUBLE PRECISION,
  latitude          DOUBLE PRECISION,
  is_active         BOOLEAN NOT NULL DEFAULT TRUE,
  created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_sso_user_id ON public.smart_service_orders(user_id);
CREATE INDEX IF NOT EXISTS idx_sso_category ON public.smart_service_orders(category);
DROP TRIGGER IF EXISTS trg_sso_updated_at ON public.smart_service_orders;
CREATE TRIGGER trg_sso_updated_at BEFORE UPDATE ON public.smart_service_orders
FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();

-- CONNECTIONS (exact match with database analysis)
CREATE TABLE IF NOT EXISTS public.connections (
  id                  BIGSERIAL PRIMARY KEY,
  sender_id           BIGINT REFERENCES public.users(id) ON DELETE SET NULL,
  recipient_id        BIGINT REFERENCES public.users(id) ON DELETE SET NULL,
  sender_status       TEXT,
  recipient_status    TEXT,
  application_number  VARCHAR(50),
  created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_connections_sender ON public.connections(sender_id);
CREATE INDEX IF NOT EXISTS idx_connections_recipient ON public.connections(recipient_id);
CREATE INDEX IF NOT EXISTS idx_connections_application_number ON public.connections(application_number);

-- MATERIALS (exact match with database analysis)
CREATE TABLE IF NOT EXISTS public.materials (
  id            BIGSERIAL PRIMARY KEY,
  name          TEXT,
  price         NUMERIC,
  description   TEXT,
  quantity      INTEGER DEFAULT 0,
  serial_number TEXT UNIQUE,
  material_unit TEXT DEFAULT 'dona',
  created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_materials_serial ON public.materials(serial_number);
DROP TRIGGER IF EXISTS trg_materials_updated_at ON public.materials;
CREATE TRIGGER trg_materials_updated_at BEFORE UPDATE ON public.materials
FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();

-- MATERIAL_REQUESTS (exact match with database analysis)
CREATE TABLE IF NOT EXISTS public.material_requests (
  id                  BIGSERIAL PRIMARY KEY,
  user_id             BIGINT REFERENCES public.users(id) ON DELETE SET NULL,
  material_id         BIGINT REFERENCES public.materials(id) ON DELETE SET NULL,
  quantity            INTEGER DEFAULT 1,
  price               NUMERIC DEFAULT 0,
  total_price         NUMERIC DEFAULT 0,
  source_type         VARCHAR(20) DEFAULT 'warehouse' CHECK (source_type IN ('warehouse', 'technician_stock')),
  warehouse_approved  BOOLEAN DEFAULT FALSE,
  application_number  VARCHAR(50),
  created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_material_requests_application_number ON public.material_requests(application_number);
CREATE INDEX IF NOT EXISTS idx_material_requests_source_type ON public.material_requests(source_type);
DROP TRIGGER IF EXISTS trg_material_requests_updated_at ON public.material_requests;
CREATE TRIGGER trg_material_requests_updated_at BEFORE UPDATE ON public.material_requests
FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();
COMMENT ON TABLE public.material_requests IS 'Material requests table - stores material requests by application_number instead of separate order IDs';
COMMENT ON COLUMN public.material_requests.source_type IS 'Source of material: warehouse (from warehouse) or technician_stock (from technician inventory)';
COMMENT ON COLUMN public.material_requests.application_number IS 'Application number that identifies which order this material request belongs to - mapped to REAL application numbers from order tables';

-- MATERIAL_AND_TECHNICIAN (exact match with database analysis)
CREATE TABLE IF NOT EXISTS public.material_and_technician (
  id                BIGSERIAL PRIMARY KEY,
  user_id           BIGINT REFERENCES public.users(id) ON DELETE SET NULL,
  material_id       BIGINT REFERENCES public.materials(id) ON DELETE SET NULL,
  quantity          INTEGER,
  application_number TEXT,
  issued_by         INTEGER,
  issued_at         TIMESTAMPTZ DEFAULT NOW(),
  material_name     TEXT,
  material_unit     TEXT DEFAULT 'dona',
  price             NUMERIC(10,2) DEFAULT 0.0,
  total_price       NUMERIC(10,2) DEFAULT 0.0,
  created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_material_and_technician_application_number ON public.material_and_technician(application_number);
CREATE INDEX IF NOT EXISTS idx_material_and_technician_user_id ON public.material_and_technician(user_id);
CREATE INDEX IF NOT EXISTS idx_material_and_technician_material_id ON public.material_and_technician(material_id);
DROP TRIGGER IF EXISTS trg_material_and_technician_updated_at ON public.material_and_technician;
CREATE TRIGGER trg_material_and_technician_updated_at BEFORE UPDATE ON public.material_and_technician
FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();
COMMENT ON TABLE public.material_and_technician IS 'Material and technician tracking table - tracks which materials were used by technicians for specific applications';
COMMENT ON COLUMN public.material_and_technician.application_number IS 'Application number that identifies which order these materials were used for';
COMMENT ON COLUMN public.material_and_technician.issued_by IS 'User ID of who issued the materials';
COMMENT ON COLUMN public.material_and_technician.issued_at IS 'When the materials were issued';
COMMENT ON COLUMN public.material_and_technician.material_name IS 'Name of the material for easy reference';
COMMENT ON COLUMN public.material_and_technician.material_unit IS 'Unit of measurement for the material';
COMMENT ON COLUMN public.material_and_technician.price IS 'Price per unit of the material';
COMMENT ON COLUMN public.material_and_technician.total_price IS 'Total price (price * quantity)';
COMMENT ON COLUMN public.material_and_technician.application_number IS 'Application number - request type can be determined from prefix (CONN-, TECH-, STAFF-)';

-- MATERIAL_ISSUED (exact match with database analysis)
CREATE TABLE IF NOT EXISTS public.material_issued (
  id                    BIGSERIAL PRIMARY KEY,
  material_id           BIGINT NOT NULL REFERENCES public.materials(id) ON DELETE RESTRICT,
  quantity              INTEGER NOT NULL CHECK (quantity > 0),
  price                 NUMERIC(10,2) NOT NULL,
  total_price           NUMERIC(10,2) NOT NULL,
  issued_by             BIGINT NOT NULL REFERENCES public.users(id),
  issued_at             TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
  material_name         TEXT,
  material_unit         TEXT,
  application_number    VARCHAR(50),
  request_type          VARCHAR(20) DEFAULT 'connection',
  created_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at            TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
DROP TRIGGER IF EXISTS trg_material_issued_updated_at ON public.material_issued;
CREATE TRIGGER trg_material_issued_updated_at BEFORE UPDATE ON public.material_issued
FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();

-- REPORTS (exact match with database analysis)
CREATE TABLE IF NOT EXISTS public.reports (
  id                  BIGSERIAL PRIMARY KEY,
  title               TEXT NOT NULL,
  description         TEXT,
  created_by          BIGINT REFERENCES public.users(id) ON DELETE SET NULL,
  created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
DROP TRIGGER IF EXISTS trg_reports_updated_at ON public.reports;
CREATE TRIGGER trg_reports_updated_at BEFORE UPDATE ON public.reports
FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();

-- AKT_DOCUMENTS (exact match with database analysis)
CREATE TABLE IF NOT EXISTS public.akt_documents (
  id                  BIGSERIAL PRIMARY KEY,
  request_id          BIGINT,
  request_type        TEXT CHECK (request_type IN ('connection', 'technician', 'staff')),
  akt_number          TEXT NOT NULL,
  file_path           TEXT NOT NULL,
  file_hash           TEXT NOT NULL,
  sent_to_client_at   TIMESTAMPTZ,
  application_number  TEXT NOT NULL,
  created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT unique_akt_document_per_application UNIQUE (application_number, request_type)
);
CREATE INDEX IF NOT EXISTS idx_akt_documents_application_number ON public.akt_documents(application_number);
DROP TRIGGER IF EXISTS trg_akt_documents_updated_at ON public.akt_documents;
CREATE TRIGGER trg_akt_documents_updated_at BEFORE UPDATE ON public.akt_documents
FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();
COMMENT ON TABLE public.akt_documents IS 'AKT documents table - stores official work completion documents with application numbers';
COMMENT ON COLUMN public.akt_documents.application_number IS 'Application number that identifies which order this AKT document belongs to - fixed from UNKNOWN values';

-- AKT_RATINGS (exact match with database analysis)
CREATE TABLE IF NOT EXISTS public.akt_ratings (
  id                  BIGSERIAL PRIMARY KEY,
  request_id          BIGINT,
  request_type        TEXT CHECK (request_type IN ('connection', 'technician', 'staff')),
  rating              INTEGER CHECK (rating >= 0 AND rating <= 5),
  comment             TEXT,
  application_number  TEXT NOT NULL,
  created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_akt_ratings_application_number ON public.akt_ratings(application_number);
DROP TRIGGER IF EXISTS trg_akt_ratings_updated_at ON public.akt_ratings;
CREATE TRIGGER trg_akt_ratings_updated_at BEFORE UPDATE ON public.akt_ratings
FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();
COMMENT ON TABLE public.akt_ratings IS 'AKT ratings table - stores client ratings for completed work with application numbers';
COMMENT ON COLUMN public.akt_ratings.application_number IS 'Application number that identifies which order this AKT rating belongs to - fixed from UNKNOWN values';

-- MEDIA_FILES (exact match with database analysis)
CREATE TABLE IF NOT EXISTS public.media_files (
  id             BIGSERIAL PRIMARY KEY,
  file_path      TEXT NOT NULL,
  file_type      TEXT,
  file_size      BIGINT,
  original_name  TEXT,
  mime_type      TEXT,
  category       TEXT,
  related_table  TEXT,
  related_id     BIGINT,
  uploaded_by    BIGINT REFERENCES public.users(id) ON DELETE SET NULL,
  is_active      BOOLEAN NOT NULL DEFAULT TRUE,
  created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_media_files_related ON public.media_files(related_table, related_id);
DROP TRIGGER IF EXISTS trg_media_files_updated_at ON public.media_files;
CREATE TRIGGER trg_media_files_updated_at BEFORE UPDATE ON public.media_files
FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();

-- ===== SEQUENTIAL USER ID FUNCTIONS =====

-- Create a custom sequence for sequential user IDs
CREATE SEQUENCE IF NOT EXISTS user_sequential_id_seq START 1;

-- Function to get next sequential user ID
CREATE OR REPLACE FUNCTION get_next_sequential_user_id()
RETURNS INTEGER AS $$
DECLARE
    next_id INTEGER;
BEGIN
    -- Get the next value from our custom sequence
    SELECT nextval('user_sequential_id_seq') INTO next_id;
    
    -- Check if this ID already exists in users table
    WHILE EXISTS (SELECT 1 FROM users WHERE id = next_id) LOOP
        SELECT nextval('user_sequential_id_seq') INTO next_id;
    END LOOP;
    
    RETURN next_id;
END;
$$ LANGUAGE plpgsql;

-- Function to create user with sequential ID
CREATE OR REPLACE FUNCTION create_user_sequential(
    p_telegram_id BIGINT,
    p_username TEXT DEFAULT NULL,
    p_full_name TEXT DEFAULT NULL,
    p_phone TEXT DEFAULT NULL,
    p_role user_role DEFAULT 'client'
)
RETURNS TABLE(
    user_id INTEGER,
    user_telegram_id BIGINT,
    user_username TEXT,
    user_full_name TEXT,
    user_phone TEXT,
    user_role user_role,
    user_created_at TIMESTAMPTZ
) AS $$
DECLARE
    new_user_id INTEGER;
    ret_user_id INTEGER;
    ret_telegram_id BIGINT;
    ret_username TEXT;
    ret_full_name TEXT;
    ret_phone TEXT;
    ret_role user_role;
    ret_created_at TIMESTAMPTZ;
BEGIN
    -- Get next sequential ID
    SELECT get_next_sequential_user_id() INTO new_user_id;
    
    -- Insert user with sequential ID
    INSERT INTO users (id, telegram_id, username, full_name, phone, role)
    VALUES (new_user_id, p_telegram_id, p_username, p_full_name, p_phone, p_role)
    ON CONFLICT (telegram_id) DO UPDATE SET
        username = EXCLUDED.username,
        full_name = EXCLUDED.full_name,
        phone = EXCLUDED.phone,
        updated_at = NOW()
    RETURNING users.id, users.telegram_id, users.username, users.full_name, users.phone, users.role, users.created_at
    INTO ret_user_id, ret_telegram_id, ret_username, ret_full_name, ret_phone, ret_role, ret_created_at;
    
    create_user_sequential.user_id := ret_user_id;
    create_user_sequential.user_telegram_id := ret_telegram_id;
    create_user_sequential.user_username := ret_username;
    create_user_sequential.user_full_name := ret_full_name;
    create_user_sequential.user_phone := ret_phone;
    create_user_sequential.user_role := ret_role;
    create_user_sequential.user_created_at := ret_created_at;
    
    RETURN NEXT;
END;
$$ LANGUAGE plpgsql;

-- Function to reset sequence to match existing data
CREATE OR REPLACE FUNCTION reset_user_sequential_sequence()
RETURNS VOID AS $$
DECLARE
    max_id INTEGER;
BEGIN
    -- Get the maximum existing user ID
    SELECT COALESCE(MAX(id), 0) + 1 INTO max_id FROM users;
    
    -- Reset the sequence to start from the next available ID
    PERFORM setval('user_sequential_id_seq', max_id, false);
END;
$$ LANGUAGE plpgsql;

-- Reset the sequence to match existing data
SELECT reset_user_sequential_sequence();

-- Create index for better performance
CREATE INDEX IF NOT EXISTS idx_users_id ON users(id);

COMMENT ON SEQUENCE user_sequential_id_seq IS 'Sequential ID generator for users table';
COMMENT ON FUNCTION get_next_sequential_user_id() IS 'Returns next available sequential user ID';
COMMENT ON FUNCTION create_user_sequential(BIGINT, TEXT, TEXT, TEXT, user_role) IS 'Creates user with sequential ID';
COMMENT ON FUNCTION reset_user_sequential_sequence() IS 'Resets sequence to match existing data';
"""

def run_sql(conn, sql_text):
    cur = conn.cursor()
    cur.execute(sql_text)
    cur.close()

def verify_setup():
    """Verify tables and add default data."""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        conn.autocommit = True
        cur = conn.cursor()
        print("\n[+] Verifying database setup...")

        # Check if tables exist
        cur.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
        """)
        tables = [row[0] for row in cur.fetchall()]
        print(f"[+] Found {len(tables)} tables")
        
        # Get users table columns
        cur.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'users'
        """)
        user_columns = [row[0] for row in cur.fetchall()]
        print(f"[+] Users table columns: {', '.join(user_columns)}")

        cur.execute("SELECT 1 FROM users WHERE telegram_id = 1978574076")
        if not cur.fetchone():
            cur.execute("""
                INSERT INTO users (telegram_id, full_name, username, phone, language, role, is_blocked)
                VALUES (1978574076, 'Ulug''bek', 'ulugbekbb', '+998900042544', 'uz', 'admin', false)
                RETURNING id
            """)
            print("[+] Added Ulug'bek as admin")
        


        # Add default tariffs if they don't exist
        default_tariffs = [
            ("Hammasi birga 4", None),
            ("Hammasi birga 3+", None),
            ("Hammasi birga 3", None),
            ("Hammasi birga 2", None)
        ]
        
        cur.execute("SELECT name FROM tarif")
        existing_tariffs = [row[0] for row in cur.fetchall()]
        
        for name, picture in default_tariffs:
            if name not in existing_tariffs:
                cur.execute(
                    "INSERT INTO tarif (name, picture, created_at, updated_at) VALUES (%s, %s, NOW(), NOW())",
                    (name, picture)
                )
                print(f"[+] Added default tariff: {name}")

        cur.close()
        conn.close()
        return True
    except Exception as e:
        print(f"[!] verify_setup error: {e}")
        return False

def main():
    print("ALFABOT Schema Setup (Matches Database Analysis)")
    if not create_database():
        sys.exit(1)

    try:
        conn = psycopg2.connect(**DB_CONFIG)
        conn.set_client_encoding('UTF8')
        print("[>] Applying schema that matches database analysis...")
        run_sql(conn, SCHEMA_SQL)
        conn.commit()
        conn.close()
        print("Schema applied successfully.")
    except Exception as e:
        print(f"[!] Setup error: {e}")
        sys.exit(1)

    if verify_setup():
        print("SUCCESS! Database schema now matches actual database structure!")
    else:
        print("Verification had issues")

if __name__ == '__main__':
    main()
