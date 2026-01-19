from __future__ import annotations

from datetime import datetime, timezone
import logging
from pathlib import Path
import uuid

from mcp.server.fastmcp import FastMCP

from .config import load_config
from .paths import probe_savedvars_candidates
from .savedvars import LuaParseError, load_var, write_var
from .crafting import suggest_profitable_crafts
from .integrations.addons import find_addons_dir, iter_installed_addons
from .integrations.auctionator import (
    AuctionatorError,
    get_auctionator_price,
    get_vendor_price_copper,
    list_realm_keys,
)
from .integrations.syndicator import SyndicatorError, aggregate_item_counts, load_syndicator, pick_default_character_key
from .integrations.tradeskillmaster import (
    TradeSkillMasterError,
    iter_crafts as iter_tsm_crafts,
    list_craft_scopes as list_tsm_craft_scopes,
    load_crafts as load_tsm_crafts,
)
from .integrations.tsm_apphelper import TsmAppHelperError, get_price_copper as get_tsm_price_copper, list_scope_keys


mcp = FastMCP("wow")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("wow-mcp")


def _utc_now_iso_z() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _file_meta(path: Path) -> dict:
    try:
        st = path.stat()
    except FileNotFoundError:
        return {"exists": False, "path": str(path)}

    mtime = datetime.fromtimestamp(st.st_mtime, tz=timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )
    return {
        "exists": True,
        "path": str(path),
        "size_bytes": st.st_size,
        "mtime_utc": mtime,
        "age_seconds": max(0, int(datetime.now(timezone.utc).timestamp() - st.st_mtime)),
    }


def _item_name_from_link(link: str | None) -> str | None:
    if not isinstance(link, str) or not link:
        return None
    start = link.find("|h[")
    if start == -1:
        return None
    start += 3
    end = link.find("]|h", start)
    if end == -1:
        return None
    name = link[start:end]
    return name or None


@mcp.tool()
async def wow_config_get() -> dict:
    """Return the effective server config and resolved file paths."""
    cfg = load_config()
    return {
        "savedvars_dir": str(cfg.savedvars_dir),
        "state_var": cfg.state_var,
        "state_file": str(cfg.state_file),
        "cmd_var": cfg.cmd_var,
        "cmd_file": str(cfg.cmd_file),
        "scan_root": str(cfg.scan_root),
        "probe_max_depth": cfg.probe_max_depth,
    }


@mcp.tool()
async def wow_state_get() -> dict:
    """Read and parse `WowMCP_State.lua` (SavedVariables) into JSON-friendly Python data."""
    cfg = load_config()
    meta = _file_meta(cfg.state_file)
    if not meta.get("exists"):
        return {
            "status": "error",
            "error": "state_file_missing",
            "meta": meta,
            "hint": "Ensure the WoW SavedVariables folder is mounted and the addon has written state (logout or /reload).",
        }

    try:
        state = load_var(cfg.state_file, cfg.state_var)
    except KeyError as e:
        return {"status": "error", "error": "state_var_missing", "meta": meta, "detail": str(e)}
    except LuaParseError as e:
        return {"status": "error", "error": "state_parse_error", "meta": meta, "detail": str(e)}

    return {"status": "success", "meta": meta, "state": state}


_ALLOWED_CMD_TYPES: set[str] = {
    "NOTICE",
    "SUGGEST_QUESTS",
    "VENDOR_LIST",
    "AH_SUGGESTIONS",
    "WAYPOINT",
}


