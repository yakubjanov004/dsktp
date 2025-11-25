from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import StateFilter
from aiogram.fsm.state import State, StatesGroup
from database.basic.user import find_user_by_telegram_id
from database.technician.materials import fetch_technician_materials
from loader import bot
import logging
import asyncpg
from config import settings

logger = logging.getLogger(__name__)

async def get_current_status(application_id: int, mode: str = "connection") -> str:
    """Get current status of an application"""
    from database.technician.materials import _conn
    conn = None
    try:
        conn = await _conn()
        if mode == "technician":
            query = """
                SELECT status FROM technician_orders 
                WHERE id = $1
            """
        else:  # connection mode
            query = """
                SELECT status FROM connection_orders 
                WHERE id = $1
            """
        result = await conn.fetchval(query, application_id)
        return result or "noma'lum"
    except Exception as e:
        print(f"Error getting status: {e}")
        return "noma'lum"
    finally:
        if conn:
            await conn.close()

async def get_application_number(application_id: int, mode: str = "connection") -> str:
    """Get application_number from database"""
    from database.technician.materials import _conn
    conn = None
    try:
        conn = await _conn()
        if mode == "technician":
            query = """
                SELECT application_number FROM technician_orders 
                WHERE id = $1
            """
        elif mode == "staff":
            query = """
                SELECT application_number FROM staff_orders 
                WHERE id = $1
            """
        else:  # connection mode
            query = """
                SELECT application_number FROM connection_orders 
                WHERE id = $1
            """
        result = await conn.fetchval(query, application_id)
        return result or str(application_id)
    except Exception as e:
        print(f"Error getting application_number: {e}")
        return str(application_id)
    finally:
        if conn:
            await conn.close()

from datetime import datetime
import html

from filters.role_filter import RoleFilter
from database.basic.user import get_user_by_telegram_id
from keyboards.client_buttons import get_rating_keyboard
from database.technician import (
    # Ulanish (connection_orders) oqimi
    fetch_technician_inbox,
    cancel_technician_request,
    accept_technician_work,
    start_technician_work,
    finish_technician_work,
    fetch_selected_materials_for_request,
    fetch_technician_materials,
    create_material_request_and_mark_in_warehouse,

    # Material oqimi (ikkala rejimda ham ishlatiladi)
    fetch_all_materials,
    fetch_materials_not_assigned_to_technician,
    fetch_material_by_id,
    fetch_assigned_qty,
    upsert_material_selection,
    upsert_material_request_and_decrease_stock,

    # Texnik xizmat (technician_orders) oqimi
    fetch_technician_inbox_tech,
    accept_technician_work_for_tech,
    start_technician_work_for_tech,
    save_technician_diagnosis,
    finish_technician_work_for_tech,
    
    # Xodim arizalari (staff_orders) oqimi
    fetch_technician_inbox_staff,
    accept_technician_work_for_staff,
    start_technician_work_for_staff,
    finish_technician_work_for_staff,
)

# =====================
# I18N
# =====================
T = {
    "title_inbox": {
        "uz": "👨‍🔧 <b>Texnik — Inbox</b>",
        "ru": "👨‍🔧 <b>Техник — Входящие</b>",
    },
    "id": {"uz": "🆔 <b>ID:</b>", "ru": "🆔 <b>ID:</b>"},
    "status": {"uz": "📌 <b>Status:</b>", "ru": "📌 <b>Статус:</b>"},
    "client": {"uz": "👤 <b>Mijoz:</b>", "ru": "👤 <b>Клиент:</b>"},
    "phone": {"uz": "📞 <b>Telefon:</b>", "ru": "📞 <b>Телефон:</b>"},
    "address": {"uz": "📍 <b>Manzil:</b>", "ru": "📍 <b>Адрес:</b>"},
    "tariff": {"uz": "📊 <b>Tarif:</b>", "ru": "📊 <b>Тариф:</b>"},
    "created": {"uz": "📅 <b>Yaratilgan:</b>", "ru": "📅 <b>Создано:</b>"},
    "desc": {"uz": "📝 <b>Tavsif:</b>", "ru": "📝 <b>Описание:</b>"},
    "jm_notes_label": {"uz": "📋 <b>JM izohi:</b>", "ru": "📋 <b>Примечание JM:</b>"},
    "media_yes": {"uz": "📎 <b>Media:</b> bor", "ru": "📎 <b>Медиа:</b> есть"},
    "pager": {"uz": "🗂️ <i>Ariza {i} / {n}</i>", "ru": "🗂️ <i>Заявка {i} / {n}</i>"},
    "staff_creator": {"uz": "👔 <b>Yaratuvchi:</b>", "ru": "👔 <b>Создатель:</b>"},
    "abonent": {"uz": "👤 <b>Abonent:</b>", "ru": "👤 <b>Абонент:</b>"},
    "req_type": {"uz": "📋 <b>Ariza turi:</b>", "ru": "📋 <b>Тип заявки:</b>"},
    "problem": {"uz": "⚠️ <b>Muammo:</b>", "ru": "⚠️ <b>Проблема:</b>"},
    "empty_connection": {"uz": "📭 Ulanish arizalari bo‘sh", "ru": "📭 Заявок на подключение нет"},
    "empty_tech": {"uz": "📭 Texnik xizmat arizalari bo‘sh", "ru": "📭 Заявок на техобслуживание нет"},
    "empty_staff": {"uz": "📭 Xodim arizalari bo‘sh", "ru": "📭 Заявок от сотрудников нет"},
    "choose_section": {"uz": "📂 Qaysi bo‘limni ko‘ramiz?", "ru": "📂 Какой раздел откроем?"},
    "no_perm": {"uz": "❌ Ruxsat yo‘q", "ru": "❌ Нет доступа"},
    "prev": {"uz": "⬅️ Oldingi", "ru": "⬅️ Предыдущая"},
    "next": {"uz": "Keyingi ➡️", "ru": "Следующая ➡️"},
    "cancel": {"uz": "🗑️ Bekor qilish", "ru": "🗑️ Отменить"},
    "accept": {"uz": "✅ Ishni qabul qilish", "ru": "✅ Принять работу"},
    "start": {"uz": "▶️ Ishni boshlash", "ru": "▶️ Начать работу"},
    "diagnostics": {"uz": "🩺 Diagnostika", "ru": "🩺 Диагностика"},
    "finish": {"uz": "✅ Yakunlash", "ru": "✅ Завершить"},
    "warehouse": {"uz": "📦 Ombor", "ru": "📦 Склад"},
    "review": {"uz": "📋 Yakuniy ko‘rinish", "ru": "📋 Итоговый вид"},
    "reached_start": {"uz": "❗️ Boshlanishga yetib keldingiz.", "ru": "❗️ Достигли начала списка."},
    "reached_end": {"uz": "❗️ Oxiriga yetib keldingiz.", "ru": "❗️ Достигли конца списка."},
    "ok_started": {"uz": "✅ Ish boshlandi", "ru": "✅ Работа начата"},
    "ok_cancelled": {"uz": "🗑️ Ariza bekor qilindi", "ru": "🗑️ Заявка отменена"},
    "empty_inbox": {"uz": "📭 Inbox bo‘sh", "ru": "📭 Входящие пусты"},
    "format_err": {"uz": "❌ Xato format", "ru": "❌ Неверный формат"},
    "not_found_mat": {"uz": "❌ Material topilmadi", "ru": "❌ Материал не найден"},
    "enter_qty": {"uz": "📦 <b>Miqdorni kiriting</b>", "ru": "📦 <b>Введите количество</b>"},
    "order_id": {"uz": "🆔 <b>Ariza ID:</b>", "ru": "🆔 <b>ID заявки:</b>"},
    "chosen_prod": {"uz": "📦 <b>Tanlangan mahsulot:</b>", "ru": "📦 <b>Выбранный товар:</b>"},
    "price": {"uz": "💰 <b>Narx:</b>", "ru": "💰 <b>Цена:</b>"},
    "assigned_left": {"uz": "📊 <b>Sizga biriktirilgan qoldiq:</b>", "ru": "📊 <b>Ваш закреплённый остаток:</b>"},
    "enter_qty_hint": {
        "uz": "📝 Iltimos, olinadigan miqdorni kiriting:\n• Faqat raqam (masalan: 2)\n\n<i>Maksimal: {max} dona</i>",
        "ru": "📝 Введите количество:\n• Только число (например: 2)\n\n<i>Максимум: {max} шт</i>",
    },
    "btn_cancel": {"uz": "❌ Bekor qilish", "ru": "❌ Отмена"},
    "only_int": {"uz": "❗️ Faqat butun son kiriting (masalan: 2).", "ru": "❗️ Введите целое число (например: 2)."},
    "gt_zero": {"uz": "❗️ Iltimos, 0 dan katta butun son kiriting.", "ru": "❗️ Введите целое число больше 0."},
    "max_exceeded": {
        "uz": "❗️ Sizga biriktirilgan miqdor: {max} dona. {max} dan oshiq kiritib bo‘lmaydi.",
        "ru": "❗️ Ваш лимит: {max} шт. Нельзя вводить больше {max}.",
    },
    "saved_selection": {"uz": "✅ <b>Tanlov saqlandi</b>", "ru": "✅ <b>Выбор сохранён</b>"},
    "selected_products": {"uz": "📦 <b>Tanlangan mahsulotlar:</b>", "ru": "📦 <b>Выбранные материалы:</b>"},
    "add_more": {"uz": "➕ Yana material tanlash", "ru": "➕ Добавить ещё материал"},
    "final_view": {"uz": "📋 Yakuniy ko‘rinish", "ru": "📋 Итоговый вид"},
    "store_header": {
        "uz": "📦 <b>Ombor jihozlari</b>\n🆔 <b>Ariza ID:</b> {id}\nKerakli jihozlarni tanlang yoki boshqa mahsulot kiriting:",
        "ru": "📦 <b>Складские позиции</b>\n🆔 <b>ID заявки:</b> {id}\nВыберите нужное или введите другой товар:",
    },
    "diag_begin_prompt": {
        "uz": "🩺 <b>Diagnostika matnini kiriting</b>\n\nMasalan: <i>Modem moslamasi ishdan chiqqan</i>.",
        "ru": "🩺 <b>Введите текст диагностики</b>\n\nНапример: <i>Неисправен модем</i>.",
    },
    "diag_saved": {"uz": "✅ <b>Diagnostika qo‘yildi!</b>", "ru": "✅ <b>Диагностика сохранена!</b>"},
    "diag_text": {"uz": "🧰 <b>Diagnostika:</b>", "ru": "🧰 <b>Диагностика:</b>"},
    "go_store_q": {
        "uz": "🧑‍🏭 <b>Ombor bilan ishlaysizmi?</b>\n<i>Agar kerakli jihozlar omborda bo‘lsa, ularni olish kerak.</i>",
        "ru": "🧑‍🏭 <b>Перейти к складу?</b>\n<i>Если нужны материалы — забираем со склада.</i>",
    },
    "yes": {"uz": "✅ Ha", "ru": "✅ Да"},
    "no": {"uz": "❌ Yo‘q", "ru": "❌ Нет"},
    "diag_cancelled": {"uz": "ℹ️ Omborga murojaat qilinmadi. Davom etishingiz mumkin.", "ru": "ℹ️ К складу не обращались. Можно продолжать."},
    "catalog_empty": {"uz": "📦 Katalog bo‘sh.", "ru": "📦 Каталог пуст."},
    "catalog_header": {"uz": "📦 <b>Mahsulot katalogi</b>\nKeraklisini tanlang:", "ru": "📦 <b>Каталог материалов</b>\nВыберите нужное:"},
    "back": {"uz": "⬅️ Orqaga", "ru": "⬅️ Назад"},
    "qty_title": {"uz": "✍️ <b>Miqdorni kiriting</b>", "ru": "✍️ <b>Введите количество</b>"},
    "order": {"uz": "🆔 Ariza:", "ru": "🆔 Заявка:"},
    "product": {"uz": "📦 Mahsulot:", "ru": "📦 Материал:"},
    "price_line": {"uz": "💰 Narx:", "ru": "💰 Цена:"},
    "ctx_lost": {"uz": "❗️ Kontekst yo‘qolgan, qaytadan urinib ko‘ring.", "ru": "❗️ Контекст потерян, попробуйте снова."},
    "req_not_found": {"uz": "❗️ Ariza aniqlanmadi.", "ru": "❗️ Заявка не найдена."},
    "x_error": {"uz": "❌ Xatolik:", "ru": "❌ Ошибка:"},
    "state_cleared": {"uz": "Bekor qilindi", "ru": "Отменено"},
    "status_mismatch": {"uz": "⚠️ Holat mos emas", "ru": "⚠️ Некорректный статус"},
    "status_mismatch_detail": {
        "uz": "⚠️ Holat mos emas (faqat 'in_technician').",
        "ru": "⚠️ Некорректный статус (только 'in_technician').",
    },
    "status_mismatch_finish": {
        "uz": "⚠️ Holat mos emas (faqat 'in_technician_work').",
        "ru": "⚠️ Некорректный статус (только 'in_technician_work').",
    },
    "work_finished": {"uz": "✅ <b>Ish yakunlandi</b>", "ru": "✅ <b>Работа завершена</b>"},
    "used_materials": {"uz": "📦 <b>Ishlatilgan mahsulotlar:</b>", "ru": "📦 <b>Использованные материалы:</b>"},
    "none": {"uz": "• (mahsulot tanlanmadi)", "ru": "• (материалы не выбраны)"},
    "akt_err_ignored": {"uz": "AKT xatoligi ishni to'xtatmaydi", "ru": "Ошибка АКТ не останавливает процесс"},
    "store_request_sent": {
        "uz": "📨 <b>Omborga so‘rov yuborildi</b>",
        "ru": "📨 <b>Заявка на склад отправлена</b>",
    },
    "req_type_info": {
        "uz": "✅ Omborga so'rov yuborildi. Omborchi tasdiqlagach materiallar sizga yetib keladi. Ishni davom ettirishingiz mumkin.",
        "ru": "✅ Запрос отправлен на склад. После подтверждения материалы будут доставлены. Можете продолжить работу.",
    },
    "sections_keyboard": {
        "uz": ["🔌 Ulanish arizalari", "🔧 Texnik xizmat arizalari", "📞 Operator arizalari"],
        "ru": ["🔌 Заявки на подключение", "🔧 Заявки на техобслуживание", "📞 Заявки от операторов"],
    },
    "cancel_order": {"uz": "🗑️ Arizani bekor qilish", "ru": "🗑️ Отменить заявку"},
    "cancel_reason_prompt": {
        "uz": "📝 <b>Bekor qilish sababini kiriting:</b>\n\nMasalan: <i>Mijoz rad etdi</i>",
        "ru": "📝 <b>Введите причину отмены:</b>\n\nНапример: <i>Клиент отказался</i>",
    },
    "cancel_success": {"uz": "✅ Ariza bekor qilindi", "ru": "✅ Заявка отменена"},
}

def t(key: str, lang: str = "uz", **kwargs) -> str:
    val = T.get(key, {}).get(lang, "")
    return val.format(**kwargs) if kwargs else val

async def resolve_lang(user_id: int, fallback: str = "uz") -> str:
    """Foydalanuvchi tilini DB'dan olish: users.lang ('uz'|'ru') bo‘lsa ishlatiladi."""
    try:
        u = await find_user_by_telegram_id(user_id)
        if u:
            lang = (u.get("lang") or u.get("user_lang") or u.get("language") or "").lower()
            if lang in ("uz", "ru"):
                return lang
    except Exception:
        pass
    return fallback

