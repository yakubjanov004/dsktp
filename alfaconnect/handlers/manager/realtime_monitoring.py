# handlers/manager/realtime_monitoring.py

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
import logging

from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
import json
import html

from filters.role_filter import RoleFilter
from database.manager.monitoring import (
    get_realtime_counts,
    list_active_detailed,
    list_urgent_detailed,
    get_workflow_history,  # NEW
)
# 🔑 Tilni DB'dan olish uchun:
from database.basic.user import get_user_by_telegram_id

router = Router()
router.message.filter(RoleFilter("manager"))
router.callback_query.filter(RoleFilter("manager"))

# ---------------- I18N (UZ/RU) ----------------
T = {
    "title": {
        "uz": "🕐 Real vaqtda kuzatish",
        "ru": "🕒 Мониторинг в реальном времени",
    },
    "btn_all": {
        "uz": "📘 Barcha zayavkalar",
        "ru": "📘 Все заявки",
    },
    "btn_urgent": {
        "uz": "🚨 Shoshilinch",
        "ru": "🚨 Срочные",
    },
    "btn_back": {"uz": "🔙 Orqaga", "ru": "🔙 Назад"},
    "btn_prev": {"uz": "⬅️ Oldingi", "ru": "⬅️ Назад"},
    "btn_next": {"uz": "➡️ Keyingi", "ru": "➡️ Далее"},
    "btn_history": {"uz": "🧾 Tarix", "ru": "🧾 История"},

    "overview_stats": {"uz": "📊 <b>Joriy holat:</b>", "ru": "📊 <b>Текущая сводка:</b>"},
    "active_total": {"uz": "• Faol zayavkalar:", "ru": "• Активные заявки:"},
    "urgent_total": {"uz": "• Shoshilinch:", "ru": "• Срочные:"},
    "updated_at":   {"uz": "🕓 <b>Yangilangan:</b>", "ru": "🕓 <b>Обновлено:</b>"},

    "no_items_all": {
        "uz": "📘 <b>Barcha faol zayavkalar</b>\n\nHech narsa topilmadi.",
        "ru": "📘 <b>Все активные заявки</b>\n\nНичего не найдено.",
    },
    "no_items_urgent": {
        "uz": "🚨 <b>Shoshilinch</b>\n\nHech narsa topilmadi.",
        "ru": "🚨 <b>Срочные</b>\n\nНичего не найдено.",
    },
    "no_data_toast": {"uz": "Ma’lumot topilmadi", "ru": "Данные не найдены"},
    "no_update_toast": {"uz": "Yangilanish yo‘q ✅", "ru": "Нет изменений ✅"},
    "list_empty_err": {"uz": "Xatolik: ro‘yxat bo‘sh.", "ru": "Ошибка: список пуст."},

    # Karta (order) maydonlari
    "card_title": {"uz": "🗂 <b>Zayavka {id}</b>", "ru": "🗂 <b>Заявка #{id}</b>"},
    "field_id": {"uz": "🪪 <b>ID:</b>", "ru": "🪪 <b>ID:</b>"},
    "field_type": {"uz": "📁 <b>Turi:</b>", "ru": "📁 <b>Тип:</b>"},
    "type_connection": {"uz": "ulanish", "ru": "подключение"},
    "field_status": {"uz": "📊 <b>Status:</b>", "ru": "📊 <b>Статус:</b>"},
    "field_creator": {"uz": "👤 <b>Yaratgan:</b>", "ru": "👤 <b>Создал(а):</b>"},
    "field_created": {"uz": "🕘 <b>Yaratilgan:</b>", "ru": "🕘 <b>Создано:</b>"},
    "field_address": {"uz": "📍 <b>Manzil:</b>", "ru": "📍 <b>Адрес:</b>"},
    "sum_title": {"uz": "📈 <b>Umumiy:</b>", "ru": "📈 <b>Итого:</b>"},
    "sum_total_time": {"uz": "• <b>Umumiy vaqt:</b>", "ru": "• <b>Общее время:</b>"},

    # Tarix (history)
    "hist_title": {"uz": "📊 <b>Workflow tarix</b> {id}", "ru": "📊 <b>История процесса</b> {id}"},
    "hist_client": {"uz": "👤 <b>Mijoz:</b>", "ru": "👤 <b>Клиент:</b>"},
    "hist_steps": {"uz": "📋 <b>Qadamlar:</b>", "ru": "📋 <b>Шаги:</b>"},
    "hist_no_steps": {"uz": "Hech qanday harakat topilmadi.", "ru": "Действия не найдены."},
    "hist_not_finished": {"uz": "hali tugamagan", "ru": "ещё не завершено"},
    "hist_time_spent": {"uz": "⏱️ <b>Vaqt sarf:</b>", "ru": "⏱️ <b>Затрачено времени:</b>"},
    "hist_by_person": {"uz": "👥 <b>Har bir shaxs uchun:</b>", "ru": "👥 <b>По каждому человеку:</b>"},
    "hist_no_user_times": {"uz": "Ma'lumot yo'q", "ru": "Данных нет"},
}

