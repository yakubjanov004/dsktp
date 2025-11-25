# handlers/controller/inbox.py
from aiogram import F, Router
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, FSInputFile
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramBadRequest
from datetime import datetime
import html
import logging

from database.controller.queries import (
    get_user_by_telegram_id,
    fetch_controller_inbox_connection,
    fetch_controller_inbox_tech,
    fetch_controller_inbox_staff,
    assign_to_technician_connection,
    assign_to_technician_tech,
    assign_to_technician_staff,
    assign_to_ccs_tech,
    assign_to_ccs_staff,
    assign_to_ccs_connection,
    get_technicians_with_load_via_history,
    get_ccs_supervisors_with_load,
)
from database.basic.user import get_users_by_role
from filters.role_filter import RoleFilter
from loader import bot

logger = logging.getLogger(__name__)

router = Router()
router.message.filter(RoleFilter("controller"))
router.callback_query.filter(RoleFilter("controller"))

# ========== Media Type Detection Helper Functions ==========

def _detect_media_kind(file_id: str | None, media_type: str | None = None) -> str | None:
    """
    Sodda media turini aniqlash
    """
    if not file_id:
        return None

    # DB dan kelgan media_type bo'lsa, shunga ishonamiz
    if media_type in {"photo", "video"}:
        return media_type

    # Telegram file_id prefixlarini tekshirish
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
    
    # Local fayl bo'lsa, kengaytmadan aniqlaymiz
    if "/" in file_id or "." in file_id:
        file_ext = file_id.lower().rsplit('.', 1)[-1] if '.' in file_id else ''
        if file_ext in ['jpg', 'jpeg', 'png', 'gif', 'webp']:
            return "photo"
        if file_ext in ['mp4', 'avi', 'mov', 'mkv', 'webm']:
            return "video"

    # Default: video sifatida qabul qilamiz
    return "video"


async def _send_media_strict(chat_id: int, file_id: str, caption: str, kb: InlineKeyboardMarkup, media_kind: str | None):
    """
    Media yuborish: technician roli kabi sodda usul
    """
    try:
        if media_kind == 'video':
            try:
                await bot.send_video(
                    chat_id=chat_id,
                    video=file_id,
                    caption=caption,
                    parse_mode='HTML',
                    reply_markup=kb
                )
                logger.info(f"Video sent successfully: {file_id}")
                return
            except Exception as e:
                logger.error(f"Video send failed, retrying as photo: {e}")
                try:
                    await bot.send_photo(
                        chat_id=chat_id,
                        photo=file_id,
                        caption=caption,
                        parse_mode='HTML',
                        reply_markup=kb
                    )
                    logger.info(f"Video sent as photo successfully: {file_id}")
                    return
                except Exception as e2:
                    logger.error(f"Photo send also failed: {e2}")
        elif media_kind == 'photo':
            try:
                await bot.send_photo(
                    chat_id=chat_id,
                    photo=file_id,
                    caption=caption,
                    parse_mode='HTML',
                    reply_markup=kb
                )
                logger.info(f"Photo sent successfully: {file_id}")
                return
            except Exception as e:
                logger.error(f"Photo send failed: {e}")
        else:
            # Aniq turi noma'lum bo'lsa, video sifatida sinab ko'ramiz
            try:
                await bot.send_video(
                    chat_id=chat_id,
                    video=file_id,
                    caption=caption,
                    parse_mode='HTML',
                    reply_markup=kb
                )
                logger.info(f"Unknown media sent as video successfully: {file_id}")
                return
            except Exception as e:
                logger.error(f"Video send failed, retrying as photo: {e}")
                try:
                    await bot.send_photo(
                        chat_id=chat_id,
                        photo=file_id,
                        caption=caption,
                        parse_mode='HTML',
                        reply_markup=kb
                    )
                    logger.info(f"Unknown media sent as photo successfully: {file_id}")
                    return
                except Exception as e2:
                    logger.error(f"Photo send also failed: {e2}")
    except Exception as e:
        logger.error(f"All media attempts failed: {e}")
    
    # Fallback: faqat matn yuborish
    logger.warning(f"Falling back to text-only message for media: {file_id}")
    await bot.send_message(chat_id=chat_id, text=caption, parse_mode="HTML", reply_markup=kb)

