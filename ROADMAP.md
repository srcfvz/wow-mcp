# WowMCP Roadmap

The project has pivoted to a **ChatLog Tailing + Clipboard Injection** architecture to eliminate latency and `/reload` dependency.

## Phase 1: Foundation (COMPLETED)
- [x] Initial MCP Server (Python/FastAPI).
- [x] Static SavedVariables parsing (WowMCP_State, Auctionator, Syndicator).
- [x] Basic Lua addon to snapshot character data.

## Phase 2: Python Log Tailer (COMPLETED)
- [x] Implement `bridge/tailer.py` to watch `Logs/WoWChatLog.txt`.
- [x] Map ChatLog events to MCP context (e.g., chat messages, combat log snippets).
- [x] Real-time updates to the bridge from the tailer.

## Phase 3: Lua EditBox & Clipboard Injection (COMPLETED)
- [x] Implement `bridge/clipboard_injector.py` to push Base64 payloads to OS clipboard.
- [x] Implement `addon/WowMCP_State/EditBox.lua` for in-game payload execution.
- [x] Test the "Paste to Execute" workflow (Bridge -> Clipboard -> In-game Paste).

## Phase 4: Integration & UX (COMPLETED)
- [x] Merge the Bridge and MCP Server into a single headless package logic.
- [x] Add auto-detection logic for WoW `Logs` and `SavedVariables` paths.
- [x] Refine the in-game UI (status indicator, ChatLogExporter settings).

## Phase 5: Distribution (COMPLETED)
- [x] Compile the Python Bridge to a standalone Windows `.exe` via PyInstaller.
- [x] User-friendly GUI (`bridge/gui.py`) for API key management and service control.
- [x] Simplified startup via `start-gui.bat` and `build-exe.bat`.
- [x] Final "WowMCP Friends Bundle" for non-technical users.
- [x] CurseForge-ready addon artifact.

## Phase 6: Auth & Free AI Integration (IN PROGRESS)
- [x] Support a default "Free Tier" model out-of-the-box via **GitHub Models** (GPT-4o) and **Groq** (Llama 3.1).
- [x] Expand provider list to include **OpenRouter** (Unified access to all models).
- [ ] Implement an easy "Login with X" flow (OAuth via local redirect) to further eliminate manual token copy-pasting.
