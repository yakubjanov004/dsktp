# handlers/junior_manager/orders.py
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
import logging

from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
import json
import html

from filters.role_filter import RoleFilter

# --- DB: ro'yxatlar ---
from database.junior_manager.orders import (
    list_new_for_jm,
    list_inprogress_for_jm,
    list_completed_for_jm,
    list_assigned_for_jm,
)
from database.basic.user import get_user_by_telegram_id

router = Router()
router.message.filter(RoleFilter("junior_manager"))
router.callback_query.filter(RoleFilter("junior_manager"))

# ===================== i18n helpers =====================
def _norm_lang(s: str | None) -> str:
    s = (s or "uz").lower()
    return "ru" if s.startswith("ru") else "uz"

# ===================== Region mapping =====================
REGION_CODE_TO_NAME = {
    "uz": {
        "1": "Toshkent shahri", "tashkent_city": "Toshkent shahri",
        "2": "Toshkent viloyati", "tashkent_region": "Toshkent viloyati", 
        "3": "Andijon", "andijon": "Andijon",
        "4": "Farg'ona", "fergana": "Farg'ona",
        "5": "Namangan", "namangan": "Namangan",
        "6": "Sirdaryo", "sirdaryo": "Sirdaryo",
        "7": "Jizzax", "jizzax": "Jizzax",
        "8": "Samarqand", "samarkand": "Samarqand",
        "9": "Buxoro", "bukhara": "Buxoro",
        "10": "Navoiy", "navoi": "Navoiy",
        "11": "Qashqadaryo", "kashkadarya": "Qashqadaryo",
        "12": "Surxondaryo", "surkhandarya": "Surxondaryo",
        "13": "Xorazm", "khorezm": "Xorazm",
        "14": "Qoraqalpog'iston", "karakalpakstan": "Qoraqalpog'iston",
    },
    "ru": {
        "1": "г. Ташкент", "tashkent_city": "г. Ташкент",
        "2": "Ташкентская область", "tashkent_region": "Ташкентская область",
        "3": "Андижан", "andijon": "Андижан",
        "4": "Фергана", "fergana": "Фергана",
        "5": "Наманган", "namangan": "Наманган",
        "6": "Сырдарья", "sirdaryo": "Сырдарья",
        "7": "Джизак", "jizzax": "Джизак",
        "8": "Самарканд", "samarkand": "Самарканд",
        "9": "Бухара", "bukhara": "Бухара",
        "10": "Навои", "navoi": "Навои",
        "11": "Кашкадарья", "kashkadarya": "Кашкадарья",
        "12": "Сурхандарья", "surkhandarya": "Сурхандарья",
        "13": "Хорезм", "khorezm": "Хорезм",
        "14": "Каракалпакстан", "karakalpakstan": "Каракалпакстан",
    }
}

def _get_region_display_name(region: str | None, lang: str) -> str:
    """Convert region code/ID to display name"""
    if not region:
        return "—"
    
    region_str = str(region).lower()
    lang = _norm_lang(lang)
    
    # Try to get display name from mapping
    display_name = REGION_CODE_TO_NAME.get(lang, {}).get(region_str)
    if display_name:
        return display_name
    
    # If not found, return the original value
    return str(region)

