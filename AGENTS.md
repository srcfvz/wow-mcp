# AGENTS.md — WoW Addon + Bridge + MCP (Codex CLI)
_Last updated (UTC): 2026-01-14 23:55:46Z._

## Goal
Build a **World of Warcraft “AI bridge”** that lets Codex CLI query in-game character state (quests, inventory, gold, etc.) and send **non-protected** UI commands back into the game.

Key rule: **WoW addons cannot do networking**. The MCP server runs outside the game. The addon is a sandboxed sensor/UI.

Deliverables:
1) WoW Addon (Lua) that exports state + receives “soft commands”
2) Local Bridge (external app) that reads addon outputs and writes commands
3) MCP Server that exposes tools to Codex CLI

---

## Non-negotiable constraints
- **No automation of protected actions** (casting, buying, posting auctions, accepting quests automatically, etc.). The addon may only **guide** and **prepare UI**, user still clicks.
- **No memory reading / injection / botting**. Do not propose ban-risk methods.
- Primary data transport should be **SavedVariables** (safe, file-based). Optionally read WoW logs for extra signals.
- Must support running on Linux (user uses Nobara/Fedora-ish). Favor **Docker** where reasonable.
- Reminder: SavedVariables are reliably flushed to disk on `/reload` and logout; don’t expect true real-time state without a log-based channel.

---

## Architecture (high-level)
### A) WoW Addon (Lua)
Responsibilities:
- Collect data snapshots (character, bags, quest log, money, profs if available).
- Store snapshot into SavedVariables as a compact table.
- Read commands (also from SavedVariables) and render them in-game:
  - show “next quests”
  - mark items to vendor/AH
  - create clickable UI buttons for user actions
  - optional: set waypoints using the map API (if available for the WoW version)

Data channels:
- `SavedVariables`: `WowMCP_State` and `WowMCP_Cmd`
- Event-driven updates: `PLAYER_LOGIN`, `BAG_UPDATE`, `QUEST_LOG_UPDATE`, `PLAYER_MONEY`, etc.
- Throttle snapshot writes (avoid UI lag)

### B) Local Bridge (outside WoW)
Responsibilities:
- Read SavedVariables file(s)
- Convert to clean JSON state for MCP server
- Accept command JSON from MCP server and write to `WowMCP_Cmd` SavedVariables
- Provide a “freshness” timestamp and ensure idempotency

Transport:
- File watcher preferred (inotify) but simple polling is OK.

### C) MCP Server
Responsibilities:
- Expose tools to Codex CLI
- Maintain the latest parsed `wow_state`
- Provide “advice” logic (quest ordering, vendor list, AH suggestions) using local heuristics + optional external pricing sources later

---

## Repo layout (recommended)
```
wow-mcp/
├── AGENTS.md
├── ROADMAP.md
├── STATUS.md
├── docker-compose.yml
├── start.sh                    # MCP entrypoint (docker, stdio)
├── mcp-server/                 # Python MCP server (Docker build context)
│   ├── Dockerfile
│   ├── pyproject.toml
│   ├── wow_mcp_server/
│   └── tests/
├── addon/                      # WoW addon (Lua) — TBD
└── bridge/                     # Optional bridge daemon — TBD
```

---

## Dev / Runbook (current)

### Prereqs
- Docker + `docker compose`
- Your WoW SavedVariables folder path on the host

### Quickstart (stdio MCP server)
1) Build the local image:
   - `docker compose build wow-mcp`
2) Point the server at your account SavedVariables directory:
   - Recommended: create `wow-mcp/.env` (gitignored) with:
     - `WOW_SAVEDVARS_DIR_HOST="/path/.../WTF/Account/<ACCOUNT>/SavedVariables"`
     - `WOW_SCAN_ROOT_HOST="/path/.../World of Warcraft/_anniversary_"` (game root; enables `wow_addons_list`)
   - Or export directly:
     - `export WOW_SAVEDVARS_DIR_HOST='/path/.../WTF/Account/<ACCOUNT>/SavedVariables'`
     - `export WOW_SCAN_ROOT_HOST='/path/.../World of Warcraft/_anniversary_'`
3) Run the MCP server (stdio):
   - `./start.sh`
4) In Codex CLI, configure an MCP server command that executes `./start.sh` (the client spawns it and speaks stdio).

### Environment variables (host-side)
- `WOW_SAVEDVARS_DIR_HOST` (required): host path mounted to `/wow/SavedVariables` in the container.
- `WOW_SCAN_ROOT_HOST` (optional): host path mounted read-only to `/wow/scan` for `wow_paths_probe` (defaults to `WOW_SAVEDVARS_DIR_HOST`).
- Optional overrides:
  - `WOW_STATE_FILE` (default `WowMCP_State.lua`)
  - `WOW_STATE_VAR` (default `WowMCP_State`)
  - `WOW_CMD_FILE` (default `WowMCP_Cmd.lua`)
  - `WOW_CMD_VAR` (default `WowMCP_Cmd`)
  - `WOW_PROBE_MAX_DEPTH` (default `9`)

### Safety notes
- `start.sh` runs the container with `--network none` (file-only bridge).
- SavedVariables update cadence depends on WoW flushing (`/reload` / logout).

---

## MCP Tools (current)
- `wow_config_get`: returns resolved paths and variable names from env.
- `wow_state_get`: parses the SavedVariables state table and returns `{status, meta, state}`.
- `wow_cmd_write`: writes a “soft command” envelope into `WowMCP_Cmd.lua` (addon consumes on next load).
- `wow_paths_probe`: scans `WOW_SCAN_ROOT` for candidate SavedVariables dirs containing the addon state file.
- `wow_sources_detect`: detects which supported data sources exist in mounted SavedVariables (Syndicator/Auctionator/TSM/etc).
- `wow_addons_list`: lists installed addons from `Interface/AddOns` under `WOW_SCAN_ROOT`.
- `wow_characters_list`: lists characters known to Syndicator.
- `wow_inventory_get`: returns aggregated inventory snapshot from Syndicator (bags + optional bank).
- `wow_inventory_value`: values inventory items using `wow_price_get` and returns top-N by total value.
- `wow_auctionator_realms_list`: lists Auctionator realm/faction keys in `AUCTIONATOR_PRICE_DATABASE`.
- `wow_tsm_scopes_list`: lists scope keys inside `TradeSkillMaster_AppHelper.lua` (TSM Desktop App integration).
- `wow_tsm_craft_scopes_list`: lists craft scopes inside `TradeSkillMaster.lua` (TSM scanned profession data).
- `wow_tsm_crafts_list`: lists crafts from TSM scanned profession data.
- `wow_price_get`: gets unit price (copper) from `tsm` / `auctionator` / `vendor` / `auto` (toggle).
- `wow_liquidation_plan`: suggests what to sell on AH vs keep/vendor (manual actions only).
- `wow_crafting_suggestions`: suggests profitable crafts from your inventory using TSM craft data + prices (manual actions only).

### Notes on supported addons (Classic Anniversary)
- Inventory: `Syndicator` (installed via Baganator) provides a cached bag/bank snapshot per character.
- Pricing:
  - Auctionator: decodes `AUCTIONATOR_PRICE_DATABASE` CBOR blob (no Desktop App needed).
  - TSM AppHelper (optional): requires TSM Desktop App to write `TradeSkillMaster_AppHelper.lua` (enables `source=tsm`).
- Crafting:
  - TSM addon stores scanned craft recipes in `TradeSkillMaster.lua` and can be used for crafting suggestions without Desktop App.
  - If crafts look stale/missing, open profession windows in-game (TSM refreshes its internal craft cache).
