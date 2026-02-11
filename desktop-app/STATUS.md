# WowMCP Desktop App Status
_Last updated (UTC): 2026-02-11 17:08:17Z._

## Phase 1: Prototype (GUI & Core)
- [x] Create directory structure.
- [x] Define dependencies (`requirements.txt`).
- [x] Implement basic GUI skeleton (`customtkinter`).
- [x] Implement System Tray integration (`pystray`).
- [x] Secure API Key storage (`keyring`).
- [x] **Feature: API Selector** (Dropdown for OpenAI, Anthropic, Gemini, Local/Ollama).
- [x] **Feature: Data Permissions Tab** (Toggles for Inventory, Chat, Quests, Combat, AH).
- [x] **Feature: MCP Server Mode** (Checkbox to expose stdio/SSE for external clients like Claude Desktop).
- [x] **Feature: Local History** (Toggle + JSON/SQLite storage implementation).
- [x] Implement Server Process Management (`subprocess` spawn/kill with permission flags).
- [x] Implement SavedVariables auto-detection (from WoW path).
- [x] Implement always-on-top Overlay Chat + tray toggle + Windows hotkey (`Ctrl+Shift+F8`).
- [x] Implement WoW Path auto-detection (registry + common-path fallback on Windows).
- [x] Implement Data Sources tab (addon detection from `scan_root` + persisted checkboxes).
- [x] Minor UI cleanups (tray status checks + safer early logging + deep-merge config defaults).

## Phase 2: Integration
- [x] Connect GUI start button to actual `mcp-server` python script, passing the config.
- [x] Implement the "Bridge" logic (reads `WowMCP_State.chat.outbox` -> writes `WowMCP_Cmd`).
- [x] Bundle `mcp-server` logic into the exe (PyInstaller `pathex` includes `mcp-server/`).

## Phase 3: Packaging
- [x] Create PyInstaller spec file (`wow_mcp.spec`).
- [x] Create Build Script (`build_windows.bat`).
- [ ] Create Inno Setup script (Install Daemon + Copy Addon).
