# WowMCP Desktop App (Prototype)
_Last updated (UTC): 2026-02-11 17:20:53Z._

This is the Python-based GUI dashboard for the WoW-MCP bridge (provider + permissions + secure API key storage).

It runs a small local “bridge daemon” that watches your `SavedVariables/WowMCP_State.lua` (written on `/reload` / logout) and writes replies into `SavedVariables/WowMCP_Cmd.lua`.

## Features
- **Privacy First**: Granular toggles for Inventory, Chat, Combat Log access.
- **Provider Agnostic**: Switch between OpenAI, Anthropic, Gemini, or Local LLMs.
- **Secure**: API Keys stored in OS Keychain (Windows Credential Manager / Gnome Keyring).
- **Background Service**: Runs in System Tray.
- **Overlay Chat**: Always-on-top overlay you can toggle (Windows hotkey: `Ctrl+Shift+F8`).
- **Windows Auto-Detection**: Detects WoW install path from registry and common install locations.
- **Data Sources Tab**: Detects installed addons from `scan_root` and lets you enable/disable each source.
- **MCP Mode Guardrail**: If MCP mode is enabled, the UI avoids starting bridge-daemon mode and shows guidance for external stdio clients.

## In-game chat UX (important limitation)
WoW addons can’t do networking and SavedVariables flush to disk reliably only on `/reload` and logout. So the in-game chat panel is **reload-based**:
- In WoW, open the panel with `/wowmcp chat`
- Type and hit **Send (Reload)** (it triggers `ReloadUI()` to flush the request to disk)
- The desktop app detects the request and writes a response into `WowMCP_Cmd.lua`
- On that reload, the addon processes the response and shows it in the panel

## Overlay Chat (recommended UX)
The overlay gives you “real-time” chat without forcing `/reload` for every message. It does not change WoW gameplay: it’s just an always-on-top window.

## Dev Setup

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Run the app:
   ```bash
   python main.py
   ```

## Building for Windows

Use the provided script (recommended): `build_windows.bat` (uses `wow_mcp.spec`).

- Builds `dist/WowMCP.exe` with PyInstaller.
- If Inno Setup Compiler (`ISCC`) is available, also builds `dist/WowMCP-Setup.exe` from `wow_mcp_installer.iss`.
