from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from ..savedvars import LuaParseError, load_var


TSM_APPHELPER_FILENAME = "TradeSkillMaster_AppHelper.lua"
TSM_APPHELPER_DB_VARS: tuple[str, ...] = (
    "TradeSkillMaster_AppHelperDB",
    "TradeSkillMaster_AppHelper",
)


class TsmAppHelperError(RuntimeError):
    pass


@dataclass(frozen=True)
class TsmPrice:
    scope_key: str | None
    price_source: str
    item_key: str
    unit_price_copper: int


def load_tsm_apphelper_db(savedvars_dir: Path) -> tuple[dict[str, Any], str]:
    path = savedvars_dir / TSM_APPHELPER_FILENAME
    if not path.exists():
        raise TsmAppHelperError(f"Missing {TSM_APPHELPER_FILENAME} in {savedvars_dir}")

    last_error: Exception | None = None
    for var in TSM_APPHELPER_DB_VARS:
        try:
            data = load_var(path, var)
        except KeyError as e:
            last_error = e
            continue
        except LuaParseError as e:
            raise TsmAppHelperError(str(e)) from e
        if isinstance(data, dict):
            return data, var
        last_error = TypeError(f"Unexpected {var} type: {type(data).__name__}")

    detail = str(last_error) if last_error else "No supported variable found"
    raise TsmAppHelperError(detail)


def list_scope_keys(savedvars_dir: Path) -> list[str]:
    """
    List available scope keys within the AppHelper DB.

    Note: TSM uses different scopes depending on game version:
    - `factionrealm` (common)
    - `realm`
    - `region`
    """
    db, _var = load_tsm_apphelper_db(savedvars_dir)
    out: set[str] = set()
    for scope in ("factionrealm", "realm", "region"):
        node = db.get(scope)
        if isinstance(node, dict):
            out.update(k for k in node.keys() if isinstance(k, str))
    keys = sorted(out)
    return keys


def _item_key_candidates(item_id: int) -> list[str]:
    # TSM commonly uses compact item strings (e.g. "i:12345").
    return [
        str(item_id),
        f"i:{item_id}",
        f"item:{item_id}",
    ]


def _coerce_price_copper(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return None


def _iter_price_maps(node: Any, *, price_source: str, max_nodes: int = 50_000) -> Iterable[dict[str, Any]]:
    """
    Yield candidate price maps for a specific price source.

    Supported shapes (best-effort, version-dependent):
    - {"dbmarket": { "i:123": 456, ... }}
    - {"prices": {"dbmarket": { ... }}}
    - nested under `factionrealm` / `realm` / `region`
    """
    stack: list[Any] = [node]
    seen: set[int] = set()
    visited = 0

    while stack:
        current = stack.pop()
        visited += 1
        if visited > max_nodes:
            return
        if not isinstance(current, dict):
            continue
        oid = id(current)
        if oid in seen:
            continue
        seen.add(oid)

        direct = current.get(price_source)
        if isinstance(direct, dict):
            yield direct

        prices = current.get("prices")
        if isinstance(prices, dict):
            nested = prices.get(price_source)
            if isinstance(nested, dict):
                yield nested

        stack.extend(v for v in current.values() if isinstance(v, dict))


def get_price_copper(
    savedvars_dir: Path,
    *,
    item_id: int,
    price_source: str = "dbmarket",
    scope_key: str | None = None,
) -> TsmPrice | None:
    """
    Best-effort retrieval of a TSM price from `TradeSkillMaster_AppHelper.lua`.

    This intentionally supports only simple table-based shapes. If your AppHelper DB uses
    a compressed/encoded `data` string, this will return None (we'll need a decoder).
    """
    db, _var = load_tsm_apphelper_db(savedvars_dir)
    candidates = _item_key_candidates(item_id)

    # If a scope key is provided, search inside it first.
    if scope_key is not None:
        for scope in ("factionrealm", "realm", "region"):
            node = db.get(scope)
            if not isinstance(node, dict):
                continue
            scoped = node.get(scope_key)
            if isinstance(scoped, dict):
                for price_map in _iter_price_maps(scoped, price_source=price_source):
                    for item_key in candidates:
                        v = _coerce_price_copper(price_map.get(item_key))
                        if v is not None:
                            return TsmPrice(
                                scope_key=scope_key,
                                price_source=price_source,
                                item_key=item_key,
                                unit_price_copper=v,
                            )

    # Fallback: scan whole DB for explicit per-item price tables.
    for price_map in _iter_price_maps(db, price_source=price_source):
        for item_key in candidates:
            v = _coerce_price_copper(price_map.get(item_key))
            if v is not None:
                return TsmPrice(
                    scope_key=None,
                    price_source=price_source,
                    item_key=item_key,
                    unit_price_copper=v,
                )

    return None

