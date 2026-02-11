import argparse
import asyncio
import copy
import os
import sys
import threading
import json
import customtkinter as ctk
import pystray
from PIL import Image, ImageDraw
import keyring
from pathlib import Path
from tkinter import filedialog
from backend_interface import ServerManager

IS_WINDOWS = sys.platform == "win32"

# Configuration constants
APP_NAME = "WoW MCP Companion"
SERVICE_NAME = "wow-mcp"
KEYRING_SERVICE_PREFIX = "wow-mcp-key-"
WOW_FLAVOR_DIRS = ["_retail_", "_classic_", "_classic_era_", "_classic_ptr_", "_ptr_"]
WOW_WINDOWS_EXECUTABLES = {"wow.exe", "wowclassic.exe", "world of warcraft launcher.exe"}
WOW_DATA_SOURCE_PRIORITIES = {
    "WowMCP": 0,
    "Syndicator": 1,
    "Auctionator": 2,
    "TradeSkillMaster": 3,
}

# Default Config
DEFAULT_CONFIG = {
    "wow_path": "",
    "savedvars_dir": "",
    "scan_root": "",
    "provider": "OpenAI",
    "model": "gpt-4-turbo",
    "mcp_mode": False,
    "save_history": False,
    "overlay_enabled": True,
    "overlay_opacity": 0.92,
    "overlay_hotkey": "Ctrl+Shift+F8",
    "data_sources": {},
    "permissions": {
        "inventory": True,
        "quests": True,
        "chat": False,  # Privacy default: OFF
        "combat": False,
        "auction": False
    }
}
CONFIG_FILE = "config.json"

class OverlayChatWindow:
    def __init__(self, parent, get_config, get_api_key, log_fn, on_send_prompt):
        self.parent = parent
        self.get_config = get_config
        self.get_api_key = get_api_key
        self.log = log_fn
        self.on_send_prompt = on_send_prompt

        self.window = ctk.CTkToplevel(parent)
        self.window.title("WowMCP Overlay")
        self.window.geometry("520x420")
        self.window.attributes("-topmost", True)
        self.window.protocol("WM_DELETE_WINDOW", self.hide)
        self.window.withdraw()

        self.header = ctk.CTkFrame(self.window)
        self.header.pack(fill="x", padx=10, pady=(10, 5))

        self.title_lbl = ctk.CTkLabel(self.header, text="WowMCP Overlay Chat", font=ctk.CTkFont(size=16, weight="bold"))
        self.title_lbl.pack(side="left")

        self.status_lbl = ctk.CTkLabel(self.header, text="Idle", text_color="gray")
        self.status_lbl.pack(side="right")

        self.chat_box = ctk.CTkTextbox(self.window, wrap="word")
        self.chat_box.pack(fill="both", expand=True, padx=10, pady=10)
        self.chat_box.insert("end", "Tip: Toggle overlay with Ctrl+Shift+F8 (Windows).\n\n")
        self.chat_box.configure(state="disabled")

        controls = ctk.CTkFrame(self.window, fg_color="transparent")
        controls.pack(fill="x", padx=10, pady=(0, 10))

        self.input_entry = ctk.CTkEntry(controls, placeholder_text="Ask something...")
        self.input_entry.pack(side="left", fill="x", expand=True)
        self.input_entry.bind("<Return>", lambda _e: self.send())

        self.send_btn = ctk.CTkButton(controls, text="Send", width=90, command=self.send)
        self.send_btn.pack(side="left", padx=(10, 0))

        footer = ctk.CTkFrame(self.window, fg_color="transparent")
        footer.pack(fill="x", padx=10, pady=(0, 10))

        self.opacity_slider = ctk.CTkSlider(footer, from_=0.55, to=1.0, number_of_steps=45, command=self._on_opacity_change)
        self.opacity_slider.pack(side="left", fill="x", expand=True)

        self.opacity_lbl = ctk.CTkLabel(footer, text="Opacity")
        self.opacity_lbl.pack(side="left", padx=(10, 0))

        self._apply_config()

    def _apply_config(self):
        cfg = self.get_config() or {}
        opacity = float(cfg.get("overlay_opacity", 0.92))
        try:
            self.window.attributes("-alpha", opacity)
        except Exception:
            pass
        try:
            self.opacity_slider.set(opacity)
        except Exception:
            pass

    def _on_opacity_change(self, value):
        try:
            self.window.attributes("-alpha", float(value))
        except Exception:
            return

        cfg = self.get_config()
        cfg["overlay_opacity"] = float(value)

    def show(self):
        self._apply_config()
        self.window.deiconify()
        self.window.lift()
        try:
            self.input_entry.focus_set()
        except Exception:
            pass

    def hide(self):
        self.window.withdraw()

    def toggle(self):
        if self.window.state() == "withdrawn":
            self.show()
        else:
            self.hide()

    def _append_line(self, who, text):
        self.chat_box.configure(state="normal")
        self.chat_box.insert("end", f"{who}: {text}\n")
        self.chat_box.see("end")
        self.chat_box.configure(state="disabled")

    def set_status(self, text, color="gray"):
        self.status_lbl.configure(text=text, text_color=color)

    def send(self):
        prompt = (self.input_entry.get() or "").strip()
        if not prompt:
            return

        self.input_entry.delete(0, "end")
        self._append_line("You", prompt)

        self.send_btn.configure(state="disabled")
        self.set_status("Thinking…", "yellow")

        def worker():
            try:
                response = self.on_send_prompt(prompt)
                self.parent.after(0, lambda: self._append_line("AI", response))
                self.parent.after(0, lambda: self.set_status("Idle", "gray"))
            except Exception as e:
                self.parent.after(0, lambda: self._append_line("Error", str(e)))
                self.parent.after(0, lambda: self.set_status("Idle", "gray"))
            finally:
                self.parent.after(0, lambda: self.send_btn.configure(state="normal"))

        threading.Thread(target=worker, daemon=True).start()


