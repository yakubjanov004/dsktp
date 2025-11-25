# handlers/manager/applications.py

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
import html
import logging
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from typing import Optional, List, Dict, Any

from filters.role_filter import RoleFilter
from database.basic.user import get_user_by_telegram_id
from database.manager.orders import (
    get_all_total_connection_orders_count,
    get_all_new_orders_count,
    get_in_progress_count,
    get_completed_today_count,
    get_cancelled_count,
    get_all_cancelled_count,
    get_new_orders_today_count,
    list_new_orders,
    list_all_in_progress_orders,
    get_all_in_progress_count,
    list_completed_today_orders,
    list_cancelled_orders,
    list_my_created_orders_by_type,
)

router = Router()
router.message.filter(RoleFilter("manager"))
router.callback_query.filter(RoleFilter("manager"))

def _safe_tz(key: str):
    try:
        return ZoneInfo(key)
    except ZoneInfoNotFoundError:
        return timezone(timedelta(hours=5))  

TZ = _safe_tz("Asia/Tashkent")

def _to_tz(dt):
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(TZ)

T = {
    # Titles
    "title_panel":    {"uz": "🗂 <b>Buyurtmalar nazorati</b>", "ru": "🗂 <b>Контроль заявок</b>"},
    "title_choose":   {"uz": "Quyidagini tanlang:",             "ru": "Выберите категорию:"},
    "title_new":      {"uz": "🆕 <b>Yangi buyurtmalar</b>",     "ru": "🆕 <b>Новые заявки</b>"},
    "title_progress": {"uz": "⏳ <b>Jarayondagilar</b>",         "ru": "⏳ <b>В процессе</b>"},
    "title_done":     {"uz": "✅ <b>Bugun bajarilgan</b>",       "ru": "✅ <b>Выполнено сегодня</b>"},
    "title_cancel":   {"uz": "🚫 <b>Bekor qilinganlar</b>",      "ru": "🚫 <b>Отменённые</b>"},
    "title_fallback": {"uz": "🗂 <b>Buyurtmalar</b>",            "ru": "🗂 <b>Заявки</b>"},
    # 🆕 My created titles
    "title_my":       {"uz": "👤 <b>Men yaratgan arizalar</b>", "ru": "👤 <b>Мои заявки</b>"},
    "title_my_choose":{"uz": "Ariza turini tanlang:",           "ru": "Выберите тип заявки:"},
    "title_my_conn":  {"uz": "🔌 <b>Ulanish arizalari</b>",      "ru": "🔌 <b>Заявки на подключение</b>"},
    "title_my_tech":  {"uz": "🛠️ <b>Texnik arizalar</b>",       "ru": "🛠️ <b>Технические заявки</b>"},

    # Stats
    "stats":          {"uz": "📊 <b>Statistika:</b>",           "ru": "📊 <b>Статистика:</b>"},
    "total":          {"uz": "• Jami:",                         "ru": "• Всего:"},
    "new":            {"uz": "• Yangi:",                        "ru": "• Новые:"},
    "in_progress":    {"uz": "• Jarayonda:",                    "ru": "• В процессе:"},
    "done_today":     {"uz": "• Bugun bajarilgan:",             "ru": "• Выполнено сегодня:"},
    "cancelled":      {"uz": "• Bekor qilinganlar:",            "ru": "• Отменённые:"},

    # Buttons (menu)
    "btn_new":        {"uz": "🆕 Yangi buyurtmalar",             "ru": "🆕 Новые заявки"},
    "btn_progress":   {"uz": "⏳ Jarayondagilar",                 "ru": "⏳ В процессе"},
    "btn_done":       {"uz": "✅ Bugun bajarilgan",              "ru": "✅ Выполнено сегодня"},
    "btn_cancel":     {"uz": "🚫 Bekor qilinganlar",             "ru": "🚫 Отменённые"},
    "btn_refresh":    {"uz": "♻️ Yangilash",                    "ru": "♻️ Обновить"},
    "btn_close":      {"uz": "❌ Yopish",                        "ru": "❌ Закрыть"},
    "btn_back":       {"uz": "🔙 Orqaga",                        "ru": "🔙 Назад"},
    "btn_prev":       {"uz": "⬅️ Oldingi",                       "ru": "⬅️ Назад"},
    "btn_next":       {"uz": "Keyingi ➡️",                       "ru": "Вперёд ➡️"},
    # 🆕 My created (menu)
    "btn_my":         {"uz": "👤 Men yaratgan arizalar",         "ru": "👤 Мои заявки"},
    "btn_my_conn":    {"uz": "🔌 Ulanish arizalari",             "ru": "🔌 Заявки на подключение"},
    "btn_my_tech":    {"uz": "🛠️ Texnik arizalar",              "ru": "🛠️ Технические заявки"},

    # Labels in item card
    "card_title":     {"uz": "🗂 <b>Buyurtma</b>",               "ru": "🗂 <b>Заявка</b>"},
    "id":             {"uz": "🆔 <b>ID:</b>",                    "ru": "🆔 <b>ID:</b>"},
    "tariff":         {"uz": "📊 <b>Tarif:</b>",                 "ru": "📊 <b>Тариф:</b>"},
    "client":         {"uz": "👤 <b>Mijoz:</b>",                 "ru": "👤 <b>Клиент:</b>"},
    "phone":          {"uz": "📞 <b>Telefon:</b>",               "ru": "📞 <b>Телефон:</b>"},
    "address":        {"uz": "📍 <b>Manzil:</b>",                "ru": "📍 <b>Адрес:</b>"},
    "status":         {"uz": "🛈 <b>Status:</b>",                "ru": "🛈 <b>Статус:</b>"},
    "created":        {"uz": "🗓 <b>Yaratilgan:</b>",            "ru": "🗓 <b>Создано:</b>"},
    "updated":        {"uz": "🗓 <b>Yangilangan:</b>",           "ru": "🗓 <b>Обновлено:</b>"},
    "item_idx":       {"uz": "📄 <b>Ariza:</b>",                 "ru": "📄 <b>Заявка:</b>"},
    # Additional labels
    "type_label":     {"uz": "📋 <b>Turi:</b>",                 "ru": "📋 <b>Тип:</b>"},
    "source_label":   {"uz": "👤 <b>Manbai:</b>",                "ru": "👤 <b>Источник:</b>"},
    "total_label":    {"uz": "📈 <b>Umumiy:</b>",                "ru": "📈 <b>Итого:</b>"},
    "total_time":     {"uz": "• Umumiy vaqt:",                   "ru": "• Общее время:"},
    # Order types
    "order_type_connection": {"uz": "🔌 Ulanish arizasi",       "ru": "🔌 Заявка на подключение"},
    "order_type_technician": {"uz": "🛠️ Texnik xizmat arizasi", "ru": "🛠️ Техническая заявка"},
    "order_type_default":   {"uz": "📋 Ariza",                  "ru": "📋 Заявка"},
    # Source types
    "source_client": {"uz": "👤 Mijoz",                         "ru": "👤 Клиент"},
    "source_staff":  {"uz": "👨‍💼 Xodim",                         "ru": "👨‍💼 Сотрудник"},
    # Error messages
    "tariff_not_selected": {"uz": "❌ Tarif tanlanmagan",        "ru": "❌ Тариф не выбран"},
    "phone_not_entered":   {"uz": "❌ Telefon kiritilmagan",    "ru": "❌ Телефон не введён"},
    "client_name_not_entered": {"uz": "❌ Mijoz nomi kiritilmagan", "ru": "❌ Имя клиента не введено"},

    # Misc
    "closed":         {"uz": "Yopildi",                          "ru": "Закрыто"},
    "updating":       {"uz": "Yangilanmoqda…",                   "ru": "Обновляем…"},
    "updated_short":  {"uz": "Yangilandi ✅",                    "ru": "Обновлено ✅"},
    "not_found":      {"uz": "— Hech narsa topilmadi.",          "ru": "— Ничего не найдено."},
}

