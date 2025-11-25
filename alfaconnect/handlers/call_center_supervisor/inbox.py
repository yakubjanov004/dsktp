# handlers/call_center_supervisor/inbox.py
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto, InputMediaDocument, InputMediaVideo
from aiogram.exceptions import TelegramBadRequest
from typing import Optional, Dict, Any
import html
from datetime import datetime
import logging
import asyncpg
from config import settings

from filters.role_filter import RoleFilter
from database.basic.language import get_user_language
from database.call_center_supervisor.inbox import (
    ccs_count_technician_orders,
    ccs_fetch_technician_orders,
    ccs_count_staff_orders,
    ccs_fetch_staff_orders,
    ccs_count_operator_orders,
    ccs_fetch_operator_orders,
    ccs_send_technician_to_operator,
    ccs_send_staff_to_operator,
    ccs_complete_technician_order,
    ccs_complete_staff_order
)

logger = logging.getLogger(__name__)

# =========================================================
# Router (role: callcenter_supervisor)
# =========================================================
router = Router()
router.message.filter(RoleFilter("callcenter_supervisor"))
router.callback_query.filter(RoleFilter("callcenter_supervisor"))

# ========== Media Type Detection Helper Functions ==========

def _detect_media_kind(file_id: str | None, media_type: str | None = None) -> str | None:
    """
    'photo' / 'video' / None qaytaradi.
    Avval DB'dagi media_type ga ishonamiz, yo'q bo'lsa Telegram API ga ishonamiz.
    """
    if not file_id:
        return None
    
    # DB'dan kelgan media_type ni tekshiramiz
    if media_type in {"photo", "video"}:
        return media_type

    # Agar file_path bo'lsa (media_files jadvalidan kelgan)
    if "/" in file_id:
        # Fayl kengaytmasi bo'yicha aniqlash
        file_ext = file_id.lower().split('.')[-1] if '.' in file_id else ''
        if file_ext in ['jpg', 'jpeg', 'png', 'gif', 'webp']:
            return "photo"
        elif file_ext in ['mp4', 'avi', 'mov', 'mkv', 'webm']:
            return "video"
    
    # Telegram file_id uchun - API o'zi aniqlaydi, biz faqat mavjudligini tekshiramiz
    # Agar file_id mavjud bo'lsa, uni yuborishga harakat qilamiz
    if file_id and len(file_id) > 10:  # Minimal file_id uzunligi
        return "photo"  # Default photo sifatida sinab ko'ramiz
    
    return None


async def _send_media_strict(target, file_id: str, caption: str, kb: InlineKeyboardMarkup, media_kind: str):
    """
    Media turiga qat'iy rioya qiladi. Agar server 'Video as Photo' kabi xatolik bersa,
    avtomatik ravishda teskari turga retry qiladi. Aks holda matnga fallback qiladi.
    
    file_id Telegram file_id yoki local file_path bo'lishi mumkin.
    """
    from aiogram.types import FSInputFile
    
    try:
        # Agar file_id local file_path bo'lsa, FSInputFile ishlatamiz
        media_input = None
        if "/" in file_id:
            # Local file_path
            media_input = FSInputFile(file_id)
        else:
            # Telegram file_id
            media_input = file_id
            
        if isinstance(target, Message):
            if media_kind == "photo":
                await target.answer_photo(photo=media_input, caption=caption, parse_mode="HTML", reply_markup=kb)
            elif media_kind == "video":
                await target.answer_video(video=media_input, caption=caption, parse_mode="HTML", reply_markup=kb)
            else:
                await target.answer(caption, parse_mode="HTML", reply_markup=kb)
        else:
            # CallbackQuery uchun
            if media_kind == "photo":
                await target.message.edit_media(
                    media=InputMediaPhoto(media=media_input, caption=caption, parse_mode="HTML"),
                    reply_markup=kb
                )
            elif media_kind == "video":
                await target.message.edit_media(
                    media=InputMediaVideo(media=media_input, caption=caption, parse_mode="HTML"),
                    reply_markup=kb
                )
            else:
                await target.message.edit_text(caption, parse_mode="HTML", reply_markup=kb)
    except TelegramBadRequest as e:
        msg = str(e)
        logger.error(f"_send_media_strict primary send failed: {msg}")

        # Avtomatik retry - agar photo bo'lsa video sifatida sinab ko'ramiz
        if media_kind == "photo":
            try:
                logger.info(f"Retrying as video: {file_id}")
                if isinstance(target, Message):
                    await target.answer_video(video=media_input, caption=caption, parse_mode="HTML", reply_markup=kb)
                else:
                    await target.message.edit_media(
                        media=InputMediaVideo(media=media_input, caption=caption, parse_mode="HTML"),
                        reply_markup=kb
                    )
                return
            except Exception as e2:
                logger.error(f"_send_media_strict retry as video failed: {e2}")

        # Aks holda matnga fallback
        if isinstance(target, Message):
            await target.answer(caption, parse_mode="HTML", reply_markup=kb)
        else:
            await target.message.edit_text(caption, parse_mode="HTML", reply_markup=kb)
    except Exception as e:
        logger.error(f"_send_media_strict unexpected error: {e}")
        if isinstance(target, Message):
            await target.answer(caption, parse_mode="HTML", reply_markup=kb)
        else:
            await target.message.edit_text(caption, parse_mode="HTML", reply_markup=kb)

# =========================================================
# Region mapping (id -> human title)
# =========================================================
REGION_CODE_TO_ID = {
    "toshkent_city": 1, "toshkent_region": 2, "andijon": 3, "fergana": 4, "namangan": 5,
    "sirdaryo": 6, "jizzax": 7, "samarkand": 8, "bukhara": 9, "navoi": 10,
    "kashkadarya": 11, "surkhandarya": 12, "khorezm": 13, "karakalpakstan": 14,
}
REGION_TITLES = {
    "toshkent_city": "Toshkent shahri",
    "toshkent_region": "Toshkent viloyati",
    "andijon": "Andijon",
    "fergana": "Farg'ona",
    "namangan": "Namangan",
    "sirdaryo": "Sirdaryo",
    "jizzax": "Jizzax",
    "samarkand": "Samarqand",
    "bukhara": "Buxoro",
    "navoi": "Navoiy",
    "kashkadarya": "Qashqadaryo",
    "surkhandarya": "Surxondaryo",
    "khorezm": "Xorazm",
    "karakalpakstan": "Qoraqalpog'iston",
}
ID_TO_REGION_TITLE = {rid: REGION_TITLES[code] for code, rid in REGION_CODE_TO_ID.items()}

