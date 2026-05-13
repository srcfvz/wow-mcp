import json
import os
from pathlib import Path

# Fix: Use a stable user-writable path for configuration
if os.name == "nt":
    # Windows: %APPDATA%/WowMCP/config.json
    CONFIG_DIR = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming")) / "WowMCP"
else:
    # Linux/macOS: ~/.config/wowmcp/config.json
    CONFIG_DIR = Path.home() / ".config" / "wowmcp"

CONFIG_FILE = CONFIG_DIR / "config.json"

DEFAULT_CONFIG = {
    "api_key": "",
    "github_token": "",
    "groq_key": "",
    "openrouter_key": "",
    "provider": "openai",
    "model": "gpt-4o-mini",
    "wow_path": "",
    "data_sources": {
        "WowMCP": True,
        "Syndicator": True,
        "Auctionator": True,
        "TradeSkillMaster": True,
        "TradeSkillMaster_AppHelper": True,
    }
}

def load_config():
    if not CONFIG_FILE.exists():
        return DEFAULT_CONFIG.copy()
    try:
        with open(CONFIG_FILE, "r") as f:
            config = json.load(f)
            # Ensure all keys are present
            for k, v in DEFAULT_CONFIG.items():
                if k not in config:
                    config[k] = v
            return config
    except Exception:
        return DEFAULT_CONFIG.copy()

def save_config(config):
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        with open(CONFIG_FILE, "w") as f:
            json.dump(config, f, indent=4)
        return True
    except Exception:
        return False