def normalize_lang(v: str | None) -> str:
    if not v:
        return "uz"
    v = v.strip().lower()
    if v in {"ru", "rus", "russian", "ru-ru", "ru_ru"}:
        return "ru"
    if v in {"uz", "uzb", "uzbek", "o'z", "oz", "uz-uz", "uz_uz"}:
        return "uz"
    return "uz"

def t(lang: str, key: str, **fmt) -> str:
    lang = normalize_lang(lang)
    val = T.get(key, {}).get(lang, T.get(key, {}).get("uz", key))
    return val.format(**fmt) if fmt else val

# ---- TZ helpers (Toshkent uchun ishonchli) ----
def _safe_tz(key: str):
    try:
        return ZoneInfo(key)
    except ZoneInfoNotFoundError:
        return timezone(timedelta(hours=5))  # Asia/Tashkent uchun barqaror offset

TZ = _safe_tz("Asia/Tashkent")

def _to_tz(dt):
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(TZ)

def _human_duration(delta: timedelta, lang: str) -> str:
    secs = int(max(delta.total_seconds(), 0))
    d, r = divmod(secs, 86400)
    h, r = divmod(r, 3600)
    m, s = divmod(r, 60)
    # qisqa birliklar: UZ -> k s m; RU -> д ч м
    if normalize_lang(lang) == "ru":
        parts = []
        if d: parts.append(f"{d}д")
        if h: parts.append(f"{h}ч")
        if m: parts.append(f"{m}м")
        if not parts: parts.append(f"{s}с")
        return " ".join(parts)
    else:
        parts = []
        if d: parts.append(f"{d}k")
        if h: parts.append(f"{h}s")
        if m: parts.append(f"{m}m")
        if not parts: parts.append(f"{s}s")
        return " ".join(parts)

# ---- Lang helpers ----
async def _get_lang_from_db(user_tg_id: int) -> str:
    user = await get_user_by_telegram_id(user_tg_id)
    return normalize_lang((user or {}).get("language"))

async def _lang(state: FSMContext, user_tg_id: int) -> str:
    data = await state.get_data()
    lang = data.get("lang")
    if lang:
        return normalize_lang(lang)
    lang = await _get_lang_from_db(user_tg_id)
    await state.update_data(lang=lang)
    return lang

# ---- Keyboards (lang-aware) ----
def _kb_overview(lang: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text=t(lang, "btn_all"), callback_data="rtm_all")
    kb.button(text=t(lang, "btn_urgent"), callback_data="rtm_urgent")
    kb.adjust(2)
    return kb.as_markup()

def _kb_card(lang: str, idx: int, total: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text=t(lang, "btn_history"), callback_data="rtm_show_history")
    kb.row()
    kb.button(text=t(lang, "btn_prev"), callback_data="rtm_prev")
    kb.button(text=f"{idx+1}/{total}", callback_data="noop")
    kb.button(text=t(lang, "btn_next"), callback_data="rtm_next")
    kb.row()
    kb.button(text=t(lang, "btn_back"), callback_data="rtm_back_overview")
    return kb.as_markup()

def _kb_history(lang: str, idx: int, total: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text=t(lang, "btn_prev"), callback_data="rtm_prev_hist")
    kb.button(text=f"{idx+1}/{total}", callback_data="noop")
    kb.button(text=t(lang, "btn_next"), callback_data="rtm_next_hist")
    kb.row()
    kb.button(text=t(lang, "btn_back"), callback_data="rtm_back_card")
    return kb.as_markup()

