from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SavedVarsCandidate:
    savedvars_dir: Path
    state_file: Path
    cmd_file: Path


def probe_savedvars_candidates(
    *,
    scan_root: Path,
    state_filename: str = "WowMCP_State.lua",
    cmd_filename: str = "WowMCP_Cmd.lua",
    max_depth: int = 9,
) -> list[SavedVarsCandidate]:
    """
    Scan for WoW account SavedVariables folders that contain our addon state file.

    Safety: scanning is constrained to `scan_root` and `max_depth`.
    """
    scan_root = scan_root.resolve()
    candidates: list[SavedVarsCandidate] = []

    root_depth = len(scan_root.parts)
    for dirpath, dirnames, filenames in os.walk(scan_root):
        current = Path(dirpath)
        depth = len(current.parts) - root_depth
        if depth > max_depth:
            dirnames[:] = []
            continue

        if state_filename not in filenames:
            continue

        savedvars_dir = current
        candidates.append(
            SavedVarsCandidate(
                savedvars_dir=savedvars_dir,
                state_file=savedvars_dir / state_filename,
                cmd_file=savedvars_dir / cmd_filename,
            )
        )

    candidates.sort(key=lambda c: str(c.savedvars_dir))
    return candidates
