# WowMCP Project Status
_Last updated (UTC): 2026-03-30 08:30:00Z._

## Snapshot
- Release status: TESTING (MVP)
- Target: March 30-31, 2026
- Architecture: **ChatLog Tailing + Clipboard JSON Protocol (WMCP1)**
- Artifacts: Addon updated, Bridge refactored into Core logic.

## 🚀 Recent Changes (Architecture Locked & Implemented)
- [x] **Secure Protocol**: Switched to `WMCP1:` (Base64-encoded JSON) for clipboard injection.
- [x] **Safe Execution**: Addon now enforces an allowlist (`NOTICE`, `WAYPOINT`, `CHAT_RESPONSE`).
- [x] **TomTom Support**: Waypoints from LLM now trigger TomTom markers in-game.
- [x] **Sender Verification**: Bridge now verifies character name before responding to triggers.
- [x] **Bridge Refactoring**: Extracted shared logic into `bridge/core.py` (CLI & GUI share code).
- [x] **Config Persistence**: Fixed settings loss by moving config to user-writable folders.

## 🛠️ Current Status
**MVP Ready for In-Game Testing.**
- Protocol hardened and scoped.
- Trigger detection refined for safety.
- GUI and CLI bridges are synchronized.

## ⚠️ Important Notes for User
- **Windows VM**: The bridge is Windows-ready.
- **Dependencies**: Requires `pyperclip` (and `xclip`/`xsel` on Linux) to bridge to clipboard.
- **WoW Setup**: User must enable `/chatlog` in WoW.
- **Addon**: Updated `EditBox.lua` must be re-installed/re-copied to WoW AddOns folder.

## Next Actions
1. Run a clean smoke test with the `WMCP1` protocol in-game.
2. Verify `WAYPOINT` logic with TomTom.
3. Fix any remaining UI thread safety or path detection edge cases.
4. Prepare final distribution bundle.

## Handoff Log
- 2026-03-28 22:04:55Z: Multi-agent review completed. Highest-risk blockers are dead `WowMCP_Cmd` plumbing, unsafe paste execution, unscoped log triggers, provider/runtime drift, and broken installers. Next agent should start from `../todo/wow-mcp.todo.md` and execute the remediation order there before touching polish or release copy.
- 2026-03-28 22:27:29Z: Recorded the local Bottle/Battle.net WoW install root for future addon pushes and QA. Git for this project lives in `/home/src21/Chat/wow-mcp/.git`; there is still no `origin` remote configured, so GitHub publication remains pending the review checklist in `../todo/github-migration.todo.md`.