# ====== STATE-lar ======
class QtyStates(StatesGroup):
    waiting_qty = State()
class CustomQtyStates(StatesGroup):
    waiting_qty = State()
class DiagStates(StatesGroup):
    waiting_text = State()
class CancellationStates(StatesGroup):
    waiting_note = State()

# ====== Router ======
router = Router()
router.message.filter(RoleFilter("technician"))
router.callback_query.filter(RoleFilter("technician"))

# =====================
# Helperlar
# =====================
def _preserve_mode_clear(state: FSMContext, keep_keys: list[str] | None = None):
    async def _inner():
        data = await state.get_data()
        mode = data.get("tech_mode")
        lang = data.get("lang")
        inbox = data.get("tech_inbox")
        idx = data.get("tech_idx")
        current_application_id = data.get("current_application_id")
        
        kept: dict = {}
        if keep_keys:
            for k in keep_keys:
                if k in data:
                    kept[k] = data[k]
        
        await state.clear()
        payload = {
            "tech_mode": mode,
            "lang": lang,
            "tech_inbox": inbox,
            "tech_idx": idx,
            "current_application_id": current_application_id
        }
        payload.update(kept)
        await state.update_data(**payload)
    return _inner()

def fmt_dt(dt) -> str:
    if isinstance(dt, str):
        try:
            dt = datetime.fromisoformat(dt)
        except Exception:
            return html.escape(dt, quote=False)
    if isinstance(dt, datetime):
        return dt.strftime("%d.%m.%Y %H:%M")
    return "-"

def esc(v) -> str:
    return "-" if v is None else html.escape(str(v), quote=False)

def _qty_of(it: dict) -> str:
    q = it.get('qty')
    if q is None:
        q = it.get('quantity', it.get('description'))
    return str(q) if q is not None else "-"

def status_emoji(s: str) -> str:
    m = {
        "between_controller_technician": "🆕",
        "in_technician": "🧰",
        "in_technician_work": "🟢",
        "in_warehouse": "📦",
        "completed": "✅",
    }
    return m.get(s, "📌")

def short_view_text(item: dict, idx: int, total: int, lang: str = "uz", mode: str = "connection") -> str:
    """Build ariza text based on mode"""
    
    # Staff arizalari uchun alohida text
    if mode == "staff":
        base = f"{t('title_inbox', lang)}\n"
        base += f"{t('id', lang)} {esc(item.get('application_number') or item.get('id'))}\n"
        
        # Ariza turi
        req_type = item.get('type_of_zayavka', '-')
        req_type_uz = "Ulanish" if req_type == "connection" else ("Texnik xizmat" if req_type == "technician" else req_type)
        req_type_ru = "Подключение" if req_type == "connection" else ("Техобслуживание" if req_type == "technician" else req_type)
        base += f"{t('req_type', lang)} {req_type_uz if lang=='uz' else req_type_ru}\n\n"
        
        # Abonent (mijoz) ma'lumotlari
        base += f"{t('abonent', lang)}\n"
        base += f"  • {esc(item.get('client_name'))}\n"
        base += f"  • {esc(item.get('client_phone'))}\n\n"
        
        # Yaratuvchi xodim
        base += f"{t('staff_creator', lang)}\n"
        creator_role = item.get('staff_creator_role', '-')
        base += f"  • {esc(item.get('staff_creator_name'))} ({esc(creator_role)})\n"
        base += f"  • {esc(item.get('staff_creator_phone'))}\n\n"
        
        # Manzil
        base += f"{t('address', lang)} {esc(item.get('address'))}\n"
        
        # Tariff yoki muammo
        tariff_or_problem = item.get('tariff_or_problem')
        if tariff_or_problem:
            if req_type == 'connection':
                base += f"{t('tariff', lang)} {esc(tariff_or_problem)}\n"
            else:
                base += f"{t('problem', lang)} {esc(tariff_or_problem)}\n"
        
        # Tavsif
        desc = (item.get("description") or "").strip()
        if desc:
            short_desc = (desc[:140] + "…") if len(desc) > 140 else desc
            base += f"{t('desc', lang)} {html.escape(short_desc, quote=False)}\n"
        
        # JM notes
        jm_notes = (item.get("jm_notes") or "").strip()
        if jm_notes:
            short_notes = (jm_notes[:100] + "…") if len(jm_notes) > 100 else jm_notes
            base += f"{t('jm_notes_label', lang)} {html.escape(short_notes, quote=False)}\n"
        
        # Diagnostika (agar mavjud bo'lsa)
        diagnostics = (item.get("diagnostics") or "").strip()
        if diagnostics:
            short_diag = (diagnostics[:100] + "…") if len(diagnostics) > 100 else diagnostics
            base += f"🔍 <b>Diagnostika:</b> {html.escape(short_diag, quote=False)}\n"
        
        if item.get("created_at"):
            base += f"{t('created', lang)} {fmt_dt(item.get('created_at'))}\n"
        
        base += "\n" + t("pager", lang, i=idx + 1, n=total)
        return base
    
    # Technician arizalari uchun alohida text
    elif mode == "technician":
        base = f"{t('title_inbox', lang)}\n"
        base += f"{t('id', lang)} {esc(item.get('application_number') or item.get('id'))}\n"
        
        # Texnik xizmat arizasi
        base += f"{t('req_type', lang)} {'Texnik xizmat' if lang=='uz' else 'Техобслуживание'}\n\n"
        
        # Mijoz ma'lumotlari
        base += f"{t('client', lang)} {esc(item.get('client_name'))}\n"
        base += f"{t('phone', lang)} {esc(item.get('client_phone'))}\n"
        base += f"{t('address', lang)} {esc(item.get('address'))}\n"
        
        # Muammo tavsifi
        problem_desc = (item.get("description") or "").strip()
        if problem_desc:
            short_problem = (problem_desc[:140] + "…") if len(problem_desc) > 140 else problem_desc
            base += f"{t('problem', lang)} {html.escape(short_problem, quote=False)}\n"
        
        # Media fayllar
        if item.get("media"):
            base += f"{t('media_yes', lang)}\n"
        
        # Diagnostika (agar mavjud bo'lsa)
        diagnostics = (item.get("diagnostics") or "").strip()
        if diagnostics:
            short_diag = (diagnostics[:100] + "…") if len(diagnostics) > 100 else diagnostics
            base += f"🔍 <b>Diagnostika:</b> {html.escape(short_diag, quote=False)}\n"
        
        if item.get("created_at"):
            base += f"{t('created', lang)} {fmt_dt(item.get('created_at'))}\n"
        
        base += "\n" + t("pager", lang, i=idx + 1, n=total)
        return base
    
    # Connection arizalari uchun
    else:  # mode == "connection"
        base = f"{t('title_inbox', lang)}\n"
        base += f"{t('id', lang)} {esc(item.get('application_number') or item.get('id'))}\n"
        
        # Ulanish arizasi
        base += f"{t('req_type', lang)} {'Ulanish' if lang=='uz' else 'Подключение'}\n\n"
        
        # Mijoz ma'lumotlari
        base += f"{t('client', lang)} {esc(item.get('client_name'))}\n"
        base += f"{t('phone', lang)} {esc(item.get('client_phone'))}\n"
        base += f"{t('address', lang)} {esc(item.get('address'))}\n"
        
        if item.get("tariff"):
            base += f"{t('tariff', lang)} {esc(item.get('tariff'))}\n"
        
        # JM notes (faqat connection uchun)
        jm_notes = (item.get("jm_notes") or "").strip()
        if jm_notes:
            short_notes = (jm_notes[:100] + "…") if len(jm_notes) > 100 else jm_notes
            base += f"{t('jm_notes_label', lang)} {html.escape(short_notes, quote=False)}\n"
        
        if item.get("created_at"):
            base += f"{t('created', lang)} {fmt_dt(item.get('created_at'))}\n"
        
        desc = (item.get("description") or "").strip()
        if desc:
            short_desc = (desc[:140] + "…") if len(desc) > 140 else desc
            base += f"{t('desc', lang)} {html.escape(short_desc, quote=False)}\n"
        
        base += "\n" + t("pager", lang, i=idx + 1, n=total)
        return base

async def get_selected_materials_summary(user_id: int, application_number: str, lang: str) -> str:
    """Get summary of selected materials for display in inbox"""
    try:
        selected = await fetch_selected_materials_for_request(user_id, application_number)
        if not selected:
            return ""
        
        summary = "\n\n📦 <b>Tanlangan mahsulotlar:</b>\n"
        for mat in selected:
            qty = mat['qty']
            name = mat['name']
            source = "🧑‍🔧 O'zimda" if mat.get('source_type') == 'technician_stock' else "🏢 Ombordan"
            summary += f"• {esc(name)} — {qty} dona [{source}]\n"
        return summary
    except Exception:
        return ""

async def short_view_text_with_materials(item: dict, idx: int, total: int, user_id: int, lang: str = "uz", mode: str = "connection") -> str:
    """Build ariza text with selected materials included"""
    base_text = short_view_text(item, idx, total, lang, mode)
    
    req_id = item.get("id")
    if req_id:
        app_number = await get_application_number(req_id, mode)
        materials_summary = await get_selected_materials_summary(user_id, app_number, lang)
        if materials_summary:
            # Insert materials before pager
            pager_start = base_text.rfind(t("pager", lang, i=idx + 1, n=total))
            if pager_start != -1:
                base_text = base_text[:pager_start] + materials_summary + "\n" + base_text[pager_start:]
            else:
                base_text += materials_summary
    
    return base_text

def _short(s: str, n: int = 48) -> str:
    s = str(s)
    return s if len(s) <= n else s[: n - 1] + "…"

def _fmt_price_uzs(val) -> str:
    try:
        s = f"{int(val):,}"
        return s.replace(",", " ")
    except Exception:
        return str(val)

async def send_completion_notification_to_client(bot, request_id: int, request_type: str):
    """
    Texnik ishni yakunlagandan so'ng clientga ariza haqida to'liq ma'lumot yuborish va rating so'rash.
    AKT yuborilmaydi - faqat ma'lumot va rating tizimi.
    """
    try:
        # Client ma'lumotlarini olish
        client_data = await get_client_data_for_notification(request_id, request_type)
        if not client_data or not client_data.get('client_telegram_id'):
            logger.warning(f"No client data found for {request_type} request {request_id}")
            return

        client_telegram_id = client_data['client_telegram_id']
        client_lang = client_data.get('client_lang', 'uz')
        
        # Ariza turini til bo'yicha formatlash
        if client_lang == "ru":
            if request_type == "connection":
                order_type_text = "подключения"
            elif request_type == "technician":
                order_type_text = "технической"
            else:
                order_type_text = "сотрудника"
        else:
            if request_type == "connection":
                order_type_text = "ulanish"
            elif request_type == "technician":
                order_type_text = "texnik xizmat"
            else:
                order_type_text = "xodim"

        # Ishlatilgan materiallarni olish
        materials_info = await get_used_materials_info(request_id, request_type, client_lang)
        
        # Diagnostika ma'lumotini olish (texnik xizmat uchun)
        diagnosis_info = await get_diagnosis_info(request_id, request_type, client_lang)

        # Notification matnini tayyorlash
        if client_lang == "ru":
            message = (
                "✅ <b>Работа завершена!</b>\n\n"
                f"📋 Заявка {order_type_text}: #{request_id}\n"
                f"📅 Дата завершения: {datetime.now().strftime('%d.%m.%Y %H:%M')}\n\n"
            )
            
            if diagnosis_info:
                message += f"🔧 <b>Выполненные работы:</b>\n{diagnosis_info}\n\n"
            
            if materials_info:
                message += f"📦 <b>Использованные материалы:</b>\n{materials_info}\n\n"
            
            message += "<i>Пожалуйста, оцените качество нашей работы:</i>"
        else:
            message = (
                "✅ <b>Ish yakunlandi!</b>\n\n"
                f"📋 {order_type_text} arizasi: #{request_id}\n"
                f"📅 Yakunlangan sana: {datetime.now().strftime('%d.%m.%Y %H:%M')}\n\n"
            )
            
            if diagnosis_info:
                message += f"🔧 <b>Bajarilgan ishlar:</b>\n{diagnosis_info}\n\n"
            
            if materials_info:
                message += f"📦 <b>Ishlatilgan materiallar:</b>\n{materials_info}\n\n"
            
            message += "<i>Iltimos, xizmatimizni baholang:</i>"

        # Rating keyboard yaratish
        rating_keyboard = get_rating_keyboard(request_id, request_type)
        
        # Xabarni yuborish
        await bot.send_message(
            chat_id=client_telegram_id,
            text=message,
            parse_mode='HTML',
            reply_markup=rating_keyboard
        )
        
        logger.info(f"Completion notification sent to client {client_telegram_id} for {request_type} request {request_id}")
        
    except Exception as e:
        logger.error(f"Error sending completion notification to client: {e}")
        raise

async def get_client_data_for_notification(request_id: int, request_type: str):
    """
    Client ma'lumotlarini olish notification uchun.
    """
    from database.connections import get_connection_url
    import asyncpg
    
    try:
        conn = await asyncpg.connect(get_connection_url())
        try:
            if request_type == "connection":
                query = """
                    SELECT 
                        u.telegram_id as client_telegram_id,
                        u.lang as client_lang,
                        u.full_name as client_name,
                        u.phone as client_phone,
                        co.address
                    FROM connection_orders co
                    LEFT JOIN users u ON u.id = co.user_id
                    WHERE co.id = $1
                """
            elif request_type == "technician":
                query = """
                    SELECT 
                        u.telegram_id as client_telegram_id,
                        u.lang as client_lang,
                        u.full_name as client_name,
                        u.phone as client_phone,
                        to.address
                    FROM technician_orders to
                    LEFT JOIN users u ON u.id = to.user_id
                    WHERE to.id = $1
                """
            elif request_type == "staff":
                query = """
                    SELECT 
                        u.telegram_id as client_telegram_id,
                        u.lang as client_lang,
                        u.full_name as client_name,
                        u.phone as client_phone,
                        so.address
                    FROM staff_orders so
                    LEFT JOIN users u ON u.id::text = so.abonent_id
                    WHERE so.id = $1
                """
            else:
                return None
                
            result = await conn.fetchrow(query, request_id)
            return dict(result) if result else None
            
        finally:
            await conn.close()
    except Exception as e:
        logger.error(f"Error getting client data: {e}")
        return None

