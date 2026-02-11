from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import threading
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from mcp.server.fastmcp import FastMCP

from .bridge_helpers import normalize_provider, summarize_state_for_prompt
from .config import load_config as load_env_config
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
from .paths import probe_savedvars_candidates
from .savedvars import LuaParseError, load_var, write_var


mcp = FastMCP("wow")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("wow-mcp")


SERVER_CONFIG: Dict[str, Any] = {}


def _utc_now_iso_z() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _file_meta(path: Path) -> dict[str, Any]:
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


def _normalize_source_name(name: str) -> str:
    return "".join(ch for ch in (name or "").lower() if ch.isalnum())


_SOURCE_EQUIVALENTS: dict[str, set[str]] = {
    "WowMCP": {"WowMCP", "WowMCP_State", "WowMCP_Cmd"},
    "Syndicator": {"Syndicator", "Baganator"},
    "Auctionator": {"Auctionator"},
    "TradeSkillMaster": {"TradeSkillMaster", "TSM"},
    "TradeSkillMaster_AppHelper": {"TradeSkillMaster_AppHelper", "TSM_AppHelper", "TSMAppHelper"},
    "TomTom": {"TomTom"},
}

_SOURCE_EQUIVALENTS_NORMALIZED: dict[str, set[str]] = {}
for alias_group in _SOURCE_EQUIVALENTS.values():
    normalized_group = {_normalize_source_name(name) for name in alias_group}
    for normalized_name in normalized_group:
        _SOURCE_EQUIVALENTS_NORMALIZED[normalized_name] = normalized_group


def _source_flags() -> dict[str, bool]:
    raw = SERVER_CONFIG.get("data_sources")
    if not isinstance(raw, dict):
        return {}

    flags: dict[str, bool] = {}
    for key, value in raw.items():
        if isinstance(key, str):
            flags[_normalize_source_name(key)] = bool(value)
    return flags


def _is_source_enabled(source_name: str) -> bool:
    flags = _source_flags()
    if not flags:
        return True

    normalized = _normalize_source_name(source_name)
    candidates = _SOURCE_EQUIVALENTS_NORMALIZED.get(normalized, {normalized})
    matched = False

    for candidate in candidates:
        if candidate in flags:
            matched = True
            if not flags[candidate]:
                return False

    # If user never configured this source (or all matched entries are enabled), keep permissive defaults.
    return True


def _source_config_snapshot() -> dict[str, bool]:
    raw = SERVER_CONFIG.get("data_sources")
    if not isinstance(raw, dict):
        return {}
    return {str(k): bool(v) for k, v in raw.items() if isinstance(k, str)}


def check_permission(perm_key: str) -> None:
    # Keep permissive defaults outside desktop-config mode.
    if not SERVER_CONFIG:
        return

    perms = SERVER_CONFIG.get("permissions")
    if not isinstance(perms, dict):
        return

    # Only enforce when explicitly present in config.
    if perm_key in perms and not bool(perms.get(perm_key)):
        raise ValueError(f"Permission denied: {perm_key}")


def check_source(source_name: str) -> None:
    if not _is_source_enabled(source_name):
        raise ValueError(f"Data source disabled: {source_name}")


# --- Bridge / Chat Logic ---