def _L(lang: str) -> dict:
    lang = _norm_lang(lang)
    if lang == "ru":
        return {
            "menu_title": "📋 <b>Просмотр заявок</b>\nВыберите раздел ниже:",
            "empty": "Ничего не найдено.",
            "new": "🆕 <b>Новые заявки</b>",
            "assigned": "🔗 <b>Назначенные</b>",
            "wip": "⏳ <b>В работе</b>",
            "done": "✅ <b>Завершённые</b>",
            "created": "📝 <b>Созданные мной</b>",
            "type_connection": "📦 connection",
            "ago_now": "только что",
            "ago_min": "{} минут назад",
            "ago_hour": "{} часов назад",
            "ago_day": "{} дней назад",
            "prev": "⬅️ Назад",
            "next": "➡️ Вперёд",
            "back": "🔙 Назад",
            "nochange": "Без изменений ✅",
            "btn_new": "🆕 Новые заявки",
            "btn_assigned": "🔗 Назначенные",
            "btn_wip": "⏳ В работе",
            "btn_done": "✅ Завершённые",
            "btn_created": "📝 Мои заявки",
        }
    return {
        "menu_title": "📋 <b>Arizalarni ko'rish</b>\nQuyidan bo'limni tanlang:",
        "empty": "Hech narsa topilmadi.",
        "new": "🆕 <b>Yangi buyurtma</b>",
        "assigned": "🔗 <b>Biriktirilgan</b>",
        "wip": "⏳ <b>Jarayonda</b>",
        "done": "✅ <b>Tugatilgan</b>",
        "created": "📝 <b>Yaratganlarim</b>",
        "type_connection": "📦 connection",
        "ago_now": "hozirgina",
        "ago_min": "{} daqiqa oldin",
        "ago_hour": "{} soat oldin",
        "ago_day": "{} kun oldin",
        "prev": "⬅️ Oldingi",
        "next": "➡️ Keyingi",
        "back": "🔙 Orqaga",
        "nochange": "Yangilanish yo'q ✅",
        "btn_new": "🆕 Yangi buyurtmalar",
        "btn_assigned": "🔗 Biriktirilganlar",
        "btn_wip": "⏳ Jarayondagilar",
        "btn_done": "✅ Tugatilganlari",
        "btn_created": "📝 Yaratganlarim",
    }

# ===================== TZ & time =====================
# --- Timezone ---

def _ago_text(dt: datetime, L: dict) -> str:
    if dt is None:
        return "—"
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    delta = datetime.now(timezone.utc) - dt
    secs = int(delta.total_seconds())
    d, r = divmod(secs, 86400)
    h, r = divmod(r, 3600)
    m, _ = divmod(r, 60)
    if d:
        return L["ago_day"].format(d)
    if h:
        return L["ago_hour"].format(h)
    if m:
        return L["ago_min"].format(m)
    return L["ago_now"]

# ===================== Keyboards =====================
def _kb_root(lang: str) -> InlineKeyboardMarkup:
    L = _L(lang)
    kb = InlineKeyboardBuilder()
    kb.button(text=L["btn_assigned"], callback_data="jm_list:assigned")
    kb.button(text=L["btn_wip"], callback_data="jm_list:wip")
    kb.button(text=L["btn_done"], callback_data="jm_list:done")
    kb.button(text=L["btn_created"], callback_data="jm_list:created")
    kb.adjust(1)
    return kb.as_markup()

def _kb_pager(idx: int, total: int, kind: str, lang: str) -> InlineKeyboardMarkup:
    L = _L(lang)
    kb = InlineKeyboardBuilder()
    kb.button(text=L["prev"], callback_data=f"jm_nav:{kind}:prev")
    kb.button(text=f"{idx+1}/{total}", callback_data="noop")
    kb.button(text=L["next"], callback_data=f"jm_nav:{kind}:next")
    kb.row()
    kb.button(text=L["back"], callback_data="jm_back")
    return kb.as_markup()


def _safe_kb_fp(kb) -> str:
    if kb is None:
        return "NONE"
    try:
        data = kb.model_dump(by_alias=True, exclude_none=True)
        return json.dumps(data, sort_keys=True, ensure_ascii=False)
    except Exception:
        return str(kb)

async def _safe_edit(cb: CallbackQuery, text: str, kb: InlineKeyboardMarkup | None, lang: str):
    msg = cb.message
    cur_text = msg.html_text or msg.text or ""
    if cur_text == text and _safe_kb_fp(msg.reply_markup) == _safe_kb_fp(kb):
        await cb.answer(_L(lang)["nochange"], show_alert=False)
        return
    try:
        await msg.edit_text(text, reply_markup=kb)
    except TelegramBadRequest as e:
        if "message is not modified" in str(e):
            await cb.answer(_L(lang)["nochange"], show_alert=False)
        else:
            raise