async def get_used_materials_info(request_id: int, request_type: str, client_lang: str = "uz"):
    """
    Ishlatilgan materiallar haqida ma'lumot olish.
    """
    try:
        from database.connections import get_connection_url
        import asyncpg
        
        conn = await asyncpg.connect(get_connection_url())
        try:
            # Get application_number from the order tables
            app_number_query = """
                SELECT application_number FROM technician_orders WHERE id = $1
                UNION ALL
                SELECT application_number FROM connection_orders WHERE id = $1
                UNION ALL
                SELECT application_number FROM staff_orders WHERE id = $1
                LIMIT 1
            """
            app_number_result = await conn.fetchrow(app_number_query, request_id)
            if not app_number_result:
                return "• Hech qanday material ishlatilmagan" if client_lang == "uz" else "• Материалы не использовались"
            
            application_number = app_number_result['application_number']
            
            # Now get materials using application_number
            query = """
                SELECT 
                    m.name as material_name,
                    mr.quantity,
                    mr.price
                FROM material_requests mr
                JOIN materials m ON m.id = mr.material_id
                WHERE mr.application_number = $1
                ORDER BY mr.created_at
            """
                
            materials = await conn.fetch(query, application_number)
            
            if not materials:
                return "• Hech qanday material ishlatilmagan" if client_lang == "uz" else "• Материалы не использовались"
            
            materials_text = []
            for mat in materials:
                name = mat['material_name'] or "Noma'lum"
                qty = mat['quantity'] or 0
                price = mat['price'] or 0
                total_price = qty * price
                
                if client_lang == "ru":
                    materials_text.append(f"• {name} — {qty} шт. (💰 {_fmt_price_uzs(total_price)} сум)")
                else:
                    materials_text.append(f"• {name} — {qty} dona (💰 {_fmt_price_uzs(total_price)} so'm)")
            
            return "\n".join(materials_text)
            
        finally:
            await conn.close()
    except Exception as e:
        logger.error(f"Error getting materials info: {e}")
        return ""

async def get_diagnosis_info(request_id: int, request_type: str, client_lang: str = "uz"):
    """
    Diagnostika ma'lumotini olish (faqat texnik xizmat uchun).
    """
    try:
        if request_type != "technician":
            return ""
            
        from database.connections import get_connection_url
        import asyncpg
        
        conn = await asyncpg.connect(get_connection_url())
        try:
            query = """
                SELECT description
                FROM technician_orders
                WHERE id = $1 AND description IS NOT NULL
            """
            
            result = await conn.fetchval(query, request_id)
            
            if not result:
                return ""
            
            # Diagnostika matnini qisqartirish
            diagnosis = result.strip()
            if len(diagnosis) > 200:
                diagnosis = diagnosis[:200] + "..."
            
            return diagnosis
            
        finally:
            await conn.close()
    except Exception as e:
        logger.error(f"Error getting diagnosis info: {e}")
        return ""

