# handlers/controller/realtime_monitoring.py
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
import logging

from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
import json

from filters.role_filter import RoleFilter
from database.controller.monitoring import (
    get_realtime_counts,
    list_active_orders_detailed,
    get_controller_workflow_history,
)

router = Router()
logger = logging.getLogger(__name__)
router.message.filter(RoleFilter("controller"))
router.callback_query.filter(RoleFilter("controller"))

# ---- Labels ----
LBL_TITLE = "🕐 Real vaqtda kuzatish"
LBL_ALL = "📘 Barcha zayavkalar"
LBL_URGENT = "🚨 Shoshilinch"
LBL_BACK = "🔙 Orqaga"
LBL_PREV = "⬅️ Oldingi"
LBL_NEXT = "➡️ Keyingi"
LBL_HISTORY = "🧾 Tarix"

UZ_ENTRY_TEXT = LBL_TITLE
RU_ENTRY_TEXT = "🕒 Реальное время"

# ---- TZ helpers ----
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

def _human_duration(delta: timedelta) -> str:
    secs = int(max(delta.total_seconds(), 0))
    d, r = divmod(secs, 86400)
    h, r = divmod(r, 3600)
    m, s = divmod(r, 60)
    parts = []
    if d: parts.append(f"{d}d")
    if h: parts.append(f"{h}h")
    if m: parts.append(f"{m}m")
    if not parts: parts.append(f"{s}s")
    return " ".join(parts)

def _kb_overview() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text=LBL_ALL, callback_data="rtm_all")
    kb.button(text=LBL_URGENT, callback_data="rtm_urgent")
    kb.adjust(2)
    return kb.as_markup()

def _kb_card(idx: int, total: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text=LBL_HISTORY, callback_data="rtm_show_history")
    kb.row()
    kb.button(text=LBL_PREV, callback_data="rtm_prev")
    kb.button(text=f"{idx+1}/{total}", callback_data="noop")
    kb.button(text=LBL_NEXT, callback_data="rtm_next")
    kb.row()
    kb.button(text=LBL_BACK, callback_data="rtm_back_overview")
    return kb.as_markup()

def _kb_history(idx: int, total: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text=LBL_PREV, callback_data="rtm_prev_hist")
    kb.button(text=f"{idx+1}/{total}", callback_data="noop")
    kb.button(text=LBL_NEXT, callback_data="rtm_next_hist")
    kb.row()
    kb.button(text=LBL_BACK, callback_data="rtm_back_card")
    return kb.as_markup()

def _fmt_overview(counts: dict) -> str:
    now_local = datetime.now(TZ).strftime("%d.%m.%Y %H:%M")
    return (
        f"<b>{LBL_TITLE}</b>\n\n"
        f"📊 <b>Joriy holat:</b>\n"
        f"• Faol zayavkalar: <b>{counts['active_total']}</b>\n"
        f"• Shoshilinch: <b>{counts['urgent_total']}</b>\n\n"
        f"🕓 <b>Yangilangan:</b> {now_local}"
    )

def _fmt_card(rec: dict) -> str:
    created_local = _to_tz(rec.get("created_at"))
    created_str = created_local.strftime("%Y-%m-%d %H:%M") if created_local else "—"
    now_local = datetime.now(TZ)
    total_dur = _human_duration(now_local - created_local) if created_local else "—"

    status = rec.get("status_text") or "—"
    addr = rec.get("address") or "—"
    creator = rec.get("creator_name") or "—"

    return (
        f"🗂 <b>Zayavka #{rec.get('id','—')}</b>\n"
        f"🪪 <b>ID:</b> <code>{rec.get('id','—')}</code>\n"
        f"📁 <b>Turi:</b> technician\n"
        f"📊 <b>Status:</b> <code>{status}</code>\n"
        f"👤 <b>Yaratgan:</b> {creator}\n"
        f"🕘 <b>Yaratilgan:</b> {created_str}\n"
        f"📍 <b>Manzil:</b> {addr}\n"
        f"\n"
        f"📈 <b>Umumiy:</b>\n"
        f"• <b>Umumiy vaqt:</b> {total_dur}\n"
    )

