# WowMCP Agents & Architecture
_Last updated (UTC): 2026-03-27 13:01:10Z._

Cross-reference: `ROADMAP.md`, `STATUS.md`, `../todo/wow-mcp.todo.md`.

## Workspace Todo Intake
Before changing this repo from `/home/srcfvz/Chat`, read these in order:
1. `../AGENTS.md`
2. `../todo/AGENTS.md`
3. `../todo/wow-mcp.todo.md`
4. This file, then `STATUS.md`, then `ROADMAP.md`

Treat `../todo/wow-mcp.todo.md` as the operational backlog until the March 28-29, 2026 release window closes.

## Snapshot
- Target architecture: ChatLog tailing for low-latency request triggers plus SavedVariables for bulk snapshots such as inventory, prices, and crafts.
- Current state: the repo is mid-pivot; legacy reload-based chat code and release docs still coexist with new bridge scaffolding.
- Release priority: accurate, safe, Windows-first release quality suitable for a public CurseForge listing.
- Safety rule: never implement or market protected-action automation.

## Data Flows

### Data OUT (WoW -> MCP)
1. **Real-time (Chat/Combat):** Handled via `WoWChatLog.txt` tailing. The WoW client writes logs to disk, and the Bridge (Python) tails them to provide instant context to the LLM.
2. **Bulk Sync (Inventory/Prices):** Handled via `SavedVariables` (WowMCP_State, Syndicator, Auctionator, TSM). These are used for snapshotting complex state that isn't streamed in logs.

### Data IN (MCP -> WoW)
1. **Payload Generation:** The Bridge receives a command from the MCP Server (e.g., a TomTom waypoint or a chat reply).
2. **Clipboard Injection:** The Bridge encodes the payload (Base64) and copies it to the OS Clipboard.
3. **In-Game Input:** The user pastes the payload into a dedicated in-game EditBox (WowMCP_State). The addon decodes the payload and executes the Lua command.

## Core Components

### 1. WoW Addon (addon/WowMCP_State)
- `WowMCP_State.lua`: Manages the snapshotting of character data (Inventory, Quests, Stats).
- `ChatLogExporter.lua`: Ensures specific events are printed to the chat log for the tailer to pick up.
- `EditBox.lua`: A hidden/toggleable UI element that listens for pasted Base64 strings to execute commands.

### 2. Bridge Daemon & GUI (bridge/)
- `gui.py`: Tkinter-based user interface for API key management, provider selection (OpenAI, Anthropic, Gemini, Ollama), and bridge control.
- `main.py`: Headless bridge logic. Detects WoW paths, monitors logs, and communicates with LLMs.
- `config_manager.py`: Manages `config.json` for persistent user settings.
- `tailer.py`: Watches `Logs/WoWChatLog.txt`. Parses events in real-time.
- `clipboard_injector.py`: Interfaces with the OS clipboard to push payloads for the user to paste.

### 3. Distribution Tools
- `start-gui.bat`: One-click startup for Windows users (installs dependencies and runs the GUI).
- `build-exe.bat`: Automated build script for creating a standalone `WowMcpBridge.exe` using PyInstaller.

### 4. MCP Server (mcp-server/)
- Standard MCP Server that exposes tools to the LLM.
- Interfaces with the Bridge via stdio or HTTP (depending on deployment).

## Working Rules
- Prefer removing ambiguity over preserving abandoned flows.
- Keep release docs, bundle docs, startup scripts, and the actual runtime architecture aligned.
- Use `STATUS.md` for short session notes; keep the multi-phase execution plan in `../todo/wow-mcp.todo.md`.
