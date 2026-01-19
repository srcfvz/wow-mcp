# WoW MCP Status
_Last updated (UTC): 2026-01-14 23:55:46Z._

## Snapshot
- Implemented: Dockerized MCP server (stdio) that reads `WowMCP_State.lua` and writes `WowMCP_Cmd.lua`.
- Local entrypoint: `start.sh` runs container with `--network none` (file-only bridge).
- Parser/writer: `mcp-server/wow_mcp_server/savedvars.py` (Lua SavedVariables subset; supports tables/strings/numbers/bools/nil).
- Tests: `python3 -m unittest discover -s tests -p 'test_*.py' -v` from `mcp-server/`.
- Working today (no custom addon needed):
  - Inventory snapshot via `Syndicator.lua` (`wow_inventory_get`, `wow_inventory_value`)
  - Pricing via `Auctionator.lua` (`wow_price_get`, `wow_auctionator_realms_list`) + vendor buy cache
  - Optional pricing via `TradeSkillMaster_AppHelper.lua` (`wow_price_get source=tsm`, `wow_tsm_scopes_list`) if TSM Desktop App is installed
  - Liquidation guidance via `wow_liquidation_plan` (manual actions only)
  - Crafting profitability suggestions via TSM craft cache (`wow_crafting_suggestions`, `wow_tsm_craft_scopes_list`)
- Still pending: quest log export + richer state (needs a small custom addon, or deeper parsing of Questie).

## Next Actions
1. Implement quest log export (prefer custom addon) and add MCP tools to query active quests.
2. Add a proper TSM AppHelper decoder if your `TradeSkillMaster_AppHelper.lua` uses encoded `data` strings (right now we only support simple table shapes).
3. Add end-to-end smoke check (Syndicator/Auctionator/TSM → MCP → advice) and then (optional) add WowMCP addon for richer state.

## Handoff Log
- _2026-01-14 15:56Z:_ Created `ROADMAP.md` + `STATUS.md` and aligned scope with workspace rules.
- _2026-01-14 22:24Z:_ Added MCP server + Docker entrypoint + SavedVariables parser/tests; documented runbook in `AGENTS.md`.
- _2026-01-14 23:29Z:_ Added read-only integrations for Syndicator inventory + Auctionator pricing and exposed MCP tools with a source toggle.
- _2026-01-14 23:55Z:_ Added TSM craft parsing + liquidation/crafting suggestion tools; added optional TSM AppHelper pricing stub; `start.sh` now sources `.env`.