def _http_post_json(url: str, headers: dict[str, str], payload: dict[str, Any], timeout_s: float) -> dict[str, Any]:
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers={**headers, "Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=timeout_s) as resp:  # nosec - URL is explicitly configured by the user
        raw = resp.read()
    return json.loads(raw.decode("utf-8", errors="replace"))


def _call_llm(provider: str, model: str, system_prompt: str, user_prompt: str, api_key: str | None) -> str:
    provider = normalize_provider(provider)
    model = model or ""
    timeout_s = 45.0

    if provider == "ollama":
        base_url = (SERVER_CONFIG.get("llm", {}) or {}).get("base_url") or os.environ.get("OLLAMA_HOST") or "http://localhost:11434"
        url = base_url.rstrip("/") + "/api/chat"
        payload = {
            "model": model or "llama3.1",
            "stream": False,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }
        data = _http_post_json(url, headers={}, payload=payload, timeout_s=timeout_s)
        msg = (((data or {}).get("message") or {}) if isinstance(data, dict) else {}).get("content")
        return (msg or "").strip() or "(no response)"

    if not api_key:
        raise ValueError("missing_api_key")

    if provider == "openai":
        url = (SERVER_CONFIG.get("llm", {}) or {}).get("base_url") or "https://api.openai.com/v1/chat/completions"
        payload = {
            "model": model or "gpt-4o-mini",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.2,
        }
        data = _http_post_json(url, headers={"Authorization": f"Bearer {api_key}"}, payload=payload, timeout_s=timeout_s)
        content = (((((data or {}).get("choices") or [None])[0] or {}).get("message") or {}) if isinstance(data, dict) else {}).get("content")
        return (content or "").strip() or "(no response)"

    if provider == "anthropic":
        url = (SERVER_CONFIG.get("llm", {}) or {}).get("base_url") or "https://api.anthropic.com/v1/messages"
        payload = {
            "model": model or "claude-3-5-sonnet-latest",
            "max_tokens": 300,
            "system": system_prompt,
            "messages": [{"role": "user", "content": user_prompt}],
        }
        headers = {"x-api-key": api_key, "anthropic-version": "2023-06-01"}
        data = _http_post_json(url, headers=headers, payload=payload, timeout_s=timeout_s)
        parts = (data or {}).get("content") if isinstance(data, dict) else None
        if isinstance(parts, list) and parts:
            text = (parts[0] or {}).get("text")
            return (text or "").strip() or "(no response)"
        return "(no response)"

    if provider == "gemini":
        model_name = model or "gemini-1.5-flash"
        if not model_name.startswith("models/"):
            model_name = "models/" + model_name
        url = f"https://generativelanguage.googleapis.com/v1beta/{model_name}:generateContent?key={api_key}"
        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": f"{system_prompt}\n\n{user_prompt}"}],
                }
            ]
        }
        data = _http_post_json(url, headers={}, payload=payload, timeout_s=timeout_s)
        candidates = (data or {}).get("candidates") if isinstance(data, dict) else None
        if isinstance(candidates, list) and candidates:
            parts = (((candidates[0] or {}).get("content") or {}).get("parts")) if isinstance(candidates[0], dict) else None
            if isinstance(parts, list) and parts:
                text = (parts[0] or {}).get("text")
                return (text or "").strip() or "(no response)"
        return "(no response)"

    raise ValueError(f"unsupported_provider:{provider}")


def _persist_bridge_state(path: Path, last_processed_seq: int) -> None:
    try:
        path.write_text(json.dumps({"last_processed_seq": last_processed_seq}, indent=2), encoding="utf-8")
    except Exception:
        logger.debug("Bridge: failed writing bridge state file", exc_info=True)


async def _write_cmd(cmd_file: Path, cmd_var: str, type_str: str, payload: dict[str, Any]) -> None:
    envelope = {
        "version": 1,
        "id": uuid.uuid4().hex,
        "type": type_str,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "payload": payload,
    }
    write_var(cmd_file, cmd_var, envelope)


async def process_chat_request(prompt: str, state_data: dict[str, Any] | None = None) -> str:
    perms = SERVER_CONFIG.get("permissions", {}) if isinstance(SERVER_CONFIG.get("permissions"), dict) else {}
    llm_cfg = SERVER_CONFIG.get("llm", {}) or {}
    provider = llm_cfg.get("provider", "openai")
    model = llm_cfg.get("model", "")

    context: list[str] = []

    if perms.get("inventory"):
        try:
            inv = await wow_inventory_get(limit=10)
            if inv.get("status") == "success":
                items_summary = ", ".join([f"{i['count']}x {i['item_id']}" for i in (inv.get("items") or [])[:5]])
                if items_summary:
                    context.append(f"Top Inventory: {items_summary}")
        except Exception:
            # Keep chat available even if inventory source is unavailable.
            pass

    if state_data and isinstance(state_data, dict):
        summary = summarize_state_for_prompt(state_data, perms)
        if summary:
            context.append(summary)

    system_prompt = (
        "You are a helpful WoW assistant. Keep answers short (max 2 sentences) because in-game UI is limited. "
        "Never suggest botting or protected-action automation."
    )
    if context:
        system_prompt += "\nContext:\n" + "\n".join(context)

    api_key = os.environ.get("WOW_MCP_API_KEY")
    provider_norm = normalize_provider(str(provider))
    logger.info("Bridge LLM Provider: %s", provider_norm)
    return _call_llm(provider_norm, str(model), system_prompt, prompt, api_key)