def normalize_lang(v: str | None) -> str:
    if not v:
        return "uz"
    s = v.strip().lower()
    if s in {"ru", "rus", "ru-ru", "ru_ru", "russian"}:
        return "ru"
    if s in {"uz", "uzb", "uz-uz", "uz_uz", "uzbek", "o'z", "oz"}:
        return "uz"
    return "uz"

def t(lang: str, key: str) -> str:
    lang = normalize_lang(lang)
    return T.get(key, {}).get(lang, T.get(key, {}).get("uz", key))

STATUS_T = {
    "new":               {"uz": "🆕 Yangi",             "ru": "🆕 Новая"},
    "in_progress":       {"uz": "⏳ Jarayonda",         "ru": "⏳ В процессе"},
    "done":              {"uz": "✅ Bajarilgan",        "ru": "✅ Выполнена"},
    "completed":         {"uz": "✅ Bajarilgan",        "ru": "✅ Выполнена"},
    "done_today":        {"uz": "✅ Bugun bajarilgan",  "ru": "✅ Выполнено сегодня"},
    "cancelled":         {"uz": "❌ Bekor qilingan",    "ru": "❌ Отменена"},
    "in_manager":        {"uz": "👨‍💼 Managerda",         "ru": "👨‍💼 У менеджера"},
    "in_junior_manager": {"uz": "👨‍💻 Kichik menejerda",  "ru": "👨‍💻 У младшего менеджера"},
    "in_controller":     {"uz": "👨‍🔧 Kontrollerda",      "ru": "👨‍🔧 У контроллера"},
    "in_technician":     {"uz": "👨‍🔧 Texnikada",         "ru": "👨‍🔧 У техника"},
    "in_warehouse":      {"uz": "🏪 Omborda",           "ru": "🏪 На складе"},
    "in_repairs":        {"uz": "🔧 Ta'mirlashda",      "ru": "🔧 В ремонте"},
    "in_technician_work":{"uz": "⚙️ Texnik ishda",      "ru": "⚙️ В технической работе"},
    "in_call_center_operator": {"uz": "📞 Call center operatorida", "ru": "📞 У оператора call center"},
    "in_call_center_supervisor": {"uz": "📞 Call center nazoratchisida", "ru": "📞 У супервизора call center"},
    "between_controller_technician": {"uz": "🔄 Kontroller va texnik o'rtasida", "ru": "🔄 Между контроллером и техником"},
}
def t_status(lang: str, status: str | None) -> str:
    key = (status or "").strip().lower()
    if key in STATUS_T:
        return STATUS_T[key].get(normalize_lang(lang), key)
    return status or "-"

