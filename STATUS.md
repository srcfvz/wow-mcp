# WoW MCP Status
_Last updated (UTC): 2026-02-21 04:22:43Z._

## Snapshot
- Implemented: Dockerized MCP server (stdio) + desktop bridge mode with full MCP tool surface restored.
- Local entrypoint: `start.sh` runs container with `--network none` (file-only bridge).
- Parser/writer: `mcp-server/wow_mcp_server/savedvars.py` (Lua SavedVariables subset; supports tables/strings/numbers/bools/nil).
- Tests: `python3 -m unittest discover -s tests -p 'test_*.py' -v` from `mcp-server/`.
- Working today (no custom addon needed):
  - Inventory snapshot via `Syndicator.lua` (`wow_inventory_get`, `wow_inventory_value`)
  - Pricing via `Auctionator.lua` (`wow_price_get`, `wow_auctionator_realms_list`) + vendor buy cache
  - Optional pricing via `TradeSkillMaster_AppHelper.lua` (`wow_price_get source=tsm`, `wow_tsm_scopes_list`) if TSM Desktop App is installed
  - Liquidation guidance via `wow_liquidation_plan` (manual actions only)
  - Crafting profitability suggestions via TSM craft cache (`wow_crafting_suggestions`, `wow_tsm_craft_scopes_list`)
- Added: `WowMCP_State` in-game chat panel (`/wowmcp chat`) with reload-based request/response via `WowMCP_Cmd`.
- Added: Desktop companion overlay chat (always-on-top) + Windows hotkey toggle (`Ctrl+Shift+F8`).
- Added: desktop `Data Sources` tab with addon auto-detection and persisted per-source toggles.
- Added: addon polish release `v0.2.0` (bounded outbox/history, richer slash commands, combat-safe reload guard, protected-command blocking).
- Built addon release artifact: `artifacts/wowmcp-addon-0.2.0.zip`.

## QA / Bug Checks
- Python compile checks:
  - `python3 -m py_compile mcp-server/wow_mcp_server/server.py`
  - `python3 -m py_compile desktop-app/main.py desktop-app/backend_interface.py`
- Lua syntax check:
  - `luac -p addon/WowMCP_State/WowMCP_State.lua`
- Unit tests:
  - `cd mcp-server && python3 -m unittest discover -s tests -p 'test_*.py' -v` (all passing)

## Next Actions
1. Add end-to-end smoke test for chat bridge (`/wowmcp chat` → bridge → `CHAT_RESPONSE` replay in-game).
2. Add a proper decoder for encoded `TradeSkillMaster_AppHelper.lua` payload variants.
3. Validate generated Inno installer on a clean Windows VM and add optional code-signing.
4. (Optional) Add log-based signal ingestion for faster local telemetry without violating addon constraints.

_Times in this log are expressed in UTC._
## Handoff Log
- _2026-01-14 15:56Z:_ Created `ROADMAP.md` + `STATUS.md` and aligned scope with workspace rules.
- _2026-01-14 22:24Z:_ Added MCP server + Docker entrypoint + SavedVariables parser/tests; documented runbook in `AGENTS.md`.
- _2026-01-14 23:29Z:_ Added read-only integrations for Syndicator inventory + Auctionator pricing and exposed MCP tools with a source toggle.
- _2026-01-14 23:55Z:_ Added TSM craft parsing + liquidation/crafting suggestion tools; added optional TSM AppHelper pricing stub; `start.sh` now sources `.env`.
- _2026-02-06 21:44Z:_ Added reload-based in-game chat panel + bridge support for `WowMCP_State.chat.outbox` → `CHAT_RESPONSE`.
- _2026-02-11 17:17Z:_ Restored full MCP tool coverage in `server.py`, added source-toggle enforcement, fixed bridge replay persistence on error, completed desktop addon-source detection tab, and polished addon UX/safety (`v0.2.0`).
- _2026-02-11 17:21Z:_ Added Inno Setup installer script (`desktop-app/wow_mcp_installer.iss`) and integrated optional installer build step into `desktop-app/build_windows.bat`.