def region_title_from_id(rid: Optional[int]) -> str:
    if rid is None:
        return "-"
    try:
        return ID_TO_REGION_TITLE.get(int(rid), str(rid))
    except Exception:
        return str(rid)

def esc(text: str) -> str:
    """Escape HTML characters"""
    if text is None:
        return "-"
    return html.escape(str(text))

def fmt_dt(dt) -> str:
    """Format datetime for display"""
    if isinstance(dt, str):
        try:
            dt = datetime.fromisoformat(dt)
        except Exception:
            return esc(dt)
    if isinstance(dt, datetime):
        return dt.strftime("%d.%m.%Y %H:%M")
    return "-"

# =========================================================
# Main Inbox Handler - Category Selection
# =========================================================
@router.message(F.text.in_(["📥 Inbox", "📥 Входящие"]))
async def ccs_inbox(message: Message):
    """CCS inbox main handler - directly shows technician orders from controller"""
    # To'g'ridan-to'g'ri tech orders ko'rsatish
    await show_technician_orders(message)

# =========================================================
# Technician Orders Handlers
# =========================================================
@router.callback_query(F.data == "ccs_tech_orders")
async def show_technician_orders_cb(callback: CallbackQuery):
    """Show technician orders from controller (callback)"""
    await _show_technician_item_with_media(callback, idx=0, user_id=callback.from_user.id)

async def show_technician_orders(target):
    """Show technician orders from controller (both Message and CallbackQuery)"""
    user_id = target.from_user.id if hasattr(target, 'from_user') else target.message.from_user.id
    await _show_technician_item_with_media(target, idx=0, user_id=user_id)

async def _show_technician_item_with_media(target, idx: int, user_id: int):
    """Show technician order item with media support"""
    lang = await get_user_language(user_id) or "uz"
    
    total = await ccs_count_technician_orders()
    if total == 0:
        text = "📭 Texnik arizalar yo'q." if lang == "uz" else "📭 Технических заявок нет."
        if isinstance(target, Message):
            return await target.answer(text, parse_mode="HTML")
        return await target.message.edit_text(text, parse_mode="HTML")
    
    idx = max(0, min(idx, total - 1))
    row = await ccs_fetch_technician_orders(offset=idx, limit=1)
    if not row:
        idx = max(0, total - 1)
        row = await ccs_fetch_technician_orders(offset=idx, limit=1)
    
    kb = _tech_kb(idx, total, row["id"], lang)
    text = _format_technician_card(row, idx, total, lang)
    
    # Check if there's media to display
    media_path = row.get("media")
    
    if isinstance(target, Message):
        if media_path:
            # Media turiga qarab to'g'ri usuldan boshlaymiz
            media_type = row.get("media_type", "")
            if media_type == 'video':
                try:
                    return await target.answer_video(
                        video=media_path,
                        caption=text,
                        reply_markup=kb,
                        parse_mode="HTML"
                    )
                except Exception:
                    try:
                        return await target.answer_photo(
                            photo=media_path,
                            caption=text,
                            reply_markup=kb,
                            parse_mode="HTML"
                        )
                    except Exception:
                        try:
                            return await target.answer_document(
                                document=media_path,
                                caption=text,
                                reply_markup=kb,
                                parse_mode="HTML"
                            )
                        except Exception:
                            return await target.answer(text, parse_mode="HTML", reply_markup=kb)
            elif media_type == 'photo':
                try:
                    return await target.answer_photo(
                        photo=media_path,
                        caption=text,
                        reply_markup=kb,
                        parse_mode="HTML"
                    )
                except Exception:
                    try:
                        return await target.answer_video(
                            video=media_path,
                            caption=text,
                            reply_markup=kb,
                            parse_mode="HTML"
                        )
                    except Exception:
                        try:
                            return await target.answer_document(
                                document=media_path,
                                caption=text,
                                reply_markup=kb,
                                parse_mode="HTML"
                            )
                        except Exception:
                            return await target.answer(text, parse_mode="HTML", reply_markup=kb)
            else:
                # media_type yo'q yoki noma'lum - fallback zanjiri
                try:
                    return await target.answer_photo(
                        photo=media_path,
                        caption=text,
                        reply_markup=kb,
                        parse_mode="HTML"
                    )
                except Exception:
                    try:
                        return await target.answer_video(
                            video=media_path,
                            caption=text,
                            reply_markup=kb,
                            parse_mode="HTML"
                        )
                    except Exception:
                        try:
                            return await target.answer_document(
                                document=media_path,
                                caption=text,
                                reply_markup=kb,
                                parse_mode="HTML"
                            )
                        except Exception:
                            return await target.answer(text, parse_mode="HTML", reply_markup=kb)
        else:
            return await target.answer(text, parse_mode="HTML", reply_markup=kb)
    else:
        # For CallbackQuery, we need to handle media differently
        if media_path:
            # Media turiga qarab to'g'ri usuldan boshlaymiz
            media_type = row.get("media_type", "")
            if media_type == 'video':
                try:
                    return await target.message.edit_media(
                        media=InputMediaVideo(
                            media=media_path,
                            caption=text,
                            parse_mode="HTML"
                        ),
                        reply_markup=kb
                    )
                except Exception:
                    try:
                        return await target.message.edit_media(
                            media=InputMediaPhoto(
                                media=media_path,
                                caption=text,
                                parse_mode="HTML"
                            ),
                            reply_markup=kb
                        )
                    except Exception:
                        try:
                            return await target.message.edit_media(
                                media=InputMediaDocument(
                                    media=media_path,
                                    caption=text,
                                    parse_mode="HTML"
                                ),
                                reply_markup=kb
                            )
                        except Exception:
                            try:
                                await target.message.delete()
                                return await target.message.answer_video(
                                    video=media_path,
                                    caption=text,
                                    reply_markup=kb,
                                    parse_mode="HTML"
                                )
                            except Exception:
                                return await target.message.answer(text, parse_mode="HTML", reply_markup=kb)
            elif media_type == 'photo':
                try:
                    return await target.message.edit_media(
                        media=InputMediaPhoto(
                            media=media_path,
                            caption=text,
                            parse_mode="HTML"
                        ),
                        reply_markup=kb
                    )
                except Exception:
                    try:
                        return await target.message.edit_media(
                            media=InputMediaVideo(
                                media=media_path,
                                caption=text,
                                parse_mode="HTML"
                            ),
                            reply_markup=kb
                        )
                    except Exception:
                        try:
                            return await target.message.edit_media(
                                media=InputMediaDocument(
                                    media=media_path,
                                    caption=text,
                                    parse_mode="HTML"
                                ),
                                reply_markup=kb
                            )
                        except Exception:
                            try:
                                await target.message.delete()
                                return await target.message.answer_photo(
                                    photo=media_path,
                                    caption=text,
                                    reply_markup=kb,
                                    parse_mode="HTML"
                                )
                            except Exception:
                                return await target.message.answer(text, parse_mode="HTML", reply_markup=kb)
            else:
                # media_type yo'q yoki noma'lum - fallback zanjiri
                try:
                    return await target.message.edit_media(
                        media=InputMediaPhoto(
                            media=media_path,
                            caption=text,
                            parse_mode="HTML"
                        ),
                        reply_markup=kb
                    )
                except Exception:
                    try:
                        return await target.message.edit_media(
                            media=InputMediaVideo(
                                media=media_path,
                                caption=text,
                                parse_mode="HTML"
                            ),
                            reply_markup=kb
                        )
                    except Exception:
                        try:
                            return await target.message.edit_media(
                                media=InputMediaDocument(
                                    media=media_path,
                                    caption=text,
                                    parse_mode="HTML"
                                ),
                                reply_markup=kb
                            )
                        except Exception:
                            try:
                                await target.message.delete()
                                return await target.message.answer_photo(
                                    photo=media_path,
                                    caption=text,
                                    reply_markup=kb,
                                    parse_mode="HTML"
                                )
                            except Exception:
                                return await target.message.answer(text, parse_mode="HTML", reply_markup=kb)
        else:
            # Check if current message has media, if so delete and send new text message
            try:
                if target.message.photo or target.message.document or target.message.video:
                    await target.message.delete()
                    return await target.message.answer(text, parse_mode="HTML", reply_markup=kb)
                else:
                    return await target.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
            except Exception:
                # If edit fails, send new message
                return await target.message.answer(text, parse_mode="HTML", reply_markup=kb)