# ---- Formatters (lang-aware) ----
def _fmt_overview(lang: str, counts: dict) -> str:
    now_local = datetime.now(TZ).strftime("%d.%m.%Y %H:%M")
    return (
        f"<b>{t(lang,'title')}</b>\n\n"
        f"{t(lang,'overview_stats')}\n"
        f"{t(lang,'active_total')} <b>{counts['active_total']}</b>\n"
        f"{t(lang,'urgent_total')} <b>{counts['urgent_total']}</b>\n\n"
        f"{t(lang,'updated_at')} {now_local}"
    )

def _fmt_card(lang: str, rec: dict) -> str:
    created_local = _to_tz(rec.get("created_at"))
    created_str = created_local.strftime("%Y-%m-%d %H:%M") if created_local else "—"
    now_local = datetime.now(TZ)
    total_dur = _human_duration(now_local - created_local, lang) if created_local else "—"

    status  = html.escape(rec.get("status_text") or "—", quote=False)
    addr    = html.escape(rec.get("address") or "—", quote=False)
    creator = html.escape(rec.get("creator_name") or "—", quote=False)
    
    # Use application_number if available, otherwise fall back to id
    app_number = rec.get("application_number", "")
    if app_number and app_number.strip():
        display_id = app_number
    else:
        display_id = rec.get("id", "—")

    return (
        f"{t(lang,'card_title', id=display_id)}\n"
        f"{t(lang,'field_id')} <code>{display_id}</code>\n"
        f"{t(lang,'field_type')} {t(lang,'type_connection')}\n"
        f"{t(lang,'field_status')} <code>{status}</code>\n"
        f"{t(lang,'field_creator')} {creator}\n"
        f"{t(lang,'field_created')} {created_str}\n"
        f"{t(lang,'field_address')} {addr}\n"
        f"\n"
        f"{t(lang,'sum_title')}\n"
        f"{t(lang,'sum_total_time')} {total_dur}\n"
    )

def _fmt_history(lang: str, title_name: str, application_number: str, steps: list, created_at, user_times: list = None) -> str:
    """Format history message - clearer and more readable"""
    header = f"{t(lang,'hist_title', id=application_number)}\n\n" \
             f"{t(lang,'hist_client')} {html.escape(title_name, quote=False)}\n"
    lines = [header]
    
    # Steps section with clearer formatting
    lines.append(f"\n{t(lang, 'hist_steps')}")
    if not steps:
        lines.append(f"{t(lang,'hist_no_steps')}")
    else:
        for i, st in enumerate(steps, 1):
            start_s = _to_tz(st['start_at']).strftime("%H:%M") if st['start_at'] else "—"
            end_s = _to_tz(st['end_at']).strftime("%H:%M") if st['end_at'] else t(lang, "hist_not_finished")
            from_name = html.escape(st['from_name'], quote=False)
            to_name = html.escape(st['to_name'], quote=False)
            duration_str = html.escape(st['duration_str'], quote=False)
            
            # Step description in the current language
            step_desc = st.get('description', {})
            if isinstance(step_desc, dict):
                description = step_desc.get(lang, step_desc.get('uz', ''))
            else:
                description = str(step_desc)
            
            description = html.escape(description, quote=False)
            
            # Clearer formatting - matches the image style better
            lines.append(
                f"\n<b>{from_name} → {to_name}:</b>\n"
                f"   {description}\n"
                f"   {start_s} → {end_s}\n"
                f"   ⏱️ {duration_str}"
            )
    
    # User times section - clearer formatting
    if user_times:
        lines.append(f"\n\n{t(lang,'hist_by_person')}")
        for i, ut in enumerate(user_times[:5], 1):  # Show top 5
            name = html.escape(ut.get('name', '—'), quote=False)
            duration_str = html.escape(ut.get('duration_str', '—'), quote=False)
            lines.append(f"{i}. <b>{name}</b> - {duration_str}")
    
    # Total time - clearer formatting
    now_local = datetime.now(TZ)
    total_dur = _human_duration(now_local - _to_tz(created_at), lang) if created_at else "—"
    lines.append(f"\n• <b>{t(lang,'sum_total_time')}</b> {total_dur}")
    return "\n".join(lines)