# ========== I18N ==========
T = {
    "title": {"uz": "🎛️ <b>Controller Inbox</b>", "ru": "🎛️ <b>Входящие контроллера</b>"},
    "id": {"uz": "🆔 <b>ID:</b>", "ru": "🆔 <b>ID:</b>"},
    "tariff": {"uz": "📊 <b>Tarif:</b>", "ru": "📊 <b>Тариф:</b>"},
    "problem": {"uz": "🔧 <b>Muammo:</b>", "ru": "🔧 <b>Проблема:</b>"},
    "client": {"uz": "👤 <b>Mijoz:</b>", "ru": "👤 <b>Клиент:</b>"},
    "phone": {"uz": "📞 <b>Telefon:</b>", "ru": "📞 <b>Телефон:</b>"},
    "address": {"uz": "📍 <b>Manzil:</b>", "ru": "📍 <b>Адрес:</b>"},
    "created": {"uz": "📅 <b>Yaratilgan:</b>", "ru": "📅 <b>Создано:</b>"},
    "order_idx": {"uz": "🗂️ <i>Ariza {i} / {n}</i>", "ru": "🗂️ <i>Заявка {i} / {n}</i>"},
    "choose_cat": {"uz": "📂 Qaysi bo'limni ko'ramiz?", "ru": "📂 Какой раздел откроем?"},
    "empty_conn": {"uz": "📭 Ulanish arizalari bo'sh", "ru": "📭 Заявок на подключение нет"},
    "empty_tech": {"uz": "📭 Texnik xizmat arizalari bo'sh", "ru": "📭 Заявок на техобслуживание нет"},
    "empty_staff": {"uz": "📭 Xodimlar yuborgan arizalar bo'sh", "ru": "📭 Заявок от сотрудников нет"},
    "btn_prev": {"uz": "⬅️ Oldingi", "ru": "⬅️ Назад"},
    "btn_next": {"uz": "Keyingi ➡️", "ru": "Вперёд ➡️"},
    "btn_assign_tech": {"uz": "🔧 Texnikga yuborish", "ru": "🔧 Отправить технику"},
    "btn_assign_tech_ccs": {"uz": "✅ Texnikga / CCS ga yuborish", "ru": "✅ Отправить технику / CCS"},
    "btn_sections_back": {"uz": "🔙 Bo'limlarga qaytish", "ru": "🔙 Назад к разделам"},
    "cat_conn": {"uz": "🔌 Ulanish uchun arizalar", "ru": "🔌 Заявки на подключение"},
    "cat_tech": {"uz": "🔧 Texnik xizmat arizalari", "ru": "🔧 Заявки на техобслуживание"},
    "cat_staff": {"uz": "👥 Xodimlar yuborgan arizalar", "ru": "👥 Заявки от сотрудников"},
    "tech_pick_title": {"uz": "🔧 <b>Texnik yoki CCS tanlang</b>", "ru": "🔧 <b>Выберите техника или CCS</b>"},
    "tech_pick_title_only": {"uz": "🔧 <b>Texnik tanlang</b>", "ru": "🔧 <b>Выберите техника</b>"},
    "btn_tech_section": {"uz": "— Texniklar —", "ru": "— Техники —"},
    "btn_ccs_section": {"uz": "— CCS Supervisorlar —", "ru": "— CCS Супервизоры —"},
    "back": {"uz": "🔙 Orqaga", "ru": "🔙 Назад"},
    "no_techs": {"uz": "Texniklar topilmadi ❗", "ru": "Техники не найдены ❗"},
    "no_ccs": {"uz": "CCS supervisorlar topilmadi ❗", "ru": "CCS супервизоры не найдены ❗"},
    "bad_format": {"uz": "❌ Noto'g'ri callback format", "ru": "❌ Неверный формат callback"},
    "no_user": {"uz": "❌ Foydalanuvchi topilmadi", "ru": "❌ Пользователь не найден"},
    "no_tech_one": {"uz": "❌ Texnik topilmadi", "ru": "❌ Техник не найден"},
    "no_ccs_one": {"uz": "❌ CCS supervisor topilmadi", "ru": "❌ CCS супервизор не найден"},
    "error_generic": {"uz": "❌ Xatolik yuz berdi:", "ru": "❌ Произошла ошибка:"},
    "ok_assigned_title": {"uz": "✅ <b>Ariza muvaffaqiyatli yuborildi!</b>", "ru": "✅ <b>Заявка успешно отправлена!</b>"},
    "order_id": {"uz": "🆔 <b>Ariza ID:</b>", "ru": "🆔 <b>ID заявки:</b>"},
    "tech": {"uz": "🔧 <b>Texnik:</b>", "ru": "🔧 <b>Техник:</b>"},
    "ccs": {"uz": "👔 <b>CCS Supervisor:</b>", "ru": "👔 <b>CCS Супервизор:</b>"},
    "sent_time": {"uz": "📅 <b>Yuborilgan vaqt:</b>", "ru": "📅 <b>Время отправки:</b>"},
    "sender": {"uz": "🎛️ <b>Yuboruvchi:</b>", "ru": "🎛️ <b>Отправитель:</b>"},
    "req_type": {"uz": "🧾 <b>Ariza turi:</b>", "ru": "🧾 <b>Тип заявки:</b>"},
    "creator": {"uz": "👷‍♂️ <b>Yaratgan xodim:</b>", "ru": "👷‍♂️ <b>Создал сотрудник:</b>"},
    "creator_role": {"uz": "roli", "ru": "роль"},
    "desc": {"uz": "📝 <b>Izoh:</b>", "ru": "📝 <b>Описание:</b>"},
    "jm_notes": {"uz": "📝 <b>Junior Manager izohi:</b>", "ru": "📝 <b>Заметка Junior Manager:</b>"},
    "abonent": {"uz": "👤 <b>Abonent:</b>", "ru": "👤 <b>Абонент:</b>"},
}

def normalize_lang(v: str | None) -> str:
    if not v:
        return "uz"
    v = v.strip().lower()
    if v in {"ru", "rus", "russian", "ru-ru", "ru_ru"}:
        return "ru"
    return "uz"

def t(lang: str, key: str, **fmt) -> str:
    lang = normalize_lang(lang)
    val = T.get(key, {}).get(lang) or T.get(key, {}).get("uz", key)
    return val.format(**fmt) if fmt else val

def fmt_dt(dt: datetime) -> str:
    if not dt:
        return "-"
    return dt.strftime("%d.%m.%Y %H:%M")

def esc(v) -> str:
    if v is None:
        return "-"
    return html.escape(str(v), quote=False)

def detect_lang_from_message(text: str) -> str:
    return "ru" if text and "Входящие" in text else "uz"

# ========== Text builders ==========