# ===================== Card formatter =====================
def _fmt_card(item: dict, kind: str, lang: str) -> str:
    L = _L(lang)
    
    # Asosiy ma'lumotlar
    rid = item.get("id")
    application_number = html.escape(item.get("application_number") or f"#{rid:03d}", quote=False)
    fio = html.escape(item.get("user_name") or "—", quote=False)
    phone = html.escape(item.get("client_phone") or "—", quote=False)
    addr = html.escape(item.get("address") or "—", quote=False)
    region = _get_region_display_name(item.get("region"), lang)
    tariff_name = html.escape(str(item.get("tariff_name") or "—"), quote=False)
    status = html.escape(str(item.get("status") or "—"), quote=False)
    
    # Order type
    order_type = item.get("order_type", "connection")
    type_icon = "🔗" if order_type == "connection" else "👨‍💼"
    type_text = "Ulanish arizasi" if order_type == "connection" else "Xodim arizasi"
    
    # Vaqtni formatlash - UTC+5 timezone
    created_at = item.get("created_at")
    
    if created_at and hasattr(created_at, 'strftime'):
        # Convert to UTC+5 timezone
        if created_at.tzinfo is None:
            # If no timezone info, assume it's UTC and convert to UTC+5
            utc_plus_5 = timezone(timedelta(hours=5))
            created_at = created_at.replace(tzinfo=timezone.utc).astimezone(utc_plus_5)
        else:
            # If timezone info exists, convert to UTC+5
            utc_plus_5 = timezone(timedelta(hours=5))
            created_at = created_at.astimezone(utc_plus_5)
        
        created_str = created_at.strftime("%d.%m.%Y %H:%M")
    else:
        created_str = str(created_at or "—")
    
    title = {"new": L["new"], "assigned": L["assigned"], "wip": L["wip"], "done": L["done"], "created": "📝 Yaratganlarim"}[kind]
    
    if lang == "ru":
        text = f"<b>📋 ПОДРОБНАЯ ИНФОРМАЦИЯ О ЗАЯВКЕ</b>\n"
        text += f"{'=' * 40}\n\n"
        text += f"<b>🆔 ID заявки:</b> {application_number}\n"
        text += f"<b>{type_icon} Тип заявки:</b> {'Заявка на подключение' if order_type == 'connection' else 'Заявка сотрудника'}\n"
        text += f"<b>👤 Клиент:</b> {fio}\n"
        text += f"<b>📞 Телефон:</b> {phone}\n"
        text += f"<b>📍 Адрес:</b> {addr}\n"
        text += f"<b>🌍 Регион:</b> {region}\n"
        text += f"<b>💰 Тариф:</b> {tariff_name}\n"
        text += f"<b>📊 Статус:</b> {status}\n"
        text += f"<b>🕐 Дата создания:</b> {created_str}\n"
    else:
        text = f"<b>📋 ARIZA BATAFSIL MA'LUMOTLARI</b>\n"
        text += f"{'=' * 40}\n\n"
        text += f"<b>🆔 Ariza ID:</b> {application_number}\n"
        text += f"<b>{type_icon} Ariza turi:</b> {'Ulanish arizasi' if order_type == 'connection' else 'Xodim arizasi'}\n"
        text += f"<b>👤 Mijoz:</b> {fio}\n"
        text += f"<b>📞 Telefon:</b> {phone}\n"
        text += f"<b>📍 Manzil:</b> {addr}\n"
        text += f"<b>🌍 Hudud:</b> {region}\n"
        text += f"<b>💰 Tarif:</b> {tariff_name}\n"
        text += f"<b>📊 Status:</b> {status}\n"
        text += f"<b>🕐 Yaratilgan:</b> {created_str}\n"
    
    # Material_issued ma'lumotlarini qo'shish (tugatilgan arizalar uchun)
    if kind == "done" and item.get('materials_text'):
        if lang == "ru":
            text += f"\n<b>🧾 Материалы:</b>\n{item['materials_text']}\n"
        else:
            text += f"\n<b>🧾 Materiallar:</b>\n{item['materials_text']}\n"
    
    return text


