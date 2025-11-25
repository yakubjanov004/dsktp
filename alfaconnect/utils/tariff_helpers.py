from __future__ import annotations

from typing import Optional

from keyboards.client_buttons import (
    B2C_PLANS,
    BIZNET_PRO_PLANS,
    TIJORAT_PLANS,
)


def resolve_tariff_code_from_callback(callback_data: Optional[str]) -> Optional[str]:
    """Convert operator callback data into canonical tariff code."""

    if not callback_data:
        return None

    if callback_data.startswith("op_tariff_b2c_plan_"):
        suffix = callback_data.rsplit("_", 1)[-1]
        if suffix.isdigit():
            return f"tariff_b2c_plan_{suffix}"

    if callback_data.startswith("op_tariff_biznet_plan_"):
        suffix = callback_data.rsplit("_", 1)[-1]
        if suffix.isdigit():
            return f"tariff_biznet_plan_{suffix}"

    if callback_data.startswith("op_tariff_tijorat_plan_"):
        suffix = callback_data.rsplit("_", 1)[-1]
        if suffix.isdigit():
            return f"tariff_tijorat_plan_{suffix}"

    return None


def get_tariff_display_label(tariff_code: Optional[str], lang: str = "uz") -> Optional[str]:
    """Return human-friendly tariff label for summaries and confirmations."""

    if not tariff_code:
        return None

    prefix_map = {
        "tariff_b2c_plan_": B2C_PLANS,
        "tariff_biznet_plan_": BIZNET_PRO_PLANS,
        "tariff_tijorat_plan_": TIJORAT_PLANS,
    }

    for prefix, plans in prefix_map.items():
        if tariff_code.startswith(prefix):
            suffix = tariff_code[len(prefix):]
            if not suffix.isdigit():
                break
            idx = int(suffix)
            if 0 <= idx < len(plans):
                plan = plans[idx]
                price_suffix = "so'm" if lang == "uz" else "сум"
                price = plan.get("price")
                price_text = f"{price} {price_suffix}" if price else ""
                if price_text:
                    return f"{plan['name']} • {price_text}"
                return plan["name"]
            break

    return tariff_code

