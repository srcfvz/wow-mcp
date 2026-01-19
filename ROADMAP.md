# WoW MCP Roadmap
_Last updated (UTC): 2026-01-14 23:55:46Z._

## Phase 0 — Repo Skeleton (✅)
- Canonical docs triad exists: `AGENTS.md`, `ROADMAP.md`, `STATUS.md`.
- Minimal repo layout in place:
  - `mcp-server/` (Python MCP server)
  - `bridge/` (placeholder)
  - `addon/` (placeholder)

## Phase 1 — MCP Server (Python + Docker) (✅)
- MCP server (stdio) exposes tools:
  - `wow_config_get`, `wow_state_get`, `wow_cmd_write`, `wow_paths_probe`
- Docker packaging present (`mcp-server/Dockerfile`) + local entrypoint (`start.sh`).
- Unit tests cover SavedVariables parsing + atomic write (`mcp-server/tests/test_savedvars.py`).
- Implemented addon integrations (read-only):
  - Inventory via `Syndicator.lua` (Baganator/Syndicator cache)
  - Pricing via `Auctionator.lua` (CBOR price database + vendor cache)

## Phase 2 — Local Bridge (Poll/inotify) (⏳)
- File watcher that:
  - Tracks `WowMCP_State.lua` changes → normalized JSON
  - Writes `WowMCP_Cmd.lua` safely (atomic writes)
  - Maintains a “freshness” timestamp and `last_seen_revision`
- Optional: read WoW chat/combat logs for higher-frequency signals (if enabled).

## Phase 3 — WoW Addon (Sensor/UI) (⏳)
- Collect snapshots (inventory, quest log, money, location) and expose via:
  - `WowMCP_State` (table) and/or `WowMCP_StateJSON` (string)
- Consume “soft commands” (`WowMCP_Cmd`) and render in-game UI:
  - suggested quest order, vendor list, clickable buttons (non-protected)
- Throttle updates and avoid UI lag.

## Phase 4 — Advice Layer (Heuristics) (⏳)
- Local-only heuristics:
  - quest ordering + travel clustering
  - vendor / keep / AH suggestions (no protected automation) (✅ initial: `wow_liquidation_plan`)
  - crafting profitability suggestions from TSM craft cache (✅ initial: `wow_crafting_suggestions`)
- Later: optional external pricing sources (explicitly opt-in).

## Non-negotiables (always)
- No protected automation, no botting, no injection/memory read.
- Primary transport is file-based; user remains in control of in-game actions.