def _esc(x: str | None) -> str:
    return html.escape(x or "-", quote=False)

def _fmt_dt(dt, lang: str = "uz") -> str:
    try:
        if isinstance(dt, str):
            return dt
        if not dt:
            return "-"
        
        # Vaqt zonasi konvertatsiyasi
        dt_local = _to_tz(dt)
        
        # Oylar nomlari
        months_uz = {
            1: "yanvar", 2: "fevral", 3: "mart", 4: "aprel", 
            5: "may", 6: "iyun", 7: "iyul", 8: "avgust", 
            9: "sentabr", 10: "oktabr", 11: "noyabr", 12: "dekabr"
        }
        months_ru = {
            1: "января", 2: "февраля", 3: "марта", 4: "апреля", 
            5: "мая", 6: "июня", 7: "июля", 8: "августа", 
            9: "сентября", 10: "октября", 11: "ноября", 12: "декабря"
        }
        
        if lang == "ru":
            month_name = months_ru.get(dt_local.month, str(dt_local.month))
            return f"{dt_local.day} {month_name} {dt_local.year} {dt_local.hour:02d}:{dt_local.minute:02d}"
        else:  # uz
            month_name = months_uz.get(dt_local.month, str(dt_local.month))
            return f"{dt_local.day} {month_name} {dt_local.year} {dt_local.hour:02d}:{dt_local.minute:02d}"
    except Exception:
        return str(dt) if dt else "-"

def _fmt_duration(created_at, lang: str = "uz") -> str:
    """Vaqt davomiyligini o'zbekcha formatda ko'rsatish"""
    try:
        if not created_at:
            return "N/A"
        
        if isinstance(created_at, str):
            created_dt = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
        else:
            created_dt = created_at
        
        # Vaqt zonasi konvertatsiyasi
        created_local = _to_tz(created_dt)
        now_local = datetime.now(TZ)
        
        duration = now_local - created_local
        
        total_seconds = int(duration.total_seconds())
        
        if total_seconds < 0:
            return "0m"
        
        days = total_seconds // 86400
        hours = (total_seconds % 86400) // 3600
        minutes = (total_seconds % 3600) // 60
        
        parts = []
        if days > 0:
            parts.append(f"{days}k")
        if hours > 0:
            parts.append(f"{hours}s")
        if minutes > 0:
            parts.append(f"{minutes}m")
        
        if not parts:
            return "0m"
        
        return " ".join(parts)
    except Exception:
        return "N/A"

