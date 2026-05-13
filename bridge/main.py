import os
import sys
from pathlib import Path

# Add mcp-server to path so we can import its logic
sys.path.append(str(Path(__file__).parent.parent / "mcp-server"))

from tailer import ChatLogTailer
from clipboard_injector import inject_to_clipboard
import config_utils
import config_manager
from core import call_llm, process_log_line, extract_msg_type_and_payload
from wow_mcp_server.savedvars import load_var
from wow_mcp_server.bridge_helpers import summarize_state_for_prompt

class WowBridge:
    def __init__(self):
        self.config = config_manager.load_config()
        self.wow_path = None
        self.log_file = None
        self.savedvars_dir = None
        self.last_state = {}

    def setup(self):
        print("[*] Detecting WoW installation...")
        self.wow_path = self.config.get("wow_path") or config_utils.detect_wow_path()
        if not self.wow_path:
            print("[!] Could not find WoW automatically. Please set WOW_PATH in config or env.")
            return False
        
        print(f"[*] Found WoW at: {self.wow_path}")
        self.savedvars_dir, _ = config_utils.detect_savedvars_dir(self.wow_path)
        
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
        
        # Initial state load
        self.get_context()
        return True

    def get_context(self) -> str:
        if not self.savedvars_dir:
            return "No SavedVariables found."
        
        state_file = Path(self.savedvars_dir) / "WowMCP_State.lua"
        if not state_file.exists():
            return "WowMCP_State.lua missing. Run /reload in-game."
        
        try:
            self.last_state = load_var(state_file, "WowMCP_State")
            perms = {"inventory": True, "quests": True}
            return summarize_state_for_prompt(self.last_state, perms)
        except Exception as e:
            return f"Error loading state: {e}"

    def handle_log_line(self, line: str):
        request = process_log_line(line, self.last_state, self.config, print)
        if request:
            prompt = request["prompt"]
            context = self.get_context()
            
            print("[*] Calling LLM...")
            response = call_llm(
                prompt, context, 
                self.config.get("provider", "openai"),
                self.config.get("model", "gpt-4o-mini"),
                self.config
            )
            print(f"[*] AI Response: {response}")
            
            msg_type, payload = extract_msg_type_and_payload(response)
            success, msg = inject_to_clipboard(payload, msg_type=msg_type)
            if success:
                print(f"[*] Response ({msg_type}) injected into clipboard. Paste in-game via /wmcpbox.")
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