def build_connection_text(item: dict, idx: int | None, total: int | None, lang: str) -> str:
    """Ulanish arizasi uchun text"""
    app_num = esc(item.get("application_number", "-"))
    tariff = esc(item.get("tariff", "-"))
    client_name = esc(item.get("client_name", "-"))
    client_phone = esc(item.get("client_phone", "-"))
    address = esc(item.get("address", "-"))
    created_dt = item.get("created_at")
    
    text = (
        f"{t(lang,'title')}\n"
        f"{t(lang,'id')} {app_num}\n"
        f"{t(lang,'tariff')} {tariff}\n"
        f"{t(lang,'client')} {client_name}\n"
        f"{t(lang,'phone')} {client_phone}\n"
        f"{t(lang,'address')} {address}\n"
        f"{t(lang,'created')} {fmt_dt(created_dt)}"
    )
    
    # jm_notes ko'rsatish
    jm_notes = item.get("jm_notes")
    if jm_notes:
        text += f"\n\n{t(lang,'jm_notes')}\n{esc(jm_notes)}"
    
    if idx is not None and total is not None and total > 0:
        text += "\n\n" + t(lang, "order_idx", i=idx + 1, n=total)
    
    return text

def build_tech_text(item: dict, idx: int | None, total: int | None, lang: str) -> str:
    """Texnik xizmat arizasi uchun text"""
    app_num = esc(item.get("application_number", "-"))
    client_name = esc(item.get("client_name", "-"))
    client_phone = esc(item.get("client_phone", "-"))
    address = esc(item.get("address", "-"))
    desc = item.get("description")
    created_dt = item.get("created_at")
    
    # Media ma'lumotlari
    media_file_id = item.get("media_file_id")
    media_type = item.get("media_type")
    
    text = (
        f"{t(lang,'title')}\n"
        f"{t(lang,'id')} {app_num}\n"
        f"{t(lang,'client')} {client_name}\n"
        f"{t(lang,'phone')} {client_phone}\n"
        f"{t(lang,'address')} {address}\n"
        f"{t(lang,'created')} {fmt_dt(created_dt)}"
    )
    
    if desc:
        text += f"\n{t(lang,'desc')} {esc(desc)}"
    
    # Media mavjudligini ko'rsatish
    if media_file_id and media_file_id.strip():
        if media_type == 'photo':
            text += f"\n📷 <b>Rasm:</b> Mavjud"
        elif media_type == 'video':
            text += f"\n🎥 <b>Video:</b> Mavjud"
        else:
            text += f"\n📎 <b>Media:</b> Mavjud"
    
    if idx is not None and total is not None and total > 0:
        text += "\n\n" + t(lang, "order_idx", i=idx + 1, n=total)
    
    return text

async def render_staff_item(message_or_cb, items: list, idx: int, lang: str, state: FSMContext):
    """Staff itemni ko'rsatish (rasm bilan)"""
    if not items or idx < 0 or idx >= len(items):
        return
    
    item = items[idx]
    text = build_staff_text(item, idx, len(items), lang)
    kb = nav_keyboard(idx, len(items), str(item["id"]), lang, "staff")
    
    media_file_id = item.get("media_file_id")
    media_type = item.get("media_type")
    
    try:
        if isinstance(message_or_cb, CallbackQuery):
            # Callback: mavjud xabarni  bilan almashtirishning keragi yo'q — matnni edit qilamiz
            await message_or_cb.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
        else:
            try:
                await message_or_cb.delete()
            except:
                pass
            
            # Media mavjudligini tekshirish va yuborish
            if media_file_id and media_file_id.strip():
                kind = _detect_media_kind(media_file_id, media_type)
                logger.info(f"Controller staff item media: file_id={media_file_id}, type={media_type}, kind={kind}")
                
                try:
                    await _send_media_strict(
                        chat_id=message_or_cb.chat.id,
                        file_id=media_file_id,
                        caption=text,
                        kb=kb,
                        media_kind=kind
                    )
                    return  # Muvaffaqiyatli yuborilgan bo'lsa, chiqamiz
                except Exception as media_error:
                    logger.error(f"Staff media send failed, falling back to text: {media_error}")
                    # Media yuborishda xatolik bo'lsa, faqat matn yuboramiz
                    await bot.send_message(message_or_cb.chat.id, text, parse_mode='HTML', reply_markup=kb)
            else:
                # Media yo'q bo'lsa, faqat matn yuboramiz
                await bot.send_message(message_or_cb.chat.id, text, parse_mode='HTML', reply_markup=kb)
    except Exception as e:
        logger.error(f"Error sending staff item with media: {e}")
        try:
            if isinstance(message_or_cb, CallbackQuery):
                await message_or_cb.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
            else:
                await bot.send_message(message_or_cb.chat.id, text, parse_mode='HTML', reply_markup=kb)
        except Exception as final_error:
            logger.error(f"Final fallback failed: {final_error}")

