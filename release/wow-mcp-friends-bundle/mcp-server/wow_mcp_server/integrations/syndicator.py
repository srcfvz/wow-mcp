from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from ..savedvars import LuaParseError, load_var


SYNDICATOR_FILENAME = "Syndicator.lua"
SYNDICATOR_DATA_VAR = "SYNDICATOR_DATA"
SYNDICATOR_CONFIG_VAR = "SYNDICATOR_CONFIG"


class SyndicatorError(RuntimeError):
    pass


@dataclass(frozen=True)
class SyndicatorItem:
    item_id: int
    item_count: int
    item_link: str | None
    is_bound: bool | None
    quality: int | None
    location: str


def _iter_item_entries(container: Any, *, location: str) -> Iterable[SyndicatorItem]:
    """
    Traverse Syndicator's slot structures and yield item entries.

    Known shapes:
    - bags: list[bag] where bag is list[slot] and slot is {} or {itemID, itemCount, ...}
    - bank: same shape
    """
    if not isinstance(container, list):
        return
    for bag in container:
        if not isinstance(bag, list):
            continue
        for slot in bag:
            if not isinstance(slot, dict):
                continue
            item_id = slot.get("itemID")
            item_count = slot.get("itemCount")
            if not isinstance(item_id, int) or not isinstance(item_count, int):
                continue
            yield SyndicatorItem(
                item_id=item_id,
                item_count=item_count,
                item_link=slot.get("itemLink") if isinstance(slot.get("itemLink"), str) else None,
                is_bound=slot.get("isBound") if isinstance(slot.get("isBound"), bool) else None,
                quality=slot.get("quality") if isinstance(slot.get("quality"), int) else None,
                location=location,
            )


def load_syndicator(savedvars_dir: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    path = savedvars_dir / SYNDICATOR_FILENAME
    if not path.exists():
        raise SyndicatorError(f"Missing {SYNDICATOR_FILENAME} in {savedvars_dir}")
    try:
        data = load_var(path, SYNDICATOR_DATA_VAR)
        config = load_var(path, SYNDICATOR_CONFIG_VAR)
    except (LuaParseError, KeyError) as e:
        raise SyndicatorError(str(e)) from e
    if not isinstance(data, dict) or not isinstance(config, dict):
        raise SyndicatorError("Unexpected Syndicator savedvars shape")
    return data, config


def list_characters(data: dict[str, Any]) -> list[str]:
    chars = data.get("Characters")
    if not isinstance(chars, dict):
        return []
    keys = [k for k in chars.keys() if isinstance(k, str)]
    keys.sort()
    return keys


def get_character(data: dict[str, Any], character_key: str) -> dict[str, Any] | None:
    chars = data.get("Characters")
    if not isinstance(chars, dict):
        return None
    c = chars.get(character_key)
    return c if isinstance(c, dict) else None


def pick_default_character_key(data: dict[str, Any]) -> str | None:
    keys = list_characters(data)
    return keys[0] if keys else None


def get_character_details(character: dict[str, Any]) -> dict[str, Any]:
    details = character.get("details")
    if isinstance(details, dict):
        return details
    return {}


def get_money_copper(character: dict[str, Any]) -> int | None:
    money = character.get("money")
    return money if isinstance(money, int) else None


def iter_items(character: dict[str, Any], *, include_bank: bool = True) -> Iterable[SyndicatorItem]:
    yield from _iter_item_entries(character.get("bags"), location="bags")
    if include_bank:
        yield from _iter_item_entries(character.get("bank"), location="bank")


def aggregate_item_counts(
    character: dict[str, Any],
    *,
    include_bank: bool = True,
) -> dict[int, dict[str, Any]]:
    """
    Returns a map item_id -> {count, example_link, bound_any, quality_max, locations}.
    """
    out: dict[int, dict[str, Any]] = {}
    locations: dict[int, set[str]] = defaultdict(set)

    for item in iter_items(character, include_bank=include_bank):
        if item.item_id not in out:
            out[item.item_id] = {
                "item_id": item.item_id,
                "count": 0,
                "example_link": item.item_link,
                "bound_any": bool(item.is_bound) if item.is_bound is not None else None,
                "quality_max": item.quality,
            }
        row = out[item.item_id]
        row["count"] += item.item_count

        if row.get("example_link") is None and item.item_link is not None:
            row["example_link"] = item.item_link

        if item.is_bound is True:
            row["bound_any"] = True

        if isinstance(item.quality, int):
            prev = row.get("quality_max")
            if not isinstance(prev, int) or item.quality > prev:
                row["quality_max"] = item.quality

        locations[item.item_id].add(item.location)

    for item_id, locs in locations.items():
        out[item_id]["locations"] = sorted(locs)

    return out
