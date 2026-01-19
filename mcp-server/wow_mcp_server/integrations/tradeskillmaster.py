from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Any, Iterable

from ..savedvars import LuaParseError, load_var


TSM_FILENAME = "TradeSkillMaster.lua"
TSM_DB_VAR = "TradeSkillMasterDB"

_CRAFTS_KEY_RE = re.compile(r"^f@(?P<scope>.+)@internalData@crafts$")


class TradeSkillMasterError(RuntimeError):
    pass


@dataclass(frozen=True)
class TsmCraft:
    craft_key: str
    name: str
    profession: str
    output_item_id: int
    output_item_string: str
    num_result: int
    mats: dict[int, int]
    mats_item_strings: dict[str, int]
    has_cooldown: bool | None
    players: list[str]


def _item_id_from_item_string(item_string: str) -> int | None:
    """
    Parse a TSM item string into an item ID.

    Supported (common) shapes:
    - "i:12345"
    - "item:12345"
    """
    if not isinstance(item_string, str) or not item_string:
        return None
    if item_string.isdigit():
        return int(item_string)
    prefix, _, rest = item_string.partition(":")
    if prefix not in {"i", "item"}:
        return None
    head, _, _tail = rest.partition(":")
    if head.isdigit():
        return int(head)
    return None


def load_tsm_db(savedvars_dir: Path) -> dict[str, Any]:
    path = savedvars_dir / TSM_FILENAME
    if not path.exists():
        raise TradeSkillMasterError(f"Missing {TSM_FILENAME} in {savedvars_dir}")
    try:
        db = load_var(path, TSM_DB_VAR)
    except (LuaParseError, KeyError) as e:
        raise TradeSkillMasterError(str(e)) from e
    if not isinstance(db, dict):
        raise TradeSkillMasterError(f"Unexpected {TSM_DB_VAR} type: {type(db).__name__}")
    return db


def list_craft_scopes(savedvars_dir: Path) -> list[str]:
    """
    List craft scopes (faction-realm keys) that have an `internalData@crafts` table.

    Example: "Horde - Thunderstrike"
    """
    db = load_tsm_db(savedvars_dir)
    scopes: set[str] = set()
    for key in db.keys():
        if not isinstance(key, str):
            continue
        m = _CRAFTS_KEY_RE.match(key)
        if m:
            scopes.add(m.group("scope"))
    out = sorted(scopes)
    return out


def load_crafts(savedvars_dir: Path, scope: str) -> dict[str, Any]:
    db = load_tsm_db(savedvars_dir)
    key = f"f@{scope}@internalData@crafts"
    crafts = db.get(key)
    if not isinstance(crafts, dict):
        raise TradeSkillMasterError(f"Missing crafts table: {key}")
    return crafts


def iter_crafts(crafts: dict[str, Any]) -> Iterable[TsmCraft]:
    for craft_key, raw in crafts.items():
        if not isinstance(craft_key, str) or not isinstance(raw, dict):
            continue
        name = raw.get("name")
        profession = raw.get("profession")
        output_item_string = raw.get("itemString")
        num_result = raw.get("numResult")
        mats_raw = raw.get("mats")

        if not isinstance(name, str) or not isinstance(profession, str) or not isinstance(output_item_string, str):
            continue
        output_item_id = _item_id_from_item_string(output_item_string)
        if output_item_id is None or not isinstance(num_result, int) or num_result <= 0:
            continue
        if not isinstance(mats_raw, dict) or not mats_raw:
            continue

        mats_item_strings: dict[str, int] = {}
        mats: dict[int, int] = {}
        for mk, mv in mats_raw.items():
            if not isinstance(mk, str) or not isinstance(mv, int) or mv <= 0:
                continue
            mats_item_strings[mk] = mv
            mid = _item_id_from_item_string(mk)
            if mid is not None:
                mats[mid] = mats.get(mid, 0) + mv

        if not mats:
            continue

        players: list[str] = []
        players_raw = raw.get("players")
        if isinstance(players_raw, dict):
            players = [k for k in players_raw.keys() if isinstance(k, str)]
            players.sort()

        has_cd = raw.get("hasCD") if isinstance(raw.get("hasCD"), bool) else None

        yield TsmCraft(
            craft_key=craft_key,
            name=name,
            profession=profession,
            output_item_id=output_item_id,
            output_item_string=output_item_string,
            num_result=num_result,
            mats=mats,
            mats_item_strings=mats_item_strings,
            has_cooldown=has_cd,
            players=players,
        )

