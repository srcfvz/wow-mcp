import json
import subprocess
import sys
import os

CONFIG_PATH = "server_config.json"

class ServerManager:
    def __init__(self):
        self.process = None

    def generate_server_config(self, app_config):
        """
        Translates the App GUI Config into the specific JSON format 
        that the MCP Server expects.
        """
        server_config = {
            "wow_path": app_config.get("wow_path"),
            "savedvars_dir": app_config.get("savedvars_dir"),
            "scan_root": app_config.get("scan_root"),
            "llm": {
                "provider": app_config.get("provider", "OpenAI").lower(),
                "model": app_config.get("model"),
                # API Key is passed via ENV var for security, not written to disk if possible
                # But for the standalone server script, we might need to pass it securely.
            },
            "permissions": app_config.get("permissions", {}),
            "data_sources": app_config.get("data_sources", {}),
            "mcp_mode": app_config.get("mcp_mode", False),
            "bridge_state_file": os.path.join(os.path.dirname(os.path.abspath(CONFIG_PATH)), "bridge_state.json"),
            "logging": {
                "save_history": app_config.get("save_history", False),
                "level": "INFO"
            }
        }
        
        with open(CONFIG_PATH, 'w') as f:
            json.dump(server_config, f, indent=4)
        
        return server_config

    def start_server(self, api_key):
        if self.process:
            return False, "Server already running"

        # Prepare Environment
        env = os.environ.copy()
        env["WOW_MCP_API_KEY"] = api_key
        # Ensure PYTHONPATH includes the mcp-server directory (bridge mode imports wow_mcp_server)
        mcp_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        server_root = os.path.join(mcp_root, "mcp-server")
        env["PYTHONPATH"] = server_root + os.pathsep + env.get("PYTHONPATH", "")

        if getattr(sys, "frozen", False):
            # In a PyInstaller build, sys.executable is the .exe. We spawn ourselves in bridge mode.
            cmd = [sys.executable, "--run-bridge", "--config", CONFIG_PATH]
        else:
            main_script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "main.py")
            cmd = [sys.executable, main_script, "--run-bridge", "--config", CONFIG_PATH]

        try:
            # On Windows, use creationflags=subprocess.CREATE_NO_WINDOW to hide console
            creation_flags = 0
            if sys.platform == "win32":
                creation_flags = subprocess.CREATE_NO_WINDOW

            self.process = subprocess.Popen(
                cmd,
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                text=True,
                creationflags=creation_flags
            )
            return True, "Server started successfully"
        except Exception as e:
            return False, f"Failed to start server: {e}"

    def stop_server(self):
        if self.process:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
            self.process = None
            return True
        return False

    def is_running(self):
        if self.process:
            return self.process.poll() is None
        return False
