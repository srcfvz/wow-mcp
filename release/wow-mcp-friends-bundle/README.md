# WowMCP Friends Bundle (WoW AddOn + MCP server)
_Last updated (UTC): 2026-01-15 22:02:28Z._

## What this is
World of Warcraft addons cannot do networking. This bundle uses SavedVariables as a safe file bridge:
- `WowMCP_State` addon writes a snapshot to `WTF/Account/<ACCOUNT>/SavedVariables/WowMCP_State.lua`
- `WowMCP_Cmd` addon reads commands from `WowMCP_Cmd.lua` and shows non-protected UI hints (chat/popup, optional waypoint)
- The MCP server runs outside WoW (Docker) and exposes tools like `wow_state_get`, `wow_inventory_get`, `wow_price_get`, `wow_cmd_write`

Safety: no protected-action automation (no casting/buying/posting). You still click/do actions manually.
Liquidation is guidance-only: keep profession tools by default (e.g., fishing pole) unless you explicitly want to sell.

## What it can and cannot do (important)
### Can do (safe)
- Read state from SavedVariables (quests, location, money, talents/skills; inventory/prices/crafts via other addons).
- Show in-game UI hints: chat/popup notifications, checklists, and (optionally) waypoints via TomTom.
- Prepare actions for you to do: “sell these on AH”, “craft these”, “go to X then do Y”.
- (Optional future) Draft messages (pre-fill chat box) that you send manually.

### Cannot do (and we won’t add)
- No botting: no movement, no combat rotation, no targeting, no interacting with NPCs/objects, no auto-loot.
- No economy automation: no auto-buy/sell, no auto-mail, no auto-auctions/posting/canceling.
- No networking from the addon; no memory reading/injection; no simulated input tricks.

## “In-game ChatGPT” UX: what’s realistic
Because WoW addons can’t do networking and can’t read arbitrary files while the game is running, there is no fully real-time “chat inside WoW” using only addons + a local MCP server.

What you can do instead:
- **Best-safe option:** a small always-on-top overlay window (outside WoW) that talks to the MCP server. It feels in-game (no alt-tab), but it’s technically an overlay, not a WoW UI frame.
- **All-in-WoW (but clunky):** type questions in-game, have a bridge write the reply into `WowMCP_Cmd.lua`, then you do `/reload` to load and display the answer in the `Codex` tab/panel.

## 0) Unzip
Extract this folder anywhere (avoid Program Files if your shell needs write access).

## 1) Install the AddOn
### Windows (auto)
1) Open PowerShell (Run as Administrator if needed).
2) In the extracted folder, run:
   - `powershell -ExecutionPolicy Bypass -File .\\install-addon-windows.ps1`
3) In WoW: enable `WowMCP State` (+ `WowMCP Cmd`), then `/reload`.
4) If it shows \"Out of date\", tick \"Load out of date AddOns\" (depends on client version).

### Manual install (any OS)
Copy these folders into your WoW AddOns directory:
- `addon/WowMCP_State` -> `<WOW>\\<FLAVOR>\\Interface\\AddOns\\WowMCP_State`
- `addon/WowMCP_Cmd` -> `<WOW>\\<FLAVOR>\\Interface\\AddOns\\WowMCP_Cmd`

Typical flavor folders:
- Classic/TBC: `_classic_`
- Classic Era: `_classic_era_`
- Retail: `_retail_`

## 2) Run the MCP server (Docker)
Prereqs: Docker Engine (Linux) or Docker Desktop (Windows).

1) Copy `.env.example` to `.env` and set at least:
   - `WOW_SAVEDVARS_DIR_HOST=".../WTF/Account/<ACCOUNT>/SavedVariables"`
   - Optional: `WOW_SCAN_ROOT_HOST=".../World of Warcraft/_classic_"` (enables addon listing / probing)
2) Build the image:
   - `docker compose build wow-mcp`
3) Run (stdio MCP server):
   - Linux/macOS/WSL: `./start.sh`
   - Windows PowerShell: `powershell -ExecutionPolicy Bypass -File .\\start-windows.ps1`

## 3) Configure your MCP client
This MCP server speaks stdio. Configure your client to spawn it and talk stdio.

Conceptually:
- Command: run `start.sh` (Linux/WSL) or `start-windows.ps1` (Windows)
- Working directory: this extracted folder

If your client supports per-server env vars, you can set `WOW_SAVEDVARS_DIR_HOST` there instead of `.env`.

## Refresh rules (super important)
- SavedVariables flush reliably on `/reload` and logout; not real-time.
- Inventory comes from Syndicator cache; open bags/bank, then `/reload`.
- Prices come from Auctionator; run a scan, then `/reload`.
- Crafts come from TSM scanned profession data; open profession windows, then `/reload`.

## Troubleshooting
- If `wow_state_get` shows stale data, do `/reload` in-game.
- If inventory/prices are missing, ensure Syndicator/Auctionator are installed and have data.
- If Docker can't mount your path on Windows, check Docker Desktop \"File Sharing\" settings.