@mcp.tool()
async def wow_cmd_write(cmd: dict) -> dict:
    """
    Write a “soft command” into `WowMCP_Cmd.lua`.

    Notes:
    - This only changes the SavedVariables file on disk.
    - The addon will observe it on the next full UI load (relog/restart), not instantly.
    """
    if not isinstance(cmd, dict):
        return {"status": "error", "error": "invalid_input", "detail": "cmd must be an object/dict"}

    cmd_type = cmd.get("type")
    payload = cmd.get("payload", {})
    cmd_id = cmd.get("id") or uuid.uuid4().hex

    if cmd_type not in _ALLOWED_CMD_TYPES:
        return {"status": "error", "error": "invalid_cmd_type", "allowed": sorted(_ALLOWED_CMD_TYPES)}
    if not isinstance(payload, dict):
        return {"status": "error", "error": "invalid_payload", "detail": "payload must be an object/dict"}

    cfg = load_config()

    envelope = {
        "version": 1,
        "id": str(cmd_id),
        "type": cmd_type,
        "generated_at": _utc_now_iso_z(),
        "payload": payload,
    }

    try:
        write_var(cfg.cmd_file, cfg.cmd_var, envelope)
    except Exception as e:
        logger.exception("Failed to write command file")
        return {"status": "error", "error": "cmd_write_failed", "detail": str(e), "path": str(cfg.cmd_file)}

    return {"status": "success", "cmd_id": str(cmd_id), "path": str(cfg.cmd_file)}


@mcp.tool()
async def wow_paths_probe() -> dict:
    """Scan `WOW_SCAN_ROOT` for candidate SavedVariables folders containing `WowMCP_State.lua`."""
    cfg = load_config()
    candidates = probe_savedvars_candidates(
        scan_root=cfg.scan_root,
        state_filename=cfg.state_file.name,
        cmd_filename=cfg.cmd_file.name,
        max_depth=cfg.probe_max_depth,
    )
    return {
        "status": "success",
        "scan_root": str(cfg.scan_root),
        "count": len(candidates),
        "candidates": [
            {
                "savedvars_dir": str(c.savedvars_dir),
                "state_file": str(c.state_file),
                "cmd_file": str(c.cmd_file),
            }
            for c in candidates
        ],
    }


@mcp.tool()
async def wow_sources_detect() -> dict:
    """Detect which supported data sources are available in the mounted SavedVariables + scan root."""
    cfg = load_config()
    sv = cfg.savedvars_dir

    def exists(name: str) -> bool:
        return (sv / name).exists()

    addons_dir = find_addons_dir(cfg.scan_root)

    return {
        "status": "success",
        "savedvars_dir": str(cfg.savedvars_dir),
        "scan_root": str(cfg.scan_root),
        "addons_dir": str(addons_dir) if addons_dir else None,
        "savedvars": {
            "Syndicator": exists("Syndicator.lua"),
            "Auctionator": exists("Auctionator.lua"),
            "TradeSkillMaster": exists("TradeSkillMaster.lua"),
            "TradeSkillMaster_AppHelper": exists("TradeSkillMaster_AppHelper.lua"),
            "Questie": exists("Questie.lua"),
            "ClassicCodex": exists("ClassicCodex.lua"),
        },
    }


@mcp.tool()
async def wow_addons_list() -> dict:
    """List installed addons from the `Interface/AddOns` directory under `WOW_SCAN_ROOT`."""
    cfg = load_config()
    addons_dir = find_addons_dir(cfg.scan_root)
    if addons_dir is None:
        return {
            "status": "error",
            "error": "addons_dir_not_found",
            "scan_root": str(cfg.scan_root),
            "hint": "Set WOW_SCAN_ROOT_HOST to your WoW game directory (the folder containing Interface/ and WTF/).",
        }

    addons = [
        {
            "name": a.name,
            "title": a.title,
            "version": a.version,
        }
        for a in iter_installed_addons(addons_dir)
    ]

    return {"status": "success", "addons_dir": str(addons_dir), "count": len(addons), "addons": addons}


@mcp.tool()
async def wow_characters_list() -> dict:
    """List characters known to Syndicator (bag cache)."""
    cfg = load_config()
    try:
        data, _config = load_syndicator(cfg.savedvars_dir)
    except SyndicatorError as e:
        return {"status": "error", "error": "syndicator_unavailable", "detail": str(e)}

    keys = sorted((data.get("Characters") or {}).keys()) if isinstance(data.get("Characters"), dict) else []
    keys = [k for k in keys if isinstance(k, str)]
    return {"status": "success", "count": len(keys), "characters": keys}