class WindowsHotkeyListener:
    def __init__(self, hotkey_text, callback):
        self.hotkey_text = hotkey_text
        self.callback = callback
        self.thread = None
        self._stop_event = threading.Event()
        self._thread_id = None
        self._registered = False

    def start(self):
        if not IS_WINDOWS:
            return
        if self.thread and self.thread.is_alive():
            return
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def stop(self):
        if not IS_WINDOWS:
            return
        try:
            import ctypes
            from ctypes import wintypes

            user32 = ctypes.windll.user32
            kernel32 = ctypes.windll.kernel32
            WM_QUIT = 0x0012
            if self._registered:
                user32.UnregisterHotKey(None, 1)
                self._registered = False
            if self._thread_id:
                user32.PostThreadMessageW(self._thread_id, WM_QUIT, 0, 0)
            _ = kernel32
        except Exception:
            pass

    def _run(self):
        try:
            import ctypes
            from ctypes import wintypes

            user32 = ctypes.windll.user32
            kernel32 = ctypes.windll.kernel32

            MOD_CONTROL = 0x0002
            MOD_SHIFT = 0x0004
            VK_F8 = 0x77
            WM_HOTKEY = 0x0312

            self._thread_id = kernel32.GetCurrentThreadId()
            if not user32.RegisterHotKey(None, 1, MOD_CONTROL | MOD_SHIFT, VK_F8):
                return
            self._registered = True

            msg = wintypes.MSG()
            while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) != 0:
                if msg.message == WM_HOTKEY:
                    try:
                        self.callback()
                    except Exception:
                        pass
        except Exception:
            return