# ---------- UI helpers ----------

def _apps_menu_kb(lang: str) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=t(lang, "btn_new"),      callback_data="apps:new")],
        [InlineKeyboardButton(text=t(lang, "btn_progress"), callback_data="apps:progress")],
        [InlineKeyboardButton(text=t(lang, "btn_done"),     callback_data="apps:done_today")],
        [InlineKeyboardButton(text=t(lang, "btn_cancel"),   callback_data="apps:cancelled")],
        # 🆕 "Men yaratgan arizalar"
        [InlineKeyboardButton(text=t(lang, "btn_my"),       callback_data="apps:my_created")],
        [InlineKeyboardButton(text=t(lang, "btn_refresh"),  callback_data="apps:refresh")],
        [InlineKeyboardButton(text=t(lang, "btn_close"),    callback_data="apps:close")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)

def _my_created_kb(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=t(lang, "btn_my_conn"), callback_data="apps:my_type:connection")],
            [InlineKeyboardButton(text=t(lang, "btn_my_tech"), callback_data="apps:my_type:technician")],
            [InlineKeyboardButton(text=t(lang, "btn_back"),    callback_data="apps:back")],
        ]
    )

def _back_kb(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=t(lang, "btn_back"), callback_data="apps:back")]]
    )

def _list_nav_kb(index: int, total_loaded: int, lang: str) -> InlineKeyboardMarkup:
    rows = []
    row = []
    if index > 0:
        row.append(InlineKeyboardButton(text=t(lang, "btn_prev"), callback_data="apps:nav:prev"))
    if index < total_loaded - 1:
        row.append(InlineKeyboardButton(text=t(lang, "btn_next"), callback_data="apps:nav:next"))
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton(text=t(lang, "btn_back"), callback_data="apps:back")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def _card_text(lang: str, total: int, new_today: int, in_progress: int, done_today: int, cancelled: int) -> str:
    return (
        f"{t(lang, 'title_panel')}\n\n"
        f"{t(lang, 'stats')}\n"
        f"{t(lang, 'total')} <b>{total}</b>\n"
        f"{t(lang, 'new')} <b>{new_today}</b>\n"
        f"{t(lang, 'in_progress')} <b>{in_progress}</b>\n"
        f"{t(lang, 'done_today')} <b>{done_today}</b>\n"
        f"{t(lang, 'cancelled')} <b>{cancelled}</b>\n\n"
        f"{t(lang, 'title_choose')}"
    )

def _item_card(lang: str, item: dict, index: int, total: int) -> str:
    # ID formatini tuzatamiz - connection_orders va staff_orders uchun
    app_number_raw = item.get("application_number", "")
    if app_number_raw and app_number_raw != "N/A" and app_number_raw.strip():
        app_number = app_number_raw
    else:
        # Agar application_number bo'lmasa, id dan foydalanamiz
        item_id = item.get("id", "N/A")
        if item_id != "N/A":
            order_source = item.get("order_source", "")
            if order_source == "client":
                app_number = f"CONN-B2C-{item_id:04d}"
            else:
                app_number = f"STAFF-CONN-B2C-{item_id:04d}"
        else:
            app_number = "N/A"
    
    client_name = _esc(item.get("client_name", "N/A"))
    client_phone= _esc(item.get("client_phone", "N/A"))
    address     = _esc(item.get("address", "N/A"))
    tariff      = _esc(item.get("tariff", "N/A"))
    status_raw  = item.get("status")
    status_txt  = _esc(t_status(lang, status_raw))
    created_at  = _fmt_dt(item.get("created_at"), lang)
    updated_at  = _fmt_dt(item.get("updated_at"), lang)
    order_source = item.get("source_type", item.get("order_source", ""))
    
    # Ariza turini ko'rsatamiz
    order_type = item.get("type_of_zayavka", "")
    if order_type == "connection":
        type_text = t(lang, "order_type_connection")
    elif order_type == "technician":
        type_text = t(lang, "order_type_technician")
    else:
        type_text = t(lang, "order_type_default")
    
    # Ariza manbaini ko'rsatamiz
    source_text = t(lang, "source_client") if order_source == "client" else t(lang, "source_staff")
    
    # Tarif uchun maxsus ko'rinish
    tariff_display = tariff if tariff != "N/A" else t(lang, "tariff_not_selected")
    
    # Telefon uchun maxsus ko'rinish
    phone_display = client_phone if client_phone != "N/A" else t(lang, "phone_not_entered")
    
    # Mijoz nomi uchun maxsus ko'rinish
    client_display = client_name if client_name != "N/A" else t(lang, "client_name_not_entered")
    
    # Umumiy vaqt hisoblash
    total_duration = _fmt_duration(item.get("created_at"), lang)

    return (
        f"{t(lang,'card_title')}\n\n"
        f"🪪 <b>ID:</b> {app_number}\n"
        f"{t(lang,'type_label')} {type_text}\n"
        f"{t(lang,'source_label')} {source_text}\n"
        f"{t(lang,'status')} {status_txt}\n"
        f"{t(lang,'client')} {client_display}\n"
        f"{t(lang,'phone')} {phone_display}\n"
        f"{t(lang,'created')} {created_at}\n"
        f"{t(lang,'address')} {address}\n"
        f"{t(lang,'tariff')} {tariff_display}\n\n"
        f"{t(lang,'total_label')}\n"
        f"{t(lang,'total_time')} {total_duration}\n"
        f"{t(lang,'item_idx')} {index + 1}/{total}"
    )