async def bridge_loop() -> None:
    """
    Poll WoW SavedVariables for chat requests from the addon (reload-based).
    """
    logger.info("Bridge: starting polling loop")

    env_cfg = load_env_config()
    state_file = env_cfg.state_file
    cmd_file = env_cfg.cmd_file

    bridge_state_path = Path(SERVER_CONFIG.get("bridge_state_file") or "bridge_state.json")
    last_processed_seq = 0
    try:
        if bridge_state_path.exists():
            last_processed_seq = int(json.loads(bridge_state_path.read_text(encoding="utf-8")).get("last_processed_seq") or 0)
    except Exception:
        last_processed_seq = 0

    while True:
        try:
            if state_file.exists():
                try:
                    state_data = load_var(state_file, env_cfg.state_var)
                except (LuaParseError, Exception):
                    # File may be in-flight while WoW writes.
                    await asyncio.sleep(0.2)
                    continue

                chat_state = state_data.get("chat") if isinstance(state_data, dict) else None
                outbox = (chat_state or {}).get("outbox") if isinstance(chat_state, dict) else None

                if isinstance(outbox, list) and outbox:
                    pending: list[tuple[int, str]] = []
                    for item in outbox:
                        if not isinstance(item, dict):
                            continue
                        seq = int(item.get("seq") or 0)
                        text = item.get("text")
                        if seq > last_processed_seq and isinstance(text, str) and text.strip():
                            pending.append((seq, text.strip()))

                    pending.sort(key=lambda row: row[0])
                    for seq, prompt in pending[:5]:
                        logger.info("Bridge: processing chat seq=%s", seq)
                        try:
                            response_text = await process_chat_request(prompt, state_data)
                            await _write_cmd(cmd_file, env_cfg.cmd_var, "CHAT_RESPONSE", {"text": response_text, "seq": seq})
                        except Exception as e:
                            await _write_cmd(cmd_file, env_cfg.cmd_var, "CHAT_ERROR", {"error": str(e), "seq": seq})
                        finally:
                            # Persist in both success and error paths to avoid replay storms.
                            last_processed_seq = seq
                            _persist_bridge_state(bridge_state_path, last_processed_seq)

        except Exception:
            logger.exception("Bridge loop error")

        await asyncio.sleep(0.25)


# --- MCP Tools ---

@mcp.tool()
async def wow_config_get() -> dict:
    """Return the effective server config and resolved file paths."""
    cfg = load_env_config()
    return {
        "savedvars_dir": str(cfg.savedvars_dir),
        "state_var": cfg.state_var,
        "state_file": str(cfg.state_file),
        "cmd_var": cfg.cmd_var,
        "cmd_file": str(cfg.cmd_file),
        "scan_root": str(cfg.scan_root),
        "probe_max_depth": cfg.probe_max_depth,
        "permissions": SERVER_CONFIG.get("permissions") if isinstance(SERVER_CONFIG.get("permissions"), dict) else {},
        "data_sources": _source_config_snapshot(),
    }


@mcp.tool()
async def wow_state_get() -> dict:
    """Read and parse `WowMCP_State.lua` (SavedVariables) into JSON-friendly Python data."""
    check_source("WowMCP")
    cfg = load_env_config()
    meta = _file_meta(cfg.state_file)
    if not meta.get("exists"):
        return {
            "status": "error",
            "error": "state_file_missing",
            "meta": meta,
            "hint": "Ensure SavedVariables are configured and run /reload in-game.",
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
    "CHAT_RESPONSE",
    "CHAT_ERROR",
}