def _tech_kb(idx: int, total: int, order_id: int, lang: str = "uz") -> InlineKeyboardMarkup:
    """Technician orders keyboard"""
    prev_cb = f"ccs_tech_prev:{idx}"
    next_cb = f"ccs_tech_next:{idx}"
    send_to_operator_cb = f"ccs_tech_send_operator:{order_id}:{idx}"

    texts = {
        "uz": {
            "back": "◀️ Orqaga",
            "next": "▶️ Oldinga",
            "send_to_operator": "📤 Operatorga jo'natish"
        },
        "ru": {
            "back": "◀️ Назад",
            "next": "▶️ Далее",
            "send_to_operator": "📤 Отправить оператору"
        }
    }
    t = texts[lang]

    # Paginatsiya tugmalari mantiqiy tarzda ko'rinadi
    keyboard = []
    
    if total > 1:
        pagination_row = []
        
        # Orqaga tugmasi - faqat boshida bo'lmasa
        if idx > 0:
            pagination_row.append(InlineKeyboardButton(text=t["back"], callback_data=prev_cb))
        
        # Oldinga tugmasi - faqat oxirida bo'lmasa
        if idx < total - 1:
            pagination_row.append(InlineKeyboardButton(text=t["next"], callback_data=next_cb))
        
        if pagination_row:  # Agar kamida bitta tugma bo'lsa
            keyboard.append(pagination_row)
    
    keyboard.append([
        InlineKeyboardButton(text=t["send_to_operator"], callback_data=send_to_operator_cb)
    ])

    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def _format_technician_card(row: dict, idx: int, total: int, lang: str = "uz") -> str:
    """Format technician order card"""
    region_text = region_title_from_id(row.get("region"))
    client_name = esc(row.get("client_name") or "-")
    client_phone = esc(row.get("client_phone") or "-")
    abonent_id = esc(row.get("abonent_id") or "-")
    address = esc(row.get("address") or "-")
    description = esc(row.get("description") or "-")
    description_operator = esc(row.get("description_operator") or "-")
    business_type = esc(row.get("business_type") or "-")

    texts = {
        "uz": {
            "title": "🔧 <b>Texnik Ariza (Controllerdan)</b>",
            "id": "🆔",
            "client": "👤 <b>Mijoz:</b>",
            "phone": "📞 <b>Telefon:</b>",
            "abonent": "🆔 <b>Abonent ID:</b>",
            "region": "📍 <b>Region:</b>",
            "address": "🏠 <b>Manzil:</b>",
            "description": "📝 <b>Muammo:</b>",
            "operator_note": "📋 <b>Operator izohi:</b>",
            "media": "📷 <b>Rasm:</b> Mavjud",
            "business_type": "🏢 <b>Yo'nalish:</b>"
        },
        "ru": {
            "title": "🔧 <b>Техническая заявка (от Controller)</b>",
            "id": "🆔",
            "client": "👤 <b>Клиент:</b>",
            "phone": "📞 <b>Телефон:</b>",
            "abonent": "🆔 <b>ID абонента:</b>",
            "region": "📍 <b>Регион:</b>",
            "address": "🏠 <b>Адрес:</b>",
            "description": "📝 <b>Проблема:</b>",
            "operator_note": "📋 <b>Примечание оператора:</b>",
            "media": "📷 <b>Фото:</b> Есть",
            "business_type": "🏢 <b>Направление:</b>"
        }
    }
    t = texts[lang]

    media_text = f"\n{t['media']}" if row.get("media") else ""
    operator_note_text = f"\n{t['operator_note']} {description_operator}" if description_operator != "-" else ""

    return (
        f"{t['title']}\n"
        f"{t['id']} <b>{row.get('application_number', row['id'])}</b> <i>({idx+1}/{total})</i>\n\n"
        f"{t['client']} {client_name}\n"
        f"{t['phone']} {client_phone}\n"
        f"{t['abonent']} {abonent_id}\n"
        f"{t['region']} {region_text}\n"
        f"{t['address']} {address}\n"
        f"{t['description']} {description}{media_text}{operator_note_text}\n"
        f"{t['business_type']} {business_type}\n\n"
        f"📅 <b>Sana:</b> {fmt_dt(row.get('created_at'))}"
    )