def build_staff_text(item: dict, idx: int | None, total: int | None, lang: str) -> str:
    """Xodim yaratgan arizalar uchun text"""
    app_num = esc(item.get("application_number", "-"))
    req_type = esc(item.get("type_of_zayavka", "-"))
    
    # Mijoz (abonent) ma'lumotlari
    client_name = esc(item.get("client_name", "-"))
    client_phone = esc(item.get("client_phone", "-"))
    
    # Yaratgan xodim ma'lumotlari
    staff_name = esc(item.get("staff_name", "-"))
    staff_phone = esc(item.get("staff_phone", "-"))
    staff_role = esc(item.get("staff_role", "-"))
    
    address = esc(item.get("address", "-"))
    desc = item.get("description")
    tariff_or_problem = esc(item.get("tariff_or_problem", "-"))
    created_dt = item.get("created_at")
    
    # Media fayl ma'lumotlari
    media_file_id = item.get("media_file_id")
    media_type = item.get("media_type")
    
    # Ariza turiga qarab label o'zgartirish
    if item.get("type_of_zayavka") == "connection":
        tariff_label = t(lang, "tariff")
    else:  # technician
        tariff_label = t(lang, "problem")
    
    text = (
        f"{t(lang,'title')}\n"
        f"{t(lang,'id')} {app_num}\n"
        f"{t(lang,'req_type')} {req_type}\n"
        f"{tariff_label} {tariff_or_problem}\n\n"
        f"{t(lang,'abonent')}\n"
        f"  • {client_name}\n"
        f"  • {client_phone}\n\n"
        f"{t(lang,'creator')}\n"
        f"  • {staff_name} ({staff_role})\n"
        f"  • {staff_phone}\n\n"
        f"{t(lang,'address')} {address}\n"
        f"{t(lang,'created')} {fmt_dt(created_dt)}"
    )
    
    if desc:
        text += f"\n{t(lang,'desc')} {esc(desc)}"
    
    # Media fayl mavjudligini ko'rsatish
    if media_file_id and media_file_id.strip():
        if media_type == 'photo':
            text += f"\n📷 <b>Rasm:</b> Mavjud"
        elif media_type == 'video':
            text += f"\n🎥 <b>Video:</b> Mavjud"
        else:
            text += f"\n📎 <b>Fayl:</b> Mavjud"
    
    if idx is not None and total is not None and total > 0:
        text += "\n\n" + t(lang, "order_idx", i=idx + 1, n=total)
    
    return text

# ========== Keyboards ==========