@mcp.tool()
async def wow_inventory_get(character_key: str | None = None, include_bank: bool = True) -> dict:
    """
    Return an aggregated inventory snapshot using Syndicator (Baganator/Syndicator).

    Notes:
    - This reflects the last cached state written by the addon; not real-time.
    """
    cfg = load_config()
    try:
        data, _config = load_syndicator(cfg.savedvars_dir)
    except SyndicatorError as e:
        return {"status": "error", "error": "syndicator_unavailable", "detail": str(e)}

    if character_key is None:
        character_key = pick_default_character_key(data)
    if character_key is None:
        return {"status": "error", "error": "no_characters_found"}

    chars = data.get("Characters")
    if not isinstance(chars, dict) or character_key not in chars or not isinstance(chars[character_key], dict):
        return {"status": "error", "error": "character_not_found", "character_key": character_key}

    character = chars[character_key]
    details = character.get("details") if isinstance(character.get("details"), dict) else {}
    money = character.get("money") if isinstance(character.get("money"), int) else None
    items = aggregate_item_counts(character, include_bank=include_bank)

    # Sort by count desc (value-based sorting is provided by wow_inventory_value)
    items_list = list(items.values())
    items_list.sort(key=lambda r: int(r.get("count") or 0), reverse=True)

    return {
        "status": "success",
        "character_key": character_key,
        "details": details,
        "money_copper": money,
        "include_bank": include_bank,
        "unique_items": len(items_list),
        "items": items_list,
    }


@mcp.tool()
async def wow_auctionator_realms_list() -> dict:
    """List Auctionator realm/faction keys present in `AUCTIONATOR_PRICE_DATABASE`."""
    cfg = load_config()
    try:
        keys = list_realm_keys(cfg.savedvars_dir)
    except AuctionatorError as e:
        return {"status": "error", "error": "auctionator_unavailable", "detail": str(e)}
    return {"status": "success", "count": len(keys), "realm_keys": keys}


@mcp.tool()
async def wow_tsm_scopes_list() -> dict:
    """List TSM scope keys present in `TradeSkillMaster_AppHelper.lua` (if installed)."""
    cfg = load_config()
    try:
        keys = list_scope_keys(cfg.savedvars_dir)
    except TsmAppHelperError as e:
        return {"status": "error", "error": "tsm_apphelper_unavailable", "detail": str(e)}
    return {"status": "success", "count": len(keys), "scope_keys": keys}