@router.callback_query(F.data.startswith("ccs_tech_prev:"))
async def ccs_tech_prev(cb: CallbackQuery):
    cur = int(cb.data.split(":")[1])
    await _show_technician_item_with_media(cb, idx=cur - 1, user_id=cb.from_user.id)
    await cb.answer()

@router.callback_query(F.data.startswith("ccs_tech_next:"))
async def ccs_tech_next(cb: CallbackQuery):
    cur = int(cb.data.split(":")[1])
    await _show_technician_item_with_media(cb, idx=cur + 1, user_id=cb.from_user.id)
    await cb.answer()


@router.callback_query(F.data.startswith("ccs_tech_send_operator:"))
async def ccs_tech_send_operator(cb: CallbackQuery):
    """Texnik arizani operator'ga yuborish - operator tanlash"""
    _, order_id_raw, cur_raw = cb.data.split(":")
    order_id = int(order_id_raw)
    cur = int(cur_raw)
    
    lang = await get_user_language(cb.from_user.id) or "uz"
    
    # Operatorlarni olish
    import asyncpg
    from config import settings
    
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        operators = await conn.fetch("SELECT id, full_name, telegram_id FROM users WHERE role = 'callcenter_operator'")
        
        if not operators:
            await cb.answer(
                ("❌ Operatorlar mavjud emas!" if lang == "uz" else "❌ Операторы не найдены!"), 
                show_alert=True
            )
            return
        
        # Operatorlarni inline keyboard qilish
        keyboard = []
        for operator in operators:
            full_name = (operator.get('full_name') or '').strip() or f"ID: {operator['id']}"
            keyboard.append([
                InlineKeyboardButton(
                    text=f"👨‍💼 {full_name}",
                    callback_data=f"ccs_tech_select_operator:{order_id}:{cur}:{operator['id']}"
                )
            ])
        
        keyboard.append([
            InlineKeyboardButton(
                text=("◀️ Orqaga" if lang == "uz" else "◀️ Назад"),
                callback_data=f"ccs_tech_back_to_item:{order_id}:{cur}"
            )
        ])
        
        reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
        
        texts = {
            "uz": {
                "title": "👨‍💼 <b>Operatorni tanlang</b>",
                "subtitle": "Texnik arizani qaysi operatorga yubormoqchisiz?"
            },
            "ru": {
                "title": "👨‍💼 <b>Выберите оператора</b>",
                "subtitle": "Какому оператору отправить техническую заявку?"
            }
        }
        t = texts[lang]
        
        text = f"{t['title']}\n\n{t['subtitle']}\n\n🆔 <b>Ariza ID:</b> #{order_id}"
        
        await cb.message.edit_text(text, reply_markup=reply_markup, parse_mode="HTML")
        
    except Exception as e:
        logger.error(f"Failed to get operators: {e}")
        await cb.answer(
            ("❌ Operatorlarni olishda xatolik!" if lang == "uz" else "❌ Ошибка получения операторов!"), 
            show_alert=True
        )
    finally:
        await conn.close()

@router.callback_query(F.data.startswith("ccs_tech_select_operator:"))
async def ccs_tech_select_operator(cb: CallbackQuery):
    """Tanlangan operatorga texnik arizani yuborish"""
    _, order_id, cur, operator_id = cb.data.split(":")
    order_id = int(order_id)
    cur = int(cur)
    operator_id = int(operator_id)
    
    lang = await get_user_language(cb.from_user.id) or "uz"
    
    try:
        # Ariza ma'lumotlarini olish
        row = await ccs_fetch_technician_orders(order_id=order_id)
        if not row:
            await cb.answer(
                ("❌ Ariza topilmadi!" if lang == "uz" else "❌ Заявка не найдена!"), 
                show_alert=True
            )
            return
        
        # Operator ma'lumotlarini olish
        import asyncpg
        from config import settings
        
        conn = await asyncpg.connect(settings.DB_URL)
        try:
            operator = await conn.fetchrow("SELECT id, full_name, telegram_id, language FROM users WHERE id = $1", operator_id)
            if not operator:
                await cb.answer(
                    ("❌ Operator topilmadi!" if lang == "uz" else "❌ Оператор не найден!"), 
                    show_alert=True
                )
                return
            
            # Ariza holatini yangilash
            result = await conn.execute("""
                UPDATE technician_orders
                SET status = 'in_call_center_operator',
                    updated_at = NOW()
                WHERE id = $1 AND status = 'in_call_center_supervisor'
            """, order_id)
            
            if result == "UPDATE 0":
                await cb.answer(
                    ("❌ Ariza holati yangilanmadi!" if lang == "uz" else "❌ Статус заявки не обновлен!"), 
                    show_alert=True
                )
                return
            
            # Sender ID ni telegram_id dan internal user ID ga o'tkazish
            sender_user = await conn.fetchrow("SELECT id FROM users WHERE telegram_id = $1", cb.from_user.id)
            if not sender_user:
                await cb.answer(
                    ("❌ Foydalanuvchi topilmadi!" if lang == "uz" else "❌ Пользователь не найден!"), 
                    show_alert=True
                )
                return
            
            sender_id = sender_user['id']
            
            # Get application_number
            app_info = await conn.fetchrow("SELECT application_number FROM technician_orders WHERE id = $1", order_id)
            
            # Connection yaratish
            await conn.execute("""
                INSERT INTO connections(
                    application_number, sender_id, recipient_id,
                    sender_status, recipient_status,
                    created_at, updated_at
                )
                VALUES ($1, $2, $3, 'in_call_center_supervisor', 'in_call_center_operator', NOW(), NOW())
            """, app_info['application_number'], sender_id, operator_id)
            
            # Operator'ga notification yuborish
            if operator['telegram_id']:
                from loader import bot
                from utils.notification_service import send_role_notification
                
                await send_role_notification(
                    bot=bot,
                    recipient_telegram_id=operator['telegram_id'],
                    order_id=row.get('application_number', f"#{order_id}"),
                    order_type="technician",
                    current_load=1,
                    lang=operator.get('language', 'uz')
                )
                logger.info(f"Notification sent to operator {operator_id} for technician order {order_id}")
            
        finally:
            await conn.close()
        
        toast_text = {
            "uz": "✅ Ariza operatorga yuborildi",
            "ru": "✅ Заявка отправлена оператору"
        }.get(lang, "✅ Sent")

        await cb.answer(toast_text)
        await _show_technician_item_with_media(cb, idx=cur, user_id=cb.from_user.id)
        
    except Exception as e:
        logger.error(f"Failed to send technician order to operator: {e}")
        await cb.answer(
            (f"❌ Xatolik: {str(e)}" if lang == "uz" else f"❌ Ошибка: {str(e)}"), 
            show_alert=True
        )