async def _load_stats(user_id: int):
    # Manager roli uchun statistika - barcha arizalar
    total      = await get_all_total_connection_orders_count()  # Barcha ulanish arizalari
    new_today  = await get_all_new_orders_count()  # Barcha manager'ga kelgan yangi arizalar
    in_prog    = await get_all_in_progress_count()  # Barcha jarayondagi arizalar
    done_today = await get_completed_today_count(user_id)  # Manager yaratgan bugun tugatilganlar
    cancelled  = await get_all_cancelled_count()  # Barcha bekor qilingan ulanish arizalari
    return total, new_today, in_prog, done_today, cancelled

async def _safe_edit(call: CallbackQuery, lang: str, text: str, kb: InlineKeyboardMarkup):
    try:
        await call.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    except TelegramBadRequest as e:
        if "not modified" in str(e).lower():
            await call.answer(t(lang, "updated_short"), show_alert=False)
        else:
            try:
                await call.message.edit_reply_markup(reply_markup=kb)
            except TelegramBadRequest:
                pass

# --------- Kirish (reply tugmadan) ---------

@router.message(F.text.in_(["📋 Arizalarni ko'rish", "📋 Все заявки"]))
async def applications_handler(message: Message, state: FSMContext):
    user = await get_user_by_telegram_id(message.from_user.id)
    lang = normalize_lang(user.get("language") if user else "uz")
    user_id = int(user["id"]) if user and user.get("id") else None

    if not user_id:
        await message.answer("❌ Foydalanuvchi topilmadi!")
        return

    total, new_today, in_prog, done_today, cancelled = await _load_stats(user_id)
    await message.answer(
        _card_text(lang, total, new_today, in_prog, done_today, cancelled),
        reply_markup=_apps_menu_kb(lang),
        parse_mode="HTML"
    )

# --------- Kategoriya bo'yicha ro'yxat ---------

CAT_NEW        = "new"
CAT_PROGRESS   = "progress"
CAT_DONE_TODAY = "done_today"
CAT_CANCELLED  = "cancelled"
CAT_MY_CREATED = "my_created"     # 🆕

async def _load_items_by_cat(cat: str, manager_user_id: Optional[int] = None, my_type: Optional[str] = None) -> list[dict]:
    if cat == CAT_NEW:
        return await list_new_orders(manager_user_id, limit=50)
    if cat == CAT_PROGRESS:
        return await list_all_in_progress_orders(limit=50)  # Barcha jarayondagi arizalar
    if cat == CAT_DONE_TODAY:
        return await list_completed_today_orders(manager_user_id, limit=50)
    if cat == CAT_CANCELLED:
        return await list_cancelled_orders(manager_user_id, limit=50)
    if cat == CAT_MY_CREATED and manager_user_id and my_type in {"connection", "technician"}:
        return await list_my_created_orders_by_type(manager_user_id, my_type, limit=50)
    return []