@mcp.tool()
async def wow_price_get(
    item_id: int,
    source: str = "auto",
    realm_key: str | None = None,
) -> dict:
    """
    Get a unit price for an item (copper).

    Sources:
    - auto: TSM (if available) else Auctionator else vendor cache
    - auctionator: Auctionator price database
    - vendor: Auctionator vendor price cache
    - tsm: TradeSkillMaster AppHelper (`dbmarket`) if available
    """
    cfg = load_config()
    source = (source or "auto").lower()

    def vendor() -> dict | None:
        try:
            v = get_vendor_price_copper(cfg.savedvars_dir, item_id)
        except AuctionatorError:
            return None
        if v is None:
            return None
        return {"source": "vendor", "unit_price_copper": v}

    def auctionator() -> dict | None:
        try:
            keys = list_realm_keys(cfg.savedvars_dir)
        except AuctionatorError:
            return None
        rk = realm_key or (keys[0] if keys else None)
        if rk is None:
            return None
        try:
            price = get_auctionator_price(cfg.savedvars_dir, realm_key=rk, db_key=str(item_id))
        except AuctionatorError as e:
            return {"error": "auctionator_error", "detail": str(e)}
        if price is None:
            return None
        return {
            "source": "auctionator",
            "realm_key": rk,
            "db_key": price.db_key,
            "unit_price_copper": price.price_copper,
            "age_days": price.age_days,
        }

    def tsm() -> dict | None:
        """
        TSM AppHelper uses scope keys which are not always the same as Auctionator realm keys.
        We reuse `realm_key` as an optional override.
        """
        try:
            keys = list_scope_keys(cfg.savedvars_dir)
        except TsmAppHelperError:
            return None
        scope_key = realm_key or (keys[0] if keys else None)
        try:
            p = get_tsm_price_copper(cfg.savedvars_dir, item_id=item_id, price_source="dbmarket", scope_key=scope_key)
        except TsmAppHelperError as e:
            return {"error": "tsm_apphelper_error", "detail": str(e)}
        if p is None:
            return None
        return {
            "source": "tsm",
            "scope_key": p.scope_key,
            "price_source": p.price_source,
            "item_key": p.item_key,
            "unit_price_copper": p.unit_price_copper,
        }

    if source == "vendor":
        out = vendor()
        return {"status": "success", "item_id": item_id, "price": out} if out else {"status": "error", "error": "no_price"}

    if source == "tsm":
        out = tsm()
        if out and "error" in out:
            return {"status": "error", **out}
        return {"status": "success", "item_id": item_id, "price": out} if out else {"status": "error", "error": "no_price"}

    if source == "auctionator":
        out = auctionator()
        if out and "error" in out:
            return {"status": "error", **out}
        return {"status": "success", "item_id": item_id, "price": out} if out else {"status": "error", "error": "no_price"}

    if source == "auto":
        out = tsm()
        if out and "error" in out:
            return {"status": "error", **out}
        if out is not None:
            return {"status": "success", "item_id": item_id, "price": out}
        out = auctionator()
        if out and "error" in out:
            return {"status": "error", **out}
        if out is None:
            out = vendor()
        return {"status": "success", "item_id": item_id, "price": out} if out else {"status": "error", "error": "no_price"}

    return {
        "status": "error",
        "error": "invalid_source",
        "allowed": ["auto", "auctionator", "vendor", "tsm"],
    }


@mcp.tool()
async def wow_inventory_value(
    character_key: str | None = None,
    include_bank: bool = True,
    price_source: str = "auto",
    realm_key: str | None = None,
    limit: int = 50,
) -> dict:
    """
    Value inventory items using available pricing sources.

    Returns top-N items by estimated total value (unit * count) for which a price is found.
    """
    inv = await wow_inventory_get(character_key=character_key, include_bank=include_bank)
    if inv.get("status") != "success":
        return inv

    items = inv.get("items") or []
    if not isinstance(items, list):
        return {"status": "error", "error": "invalid_inventory_shape"}

    valued: list[dict] = []
    for row in items:
        if not isinstance(row, dict):
            continue
        item_id = row.get("item_id")
        count = row.get("count")
        if not isinstance(item_id, int) or not isinstance(count, int):
            continue
        p = await wow_price_get(item_id=item_id, source=price_source, realm_key=realm_key)
        if p.get("status") != "success":
            continue
        price = p.get("price")
        if not isinstance(price, dict):
            continue
        unit = price.get("unit_price_copper")
        if not isinstance(unit, (int, float)):
            continue
        total = float(unit) * count
        valued.append(
            {
                "item_id": item_id,
                "count": count,
                "unit_price_copper": unit,
                "total_value_copper": total,
                "price_source": price.get("source"),
                "realm_key": price.get("realm_key"),
                "age_days": price.get("age_days"),
                "bound_any": row.get("bound_any"),
                "locations": row.get("locations"),
                "example_link": row.get("example_link"),
            }
        )

    valued.sort(key=lambda r: float(r.get("total_value_copper") or 0), reverse=True)
    if limit > 0:
        valued = valued[:limit]

    return {
        "status": "success",
        "character_key": inv.get("character_key"),
        "details": inv.get("details"),
        "include_bank": include_bank,
        "price_source": price_source,
        "realm_key": realm_key,
        "count": len(valued),
        "items": valued,
    }