def materials_keyboard(materials: list[dict], applications_id: int, lang: str = "uz") -> InlineKeyboardMarkup:
    rows = []
    if materials:
        for mat in materials:
            name = _short(mat.get('name', 'NO NAME'))
            price = _fmt_price_uzs(mat.get('price', 0))
            stock = mat.get('stock_quantity', '0')
            title = f"📦 {name} — {price} so'm ({stock} dona)" if lang == "uz" else f"📦 {name} — {price} сум ({stock} шт)"
            rows.append([InlineKeyboardButton(
                text=title[:64],
                callback_data=f"tech_mat_select_{mat.get('material_id')}_{applications_id}"
            )])
    rows.append([InlineKeyboardButton(text=("➕ Boshqa mahsulot" if lang == "uz" else "➕ Другой материал"),
                                      callback_data=f"tech_mat_custom_{applications_id}")])
    # Add "Orqaga" button
    rows.append([InlineKeyboardButton(text=t("back", lang), callback_data=f"tech_back_to_order_{applications_id}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def unassigned_materials_keyboard(materials: list[dict], applications_id: int, lang: str = "uz") -> InlineKeyboardMarkup:
    """Texnikka biriktirilmagan materiallar uchun keyboard"""
    rows = []
    if materials:
        for mat in materials:
            name = _short(mat.get('name', 'NO NAME'))
            price = _fmt_price_uzs(mat.get('price', 0))
            stock = mat.get('stock_quantity', '0')
            title = f"📦 {name} — {price} so'm ({stock} dona)" if lang == "uz" else f"📦 {name} — {price} сум ({stock} шт)"
            rows.append([InlineKeyboardButton(
                text=title[:64],
                callback_data=f"tech_unassigned_select_{mat.get('material_id')}_{applications_id}"
            )])
    rows.append([InlineKeyboardButton(text=t("back", lang), callback_data=f"tech_back_to_order_{applications_id}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

async def action_keyboard(item_id: int, index: int, total: int, status: str, mode: str = "connection", lang: str = "uz", item: dict = None) -> InlineKeyboardMarkup:
    """
    Statusga qarab to'g'ri inline tugmalarni ko'rsatadi.
    
    Status: between_controller_technician -> [Bekor qilish] [Qabul qilish]
    Status: in_technician -> [Ishni boshlash]
    Status: in_technician_work -> 
        - Technician mode yoki staff(technician): faqat diagnostika borligini tekshirib, keyin [Ombor] [Yakuniy ko'rinish]
        - Connection mode yoki staff(connection): [Ombor] [Yakuniy ko'rinish]
    """
    rows: list[list[InlineKeyboardButton]] = []
    
    # Paginatsiya (agar bir nechta ariza bo'lsa)
    if total > 1:
        nav = []
        if index > 0:
            nav.append(InlineKeyboardButton(text=t("prev", lang), callback_data=f"tech_inbox_prev_{index}"))
        if index < total - 1:
            nav.append(InlineKeyboardButton(text=t("next", lang), callback_data=f"tech_inbox_next_{index}"))
        if nav:
            rows.append(nav)
    
    # Statusga qarab amal tugmalari
    if status == "between_controller_technician":
        # Faqat accept tugmasi ko'rsatiladi, cancel tugmasi faqat yakuniy ko'rinishda
        rows.append([
            InlineKeyboardButton(text=t("accept", lang), callback_data=f"tech_accept_{item_id}"),
        ])
    
    elif status == "in_technician":
        rows.append([InlineKeyboardButton(text=t("start", lang), callback_data=f"tech_start_{item_id}")])
    
    elif status == "in_technician_work":
        # Diagnostika tugmasi (faqat technician va staff uchun)
        if mode == "technician" or (mode == "staff" and item and item.get("type_of_zayavka") == "technician"):
            # Diagnostika mavjudligini tekshirish
            has_diagnostics = False
            if item:
                diagnostics = item.get("diagnostics")
                # Diagnostika mavjud va bo'sh emasligini tekshirish
                has_diagnostics = bool(diagnostics and str(diagnostics).strip())
            
            if not has_diagnostics:
                # Diagnostika qo'shilmagan bo'lsa, diagnostika tugmasi ko'rsatish
                rows.append([InlineKeyboardButton(text=t("diagnostics", lang), callback_data=f"tech_diag_{item_id}")])
            else:
                # Diagnostika qo'shilgan bo'lsa, ombor va yakuniy ko'rinish
                rows.append([
                    InlineKeyboardButton(text=t("warehouse", lang), callback_data=f"tech_add_more_{item_id}"),
                    InlineKeyboardButton(text=t("review", lang), callback_data=f"tech_review_{item_id}"),
                ])
        else:
            # Connection mode yoki staff(connection) uchun to'g'ridan-to'g'ri ombor va yakuniy ko'rinish
            rows.append([
                InlineKeyboardButton(text=t("warehouse", lang), callback_data=f"tech_add_more_{item_id}"),
                InlineKeyboardButton(text=t("review", lang), callback_data=f"tech_review_{item_id}"),
            ])
    
    return InlineKeyboardMarkup(inline_keyboard=rows)

def _dedup_by_id(items: list[dict]) -> list[dict]:
    seen = set(); out = []
    for it in items:
        i = it.get("id")
        if i in seen: continue
        seen.add(i); out.append(it)
    return out

def tech_category_keyboard(lang: str = "uz") -> InlineKeyboardMarkup:
    a, b, c = T["sections_keyboard"][lang]
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=a, callback_data="tech_inbox_cat_connection")],
        [InlineKeyboardButton(text=b, callback_data="tech_inbox_cat_tech")],
        [InlineKeyboardButton(text=c, callback_data="tech_inbox_cat_operator")],
    ])

async def purge_tracked_messages(state: FSMContext, chat_id: int):
    """Delete or clear markup from all tracked interactive messages"""
    st = await state.get_data()
    msg_ids = st.get("active_msg_ids", [])
    for msg_id in msg_ids:
        try:
            await bot.delete_message(chat_id, msg_id)
        except:
            try:
                await bot.edit_message_reply_markup(chat_id, msg_id, reply_markup=None)
            except:
                pass
    await state.update_data(active_msg_ids=[])

async def track_message(state: FSMContext, message_id: int):
    """Add message ID to tracking list"""
    st = await state.get_data()
    msg_ids = st.get("active_msg_ids", [])
    msg_ids.append(message_id)
    await state.update_data(active_msg_ids=msg_ids)

async def clear_temp_contexts(state: FSMContext):
    """Clear temporary contexts while preserving persistent fields"""
    st = await state.get_data()
    await state.update_data(
        qty_ctx=None,
        custom_ctx=None,
        unassigned_ctx=None,
        diag_ctx=None,
        active_msg_ids=[]
    )

async def render_item(message, item: dict, idx: int, total: int, lang: str, mode: str, user_id: int = None, state: FSMContext = None):
    """Arizani rasm bilan yoki rasmsiz ko'rsatish"""
    if user_id:
        text = await short_view_text_with_materials(item, idx, total, user_id, lang, mode)
    else:
        text = short_view_text(item, idx, total, lang, mode)
    kb = await action_keyboard(item.get("id"), idx, total, item.get("status", ""), mode=mode, lang=lang, item=item)
    
    media_file_id = item.get("media_file_id")
    media_type = item.get("media_type")
    
    # Detect actual media type from file_id if database type is incorrect
    def detect_media_type_from_file_id(file_id: str) -> str:
        """Detect media type from Telegram file ID prefix"""
        if not file_id:
            return None
        
        # Telegram file ID prefixes for different media types
        if file_id.startswith('BAADBAAD'):  # Video note
            return 'video'
        elif file_id.startswith('BAACAgI'):  # Video
            return 'video'
        elif file_id.startswith('BAAgAgI'):  # Video
            return 'video'
        elif file_id.startswith('AgACAgI'):  # Photo
            return 'photo'
        elif file_id.startswith('CAAQAgI'):  # Photo
            return 'photo'
        # Check for file extensions in local files
        elif file_id.lower().endswith(('.mp4', '.avi', '.mov', '.mkv', '.webm')):
            return 'video'
        elif file_id.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp')):
            return 'photo'
        else:
            # If we can't determine from file ID, return None to use original media_type
            return None
    
    # Use detected media type instead of database value
    detected_type = detect_media_type_from_file_id(media_file_id) if media_file_id else None
    actual_media_type = detected_type if detected_type else media_type
    
    try:
        # Eski xabarni o'chirish (inline tugmalar qolmasligi uchun)
        try:
            await message.delete()
        except:
            pass
        
        # Yangi xabar yuborish
        sent_msg = None
        if media_file_id and media_file_id.strip():
            if actual_media_type == 'video':
                try:
                    sent_msg = await bot.send_video(
                        chat_id=message.chat.id,
                        video=media_file_id,
                        caption=text,
                        parse_mode='HTML',
                        reply_markup=kb
                    )
                except Exception as e:
                    logger.error(f"Video send failed, retrying as photo: {e}")
                    try:
                        sent_msg = await bot.send_photo(
                            chat_id=message.chat.id,
                            photo=media_file_id,
                            caption=text,
                            parse_mode='HTML',
                            reply_markup=kb
                        )
                    except Exception as e2:
                        logger.error(f"Photo send also failed: {e2}")
                        sent_msg = await bot.send_message(message.chat.id, text, parse_mode='HTML', reply_markup=kb)
            elif actual_media_type == 'photo':
                try:
                    sent_msg = await bot.send_photo(
                        chat_id=message.chat.id,
                        photo=media_file_id,
                        caption=text,
                        parse_mode='HTML',
                        reply_markup=kb
                    )
                except Exception as e:
                    logger.error(f"Photo send failed, retrying as video: {e}")
                    # Check if the error is specifically about wrong file type
                    if "can't use file of type Video as Photo" in str(e):
                        logger.info("File is actually a video, sending as video")
                        try:
                            sent_msg = await bot.send_video(
                                chat_id=message.chat.id,
                                video=media_file_id,
                                caption=text,
                                parse_mode='HTML',
                                reply_markup=kb
                            )
                        except Exception as e2:
                            logger.error(f"Video send also failed: {e2}")
                            sent_msg = await bot.send_message(message.chat.id, text, parse_mode='HTML', reply_markup=kb)
                    else:
                        # For other errors, try as document
                        try:
                            sent_msg = await bot.send_document(
                                chat_id=message.chat.id,
                                document=media_file_id,
                                caption=text,
                                parse_mode='HTML',
                                reply_markup=kb
                            )
                        except Exception as e3:
                            logger.error(f"Document send also failed: {e3}")
                            sent_msg = await bot.send_message(message.chat.id, text, parse_mode='HTML', reply_markup=kb)
            else:
                # media_type yo'q yoki noma'lum - fallback zanjiri
                try:
                    sent_msg = await bot.send_photo(
                        chat_id=message.chat.id,
                        photo=media_file_id,
                        caption=text,
                        parse_mode='HTML',
                        reply_markup=kb
                    )
                except Exception as e:
                    logger.error(f"Photo send failed, retrying as video: {e}")
                    # Check if the error is specifically about wrong file type
                    if "can't use file of type Video as Photo" in str(e):
                        logger.info("File is actually a video, sending as video")
                        try:
                            sent_msg = await bot.send_video(
                                chat_id=message.chat.id,
                                video=media_file_id,
                                caption=text,
                                parse_mode='HTML',
                                reply_markup=kb
                            )
                        except Exception as e2:
                            logger.error(f"Video send also failed: {e2}")
                            sent_msg = await bot.send_message(message.chat.id, text, parse_mode='HTML', reply_markup=kb)
                    else:
                        # For other errors, try as document
                        try:
                            sent_msg = await bot.send_document(
                                chat_id=message.chat.id,
                                document=media_file_id,
                                caption=text,
                                parse_mode='HTML',
                                reply_markup=kb
                            )
                        except Exception as e3:
                            logger.error(f"Document send also failed: {e3}")
                            sent_msg = await bot.send_message(message.chat.id, text, parse_mode='HTML', reply_markup=kb)
        else:
            sent_msg = await bot.send_message(message.chat.id, text, parse_mode='HTML', reply_markup=kb)
        
        # Track the sent message if state is provided
        if state and sent_msg:
            await track_message(state, sent_msg.message_id)
        
        return sent_msg
    except Exception:
        # Agar delete ishlamasa ham, matn yuborishga harakat qilamiz
        try:
            sent_msg = await bot.send_message(message.chat.id, text, parse_mode='HTML', reply_markup=kb)
            if state and sent_msg:
                await track_message(state, sent_msg.message_id)
            return sent_msg
        except:
            return None

async def render_item_new_message(message: Message, item: dict, idx: int, total: int, lang: str, mode: str, user_id: int = None, state: FSMContext = None):
    """Arizani yangi xabar sifatida render qilish (edit emas)"""
    if user_id:
        text = await short_view_text_with_materials(item, idx, total, user_id, lang, mode)
    else:
        text = short_view_text(item, idx, total, lang, mode)
    kb = await action_keyboard(item.get("id"), idx, total, item.get("status", ""), mode=mode, lang=lang, item=item)
    
    media_file_id = item.get("media_file_id")
    media_type = item.get("media_type")
    
    try:
        # Yangi xabar yuborish
        sent_msg = None
        if media_file_id and media_type:
            try:
                if media_type == 'photo':
                    sent_msg = await bot.send_photo(
                        chat_id=message.chat.id,
                        photo=media_file_id,
                        caption=text,
                        parse_mode='HTML',
                        reply_markup=kb
                    )
                elif media_type == 'video':
                    sent_msg = await bot.send_video(
                        chat_id=message.chat.id,
                        video=media_file_id,
                        caption=text,
                        parse_mode='HTML',
                        reply_markup=kb
                    )
                elif media_type == 'document':
                    sent_msg = await bot.send_document(
                        chat_id=message.chat.id,
                        document=media_file_id,
                        caption=text,
                        parse_mode='HTML',
                        reply_markup=kb
                    )
            except Exception as e:
                # Agar media yuborishda xatolik bo'lsa, oddiy matn yuboramiz
                sent_msg = await bot.send_message(message.chat.id, text, parse_mode='HTML', reply_markup=kb)
        else:
            sent_msg = await bot.send_message(message.chat.id, text, parse_mode='HTML', reply_markup=kb)
        
        # Track the sent message if state is provided
        if state and sent_msg:
            await track_message(state, sent_msg.message_id)
        
        return sent_msg
    except Exception:
        # Agar xatolik bo'lsa, oddiy matn yuborishga harakat qilamiz
        try:
            sent_msg = await bot.send_message(message.chat.id, text, parse_mode='HTML', reply_markup=kb)
            if state and sent_msg:
                await track_message(state, sent_msg.message_id)
            return sent_msg
        except:
            return None

# ====== Inbox ochish: avval kategoriya ======
@router.message(F.text.in_(["📥 Inbox", "Inbox", "📥 Входящие"]))
async def tech_open_inbox(message: Message, state: FSMContext):
    user = await find_user_by_telegram_id(message.from_user.id)
    if not user or user.get("role") != "technician":
        return
    lang = await resolve_lang(message.from_user.id, fallback=("ru" if message.text == "📥 Входящие" else "uz"))
    await state.update_data(tech_mode=None, tech_inbox=[], tech_idx=0, lang=lang)
    await message.answer(t("choose_section", lang), reply_markup=tech_category_keyboard(lang))

# ====== Kategoriya handlerlari ======
@router.callback_query(F.data == "tech_inbox_cat_connection")
async def tech_cat_connection(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    st = await state.get_data(); lang = st.get("lang") or await resolve_lang(cb.from_user.id)
    user = await find_user_by_telegram_id(cb.from_user.id)
    if not user or user.get("role") != "technician":
        return await cb.answer(t("no_perm", lang), show_alert=True)

    # Purge tracked messages and delete category selection message
    await purge_tracked_messages(state, cb.message.chat.id)
    try:
        await cb.message.delete()
    except:
        pass

    items = _dedup_by_id(await fetch_technician_inbox(technician_id=user["id"], limit=50, offset=0))
    await state.update_data(tech_mode="connection", tech_inbox=items, tech_idx=0, lang=lang)
    if not items:
        sent_msg = await bot.send_message(cb.message.chat.id, t("empty_connection", lang), reply_markup=InlineKeyboardMarkup(inline_keyboard=[]))
        await track_message(state, sent_msg.message_id)
        return
    
    # Connection arizalarida rasmlar bo'lmaydi, shuning uchun oddiy send
    item = items[0]; total = len(items)
    text = await short_view_text_with_materials(item, 0, total, user["id"], lang, mode="connection")
    kb = await action_keyboard(item.get("id"), 0, total, item.get("status", ""), mode="connection", lang=lang, item=item)
    sent_msg = await bot.send_message(cb.message.chat.id, text, reply_markup=kb, parse_mode="HTML")
    await track_message(state, sent_msg.message_id)

@router.callback_query(F.data == "tech_inbox_cat_tech")
async def tech_cat_tech(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    st = await state.get_data(); lang = st.get("lang") or await resolve_lang(cb.from_user.id)
    user = await find_user_by_telegram_id(cb.from_user.id)
    if not user or user.get("role") != "technician":
        return await cb.answer(t("no_perm", lang), show_alert=True)

    # Purge tracked messages and delete category selection message
    await purge_tracked_messages(state, cb.message.chat.id)
    try:
        await cb.message.delete()
    except:
        pass

    items = _dedup_by_id(await fetch_technician_inbox_tech(technician_id=user["id"], limit=50, offset=0))
    await state.update_data(tech_mode="technician", tech_inbox=items, tech_idx=0, lang=lang)
    if not items:
        sent_msg = await bot.send_message(cb.message.chat.id, t("empty_tech", lang), reply_markup=InlineKeyboardMarkup(inline_keyboard=[]))
        await track_message(state, sent_msg.message_id)
        return
    
    # Texnik xizmat arizalarida rasmlar bo'lishi mumkin - render_item ishlatamiz
    await render_item(cb.message, items[0], 0, len(items), lang, "technician", user["id"], state)

@router.callback_query(F.data == "tech_inbox_cat_operator")
async def tech_cat_operator(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    st = await state.get_data(); lang = st.get("lang") or await resolve_lang(cb.from_user.id)
    user = await find_user_by_telegram_id(cb.from_user.id)
    if not user or user.get("role") != "technician":
        return await cb.answer(t("no_perm", lang), show_alert=True)

    # Purge tracked messages and delete category selection message
    await purge_tracked_messages(state, cb.message.chat.id)
    try:
        await cb.message.delete()
    except:
        pass

    items = _dedup_by_id(await fetch_technician_inbox_staff(technician_id=user["id"], limit=50, offset=0))
    await state.update_data(tech_mode="staff", tech_inbox=items, tech_idx=0, lang=lang)
    if not items:
        sent_msg = await bot.send_message(cb.message.chat.id, t("empty_staff", lang), reply_markup=InlineKeyboardMarkup(inline_keyboard=[]))
        await track_message(state, sent_msg.message_id)
        return
    
    # Staff arizalarida rasmlar yo'q - oddiy send
    item = items[0]; total = len(items)
    text = await short_view_text_with_materials(item, 0, total, user["id"], lang, mode="staff")
    kb = await action_keyboard(item.get("id"), 0, total, item.get("status", ""), mode="staff", lang=lang, item=item)
    sent_msg = await bot.send_message(cb.message.chat.id, text, reply_markup=kb, parse_mode="HTML")
    await track_message(state, sent_msg.message_id)

# ====== Navigatsiya (prev/next) ======
@router.callback_query(F.data.startswith("tech_inbox_prev_"))
async def tech_prev(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    st = await state.get_data(); lang = st.get("lang") or await resolve_lang(cb.from_user.id)
    user = await find_user_by_telegram_id(cb.from_user.id)
    if not user or user.get("role") != "technician":
        return await cb.answer(t("no_perm", lang), show_alert=True)
    
    mode = st.get("tech_mode", "connection")
    items = _dedup_by_id(st.get("tech_inbox", []))
    if not items:
        return await cb.answer(t("empty_inbox", lang))
    total = len(items)
    idx = int(cb.data.replace("tech_inbox_prev_", "")) - 1
    if idx < 0 or idx >= total:
        return await cb.answer(t("reached_start", lang))
    await state.update_data(tech_inbox=items, tech_idx=idx)
    
    # Purge tracked messages and delete current message
    await purge_tracked_messages(state, cb.message.chat.id)
    try:
        await cb.message.delete()
    except:
        pass
    
    # Modga qarab render qilish
    if mode == "technician":
        # Technician mode - rasmlar bor, render_item
        await render_item(cb.message, items[idx], idx, total, lang, mode, user["id"], state)
    else:
        # Connection/staff mode - rasmlar yo'q, oddiy send
        text = await short_view_text_with_materials(items[idx], idx, total, user["id"], lang, mode)
        kb = await action_keyboard(items[idx].get("id"), idx, total, items[idx].get("status", ""), mode=mode, lang=lang, item=items[idx])
        sent_msg = await bot.send_message(cb.message.chat.id, text, reply_markup=kb, parse_mode="HTML")
        await track_message(state, sent_msg.message_id)

@router.callback_query(F.data.startswith("tech_inbox_next_"))
async def tech_next(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    st = await state.get_data(); lang = st.get("lang") or await resolve_lang(cb.from_user.id)
    user = await find_user_by_telegram_id(cb.from_user.id)
    if not user or user.get("role") != "technician":
        return await cb.answer(t("no_perm", lang), show_alert=True)
    
    mode = st.get("tech_mode", "connection")
    items = _dedup_by_id(st.get("tech_inbox", []))
    if not items:
        return await cb.answer(t("empty_inbox", lang))
    total = len(items)
    idx = int(cb.data.replace("tech_inbox_next_", "")) + 1
    if idx < 0 or idx >= total:
        return await cb.answer(t("reached_end", lang))
    await state.update_data(tech_inbox=items, tech_idx=idx)
    
    # Purge tracked messages and delete current message
    await purge_tracked_messages(state, cb.message.chat.id)
    try:
        await cb.message.delete()
    except:
        pass
    
    # Modga qarab render qilish
    if mode == "technician":
        # Technician mode - rasmlar bor, render_item
        await render_item(cb.message, items[idx], idx, total, lang, mode, user["id"], state)
    else:
        # Connection/staff mode - rasmlar yo'q, oddiy send
        text = await short_view_text_with_materials(items[idx], idx, total, user["id"], lang, mode)
        kb = await action_keyboard(items[idx].get("id"), idx, total, items[idx].get("status", ""), mode=mode, lang=lang, item=items[idx])
        sent_msg = await bot.send_message(cb.message.chat.id, text, reply_markup=kb, parse_mode="HTML")
        await track_message(state, sent_msg.message_id)

# ====== Qabul qilish / Bekor qilish / Boshlash ======
@router.callback_query(F.data.startswith("tech_accept_"))
async def tech_accept(cb: CallbackQuery, state: FSMContext):
    st = await state.get_data(); lang = st.get("lang") or await resolve_lang(cb.from_user.id)
    mode = st.get("tech_mode", "connection")
    user = await find_user_by_telegram_id(cb.from_user.id)
    if not user or user.get("role") != "technician":
        return await cb.answer(t("no_perm", lang), show_alert=True)

    req_id = int(cb.data.replace("tech_accept_", ""))
    try:
        if mode == "technician":
            ok = await accept_technician_work_for_tech(applications_id=req_id, technician_id=user["id"])
        elif mode == "staff":
            ok = await accept_technician_work_for_staff(applications_id=req_id, technician_id=user["id"])
        else:
            ok = await accept_technician_work(applications_id=req_id, technician_id=user["id"])
        if not ok:
            return await cb.answer(t("status_mismatch", lang), show_alert=True)
        
        # Controller'ga notification yuboramiz (texnik qabul qildi)
        try:
            from utils.notification_service import send_role_notification
            from database.connections import get_connection_url
            import asyncpg
            
            # Controller'ning telegram_id ni olamiz (connections jadvalidan)
            conn = await asyncpg.connect(get_connection_url())
            try:
                # Get controller who assigned this order to technician
                controller_info = None
                
                # First, get application_number from the order
                app_number = None
                if mode == "technician":
                    row = await conn.fetchrow("SELECT application_number FROM technician_orders WHERE id = $1", req_id)
                    app_number = row["application_number"] if row else None
                elif mode == "staff":
                    row = await conn.fetchrow("SELECT application_number FROM staff_orders WHERE id = $1", req_id)
                    app_number = row["application_number"] if row else None
                else:  # connection mode
                    row = await conn.fetchrow("SELECT application_number FROM connection_orders WHERE id = $1", req_id)
                    app_number = row["application_number"] if row else None
                
                if app_number:
                    controller_info = await conn.fetchrow("""
                        SELECT u.telegram_id, u.language 
                        FROM connections c
                        JOIN users u ON u.id = c.sender_id
                        WHERE c.application_number = $1 AND c.sender_id IN (
                            SELECT id FROM users WHERE role = 'controller'
                        )
                        ORDER BY c.created_at DESC LIMIT 1
                    """, app_number)
                

            finally:
                await conn.close()
        except Exception as notif_error:
            logger.error(f"Failed to send notification to controller: {notif_error}")
            # Notification xatosi asosiy jarayonga ta'sir qilmaydi
    except Exception as e:
        return await cb.answer(f"{t('x_error', lang)} {e}", show_alert=True)

    # Purge tracked messages and delete current message
    await purge_tracked_messages(state, cb.message.chat.id)
    try:
        await cb.message.delete()
    except:
        pass

    items = _dedup_by_id((await state.get_data()).get("tech_inbox", []))
    idx = int((await state.get_data()).get("tech_idx", 0))
    for it in items:
        if it.get("id") == req_id:
            it["status"] = "in_technician"
            break
    await state.update_data(tech_inbox=items)
    total = len(items)
    item = items[idx] if 0 <= idx < total else items[0]
    
    # Modga qarab render qilish
    if mode == "technician":
        await render_item(cb.message, item, idx, total, lang, mode, user["id"], state)
    else:
        # Connection/staff mode - oddiy send
        text = await short_view_text_with_materials(item, idx, total, user["id"], lang, mode)
        kb = await action_keyboard(item.get("id"), idx, total, item.get("status", ""), mode=mode, lang=lang, item=item)
        sent_msg = await bot.send_message(cb.message.chat.id, text, reply_markup=kb, parse_mode="HTML")
        await track_message(state, sent_msg.message_id)
    
    await cb.answer()

@router.callback_query(F.data.startswith("tech_start_"))
async def tech_start(cb: CallbackQuery, state: FSMContext):
    """
    Ishni boshlash handler.
    - Technician mode yoki staff(technician) -> darhol diagnostika so'raydi
    - Connection mode yoki staff(connection) -> to'g'ri materiallar ko'rsatadi
    """
    st = await state.get_data(); lang = st.get("lang") or await resolve_lang(cb.from_user.id)
    mode = st.get("tech_mode", "connection")
    user = await find_user_by_telegram_id(cb.from_user.id)
    if not user or user.get("role") != "technician":
        return await cb.answer(t("no_perm", lang), show_alert=True)
    req_id = int(cb.data.replace("tech_start_", ""))
    
    # Statusni yangilash
    try:
        if mode == "technician":
            ok = await start_technician_work_for_tech(applications_id=req_id, technician_id=user["id"])
        elif mode == "staff":
            ok = await start_technician_work_for_staff(applications_id=req_id, technician_id=user["id"])
        else:
            ok = await start_technician_work(applications_id=req_id, technician_id=user["id"])
        if not ok:
            current_status = await get_current_status(req_id, mode)
            status_display = current_status or 'noma\'lum'
            error_msg = f"⚠️ Xatolik! Avval 'Qabul qilish' tugmasini bosing.\n\n"
            error_msg += f"Joriy holat: {status_display}\n"
            error_msg += "Kerakli holat: in_technician"
            return await cb.answer(error_msg, show_alert=True)
    except Exception as e:
        return await cb.answer(f"{t('x_error', lang)} {e}", show_alert=True)

    # Purge tracked messages and delete current message
    await purge_tracked_messages(state, cb.message.chat.id)
    try:
        await cb.message.delete()
    except:
        pass

    # Inbox'ni yangilash
    items = _dedup_by_id((await state.get_data()).get("tech_inbox", []))
    idx = int((await state.get_data()).get("tech_idx", 0))
    for it in items:
        if it.get("id") == req_id:
            it["status"] = "in_technician_work"
            break
    await state.update_data(tech_inbox=items)

    total = len(items)
    item = items[idx] if 0 <= idx < total else items[0]
    
    # Ariza ko'rinishini yangilash
    if mode == "technician":
        await render_item(cb.message, item, idx, total, lang, mode, user["id"], state)
    else:
        text = await short_view_text_with_materials(item, idx, total, user["id"], lang, mode)
        kb = await action_keyboard(item.get("id"), idx, total, item.get("status", ""), mode=mode, lang=lang, item=item)
        sent_msg = await bot.send_message(cb.message.chat.id, text, reply_markup=kb, parse_mode="HTML")
        await track_message(state, sent_msg.message_id)
    
    # Ish boshlangan xabari
    await cb.answer(t("ok_started", lang))

# ====== DIAGNOSTIKA ======
# tech_diag_begin o'chirildi - endi diagnostika to'g'ridan-to'g'ri tech_start'dan boshlanadi

@router.message(StateFilter(DiagStates.waiting_text))
async def tech_diag_text(msg: Message, state: FSMContext):
    """Diagnostika matnini qabul qilish va saqlash"""
    user = await find_user_by_telegram_id(msg.from_user.id)
    st = await state.get_data(); lang = st.get("lang") or await resolve_lang(msg.from_user.id)
    if not user or user.get("role") != "technician":
        return await msg.answer(t("no_perm", lang))

    data = await state.get_data()
    req_id = int(data.get("diag_req_id", 0))
    if req_id <= 0:
        await clear_temp_contexts(state)
        return await msg.answer(t("req_not_found", lang))

    text = (msg.text or "").strip()
    if not text:
        return await msg.answer("❌ Diagnostika matnini kiriting" if lang == "uz" else "❌ Введите текст диагностики")

    try:
        # Mode'ga qarab to'g'ri jadvalga diagnostika yozish
        mode = st.get("tech_mode", "connection")
        if mode == "staff":
            # Staff arizalar uchun staff_orders jadvaliga yozish (faqat technician type uchun)
            conn = await asyncpg.connect(settings.DB_URL)
            try:
                await conn.execute(
                    """
                    UPDATE staff_orders
                       SET diagnostics = $2,
                           updated_at = NOW()
                     WHERE id = $1 AND type_of_zayavka = 'technician'
                    """,
                    req_id, text
                )
            finally:
                await conn.close()
        elif mode == "technician":
            # Technician arizalar uchun technician_orders jadvaliga yozish
            await save_technician_diagnosis(applications_id=req_id, technician_id=user["id"], text=text)
        # Connection mode uchun diagnostika qo'shish kerak emas
    except Exception as e:
        await clear_temp_contexts(state)
        return await msg.answer(f"{t('x_error', lang)} {e}")

    # Purge tracked messages and delete user's text input
    await purge_tracked_messages(state, msg.chat.id)
    try:
        await msg.delete()
    except Exception:
        pass

    mode = st.get("tech_mode", "connection")
    app_number = await get_application_number(req_id, mode)
        # Diagnostika saqlangandan keyin tasdiqlash xabari
    success_text = f"✅ <b>{'Diagnostika saqlandi!' if lang=='uz' else 'Диагностика сохранена!'}</b>\n\n"
    success_text += f"🆔 <b>{'Ariza raqami:' if lang=='uz' else 'Номер заявки:'}</b> {app_number}\n"
    success_text += f"📝 <b>{'Diagnostika:' if lang=='uz' else 'Диагностика:'}</b>\n<code>{html.escape(text, quote=False)}</code>\n\n"
    success_text += f"{'Davom etishingiz mumkin' if lang=='uz' else 'Можете продолжить'}"
    
    await msg.answer(success_text, parse_mode="HTML")
    
    await clear_temp_contexts(state)

    # Diagnostika tugaganidan so'ng, ariza ko'rinishini yangilash
    items = _dedup_by_id((await state.get_data()).get("tech_inbox", []))
    idx = int((await state.get_data()).get("tech_idx", 0))
    total = len(items)
    
    # Agar items bo'sh bo'lsa, oddiy xabar yuboramiz
    if not items:
        # Inline tugmalar yaratish
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text=t("warehouse", lang), callback_data=f"tech_add_more_{req_id}"),
                InlineKeyboardButton(text=t("review", lang), callback_data=f"tech_review_{req_id}"),
            ]
        ])
        
        sent_msg = await msg.answer(diag_text, reply_markup=kb, parse_mode="HTML")
        await track_message(state, sent_msg.message_id)
        return
    
    item = items[idx] if 0 <= idx < total else items[0]
    
    # Item'da diagnostika maydonini yangilash
    if item:
        item["diagnostics"] = text
    
    # Yangi xabar yuborish (edit emas) - faqat bitta xabar
    if item and mode == "technician":
        await render_item_new_message(msg, item, idx, total, lang, mode, user["id"], state)
    elif item:
        text = await short_view_text_with_materials(item, idx, total, user["id"], lang, mode)
        kb = await action_keyboard(item.get("id"), idx, total, item.get("status", ""), mode=mode, lang=lang, item=item)
        sent_msg = await msg.answer(text, reply_markup=kb, parse_mode="HTML")
        await track_message(state, sent_msg.message_id)
    else:
        # Agar item yo'q bo'lsa, oddiy xabar yuboramiz
        diag_text = f"✅ <b>{'Diagnostika saqlandi!' if lang=='uz' else 'Диагностика сохранена!'}</b>\n\n"
        diag_text += f"{t('order_id', lang)} {esc(app_number)}\n"
        diag_text += f"{t('diag_text', lang)}\n<code>{html.escape(text, quote=False)}</code>\n\n"
        diag_text += f"{'Davom etishingiz mumkin' if lang=='uz' else 'Можете продолжить'}"
        
        # Inline tugmalar yaratish
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text=t("warehouse", lang), callback_data=f"tech_add_more_{req_id}"),
                InlineKeyboardButton(text=t("review", lang), callback_data=f"tech_review_{req_id}"),
            ]
        ])
        
        sent_msg = await msg.answer(diag_text, reply_markup=kb, parse_mode="HTML")
        await track_message(state, sent_msg.message_id)

