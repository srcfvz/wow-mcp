import os
import sys
import json
import base64
import time
import threading
import urllib.request
from pathlib import Path
from typing import Any, Callable, Dict, Optional

# Add mcp-server to path so we can import its logic
sys.path.append(str(Path(__file__).parent.parent / "mcp-server"))

from tailer import ChatLogTailer
from clipboard_injector import inject_to_clipboard
import config_utils
from wow_mcp_server.savedvars import load_var, LuaParseError
from wow_mcp_server.bridge_helpers import normalize_provider, summarize_state_for_prompt

# --- Configuration ---
# You can set these via environment variables or a config file later.
API_KEY = os.environ.get("WOW_MCP_API_KEY")
LLM_PROVIDER = os.environ.get("WOW_MCP_PROVIDER", "openai")
LLM_MODEL = os.environ.get("WOW_MCP_MODEL", "")

def _http_post_json(url: str, headers: dict, payload: dict, timeout_s: float = 45.0) -> dict:
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers={**headers, "Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=timeout_s) as resp:
        raw = resp.read()
    return json.loads(raw.decode("utf-8", errors="replace"))

def call_llm(prompt: str, context: str) -> str:
    provider = normalize_provider(LLM_PROVIDER)
    system_prompt = (
        "You are a helpful WoW assistant. Keep answers short (max 2 sentences). "
        "Never suggest botting or protected-action automation.\n"
        f"Context:\n{context}"
    )
    
    if provider == "ollama":
        url = os.environ.get("OLLAMA_HOST", "http://localhost:11434") + "/api/chat"
        payload = {
            "model": LLM_MODEL or "llama3.1",
            "stream": False,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
        }
        try:
            data = _http_post_json(url, {}, payload)
            return data.get("message", {}).get("content", "").strip()
        except Exception as e:
            return f"Error calling Ollama: {e}"

    if not API_KEY:
        return "Error: WOW_MCP_API_KEY not set."

    if provider == "openai":
        url = "https://api.openai.com/v1/chat/completions"
        payload = {
            "model": LLM_MODEL or "gpt-4o-mini",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.2,
        }
        try:
            data = _http_post_json(url, {"Authorization": f"Bearer {API_KEY}"}, payload)
            return data.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
        except Exception as e:
            return f"Error calling OpenAI: {e}"

    return f"Error: Unsupported provider {provider}"

class WowBridge:
    def __init__(self):
        self.wow_path = None
        self.log_file = None
        self.savedvars_dir = None
        self.scan_root = None
        self.last_state = {}

    def setup(self):
        print("[*] Detecting WoW installation...")
        self.wow_path = config_utils.detect_wow_path()
        if not self.wow_path:
            print("[!] Could not find WoW automatically. Please set WOW_PATH env var.")
            return False
        
        print(f"[*] Found WoW at: {self.wow_path}")
        self.savedvars_dir, self.scan_root = config_utils.detect_savedvars_dir(self.wow_path)
        
        # Detect Log file
        flavors = ["_retail_", "_classic_", "_classic_era_", "_ptr_"]
        for flavor in flavors:
            candidate = Path(self.wow_path) / flavor / "Logs" / "WoWChatLog.txt"
            if candidate.exists():
                self.log_file = str(candidate)
                break
        
        if not self.log_file:
            print("[!] Could not find WoWChatLog.txt. Ensure /chatlog is enabled in-game.")
            return False
            
        print(f"[*] Monitoring log: {self.log_file}")
        print(f"[*] Using SavedVariables from: {self.savedvars_dir}")
        return True

    def get_context(self) -> str:
        if not self.savedvars_dir:
            return "No SavedVariables found."
        
        state_file = Path(self.savedvars_dir) / "WowMCP_State.lua"
        if not state_file.exists():
            return "WowMCP_State.lua missing. Run /reload in-game."
        
        try:
            state = load_var(state_file, "WowMCP_State")
            # We assume permissions for inventory and quests are granted for the bridge
            perms = {"inventory": True, "quests": True}
            return summarize_state_for_prompt(state, perms)
        except Exception as e:
            return f"Error loading state: {e}"

    def handle_log_line(self, line: str):
        # WoW log format usually: "3/27 13:45:00.000  [Say] [Character]: message"
        # Simple trigger detection: look for "!ai " or "WowMCP "
        trigger = None
        if "!ai " in line:
            trigger = "!ai "
        elif "!wmcp " in line:
            trigger = "!wmcp "
        
        if trigger:
            parts = line.split(trigger, 1)
            if len(parts) > 1:
                prompt = parts[1].strip()
                print(f"[!] Trigger detected: {prompt}")
                
                context = self.get_context()
                print("[*] Calling LLM...")
                response = call_llm(prompt, context)
                print(f"[*] AI Response: {response}")
                
                success, msg = inject_to_clipboard(response)
                if success:
                    print("[*] Response injected into clipboard. Paste in-game via /wmcpbox.")
                else:
                    print(f"[!] Clipboard error: {msg}")

    def run(self):
        if not self.setup():
            return
        
        tailer = ChatLogTailer(self.log_file, self.handle_log_line)
        print("=== WowMCP Bridge Active (Ctrl+C to stop) ===")
        try:
            tailer.start()
        except KeyboardInterrupt:
            tailer.stop()
            print("\n[*] Stopping bridge...")

if __name__ == "__main__":
    bridge = WowBridge()
    bridge.run()