# ---- Safe edit helper (lang-aware toast) ----
def _kb_fingerprint(kb) -> str:
    if kb is None:
        return "NONE"
    try:
        data = kb.model_dump(by_alias=True, exclude_none=True)
        return json.dumps(data, sort_keys=True, ensure_ascii=False)
    except Exception:
        return str(kb)

async def _safe_edit(cb: CallbackQuery, lang: str, new_text: str, new_kb: InlineKeyboardMarkup | None):
    msg = cb.message
    cur_text = msg.html_text or msg.text or ""
    cur_fp = _kb_fingerprint(msg.reply_markup)
    new_fp = _kb_fingerprint(new_kb)
    if cur_text == new_text and cur_fp == new_fp:
        await cb.answer(t(lang, "no_update_toast"), show_alert=False)
        return
    try:
        await msg.edit_text(new_text, reply_markup=new_kb, parse_mode="HTML")
    except TelegramBadRequest as e:
        if "not modified" in str(e).lower():
            await cb.answer(t(lang, "no_update_toast"), show_alert=False)
        else:
            raise

# ----- ENTRY TEXTLAR (faqat bitta UZ va bitta RU) -----
UZ_ENTRY_TEXT = "🕐 Real vaqtda kuzatish"
RU_ENTRY_TEXT = "🕐 Мониторинг в реальном времени"

@router.message(RoleFilter("manager"), F.text.in_([UZ_ENTRY_TEXT, RU_ENTRY_TEXT]))
async def rtm_entry_button(msg: Message, state: FSMContext):
    await state.update_data(lang=await _get_lang_from_db(msg.from_user.id))
    lang = await _lang(state, msg.from_user.id)
    counts = await get_realtime_counts()
    await msg.answer(_fmt_overview(lang, counts), reply_markup=_kb_overview(lang))

@router.message(RoleFilter("manager"), F.text == "/rtm")
async def rtm_cmd(message: Message, state: FSMContext):
    await state.update_data(lang=await _get_lang_from_db(message.from_user.id))
    lang = await _lang(state, message.from_user.id)
    counts = await get_realtime_counts()
    await message.answer(_fmt_overview(lang, counts), reply_markup=_kb_overview(lang))

# ---- Overview → ALL/URGENT (paginate one-by-one) ----
@router.callback_query(RoleFilter("manager"), F.data == "rtm_all")
async def rtm_all(cb: CallbackQuery, state: FSMContext):
    lang = await _lang(state, cb.from_user.id)
    items = await list_active_detailed(limit=200)
    if not items:
        await _safe_edit(cb, lang, t(lang, "no_items_all"), _kb_overview(lang))
        return
    await state.update_data(view="card", items=items, idx=0)
    await _safe_edit(cb, lang, _fmt_card(lang, items[0]), _kb_card(lang, 0, len(items)))

@router.callback_query(RoleFilter("manager"), F.data == "rtm_urgent")
async def rtm_urgent(cb: CallbackQuery, state: FSMContext):
    lang = await _lang(state, cb.from_user.id)
    items = await list_urgent_detailed(limit=200)
    if not items:
        await _safe_edit(cb, lang, t(lang, "no_items_urgent"), _kb_overview(lang))
        return
    await state.update_data(view="card", items=items, idx=0)
    await _safe_edit(cb, lang, _fmt_card(lang, items[0]), _kb_card(lang, 0, len(items)))

@router.callback_query(RoleFilter("manager"), F.data == "rtm_prev")
async def rtm_prev(cb: CallbackQuery, state: FSMContext):
    lang = await _lang(state, cb.from_user.id)
    data = await state.get_data()
    items = data.get("items") or []
    if not items:
        await cb.answer(t(lang, "no_data_toast"), show_alert=False); return
    idx = (int(data.get("idx", 0)) - 1) % len(items)
    await state.update_data(idx=idx, view="card")
    await _safe_edit(cb, lang, _fmt_card(lang, items[idx]), _kb_card(lang, idx, len(items)))

@router.callback_query(RoleFilter("manager"), F.data == "rtm_next")
async def rtm_next(cb: CallbackQuery, state: FSMContext):
    lang = await _lang(state, cb.from_user.id)
    data = await state.get_data()
    items = data.get("items") or []
    if not items:
        await cb.answer(t(lang, "no_data_toast"), show_alert=False); return
    idx = (int(data.get("idx", 0)) + 1) % len(items)
    await state.update_data(idx=idx, view="card")
    await _safe_edit(cb, lang, _fmt_card(lang, items[idx]), _kb_card(lang, idx, len(items)))