@mcp.tool()
async def wow_cmd_write(cmd: dict) -> dict:
    """
    Write a "soft command" into `WowMCP_Cmd.lua`.

    Notes:
    - This only changes the SavedVariables file on disk.
    - The addon observes it on next load (`/reload` or relog), not instantly.
    """
    check_source("WowMCP")

    if not isinstance(cmd, dict):
        return {"status": "error", "error": "invalid_input", "detail": "cmd must be an object/dict"}

    cmd_type = cmd.get("type")
    payload = cmd.get("payload", {})
    cmd_id = cmd.get("id") or uuid.uuid4().hex

    if cmd_type not in _ALLOWED_CMD_TYPES:
        return {"status": "error", "error": "invalid_cmd_type", "allowed": sorted(_ALLOWED_CMD_TYPES)}
    if not isinstance(payload, dict):
        return {"status": "error", "error": "invalid_payload", "detail": "payload must be an object/dict"}

    cfg = load_env_config()

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
    check_source("WowMCP")
    cfg = load_env_config()
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
    """Detect which supported data sources are available in mounted SavedVariables + scan root."""
    cfg = load_env_config()
    sv = cfg.savedvars_dir

    def exists(name: str) -> bool:
        return (sv / name).exists()

    addons_dir = find_addons_dir(cfg.scan_root)

    return {
        "status": "success",
        "savedvars_dir": str(cfg.savedvars_dir),
        "scan_root": str(cfg.scan_root),
        "addons_dir": str(addons_dir) if addons_dir else None,
        "configured_sources": _source_config_snapshot(),
        "savedvars": {
            "Syndicator": exists("Syndicator.lua"),
            "Auctionator": exists("Auctionator.lua"),
            "TradeSkillMaster": exists("TradeSkillMaster.lua"),
            "TradeSkillMaster_AppHelper": exists("TradeSkillMaster_AppHelper.lua"),
            "Questie": exists("Questie.lua"),
            "ClassicCodex": exists("ClassicCodex.lua"),
            "WowMCP_State": exists("WowMCP_State.lua"),
            "WowMCP_Cmd": exists("WowMCP_Cmd.lua"),
        },
    }


