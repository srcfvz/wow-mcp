# WowMCP Implementation Log
_Last updated (UTC): 2026-02-11 17:21:38Z._

## Goal
Deliver a production-ready WoW MCP flow for Windows users:
- Desktop GUI companion for easy setup and API key management.
- One-click startup via `start-gui.bat`.
- Zero-latency ChatLog tailing and clipboard injection.
- Addon-data source detection and toggles.

## Process
1.  **GUI Implementation**: Created `bridge/gui.py` using Tkinter for maximum Windows compatibility without heavy dependencies.
2.  **Config Management**: Implemented `bridge/config_manager.py` to handle `config.json` for persistence.
3.  **Data Sources UI**: Added dynamic addon scanning to the GUI using `config_utils.detect_addons_from_scan_root()`. The GUI now displays checkboxes for supported addons (Syndicator, Auctionator, TSM) and saves user preferences.
4.  **Windows Integration**: Created `start-gui.bat` to automate dependency installation (`pyperclip`) and launch the GUI.
5.  **UX Polish**: Added real-time log tailing and status indicators in the GUI.
6.  **Documentation**: Created a new top-level `README.md` focusing on the GUI workflow for end-users.

## Main Changes
- `mcp-server/wow_mcp_server/server.py`
  - Restored full MCP tool coverage.
  - Kept bridge chat loop and fixed replay persistence in error path.
  - Added source-toggle enforcement (`data_sources`) and permission checks.
  - Preserved compatibility modes for bridge-only and stdio runs.
- `desktop-app/main.py`
  - Added Windows WoW path auto-detection (registry + common paths).
  - Added `Data Sources` tab with addon discovery and per-source checkboxes.
  - Persisted source selection in config.
  - Cleaned tray/server-state and minor dead code.
- `desktop-app/backend_interface.py`
  - Included `data_sources` in generated server config.
  - Removed unused import.
- `desktop-app/wow_mcp_installer.iss`
  - Added Inno Setup definition for app install + bundled addon payload + optional addon install step.
- `addon/WowMCP_State/WowMCP_State.lua`
  - Bumped release quality to `0.2.0`.
  - Added richer slash command UX and safer reload behavior.
  - Added command safety blocking for protected-action envelopes.
  - Added outbox/history bounds and text sanitation.
- `addon/WowMCP_State/WowMCP_State.toc`
- `addon/WowMCP_Cmd/WowMCP_Cmd.toc`
- `addon/README.md`

## Validation Commands
- `python3 -m py_compile mcp-server/wow_mcp_server/server.py`
- `python3 -m py_compile desktop-app/main.py desktop-app/backend_interface.py`
- `cd mcp-server && python3 -m unittest discover -s tests -p 'test_*.py' -v`
- `luac -p addon/WowMCP_State/WowMCP_State.lua`

## Known Remaining Work
- Add end-to-end automated smoke test for reload-based chat roundtrip.
- Expand TSM AppHelper decoding for encoded `data` shapes.
- Validate installer behavior on clean Windows VMs and add optional code-signing.

## Generated Artifact
- `artifacts/wowmcp-addon-0.2.0.zip`
