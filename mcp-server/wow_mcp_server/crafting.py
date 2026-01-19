from __future__ import annotations

from typing import Any, Awaitable, Callable

from .integrations.tradeskillmaster import iter_crafts as iter_tsm_crafts


GetPrice = Callable[[int], Awaitable[dict[str, Any] | None]]
GetVendorPrice = Callable[[int], float | None]


async def suggest_profitable_crafts(
    crafts_raw: dict[str, Any],
    *,
    have_by_id: dict[int, int],
    get_price: GetPrice,
    get_vendor_price: GetVendorPrice,
    ah_cut_rate: float = 0.05,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """
    Compute profitable craft suggestions from TSM craft data + inventory + price sources.

    Vendor-buyable mats are not treated as limiting (vials, etc.) and use vendor cost when available.
    """
    suggestions: list[dict[str, Any]] = []

    for craft in iter_tsm_crafts(crafts_raw):
        out_price = await get_price(craft.output_item_id)
        if not isinstance(out_price, dict):
            continue
        out_unit = out_price.get("unit_price_copper")
        out_src = out_price.get("source")
        if out_src not in {"auctionator", "tsm"} or not isinstance(out_unit, (int, float)):
            continue

        mats: list[dict[str, Any]] = []
        missing_prices = False
        non_vendor_limits: list[int] = []
        total_cost = 0.0

        for mid, qty in craft.mats.items():
            vendor_unit = get_vendor_price(mid)
            if vendor_unit is not None:
                unit = vendor_unit
                src = "vendor"
            else:
                mp = await get_price(mid)
                if not isinstance(mp, dict):
                    missing_prices = True
                    break
                unit = mp.get("unit_price_copper")
                src = mp.get("source")
                if not isinstance(unit, (int, float)):
                    missing_prices = True
                    break

            have = have_by_id.get(mid, 0)
            is_vendor_buy = src == "vendor"
            if not is_vendor_buy:
                non_vendor_limits.append(have // qty)

            total_cost += float(unit) * qty
            mats.append(
                {
                    "item_id": mid,
                    "quantity_per_craft": qty,
                    "have": have,
                    "unit_price_copper": unit,
                    "price_source": src,
                    "total_cost_copper": float(unit) * qty,
                }
            )

        if missing_prices or not non_vendor_limits:
            continue

        max_crafts = min(non_vendor_limits)
        if max_crafts <= 0:
            continue

        gross_sell = float(out_unit) * craft.num_result
        net_sell = gross_sell * max(0.0, 1.0 - float(ah_cut_rate))
        profit = net_sell - total_cost
        total_profit = profit * max_crafts

        if profit <= 0 or total_profit <= 0:
            continue

        suggestions.append(
            {
                "name": craft.name,
                "profession": craft.profession,
                "output_item_id": craft.output_item_id,
                "num_result": craft.num_result,
                "output_unit_price_copper": out_unit,
                "output_price_source": out_src,
                "gross_sell_copper": gross_sell,
                "ah_cut_rate": ah_cut_rate,
                "net_sell_copper": net_sell,
                "cost_copper": total_cost,
                "profit_per_craft_copper": profit,
                "max_crafts": max_crafts,
                "total_profit_copper": total_profit,
                "mats": mats,
                "players": craft.players,
                "has_cooldown": craft.has_cooldown,
            }
        )

    suggestions.sort(key=lambda r: float(r.get("total_profit_copper") or 0), reverse=True)
    if limit > 0:
        suggestions = suggestions[:limit]
    return suggestions