@mcp.tool()
async def wow_addons_list() -> dict:
    """List installed addons from `Interface/AddOns` under `WOW_SCAN_ROOT`."""
    cfg = load_env_config()
    addons_dir = find_addons_dir(cfg.scan_root)
    if addons_dir is None:
        return {
            "status": "error",
            "error": "addons_dir_not_found",
            "scan_root": str(cfg.scan_root),
            "hint": "Set WOW_SCAN_ROOT to your WoW folder containing Interface/AddOns.",
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
    check_permission("inventory")
    check_source("Syndicator")

    cfg = load_env_config()
    try:
        data, _ = load_syndicator(cfg.savedvars_dir)
    except SyndicatorError as e:
        return {"status": "error", "error": "syndicator_unavailable", "detail": str(e)}

    keys = sorted((data.get("Characters") or {}).keys()) if isinstance(data.get("Characters"), dict) else []
    keys = [k for k in keys if isinstance(k, str)]
    return {"status": "success", "count": len(keys), "characters": keys}


@mcp.tool()
async def wow_inventory_get(character_key: str | None = None, include_bank: bool = True, limit: int = 0) -> dict:
    """
    Return an aggregated inventory snapshot using Syndicator (Baganator/Syndicator).

    Notes:
    - This reflects the last cached state written by the addon; not real-time.
    """
    check_permission("inventory")
    check_source("Syndicator")

    cfg = load_env_config()
    try:
        data, _ = load_syndicator(cfg.savedvars_dir)
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

    items_list = list(items.values())
    items_list.sort(key=lambda row: int(row.get("count") or 0), reverse=True)
    if limit > 0:
        items_list = items_list[:limit]

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
    check_permission("auction")
    check_source("Auctionator")

    cfg = load_env_config()
    try:
        keys = list_realm_keys(cfg.savedvars_dir)
    except AuctionatorError as e:
        return {"status": "error", "error": "auctionator_unavailable", "detail": str(e)}
    return {"status": "success", "count": len(keys), "realm_keys": keys}


@mcp.tool()
async def wow_tsm_scopes_list() -> dict:
    """List TSM scope keys present in `TradeSkillMaster_AppHelper.lua` (if installed)."""
    check_permission("auction")
    check_source("TradeSkillMaster_AppHelper")

    cfg = load_env_config()
    try:
        keys = list_scope_keys(cfg.savedvars_dir)
    except TsmAppHelperError as e:
        return {"status": "error", "error": "tsm_apphelper_unavailable", "detail": str(e)}
    return {"status": "success", "count": len(keys), "scope_keys": keys}


@mcp.tool()
async def wow_price_get(item_id: int, source: str = "auto", realm_key: str | None = None) -> dict:
    """
    Get a unit price for an item (copper).

    Sources:
    - auto: TSM (if available) else Auctionator else vendor cache
    - auctionator: Auctionator price database
    - vendor: Auctionator vendor price cache
    - tsm: TradeSkillMaster AppHelper (`dbmarket`) if available
    """
    check_permission("auction")

    cfg = load_env_config()
    source = (source or "auto").lower()

    def vendor() -> dict[str, Any] | None:
        check_source("Auctionator")
        try:
            value = get_vendor_price_copper(cfg.savedvars_dir, item_id)
        except AuctionatorError:
            return None
        if value is None:
            return None
        return {"source": "vendor", "unit_price_copper": value}

    def auctionator() -> dict[str, Any] | None:
        check_source("Auctionator")
        try:
            keys = list_realm_keys(cfg.savedvars_dir)
        except AuctionatorError:
            return None
        selected_realm = realm_key or (keys[0] if keys else None)
        if selected_realm is None:
            return None
        try:
            price = get_auctionator_price(cfg.savedvars_dir, realm_key=selected_realm, db_key=str(item_id))
        except AuctionatorError as e:
            return {"error": "auctionator_error", "detail": str(e)}
        if price is None:
            return None
        return {
            "source": "auctionator",
            "realm_key": selected_realm,
            "db_key": price.db_key,
            "unit_price_copper": price.price_copper,
            "age_days": price.age_days,
        }

    def tsm() -> dict[str, Any] | None:
        check_source("TradeSkillMaster_AppHelper")
        try:
            keys = list_scope_keys(cfg.savedvars_dir)
        except TsmAppHelperError:
            return None
        scope_key = realm_key or (keys[0] if keys else None)
        try:
            price = get_tsm_price_copper(cfg.savedvars_dir, item_id=item_id, price_source="dbmarket", scope_key=scope_key)
        except TsmAppHelperError as e:
            return {"error": "tsm_apphelper_error", "detail": str(e)}
        if price is None:
            return None
        return {
            "source": "tsm",
            "scope_key": price.scope_key,
            "price_source": price.price_source,
            "item_key": price.item_key,
            "unit_price_copper": price.unit_price_copper,
        }

    if source == "vendor":
        try:
            out = vendor()
        except ValueError as e:
            return {"status": "error", "error": "source_disabled", "detail": str(e)}
        return {"status": "success", "item_id": item_id, "price": out} if out else {"status": "error", "error": "no_price"}

    if source == "tsm":
        try:
            out = tsm()
        except ValueError as e:
            return {"status": "error", "error": "source_disabled", "detail": str(e)}
        if out and "error" in out:
            return {"status": "error", **out}
        return {"status": "success", "item_id": item_id, "price": out} if out else {"status": "error", "error": "no_price"}

    if source == "auctionator":
        try:
            out = auctionator()
        except ValueError as e:
            return {"status": "error", "error": "source_disabled", "detail": str(e)}
        if out and "error" in out:
            return {"status": "error", **out}
        return {"status": "success", "item_id": item_id, "price": out} if out else {"status": "error", "error": "no_price"}

    if source == "auto":
        # In auto mode, disabled sources are skipped rather than hard-failing.
        try:
            out = tsm()
        except ValueError:
            out = None
        if out and "error" in out:
            return {"status": "error", **out}
        if out is not None:
            return {"status": "success", "item_id": item_id, "price": out}

        try:
            out = auctionator()
        except ValueError:
            out = None
        if out and "error" in out:
            return {"status": "error", **out}
        if out is not None:
            return {"status": "success", "item_id": item_id, "price": out}

        try:
            out = vendor()
        except ValueError:
            out = None
        return {"status": "success", "item_id": item_id, "price": out} if out else {"status": "error", "error": "no_price"}

    return {"status": "error", "error": "invalid_source", "allowed": ["auto", "auctionator", "vendor", "tsm"]}


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

    valued: list[dict[str, Any]] = []
    for row in items:
        if not isinstance(row, dict):
            continue
        item_id = row.get("item_id")
        count = row.get("count")
        if not isinstance(item_id, int) or not isinstance(count, int):
            continue

        price_payload = await wow_price_get(item_id=item_id, source=price_source, realm_key=realm_key)
        if price_payload.get("status") != "success":
            continue
        price = price_payload.get("price")
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

    valued.sort(key=lambda row: float(row.get("total_value_copper") or 0), reverse=True)
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

    price_cache: dict[int, dict[str, Any] | None] = {}

    async def get_price(item_id: int) -> dict[str, Any] | None:
        if item_id in price_cache:
            return price_cache[item_id]
        price_payload = await wow_price_get(item_id=item_id, source=price_source, realm_key=realm_key)
        if price_payload.get("status") != "success":
            price_cache[item_id] = None
            return None
        price = price_payload.get("price")
        if not isinstance(price, dict):
            price_cache[item_id] = None
            return None
        price_cache[item_id] = price
        return price

    rows: list[dict[str, Any]] = []
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
        source_name: str | None = None
        if isinstance(price, dict):
            unit = price.get("unit_price_copper")
            source_name = price.get("source")

        market_unit: float | int | None = None
        if source_name in {"auctionator", "tsm"} and isinstance(unit, (int, float)):
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
                "price_source": source_name,
                "age_days": price.get("age_days") if isinstance(price, dict) else None,
                "locations": row.get("locations"),
                "action": action,
                "example_link": row.get("example_link"),
            }
        )

    rows.sort(key=lambda row: float(row.get("market_total_value_copper") or 0), reverse=True)
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
            "Prices are best-effort and depend on your latest addon scans.",
        ],
    }


