# WowMCP - World of Warcraft Model Context Protocol
Status: abandoned — I stopped playing. The MCP server worked: I used it from Codex CLI to query my inventory and Auctionator prices. It reads WoW's SavedVariables files, which the game only writes on /reload or logout, so data was only as fresh as the last /reload (I kept a macro for it). The in-game !ai flow below was started but never finished.
WowMCP connects your World of Warcraft experience with AI (LLMs) to provide real-time assistance, inventory analysis, and more.

## 🚀 Quick Start (Windows Users)

1.  **Install the Addon:**
    *   Copy the `addon/WowMCP_State` folder to your `World of Warcraft/_retail_/Interface/AddOns/` directory.
    *   Log into WoW and ensure the addon is enabled.
2.  **Start the Bridge:**
    *   **Option A (Recommended): Standalone EXE**
        *   If you have the `WowMcpBridge.exe` (found in `dist/` after running `build-exe.bat`), just double-click it.
    *   **Option B: Python Script**
        *   Double-click `start-gui.bat` in this folder (requires Python installed).
3.  **In-Game Setup:**
    *   Type `/chatlog` in your WoW chat to enable log recording (required for the bridge to see your messages).
    *   Type `/wmcpbox` to open the addon's interaction window.

## 🛠️ Build Standalone EXE (Developer/Advanced)

If you want to create a standalone `.exe` for your friends or yourself (no Python required on the target machine):
1.  Double-click `build-exe.bat`.
2.  Wait for the process to finish.
3.  Find your app in `dist/WowMcpBridge.exe`.

## 🎮 In-game flow (unfinished — never worked end-to-end)

*   **Ask AI:** Type `!ai <your question>` in any chat channel (Say, Party, Guild).
    *   *Example:* `!ai What are the best items in my bags?`
*   **Get Response:** 
    1.  The Bridge will detect your message and call the AI.
    2.  The response will be copied to your **Clipboard** automatically.
    3.  Open the `/wmcpbox` window in WoW.
    4.  Press **Ctrl+V** (Paste) and then **Enter**.
    5.  The AI's response will appear in your chat or as a helpful notification.

## 🛠️ Configuration

The Bridge GUI allows you to choose between providers:
*   **OpenAI:** (Default) Requires an API Key.
*   **Anthropic:** Requires a Claude API Key.
*   **Ollama:** For local AI (no API key needed, requires Ollama running).

## ⚠️ Important Notes
*   **Latency:** This version uses "ChatLog Tailing" for near-instant responses without needing to reload your UI.
*   **Safety:** The addon follows Blizzard's TOS and will never perform "protected" actions like automation or botting.

---
*WowMCP v0.3.0 - March 2026*