def _fmt_history(title_name: str, order_id: int, steps: list, created_at) -> str:
    header = f"📊 <b>Workflow tarix</b> #{order_id}\n\n" \
             f"👤 <b>Mijoz:</b> {title_name}\n"
    lines = [header, "📋 <b>Qadamlar:</b>"]
    if not steps:
        lines.append("\nHech qanday harakat topilmadi.")
    else:
        for i, st in enumerate(steps, 1):
            start_s = _to_tz(st['start_at']).strftime("%H:%M") if st['start_at'] else "—"
            end_s = (_to_tz(st['end_at']).strftime("%H:%M") if st['end_at'] else "hali tugamagan")
            lines.append(
                f"\n<b>{i}.</b> {st['from_name']} → {st['to_name']}\n"
                f"   🗓 {start_s} → {end_s}\n"
                f"   ⏱ {st['duration_str']}"
            )
    now_local = datetime.now(TZ)
    total_dur = _human_duration(now_local - _to_tz(created_at)) if created_at else "—"
    lines.append(f"\n📈 <b>Umumiy vaqt:</b> {total_dur}")
    return "\n".join(lines)

# ---- Safe edit helper ----
def _kb_fingerprint(kb) -> str:
    if kb is None:
        return "NONE"
    try:
        data = kb.model_dump(by_alias=True, exclude_none=True)
        return json.dumps(data, sort_keys=True, ensure_ascii=False)
    except Exception:
        return str(kb)

async def _safe_edit(cb: CallbackQuery, new_text: str, new_kb: InlineKeyboardMarkup | None):
    msg = cb.message
    cur_text = msg.html_text or msg.text or ""
    cur_fp = _kb_fingerprint(msg.reply_markup)
    new_fp = _kb_fingerprint(new_kb)
    if cur_text == new_text and cur_fp == new_fp:
        await cb.answer("Yangilanish yo‘q ✅", show_alert=False)
        return
    try:
        await msg.edit_text(new_text, reply_markup=new_kb)
    except TelegramBadRequest as e:
        if "message is not modified" in str(e):
            await cb.answer("Yangilanish yo‘q ✅", show_alert=False)
        else:
            raise

# ---- Entry points (E’TIBOR: controller!) ----
@router.message(RoleFilter("controller"), F.text.in_([UZ_ENTRY_TEXT, RU_ENTRY_TEXT]))
async def rtm_entry_button(msg: Message):
    counts = await get_realtime_counts()
    await msg.answer(_fmt_overview(counts), reply_markup=_kb_overview())

@router.message(RoleFilter("controller"), F.text == "/rtm")
async def rtm_cmd(message: Message):
    counts = await get_realtime_counts()
    await message.answer(_fmt_overview(counts), reply_markup=_kb_overview())

# ---- Overview → ALL/URGENT ----
@router.callback_query(RoleFilter("controller"), F.data == "rtm_all")
async def rtm_all(cb: CallbackQuery, state: FSMContext):
    items = await list_active_detailed(limit=200)
    if not items:
        await _safe_edit(cb, "📘 <b>Barcha faol zayavkalar</b>\n\nHech narsa topilmadi.", _kb_overview())
        return
    await state.update_data(view="card", items=items, idx=0)
    await _safe_edit(cb, _fmt_card(items[0]), _kb_card(0, len(items)))

@router.callback_query(RoleFilter("controller"), F.data == "rtm_urgent")
async def rtm_urgent(cb: CallbackQuery, state: FSMContext):
    items = await list_urgent_detailed(limit=200)
    if not items:
        await _safe_edit(cb, "🚨 <b>Shoshilinch</b>\n\nHech narsa topilmadi.", _kb_overview())
        return
    await state.update_data(view="card", items=items, idx=0)
    await _safe_edit(cb, _fmt_card(items[0]), _kb_card(0, len(items)))

