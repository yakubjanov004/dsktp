from __future__ import annotations

from typing import List

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from keyboards.client_buttons import (
    B2C_PLANS,
    BIZNET_PRO_PLANS,
    TIJORAT_PLANS,
)


def _format_price(price: str, lang: str) -> str:
    suffix = "so'm" if lang == "uz" else "сум"
    return f"{price} {suffix}"


def get_staff_tariff_category_keyboard(*, prefix: str = "op_tariff", lang: str = "uz") -> InlineKeyboardMarkup:
    """Inline keyboard to pick a B2B tariff category (BizNET vs Tijorat)."""

    back_text = "◀️ Orqaga" if lang == "uz" else "◀️ Назад"

    keyboard = [
        [InlineKeyboardButton(text="BizNET-Pro", callback_data=f"{prefix}_category_biznet")],
        [InlineKeyboardButton(text="Tijorat", callback_data=f"{prefix}_category_tijorat")],
        [InlineKeyboardButton(text=back_text, callback_data=f"{prefix}_back_to_type")],
    ]

    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_staff_b2c_tariff_keyboard(*, prefix: str = "op_tariff", lang: str = "uz") -> InlineKeyboardMarkup:
    """Inline keyboard for B2C tariffs with price information."""

    rows: List[List[InlineKeyboardButton]] = []

    for i in range(0, len(B2C_PLANS), 2):
        row: List[InlineKeyboardButton] = []
        for j in range(2):
            idx = i + j
            if idx >= len(B2C_PLANS):
                continue
            plan = B2C_PLANS[idx]
            text = f"{plan['name']} • {_format_price(plan['price'], lang)}"
            row.append(
                InlineKeyboardButton(
                    text=text,
                    callback_data=f"{prefix}_b2c_plan_{idx}",
                )
            )
        if row:
            rows.append(row)

    back_text = "◀️ Orqaga" if lang == "uz" else "◀️ Назад"
    rows.append([InlineKeyboardButton(text=back_text, callback_data=f"{prefix}_back_to_type")])

    return InlineKeyboardMarkup(inline_keyboard=rows)


def get_staff_biznet_tariff_keyboard(*, prefix: str = "op_tariff", lang: str = "uz") -> InlineKeyboardMarkup:
    rows: List[List[InlineKeyboardButton]] = []

    for idx, plan in enumerate(BIZNET_PRO_PLANS):
        text = f"{plan['name']} • {_format_price(plan['price'], lang)}"
        rows.append([
            InlineKeyboardButton(
                text=text,
                callback_data=f"{prefix}_biznet_plan_{idx}",
            )
        ])

    back_text = "◀️ Orqaga" if lang == "uz" else "◀️ Назад"
    rows.append([InlineKeyboardButton(text=back_text, callback_data=f"{prefix}_back_to_categories")])

    return InlineKeyboardMarkup(inline_keyboard=rows)


def get_staff_tijorat_tariff_keyboard(*, prefix: str = "op_tariff", lang: str = "uz") -> InlineKeyboardMarkup:
    rows: List[List[InlineKeyboardButton]] = []

    for idx, plan in enumerate(TIJORAT_PLANS):
        text = f"{plan['name']} • {_format_price(plan['price'], lang)}"
        rows.append([
            InlineKeyboardButton(
                text=text,
                callback_data=f"{prefix}_tijorat_plan_{idx}",
            )
        ])

    back_text = "◀️ Orqaga" if lang == "uz" else "◀️ Назад"
    rows.append([InlineKeyboardButton(text=back_text, callback_data=f"{prefix}_back_to_categories")])

    return InlineKeyboardMarkup(inline_keyboard=rows)