@mcp.tool()
async def wow_tsm_craft_scopes_list() -> dict:
    """List TSM craft scopes present in `TradeSkillMaster.lua`."""
    check_source("TradeSkillMaster")

    cfg = load_env_config()
    try:
        scopes = list_tsm_craft_scopes(cfg.savedvars_dir)
    except TradeSkillMasterError as e:
        return {"status": "error", "error": "tsm_unavailable", "detail": str(e)}
    return {"status": "success", "count": len(scopes), "scopes": scopes}


@mcp.tool()
async def wow_tsm_crafts_list(scope: str | None = None, profession: str | None = None, limit: int = 200) -> dict:
    """List crafts known to TSM (from its scanned profession data)."""
    check_source("TradeSkillMaster")

    cfg = load_env_config()
    try:
        scopes = list_tsm_craft_scopes(cfg.savedvars_dir)
    except TradeSkillMasterError as e:
        return {"status": "error", "error": "tsm_unavailable", "detail": str(e)}
    if not scopes:
        return {"status": "error", "error": "no_tsm_craft_scopes_found"}

    chosen_scope = scope or scopes[0]
    if chosen_scope not in scopes:
        return {"status": "error", "error": "scope_not_found", "scope": chosen_scope, "available": scopes}

    try:
        crafts_raw = load_tsm_crafts(cfg.savedvars_dir, chosen_scope)
    except TradeSkillMasterError as e:
        return {"status": "error", "error": "tsm_crafts_unavailable", "detail": str(e)}

    crafts: list[dict[str, Any]] = []
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
        "scope": chosen_scope,
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
    Suggest profitable crafts using TSM craft data + current inventory.

    Notes:
    - Guidance-only; you still craft and post manually.
    - Profit is best-effort (AH deposit not modeled).
    """
    check_source("TradeSkillMaster")

    cfg = load_env_config()

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
        item_id = row.get("item_id")
        count = row.get("count")
        if isinstance(item_id, int) and isinstance(count, int) and count > 0:
            have_by_id[item_id] = have_by_id.get(item_id, 0) + count

    try:
        scopes = list_tsm_craft_scopes(cfg.savedvars_dir)
    except TradeSkillMasterError as e:
        return {"status": "error", "error": "tsm_unavailable", "detail": str(e)}
    if not scopes:
        return {"status": "error", "error": "no_tsm_craft_scopes_found"}

    chosen_scope = tsm_scope or scopes[0]
    if chosen_scope not in scopes:
        return {"status": "error", "error": "tsm_scope_not_found", "tsm_scope": chosen_scope, "available": scopes}

    try:
        crafts_raw = load_tsm_crafts(cfg.savedvars_dir, chosen_scope)
    except TradeSkillMasterError as e:
        return {"status": "error", "error": "tsm_crafts_unavailable", "detail": str(e)}

    price_cache: dict[int, dict[str, Any] | None] = {}

    async def get_price(item_id: int) -> dict[str, Any] | None:
        if item_id in price_cache:
            return price_cache[item_id]
        payload = await wow_price_get(item_id=item_id, source=price_source, realm_key=realm_key)
        if payload.get("status") != "success":
            price_cache[item_id] = None
            return None
        price = payload.get("price")
        if not isinstance(price, dict):
            price_cache[item_id] = None
            return None
        price_cache[item_id] = price
        return price

    def vendor_price(item_id: int) -> float | None:
        try:
            check_source("Auctionator")
            return get_vendor_price_copper(cfg.savedvars_dir, item_id)
        except (AuctionatorError, ValueError):
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
        "tsm_scope": chosen_scope,
        "price_source": price_source,
        "realm_key": realm_key,
        "count": len(suggestions),
        "suggestions": suggestions,
        "notes": [
            "All actions remain manual (crafting/posting).",
            "TSM crafts come from scanned profession data; open profession windows in-game to refresh.",
        ],
    }


def _apply_config_env(config: dict[str, Any]) -> None:
    savedvars_dir = str(config.get("savedvars_dir") or "").strip()
    scan_root = str(config.get("scan_root") or "").strip()
    if savedvars_dir:
        os.environ["WOW_SAVEDVARS_DIR"] = savedvars_dir
    if scan_root:
        os.environ["WOW_SCAN_ROOT"] = scan_root
    elif savedvars_dir:
        os.environ["WOW_SCAN_ROOT"] = savedvars_dir


def _start_bridge_thread() -> threading.Thread:
    loop = asyncio.new_event_loop()

    def runner() -> None:
        asyncio.set_event_loop(loop)
        loop.run_until_complete(bridge_loop())

    thread = threading.Thread(target=runner, daemon=True, name="wow-mcp-bridge")
    thread.start()
    return thread


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", help="Path to server_config.json")
    parser.add_argument("--bridge-only", action="store_true", help="Run bridge poll loop only (no MCP stdio server)")
    args = parser.parse_args()

    global SERVER_CONFIG
    if args.config and os.path.exists(args.config):
        with open(args.config, "r", encoding="utf-8") as fh:
            SERVER_CONFIG = json.load(fh)
        _apply_config_env(SERVER_CONFIG)
        logger.info("Loaded config from %s", args.config)
    elif args.config:
        logger.warning("Config file does not exist: %s", args.config)
    else:
        logger.info("No config file passed; running with env defaults.")

    # Compatibility mode for desktop companion JSON config.
    if args.bridge_only or (SERVER_CONFIG and SERVER_CONFIG.get("mcp_mode") is False):
        logger.info("Running in bridge-only mode")
        asyncio.run(bridge_loop())
        return

    # In stdio MCP mode we can optionally run bridge in background if config is present.
    if SERVER_CONFIG:
        _start_bridge_thread()
        logger.info("Bridge thread started in background")

    logger.info("Starting WoW MCP Server (stdio)")
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