@mcp.tool()
async def wow_liquidation_plan(
    character_key: str | None = None,
    include_bank: bool = True,
    price_source: str = "auto",
    realm_key: str | None = None,
    limit: int = 80,
) -> dict:
    """
    Suggest a liquidation plan for your inventory.

    This is guidance-only: it does not (and cannot) perform protected actions.
    """
    inv = await wow_inventory_get(character_key=character_key, include_bank=include_bank)
    if inv.get("status") != "success":
        return inv

    items = inv.get("items") or []
    if not isinstance(items, list):
        return {"status": "error", "error": "invalid_inventory_shape"}

    price_cache: dict[int, dict | None] = {}

    async def get_price(item_id: int) -> dict | None:
        if item_id in price_cache:
            return price_cache[item_id]
        p = await wow_price_get(item_id=item_id, source=price_source, realm_key=realm_key)
        if p.get("status") != "success":
            price_cache[item_id] = None
            return None
        price = p.get("price")
        if not isinstance(price, dict):
            price_cache[item_id] = None
            return None
        price_cache[item_id] = price
        return price

    rows: list[dict] = []
    for row in items:
        if not isinstance(row, dict):
            continue
        item_id = row.get("item_id")
        count = row.get("count")
        if not isinstance(item_id, int) or not isinstance(count, int) or count <= 0:
            continue

        bound_any = row.get("bound_any")
        name = _item_name_from_link(row.get("example_link"))
        price = await get_price(item_id)

        unit: float | int | None = None
        src: str | None = None
        if isinstance(price, dict):
            unit = price.get("unit_price_copper")
            src = price.get("source")

        market_unit: float | int | None = None
        if src in {"auctionator", "tsm"} and isinstance(unit, (int, float)):
            market_unit = unit

        total_value: float | None = None
        if market_unit is not None:
            total_value = float(market_unit) * count

        action = "unknown"
        if bound_any is True:
            action = "bound_keep_or_vendor"
        elif market_unit is not None:
            action = "sell_ah"

        rows.append(
            {
                "item_id": item_id,
                "name": name,
                "count": count,
                "bound_any": bound_any,
                "market_unit_price_copper": market_unit,
                "market_total_value_copper": total_value,
                "price_source": src,
                "age_days": price.get("age_days") if isinstance(price, dict) else None,
                "locations": row.get("locations"),
                "action": action,
                "example_link": row.get("example_link"),
            }
        )

    rows.sort(key=lambda r: float(r.get("market_total_value_copper") or 0), reverse=True)
    if limit > 0:
        rows = rows[:limit]

    return {
        "status": "success",
        "character_key": inv.get("character_key"),
        "details": inv.get("details"),
        "include_bank": include_bank,
        "price_source": price_source,
        "realm_key": realm_key,
        "count": len(rows),
        "items": rows,
        "notes": [
            "AH suggestions require manual posting (no protected automation).",
            "Prices are best-effort and depend on last addon scan; run an Auctionator scan and /reload for freshness.",
        ],
    }


@mcp.tool()
async def wow_tsm_craft_scopes_list() -> dict:
    """List TSM craft scopes present in `TradeSkillMaster.lua`."""
    cfg = load_config()
    try:
        scopes = list_tsm_craft_scopes(cfg.savedvars_dir)
    except TradeSkillMasterError as e:
        return {"status": "error", "error": "tsm_unavailable", "detail": str(e)}
    return {"status": "success", "count": len(scopes), "scopes": scopes}


@mcp.tool()
async def wow_tsm_crafts_list(
    scope: str | None = None,
    profession: str | None = None,
    limit: int = 200,
) -> dict:
    """List crafts known to TSM (from its scanned profession data)."""
    cfg = load_config()
    try:
        scopes = list_tsm_craft_scopes(cfg.savedvars_dir)
    except TradeSkillMasterError as e:
        return {"status": "error", "error": "tsm_unavailable", "detail": str(e)}
    if not scopes:
        return {"status": "error", "error": "no_tsm_craft_scopes_found"}

    chosen = scope or scopes[0]
    if chosen not in scopes:
        return {"status": "error", "error": "scope_not_found", "scope": chosen, "available": scopes}

    try:
        crafts_raw = load_tsm_crafts(cfg.savedvars_dir, chosen)
    except TradeSkillMasterError as e:
        return {"status": "error", "error": "tsm_crafts_unavailable", "detail": str(e)}

    crafts: list[dict] = []
    for craft in iter_tsm_crafts(crafts_raw):
        if profession is not None and craft.profession.lower() != profession.lower():
            continue
        crafts.append(
            {
                "craft_key": craft.craft_key,
                "name": craft.name,
                "profession": craft.profession,
                "output_item_id": craft.output_item_id,
                "num_result": craft.num_result,
                "mats": [{"item_id": mid, "quantity": qty} for mid, qty in sorted(craft.mats.items())],
                "players": craft.players,
                "has_cooldown": craft.has_cooldown,
            }
        )
        if limit > 0 and len(crafts) >= limit:
            break

    return {
        "status": "success",
        "scope": chosen,
        "profession": profession,
        "count": len(crafts),
        "crafts": crafts,
    }