async def _open_category(call: CallbackQuery, state: FSMContext, lang: str, cat: str, title: str,
                         manager_user_id: Optional[int] = None, my_type: Optional[str] = None):
    await call.answer()
    items = await _load_items_by_cat(cat, manager_user_id=manager_user_id, my_type=my_type)
    if not items:
        await _safe_edit(call, lang, f"{title}\n\n{t(lang,'not_found')}", _back_kb(lang))
        return

    idx = 0
    total_loaded = len(items)
    await state.update_data(apps_cat=cat, apps_items=items, apps_idx=idx, apps_total=total_loaded)

    text = f"{title}\n\n" + _item_card(lang, items[idx], idx, total_loaded)
    kb = _list_nav_kb(idx, total_loaded, lang)
    await _safe_edit(call, lang, text, kb)

@router.callback_query(F.data == "apps:new")
async def apps_new(call: CallbackQuery, state: FSMContext):
    user = await get_user_by_telegram_id(call.from_user.id)
    lang = normalize_lang(user.get("language") if user else "uz")
    user_id = int(user["id"]) if user and user.get("id") else None
    
    if not user_id:
        await call.answer("❌ Foydalanuvchi topilmadi!")
        return
        
    await _open_category(call, state, lang, CAT_NEW, t(lang, "title_new"), manager_user_id=user_id)

@router.callback_query(F.data == "apps:progress")
async def apps_progress(call: CallbackQuery, state: FSMContext):
    user = await get_user_by_telegram_id(call.from_user.id)
    lang = normalize_lang(user.get("language") if user else "uz")
    user_id = int(user["id"]) if user and user.get("id") else None
    
    if not user_id:
        await call.answer("❌ Foydalanuvchi topilmadi!")
        return
        
    await _open_category(call, state, lang, CAT_PROGRESS, t(lang, "title_progress"), manager_user_id=user_id)

@router.callback_query(F.data == "apps:done_today")
async def apps_done_today(call: CallbackQuery, state: FSMContext):
    user = await get_user_by_telegram_id(call.from_user.id)
    lang = normalize_lang(user.get("language") if user else "uz")
    user_id = int(user["id"]) if user and user.get("id") else None
    
    if not user_id:
        await call.answer("❌ Foydalanuvchi topilmadi!")
        return
        
    await _open_category(call, state, lang, CAT_DONE_TODAY, t(lang, "title_done"), manager_user_id=user_id)

@router.callback_query(F.data == "apps:cancelled")
async def apps_cancelled(call: CallbackQuery, state: FSMContext):
    user = await get_user_by_telegram_id(call.from_user.id)
    lang = normalize_lang(user.get("language") if user else "uz")
    user_id = int(user["id"]) if user and user.get("id") else None
    
    if not user_id:
        await call.answer("❌ Foydalanuvchi topilmadi!")
        return
        
    await _open_category(call, state, lang, CAT_CANCELLED, t(lang, "title_cancel"), manager_user_id=user_id)

# --------- 🆕 Men yaratgan arizalar: submenu ---------

@router.callback_query(F.data == "apps:my_created")
async def apps_my_created_root(call: CallbackQuery, state: FSMContext):
    user = await get_user_by_telegram_id(call.from_user.id)
    lang = normalize_lang(user.get("language") if user else "uz")
    await _safe_edit(
        call,
        lang,
        f"{t(lang,'title_my')}\n{t(lang,'title_my_choose')}",
        _my_created_kb(lang)
    )

@router.callback_query(F.data.startswith("apps:my_type:"))
async def apps_my_created_by_type(call: CallbackQuery, state: FSMContext):
    user = await get_user_by_telegram_id(call.from_user.id)
    lang = normalize_lang(user.get("language") if user else "uz")
    manager_id = int(user["id"]) if user and user.get("id") else None

    _type = call.data.split(":", 2)[2]  # connection | technician
    title = t(lang, "title_my_conn") if _type == "connection" else t(lang, "title_my_tech")
    await _open_category(
        call, state, lang,
        CAT_MY_CREATED, title,
        manager_user_id=manager_id,
        my_type=_type
    )

# --------- Oldingi / Keyingi ---------

