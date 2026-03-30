# WowMCP Remediation Plan
_Last updated (UTC): 2026-03-30 06:16:51Z._

## Goal
Convert the 2026-03-30 review into one safe, internally consistent runtime path that the next agent can execute without re-opening architecture drift.

## Review Findings To Resolve
1. The reload-based reply path is broken because the addon no longer declares `WowMCP_Cmd`, while the server still writes replies there.
2. The clipboard path is unsafe because pasted payloads can execute arbitrary slash commands.
3. Chat triggers are unscoped and currently fire on any log line containing `!ai` / `!wmcp`.
4. The standalone EXE does not have a stable config storage path, so settings are likely lost between launches.
5. The Tk GUI updates widgets from the worker thread, which risks crashes/freezes under real traffic.
6. `bridge/main.py` tells users to set `WOW_PATH`, but path detection never reads that override.

## Architecture Lock
### Recommended release path
Ship one canonical path only:

`tagged in-game trigger -> chat log tailer -> bridge -> safe clipboard payload -> manual paste into WowMCP edit box`

### Fallback if the clipboard path slips
Restore `WowMCP_Cmd` as an explicit SavedVariable and ship the reload-based roundtrip honestly, but do not keep both user-facing paths active at the same time.

### Non-negotiable rules
- One payload envelope.
- One trigger format.
- One startup path per distribution target.
- No raw slash-command execution from model output.
- No protected-action automation and no docs that imply otherwise.

## Execution Order
### Phase 0: Stop the drift first
- [ ] Confirm the canonical release path before touching runtime code. Recommended: keep the chatlog/clipboard/manual-paste path.
- [ ] Treat the reload-based `WowMCP_Cmd` path as either `experimental` or `removed` in docs and startup flows until it is fully restored.
- [ ] Freeze user-facing copy until the chosen path passes a real smoke test.

### Phase 1: Harden the clipboard contract
- [ ] Replace the raw `WMCP:<base64(text)>` format with a structured envelope, for example `WMCP1:<base64(json)>`.
- [ ] Require fields: `version`, `id`, `type`, and `payload`.
- [ ] Allow only weekend-safe types in `EditBox.lua`: `NOTICE`, `CHAT_RESPONSE`, and `WAYPOINT`.
- [ ] Remove the `decoded starts with "/"` execution path entirely.
- [ ] Add max payload length checks and either chunking or hard failure messaging for oversized replies.
- [ ] Mirror the same allowlist in the Python bridge helpers so unsafe types never reach the clipboard.

### Phase 2: Scope and verify triggers
- [ ] Make `ChatLogExporter.lua` emit one deterministic tagged format for requests instead of relying on free-form substring search.
- [ ] Parse only messages authored by the local player or an explicit tagged slash-command path.
- [ ] Include enough metadata in the tag to reject unrelated chat lines and replayed content.
- [ ] Add unit tests for trigger parsing and malformed-input rejection.

### Phase 3: Converge the bridge runtimes
- [ ] Extract shared bridge logic so `bridge/main.py` and `bridge/gui.py` stop maintaining separate trigger, provider, and clipboard flows.
- [ ] Add a real `WOW_PATH` env/config override to `config_utils.detect_wow_path()`.
- [ ] Move GUI config persistence to a stable user-writable path, not next to `__file__` in a PyInstaller onefile extraction directory.
- [ ] Marshal all Tk log/status updates back onto the main thread via `root.after(...)`.
- [ ] Decide whether the MCP server should launch the bridge in stdio mode. If not, stop claiming that merged mode exists.

### Phase 4: Resolve the dead reload contract
- [ ] If the clipboard path remains canonical, remove or clearly quarantine `WowMCP_Cmd` references from the default runtime, docs, installers, and MCP helpers.
- [ ] If the reload path becomes the fallback release path, restore it fully by declaring `WowMCP_Cmd` in addon SavedVariables, aligning server defaults, and documenting `/reload` as required.
- [ ] Do not leave the repo in the current half-and-half state.

### Phase 5: Packaging and documentation truth pass
- [ ] Align root README, release bundle README, startup scripts, and addon README to the same architecture.
- [ ] Remove claims that the EXE is the recommended path until config persistence is fixed.
- [ ] Remove claims that replies "execute as a command" unless the new envelope explicitly supports and constrains that behavior.
- [ ] Update version strings only after runtime behavior is stable.

### Phase 6: Verification gate
- [ ] Add bridge/addon tests for payload parsing, type allowlisting, trigger scoping, and `WOW_PATH` override behavior.
- [ ] Add a packaging test or checklist for persistent config location in the standalone build.
- [ ] Run `python -m unittest discover -s tests -q` from `mcp-server/`.
- [ ] Run one real Windows smoke test for the chosen release path before any public publish.
- [ ] Verify failure modes: missing `/chatlog`, missing TomTom, missing clipboard provider, bad payload, and disabled WoW path auto-detection.

## Suggested Ownership Split
### Addon + protocol
- Files: `addon/WowMCP_State/EditBox.lua`, `addon/WowMCP_State/ChatLogExporter.lua`, `addon/WowMCP_State/WowMCP_State.lua`, `addon/WowMCP_State/WowMCP_State.toc`
- Goal: one safe trigger format and one safe paste protocol

### Bridge + GUI runtime
- Files: `bridge/main.py`, `bridge/gui.py`, `bridge/clipboard_injector.py`, `bridge/config_utils.py`, `bridge/config_manager.py`, `bridge/tailer.py`
- Goal: shared bridge core, stable settings, real path override, thread-safe UI

### MCP server + packaging
- Files: `mcp-server/wow_mcp_server/server.py`, `mcp-server/wow_mcp_server/config.py`, `README.md`, `release/wow-mcp-friends-bundle/README.md`, `start-gui.bat`, `build-exe.bat`, `release/wow-mcp-friends-bundle/start-windows.ps1`
- Goal: remove dead modes, align startup scripts, and keep docs honest

## Acceptance Criteria
- The chosen runtime path works end-to-end without hidden fallback assumptions.
- There is no raw slash-command execution path from clipboard/model output.
- Trigger parsing is scoped tightly enough that random public chat cannot fire the bridge.
- Windows users have one documented startup path that matches reality.
- `STATUS.md`, this plan, and release docs all describe the same supported behavior.

## Cut Line
If the clipboard path cannot be made safe and scoped in one pass, stop advertising it as the release path. Either ship the reload-based path honestly after restoring it fully, or pause release work instead of keeping both paths half-alive.