@router.callback_query(RoleFilter("manager"), F.data == "rtm_back_overview")
async def rtm_back_overview(cb: CallbackQuery, state: FSMContext):
    lang = await _lang(state, cb.from_user.id)
    counts = await get_realtime_counts()
    await state.clear()
    await state.update_data(lang=lang)
    await _safe_edit(cb, lang, _fmt_overview(lang, counts), _kb_overview(lang))

# ---- Show history for current card ----
@router.callback_query(RoleFilter("manager"), F.data == "rtm_show_history")
async def rtm_show_history(cb: CallbackQuery, state: FSMContext):
    lang = await _lang(state, cb.from_user.id)
    data = await state.get_data()
    items = data.get("items") or []
    idx = int(data.get("idx", 0))
    if not items:
        await cb.answer(t(lang, "no_data_toast"), show_alert=False); return
    order = items[idx]
    app_number = order.get("application_number")
    if not app_number:
        await cb.answer(t(lang, "no_data_toast"), show_alert=False); return
    history = await get_workflow_history(application_number=app_number)
    text = _fmt_history(lang, order.get("creator_name") or "—", app_number, history["steps"], order.get("created_at"), history.get("user_times", []))
    await state.update_data(view="history")
    await _safe_edit(cb, lang, text, _kb_history(lang, idx, len(items)))

@router.callback_query(RoleFilter("manager"), F.data == "rtm_prev_hist")
async def rtm_prev_hist(cb: CallbackQuery, state: FSMContext):
    lang = await _lang(state, cb.from_user.id)
    data = await state.get_data()
    items = data.get("items") or []
    if not items:
        await cb.answer(t(lang, "no_data_toast"), show_alert=False); return
    idx = (int(data.get("idx", 0)) - 1) % len(items)
    await state.update_data(idx=idx, view="history")
    order = items[idx]
    app_number = order.get("application_number")
    if not app_number:
        await cb.answer(t(lang, "no_data_toast"), show_alert=False); return
    history = await get_workflow_history(application_number=app_number)
    text = _fmt_history(lang, order.get("creator_name") or "—", app_number, history["steps"], order.get("created_at"), history.get("user_times", []))
    await _safe_edit(cb, lang, text, _kb_history(lang, idx, len(items)))

@router.callback_query(RoleFilter("manager"), F.data == "rtm_next_hist")
async def rtm_next_hist(cb: CallbackQuery, state: FSMContext):
    lang = await _lang(state, cb.from_user.id)
    data = await state.get_data()
    items = data.get("items") or []
    if not items:
        await cb.answer(t(lang, "no_data_toast"), show_alert=False); return
    idx = (int(data.get("idx", 0)) + 1) % len(items)
    await state.update_data(idx=idx, view="history")
    order = items[idx]
    app_number = order.get("application_number")
    if not app_number:
        await cb.answer(t(lang, "no_data_toast"), show_alert=False); return
    history = await get_workflow_history(application_number=app_number)
    text = _fmt_history(lang, order.get("creator_name") or "—", app_number, history["steps"], order.get("created_at"), history.get("user_times", []))
    await _safe_edit(cb, lang, text, _kb_history(lang, idx, len(items)))

@router.callback_query(RoleFilter("manager"), F.data == "rtm_back_card")
async def rtm_back_card(cb: CallbackQuery, state: FSMContext):
    lang = await _lang(state, cb.from_user.id)
    data = await state.get_data()
    items = data.get("items") or []
    idx = int(data.get("idx", 0))
    if not items:
        await _safe_edit(cb, lang, t(lang, "list_empty_err"), _kb_overview(lang)); return
    await state.update_data(view="card")
    await _safe_edit(cb, lang, _fmt_card(lang, items[idx]), _kb_card(lang, idx, len(items)))

@router.callback_query(RoleFilter("manager"), F.data == "noop")
async def noop(cb: CallbackQuery, state: FSMContext):
    lang = await _lang(state, cb.from_user.id)
    await cb.answer(t(lang, "no_update_toast"), show_alert=False)
