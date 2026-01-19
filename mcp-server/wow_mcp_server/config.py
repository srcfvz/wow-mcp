from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path


@dataclass(frozen=True)
class WowMcpConfig:
    savedvars_dir: Path
    state_file: Path
    cmd_file: Path
    state_var: str
    cmd_var: str
    scan_root: Path
    probe_max_depth: int


def load_config(env: dict[str, str] | None = None) -> WowMcpConfig:
    env = env or os.environ

    savedvars_dir = Path(env.get("WOW_SAVEDVARS_DIR", "/wow/SavedVariables"))
    state_filename = env.get("WOW_STATE_FILE", "WowMCP_State.lua")
    cmd_filename = env.get("WOW_CMD_FILE", "WowMCP_Cmd.lua")

    state_var = env.get("WOW_STATE_VAR", "WowMCP_State")
    cmd_var = env.get("WOW_CMD_VAR", "WowMCP_Cmd")

    scan_root = Path(env.get("WOW_SCAN_ROOT", str(savedvars_dir)))
    probe_max_depth = int(env.get("WOW_PROBE_MAX_DEPTH", "9"))

    return WowMcpConfig(
        savedvars_dir=savedvars_dir,
        state_file=savedvars_dir / state_filename,
        cmd_file=savedvars_dir / cmd_filename,
        state_var=state_var,
        cmd_var=cmd_var,
        scan_root=scan_root,
        probe_max_depth=probe_max_depth,
    )