@router.callback_query(F.data.startswith("ccs_tech_back_to_item:"))
async def ccs_tech_back_to_item(cb: CallbackQuery):
    """Operator tanlashdan ariza ko'rinishiga qaytish"""
    _, order_id, cur = cb.data.split(":")
    order_id = int(order_id)
    cur = int(cur)
    
    await _show_technician_item_with_media(cb, idx=cur, user_id=cb.from_user.id)
    await cb.answer()


# =========================================================
# Staff Orders Handlers
# =========================================================
@router.callback_query(F.data == "ccs_staff_orders")
async def show_staff_orders(callback: CallbackQuery):
    """Show staff orders from operators"""
    await _show_staff_item(callback, idx=0, user_id=callback.from_user.id)

async def _show_staff_item(target, idx: int, user_id: int):
    """Show staff order item"""
    lang = await get_user_language(user_id) or "uz"
    
    total = await ccs_count_staff_orders()
    if total == 0:
        text = "📭 Operator arizalari yo'q." if lang == "uz" else "📭 Заявок операторов нет."
        if isinstance(target, Message):
            return await target.answer(text, parse_mode="HTML")
        return await target.message.edit_text(text, parse_mode="HTML")
    
    idx = max(0, min(idx, total - 1))
    row = await ccs_fetch_staff_orders(offset=idx, limit=1)
    if not row:
        idx = max(0, total - 1)
        row = await ccs_fetch_staff_orders(offset=idx, limit=1)
    
    kb = _staff_kb(idx, total, row["id"], lang)
    text = _format_staff_card(row, idx, total, lang)
    
    if isinstance(target, Message):
        return await target.answer(text, parse_mode="HTML", reply_markup=kb)
    else:
        return await target.message.edit_text(text, parse_mode="HTML", reply_markup=kb)

def _staff_kb(idx: int, total: int, order_id: int, lang: str = "uz") -> InlineKeyboardMarkup:
    """Staff orders keyboard"""
    prev_cb = f"ccs_staff_prev:{idx}"
    next_cb = f"ccs_staff_next:{idx}"
    send_to_operator_cb = f"ccs_staff_send_operator:{order_id}:{idx}"
    back_cb = "ccs_back_to_categories"

    texts = {
        "uz": {
            "back": "◀️ Orqaga",
            "next": "▶️ Oldinga",
            "send_to_operator": "📤 Operatorga jo'natish",
            "categories": "🔙 Kategoriyalar"
        },
        "ru": {
            "back": "◀️ Назад",
            "next": "▶️ Далее",
            "send_to_operator": "📤 Отправить оператору",
            "categories": "🔙 Категории"
        }
    }
    t = texts[lang]

    # Paginatsiya tugmalari mantiqiy tarzda ko'rinadi
    keyboard = []
    
    if total > 1:
        pagination_row = []
        
        # Orqaga tugmasi - faqat boshida bo'lmasa
        if idx > 0:
            pagination_row.append(InlineKeyboardButton(text=t["back"], callback_data=prev_cb))
        
        # Oldinga tugmasi - faqat oxirida bo'lmasa
        if idx < total - 1:
            pagination_row.append(InlineKeyboardButton(text=t["next"], callback_data=next_cb))
        
        if pagination_row:  # Agar kamida bitta tugma bo'lsa
            keyboard.append(pagination_row)
    
    keyboard.append([
        InlineKeyboardButton(text=t["send_to_operator"], callback_data=send_to_operator_cb)
    ])
    keyboard.append([
        InlineKeyboardButton(text=t["categories"], callback_data=back_cb)
    ])

    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def _format_staff_card(row: dict, idx: int, total: int, lang: str = "uz") -> str:
    """Format staff order card"""
    region_text = region_title_from_id(row.get("region"))
    client_name = esc(row.get("client_name") or "-")
    client_phone = esc(row.get("client_phone") or "-")
    abonent_id = esc(row.get("abonent_id") or "-")
    address = esc(row.get("address") or "-")
    description = esc(row.get("description") or "-")
    operator_name = esc(row.get("operator_name") or "-")
    operator_phone = esc(row.get("operator_phone") or "-")
    operator_role = esc(row.get("operator_role") or "-")
    tariff_or_problem = esc(row.get("tariff_or_problem") or "-")
    order_type = row.get("type_of_zayavka", "unknown")

    texts = {
        "uz": {
            "title": "👥 <b>Operator Arizi</b>",
            "id": "🆔",
            "client": "👤 <b>Mijoz:</b>",
            "phone": "📞 <b>Telefon:</b>",
            "abonent": "🆔 <b>Abonent ID:</b>",
            "region": "📍 <b>Region:</b>",
            "address": "🏠 <b>Manzil:</b>",
            "operator": "👨‍💼 <b>Operator:</b>",
            "operator_phone": "📞 <b>Operator tel:</b>",
            "operator_role": "🎭 <b>Operator roli:</b>",
            "tariff": "💳 <b>Tarif:</b>",
            "problem": "📝 <b>Muammo:</b>",
            "description": "📄 <b>Tavsif:</b>",
            "connection": "🔌 Ulanish arizasi",
            "technician": "🔧 Texnik xizmat arizasi"
        },
        "ru": {
            "title": "👥 <b>Заявка оператора</b>",
            "id": "🆔",
            "client": "👤 <b>Клиент:</b>",
            "phone": "📞 <b>Телефон:</b>",
            "abonent": "🆔 <b>ID абонента:</b>",
            "region": "📍 <b>Регион:</b>",
            "address": "🏠 <b>Адрес:</b>",
            "operator": "👨‍💼 <b>Оператор:</b>",
            "operator_phone": "📞 <b>Тел оператора:</b>",
            "operator_role": "🎭 <b>Роль оператора:</b>",
            "tariff": "💳 <b>Тариф:</b>",
            "problem": "📝 <b>Проблема:</b>",
            "description": "📄 <b>Описание:</b>",
            "connection": "🔌 Заявка на подключение",
            "technician": "🔧 Заявка на техобслуживание"
        }
    }
    t = texts[lang]

    order_type_text = t["connection"] if order_type == "connection" else t["technician"]
    tariff_or_problem_label = t["tariff"] if order_type == "connection" else t["problem"]

    return (
        f"{t['title']}\n"
        f"{t['id']} <b>{row['id']}</b> <i>({idx+1}/{total})</i>\n"
        f"📋 <b>Ariza turi:</b> {order_type_text}\n\n"
        f"{t['client']} {client_name}\n"
        f"{t['phone']} {client_phone}\n"
        f"{t['abonent']} {abonent_id}\n"
        f"{t['region']} {region_text}\n"
        f"{t['address']} {address}\n"
        f"{tariff_or_problem_label} {tariff_or_problem}\n"
        f"{t['description']} {description}\n\n"
        f"{t['operator']} {operator_name}\n"
        f"{t['operator_phone']} {operator_phone}\n"
        f"{t['operator_role']} {operator_role}\n\n"
        f"📅 <b>Sana:</b> {fmt_dt(row.get('created_at'))}"
    )