# ====== Diagnostika tugmasi ======
@router.callback_query(F.data.startswith("tech_diag_"))
async def tech_diag_button(cb: CallbackQuery, state: FSMContext):
    """Diagnostika tugmasi bosilganda"""
    st = await state.get_data(); lang = st.get("lang") or await resolve_lang(cb.from_user.id)
    user = await find_user_by_telegram_id(cb.from_user.id)
    if not user or user.get("role") != "technician":
        return await cb.answer(t("no_perm", lang), show_alert=True)
    
    req_id = int(cb.data.replace("tech_diag_", ""))
    mode = st.get("tech_mode", "connection")
    
    # Diagnostika so'rash
    await cb.message.edit_reply_markup(reply_markup=None)  # Inline keyboard o'chirish
    await cb.message.answer(
        t("diag_begin_prompt", lang),
        parse_mode="HTML"
    )
    await state.update_data(diag_req_id=req_id)
    await state.set_state(DiagStates.waiting_text)
    await cb.answer()

# Eski diagnostika handlerlari o'chirildi - endi soddalashtirilgan oqim

# ====== Materiallar oqimi ======
@router.callback_query(F.data.startswith("tech_mat_select_"))
async def tech_mat_select(cb: CallbackQuery, state: FSMContext):
    st = await state.get_data(); lang = st.get("lang") or await resolve_lang(cb.from_user.id)
    try:
        payload = cb.data[len("tech_mat_select_"):]
        parts = payload.split("_")
        if len(parts) != 2:
            raise ValueError("Invalid format")
        material_id, req_id = map(int, parts)
    except Exception as e:
        return await cb.answer(t("format_err", lang), show_alert=True)

    user = await find_user_by_telegram_id(cb.from_user.id)
    if not user or user.get("role") != "technician":
        return await cb.answer(t("no_perm", lang), show_alert=True)

    mat = await fetch_material_by_id(material_id)
    if not mat:
        return await cb.answer(t("not_found_mat", lang), show_alert=True)

    # Texnikda mavjud materiallarni olish
    technician_materials = await fetch_technician_materials(user["id"])
    
    # Joriy materialni topish
    current_material = None
    for mat in technician_materials:
        if mat['material_id'] == material_id:
            current_material = mat
            break
    
    if not current_material:
        # Texnikda bu material yo'q, ombordan so'rash kerak
        source_type = "warehouse"
        real_available = 0
    else:
        # Texnikda mavjud, miqdorini tekshirish
        real_available = current_material['stock_quantity']
        source_type = "technician_stock" if real_available > 0 else "warehouse"

    # Purge tracked messages and delete current message
    await purge_tracked_messages(state, cb.message.chat.id)
    try:
        await cb.message.delete()
    except Exception:
        pass

    # Application number ni olish
    mode = st.get("tech_mode", "connection")
    app_number = await get_application_number(req_id, mode)
    
    currency = 'so\'m' if lang=='uz' else 'сум'
    unit = 'dona' if lang=='uz' else 'шт'
    text = (
        f"{t('enter_qty', lang)}\n\n"
        f"{t('order_id', lang)} {esc(app_number)}\n"
        f"{t('chosen_prod', lang)} {esc(mat['name'])}\n"
        f"{t('price', lang)} {_fmt_price_uzs(mat['price'])} {currency}\n"
        f"✅ Mavjud: {real_available} {unit}\n\n"
        + t("enter_qty_hint", lang, max=real_available)
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t("btn_cancel", lang), callback_data=f"tech_qty_cancel_{req_id}")],
        [InlineKeyboardButton(text=t("back", lang), callback_data=f"tech_back_to_order_{req_id}")]
    ])

    await state.update_data(
        current_application_id=req_id,
        qty_ctx={
            "applications_id": req_id,
            "material_id": material_id,
            "material_name": mat["name"],
            "price": mat["price"],
            "max_qty": real_available,
            "lang": lang,
            "qty_message_id": None,  # Miqdor xabari ID'si
            "source_type": source_type,  # Material manbai
        }
    )

    qty_message = await cb.message.answer(text, reply_markup=kb, parse_mode="HTML")
    await track_message(state, qty_message.message_id)
    
    # Miqdor xabari ID'sini saqlash
    await state.update_data(
        qty_ctx={
            "applications_id": req_id,
            "material_id": material_id,
            "material_name": mat["name"],
            "price": mat["price"],
            "max_qty": real_available,
            "lang": lang,
            "qty_message_id": qty_message.message_id,
            "source_type": source_type,  # Material manbai
        }
    )
    
    await state.set_state(QtyStates.waiting_qty)
    await cb.answer()

@router.callback_query(F.data.startswith("tech_qty_cancel_"))
async def tech_qty_cancel(cb: CallbackQuery, state: FSMContext):
    st = await state.get_data(); lang = st.get("lang") or await resolve_lang(cb.from_user.id)
    try:
        req_id = int(cb.data.replace("tech_qty_cancel_", ""))
    except Exception:
        return await cb.answer()

    user = await find_user_by_telegram_id(cb.from_user.id)
    if not user or user.get("role") != "technician":
        return await cb.answer(t("no_perm", lang), show_alert=True)

    # Purge tracked messages and delete current message
    await purge_tracked_messages(state, cb.message.chat.id)
    try:
        await cb.message.delete()
    except Exception:
        pass

    mode = st.get("tech_mode", "connection")
    
    # 🟢 YANGI YONDASHUV: To'g'ridan-to'g'ri DB'dan olish
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        if mode == "technician":
            query = """
                SELECT * FROM technician_orders 
                WHERE id = $1
            """
        elif mode == "staff":
            query = """
                SELECT * FROM staff_orders 
                WHERE id = $1
            """
        else:
            query = """
                SELECT * FROM connection_orders 
                WHERE id = $1
            """
        
        item = await conn.fetchrow(query, req_id)
        
        if not item:
            return await cb.answer(
                "❌ Ariza topilmadi" if lang == "uz" else "❌ Заявка не найдена",
                show_alert=True
            )
        
        item = dict(item)
        
    finally:
        await conn.close()
    
    # Materiallar ro'yxatini olish
    mats = await fetch_technician_materials(user_id=user["id"])
    
    # Ariza ma'lumotlarini ko'rsatish
    text = short_view_text(item, 0, 1, lang, mode)
    
    materials_text = "\n\n📦 <b>Ombor jihozlari</b>\n"
    materials_text += "Kerakli jihozlarni tanlang yoki boshqa mahsulot kiriting:\n\n"
    
    if mats:
        for mat in mats:
            name = _short(mat.get('name', 'NO NAME'))
            price = _fmt_price_uzs(mat.get('price', 0))
            stock = mat.get('stock_quantity', '0')
            materials_text += f"📦 {name} — {price} so'm ({stock} dona)\n"
    else:
        materials_text += "• Texnikda materiallar yo'q\n"
    
    full_text = text + materials_text
    kb = materials_keyboard(mats, applications_id=req_id, lang=lang)
    
    sent_msg = await cb.message.answer(full_text, reply_markup=kb, parse_mode="HTML")
    await track_message(state, sent_msg.message_id)
    await clear_temp_contexts(state)
    await cb.answer()

@router.message(StateFilter(QtyStates.waiting_qty))
async def tech_qty_entered(msg: Message, state: FSMContext):
    st = await state.get_data(); lang = st.get("lang") or await resolve_lang(msg.from_user.id)
    user = await find_user_by_telegram_id(msg.from_user.id)
    if not user or user.get("role") != "technician":
        return await msg.answer(t("no_perm", lang))

    ctx = st.get("qty_ctx") or {}
    req_id = int(ctx.get("applications_id", 0))
    material_id = int(ctx.get("material_id", 0))
    max_qty = int(ctx.get("max_qty", 0))
    qty_message_id = ctx.get("qty_message_id")
    source_type = ctx.get("source_type", "warehouse")

    try:
        qty = int((msg.text or "").strip())
        if qty <= 0:
            return await msg.answer(t("gt_zero", lang))
    except Exception:
        return await msg.answer(t("only_int", lang))

    if qty > max_qty:
        return await msg.answer(t("max_exceeded", lang, max=max_qty))

    # Material tanlovini darhol saqlash
    try:
        mode = st.get("tech_mode", "connection")
        await upsert_material_selection(
            user_id=user["id"],
            application_id=req_id,
            material_id=material_id,
            qty=qty,
            request_type=mode,
            source_type=source_type
        )
    except ValueError as ve:
        return await msg.answer(f"❌ {ve}")
    except Exception as e:
        return await msg.answer(f"{t('x_error', lang)} {e}")

    await purge_tracked_messages(state, msg.chat.id)
    try:
        await msg.delete()
    except Exception:
        pass

    conn = await asyncpg.connect(settings.DB_URL)
    try:
        if mode == "technician":
            query = """
                SELECT 
                    to2.*,
                    to2.description_ish AS diagnostics,
                    COALESCE(client_user.full_name, user_user.full_name) AS client_name,
                    COALESCE(client_user.phone, user_user.phone) AS client_phone
                FROM technician_orders to2
                LEFT JOIN users client_user ON client_user.id::text = to2.abonent_id
                LEFT JOIN users user_user ON user_user.id = to2.user_id
                WHERE to2.id = $1
            """
        elif mode == "staff":
            query = """
                SELECT 
                    so.*,
                    COALESCE(client_user.full_name, 'Mijoz') AS client_name,
                    COALESCE(client_user.phone, so.phone) AS client_phone,
                    creator.full_name AS staff_creator_name,
                    creator.phone AS staff_creator_phone,
                    creator.role AS staff_creator_role
                FROM staff_orders so
                LEFT JOIN users client_user ON client_user.id::text = so.abonent_id
                LEFT JOIN users creator ON creator.id = so.user_id
                WHERE so.id = $1
            """
        else:
            query = """
                SELECT 
                    co.*,
                    u.full_name AS client_name,
                    u.phone AS client_phone
                FROM connection_orders co
                LEFT JOIN users u ON u.id = co.user_id
                WHERE co.id = $1
            """
        
        item = await conn.fetchrow(query, req_id)
        
        if not item:
            return await msg.answer(
                "❌ Ariza topilmadi" if lang == "uz" else "❌ Заявка не найдена"
            )
        
        item = dict(item)
        
    finally:
        await conn.close()
    
    # Build text with order details + selected materials
    # Joriy inbox state ni saqlab qolish
    current_idx = st.get("tech_idx", 0)
    current_inbox = st.get("tech_inbox", [])
    total_items = len(current_inbox)
    
    original_text = short_view_text(item, current_idx, total_items, lang, mode)
    
    # Application number ni olish va materiallarni olish
    app_number = await get_application_number(req_id, mode)
    selected = await fetch_selected_materials_for_request(user["id"], app_number)
    materials_text = "\n\n📦 <b>Ishlatilayotgan mahsulotlar:</b>\n"
    
    if selected:
        currency_unit = 'so\'m' if lang=='uz' else 'сум'
        unit_name = 'dona' if lang=='uz' else 'шт'
        for it in selected:
            qty_txt = f"{_qty_of(it)} {unit_name}"
            price_txt = f"{_fmt_price_uzs(it['price'])} {currency_unit}"
            materials_text += f"• {esc(it['name'])} — {qty_txt} (💰 {price_txt})\n"
    else:
        materials_text += "• (tanlanmagan)\n"
    
    # Combine original text with materials
    full_text = original_text + materials_text

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t("add_more", lang), callback_data=f"tech_add_more_{req_id}")],
        [InlineKeyboardButton(text=t("final_view", lang), callback_data=f"tech_review_{req_id}")]
    ])
    
    # Always send new message instead of editing
    sent_msg = await msg.answer(full_text, reply_markup=kb, parse_mode="HTML")
    await track_message(state, sent_msg.message_id)
    
    await clear_temp_contexts(state)

