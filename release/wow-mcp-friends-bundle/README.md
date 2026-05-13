# WowMCP Friends Bundle (March 2026)

Welcome to the early release of WowMCP! This is a WoW companion that uses LLMs to help you with your game data.

## 🚀 How it Works (New Low-Latency Mode)
1.  **Chat Tailing**: The bridge reads your WoW Chat Logs in real-time.
2.  **AI Context**: It looks at your SavedVariables (inventory, etc.) for context.
3.  **Clipboard Injection**: AI responses are put directly into your OS clipboard.
4.  **Paste & Execute**: You paste the response back into WoW via a simple in-game box.

## ⚙️ Quick Setup
1.  **Install Addon**: Copy `addon/WowMCP_State` to your `Interface/AddOns` folder.
2.  **Enable Logs**: Log into WoW and type `/chatlog`. (Important!)
3.  **Configure AI**: 
    -   Set your API key: `setx WOW_MCP_API_KEY "your-key-here"` (Windows)
    -   (Optional) Set provider: `setx WOW_MCP_PROVIDER "openai"` (default)
4.  **Start Bridge**: Run `start-windows.ps1` (Right-click -> Run with PowerShell).

## 🎮 Using it in-game
-   **Trigger**: Type something starting with `!ai ` in chat.
    -   Example: `/say !ai what's the most valuable item in my bags?`
-   **Wait**: Give it 1-3 seconds.
-   **Paste**: Type `/wmcpbox` (or use a hotkey) and press `Ctrl+V`.
-   **See Result**: The AI response appears in your chat frame or executes as a command.

## ⚠️ Requirements
-   Windows 10/11
-   Python 3.11+ (if running from source)
-   `pyperclip` installed (`pip install pyperclip`)
-   `/chatlog` enabled in WoW

## 🛡️ Safety
WowMCP **never** performs protected actions. It only reads logs and writes to your clipboard. You are the one who pastes and hits enter.