async def build_assign_keyboard_tech_only(full_id: str, lang: str) -> InlineKeyboardMarkup:
    """Faqat texniklar ro'yxati (connection uchun)"""
    rows = []
    load_suffix = "ta" if lang == "uz" else ""
    
    
    technicians = await get_technicians_with_load_via_history()
    if technicians:
        for tech in technicians:
            load = tech.get("load_count", 0) or 0
            title = f"🔧 {tech.get('full_name', '—')} ({load}{load_suffix})"
            rows.append([InlineKeyboardButton(
                text=title, callback_data=f"ctrl_inbox_tech_{full_id}_{tech['id']}")])
    else:
        rows.append([InlineKeyboardButton(text=t(lang, "no_techs"), callback_data="noop")])
    
    rows.append([InlineKeyboardButton(text=t(lang, "back"), callback_data=f"ctrl_inbox_back_{full_id}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

async def build_assign_keyboard_tech_and_ccs(full_id: str, lang: str) -> InlineKeyboardMarkup:
    """Texniklar va CCS ro'yxati (tech va staff uchun)"""
    rows = []
    
    # Texnikka yuborish tugmasi
    rows.append([InlineKeyboardButton(text=t(lang, "btn_assign_tech"), callback_data=f"ctrl_inbox_to_tech_{full_id}")])
    
    # CCS ga yuborish tugmasi (1ta CCS)
    rows.append([InlineKeyboardButton(text="👔 CCS ga yuborish" if lang == "uz" else "👔 Отправить в CCS", 
                                      callback_data=f"ctrl_inbox_to_ccs_{full_id}")])
    
    rows.append([InlineKeyboardButton(text=t(lang, "back"), callback_data=f"ctrl_inbox_back_{full_id}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

async def build_tech_list_keyboard(full_id: str, lang: str) -> InlineKeyboardMarkup:
    """Texniklar ro'yxati"""
    rows = []
    load_suffix = "ta" if lang == "uz" else ""
    
    technicians = await get_technicians_with_load_via_history()
    if technicians:
        for tech in technicians:
            load = tech.get("load_count", 0) or 0
            title = f"🔧 {tech.get('full_name', '—')} ({load}{load_suffix})"
            rows.append([InlineKeyboardButton(
                text=title, callback_data=f"ctrl_inbox_tech_{full_id}_{tech['id']}")])
    else:
        rows.append([InlineKeyboardButton(text=t(lang, "no_techs"), callback_data="noop")])
    
    rows.append([InlineKeyboardButton(text=t(lang, "back"), callback_data=f"ctrl_inbox_assign_{full_id}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def nav_keyboard(index: int, total: int, current_id: str, lang: str, mode: str) -> InlineKeyboardMarkup:
    """
    mode: 'connection', 'tech', 'staff'
    """
    rows = []
    nav_row = []
    
    if index > 0:
        nav_row.append(InlineKeyboardButton(text=t(lang, "btn_prev"), callback_data=f"ctrl_inbox_prev_{index}"))
    if index < total - 1:
        nav_row.append(InlineKeyboardButton(text=t(lang, "btn_next"), callback_data=f"ctrl_inbox_next_{index}"))
    
    if nav_row:
        rows.append(nav_row)
    
    # Assign button
    if mode == "connection":
        assign_text = t(lang, "btn_assign_tech")
    else:
        assign_text = t(lang, "btn_assign_tech_ccs")
    
    rows.append([InlineKeyboardButton(text=assign_text, callback_data=f"ctrl_inbox_assign_{current_id}")])
    rows.append([InlineKeyboardButton(text=t(lang, "btn_sections_back"), callback_data="ctrl_inbox_cat_back")])
    
    return InlineKeyboardMarkup(inline_keyboard=rows)

def category_keyboard(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=t(lang, "cat_conn"), callback_data="ctrl_inbox_cat_connection")],
            [InlineKeyboardButton(text=t(lang, "cat_tech"), callback_data="ctrl_inbox_cat_tech")],
            [InlineKeyboardButton(text=t(lang, "cat_staff"), callback_data="ctrl_inbox_cat_staff")],
        ]
    )

# ========== Handlers ==========

@router.message(F.text.in_(["📥 Inbox", "📥 Входящие"]))
async def open_inbox(message: Message, state: FSMContext):
    user = await get_user_by_telegram_id(message.from_user.id)
    if not user or user.get("role") != "controller":
        return
    lang = detect_lang_from_message(message.text)
    await state.update_data(lang=lang, inbox=[], idx=0, mode="connection")
    await message.answer(t(lang, "choose_cat"), reply_markup=category_keyboard(lang))

@router.callback_query(F.data == "ctrl_inbox_cat_connection")
async def cat_connection_flow(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    data = await state.get_data()
    lang = normalize_lang(data.get("lang"))
    items = await fetch_controller_inbox_connection(limit=50, offset=0)
    if not items:
        try:
            await cb.message.edit_text(t(lang, "empty_conn"), reply_markup=category_keyboard(lang))
        except TelegramBadRequest:
            pass
        return
    
    await state.update_data(mode="connection", inbox=items, idx=0)
    text = build_connection_text(items[0], idx=0, total=len(items), lang=lang)
    kb = nav_keyboard(0, len(items), str(items[0]["id"]), lang, "connection")
    
    try:
        await cb.message.delete()
    except:
        pass
    
    await cb.message.answer(text, reply_markup=kb, parse_mode="HTML")

@router.callback_query(F.data == "ctrl_inbox_cat_tech")
async def cat_tech_flow(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    data = await state.get_data()
    lang = normalize_lang(data.get("lang"))
    
    try:
        items = await fetch_controller_inbox_tech(limit=50, offset=0)
        logger.info(f"Fetched {len(items) if items else 0} tech items for controller")
        
        if not items:
            try:
                await cb.message.edit_text(t(lang, "empty_tech"), reply_markup=category_keyboard(lang))
            except TelegramBadRequest:
                pass
            return
        
        await state.update_data(mode="tech", inbox=items, idx=0)
        
        # Eski messageni o'chirish
        try:
            await cb.message.delete()
        except:
            pass
        
        # Birinchi itemni ko'rsatish (rasm bilan)
        await render_tech_item(cb.message, items, 0, lang, state)
        
    except Exception as e:
        logger.error(f"Error in cat_tech_flow: {e}")
        try:
            await cb.message.edit_text(f"❌ Xatolik yuz berdi: {str(e)}", reply_markup=category_keyboard(lang))
        except:
            pass

@router.callback_query(F.data == "ctrl_inbox_cat_staff")
async def cat_staff_flow(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    data = await state.get_data()
    lang = normalize_lang(data.get("lang"))
    
    try:
        items = await fetch_controller_inbox_staff(limit=50, offset=0)
        logger.info(f"Fetched {len(items) if items else 0} staff items for controller")
        
        if not items:
            try:
                await cb.message.edit_text(t(lang, "empty_staff"), reply_markup=category_keyboard(lang))
            except TelegramBadRequest:
                pass
            return
        
        await state.update_data(mode="staff", inbox=items, idx=0)
        
        # Eski messageni o'chirish
        try:
            await cb.message.delete()
        except:
            pass
        
        # Birinchi itemni ko'rsatish (rasm bilan)
        await render_staff_item(cb.message, items, 0, lang, state)
        
    except Exception as e:
        logger.error(f"Error in cat_staff_flow: {e}")
        try:
            await cb.message.edit_text(f"❌ Xatolik yuz berdi: {str(e)}", reply_markup=category_keyboard(lang))
        except:
            pass

async def render_tech_item(message, items: list, idx: int, lang: str, state: FSMContext):
    """Texnik xizmat arizasini media bilan ko'rsatish"""
    if idx < 0 or idx >= len(items):
        return
    
    item = items[idx]
    text = build_tech_text(item, idx, len(items), lang)
    kb = nav_keyboard(idx, len(items), str(item["id"]), lang, "tech")
    
    media_file_id = item.get("media_file_id")
    media_type = item.get("media_type")
    
    try:
        # Eski messageni o'chirish
        try:
            await message.delete()
        except:
            pass
        
        # Media mavjudligini tekshirish va yuborish
        if media_file_id and media_file_id.strip():
            kind = _detect_media_kind(media_file_id, media_type)
            logger.info(f"Controller tech item media: file_id={media_file_id}, type={media_type}, kind={kind}")
            
            # Media yuborishni sinab ko'rish
            try:
                await _send_media_strict(
                    chat_id=message.chat.id,
                    file_id=media_file_id,
                    caption=text,
                    kb=kb,
                    media_kind=kind
                )
                return  # Muvaffaqiyatli yuborilgan bo'lsa, chiqamiz
            except Exception as media_error:
                logger.error(f"Media send failed, falling back to text: {media_error}")
                # Media yuborishda xatolik bo'lsa, faqat matn yuboramiz
                await bot.send_message(message.chat.id, text, parse_mode='HTML', reply_markup=kb)
        else:
            # Media yo'q bo'lsa, faqat matn yuboramiz
            await bot.send_message(message.chat.id, text, parse_mode='HTML', reply_markup=kb)
    except Exception as e:
        logger.error(f"Error rendering tech item: {e}")
        try:
            await bot.send_message(message.chat.id, text, parse_mode='HTML', reply_markup=kb)
        except Exception as final_error:
            logger.error(f"Final fallback failed: {final_error}")

@router.callback_query(F.data.startswith("ctrl_inbox_prev_"))
async def prev_item(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    data = await state.get_data()
    items = data.get("inbox", []) or []
    lang = normalize_lang(data.get("lang"))
    mode = data.get("mode", "connection")
    
    try:
        cur = int(cb.data.replace("ctrl_inbox_prev_", ""))
    except ValueError:
        logger.error(f"Invalid prev callback data: {cb.data}")
        return
    
    idx = max(0, cur - 1)
    if not items or idx < 0 or idx >= len(items):
        logger.warning(f"Invalid index for prev: idx={idx}, items_count={len(items)}")
        return
    
    await state.update_data(idx=idx)
    
    # Eski messageni o'chirish
    try:
        await cb.message.delete()
    except:
        pass
    
    # Yangi message yuborish
    try:
        if mode == "connection":
            text = build_connection_text(items[idx], idx, len(items), lang)
            kb = nav_keyboard(idx, len(items), str(items[idx]["id"]), lang, mode)
            await bot.send_message(cb.message.chat.id, text, reply_markup=kb, parse_mode="HTML")
        elif mode == "tech":
            await render_tech_item(cb.message, items, idx, lang, state)
        else:  # staff
            await render_staff_item(cb.message, items, idx, lang, state)
    except Exception as e:
        logger.error(f"Error in prev_item: {e}")
        try:
            await cb.answer("❌ Xatolik yuz berdi", show_alert=True)
        except:
            pass

@router.callback_query(F.data.startswith("ctrl_inbox_next_"))
async def next_item(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    data = await state.get_data()
    items = data.get("inbox", []) or []
    lang = normalize_lang(data.get("lang"))
    mode = data.get("mode", "connection")
    
    try:
        cur = int(cb.data.replace("ctrl_inbox_next_", ""))
    except ValueError:
        logger.error(f"Invalid next callback data: {cb.data}")
        return
    
    idx = min(cur + 1, len(items) - 1)
    if not items or idx < 0 or idx >= len(items):
        logger.warning(f"Invalid index for next: idx={idx}, items_count={len(items)}")
        return
    
    await state.update_data(idx=idx)
    
    # Eski messageni o'chirish
    try:
        await cb.message.delete()
    except:
        pass
    
    # Yangi message yuborish
    try:
        if mode == "connection":
            text = build_connection_text(items[idx], idx, len(items), lang)
            kb = nav_keyboard(idx, len(items), str(items[idx]["id"]), lang, mode)
            await bot.send_message(cb.message.chat.id, text, reply_markup=kb, parse_mode="HTML")
        elif mode == "tech":
            await render_tech_item(cb.message, items, idx, lang, state)
        else:  # staff
            await render_staff_item(cb.message, items, idx, lang, state)
    except Exception as e:
        logger.error(f"Error in next_item: {e}")
        try:
            await cb.answer("❌ Xatolik yuz berdi", show_alert=True)
        except:
            pass

@router.callback_query(F.data.startswith("ctrl_inbox_assign_"))
async def assign_open(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    full_id = cb.data.replace("ctrl_inbox_assign_", "")
    data = await state.get_data()
    lang = normalize_lang(data.get("lang"))
    mode = data.get("mode", "connection")
    items = data.get("inbox", []) or []
    
    # Order ID ni olish
    order_id = int(full_id.split("_")[0]) if "_" in full_id else int(full_id)
    
    # Order ma'lumotlarini topish va application_number ni olish
    application_number = str(order_id)  # Default fallback
    for item in items:
        if item.get("id") == order_id:
            application_number = item.get("application_number", str(order_id))
            break
    
    # Mode bo'yicha keyboard tanlash
    if mode == "connection":
        kb = await build_assign_keyboard_tech_only(full_id, lang)
        text = f"{t(lang,'tech_pick_title_only')}\n🆔 {esc(application_number)}"
    else:  # tech yoki staff
        kb = await build_assign_keyboard_tech_and_ccs(full_id, lang)
        text = f"{t(lang,'tech_pick_title')}\n🆔 {esc(application_number)}"
    
    # Eski messageni o'chirish va yangi yuborish
    try:
        await cb.message.delete()
    except:
        pass
    
    await bot.send_message(cb.message.chat.id, text, reply_markup=kb, parse_mode="HTML")

@router.callback_query(F.data.startswith("ctrl_inbox_to_tech_"))
async def show_tech_list(cb: CallbackQuery, state: FSMContext):
    """Texniklar ro'yxatini ko'rsatish"""
    await cb.answer()
    full_id = cb.data.replace("ctrl_inbox_to_tech_", "")
    data = await state.get_data()
    lang = normalize_lang(data.get("lang"))
    items = data.get("inbox", []) or []
    
    # Order ID ni olish
    order_id = int(full_id.split("_")[0]) if "_" in full_id else int(full_id)
    
    # Order ma'lumotlarini topish va application_number ni olish
    application_number = str(order_id)  # Default fallback
    for item in items:
        if item.get("id") == order_id:
            application_number = item.get("application_number", str(order_id))
            break
    
    kb = await build_tech_list_keyboard(full_id, lang)
    text = f"{t(lang,'tech_pick_title_only')}\n🆔 {esc(application_number)}"
    
    try:
        await cb.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    except TelegramBadRequest:
        pass

@router.callback_query(F.data.startswith("ctrl_inbox_to_ccs_"))
async def assign_to_ccs_direct(cb: CallbackQuery, state: FSMContext):
    """CCS ga to'g'ridan-to'g'ri yuborish (1ta CCS)"""
    await cb.answer()
    full_id = cb.data.replace("ctrl_inbox_to_ccs_", "")
    data = await state.get_data()
    lang = normalize_lang(data.get("lang"))
    mode = data.get("mode", "tech")
    items = data.get("inbox", []) or []
    
    user = await get_user_by_telegram_id(cb.from_user.id)
    if not user:
        await cb.answer(t(lang, "no_user"), show_alert=True)
        return
    
    # Connection arizalari CCS ga yuborilmaydi!
    if mode == "connection":
        await cb.answer(
            "❌ Ulanish arizalari faqat texnikka yuboriladi!" if lang == "uz" 
            else "❌ Заявки на подключение отправляются только технику!",
            show_alert=True
        )
        return
    
    # 1ta CCS ni topish
    ccs_list = await get_ccs_supervisors_with_load()
    if not ccs_list:
        await cb.answer(t(lang, "no_ccs"), show_alert=True)
        return
    
    # Eng kam yuklangan CCS ni olish
    selected_ccs = ccs_list[0]
    ccs_id = selected_ccs.get("id")
    
    try:
        request_id = int(full_id.split("_")[0]) if "_" in full_id else int(full_id)
        
        if mode == "tech":
            result = await assign_to_ccs_tech(request_id=request_id, ccs_id=ccs_id, actor_id=user["id"])
        elif mode == "staff":
            result = await assign_to_ccs_staff(request_id=request_id, ccs_id=ccs_id, actor_id=user["id"])
        elif mode == "connection":
            await cb.answer(
                "❌ Ulanish arizalari CCS ga yuborilmaydi!" if lang == "uz"
                else "❌ Заявки на подключение не отправляются в CCS!",
                show_alert=True
            )
            return
        else:
            await cb.answer("❌ Noto'g'ri mode", show_alert=True)
            return
        
        # Notification yuborish
        if result:
            notif_lang = normalize_lang(result.get("language"))
            app_num = result.get("application_number", "")
            load = result.get("current_load", 0)
            
            if notif_lang == "uz":
                notif_text = f"👔 Yangi ariza: {app_num}\nSizda yana {load}ta ariza bor."
            else:
                notif_text = f"👔 Новая заявка: {app_num}\nУ вас ещё {load} заявок."
            
            try:
                await bot.send_message(result["telegram_id"], notif_text)
            except Exception as e:
                logger.error(f"Failed to send notification: {e}")
    
    except Exception as e:
        await cb.answer(f"{t(lang,'error_generic')} {str(e)}", show_alert=True)
        logger.error(f"Error assigning to CCS: {e}")
        return
    
    # Eski messageni o'chirish
    try:
        await cb.message.delete()
    except:
        pass
    
    # Confirmation yuborish
    app_num_short = full_id.split("_")[0] if "_" in full_id else full_id
    
    # Actual application_number ni olish
    actual_app_number = app_num_short  # Default fallback
    if result and result.get("application_number"):
        actual_app_number = result.get("application_number")
    else:
        # Fallback: items dan qidirish
        items = data.get("inbox", []) or []
        order_id = int(app_num_short)
        for item in items:
            if item.get("id") == order_id:
                actual_app_number = item.get("application_number", app_num_short)
                break
    
    confirmation_text = (
        f"{t(lang,'ok_assigned_title')}\n\n"
        f"{t(lang,'order_id')} {esc(actual_app_number)}\n"
        f"{t(lang,'ccs')} {esc(selected_ccs.get('full_name','—'))}\n"
        f"{t(lang,'sent_time')} {fmt_dt(datetime.now())}\n"
        f"{t(lang,'sender')} {esc(user.get('full_name', 'Controller'))}"
    )
    
    await bot.send_message(cb.message.chat.id, confirmation_text, parse_mode="HTML")
    
    # Itemni listdan o'chirish
    items = [it for it in items if str(it.get("id")) != full_id]
    await state.update_data(inbox=items)
    
    # Inbox'ni qaytib ochish - mode bo'yicha
    if items:  # Agar boshqa arizalar bo'lsa
        try:
            await cb.message.delete()
        except:
            pass
        
        # Mode bo'yicha tegishli inbox funksiyasini chaqirish
        if mode == "connection":
            await render_tech_item(cb.message, items, 0, lang, state)  # Temporary fix
        elif mode == "tech":
            await render_tech_item(cb.message, items, 0, lang, state)
        elif mode == "staff":
            await render_staff_item(cb.message, items, 0, lang, state)
    
    await cb.answer()

@router.callback_query(F.data.startswith("ctrl_inbox_tech_"))
async def assign_to_tech(cb: CallbackQuery, state: FSMContext):
    """Texnikka yuborish"""
    data = await state.get_data()
    lang = normalize_lang(data.get("lang"))
    mode = data.get("mode", "connection")
    items = data.get("inbox", []) or []
    
    try:
        raw = cb.data.replace("ctrl_inbox_tech_", "")
        full_id, tech_id_str = raw.rsplit("_", 1)
        tech_id = int(tech_id_str)
    except ValueError:
        await cb.answer(t(lang, "bad_format"), show_alert=True)
        return
    
    user = await get_user_by_telegram_id(cb.from_user.id)
    if not user:
        await cb.answer(t(lang, "no_user"), show_alert=True)
        return
    
    technicians = await get_users_by_role("technician")
    selected_tech = next((tech for tech in technicians if tech.get("id") == tech_id), None)
    if not selected_tech:
        await cb.answer(t(lang, "no_tech_one"), show_alert=True)
        return
    
    try:
        request_id = int(full_id.split("_")[0]) if "_" in full_id else int(full_id)
        
        if mode == "connection":
            result = await assign_to_technician_connection(request_id=request_id, tech_id=tech_id, actor_id=user["id"])
        elif mode == "tech":
            result = await assign_to_technician_tech(request_id=request_id, tech_id=tech_id, actor_id=user["id"])
        else:  # staff
            result = await assign_to_technician_staff(request_id=request_id, tech_id=tech_id, actor_id=user["id"])
        
        # Notification yuborish - markaziy helper orqali
        if result:
            try:
                from utils.notification_service import send_cross_role_notification
                await send_cross_role_notification(
                    bot,
                    sender_role=result.get("sender_role", "controller"),
                    recipient_role=result.get("recipient_role", "technician"),
                    sender_id=result.get("sender_id"),
                    recipient_id=result.get("recipient_id"),
                    creator_id=result.get("creator_id"),
                    recipient_telegram_id=result.get("telegram_id"),
                    application_number=result.get("application_number") or f"ID:{request_id}",
                    order_type=result.get("order_type", "technician"),
                    current_load=result.get("current_load", 0),
                    lang=result.get("language") or "uz",
                )
            except Exception as e:
                logger.error(f"Failed to send notification: {e}")
    
    except Exception as e:
        await cb.answer(f"{t(lang,'error_generic')} {str(e)}", show_alert=True)
        logger.error(f"Error assigning to tech: {e}")
        return
    
    # Eski messageni o'chirish
    try:
        await cb.message.delete()
    except:
        pass
    
    # Confirmation yuborish
    app_num_short = full_id.split("_")[0] if "_" in full_id else full_id
    
    actual_app_number = app_num_short  
    if result and result.get("application_number"):
        actual_app_number = result.get("application_number")
    else:
        # Fallback: items dan qidirish
        items = data.get("inbox", []) or []
        order_id = int(app_num_short)
        for item in items:
            if item.get("id") == order_id:
                actual_app_number = item.get("application_number", app_num_short)
                break
    
    confirmation_text = (
        f"{t(lang,'ok_assigned_title')}\n\n"
        f"{t(lang,'order_id')} {esc(actual_app_number)}\n"
        f"{t(lang,'tech')} {esc(selected_tech.get('full_name','—'))}\n"
        f"{t(lang,'sent_time')} {fmt_dt(datetime.now())}\n"
        f"{t(lang,'sender')} {esc(user.get('full_name', 'Controller'))}"
    )
    
    await bot.send_message(cb.message.chat.id, confirmation_text, parse_mode="HTML")
    
    # Itemni listdan o'chirish
    items = [it for it in items if str(it.get("id")) != full_id]
    await state.update_data(inbox=items)
    
    # Inbox'ni qaytib ochish - mode bo'yicha
    if items:  # Agar boshqa arizalar bo'lsa
        try:
            await cb.message.delete()
        except:
            pass
        
        # Mode bo'yicha tegishli inbox funksiyasini chaqirish
        if mode == "connection":
            await render_tech_item(cb.message, items, 0, lang, state)  # Temporary fix
        elif mode == "tech":
            await render_tech_item(cb.message, items, 0, lang, state)
        elif mode == "staff":
            await render_staff_item(cb.message, items, 0, lang, state)
    
    await cb.answer()


@router.callback_query(F.data.startswith("ctrl_inbox_back_"))
async def assign_back(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    full_id = cb.data.replace("ctrl_inbox_back_", "")
    data = await state.get_data()
    items = data.get("inbox", []) or []
    lang = normalize_lang(data.get("lang"))
    mode = data.get("mode", "connection")
    idx = int(data.get("idx", 0))
    
    if not items:
        try:
            await cb.message.delete()
        except:
            pass
        await bot.send_message(cb.message.chat.id, t(lang, "choose_cat"), reply_markup=category_keyboard(lang))
        return
    
    try:
        idx = next(i for i, it in enumerate(items) if str(it.get("id")) == full_id)
    except StopIteration:
        idx = max(0, min(idx, len(items) - 1))
    
    await state.update_data(idx=idx)
    
    # Eski messageni o'chirish
    try:
        await cb.message.delete()
    except:
        pass
    
    # Yangi message yuborish
    if mode == "connection":
        text = build_connection_text(items[idx], idx, len(items), lang)
        kb = nav_keyboard(idx, len(items), str(items[idx]["id"]), lang, mode)
        await bot.send_message(cb.message.chat.id, text, reply_markup=kb, parse_mode="HTML")
    elif mode == "tech":
        await render_tech_item(cb.message, items, idx, lang, state)
    else:  # staff
        await render_staff_item(cb.message, items, idx, lang, state)

@router.callback_query(F.data == "ctrl_inbox_cat_back")
async def cat_back(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    data = await state.get_data()
    lang = normalize_lang(data.get("lang"))
    await state.update_data(inbox=[], idx=0)
    
    try:
        await cb.message.delete()
    except:
        pass
    
    await bot.send_message(cb.message.chat.id, t(lang, "choose_cat"), reply_markup=category_keyboard(lang))

@router.callback_query(F.data == "noop")
async def noop(cb: CallbackQuery):
    await cb.answer()