@mcp.tool()
async def wow_crafting_suggestions(
    character_key: str | None = None,
    include_bank: bool = True,
    tsm_scope: str | None = None,
    price_source: str = "auto",
    realm_key: str | None = None,
    limit: int = 20,
    ah_cut_rate: float = 0.05,
) -> dict:
    """
    Suggest profitable crafts using TSM's scanned craft data + your current inventory.

    Notes:
    - Guidance-only; you still craft and post manually.
    - Profit is best-effort (AH deposit not modeled).
    """
    cfg = load_config()

    inv = await wow_inventory_get(character_key=character_key, include_bank=include_bank)
    if inv.get("status") != "success":
        return inv
    items = inv.get("items") or []
    if not isinstance(items, list):
        return {"status": "error", "error": "invalid_inventory_shape"}

    have_by_id: dict[int, int] = {}
    for row in items:
        if not isinstance(row, dict):
            continue
        iid = row.get("item_id")
        cnt = row.get("count")
        if isinstance(iid, int) and isinstance(cnt, int) and cnt > 0:
            have_by_id[iid] = have_by_id.get(iid, 0) + cnt

    try:
        scopes = list_tsm_craft_scopes(cfg.savedvars_dir)
    except TradeSkillMasterError as e:
        return {"status": "error", "error": "tsm_unavailable", "detail": str(e)}
    if not scopes:
        return {"status": "error", "error": "no_tsm_craft_scopes_found"}

    chosen = tsm_scope or scopes[0]
    if chosen not in scopes:
        return {"status": "error", "error": "tsm_scope_not_found", "tsm_scope": chosen, "available": scopes}

    try:
        crafts_raw = load_tsm_crafts(cfg.savedvars_dir, chosen)
    except TradeSkillMasterError as e:
        return {"status": "error", "error": "tsm_crafts_unavailable", "detail": str(e)}

    price_cache: dict[int, dict | None] = {}

    async def get_price(item_id: int) -> dict | None:
        if item_id in price_cache:
            return price_cache[item_id]
        p = await wow_price_get(item_id=item_id, source=price_source, realm_key=realm_key)
        if p.get("status") != "success":
            price_cache[item_id] = None
            return None
        price = p.get("price")
        if not isinstance(price, dict):
            price_cache[item_id] = None
            return None
        price_cache[item_id] = price
        return price

    def vendor_price(item_id: int) -> float | None:
        try:
            return get_vendor_price_copper(cfg.savedvars_dir, item_id)
        except AuctionatorError:
            return None

    suggestions = await suggest_profitable_crafts(
        crafts_raw,
        have_by_id=have_by_id,
        get_price=get_price,
        get_vendor_price=vendor_price,
        ah_cut_rate=ah_cut_rate,
        limit=limit,
    )

    return {
        "status": "success",
        "character_key": inv.get("character_key"),
        "details": inv.get("details"),
        "include_bank": include_bank,
        "tsm_scope": chosen,
        "price_source": price_source,
        "realm_key": realm_key,
        "count": len(suggestions),
        "suggestions": suggestions,
        "notes": [
            "All actions remain manual (crafting, posting).",
            "TSM crafts come from TSM's internal scanned data; open profession windows in-game to refresh it.",
        ],
    }


def main() -> None:
    logger.info("Starting WoW MCP Server (stdio)...")
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