@router.callback_query(F.data.startswith("tech_back_to_order_"))
async def tech_back_to_order(cb: CallbackQuery, state: FSMContext):
    """Return to main order view with [Ombor] [Yakuniy ko'rinish] buttons"""
    st = await state.get_data(); lang = st.get("lang") or await resolve_lang(cb.from_user.id)
    try:
        req_id = int(cb.data.replace("tech_back_to_order_", ""))
    except Exception:
        return await cb.answer()
    user = await find_user_by_telegram_id(cb.from_user.id)
    if not user or user.get("role") != "technician":
        return await cb.answer(t("no_perm", lang), show_alert=True)

    # Purge tracked messages and delete current message
    await purge_tracked_messages(state, cb.message.chat.id)
    try:
        await cb.message.delete()
    except Exception:
        pass

    mode = st.get("tech_mode", "connection")
    
    # 🟢 YANGI YONDASHUV: To'g'ridan-to'g'ri DB'dan olish
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        if mode == "technician":
            query = """
                SELECT 
                    to2.*,
                    to2.description_ish AS diagnostics,
                    COALESCE(client_user.full_name, user_user.full_name) AS client_name,
                    COALESCE(client_user.phone, user_user.phone) AS client_phone
                FROM technician_orders to2
                LEFT JOIN users client_user ON client_user.id::text = to2.abonent_id
                LEFT JOIN users user_user ON user_user.id = to2.user_id
                WHERE to2.id = $1
            """
        elif mode == "staff":
            query = """
                SELECT 
                    so.*,
                    COALESCE(client_user.full_name, 'Mijoz') AS client_name,
                    COALESCE(client_user.phone, so.phone) AS client_phone,
                    creator.full_name AS staff_creator_name,
                    creator.phone AS staff_creator_phone,
                    creator.role AS staff_creator_role
                FROM staff_orders so
                LEFT JOIN users client_user ON client_user.id::text = so.abonent_id
                LEFT JOIN users creator ON creator.id = so.user_id
                WHERE so.id = $1
            """
        else:
            query = """
                SELECT 
                    co.*,
                    u.full_name AS client_name,
                    u.phone AS client_phone
                FROM connection_orders co
                LEFT JOIN users u ON u.id = co.user_id
                WHERE co.id = $1
            """
        
        item = await conn.fetchrow(query, req_id)
        
        if not item:
            return await cb.answer(
                "❌ Ariza topilmadi" if lang == "uz" else "❌ Заявка не найдена",
                show_alert=True
            )
        
        item = dict(item)
        
    finally:
        await conn.close()
    
    # Restore original text with [Ombor] [Yakuniy ko'rinish] buttons
    original_text = short_view_text(item, 0, 1, lang, mode)
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=t("warehouse", lang), callback_data=f"tech_add_more_{req_id}"),
            InlineKeyboardButton(text=t("review", lang), callback_data=f"tech_review_{req_id}"),
        ]
    ])
    
    sent_msg = await cb.message.answer(original_text, reply_markup=kb, parse_mode="HTML")
    await track_message(state, sent_msg.message_id)
    await clear_temp_contexts(state)
    await cb.answer()

@router.callback_query(F.data.startswith("tech_back_to_materials_"))
async def tech_back_to_materials(cb: CallbackQuery, state: FSMContext):
    st = await state.get_data(); lang = st.get("lang") or await resolve_lang(cb.from_user.id)
    try:
        req_id = int(cb.data.replace("tech_back_to_materials_", ""))
    except Exception:
        return await cb.answer()
    user = await find_user_by_telegram_id(cb.from_user.id)
    if not user or user.get("role") != "technician":
        return await cb.answer(t("no_perm", lang), show_alert=True)

    # Purge tracked messages and delete current message
    await purge_tracked_messages(state, cb.message.chat.id)
    try:
        await cb.message.delete()
    except Exception:
        pass

    mode = st.get("tech_mode", "connection")
    
    # 🟢 YANGI YONDASHUV: To'g'ridan-to'g'ri DB'dan olish
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        if mode == "technician":
            query = """
                SELECT * FROM technician_orders 
                WHERE id = $1
            """
        elif mode == "staff":
            query = """
                SELECT * FROM staff_orders 
                WHERE id = $1
            """
        else:
            query = """
                SELECT * FROM connection_orders 
                WHERE id = $1
            """
        
        item = await conn.fetchrow(query, req_id)
        
        if not item:
            return await cb.answer(
                "❌ Ariza topilmadi" if lang == "uz" else "❌ Заявка не найдена",
                show_alert=True
            )
        
        item = dict(item)
        
    finally:
        await conn.close()
    
    # Restore original text with [Ombor] [Yakuniy ko'rinish] buttons
    original_text = short_view_text(item, 0, 1, lang, mode)
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=t("warehouse", lang), callback_data=f"tech_add_more_{req_id}"),
            InlineKeyboardButton(text=t("review", lang), callback_data=f"tech_review_{req_id}"),
        ]
    ])
    
    sent_msg = await cb.message.answer(original_text, reply_markup=kb, parse_mode="HTML")
    await track_message(state, sent_msg.message_id)
    await clear_temp_contexts(state)
    await cb.answer()

@router.callback_query(F.data.startswith("tech_finish_"))
async def tech_finish(cb: CallbackQuery, state: FSMContext):
    st = await state.get_data(); lang = st.get("lang") or await resolve_lang(cb.from_user.id)
    try:
        req_id = int(cb.data.replace("tech_finish_", ""))
    except Exception:
        return await cb.answer()

    user = await find_user_by_telegram_id(cb.from_user.id)
    if not user or user.get("role") != "technician":
        return await cb.answer(t("no_perm", lang), show_alert=True)

    mode = st.get("tech_mode", "connection")
    # Application number ni olish va materiallarni olish
    app_number = await get_application_number(req_id, mode)
    selected = await fetch_selected_materials_for_request(user["id"], app_number)

    # Request type ni avval aniqlash
    if mode == "technician":
        request_type = "technician"
    elif mode == "staff":
        request_type = "staff"
    else:
        request_type = "connection"

    # MUHIM: Yakunlashda FAQAT material_issued ga yozish
    # Material_and_technician allaqachon selection vaqtida kamaytirilgan!
    if selected:
        try:
            from database.technician.materials import create_material_issued_from_review
            await create_material_issued_from_review(
                user_id=user["id"],
                application_number=app_number,
                request_type=request_type
            )
        except Exception as e:
            logger.error(f"Error creating material_issued: {e}")

    try:
        # Status o'zgarmaydi! Oddiy finish_technician_work chaqirish
        if mode == "technician":
            ok = await finish_technician_work_for_tech(applications_id=req_id, technician_id=user["id"])
        elif mode == "staff":
            ok = await finish_technician_work_for_staff(applications_id=req_id, technician_id=user["id"])
        else:
            ok = await finish_technician_work(applications_id=req_id, technician_id=user["id"])
        
        if not ok:
            return await cb.answer(t("status_mismatch_finish", lang), show_alert=True)
    except Exception as e:
        return await cb.answer(f"{t('x_error', lang)} {e}", show_alert=True)

    # Purge tracked messages and delete current message
    await purge_tracked_messages(state, cb.message.chat.id)
    try:
        await cb.message.delete()
    except Exception:
        pass

    lines = [t("work_finished", lang) + "\n", f"{t('order_id', lang)} {esc(app_number)}", t("used_materials", lang)]
    if selected:
        for it in selected:
            qty_txt = f"{_qty_of(it)} {'dona' if lang=='uz' else 'шт'}"
            lines.append(f"• {esc(it['name'])} — {qty_txt}")
    else:
        lines.append(T["none"][lang])

    # Send completion summary (no inline buttons) - don't track this message
    await cb.message.answer("\n".join(lines), parse_mode="HTML")
    await cb.answer(t("finish", lang) + " ✅")

    # Clear all temporary contexts
    await clear_temp_contexts(state)

    try:
        # Avval clientga ariza haqida ma'lumot yuboramiz va rating so'ramiz
        from utils.completion_notification import send_completion_notification_to_client
        await send_completion_notification_to_client(cb.bot, req_id, request_type)
    except Exception as e:
        logger.error(f"Error sending completion notification: {e}")
        # Notification xatosi jarayonni to'xtatmaydi

@router.callback_query(F.data.startswith("tech_add_more_"))
async def tech_add_more(cb: CallbackQuery, state: FSMContext):
    st = await state.get_data(); lang = st.get("lang") or await resolve_lang(cb.from_user.id)
    req_id = int(cb.data.replace("tech_add_more_", ""))
    user = await find_user_by_telegram_id(cb.from_user.id)
    if not user or user.get("role") != "technician":
        return await cb.answer(t("no_perm", lang), show_alert=True)

    # Purge tracked messages and delete current message
    await purge_tracked_messages(state, cb.message.chat.id)
    try:
        await cb.message.delete()
    except Exception:
        pass

    mode = st.get("tech_mode", "connection")
    
    # 🟢 YANGI YONDASHUV: To'g'ridan-to'g'ri DB'dan olish
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        if mode == "technician":
            query = """
                SELECT 
                    to2.*,
                    to2.description_ish AS diagnostics,
                    COALESCE(client_user.full_name, user_user.full_name) AS client_name,
                    COALESCE(client_user.phone, user_user.phone) AS client_phone
                FROM technician_orders to2
                LEFT JOIN users client_user ON client_user.id::text = to2.abonent_id
                LEFT JOIN users user_user ON user_user.id = to2.user_id
                WHERE to2.id = $1
            """
        elif mode == "staff":
            query = """
                SELECT 
                    so.*,
                    COALESCE(client_user.full_name, 'Mijoz') AS client_name,
                    COALESCE(client_user.phone, so.phone) AS client_phone,
                    creator.full_name AS staff_creator_name,
                    creator.phone AS staff_creator_phone,
                    creator.role AS staff_creator_role
                FROM staff_orders so
                LEFT JOIN users client_user ON client_user.id::text = so.abonent_id
                LEFT JOIN users creator ON creator.id = so.user_id
                WHERE so.id = $1
            """
        else:
            query = """
                SELECT 
                    co.*,
                    u.full_name AS client_name,
                    u.phone AS client_phone
                FROM connection_orders co
                LEFT JOIN users u ON u.id = co.user_id
                WHERE co.id = $1
            """
        
        item = await conn.fetchrow(query, req_id)
        
        if not item:
            return await cb.answer(
                "❌ Ariza topilmadi" if lang == "uz" else "❌ Заявка не найдена",
                show_alert=True
            )
        
        item = dict(item)
        
    finally:
        await conn.close()
    
    # Build text with order details (materials list olib tashlandi)
    original_text = short_view_text(item, 0, 1, lang, mode)
    
    # Get technician's materials only
    mats = await fetch_technician_materials(user_id=user["id"])
    
    # Combine original text (materials text qo'shilmadi)
    full_text = original_text
    
    # Yangi xabar yuborish (edit emas)
    kb = materials_keyboard(mats, applications_id=req_id, lang=lang)
    sent_msg = await cb.message.answer(full_text, reply_markup=kb, parse_mode="HTML")
    await track_message(state, sent_msg.message_id)
    await cb.answer()

