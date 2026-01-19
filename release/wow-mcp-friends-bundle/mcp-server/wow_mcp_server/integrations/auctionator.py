from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..cbor import CborDecodeError, loads as cbor_loads
from ..savedvars import LuaParseError, load_var


AUCTIONATOR_FILENAME = "Auctionator.lua"
AUCTIONATOR_PRICE_DB_VAR = "AUCTIONATOR_PRICE_DATABASE"
AUCTIONATOR_VENDOR_CACHE_VAR = "AUCTIONATOR_VENDOR_PRICE_CACHE"

_SCAN_DAY_0_UTC = datetime(2020, 1, 1, tzinfo=timezone.utc)


class AuctionatorError(RuntimeError):
    pass


@dataclass(frozen=True)
class AuctionatorPrice:
    db_key: str
    price_copper: int
    age_days: int | None


@dataclass(frozen=True)
class _RealmCacheEntry:
    mtime_ns: int
    realm_key: str
    db: dict[str, Any]


_realm_cache: dict[tuple[str, str], _RealmCacheEntry] = {}


def _scan_day_now() -> int:
    now = datetime.now(timezone.utc)
    return int((now - _SCAN_DAY_0_UTC).total_seconds() // 86400)


def _decode_cbor_blob(blob: str) -> Any:
    try:
        payload = blob.encode("latin-1")
    except UnicodeEncodeError as e:
        raise AuctionatorError(f"Failed to encode blob as latin-1: {e}") from e
    try:
        return cbor_loads(payload)
    except CborDecodeError as e:
        raise AuctionatorError(f"CBOR decode failed: {e}") from e


def _load_vars(savedvars_dir: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    path = savedvars_dir / AUCTIONATOR_FILENAME
    if not path.exists():
        raise AuctionatorError(f"Missing {AUCTIONATOR_FILENAME} in {savedvars_dir}")

    try:
        price_db = load_var(path, AUCTIONATOR_PRICE_DB_VAR)
        vendor_cache = load_var(path, AUCTIONATOR_VENDOR_CACHE_VAR)
    except (LuaParseError, KeyError) as e:
        raise AuctionatorError(str(e)) from e

    if not isinstance(price_db, dict) or not isinstance(vendor_cache, dict):
        raise AuctionatorError("Unexpected Auctionator savedvars shape")

    return price_db, vendor_cache


def list_realm_keys(savedvars_dir: Path) -> list[str]:
    price_db, _ = _load_vars(savedvars_dir)
    keys = [k for k in price_db.keys() if isinstance(k, str) and k != "__dbversion"]
    keys.sort()
    return keys


def load_realm_db(savedvars_dir: Path, realm_key: str) -> dict[str, Any]:
    path = savedvars_dir / AUCTIONATOR_FILENAME
    mtime_ns = path.stat().st_mtime_ns

    cache_key = (str(savedvars_dir), realm_key)
    cached = _realm_cache.get(cache_key)
    if cached is not None and cached.mtime_ns == mtime_ns:
        return cached.db

    price_db, _ = _load_vars(savedvars_dir)
    raw = price_db.get(realm_key)
    if raw is None:
        raise AuctionatorError(f"Realm key not found: {realm_key!r}")
    if not isinstance(raw, str):
        raise AuctionatorError(f"Unexpected realm db type: {type(raw).__name__}")

    decoded = _decode_cbor_blob(raw)
    if not isinstance(decoded, dict):
        raise AuctionatorError(f"Unexpected decoded realm db type: {type(decoded).__name__}")

    _realm_cache[cache_key] = _RealmCacheEntry(mtime_ns=mtime_ns, realm_key=realm_key, db=decoded)
    return decoded


def get_vendor_price_copper(savedvars_dir: Path, item_id: int) -> float | None:
    _, vendor_cache = _load_vars(savedvars_dir)
    v = vendor_cache.get(str(item_id))
    if isinstance(v, (int, float)):
        return float(v)
    return None


def get_auctionator_price(
    savedvars_dir: Path,
    *,
    realm_key: str,
    db_key: str,
) -> AuctionatorPrice | None:
    db = load_realm_db(savedvars_dir, realm_key)
    entry = db.get(db_key)
    if entry is None:
        # Auctionator uses CBOR byte-string keys for db keys.
        try:
            entry = db.get(db_key.encode("ascii"))
        except UnicodeEncodeError:
            entry = None
    if not isinstance(entry, dict):
        return None

    price = entry.get("m")
    if price is None:
        price = entry.get(b"m")
    if not isinstance(price, int):
        return None

    age_days: int | None = None
    history_h = entry.get("h")
    if history_h is None:
        history_h = entry.get(b"h")
    if isinstance(history_h, dict) and history_h:
        day_keys: list[int] = []
        for k in history_h.keys():
            if isinstance(k, str) and k.isdigit():
                day_keys.append(int(k))
            elif isinstance(k, (bytes, bytearray)):
                try:
                    ks = bytes(k).decode("ascii")
                except UnicodeDecodeError:
                    continue
                if ks.isdigit():
                    day_keys.append(int(ks))
        if day_keys:
            age_days = _scan_day_now() - max(day_keys)

    return AuctionatorPrice(db_key=db_key, price_copper=price, age_days=age_days)
