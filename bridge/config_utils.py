import os
import sys
import json
from pathlib import Path

IS_WINDOWS = sys.platform == "win32"
WOW_FLAVOR_DIRS = ["_retail_", "_classic_", "_classic_era_", "_classic_ptr_", "_ptr_"]
WOW_WINDOWS_EXECUTABLES = {"wow.exe", "wowclassic.exe", "world of warcraft launcher.exe"}

def looks_like_wow_install(path_obj):
    if not path_obj or not path_obj.is_dir():
        return False
    if (path_obj / "WTF").is_dir() or (path_obj / "Interface").is_dir():
        return True
    for flavor in WOW_FLAVOR_DIRS:
        flavor_dir = path_obj / flavor
        if flavor_dir.is_dir():
            return True
    for exe_name in WOW_WINDOWS_EXECUTABLES:
        if (path_obj / exe_name).exists():
            return True
    return False

def normalize_wow_candidate(raw_path):
    if not raw_path:
        return None
    try:
        path_obj = Path(str(raw_path).strip().strip('"')).expanduser()
    except Exception:
        return None
    if not str(path_obj):
        return None
    if path_obj.suffix.lower() == ".exe":
        path_obj = path_obj.parent
    if path_obj.name.lower() in WOW_FLAVOR_DIRS:
        path_obj = path_obj.parent
    return path_obj

def collect_registry_wow_paths():
    if not IS_WINDOWS:
        return []
    try:
        import winreg
    except Exception:
        return []

    key_specs = [
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Blizzard Entertainment\World of Warcraft"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Blizzard Entertainment\World of Warcraft"),
        (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Blizzard Entertainment\Battle.net\Launch Options\WoW"),
        (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Blizzard Entertainment\Battle.net\Launch Options\WOW"),
        (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Blizzard Entertainment\Battle.net\Launch Options\wow"),
    ]

    found = []
    for hive, key_path in key_specs:
        try:
            key = winreg.OpenKey(hive, key_path)
        except OSError:
            continue
        try:
            idx = 0
            while True:
                name, value, _val_type = winreg.EnumValue(key, idx)
                idx += 1
                if not isinstance(value, str):
                    continue
                candidate = normalize_wow_candidate(value)
                if candidate and looks_like_wow_install(candidate):
                    found.append((candidate, f"registry:{key_path}:{name}"))
        except OSError:
            pass
        finally:
            try:
                winreg.CloseKey(key)
            except Exception:
                pass
    return found

def collect_common_wow_paths():
    roots = []
    env_candidates = [
        os.environ.get("ProgramFiles(x86)", ""),
        os.environ.get("ProgramFiles", ""),
        os.environ.get("PUBLIC", ""),
    ]
    for base in env_candidates:
        if base:
            roots.append(Path(base))
    roots.extend([Path.home() / "Games", Path("C:/Games"), Path("D:/Games"), Path("E:/Games")])

    path_candidates = []
    for root in roots:
        path_candidates.extend(
            [
                root / "World of Warcraft",
                root / "Battle.net" / "World of Warcraft",
                root / "Blizzard" / "World of Warcraft",
            ]
        )
    # Include direct roots as a safety fallback for unusual installs.
    path_candidates.extend([Path("C:/World of Warcraft"), Path("D:/World of Warcraft"), Path("E:/World of Warcraft")])

    found = []
    for candidate in path_candidates:
        norm = normalize_wow_candidate(candidate)
        if norm and looks_like_wow_install(norm):
            found.append((norm, "common-path"))
    return found

def pick_best_wow_path(candidates):
    scored = []
    for path_obj, source in candidates:
        score = 0
        if (path_obj / "WTF").is_dir():
            score += 2
        if (path_obj / "Interface").is_dir():
            score += 2
        for flavor in WOW_FLAVOR_DIRS:
            flavor_dir = path_obj / flavor
            if flavor_dir.is_dir():
                score += 3
            if (flavor_dir / "WTF").is_dir():
                score += 2
            if (flavor_dir / "Interface").is_dir():
                score += 2
            for exe_name in WOW_WINDOWS_EXECUTABLES:
                if (flavor_dir / exe_name).exists():
                    score += 1
        for exe_name in WOW_WINDOWS_EXECUTABLES:
            if (path_obj / exe_name).exists():
                score += 1
        scored.append((score, str(path_obj), source))
    if not scored:
        return None
    scored.sort(key=lambda item: (item[0], item[1].lower()), reverse=True)
    best_score, best_path, _ = scored[0]
    if best_score <= 0:
        return None
    return best_path

def detect_wow_path():
    candidate_map = {}
    for path_obj, source in collect_registry_wow_paths():
        candidate_map[str(path_obj).lower()] = (path_obj, source)
    for path_obj, source in collect_common_wow_paths():
        candidate_map.setdefault(str(path_obj).lower(), (path_obj, source))
    return pick_best_wow_path(candidate_map.values())

def detect_savedvars_dir(wow_path):
    if not wow_path:
        return None, None

    roots = [wow_path]
    for flavor in WOW_FLAVOR_DIRS:
        roots.append(os.path.join(wow_path, flavor))

    candidates = []
    for root in roots:
        wtf = os.path.join(root, "WTF", "Account")
        if not os.path.isdir(wtf):
            continue
        for account in os.listdir(wtf):
            sv = os.path.join(wtf, account, "SavedVariables")
            if os.path.isdir(sv):
                try:
                    mtime = os.path.getmtime(sv)
                except Exception:
                    mtime = 0
                candidates.append((mtime, sv, root))

    if not candidates:
        return None, None

    candidates.sort(key=lambda t: t[0], reverse=True)
    _, savedvars_dir, scan_root = candidates[0]
    return savedvars_dir, scan_root

def parse_addon_toc(toc_path):
    title = None
    version = None
    try:
        raw = toc_path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return (None, None)

    for line in raw.splitlines():
        line = line.strip()
        if not line.startswith("##") or ":" not in line:
            continue
        key, value = line[2:].split(":", 1)
        key = key.strip().lower()
        value = value.strip()
        if key == "title" and title is None:
            title = value
        elif key == "version" and version is None:
            version = value
        if title is not None and version is not None:
            break
    return (title, version)

def detect_addons_from_scan_root(scan_root):
    if not scan_root:
        return {}
    root = Path(scan_root).expanduser()
    if not root.is_dir():
        return {}

    addons_dir_candidates = [
        root / "Interface" / "AddOns",
        root / "AddOns",
    ]
    if root.name.lower() == "addons":
        addons_dir_candidates.insert(0, root)

    addons_dir = None
    for candidate in addons_dir_candidates:
        if candidate.is_dir():
            addons_dir = candidate
            break

    if addons_dir is None:
        try:
            for interface_dir in root.rglob("Interface"):
                if not interface_dir.is_dir():
                    continue
                maybe_addons = interface_dir / "AddOns"
                if maybe_addons.is_dir():
                    addons_dir = maybe_addons
                    break
        except Exception:
            addons_dir = None

    if addons_dir is None:
        return {}

    found = {}
    try:
        entries = sorted(addons_dir.iterdir(), key=lambda p: p.name.lower())
    except Exception:
        return {}

    for addon_dir in entries:
        if not addon_dir.is_dir() or addon_dir.name in {".git", ".svn"}:
            continue
        toc_files = sorted(addon_dir.glob("*.toc"), key=lambda p: p.name.lower())
        title = None
        version = None
        if toc_files:
            title, version = parse_addon_toc(toc_files[0])
        found[addon_dir.name] = {
            "title": title,
            "version": version,
            "path": str(addon_dir),
        }
    return found