@router.callback_query(F.data.startswith("tech_review_"))
async def tech_review(cb: CallbackQuery, state: FSMContext):
    st = await state.get_data(); lang = st.get("lang") or await resolve_lang(cb.from_user.id)
    req_id = int(cb.data.replace("tech_review_", ""))    
    user = await find_user_by_telegram_id(cb.from_user.id)
    if not user or user.get("role") != "technician":
        return await cb.answer(t("no_perm", lang), show_alert=True)

    # Purge tracked messages and delete current message
    await purge_tracked_messages(state, cb.message.chat.id)
    try:
        await cb.message.delete()
    except Exception:
        pass

    # Application number ni olish
    mode = st.get("tech_mode", "connection")
    app_number = await get_application_number(req_id, mode)
    
    # Material_issued ga yozmaslik - faqat Yakunlash bosganda yoziladi!
    
    # 🟢 YANGI YONDASHUV: To'g'ridan-to'g'ri DB'dan olish
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        if mode == "technician":
            query = """
                SELECT 
                    to2.*,
                    to2.description_ish AS diagnostics,
                    COALESCE(client_user.full_name, user_user.full_name) AS client_name,
                    COALESCE(client_user.phone, user_user.phone) AS client_phone
                FROM technician_orders to2
                LEFT JOIN users client_user ON client_user.id::text = to2.abonent_id
                LEFT JOIN users user_user ON user_user.id = to2.user_id
                WHERE to2.id = $1
            """
        elif mode == "staff":
            query = """
                SELECT 
                    so.*,
                    COALESCE(client_user.full_name, 'Mijoz') AS client_name,
                    COALESCE(client_user.phone, so.phone) AS client_phone,
                    creator.full_name AS staff_creator_name,
                    creator.phone AS staff_creator_phone,
                    creator.role AS staff_creator_role
                FROM staff_orders so
                LEFT JOIN users client_user ON client_user.id::text = so.abonent_id
                LEFT JOIN users creator ON creator.id = so.user_id
                WHERE so.id = $1
            """
        else:
            query = """
                SELECT 
                    co.*,
                    u.full_name AS client_name,
                    u.phone AS client_phone
                FROM connection_orders co
                LEFT JOIN users u ON u.id = co.user_id
                WHERE co.id = $1
            """
        
        item = await conn.fetchrow(query, req_id)
        
        if not item:
            return await cb.answer(
                "❌ Ariza topilmadi" if lang == "uz" else "❌ Заявка не найдена",
                show_alert=True
            )
        
        item = dict(item)
        
    finally:
        await conn.close()
    
    # Build text with order details + materials list
    original_text = short_view_text(item, 0, 1, lang, mode)
    
    # Application number ni olish va materiallarni olish
    app_number = await get_application_number(req_id, mode)
    selected = await fetch_selected_materials_for_request(user["id"], app_number)
    materials_text = "\n\n📦 <b>Ishlatilgan mahsulotlar:</b>\n"
    
    if selected:
        currency_unit = 'so\'m' if lang=='uz' else 'сум'
        unit_name = 'dona' if lang=='uz' else 'шт'
        for it in selected:
            qty_txt = f"{_qty_of(it)} {unit_name}"
            price_txt = f"{_fmt_price_uzs(it['price'])} {currency_unit}"
            # Source indicator
            source_indicator = ""
            if it.get('source_type') == 'technician_stock':
                source_indicator = " [🧑‍🔧 O'zimda]" if lang == 'uz' else " [🧑‍🔧 У меня]"
            elif it.get('source_type') == 'warehouse':
                source_indicator = " [🏢 Ombordan]" if lang == 'uz' else " [🏢 Со склада]"
            materials_text += f"• {esc(it['name'])} — {qty_txt} (💰 {price_txt}){source_indicator}\n"
    else:
        materials_text += "• (tanlanmagan)\n"
    
    # Check if there are warehouse materials that need confirmation
    warehouse_mats = [m for m in selected if m.get('source_type') == 'warehouse']
    
    if warehouse_mats:
        # Show warehouse confirmation dialog
        warehouse_text = "\n\n🏢 <b>Ombordan so'ralgan mahsulotlar:</b>\n"
        for mat in warehouse_mats:
            qty_txt = f"{_qty_of(mat)} {'dona' if lang=='uz' else 'шт'}"
            warehouse_text += f"• {esc(mat['name'])} — {qty_txt}\n"
        warehouse_text += "\n\nOmborga yuborish tasdiqlaysizmi?"
        
        full_text = original_text + materials_text + warehouse_text
        
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"tech_confirm_warehouse_{req_id}")],
            [InlineKeyboardButton(text="❌ Bekor qilish", callback_data=f"tech_back_to_order_{req_id}")],
            [InlineKeyboardButton(text=t("back", lang), callback_data=f"tech_back_to_order_{req_id}")]
        ])
    else:
        # No warehouse materials, show regular buttons
        full_text = original_text + materials_text
        
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=t("finish", lang), callback_data=f"tech_finish_{req_id}")],
            [InlineKeyboardButton(text=t("cancel_order", lang), callback_data=f"tech_cancel_order_{req_id}")],
            [InlineKeyboardButton(text=t("back", lang), callback_data=f"tech_back_to_order_{req_id}")]
        ])
    
    sent_msg = await cb.message.answer(full_text, reply_markup=kb, parse_mode="HTML")
    await track_message(state, sent_msg.message_id)
    await cb.answer()

@router.callback_query(F.data.startswith("tech_confirm_warehouse_"))
async def tech_confirm_warehouse(cb: CallbackQuery, state: FSMContext):
    st = await state.get_data()
    lang = st.get("lang") or await resolve_lang(cb.from_user.id)
    req_id = int(cb.data.replace("tech_confirm_warehouse_", ""))
    
    user = await find_user_by_telegram_id(cb.from_user.id)
    if not user or user.get("role") != "technician":
        return await cb.answer(t("no_perm", lang), show_alert=True)
    
    mode = st.get("tech_mode", "connection")
    
    # Send to warehouse
    try:
        from database.technician.materials import send_selection_to_warehouse
        success = await send_selection_to_warehouse(
            applications_id=req_id,
            technician_user_id=user["id"],
            request_type=mode
        )
        
        if success:
            try:
                from loader import bot
                from database.connections import _conn
                
                # Warehouse user'ni topish
                conn = await _conn()
                warehouse_user = await conn.fetchrow("""
                    SELECT telegram_id, language FROM users 
                    WHERE role = 'warehouse' 
                    ORDER BY id ASC LIMIT 1
                """)
                
                if warehouse_user:
                    # Application number olish
                    app_number = await get_application_number(req_id, mode)
                    
                    # Notification matnini tayyorlash
                    recipient_lang = warehouse_user["language"] or "uz"
                    
                    if recipient_lang == "ru":
                        notification = f"📦 <b>Новый запрос материалов</b>\n\n🆔 {app_number}\n\n📋 Тип: {'Подключение' if mode == 'connection' else 'Техническое обслуживание' if mode == 'technician' else 'Сотрудник'}\n\n📊 Ожидает подтверждения склада"
                    else:
                        notification = f"📦 <b>Yangi material so'rovi</b>\n\n🆔 {app_number}\n\n📋 Tur: {'Ulanish' if mode == 'connection' else 'Texnik xizmat' if mode == 'technician' else 'Xodim'}\n\n📊 Ombor tasdigini kutmoqda"
                    
                    # Notification yuborish
                    await bot.send_message(
                        chat_id=warehouse_user["telegram_id"],
                        text=notification,
                        parse_mode="HTML"
                    )
                    logger.info(f"Notification sent to warehouse for order {app_number}")
            except Exception as notif_error:
                logger.error(f"Failed to send warehouse notification: {notif_error}")
                # Notification xatosi asosiy jarayonga ta'sir qilmaydi
            
            # Purge tracked messages and delete current message
            await purge_tracked_messages(state, cb.message.chat.id)
            try:
                await cb.message.delete()
            except Exception:
                pass
            
            # Show finish/cancel/back buttons
            # 🟢 YANGI YONDASHUV: To'g'ridan-to'g'ri DB'dan olish
            conn = await asyncpg.connect(settings.DB_URL)
            try:
                if mode == "technician":
                    query = """
                        SELECT * FROM technician_orders 
                        WHERE id = $1
                    """
                elif mode == "staff":
                    query = """
                        SELECT * FROM staff_orders 
                        WHERE id = $1
                    """
                else:
                    query = """
                        SELECT * FROM connection_orders 
                        WHERE id = $1
                    """
                
                item = await conn.fetchrow(query, req_id)
                
                if not item:
                    return await cb.answer(
                        "❌ Ariza topilmadi" if lang == "uz" else "❌ Заявка не найдена",
                        show_alert=True
                    )
                
                item = dict(item)
                
            finally:
                await conn.close()
            
            # Build text with order details + materials list
            original_text = short_view_text(item, 0, 1, lang, mode)
            
            # Application number ni olish va materiallarni olish
            app_number = await get_application_number(req_id, mode)
            selected = await fetch_selected_materials_for_request(user["id"], app_number)
            materials_text = "\n\n📦 <b>Ishlatilgan mahsulotlar:</b>\n"
            
            if selected:
                currency_unit = 'so\'m' if lang=='uz' else 'сум'
                unit_name = 'dona' if lang=='uz' else 'шт'
                for it in selected:
                    qty_txt = f"{_qty_of(it)} {unit_name}"
                    price_txt = f"{_fmt_price_uzs(it['price'])} {currency_unit}"
                    # Source indicator
                    source_indicator = ""
                    if it.get('source_type') == 'technician_stock':
                        source_indicator = " [🧑‍🔧 O'zimda]" if lang == 'uz' else " [🧑‍🔧 У меня]"
                    elif it.get('source_type') == 'warehouse':
                        source_indicator = " [🏢 Ombordan]" if lang == 'uz' else " [🏢 Со склада]"
                    materials_text += f"• {esc(it['name'])} — {qty_txt} (💰 {price_txt}){source_indicator}\n"
            else:
                materials_text += "• (tanlanmagan)\n"
            
            full_text = original_text + materials_text + "\n\n✅ Omborga yuborildi!"
            
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text=t("finish", lang), callback_data=f"tech_finish_{req_id}")],
                [InlineKeyboardButton(text=t("cancel_order", lang), callback_data=f"tech_cancel_order_{req_id}")],
                [InlineKeyboardButton(text=t("back", lang), callback_data=f"tech_back_to_order_{req_id}")]
            ])
            
            sent_msg = await cb.message.answer(full_text, reply_markup=kb, parse_mode="HTML")
            await track_message(state, sent_msg.message_id)
            try:
                await cb.answer("✅ Omborga yuborildi!")
            except Exception:
                pass  # Ignore callback timeout errors
        else:
            try:
                await cb.answer("❌ Xatolik yuz berdi", show_alert=True)
            except Exception:
                pass  # Ignore callback timeout errors
    except Exception as e:
        logger.error(f"Error sending to warehouse: {e}")
        try:
            await cb.answer("❌ Xatolik yuz berdi", show_alert=True)
        except Exception:
            pass  # Ignore callback timeout errors

@router.callback_query(F.data.startswith("tech_cancel_order_"))
async def tech_cancel_order(cb: CallbackQuery, state: FSMContext):
    """Arizani bekor qilish - avval sabab so'rash"""
    await cb.answer()
    st = await state.get_data()
    lang = st.get("lang") or await resolve_lang(cb.from_user.id)
    req_id = int(cb.data.replace("tech_cancel_order_", ""))
    
    user = await find_user_by_telegram_id(cb.from_user.id)
    if not user or user.get("role") != "technician":
        return await cb.answer(t("no_perm", lang), show_alert=True)
    
    # Texnik arizani bekor qilish huquqiga ega
    # Faqat texnik rolini tekshirish kifoya
    
    # Purge tracked messages and delete current message
    await purge_tracked_messages(state, cb.message.chat.id)
    try:
        await cb.message.delete()
    except Exception:
        pass
    
    # Bekor qilish sababini so'rash
    await state.update_data(cancel_req_id=req_id)
    await state.set_state(CancellationStates.waiting_note)
    
    sent_msg = await cb.message.answer(
        t("cancel_reason_prompt", lang),
        parse_mode="HTML"
    )
    await track_message(state, sent_msg.message_id)

@router.message(StateFilter(CancellationStates.waiting_note))
async def tech_cancellation_note(msg: Message, state: FSMContext):
    """Bekor qilish sababini qabul qilish va jarayonni yakunlash"""
    user = await find_user_by_telegram_id(msg.from_user.id)
    st = await state.get_data()
    lang = st.get("lang") or await resolve_lang(msg.from_user.id)
    
    if not user or user.get("role") != "technician":
        return await msg.answer(t("no_perm", lang))
    
    req_id = int(st.get("cancel_req_id", 0))
    if req_id <= 0:
        await clear_temp_contexts(state)
        return await msg.answer(t("req_not_found", lang))
    
    note = (msg.text or "").strip()
    if not note:
        return await msg.answer("❌ Bekor qilish sababini kiriting" if lang == "uz" else "❌ Введите причину отмены")
    
    mode = st.get("tech_mode", "connection")
    
    # Application number ni olish
    app_number = await get_application_number(req_id, mode)
    
    # Materiallarni qaytarish va ma'lumotlarni tozalash
    try:
        from database.technician.materials import restore_technician_materials_on_cancel
        await restore_technician_materials_on_cancel(user["id"], app_number)
    except Exception as e:
        logger.error(f"Error restoring materials on cancel: {e}")
    
    # Arizani bekor qilish va sababni saqlash
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        if mode == "technician":
            await conn.execute(
                "UPDATE technician_orders SET status='cancelled', cancellation_note=$2, updated_at=NOW() WHERE id=$1",
                req_id, note
            )
        elif mode == "staff":
            # staff_orders da cancellation_note yo'q, faqat statusni o'zgartiramiz
            await conn.execute(
                "UPDATE staff_orders SET status='cancelled', updated_at=NOW() WHERE id=$1",
                req_id
            )
        else:
            await conn.execute(
                "UPDATE connection_orders SET status='cancelled'::connection_order_status, cancellation_note=$2, updated_at=NOW() WHERE id=$1",
                req_id, note
            )
    finally:
        await conn.close()
    
    # Inbox'dan o'chirish va keyingi arizani ko'rsatish (state tozalashdan oldin!)
    items = _dedup_by_id(st.get("tech_inbox", []))
    items = [it for it in items if it.get("id") != req_id]
    
    # Purge tracked messages and delete user's text input
    await purge_tracked_messages(state, msg.chat.id)
    try:
        await msg.delete()
    except Exception:
        pass
    
    # Clear state (including cancellation state)
    await state.clear()
    
    # Send confirmation message (no inline buttons) - don't track this message
    await msg.answer(t("cancel_success", lang))
    
    # Keyingi arizani ko'rsatish
    if items:
        await state.update_data(tech_inbox=items, tech_idx=0, tech_mode=mode, lang=lang)
        item = items[0]
        text = await short_view_text_with_materials(item, 0, len(items), user["id"], lang, mode)
        kb = await action_keyboard(item.get("id"), 0, len(items), item.get("status", ""), mode=mode, lang=lang, item=item)
        sent_msg = await msg.answer(text, reply_markup=kb, parse_mode="HTML")
        await track_message(state, sent_msg.message_id)
    else:
        await msg.answer("📭 Inbox bo'sh" if lang == "uz" else "📭 Входящие пусты")

@router.callback_query(F.data.startswith("tech_mat_custom_"))
async def tech_mat_custom(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    st = await state.get_data(); lang = st.get("lang") or await resolve_lang(cb.from_user.id)
    try:
        req_id = int(cb.data.replace("tech_mat_custom_", ""))
    except Exception:
        return
    
    user = await find_user_by_telegram_id(cb.from_user.id)
    if not user or user.get("role") != "technician":
        return await cb.answer(t("no_perm", lang), show_alert=True)
    
    # Purge tracked messages and delete current message
    await purge_tracked_messages(state, cb.message.chat.id)
    try:
        await cb.message.delete()
    except Exception:
        pass
    
    # Get all materials (25 total) and filter out technician's materials (7 items)
    # Result: 18 materials from warehouse only
    all_mats = await fetch_all_materials(limit=200, offset=0)
    tech_mats = await fetch_technician_materials(user_id=user["id"])
    
    # Get technician's material IDs
    tech_material_ids = {mat['material_id'] for mat in tech_mats}
    
    # Filter out materials that technician already has
    warehouse_mats = [mat for mat in all_mats if mat['material_id'] not in tech_material_ids]
    
    if not warehouse_mats:
        sent_msg = await cb.message.answer(
            ("📦 Ombordan qo'shimcha materiallar yo'q" if lang == "uz" else "📦 Нет дополнительных материалов на складе"),
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text=t("back", lang), callback_data=f"tech_back_to_order_{req_id}")]
            ])
        )
        await track_message(state, sent_msg.message_id)
        return

    # Application number ni olish
    mode = st.get("tech_mode", "connection")
    app_number = await get_application_number(req_id, mode)
    
    header_text = ("📦 <b>Ombordan qo'shimcha materiallar</b>\n🆔 <b>Ariza ID:</b> {id}\nKerakli materialni tanlang:" if lang == "uz" else "📦 <b>Дополнительные материалы со склада</b>\n🆔 <b>ID заявки:</b> {id}\nВыберите нужный материал:")
    
    # Send new message instead of editing
    sent_msg = await cb.message.answer(
        header_text.format(id=app_number), 
        reply_markup=unassigned_materials_keyboard(warehouse_mats, applications_id=req_id, lang=lang),
        parse_mode="HTML"
    )
    await track_message(state, sent_msg.message_id)