# Tugmani O'ZGARTIRMAYMIZ: reply keyboarddagi label'lar bilan to'g'ridan-to'g'ri mos.
ENTRY_TEXTS = [
    "📋 Arizalarni ko'rish",  # uz
    "📋 Просмотр заявок",     # ru
    "📋 Arizalarni ko‘rish",  # (ko‘ varianti)
]

@router.message(F.text.in_(ENTRY_TEXTS))
async def jm_orders_menu(msg: Message):
    # Eski xabarlarda eski inline klaviatura bo‘lsa, tozalab yuborish (reply_markup tozalash)
    try:
        if msg.reply_to_message and getattr(msg.reply_to_message, "reply_markup", None):
            await msg.reply_to_message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    u = await get_user_by_telegram_id(msg.from_user.id)
    lang = _norm_lang(u.get("language") if u else "ru")
    await msg.answer(_L(lang)["menu_title"], reply_markup=_kb_root(lang))

# ===================== Open list =====================
@router.callback_query(F.data.startswith("jm_list:"))
async def jm_open_list(cb: CallbackQuery, state: FSMContext):
    u = await get_user_by_telegram_id(cb.from_user.id)
    lang = _norm_lang(u.get("language") if u else "ru")
    kind = cb.data.split(":")[1]  # assigned | wip | done | created
    jm_id = u["id"]
    if kind == "assigned":
        items = await list_assigned_for_jm(jm_id)
    elif kind == "wip":
        items = await list_inprogress_for_jm(jm_id)
    elif kind == "done":
        items = await list_completed_for_jm(jm_id)
        # Yakunlanganlarga material_issued ma'lumotini qo'shamiz:
        from database.warehouse.material_issued_queries import fetch_materials_for_application
        for item in items:
            materials = await fetch_materials_for_application(item['application_number'], 'connection')
            if materials:
                item['materials_text'] = '\n'.join([
                    f"{m['material_name']}: {m['quantity']} dona (summa: {m['total_price']})" for m in materials
                ])
    elif kind == "created":
        from database.junior_manager.orders import list_staff_created_by_jm
        items = await list_staff_created_by_jm(jm_id)
    else:
        items = []
    if not items:
        await _safe_edit(cb, _L(lang)["empty"], _kb_root(lang), lang)
        return
    await state.update_data(jm_items=items, jm_idx=0, jm_kind=kind)
    text = _fmt_card(items[0], kind, lang)
    await _safe_edit(cb, text, _kb_pager(0, len(items), kind, lang), lang)

# ===================== Navigation =====================
@router.callback_query(F.data.startswith("jm_nav:"))
async def jm_nav(cb: CallbackQuery, state: FSMContext):
    u = await get_user_by_telegram_id(cb.from_user.id)
    lang = _norm_lang(u.get("language") if u else "ru")

    _, kind, direction = cb.data.split(":")
    data = await state.get_data()
    items = data.get("jm_items") or []
    if not items:
        await cb.answer(_L(lang)["empty"], show_alert=False)
        return

    idx = int(data.get("jm_idx", 0))
    if direction == "prev":
        idx = (idx - 1) % len(items)
    else:
        idx = (idx + 1) % len(items)

    await state.update_data(jm_idx=idx, jm_kind=kind)
    text = _fmt_card(items[idx], kind, lang)
    await _safe_edit(cb, text, _kb_pager(idx, len(items), kind, lang), lang)

@router.callback_query(F.data == "jm_back")
async def jm_back(cb: CallbackQuery, state: FSMContext):
    u = await get_user_by_telegram_id(cb.from_user.id)
    lang = _norm_lang(u.get("language") if u else "ru")

    await state.clear()
    await _safe_edit(cb, _L(lang)["menu_title"], _kb_root(lang), lang)


@router.callback_query(F.data == "noop")
async def noop(cb: CallbackQuery):
    await cb.answer()