@router.callback_query(RoleFilter("controller"), F.data == "rtm_prev")
async def rtm_prev(cb: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    items = data.get("items") or []
    if not items:
        await cb.answer("Ma’lumot topilmadi", show_alert=False); return
    idx = (int(data.get("idx", 0)) - 1) % len(items)
    await state.update_data(idx=idx, view="card")
    await _safe_edit(cb, _fmt_card(items[idx]), _kb_card(idx, len(items)))

@router.callback_query(RoleFilter("controller"), F.data == "rtm_next")
async def rtm_next(cb: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    items = data.get("items") or []
    if not items:
        await cb.answer("Ma’lumot topilmadi", show_alert=False); return
    idx = (int(data.get("idx", 0)) + 1) % len(items)
    await state.update_data(idx=idx, view="card")
    await _safe_edit(cb, _fmt_card(items[idx]), _kb_card(idx, len(items)))

@router.callback_query(RoleFilter("controller"), F.data == "rtm_back_overview")
async def rtm_back_overview(cb: CallbackQuery, state: FSMContext):
    counts = await get_realtime_counts()
    await state.clear()
    await _safe_edit(cb, _fmt_overview(counts), _kb_overview())

# ---- History ----
@router.callback_query(RoleFilter("controller"), F.data == "rtm_show_history")
async def rtm_show_history(cb: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    items = data.get("items") or []
    idx = int(data.get("idx", 0))
    if not items:
        await cb.answer("Ma’lumot topilmadi", show_alert=False); return
    order = items[idx]
    history = await get_workflow_history(order_id=order["id"])
    text = _fmt_history(order.get("creator_name") or "—", order["id"], history["steps"], order.get("created_at"))
    await state.update_data(view="history")
    await _safe_edit(cb, text, _kb_history(idx, len(items)))

@router.callback_query(RoleFilter("controller"), F.data == "rtm_prev_hist")
async def rtm_prev_hist(cb: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    items = data.get("items") or []
    if not items:
        await cb.answer("Ma’lumot topilmadi", show_alert=False); return
    idx = (int(data.get("idx", 0)) - 1) % len(items)
    await state.update_data(idx=idx, view="history")
    order = items[idx]
    history = await get_workflow_history(order_id=order["id"])
    text = _fmt_history(order.get("creator_name") or "—", order["id"], history["steps"], order.get("created_at"))
    await _safe_edit(cb, text, _kb_history(idx, len(items)))

@router.callback_query(RoleFilter("controller"), F.data == "rtm_next_hist")
async def rtm_next_hist(cb: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    items = data.get("items") or []
    if not items:
        await cb.answer("Ma’lumot topilmadi", show_alert=False); return
    idx = (int(data.get("idx", 0)) + 1) % len(items)
    await state.update_data(idx=idx, view="history")
    order = items[idx]
    history = await get_workflow_history(order_id=order["id"])
    text = _fmt_history(order.get("creator_name") or "—", order["id"], history["steps"], order.get("created_at"))
    await _safe_edit(cb, text, _kb_history(idx, len(items)))

@router.callback_query(RoleFilter("controller"), F.data == "rtm_back_card")
async def rtm_back_card(cb: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    items = data.get("items") or []
    idx = int(data.get("idx", 0))
    if not items:
        await _safe_edit(cb, "Xatolik: ro‘yxat bo‘sh.", _kb_overview()); return
    await state.update_data(view="card")
    await _safe_edit(cb, _fmt_card(items[idx]), _kb_card(idx, len(items)))

@router.callback_query(RoleFilter("controller"), F.data == "noop")
async def noop(cb: CallbackQuery):
    await cb.answer()