@router.callback_query(F.data.startswith("tech_unassigned_select_"))
async def tech_unassigned_select(cb: CallbackQuery, state: FSMContext):
    """Texnikka biriktirilmagan materialni tanlash"""
    await cb.answer()
    st = await state.get_data(); lang = st.get("lang") or await resolve_lang(cb.from_user.id)
    try:
        payload = cb.data[len("tech_unassigned_select_"):]
        material_id, req_id = map(int, payload.split("_", 1))
    except Exception:
        return

    mat = await fetch_material_by_id(material_id)
    if not mat:
        return await cb.answer(t("not_found_mat", lang), show_alert=True)

    # Purge tracked messages and delete current message
    await purge_tracked_messages(state, cb.message.chat.id)
    try:
        await cb.message.delete()
    except Exception:
        pass

    mode = st.get("tech_mode", "connection")
    app_number = await get_application_number(req_id, mode)
    currency_unit = 'so\'m' if lang=='uz' else 'сум'
    
    text = (
        f"📦 <b>{t('product', lang)}:</b> {esc(mat['name'])}\n"
        f"💰 <b>{t('price_line', lang)}:</b> {_fmt_price_uzs(mat.get('price',0))} {currency_unit}\n"
        f"🆔 <b>{t('order', lang)}:</b> {esc(app_number)}\n\n"
        f"{'Miqdorini kiriting:' if lang=='uz' else 'Введите количество:'}"
    )
    
    await state.update_data(
        current_application_id=req_id,
        qty_ctx={
            "applications_id": req_id,
            "material_id": material_id,
            "material_name": mat["name"],
            "price": mat["price"],
            "max_qty": 999,  
            "lang": lang,
            "source_type": "warehouse",
            "qty_message_id": None  # Will be set after sending message
        }
    )
    
    # Show quantity input prompt with cancel and back buttons
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t("btn_cancel", lang), callback_data=f"tech_qty_cancel_{req_id}")],
        [InlineKeyboardButton(text=t("back", lang), callback_data=f"tech_back_to_order_{req_id}")]
    ])
    
    qty_message = await cb.message.answer(text, reply_markup=kb, parse_mode="HTML")
    await track_message(state, qty_message.message_id)
    
    # Update qty_message_id in context
    await state.update_data(
        qty_ctx={
            "applications_id": req_id,
            "material_id": material_id,
            "material_name": mat["name"],
            "price": mat["price"],
            "max_qty": 999,  
            "lang": lang,
            "source_type": "warehouse",
            "qty_message_id": qty_message.message_id
        }
    )
    
    await state.set_state(QtyStates.waiting_qty)

@router.callback_query(F.data.startswith("tech_custom_select_"))
async def tech_custom_select(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    st = await state.get_data(); lang = st.get("lang") or await resolve_lang(cb.from_user.id)
    try:
        payload = cb.data[len("tech_custom_select_"):]
        material_id, req_id = map(int, payload.split("_", 1))
    except Exception:
        return

    mat = await fetch_material_by_id(material_id)
    if not mat:
        return await cb.answer(t("not_found_mat", lang), show_alert=True)

    # Material ma'lumotlarini ko'rsatish va tasdiqlash so'rash
    mode = st.get("tech_mode", "connection")
    app_number = await get_application_number(req_id, mode)
    
    currency_unit = 'so\'m' if lang=='uz' else 'сум'
    text = (
        f"📦 <b>{t('product', lang)}:</b> {esc(mat['name'])}\n"
        f"💰 <b>{t('price_line', lang)}:</b> {_fmt_price_uzs(mat.get('price',0))} {currency_unit}\n\n"
        f"{'Bu materialni tanlamoqchimisiz?' if lang=='uz' else 'Хотите выбрать этот материал?'}"
    )
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="✅ Ha" if lang=='uz' else "✅ Да", 
                callback_data=f"tech_confirm_custom_{material_id}_{req_id}"
            ),
            InlineKeyboardButton(
                text="❌ Yo'q" if lang=='uz' else "❌ Нет", 
                callback_data=f"tech_back_to_materials_{req_id}"
            )
        ]
    ])

    await cb.message.answer(text, reply_markup=kb, parse_mode="HTML")

@router.callback_query(F.data.startswith("tech_confirm_unassigned_"))
async def tech_confirm_unassigned(cb: CallbackQuery, state: FSMContext):
    """Texnikka biriktirilmagan materialni tasdiqlagandan so'ng miqdor kiritish"""
    await cb.answer()
    st = await state.get_data(); lang = st.get("lang") or await resolve_lang(cb.from_user.id)
    
    try:
        payload = cb.data[len("tech_confirm_unassigned_"):]
        material_id, req_id = map(int, payload.split("_", 1))
    except Exception:
        return

    mat = await fetch_material_by_id(material_id)
    if not mat:
        return await cb.answer(t("not_found_mat", lang), show_alert=True)

    await state.update_data(unassigned_ctx={
        "applications_id": req_id,
        "material_id": material_id,
        "material_name": mat["name"],
        "price": mat.get("price", 0),
        "lang": lang,
    })

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t("btn_cancel", lang), callback_data=f"tech_back_to_materials_{req_id}")]
    ])

    # Application number ni olish
    mode = st.get("tech_mode", "connection")
    app_number = await get_application_number(req_id, mode)
    currency_unit = 'so\'m' if lang=='uz' else 'сум'
    warning_msg = '⚠️ Bu material texnikka biriktirilmagan. Omborchi tasdiqlagandan so\'ng texnikka biriktiriladi.' if lang=='uz' else '⚠️ Этот материал не привязан к технику. После подтверждения склада будет привязан к технику.'
    
    await cb.message.answer(
        f"{t('qty_title', lang)}\n\n"
        f"{t('order', lang)} {esc(app_number)}\n"
        f"{t('product', lang)} {esc(mat['name'])}\n"
        f"{t('price_line', lang)} {_fmt_price_uzs(mat.get('price',0))} {currency_unit}\n\n"
        f"{'Miqdorni kiriting (faqat raqam):' if lang=='uz' else 'Введите количество (только число):'}\n\n"
        f"{warning_msg}",
        reply_markup=kb,
        parse_mode="HTML"
    )
    await state.set_state(CustomQtyStates.waiting_qty)

@router.callback_query(F.data.startswith("tech_confirm_custom_"))
async def tech_confirm_custom(cb: CallbackQuery, state: FSMContext):
    """Materialni tasdiqlagandan so'ng source_type so'rash"""
    await cb.answer()
    st = await state.get_data(); lang = st.get("lang") or await resolve_lang(cb.from_user.id)
    
    try:
        payload = cb.data[len("tech_confirm_custom_"):]
        material_id, req_id = map(int, payload.split("_", 1))
    except Exception:
        return

    mat = await fetch_material_by_id(material_id)
    if not mat:
        return await cb.answer(t("not_found_mat", lang), show_alert=True)

    await state.update_data(custom_ctx={
        "applications_id": req_id,
        "material_id": material_id,
        "material_name": mat["name"],
        "price": mat.get("price", 0),
        "lang": lang,
    })

    # Application number ni olish
    mode = st.get("tech_mode", "connection")
    app_number = await get_application_number(req_id, mode)
    
    # Source type tanlash tugmalari
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🧑‍🔧 O'zimda" if lang=='uz' else "🧑‍🔧 У меня", callback_data=f"tech_source_technician_{material_id}_{req_id}"),
            InlineKeyboardButton(text="🏢 Ombordan" if lang=='uz' else "🏢 Со склада", callback_data=f"tech_source_warehouse_{material_id}_{req_id}")
        ],
        [InlineKeyboardButton(text=t("btn_cancel", lang), callback_data=f"tech_back_to_materials_{req_id}")]
    ])
    
    currency_unit = 'so\'m' if lang=='uz' else 'сум'
    await cb.message.answer(
        f"📦 <b>{t('product', lang)}:</b> {esc(mat['name'])}\n"
        f"💰 <b>{t('price_line', lang)}:</b> {_fmt_price_uzs(mat.get('price',0))} {currency_unit}\n"
        f"🆔 <b>{t('order', lang)}:</b> {esc(app_number)}\n\n"
        f"{'Material qayerdan olinadi?' if lang=='uz' else 'Откуда взять материал?'}",
        reply_markup=kb,
        parse_mode="HTML"
    )
    await state.set_state(CustomQtyStates.waiting_qty)

@router.callback_query(F.data.startswith("tech_source_"))
async def tech_source_type_selected(cb: CallbackQuery, state: FSMContext):
    """Source type tanlangandan so'ng miqdor kiritish"""
    await cb.answer()
    st = await state.get_data(); lang = st.get("lang") or await resolve_lang(cb.from_user.id)
    
    try:
        payload = cb.data[len("tech_source_"):]
        parts = payload.split("_")
        if len(parts) != 3:
            raise ValueError("Invalid format")
        source_type, material_id, req_id = parts[0], int(parts[1]), int(parts[2])
    except Exception:
        return

    mat = await fetch_material_by_id(material_id)
    if not mat:
        return await cb.answer(t("not_found_mat", lang), show_alert=True)

    # Source type ni context ga qo'shish
    custom_ctx = st.get("custom_ctx", {})
    custom_ctx.update({
        "applications_id": req_id,
        "material_id": material_id,
        "material_name": mat["name"],
        "price": mat.get("price", 0),
        "source_type": source_type,
        "lang": lang,
    })
    await state.update_data(custom_ctx=custom_ctx)

    # Application number ni olish
    mode = st.get("tech_mode", "connection")
    app_number = await get_application_number(req_id, mode)
    
    # Miqdor kiritish uchun keyboard
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t("btn_cancel", lang), callback_data=f"tech_back_to_materials_{req_id}")]
    ])
    
    source_text = "🧑‍🔧 O'zimda" if source_type == "technician" else "🏢 Ombordan"
    if lang != "uz":
        source_text = "🧑‍🔧 У меня" if source_type == "technician" else "🏢 Со склада"
    
    currency_unit = 'so\'m' if lang=='uz' else 'сум'
    await cb.message.answer(
        f"📦 <b>{t('product', lang)}:</b> {esc(mat['name'])}\n"
        f"💰 <b>{t('price_line', lang)}:</b> {_fmt_price_uzs(mat.get('price',0))} {currency_unit}\n"
        f"🆔 <b>{t('order', lang)}:</b> {esc(app_number)}\n"
        f"📍 <b>Manba:</b> {source_text}\n\n"
        f"{'Miqdorini kiriting:' if lang=='uz' else 'Введите количество:'}",
        reply_markup=kb,
        parse_mode="HTML"
    )
    await state.set_state(CustomQtyStates.waiting_qty)

@router.message(StateFilter(CustomQtyStates.waiting_qty))
async def custom_qty_entered(msg: Message, state: FSMContext):
    st = await state.get_data(); lang = st.get("lang") or await resolve_lang(msg.from_user.id)
    user = await find_user_by_telegram_id(msg.from_user.id)
    if not user or user.get("role") != "technician":
        return await msg.answer(t("no_perm", lang))

    # Texnikka biriktirilmagan materiallar uchun alohida kontekst
    unassigned_ctx = st.get("unassigned_ctx")
    if unassigned_ctx:
        req_id = int(unassigned_ctx.get("applications_id", 0))
        material_id = int(unassigned_ctx.get("material_id", 0))
        material_name = unassigned_ctx.get("material_name", "")
        
        try:
            qty = int((msg.text or "").strip())
            if qty <= 0:
                return await msg.answer(t("gt_zero", lang))
        except Exception:
            return await msg.answer(t("only_int", lang))

        # Texnikka biriktirilmagan material uchun faqat tanlov saqlash
        try:
            mode = st.get("tech_mode", "connection")
            await upsert_material_selection(
                user_id=user["id"],
                application_id=req_id,
                material_id=material_id,
                qty=qty,
                request_type=mode,
                source_type="warehouse"  # Unassigned materials are from warehouse
            )
        except Exception as e:
            return await msg.answer(f"{t('x_error', lang)} {e}")

        # Application number ni olish
        mode = st.get("tech_mode", "connection")
        app_number = await get_application_number(req_id, mode)
        
        # Xabar yuborish
        unit_name = 'dona' if lang=='uz' else 'шт'
        confirmation_msg = 'Omborchi tasdiqlagandan so\'ng material texnikka biriktiriladi' if lang=='uz' else 'После подтверждения склада материал будет привязан к технику'
        add_more_msg = 'Yana material qo\'shish uchun \"Ombor\" tugmasini bosing' if lang=='uz' else 'Для добавления ещё материалов нажмите кнопку \"Склад\"'
        await msg.answer(
            f"✅ <b>Material omborga so'rov yuborildi</b>\n\n"
            f"📦 <b>Material:</b> {esc(material_name)}\n"
            f"📊 <b>Miqdor:</b> {qty} {unit_name}\n"
            f"🆔 <b>Ariza ID:</b> {esc(app_number)}\n\n"
            f"{confirmation_msg}\n\n"
            f"{add_more_msg}",
            parse_mode="HTML"
        )
        
        await _preserve_mode_clear(state)
        return

    ctx  = st.get("custom_ctx") or {}
    req_id      = int(ctx.get("applications_id", 0))
    material_id = int(ctx.get("material_id", 0))
    if not (req_id and material_id):
        await _preserve_mode_clear(state)
        return await msg.answer(t("ctx_lost", lang))

    try:
        qty = int((msg.text or "").strip())
        if qty <= 0:
            return await msg.answer(t("gt_zero", lang))
    except Exception:
        return await msg.answer(t("only_int", lang))

    mode = st.get("tech_mode", "connection")
    request_type = "technician" if mode == "technician" else ("staff" if mode == "staff" else "connection")

    try:
        mode = st.get("tech_mode", "connection")
        source_type = ctx.get("source_type", "warehouse") 
        await upsert_material_selection(
            user_id=user["id"],
            applications_id=req_id,
            material_id=material_id,
            qty=qty,
            request_type=mode,
            source_type=source_type
        )
    except Exception as e:
        return await msg.answer(f"{t('x_error', lang)} {e}")

    mode = st.get("tech_mode", "connection")
    app_number = await get_application_number(req_id, mode)
    
    selected = await fetch_selected_materials_for_request(user["id"], app_number)
    lines = [t("saved_selection", lang) + "\n", f"{t('order_id', lang)} {esc(app_number)}", t("selected_products", lang)]
    currency_unit = 'so\'m' if lang=='uz' else 'сум'
    unit_name = 'dona' if lang=='uz' else 'шт'
    for it in selected:
        qty_txt = f"{_qty_of(it)} {unit_name}"
        price_txt = f"{_fmt_price_uzs(it['price'])} {currency_unit}"
        lines.append(f"• {esc(it['name'])} — {qty_txt} (💰 {price_txt})")

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t("add_more", lang), callback_data=f"tech_add_more_{req_id}")],
        [InlineKeyboardButton(text=t("final_view", lang), callback_data=f"tech_review_{req_id}")]
    ])
    
    await _preserve_mode_clear(state)
    await msg.answer("\n".join(lines), reply_markup=kb, parse_mode="HTML")
