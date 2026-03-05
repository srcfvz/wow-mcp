# WoW MCP Roadmap
_Last updated (UTC): 2026-03-05 16:19:09Z._

## Phase 0 — Repo Skeleton (✅)
- Canonical docs triad exists: `AGENTS.md`, `ROADMAP.md`, `STATUS.md`.
- Minimal repo layout in place:
  - `mcp-server/` (Python MCP server)
  - `bridge/` (placeholder)
  - `addon/` (placeholder)

## Phase 1 — MCP Server (Python + Docker) (✅)
- MCP server (stdio) exposes full toolset:
  - config/state/cmd/path tools: `wow_config_get`, `wow_state_get`, `wow_cmd_write`, `wow_paths_probe`
  - discovery/inventory/pricing/crafting tools: `wow_sources_detect`, `wow_addons_list`, `wow_characters_list`, `wow_inventory_get`, `wow_inventory_value`, `wow_auctionator_realms_list`, `wow_tsm_scopes_list`, `wow_price_get`, `wow_liquidation_plan`, `wow_tsm_craft_scopes_list`, `wow_tsm_crafts_list`, `wow_crafting_suggestions`
- Docker packaging present (`mcp-server/Dockerfile`) + local entrypoint (`start.sh`).
- Unit tests cover SavedVariables parsing + atomic write (`mcp-server/tests/test_savedvars.py`).
- Implemented addon integrations (read-only):
  - Inventory via `Syndicator.lua` (Baganator/Syndicator cache)
  - Pricing via `Auctionator.lua` (CBOR price database + vendor cache)

## Phase 2 — Local Bridge (Poll/inotify) (✅)
- File watcher that:
  - Tracks `WowMCP_State.lua` changes → normalized JSON
  - Writes `WowMCP_Cmd.lua` safely (atomic writes)
  - Maintains a `last_processed_seq` state and avoids replay storms after errors
- Optional: read WoW chat/combat logs for higher-frequency signals (if enabled).

## Phase 3 — WoW Addon (Sensor/UI) (✅)
- Collect snapshots (inventory, quest log, money, location) and expose via:
  - `WowMCP_State` (table) and/or `WowMCP_StateJSON` (string)
- Consume “soft commands” (`WowMCP_Cmd`) and render in-game UI:
  - suggested quest order, vendor list, clickable buttons (non-protected)
  - reload-based chat panel (`/wowmcp chat`) + command UX polish + safety hardening (`v0.2.0`)
- Throttle updates and avoid UI lag.

## Phase 4 — Advice Layer (Heuristics) (🚧)
- Local-only heuristics:
  - quest ordering + travel clustering
  - vendor / keep / AH suggestions (no protected automation) (✅ initial: `wow_liquidation_plan`)
  - crafting profitability suggestions from TSM craft cache (✅ initial: `wow_crafting_suggestions`)
- Later: optional external pricing sources (explicitly opt-in).

## Phase 5 — Windows Desktop Distribution (🚧)
- Desktop companion (`desktop-app/`) now includes:
  - WoW path auto-detect (Windows registry + common-path fallback)
  - `Data Sources` tab with addon detection and per-source toggles
  - secure API key storage + overlay chat + bridge process management
  - Inno Setup installer script (`desktop-app/wow_mcp_installer.iss`) wired into `build_windows.bat`
- Remaining packaging tasks:
  - optional code-signing and installer QA matrix

## Phase 6 — CurseForge Release Readiness (🚧)
- Release is intentionally gated by pre-release testing.
- Required before first upload:
  - complete E2E chat bridge smoke test on live addon flow
  - validate encoded `TradeSkillMaster_AppHelper.lua` payload decoding
  - validate installer behavior on a clean Windows VM
  - produce CurseForge-ready addon archive layout (`WowMCP_State/`, `WowMCP_Cmd/` at archive root)
  - confirm TOC/flavor strategy against target WoW client variants

## Non-negotiables (always)
- No protected automation, no botting, no injection/memory read.
- Primary transport is file-based; user remains in control of in-game actions.
