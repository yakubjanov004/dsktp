# database/basic/region.py
# Region helpers for normalizing codes and titles

from __future__ import annotations

from typing import Optional, Union

REGION_ID_TO_CODE = {
    1: "toshkent_city",
    2: "toshkent_region",
    3: "andijon",
    4: "fergana",
    5: "namangan",
    6: "sirdaryo",
    7: "jizzax",
    8: "samarkand",
    9: "bukhara",
    10: "navoi",
    11: "kashkadarya",
    12: "surkhandarya",
    13: "khorezm",
    14: "karakalpakstan",
}

REGION_CODE_TO_ID = {code: region_id for region_id, code in REGION_ID_TO_CODE.items()}


def normalize_region_code(region: Optional[Union[int, str]]) -> Optional[str]:
    """Convert various region representations to canonical code form."""

    if region is None:
        return None

    if isinstance(region, int):
        return REGION_ID_TO_CODE.get(region, str(region))

    region_str = str(region).strip()
    if not region_str:
        return None

    lower = region_str.lower()

    if lower in REGION_CODE_TO_ID:
        return lower

    digits: Optional[int] = None
    if lower.isdigit():
        digits = int(lower)
    else:
        cleaned = lower.replace("-", "_").replace(" ", "_")
        if cleaned in REGION_CODE_TO_ID:
            return cleaned
        if cleaned.startswith("region"):
            suffix = cleaned.replace("region", "", 1).lstrip("_ ")
            if suffix.isdigit():
                digits = int(suffix)

    if digits is not None:
        return REGION_ID_TO_CODE.get(digits, str(digits))

    return lower.replace(" ", "_")


def region_display_name(region_code: Optional[str], lang: str = "uz") -> Optional[str]:
    """Return localized display name for a region code."""

    if not region_code:
        return None

    mapping = {
        "toshkent_city": {"uz": "Toshkent shahri", "ru": "г. Ташкент"},
        "toshkent_region": {"uz": "Toshkent viloyati", "ru": "Ташкентская область"},
        "andijon": {"uz": "Andijon", "ru": "Андижан"},
        "fergana": {"uz": "Farg'ona", "ru": "Фергана"},
        "namangan": {"uz": "Namangan", "ru": "Наманган"},
        "sirdaryo": {"uz": "Sirdaryo", "ru": "Сырдарья"},
        "jizzax": {"uz": "Jizzax", "ru": "Джизак"},
        "samarkand": {"uz": "Samarqand", "ru": "Самарканд"},
        "bukhara": {"uz": "Buxoro", "ru": "Бухара"},
        "navoi": {"uz": "Navoiy", "ru": "Навои"},
        "kashkadarya": {"uz": "Qashqadaryo", "ru": "Кашкадарья"},
        "surkhandarya": {"uz": "Surxondaryo", "ru": "Сурхандарья"},
        "khorezm": {"uz": "Xorazm", "ru": "Хорезм"},
        "karakalpakstan": {"uz": "Qoraqalpog'iston", "ru": "Каракалпакстан"},
    }

    code = normalize_region_code(region_code)
    if not code:
        return None

    names = mapping.get(code)
    if not names:
        return code.replace("_", " ").title()

    return names.get(lang) or names.get("uz")


__all__ = [
    "REGION_ID_TO_CODE",
    "REGION_CODE_TO_ID",
    "normalize_region_code",
    "region_display_name",
]

