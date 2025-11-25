-- Migration 001: Database Setup
-- Creates initial database structure with foreign key constraints

-- Drop existing tables if they exist (in reverse dependency order)
DROP TABLE IF EXISTS public.akt_ratings CASCADE;
DROP TABLE IF EXISTS public.akt_documents CASCADE;
DROP TABLE IF EXISTS public.reports CASCADE;
DROP TABLE IF EXISTS public.material_requests CASCADE;
DROP TABLE IF EXISTS public.material_and_technician CASCADE;
DROP TABLE IF EXISTS public.connections CASCADE;
DROP TABLE IF EXISTS public.smart_service_orders CASCADE;
DROP TABLE IF EXISTS public.staff_orders CASCADE;
DROP TABLE IF EXISTS public.technician_orders CASCADE;
DROP TABLE IF EXISTS public.connection_orders CASCADE;
DROP TABLE IF EXISTS public.materials CASCADE;
DROP TABLE IF EXISTS public.tarif CASCADE;
DROP TABLE IF EXISTS public.users CASCADE;

-- Drop sequences
DROP SEQUENCE IF EXISTS public.user_sequential_id_seq CASCADE;
DROP SEQUENCE IF EXISTS public.users_id_seq CASCADE;
DROP SEQUENCE IF EXISTS public.connection_orders_id_seq CASCADE;
DROP SEQUENCE IF EXISTS public.technician_orders_id_seq CASCADE;
DROP SEQUENCE IF EXISTS public.staff_orders_id_seq CASCADE;
DROP SEQUENCE IF EXISTS public.smart_service_orders_id_seq CASCADE;
DROP SEQUENCE IF EXISTS public.tarif_id_seq CASCADE;
DROP SEQUENCE IF EXISTS public.connections_id_seq CASCADE;
DROP SEQUENCE IF EXISTS public.materials_id_seq CASCADE;
DROP SEQUENCE IF EXISTS public.material_and_technician_id_seq CASCADE;
DROP SEQUENCE IF EXISTS public.material_requests_id_seq CASCADE;
DROP SEQUENCE IF EXISTS public.reports_id_seq CASCADE;
DROP SEQUENCE IF EXISTS public.akt_documents_id_seq CASCADE;
DROP SEQUENCE IF EXISTS public.akt_ratings_id_seq CASCADE;

-- Drop types
DROP TYPE IF EXISTS public.connection_order_status CASCADE;
DROP TYPE IF EXISTS public.smart_service_category CASCADE;
DROP TYPE IF EXISTS public.smart_service_type CASCADE;
DROP TYPE IF EXISTS public.technician_order_status CASCADE;
DROP TYPE IF EXISTS public.type_of_zayavka CASCADE;
DROP TYPE IF EXISTS public.user_role CASCADE;

-- Create ENUM Types
CREATE TYPE public.connection_order_status AS ENUM (
    'new',
    'in_manager',
    'in_junior_manager',
    'in_controller',
    'in_technician',
    'in_diagnostics',
    'in_repairs',
    'in_warehouse',
    'in_technician_work',
    'completed',
    'between_controller_technician',
    'in_call_center_supervisor'
);

CREATE TYPE public.smart_service_category AS ENUM (
    'aqlli_avtomatlashtirilgan_xizmatlar',
    'xavfsizlik_kuzatuv_tizimlari',
    'internet_tarmoq_xizmatlari',
    'energiya_yashil_texnologiyalar',
    'multimediya_aloqa_tizimlari',
    'maxsus_qoshimcha_xizmatlar'
);