class WowMcpApp:
    def __init__(self):
        self.root = None
        self.icon = None
        self.server_manager = ServerManager()
        self.config = self.load_config()
        self.overlay = None
        self.hotkey_listener = None
        
        self.setup_gui()
        self.setup_tray()
        self.setup_overlay()
        self.setup_hotkey()

    def load_config(self):
        base = copy.deepcopy(DEFAULT_CONFIG)
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    # Merge with default to ensure all keys exist
                    base.update(data)
                    # Deep merge permissions
                    if isinstance(data.get("permissions"), dict):
                        base["permissions"].update(data["permissions"])
                    if isinstance(data.get("data_sources"), dict):
                        base["data_sources"].update(data["data_sources"])
                    return base
            except Exception as e:
                print(f"Error loading config: {e}")
        return base

    def save_config(self):
        # Update config object from UI elements if they exist
        if self.root:
            self.config["wow_path"] = self.path_entry.get()
            self.config["savedvars_dir"] = self.savedvars_entry.get()
            self.config["scan_root"] = self.scan_root_entry.get()
            self.config["provider"] = self.provider_combo.get()
            self.config["model"] = self.model_entry.get()
            self.config["mcp_mode"] = bool(self.mcp_mode_switch.get())
            self.config["save_history"] = bool(self.history_switch.get())
            self.config["overlay_enabled"] = bool(self.overlay_switch.get())
            self.config["data_sources"] = self.config.get("data_sources", {}) or {}
            
            # Update permissions
            for key, switch in self.perm_switches.items():
                self.config["permissions"][key] = bool(switch.get())
            # Update selected data sources
            for source_name, switch in self.data_source_switches.items():
                self.config["data_sources"][source_name] = bool(switch.get())

        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(self.config, f, indent=4)
            print("Config saved.")
        except Exception as e:
            print(f"Error saving config: {e}")

    def setup_gui(self):
        ctk.set_appearance_mode("Dark")
        ctk.set_default_color_theme("blue")
        
        self.root = ctk.CTk()
        self.root.title(APP_NAME)
        self.root.geometry("600x550")
        self.root.protocol("WM_DELETE_WINDOW", self.hide_window)
        
        # Main Container
        self.main_frame = ctk.CTkFrame(self.root)
        self.main_frame.pack(pady=10, padx=10, fill="both", expand=True)

        # Title / Status Header
        header_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        header_frame.pack(fill="x", pady=(10, 5), padx=10)
        
        title_lbl = ctk.CTkLabel(header_frame, text=APP_NAME, font=ctk.CTkFont(size=20, weight="bold"))
        title_lbl.pack(side="left")
        
        self.status_indicator = ctk.CTkLabel(header_frame, text="● Stopped", text_color="red", font=ctk.CTkFont(weight="bold"))
        self.status_indicator.pack(side="right")

        # Tabs
        self.tab_view = ctk.CTkTabview(self.main_frame)
        self.tab_view.pack(fill="both", expand=True, padx=10, pady=10)
        
        self.tab_general = self.tab_view.add("General")
        self.tab_ai = self.tab_view.add("AI Provider")
        self.tab_privacy = self.tab_view.add("Privacy & Data")
        self.tab_sources = self.tab_view.add("Data Sources")
        self.tab_logs = self.tab_view.add("Logs")

        # --- General Tab ---
        ctk.CTkLabel(self.tab_general, text="WoW Installation Path:", anchor="w").pack(fill="x", pady=(10, 0))
        self.path_entry = ctk.CTkEntry(self.tab_general)
        self.path_entry.pack(fill="x", pady=(5, 10))
        self.path_entry.insert(0, self.config.get("wow_path", ""))
        
        path_btns = ctk.CTkFrame(self.tab_general, fg_color="transparent")
        path_btns.pack(fill="x", pady=(0, 10))
        ctk.CTkButton(path_btns, text="Auto-Detect WoW Path", command=self.detect_wow_path).pack(side="left")
        ctk.CTkButton(path_btns, text="Browse...", command=self.browse_wow_path).pack(side="left", padx=10)

        ctk.CTkLabel(self.tab_general, text="SavedVariables Folder (WTF/Account/.../SavedVariables):", anchor="w").pack(fill="x", pady=(10, 0))
        self.savedvars_entry = ctk.CTkEntry(self.tab_general)
        self.savedvars_entry.pack(fill="x", pady=(5, 10))
        self.savedvars_entry.insert(0, self.config.get("savedvars_dir", ""))

        savedvars_btns = ctk.CTkFrame(self.tab_general, fg_color="transparent")
        savedvars_btns.pack(fill="x", pady=(0, 10))
        ctk.CTkButton(savedvars_btns, text="Auto-Detect SavedVariables", command=self.detect_savedvars_dir).pack(side="left")
        ctk.CTkButton(savedvars_btns, text="Browse...", command=self.browse_savedvars_dir).pack(side="left", padx=10)

        ctk.CTkLabel(self.tab_general, text="Scan Root (optional, enables addon listing):", anchor="w").pack(fill="x", pady=(10, 0))
        self.scan_root_entry = ctk.CTkEntry(self.tab_general)
        self.scan_root_entry.pack(fill="x", pady=(5, 10))
        self.scan_root_entry.insert(0, self.config.get("scan_root", ""))
        scan_root_btns = ctk.CTkFrame(self.tab_general, fg_color="transparent")
        scan_root_btns.pack(fill="x", pady=(0, 10))
        ctk.CTkButton(scan_root_btns, text="Browse...", command=self.browse_scan_root).pack(side="left")
        ctk.CTkButton(scan_root_btns, text="Detect Data Sources", command=self.refresh_data_sources).pack(side="left", padx=10)

        self.mcp_mode_switch = ctk.CTkSwitch(self.tab_general, text="Expose as MCP Server (External Clients)")
        self.mcp_mode_switch.pack(anchor="w", pady=10)
        if self.config.get("mcp_mode"): self.mcp_mode_switch.select()

        self.history_switch = ctk.CTkSwitch(self.tab_general, text="Save Chat History Locally")
        self.history_switch.pack(anchor="w", pady=10)
        if self.config.get("save_history"): self.history_switch.select()

        self.overlay_switch = ctk.CTkSwitch(self.tab_general, text="Enable Overlay Chat (always-on-top)")
        self.overlay_switch.pack(anchor="w", pady=10)
        if self.config.get("overlay_enabled", True):
            self.overlay_switch.select()

        overlay_row = ctk.CTkFrame(self.tab_general, fg_color="transparent")
        overlay_row.pack(fill="x", pady=(0, 10))
        ctk.CTkButton(overlay_row, text="Open Overlay", command=self.open_overlay).pack(side="left")
        ctk.CTkLabel(overlay_row, text=f"Hotkey: {self.config.get('overlay_hotkey','Ctrl+Shift+F8')}", text_color="gray").pack(side="left", padx=10)

        # --- AI Provider Tab ---
        ctk.CTkLabel(self.tab_ai, text="Select AI Provider:", anchor="w").pack(fill="x", pady=(10, 0))
        self.provider_combo = ctk.CTkComboBox(self.tab_ai, values=["OpenAI", "Anthropic", "Google Gemini", "Local (Ollama)"], command=self.on_provider_change)
        self.provider_combo.pack(fill="x", pady=(5, 10))
        self.provider_combo.set(self.config.get("provider", "OpenAI"))

        ctk.CTkLabel(self.tab_ai, text="Model Name:", anchor="w").pack(fill="x", pady=(10, 0))
        self.model_entry = ctk.CTkEntry(self.tab_ai)
        self.model_entry.pack(fill="x", pady=(5, 10))
        self.model_entry.insert(0, self.config.get("model", "gpt-4-turbo"))

        ctk.CTkLabel(self.tab_ai, text="API Key:", anchor="w").pack(fill="x", pady=(10, 0))
        self.api_key_entry = ctk.CTkEntry(self.tab_ai, show="*")
        self.api_key_entry.pack(fill="x", pady=(5, 10))
        
        self.load_api_key() # Load key for current provider

        ctk.CTkButton(self.tab_ai, text="Save API Key Securely", command=self.save_api_key).pack(pady=10)

        # --- Privacy Tab ---
        ctk.CTkLabel(self.tab_privacy, text="Data Access Permissions", font=ctk.CTkFont(size=16, weight="bold")).pack(anchor="w", pady=(10, 5))
        ctk.CTkLabel(self.tab_privacy, text="Select what game data the AI is allowed to read.", text_color="gray").pack(anchor="w", pady=(0, 15))

        self.perm_switches = {}
        perms = [
            ("inventory", "Inventory & Bags", "Allow AI to see your items and currency"),
            ("quests", "Quest Log", "Allow AI to see active quests and objectives"),
            ("chat", "Chat Channels", "Allow AI to read public chat (Trade, General) - PRIVACY RISK"),
            ("combat", "Combat Log", "Allow AI to analyze damage/healing events"),
            ("auction", "Auction House", "Allow AI to scan AH prices (requires open window)")
        ]

        for key, title, desc in perms:
            frame = ctk.CTkFrame(self.tab_privacy, fg_color="transparent")
            frame.pack(fill="x", pady=5)
            
            switch = ctk.CTkSwitch(frame, text=title)
            switch.pack(side="left")
            if self.config["permissions"].get(key, False):
                switch.select()
            self.perm_switches[key] = switch
            
            ctk.CTkLabel(frame, text=f"({desc})", font=ctk.CTkFont(size=11), text_color="gray").pack(side="left", padx=10)

        # --- Data Sources Tab ---
        ctk.CTkLabel(self.tab_sources, text="Installed Addon Data Sources", font=ctk.CTkFont(size=16, weight="bold")).pack(anchor="w", pady=(10, 5))
        ctk.CTkLabel(
            self.tab_sources,
            text="Detected from Scan Root. Disable sources you do not want exposed to MCP tools.",
            text_color="gray",
        ).pack(anchor="w", pady=(0, 10))
        sources_actions = ctk.CTkFrame(self.tab_sources, fg_color="transparent")
        sources_actions.pack(fill="x", pady=(0, 10))
        ctk.CTkButton(sources_actions, text="Refresh from Scan Root", command=self.refresh_data_sources).pack(side="left")
        self.sources_status_label = ctk.CTkLabel(sources_actions, text="", text_color="gray")
        self.sources_status_label.pack(side="left", padx=10)
        self.sources_scroll = ctk.CTkScrollableFrame(self.tab_sources)
        self.sources_scroll.pack(fill="both", expand=True)
        self.data_source_switches = {}
        self.detected_addon_meta = {}

        # --- Logs Tab ---
        self.log_textbox = ctk.CTkTextbox(self.tab_logs)
        self.log_textbox.pack(fill="both", expand=True)
        self.log("Application started.")
        self.refresh_data_sources(log_result=False)

        # Footer Actions
        footer = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        footer.pack(fill="x", pady=10)

        self.start_btn = ctk.CTkButton(footer, text="START SERVER", height=40, font=ctk.CTkFont(weight="bold"), command=self.toggle_server)
        self.start_btn.pack(side="right", padx=10)
        
        ctk.CTkButton(footer, text="Save Settings", fg_color="transparent", border_width=1, command=self.save_config).pack(side="right")

    def log(self, message):
        if not hasattr(self, "log_textbox"):
            print(message)
            return
        self.log_textbox.insert("end", f"{message}\n")
        self.log_textbox.see("end")

    def create_image(self):
        width = 64
        height = 64
        image = Image.new('RGB', (width, height), (0, 0, 0))
        dc = ImageDraw.Draw(image)
        # Simple WoW-like colors
        dc.rectangle((0, 0, width, height), fill='#1a1a1a') # Dark bg
        dc.ellipse((10, 10, 54, 54), fill='#f8b700') # Gold coin/portal
        return image

    def setup_tray(self):
        menu = (
            pystray.MenuItem('Open Dashboard', self.show_window_action),
            pystray.MenuItem('Toggle Overlay', self.toggle_overlay_action),
            pystray.MenuItem('Start Server', self.start_server_action_safe, checked=lambda item: not self.server_manager.is_running()),
            pystray.MenuItem('Stop Server', self.stop_server_action_safe, checked=lambda item: self.server_manager.is_running()),
            pystray.MenuItem('Exit', self.quit_app_action)
        )
        self.icon = pystray.Icon("wow_mcp", self.create_image(), APP_NAME, menu)

    def on_provider_change(self, choice):
        # Save current key before switching? Maybe auto-save.
        # Load key for new provider
        self.load_api_key()
        # Set default model for provider if empty or default
        if choice == "Anthropic":
            self.model_entry.delete(0, "end")
            self.model_entry.insert(0, "claude-3-opus-20240229")
        elif choice == "OpenAI":
            self.model_entry.delete(0, "end")
            self.model_entry.insert(0, "gpt-4-turbo")

    def get_keyring_service_name(self):
        provider = self.provider_combo.get().lower().replace(" ", "_")
        return f"{KEYRING_SERVICE_PREFIX}{provider}"

    def load_api_key(self):
        self.api_key_entry.delete(0, "end")
        service = self.get_keyring_service_name()
        saved = keyring.get_password(SERVICE_NAME, service)
        if saved:
            self.api_key_entry.insert(0, saved)

    def save_api_key(self):
        key = self.api_key_entry.get()
        if key:
            service = self.get_keyring_service_name()
            keyring.set_password(SERVICE_NAME, service, key)
            self.log(f"API Key for {self.provider_combo.get()} saved securely.")
        else:
            self.log("Cannot save empty API key.")

    def _looks_like_wow_install(self, path_obj):
        if not path_obj or not path_obj.is_dir():
            return False
        if (path_obj / "WTF").is_dir() or (path_obj / "Interface").is_dir():
            return True
        for flavor in WOW_FLAVOR_DIRS:
            flavor_dir = path_obj / flavor
            if flavor_dir.is_dir():
                return True
        for exe_name in WOW_WINDOWS_EXECUTABLES:
            if (path_obj / exe_name).exists():
                return True
        return False

    def _normalize_wow_candidate(self, raw_path):
        if not raw_path:
            return None
        try:
            path_obj = Path(str(raw_path).strip().strip('"')).expanduser()
        except Exception:
            return None
        if not str(path_obj):
            return None
        if path_obj.suffix.lower() == ".exe":
            path_obj = path_obj.parent
        if path_obj.name.lower() in WOW_FLAVOR_DIRS:
            path_obj = path_obj.parent
        return path_obj

    def _collect_registry_wow_paths(self):
        if not IS_WINDOWS:
            return []
        try:
            import winreg
        except Exception:
            return []

        key_specs = [
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Blizzard Entertainment\World of Warcraft"),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Blizzard Entertainment\World of Warcraft"),
            (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Blizzard Entertainment\Battle.net\Launch Options\WoW"),
            (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Blizzard Entertainment\Battle.net\Launch Options\WOW"),
            (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Blizzard Entertainment\Battle.net\Launch Options\wow"),
        ]

        found = []
        for hive, key_path in key_specs:
            try:
                key = winreg.OpenKey(hive, key_path)
            except OSError:
                continue
            try:
                idx = 0
                while True:
                    name, value, _val_type = winreg.EnumValue(key, idx)
                    idx += 1
                    if not isinstance(value, str):
                        continue
                    candidate = self._normalize_wow_candidate(value)
                    if candidate and self._looks_like_wow_install(candidate):
                        found.append((candidate, f"registry:{key_path}:{name}"))
            except OSError:
                pass
            finally:
                try:
                    winreg.CloseKey(key)
                except Exception:
                    pass
        return found

    def _collect_common_wow_paths(self):
        roots = []
        env_candidates = [
            os.environ.get("ProgramFiles(x86)", ""),
            os.environ.get("ProgramFiles", ""),
            os.environ.get("PUBLIC", ""),
        ]
        for base in env_candidates:
            if base:
                roots.append(Path(base))
        roots.extend([Path.home() / "Games", Path("C:/Games"), Path("D:/Games"), Path("E:/Games")])

        path_candidates = []
        for root in roots:
            path_candidates.extend(
                [
                    root / "World of Warcraft",
                    root / "Battle.net" / "World of Warcraft",
                    root / "Blizzard" / "World of Warcraft",
                ]
            )
        # Include direct roots as a safety fallback for unusual installs.
        path_candidates.extend([Path("C:/World of Warcraft"), Path("D:/World of Warcraft"), Path("E:/World of Warcraft")])

        found = []
        for candidate in path_candidates:
            norm = self._normalize_wow_candidate(candidate)
            if norm and self._looks_like_wow_install(norm):
                found.append((norm, "common-path"))
        return found

    def _pick_best_wow_path(self, candidates):
        scored = []
        for path_obj, source in candidates:
            score = 0
            if (path_obj / "WTF").is_dir():
                score += 2
            if (path_obj / "Interface").is_dir():
                score += 2
            for flavor in WOW_FLAVOR_DIRS:
                flavor_dir = path_obj / flavor
                if flavor_dir.is_dir():
                    score += 3
                if (flavor_dir / "WTF").is_dir():
                    score += 2
                if (flavor_dir / "Interface").is_dir():
                    score += 2
                for exe_name in WOW_WINDOWS_EXECUTABLES:
                    if (flavor_dir / exe_name).exists():
                        score += 1
            for exe_name in WOW_WINDOWS_EXECUTABLES:
                if (path_obj / exe_name).exists():
                    score += 1
            scored.append((score, str(path_obj), source))
        if not scored:
            return None
        scored.sort(key=lambda item: (item[0], item[1].lower()), reverse=True)
        best_score, best_path, best_source = scored[0]
        if best_score <= 0:
            return None
        return best_path, best_source

    def detect_wow_path(self):
        candidate_map = {}
        for path_obj, source in self._collect_registry_wow_paths():
            candidate_map[str(path_obj).lower()] = (path_obj, source)
        for path_obj, source in self._collect_common_wow_paths():
            candidate_map.setdefault(str(path_obj).lower(), (path_obj, source))

        best = self._pick_best_wow_path(candidate_map.values())
        if not best:
            self.log("WoW auto-detection failed. Use Browse and select your game folder manually.")
            return

        wow_path, source = best
        self.path_entry.delete(0, "end")
        self.path_entry.insert(0, wow_path)
        if not (self.scan_root_entry.get() or "").strip():
            self.scan_root_entry.delete(0, "end")
            self.scan_root_entry.insert(0, wow_path)

        self.log(f"Detected WoW path ({source}): {wow_path}")
        self.detect_savedvars_dir()
        self.refresh_data_sources(log_result=False)

    def setup_overlay(self):
        def get_cfg():
            return self.config

        def get_key():
            service = self.get_keyring_service_name()
            return keyring.get_password(SERVICE_NAME, service)

        self.overlay = OverlayChatWindow(
            parent=self.root,
            get_config=get_cfg,
            get_api_key=get_key,
            log_fn=self.log,
            on_send_prompt=self.generate_overlay_response,
        )

    def setup_hotkey(self):
        if not IS_WINDOWS:
            return
        def cb():
            if not self.root:
                return
            self.root.after(0, self.toggle_overlay)
        self.hotkey_listener = WindowsHotkeyListener(self.config.get("overlay_hotkey", "Ctrl+Shift+F8"), cb)
        self.hotkey_listener.start()

    def open_overlay(self):
        if not self.overlay:
            return
        self.overlay.show()

    def toggle_overlay(self, icon=None, item=None):
        if not self.overlay:
            return
        if not self.overlay_switch.get():
            self.log("Overlay is disabled in settings.")
            return
        self.overlay.toggle()

    def _load_wow_state(self):
        savedvars_dir = (self.config.get("savedvars_dir") or "").strip()
        if not savedvars_dir:
            return None
        try:
            repo_root = Path(__file__).resolve().parents[1]
            mcp_server_dir = repo_root / "mcp-server"
            if mcp_server_dir.exists() and str(mcp_server_dir) not in sys.path:
                sys.path.insert(0, str(mcp_server_dir))
        except Exception:
            pass

        try:
            from wow_mcp_server.savedvars import LuaParseError, load_var
        except Exception:
            return None

        state_file = Path(savedvars_dir) / "WowMCP_State.lua"
        if not state_file.exists():
            return None

        try:
            return load_var(state_file, "WowMCP_State")
        except (LuaParseError, Exception):
            return None

    def generate_overlay_response(self, prompt: str) -> str:
        cfg = self.config
        perms = cfg.get("permissions", {}) or {}
        provider = cfg.get("provider", "OpenAI")
        model = cfg.get("model", "")

        # Gate any local state context behind existing toggles.
        want_context = bool(perms.get("inventory") or perms.get("quests"))
        state_data = self._load_wow_state() if want_context else None

        context_lines = []
        if state_data and isinstance(state_data, dict):
            try:
                from wow_mcp_server.bridge_helpers import summarize_state_for_prompt
                summary = summarize_state_for_prompt(state_data, perms)
                if summary:
                    context_lines.append(summary)
            except Exception:
                pass

        system_prompt = (
            "You are a helpful WoW assistant. Keep answers short (max 3 sentences). "
            "Never suggest botting, memory reading, or protected-action automation."
        )
        if context_lines:
            system_prompt += "\nContext:\n" + "\n".join(context_lines)

        api_key = self.api_key_entry.get()
        if not api_key:
            service = self.get_keyring_service_name()
            api_key = keyring.get_password(SERVICE_NAME, service) or ""

        try:
            from wow_mcp_server import server as wow_server
            from wow_mcp_server.bridge_helpers import normalize_provider
        except Exception as e:
            raise RuntimeError(f"Backend import failed: {e}")

        provider_norm = normalize_provider(provider)
        if provider_norm != "ollama" and not api_key:
            return "Missing API key for this provider."

        return wow_server._call_llm(provider_norm, model, system_prompt, prompt, api_key or None)

    def browse_wow_path(self):
        chosen = filedialog.askdirectory(title="Select WoW folder (contains WTF/ and Interface/)")
        if chosen:
            self.path_entry.delete(0, "end")
            self.path_entry.insert(0, chosen)

    def browse_scan_root(self):
        chosen = filedialog.askdirectory(title="Select WoW scan root (contains Interface/AddOns)")
        if chosen:
            self.scan_root_entry.delete(0, "end")
            self.scan_root_entry.insert(0, chosen)
            self.refresh_data_sources(log_result=False)

    def browse_savedvars_dir(self):
        chosen = filedialog.askdirectory(title="Select SavedVariables folder")
        if chosen:
            self.savedvars_entry.delete(0, "end")
            self.savedvars_entry.insert(0, chosen)

    def _parse_addon_toc(self, toc_path):
        title = None
        version = None
        try:
            raw = toc_path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            return (None, None)

        for line in raw.splitlines():
            line = line.strip()
            if not line.startswith("##") or ":" not in line:
                continue
            key, value = line[2:].split(":", 1)
            key = key.strip().lower()
            value = value.strip()
            if key == "title" and title is None:
                title = value
            elif key == "version" and version is None:
                version = value
            if title is not None and version is not None:
                break
        return (title, version)

    def _detect_addons_from_scan_root(self, scan_root):
        if not scan_root:
            return {}
        root = Path(scan_root).expanduser()
        if not root.is_dir():
            return {}

        addons_dir_candidates = [
            root / "Interface" / "AddOns",
            root / "AddOns",
        ]
        if root.name.lower() == "addons":
            addons_dir_candidates.insert(0, root)

        addons_dir = None
        for candidate in addons_dir_candidates:
            if candidate.is_dir():
                addons_dir = candidate
                break

        if addons_dir is None:
            try:
                for interface_dir in root.rglob("Interface"):
                    if not interface_dir.is_dir():
                        continue
                    maybe_addons = interface_dir / "AddOns"
                    if maybe_addons.is_dir():
                        addons_dir = maybe_addons
                        break
            except Exception:
                addons_dir = None

        if addons_dir is None:
            return {}

        found = {}
        try:
            entries = sorted(addons_dir.iterdir(), key=lambda p: p.name.lower())
        except Exception:
            return {}

        for addon_dir in entries:
            if not addon_dir.is_dir() or addon_dir.name in {".git", ".svn"}:
                continue
            toc_files = sorted(addon_dir.glob("*.toc"), key=lambda p: p.name.lower())
            title = None
            version = None
            if toc_files:
                title, version = self._parse_addon_toc(toc_files[0])
            found[addon_dir.name] = {
                "title": title,
                "version": version,
                "path": str(addon_dir),
            }
        return found

    def _sorted_source_names(self, names):
        return sorted(
            names,
            key=lambda name: (WOW_DATA_SOURCE_PRIORITIES.get(name, 99), name.lower()),
        )

    def refresh_data_sources(self, log_result=True):
        scan_root = (self.scan_root_entry.get() or "").strip() if self.root else (self.config.get("scan_root") or "").strip()
        detected = self._detect_addons_from_scan_root(scan_root)
        self.detected_addon_meta = detected

        current_config = self.config.get("data_sources", {}) or {}
        if not isinstance(current_config, dict):
            current_config = {}

        display_names = self._sorted_source_names(set(current_config.keys()) | set(detected.keys()))
        if detected and not current_config:
            for name in detected:
                current_config[name] = True
        else:
            for name in detected:
                current_config.setdefault(name, True)
        self.config["data_sources"] = current_config

        for child in self.sources_scroll.winfo_children():
            child.destroy()
        self.data_source_switches = {}

        if not display_names:
            ctk.CTkLabel(
                self.sources_scroll,
                text="No addons detected from Scan Root. Set Scan Root in General and refresh.",
                text_color="gray",
            ).pack(anchor="w", padx=5, pady=10)
            self.sources_status_label.configure(text="No addons detected")
            if log_result:
                self.log("No addons detected from scan_root. Check the Scan Root path.")
            return

        for addon_name in display_names:
            meta = detected.get(addon_name, {})
            frame = ctk.CTkFrame(self.sources_scroll, fg_color="transparent")
            frame.pack(fill="x", pady=4, padx=2)

            switch = ctk.CTkSwitch(frame, text=addon_name)
            switch.pack(side="left")
            if current_config.get(addon_name, False):
                switch.select()
            self.data_source_switches[addon_name] = switch

            details = []
            title = meta.get("title") if isinstance(meta, dict) else None
            version = meta.get("version") if isinstance(meta, dict) else None
            if title and title != addon_name:
                details.append(title)
            if version:
                details.append(f"v{version}")
            if addon_name not in detected:
                details.append("not currently detected")
            if details:
                ctk.CTkLabel(frame, text=f"({' | '.join(details)})", text_color="gray").pack(side="left", padx=10)

        detected_count = len(detected)
        self.sources_status_label.configure(text=f"{detected_count} detected")
        if log_result:
            self.log(f"Detected {detected_count} addon(s) from scan_root.")

    def detect_savedvars_dir(self):
        wow_path = (self.path_entry.get() or "").strip()
        if not wow_path:
            self.log("Set WoW path first, or use Browse to select SavedVariables directly.")
            return

        roots = [wow_path]
        for flavor in ["_retail_", "_classic_", "_classic_era_", "_classic_ptr_", "_ptr_"]:
            roots.append(os.path.join(wow_path, flavor))

        candidates = []
        for root in roots:
            wtf = os.path.join(root, "WTF", "Account")
            if not os.path.isdir(wtf):
                continue
            for account in os.listdir(wtf):
                sv = os.path.join(wtf, account, "SavedVariables")
                if os.path.isdir(sv):
                    try:
                        mtime = os.path.getmtime(sv)
                    except Exception:
                        mtime = 0
                    candidates.append((mtime, sv, root))

        if not candidates:
            self.log("No SavedVariables folders found under the provided WoW path.")
            return

        candidates.sort(key=lambda t: t[0], reverse=True)
        _, savedvars_dir, scan_root = candidates[0]
        self.savedvars_entry.delete(0, "end")
        self.savedvars_entry.insert(0, savedvars_dir)
        self.scan_root_entry.delete(0, "end")
        self.scan_root_entry.insert(0, scan_root)
        self.log(f"Detected SavedVariables: {savedvars_dir}")
        self.refresh_data_sources(log_result=False)

    def toggle_server(self):
        if "Stopped" in self.status_indicator.cget("text"):
            self.start_server_action()
        else:
            self.stop_server_action()

    def start_server_action(self, icon=None, item=None):
        # 1. Save config first
        self.save_config()

        if self.config.get("mcp_mode"):
            self.log(
                "MCP mode is intended for external clients that launch the process over stdio. "
                "Disable 'Expose as MCP Server' to run the local bridge daemon from this UI."
            )
            return
        
        # 2. Generate backend config
        self.server_manager.generate_server_config(self.config)

        savedvars_dir = (self.config.get("savedvars_dir") or "").strip()
        if not savedvars_dir:
            self.log("Error: SavedVariables folder is missing. Set it in General tab.")
            return
        if not os.path.isdir(savedvars_dir):
            self.log(f"Error: SavedVariables folder not found: {savedvars_dir}")
            return
        
        # 3. Retrieve API Key
        api_key = self.api_key_entry.get()
        if not api_key:
            # Try loading if field is empty (e.g. starting from tray)
            service = self.get_keyring_service_name()
            api_key = keyring.get_password(SERVICE_NAME, service)
            
        provider = (self.provider_combo.get() or "").lower()
        if ("local" not in provider) and not api_key:
            self.log("Error: API Key is missing. Please save it in the AI Provider tab.")
            return

        # 4. Start Server
        self.log("Starting Daemon...")
        success, message = self.server_manager.start_server(api_key)
        
        if success:
            self.status_indicator.configure(text="● Running", text_color="green")
            self.start_btn.configure(text="STOP SERVER", fg_color="red", hover_color="darkred")
            self.log(f"Server started. PID: {self.server_manager.process.pid}")
        else:
            self.log(f"Error starting server: {message}")

    def stop_server_action(self, icon=None, item=None):
        self.log("Stopping Daemon...")
        if self.server_manager.stop_server():
            self.status_indicator.configure(text="● Stopped", text_color="red")
            self.start_btn.configure(text="START SERVER", fg_color="#1f538d", hover_color="#14375e")
            self.log("Server stopped.")
        else:
            self.log("Server was not running.")

    def show_window(self, icon=None, item=None):
        self.root.deiconify()
        self.root.lift()

    def show_window_action(self, icon=None, item=None):
        if self.root:
            self.root.after(0, self.show_window)

    def hide_window(self):
        self.root.withdraw()
        # Notification could go here

    def toggle_overlay_action(self, icon=None, item=None):
        if self.root:
            self.root.after(0, self.toggle_overlay)

    def start_server_action_safe(self, icon=None, item=None):
        if self.root:
            self.root.after(0, self.start_server_action)

    def stop_server_action_safe(self, icon=None, item=None):
        if self.root:
            self.root.after(0, self.stop_server_action)

    def quit_app(self, icon=None, item=None):
        if self.icon:
            self.icon.stop()
        if self.hotkey_listener:
            self.hotkey_listener.stop()
        self.root.quit()
        sys.exit(0)

    def quit_app_action(self, icon=None, item=None):
        if self.root:
            self.root.after(0, self.quit_app)

    def run(self):
        tray_thread = threading.Thread(target=self.icon.run)
        tray_thread.start()
        self.root.mainloop()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--run-bridge", action="store_true")
    parser.add_argument("--config", default="")
    args, _ = parser.parse_known_args()

    if args.run_bridge:
        config_path = args.config or ""
        if not config_path or not os.path.exists(config_path):
            print("ERROR: --config path missing for --run-bridge", file=sys.stderr)
            raise SystemExit(2)

        cfg = json.load(open(config_path, "r", encoding="utf-8"))
        savedvars_dir = (cfg.get("savedvars_dir") or "").strip()
        scan_root = (cfg.get("scan_root") or "").strip()
        if savedvars_dir:
            os.environ["WOW_SAVEDVARS_DIR"] = savedvars_dir
        if scan_root:
            os.environ["WOW_SCAN_ROOT"] = scan_root
        elif savedvars_dir:
            os.environ["WOW_SCAN_ROOT"] = savedvars_dir

        try:
            repo_root = Path(__file__).resolve().parents[1]
            mcp_server_dir = repo_root / "mcp-server"
            if mcp_server_dir.exists() and str(mcp_server_dir) not in sys.path:
                sys.path.insert(0, str(mcp_server_dir))
        except Exception:
            pass

        from wow_mcp_server import server as wow_server

        wow_server.SERVER_CONFIG = cfg
        asyncio.run(wow_server.bridge_loop())
        raise SystemExit(0)

    app = WowMcpApp()
    app.run()