@router.callback_query(F.data.startswith("ccs_staff_prev:"))
async def ccs_staff_prev(cb: CallbackQuery):
    cur = int(cb.data.split(":")[1])
    await _show_staff_item(cb, idx=cur - 1, user_id=cb.from_user.id)
    await cb.answer()

@router.callback_query(F.data.startswith("ccs_staff_next:"))
async def ccs_staff_next(cb: CallbackQuery):
    cur = int(cb.data.split(":")[1])
    await _show_staff_item(cb, idx=cur + 1, user_id=cb.from_user.id)
    await cb.answer()

@router.callback_query(F.data.startswith("ccs_staff_send_operator:"))
async def ccs_staff_send_operator(cb: CallbackQuery):
    """Staff arizani operator'ga yuborish - operator tanlash"""
    _, order_id, cur = cb.data.split(":")
    order_id = int(order_id)
    cur = int(cur)
    
    lang = await get_user_language(cb.from_user.id) or "uz"
    
    # Operatorlarni olish
    import asyncpg
    from config import settings
    
    conn = await asyncpg.connect(settings.DB_URL)
    try:
        operators = await conn.fetch("SELECT id, full_name, telegram_id FROM users WHERE role = 'callcenter_operator'")
        
        if not operators:
            await cb.answer(
                ("❌ Operatorlar mavjud emas!" if lang == "uz" else "❌ Операторы не найдены!"), 
                show_alert=True
            )
            return
        
        # Operatorlarni inline keyboard qilish
        keyboard = []
        for operator in operators:
            full_name = (operator.get('full_name') or '').strip() or f"ID: {operator['id']}"
            keyboard.append([
                InlineKeyboardButton(
                    text=f"👨‍💼 {full_name}",
                    callback_data=f"ccs_staff_select_operator:{order_id}:{cur}:{operator['id']}"
                )
            ])
        
        keyboard.append([
            InlineKeyboardButton(
                text=("◀️ Orqaga" if lang == "uz" else "◀️ Назад"),
                callback_data=f"ccs_staff_back_to_item:{order_id}:{cur}"
            )
        ])
        
        reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
        
        texts = {
            "uz": {
                "title": "👨‍💼 <b>Operatorni tanlang</b>",
                "subtitle": "Staff arizani qaysi operatorga yubormoqchisiz?"
            },
            "ru": {
                "title": "👨‍💼 <b>Выберите оператора</b>",
                "subtitle": "Какому оператору отправить заявку оператора?"
            }
        }
        t = texts[lang]
        
        text = f"{t['title']}\n\n{t['subtitle']}\n\n🆔 <b>Ariza ID:</b> #{order_id}"
        
        await cb.message.edit_text(text, reply_markup=reply_markup, parse_mode="HTML")
        
    except Exception as e:
        logger.error(f"Failed to get operators: {e}")
        await cb.answer(
            ("❌ Operatorlarni olishda xatolik!" if lang == "uz" else "❌ Ошибка получения операторов!"), 
            show_alert=True
        )
    finally:
        await conn.close()