CREATE DOMAIN public.smart_service_type AS text
    CONSTRAINT smart_service_type_check CHECK ((VALUE = ANY (ARRAY[
        'aqlli_uy_tizimlarini_ornatish_sozlash'::text,
        'aqlli_yoritish_smart_lighting_tizimlari'::text,
        'aqlli_termostat_iqlim_nazarati_tizimlari'::text,
        'smart_lock_internet_orqali_boshqariladigan_eshik_qulfi_tizimlari'::text,
        'aqlli_rozetalar_energiya_monitoring_tizimlari'::text,
        'uyni_masofadan_boshqarish_qurilmalari_yagona_uzim_orqali_boshqarish'::text,
        'aqlli_pardalari_jaluz_tizimlari'::text,
        'aqlli_malahiy_texnika_integratsiyasi'::text,
        'videokuzatuv_kameralarini_ornatish_ip_va_analog'::text,
        'kamera_arxiv_tizimlari_bulutli_saqlash_xizmatlari'::text,
        'domofon_tizimlari_ornatish'::text,
        'xavfsizlik_signalizatsiyasi_harakat_sensorlarini_ornatish'::text,
        'yong_signalizatsiyasi_tizimlari'::text,
        'gaz_sizish_sav_toshqinliqqa_qarshi_tizimlar'::text,
        'yuzni_tanish_face_recognition_tizimlari'::text,
        'avtomatik_eshik_darvoza_boshqaruv_tizimlari'::text,
        'wi_fi_tarmoqlarini_ornatish_sozlash'::text,
        'wi_fi_qamrov_zonasini_kengaytirish_access_point'::text,
        'mobil_aloqa_signalini_kuchaytirish_repeater'::text,
        'ofis_va_uy_uchun_lokal_tarmoq_lan_qurish'::text,
        'internet_provayder_xizmatlarini_ulash'::text,
        'server_va_nas_qurilmalarini_ornatish'::text,
        'bulutli_fayl_almashish_zaxira_tizimlari'::text,
        'vpn_va_xavfsiz_internet_ulanishlarini_tashkil_qilish'::text,
        'quyosh_panellarini_ornatish_ulash'::text,
        'quyosh_batareyalari_orqali_energiya_saqlash_tizimlari'::text,
        'shamol_generatorlarini_ornatish'::text,
        'elektr_energiyasini_tejovchi_yoritish_tizimlari'::text,
        'avtomatik_suv_orish_tizimlari_smart_irrigation'::text,
        'smart_tv_ornatish_ulash'::text,
        'uy_kinoteatri_tizimlari_ornatish'::text,
        'audio_tizimlar_multiroom'::text,
        'ip_telefoniya_mini_ats_tizimlarini_tashkil_qilish'::text,
        'video_konferensiya_tizimlari'::text,
        'interaktiv_taqdimot_tizimlari_proyektor_led_ekran'::text,
        'aqlli_ofis_tizimlarini_ornatish'::text,
        'data_markaz_server_room_loyihalash_montaj_qilish'::text,
        'qurilma_tizimlar_uchun_texnik_xizmat_korsatish'::text,
        'dasturiy_taminotni_ornatish_yangilash'::text,
        'iot_internet_of_things_qurilmalarini_integratsiya_qilish'::text,
        'qurilmalarni_masofadan_boshqarish_tizimlarini_sozlash'::text,
        'suniy_intellekt_asosidagi_uy_ofis_boshqaruv_tizimlari'::text
    ])));

CREATE TYPE public.technician_order_status AS ENUM (
    'new',
    'in_controller',
    'in_technician',
    'in_diagnostics',
    'in_repairs',
    'in_warehouse',
    'in_technician_work',
    'completed',
    'between_controller_technician',
    'in_call_center_operator'
);

CREATE TYPE public.type_of_zayavka AS ENUM (
    'connection',
    'technician'
);

CREATE TYPE public.user_role AS ENUM (
    'admin',
    'client',
    'manager',
    'junior_manager',
    'controller',
    'technician',
    'warehouse',
    'callcenter_supervisor',
    'callcenter_operator'
);

-- Create Sequences
CREATE SEQUENCE public.user_sequential_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

CREATE SEQUENCE public.users_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

CREATE SEQUENCE public.connection_orders_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

CREATE SEQUENCE public.technician_orders_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

CREATE SEQUENCE public.staff_orders_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

CREATE SEQUENCE public.smart_service_orders_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

CREATE SEQUENCE public.tarif_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

CREATE SEQUENCE public.connections_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

CREATE SEQUENCE public.materials_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

CREATE SEQUENCE public.material_and_technician_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

CREATE SEQUENCE public.material_requests_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

CREATE SEQUENCE public.reports_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

CREATE SEQUENCE public.akt_documents_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

CREATE SEQUENCE public.akt_ratings_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

-- Create Tables
CREATE TABLE public.users (
    id bigint NOT NULL DEFAULT nextval('public.users_id_seq'::regclass),
    telegram_id bigint,
    full_name text,
    username text,
    phone text,
    language character varying(5) DEFAULT 'uz'::character varying NOT NULL,
    region integer,
    address text,
    role public.user_role,
    abonent_id text,
    is_blocked boolean DEFAULT false NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);

CREATE TABLE public.tarif (
    id bigint NOT NULL DEFAULT nextval('public.tarif_id_seq'::regclass),
    name text,
    picture text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);

CREATE TABLE public.connection_orders (
    id bigint NOT NULL DEFAULT nextval('public.connection_orders_id_seq'::regclass),
    user_id bigint,
    region text,
    address text,
    tarif_id bigint,
    longitude double precision,
    latitude double precision,
    rating integer,
    notes text,
    jm_notes text,
    is_active boolean DEFAULT true NOT NULL,
    status public.connection_order_status DEFAULT 'new'::public.connection_order_status NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    controller_notes text DEFAULT ''::text NOT NULL
);