@router.callback_query(F.data == "apps:nav:prev")
async def apps_nav_prev(call: CallbackQuery, state: FSMContext):
    await call.answer()
    user = await get_user_by_telegram_id(call.from_user.id)
    lang = normalize_lang(user.get("language") if user else "uz")

    data = await state.get_data()
    items = data.get("apps_items", [])
    idx   = max(0, int(data.get("apps_idx", 0)) - 1)
    total_loaded = len(items)
    if not items:
        await _safe_edit(call, lang, t(lang, "not_found"), _back_kb(lang)); return

    await state.update_data(apps_idx=idx)
    text = _item_card(lang, items[idx], idx, total_loaded)

    cat = data.get("apps_cat", "")
    title = {
        CAT_NEW:        t(lang, "title_new"),
        CAT_PROGRESS:   t(lang, "title_progress"),
        CAT_DONE_TODAY: t(lang, "title_done"),
        CAT_CANCELLED:  t(lang, "title_cancel"),
        CAT_MY_CREATED: t(lang, "title_my"),   # umumiy title (typeda keldingiz)
    }.get(cat, t(lang, "title_fallback"))

    kb = _list_nav_kb(idx, total_loaded, lang)
    await _safe_edit(call, lang, f"{title}\n\n{text}", kb)

@router.callback_query(F.data == "apps:nav:next")
async def apps_nav_next(call: CallbackQuery, state: FSMContext):
    await call.answer()
    user = await get_user_by_telegram_id(call.from_user.id)
    lang = normalize_lang(user.get("language") if user else "uz")

    data = await state.get_data()
    items = data.get("apps_items", [])
    idx   = min(len(items)-1, int(data.get("apps_idx", 0)) + 1)
    total_loaded = len(items)
    if not items:
        await _safe_edit(call, lang, t(lang, "not_found"), _back_kb(lang)); return

    await state.update_data(apps_idx=idx)
    text = _item_card(lang, items[idx], idx, total_loaded)

    cat = data.get("apps_cat", "")
    title = {
        CAT_NEW:        t(lang, "title_new"),
        CAT_PROGRESS:   t(lang, "title_progress"),
        CAT_DONE_TODAY: t(lang, "title_done"),
        CAT_CANCELLED:  t(lang, "title_cancel"),
        CAT_MY_CREATED: t(lang, "title_my"),
    }.get(cat, t(lang, "title_fallback"))

    kb = _list_nav_kb(idx, total_loaded, lang)
    await _safe_edit(call, lang, f"{title}\n\n{text}", kb)

# --------- Yangilash / Orqaga / Yopish ---------

@router.callback_query(F.data == "apps:refresh")
async def apps_refresh(call: CallbackQuery, state: FSMContext):
    user = await get_user_by_telegram_id(call.from_user.id)
    lang = normalize_lang(user.get("language") if user else "uz")
    user_id = int(user["id"]) if user and user.get("id") else None

    if not user_id:
        await call.answer("❌ Foydalanuvchi topilmadi!")
        return

    await call.answer(t(lang, "updating"))
    total, new_today, in_prog, done_today, cancelled = await _load_stats(user_id)
    await _safe_edit(
        call,
        lang,
        _card_text(lang, total, new_today, in_prog, done_today, cancelled),
        _apps_menu_kb(lang)
    )

@router.callback_query(F.data == "apps:back")
async def apps_back(call: CallbackQuery, state: FSMContext):
    await call.answer()
    user = await get_user_by_telegram_id(call.from_user.id)
    lang = normalize_lang(user.get("language") if user else "uz")
    user_id = int(user["id"]) if user and user.get("id") else None

    if not user_id:
        await call.answer("❌ Foydalanuvchi topilmadi!")
        return

    total, new_today, in_prog, done_today, cancelled = await _load_stats(user_id)
    await _safe_edit(
        call,
        lang,
        _card_text(lang, total, new_today, in_prog, done_today, cancelled),
        _apps_menu_kb(lang)
    )

@router.callback_query(F.data == "apps:close")
async def apps_close(call: CallbackQuery, state: FSMContext):
    user = await get_user_by_telegram_id(call.from_user.id)
    lang = normalize_lang(user.get("language") if user else "uz")

    await call.answer(t(lang, "closed"))
    await state.update_data(apps_cat=None, apps_items=None, apps_idx=None, apps_total=None)
    try:
        await call.message.delete()
    except TelegramBadRequest:
        try:
            await call.message.edit_reply_markup(reply_markup=None)
        except TelegramBadRequest:
            pass