@router.callback_query(F.data.startswith("ccs_staff_select_operator:"))
async def ccs_staff_select_operator(cb: CallbackQuery):
    """Tanlangan operatorga staff arizani yuborish"""
    _, order_id, cur, operator_id = cb.data.split(":")
    order_id = int(order_id)
    cur = int(cur)
    operator_id = int(operator_id)
    
    lang = await get_user_language(cb.from_user.id) or "uz"
    
    try:
        # Ariza ma'lumotlarini olish
        row = await ccs_fetch_staff_orders(offset=cur, limit=1)
        if not row:
            await cb.answer(
                ("❌ Ariza topilmadi!" if lang == "uz" else "❌ Заявка не найдена!"), 
                show_alert=True
            )
            return
        
        # Operator ma'lumotlarini olish
        import asyncpg
        from config import settings
        
        conn = await asyncpg.connect(settings.DB_URL)
        try:
            operator = await conn.fetchrow("SELECT id, full_name, telegram_id, language FROM users WHERE id = $1", operator_id)
            if not operator:
                await cb.answer(
                    ("❌ Operator topilmadi!" if lang == "uz" else "❌ Оператор не найден!"), 
                    show_alert=True
                )
                return
            
            # Ariza holatini yangilash
            result = await conn.execute("""
                UPDATE staff_orders
                SET status = 'in_call_center_operator',
                    updated_at = NOW()
                WHERE id = $1 AND status = 'in_call_center_supervisor'
            """, order_id)
            
            if result == "UPDATE 0":
                await cb.answer(
                    ("❌ Ariza holati yangilanmadi!" if lang == "uz" else "❌ Статус заявки не обновлен!"), 
                    show_alert=True
                )
                return
            
            # Sender ID ni telegram_id dan internal user ID ga o'tkazish
            sender_user = await conn.fetchrow("SELECT id FROM users WHERE telegram_id = $1", cb.from_user.id)
            if not sender_user:
                await cb.answer(
                    ("❌ Foydalanuvchi topilmadi!" if lang == "uz" else "❌ Пользователь не найден!"), 
                    show_alert=True
                )
                return
            
            sender_id = sender_user['id']
            
            # Get application_number
            app_info = await conn.fetchrow("SELECT application_number FROM staff_orders WHERE id = $1", order_id)
            
            # Connection yaratish
            await conn.execute("""
                INSERT INTO connections(
                    application_number, sender_id, recipient_id,
                    sender_status, recipient_status,
                    created_at, updated_at
                )
                VALUES ($1, $2, $3, 'in_call_center_supervisor', 'in_call_center_operator', NOW(), NOW())
            """, app_info['application_number'], sender_id, operator_id)
            
            # Operator'ga notification yuborish
            if operator['telegram_id']:
                from loader import bot
                from utils.notification_service import send_role_notification
                
                await send_role_notification(
                    bot=bot,
                    recipient_telegram_id=operator['telegram_id'],
                    order_id=f"#{order_id}",
                    order_type="staff",
                    current_load=1,
                    lang=operator.get('language', 'uz')
                )
                logger.info(f"Notification sent to operator {operator_id} for staff order {order_id}")
            
        finally:
            await conn.close()
        
        # Tasdiqlash xabari
        operator_name = (operator.get('full_name') or '').strip() or f"ID: {operator_id}"
        
        texts = {
            "uz": {
                "success": "✅ <b>Muvaffaqiyatli yuborildi!</b>",
                "operator": "👨‍💼 <b>Operator:</b>",
                "order": "🆔 <b>Ariza ID:</b>",
                "message": "Staff ariza operatorga muvaffaqiyatli yuborildi!"
            },
            "ru": {
                "success": "✅ <b>Успешно отправлено!</b>",
                "operator": "👨‍💼 <b>Оператор:</b>",
                "order": "🆔 <b>ID заявки:</b>",
                "message": "Заявка оператора успешно отправлена оператору!"
            }
        }
        t = texts[lang]
        
        success_text = (
            f"{t['success']}\n\n"
            f"{t['operator']} {operator_name}\n"
            f"{t['order']} #{order_id}\n\n"
            f"{t['message']}"
        )
        
        # Xabarni o'chirib, yangi xabarni yuborish
        await cb.message.delete()
        await cb.message.answer(success_text, parse_mode="HTML")
        
        # Asosiy menyuga qaytish
        await cb.message.answer(
            ("🏠 Asosiy menyu:" if lang == "uz" else "🏠 Главное меню:"),
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(
                    text=("📥 Inbox" if lang == "uz" else "📥 Входящие"),
                    callback_data="ccs_back_to_categories"
                )]
            ])
        )
        
    except Exception as e:
        logger.error(f"Failed to send staff order to operator: {e}")
        await cb.answer(
            (f"❌ Xatolik: {str(e)}" if lang == "uz" else f"❌ Ошибка: {str(e)}"), 
            show_alert=True
        )

@router.callback_query(F.data.startswith("ccs_staff_back_to_item:"))
async def ccs_staff_back_to_item(cb: CallbackQuery):
    """Operator tanlashdan staff ariza ko'rinishiga qaytish"""
    _, order_id, cur = cb.data.split(":")
    order_id = int(order_id)
    cur = int(cur)
    
    await _show_staff_item(cb, idx=cur, user_id=cb.from_user.id)
    await cb.answer()



# =========================================================
# Operator Orders Handlers
# =========================================================

@router.callback_query(F.data == "ccs_operator_orders")
async def show_operator_orders(callback: CallbackQuery):
    """Call Center operator arizalarini ko'rsatish"""
    await _show_operator_item(callback, idx=0, user_id=callback.from_user.id)

