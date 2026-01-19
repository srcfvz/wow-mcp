from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class AddonInfo:
    name: str
    path: Path
    toc_path: Path | None
    title: str | None
    version: str | None


def _parse_toc_meta(toc_path: Path) -> tuple[str | None, str | None]:
    title: str | None = None
    version: str | None = None

    try:
        raw = toc_path.read_text(encoding="utf-8", errors="replace")
    except FileNotFoundError:
        return (None, None)

    for line in raw.splitlines():
        line = line.strip()
        if not line.startswith("##"):
            continue
        # Examples:
        # ## Title: Auctionator
        # ## Version: 10.1.2
        if ":" not in line:
            continue
        key, val = line[2:].split(":", 1)
        key = key.strip().lower()
        val = val.strip()
        if key == "title" and title is None:
            title = val
        if key == "version" and version is None:
            version = val
        if title is not None and version is not None:
            break

    return (title, version)


def find_addons_dir(scan_root: Path) -> Path | None:
    """
    Best-effort discovery of the WoW AddOns directory from a scan root.

    Supports passing:
    - the game root (contains Interface/AddOns)
    - Interface/
    - Interface/AddOns/
    """
    candidates = [
        scan_root / "Interface" / "AddOns",
        scan_root / "AddOns",
        scan_root / "Interface" / "AddOns".lower(),
    ]
    for c in candidates:
        if c.is_dir():
            return c
    # Heuristic: search a few levels deep for Interface/AddOns
    for p in scan_root.rglob("Interface"):
        if not p.is_dir():
            continue
        c = p / "AddOns"
        if c.is_dir():
            return c
    return None


def iter_installed_addons(addons_dir: Path) -> Iterable[AddonInfo]:
    for entry in sorted(addons_dir.iterdir(), key=lambda p: p.name.lower()):
        if not entry.is_dir():
            continue
        # Ignore common non-addon folders.
        if entry.name in {".git", ".svn"}:
            continue

        toc_files = sorted(entry.glob("*.toc"), key=lambda p: p.name.lower())
        toc_path = toc_files[0] if toc_files else None
        title, version = (None, None)
        if toc_path is not None:
            title, version = _parse_toc_meta(toc_path)
        yield AddonInfo(
            name=entry.name,
            path=entry,
            toc_path=toc_path,
            title=title,
            version=version,
        )