async def _show_operator_item(target, idx: int, user_id: int):
    """Operator arizalarini ko'rsatish"""
    lang = await get_user_language(user_id) or "uz"
    
    try:
        row = await ccs_fetch_operator_orders(offset=idx, limit=1)
        if not row:
            text = (
                "📞 <b>Call Center operator arizalari</b>\n\n"
                "❌ Arizalar yo'q"
                if lang == "uz" else
                "📞 <b>Заявки операторов Call Center</b>\n\n"
                "❌ Нет заявок"
            )
            await target.message.edit_text(text, parse_mode="HTML")
            return
        
        # Ariza ma'lumotlarini formatlash
        order_type = row.get('type_of_zayavka', 'unknown')
        business_type = row.get('business_type', 'B2C')
        
        order_type_text = {
            "uz": {
                "connection": "🔌 Ulanish arizasi",
                "technician": "🔧 Texnik xizmat arizasi"
            },
            "ru": {
                "connection": "🔌 Заявка на подключение", 
                "technician": "🔧 Заявка на техническое обслуживание"
            }
        }
        
        type_text = order_type_text[lang].get(order_type, order_type)
        no_value_uz = 'Yo\'q'
        
        text = (
            f"📞 <b>Call Center operator arizasi</b>\n\n"
            f"🆔 <b>Ariza:</b> {row.get('application_number', 'N/A')}\n"
            f"📋 <b>Tur:</b> {type_text}\n"
            f"🏢 <b>Biznes:</b> {business_type}\n"
            f"👤 <b>Mijoz:</b> {row.get('client_name', 'N/A')}\n"
            f"📞 <b>Tel:</b> {row.get('client_phone', 'N/A')}\n"
            f"📍 <b>Region:</b> {row.get('region', 'N/A')}\n"
            f"🏠 <b>Manzil:</b> {row.get('address', 'N/A')}\n"
            f"👨‍💼 <b>Operator:</b> {row.get('operator_name', 'N/A')}\n"
            f"🕐 <b>Yaratilgan:</b> {fmt_dt(row.get('created_at'))}\n\n"
            f"📝 <b>Tavsif:</b> {row.get('description', no_value_uz) if order_type == 'technician' else row.get('tariff_or_problem', no_value_uz)}"
            if lang == "uz" else
            f"📞 <b>Заявка оператора Call Center</b>\n\n"
            f"🆔 <b>Заявка:</b> {row.get('application_number', 'N/A')}\n"
            f"📋 <b>Тип:</b> {type_text}\n"
            f"🏢 <b>Бизнес:</b> {business_type}\n"
            f"👤 <b>Клиент:</b> {row.get('client_name', 'N/A')}\n"
            f"📞 <b>Тел:</b> {row.get('client_phone', 'N/A')}\n"
            f"📍 <b>Регион:</b> {row.get('region', 'N/A')}\n"
            f"🏠 <b>Адрес:</b> {row.get('address', 'N/A')}\n"
            f"👨‍💼 <b>Оператор:</b> {row.get('operator_name', 'N/A')}\n"
            f"🕐 <b>Создано:</b> {fmt_dt(row.get('created_at'))}\n\n"
            f"📝 <b>Описание:</b> {row.get('description', 'Нет') if order_type == 'technician' else row.get('tariff_or_problem', 'Нет')}"
        )
        
        # Navigation keyboard
        total_count = await ccs_count_operator_orders()
        
        # Paginatsiya tugmalari mantiqiy tarzda ko'rinadi
        keyboard_rows = []
        
        if total_count > 1:
            pagination_row = []
            
            # Orqaga tugmasi - faqat boshida bo'lmasa
            if idx > 0:
                pagination_row.append(InlineKeyboardButton(text="⬅️", callback_data=f"ccs_operator_prev:{idx}"))
            
            # O'rta qismda raqam ko'rsatish
            pagination_row.append(InlineKeyboardButton(text=f"{idx + 1}/{total_count}", callback_data="noop"))
            
            # Oldinga tugmasi - faqat oxirida bo'lmasa
            if idx < total_count - 1:
                pagination_row.append(InlineKeyboardButton(text="➡️", callback_data=f"ccs_operator_next:{idx}"))
            
            if pagination_row:  # Agar kamida bitta tugma bo'lsa
                keyboard_rows.append(pagination_row)
        
        keyboard_rows.append([
            InlineKeyboardButton(
                text="📤 Controllerga yuborish" if lang == "uz" else "📤 Отправить контроллеру",
                callback_data=f"ccs_operator_send_controller:{row['id']}:{idx}"
            )
        ])
        keyboard_rows.append([
            InlineKeyboardButton(
                text="🔙 Orqaga" if lang == "uz" else "🔙 Назад",
                callback_data="ccs_back_to_categories"
            )
        ])
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_rows)
        
        await target.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
        
    except Exception as e:
        logger.error(f"Error showing operator order: {e}")
        await target.answer(
            ("❌ Xatolik yuz berdi!" if lang == "uz" else "❌ Произошла ошибка!"),
            show_alert=True
        )

@router.callback_query(F.data.startswith("ccs_operator_prev:"))
async def ccs_operator_prev(cb: CallbackQuery):
    """Operator arizalarida oldingi"""
    _, idx = cb.data.split(":")
    idx = max(0, int(idx) - 1)
    await _show_operator_item(cb, idx, cb.from_user.id)
    await cb.answer()

@router.callback_query(F.data.startswith("ccs_operator_next:"))
async def ccs_operator_next(cb: CallbackQuery):
    """Operator arizalarida keyingi"""
    _, idx = cb.data.split(":")
    idx = int(idx) + 1
    await _show_operator_item(cb, idx, cb.from_user.id)
    await cb.answer()

@router.callback_query(F.data.startswith("ccs_operator_send_controller:"))
async def ccs_operator_send_controller(cb: CallbackQuery):
    """Operator arizasini controllerga yuborish"""
    _, order_id, idx = cb.data.split(":")
    order_id = int(order_id)
    idx = int(idx)
    
    lang = await get_user_language(cb.from_user.id) or "uz"
    
    try:
        import asyncpg
        from config import settings
        
        conn = await asyncpg.connect(settings.DB_URL)
        try:
            # Ariza holatini yangilash
            result = await conn.execute("""
                UPDATE staff_orders
                SET status = 'in_controller',
                    updated_at = NOW()
                WHERE id = $1 AND status = 'in_call_center_supervisor'
            """, order_id)
            
            if result == "UPDATE 0":
                await cb.answer(
                    ("❌ Ariza topilmadi yoki allaqachon yuborilgan!" if lang == "uz" else "❌ Заявка не найдена или уже отправлена!"),
                    show_alert=True
                )
                return
            
            # Guruhga xabar yuborish
            try:
                from loader import bot
                from utils.notification_service import send_group_notification_for_staff_order
                
                row = await ccs_fetch_operator_orders(offset=idx, limit=1)
                if row:
                    await send_group_notification_for_staff_order(
                        bot=bot,
                        order_id=order_id,
                        order_type=row.get('type_of_zayavka', 'connection'),
                        client_name=row.get('client_name', 'N/A'),
                        client_phone=row.get('client_phone', 'N/A'),
                        creator_name=cb.from_user.full_name,
                        creator_role='call_center_supervisor',
                        region=row.get('region', 'N/A'),
                        address=row.get('address', 'N/A'),
                        tariff_name=row.get('tariff_or_problem', 'N/A'),
                        business_type=row.get('business_type', 'B2C')
                    )
            except Exception as group_error:
                logger.error(f"Failed to send group notification: {group_error}")
            
            await cb.answer(
                ("✅ Controllerga yuborildi!" if lang == "uz" else "✅ Отправлено контроллеру!"),
                show_alert=True
            )
            
            # Keyingi arizaga o'tish
            await _show_operator_item(cb, idx, cb.from_user.id)
            
        finally:
            await conn.close()
            
    except Exception as e:
        logger.error(f"Error sending operator order to controller: {e}")
        await cb.answer(
            ("❌ Xatolik yuz berdi!" if lang == "uz" else "❌ Произошла ошибка!"),
            show_alert=True
        )

# =========================================================
# Complete Handlers
# =========================================================
# =========================================================
# Back to Categories
# =========================================================
@router.callback_query(F.data == "ccs_back_to_categories")
async def ccs_back_to_categories(cb: CallbackQuery):
    """Back to main categories"""
    await _ccs_inbox_content(cb, cb.from_user.id)
    await cb.answer()
