import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import threading
import os
import sys
import time
import webbrowser
from pathlib import Path
from typing import Any, Callable, Dict, Optional

# Add mcp-server to path so we can import its logic
sys.path.append(str(Path(__file__).parent.parent / "mcp-server"))

from tailer import ChatLogTailer
from clipboard_injector import inject_to_clipboard
import config_utils
import config_manager
from core import call_llm, process_log_line, extract_msg_type_and_payload
from wow_mcp_server.savedvars import load_var
from wow_mcp_server.bridge_helpers import summarize_state_for_prompt

class WowMcpGui:
    def __init__(self, root):
        self.root = root
        self.root.title("WowMCP Bridge - v0.3.3")
        self.root.geometry("700x750")
        self.root.resizable(True, True)

        self.config = config_manager.load_config()
        self.bridge_running = False
        self.tailer = None
        self.data_source_vars = {}
        self.last_state = {}
        
        self.setup_ui()
        self.refresh_status()

    def setup_ui(self):
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # 1. Configuration Section
        config_lf = ttk.LabelFrame(main_frame, text=" Configuration (AI Settings) ", padding="10")
        config_lf.pack(fill=tk.X, pady=5)

        ttk.Label(config_lf, text="AI Provider:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.provider_var = tk.StringVar(value=self.config.get("provider", "openai"))
        providers = ["openai", "github", "groq", "openrouter", "anthropic", "gemini", "ollama"]
        self.provider_combo = ttk.Combobox(config_lf, textvariable=self.provider_var, values=providers, state="readonly")
        self.provider_combo.grid(row=0, column=1, sticky=tk.W, pady=5, padx=5)
        self.provider_combo.bind("<<ComboboxSelected>>", self.on_provider_change)

        self.keys_frame = ttk.Frame(config_lf)
        self.keys_frame.grid(row=1, column=0, columnspan=2, sticky=tk.W+tk.E, pady=5)
        self.key_widgets = {}
        
        # OpenAI
        oai_f = ttk.Frame(self.keys_frame)
        ttk.Label(oai_f, text="OpenAI Key:").pack(side=tk.LEFT)
        self.oai_key_var = tk.StringVar(value=self.config.get("api_key", ""))
        ttk.Entry(oai_f, textvariable=self.oai_key_var, show="*", width=35).pack(side=tk.LEFT, padx=5)
        self.key_widgets["openai"] = oai_f

        # GitHub
        gh_f = ttk.Frame(self.keys_frame)
        ttk.Label(gh_f, text="GitHub Token:").pack(side=tk.LEFT)
        self.gh_token_var = tk.StringVar(value=self.config.get("github_token", ""))
        ttk.Entry(gh_f, textvariable=self.gh_token_var, show="*", width=35).pack(side=tk.LEFT, padx=5)
        ttk.Button(gh_f, text="Get Token", command=lambda: webbrowser.open("https://github.com/settings/tokens?type=beta")).pack(side=tk.LEFT, padx=5)
        self.key_widgets["github"] = gh_f

        # Groq
        groq_f = ttk.Frame(self.keys_frame)
        ttk.Label(groq_f, text="Groq Key:").pack(side=tk.LEFT)
        self.groq_key_var = tk.StringVar(value=self.config.get("groq_key", ""))
        ttk.Entry(groq_f, textvariable=self.groq_key_var, show="*", width=35).pack(side=tk.LEFT, padx=5)
        self.key_widgets["groq"] = groq_f

        # OpenRouter
        or_f = ttk.Frame(self.keys_frame)
        ttk.Label(or_f, text="OpenRouter Key:").pack(side=tk.LEFT)
        self.or_key_var = tk.StringVar(value=self.config.get("openrouter_key", ""))
        ttk.Entry(or_f, textvariable=self.or_key_var, show="*", width=35).pack(side=tk.LEFT, padx=5)
        self.key_widgets["openrouter"] = or_f

        self.model_frame = ttk.Frame(config_lf)
        self.model_frame.grid(row=2, column=0, columnspan=2, sticky=tk.W, pady=5)
        ttk.Label(self.model_frame, text="Model:").pack(side=tk.LEFT)
        self.model_var = tk.StringVar(value=self.config.get("model", "gpt-4o-mini"))
        ttk.Entry(self.model_frame, textvariable=self.model_var, width=25).pack(side=tk.LEFT, padx=5)
        self.model_hint = ttk.Label(self.model_frame, text="", font=("Segoe UI", 8, "italic"))
        self.model_hint.pack(side=tk.LEFT)

        self.on_provider_change()

        # 2. Data Sources
        self.sources_lf = ttk.LabelFrame(main_frame, text=" Data Sources (Detected Addons) ", padding="10")
        self.sources_lf.pack(fill=tk.X, pady=5)
        self.sources_container = ttk.Frame(self.sources_lf)
        self.sources_container.pack(fill=tk.X)
        self.rebuild_data_sources_ui()

        # 3. Status
        status_lf = ttk.LabelFrame(main_frame, text=" Status ", padding="10")
        status_lf.pack(fill=tk.X, pady=5)
        self.wow_path_label = ttk.Label(status_lf, text="WoW Path: Detecting...")
        self.wow_path_label.pack(anchor=tk.W)
        self.log_file_label = ttk.Label(status_lf, text="Log File: Detecting...")
        self.log_file_label.pack(anchor=tk.W)

        actions_frame = ttk.Frame(main_frame, padding="5")
        actions_frame.pack(fill=tk.X)
        self.start_btn = ttk.Button(actions_frame, text="Start Bridge", command=self.toggle_bridge)
        self.start_btn.pack(side=tk.LEFT, padx=5)
        self.save_btn = ttk.Button(actions_frame, text="Save Settings", command=self.save_settings)
        self.save_btn.pack(side=tk.LEFT, padx=5)
        self.detect_btn = ttk.Button(actions_frame, text="Scan & Re-detect", command=self.refresh_status)
        self.detect_btn.pack(side=tk.LEFT, padx=5)

        # 4. Console
        console_lf = ttk.LabelFrame(main_frame, text=" Activity Log ", padding="5")
        console_lf.pack(fill=tk.BOTH, expand=True, pady=5)
        self.console = tk.Text(console_lf, height=10, state=tk.DISABLED, wrap=tk.WORD, font=("Consolas", 9))
        self.console.pack(fill=tk.BOTH, expand=True)
        scrollbar = ttk.Scrollbar(self.console, command=self.console.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.console['yscrollcommand'] = scrollbar.set

    def log(self, message):
        def _append():
            timestamp = time.strftime("[%H:%M:%S] ")
            self.console.config(state=tk.NORMAL)
            self.console.insert(tk.END, timestamp + str(message) + "\n")
            self.console.see(tk.END)
            self.console.config(state=tk.DISABLED)
        self.root.after(0, _append)

    def on_provider_change(self, event=None):
        p = self.provider_var.get()
        for widget in self.key_widgets.values(): widget.pack_forget()
        if p in self.key_widgets: self.key_widgets[p].pack(side=tk.LEFT, fill=tk.X)
        
        hints = {"openai": "gpt-4o-mini", "github": "gpt-4o", "groq": "llama-3.1-70b-versatile", 
                 "openrouter": "anthropic/claude-3.5-sonnet", "anthropic": "claude-3-5-sonnet-latest", 
                 "gemini": "gemini-1.5-flash", "ollama": "llama3.1"}
        self.model_hint.config(text=f" (Suggested: {hints.get(p, '')})")

    def rebuild_data_sources_ui(self, detected_addons=None):
        for widget in self.sources_container.winfo_children(): widget.destroy()
        targets = ["WowMCP", "Syndicator", "Auctionator", "TradeSkillMaster"]
        all_relevant = set(targets)
        if detected_addons:
            for addon_name in detected_addons:
                if any(t.lower() in addon_name.lower() for t in targets): all_relevant.add(addon_name)
        
        sorted_sources = sorted(list(all_relevant))
        for i, name in enumerate(sorted_sources):
            if name not in self.data_source_vars:
                val = self.config.get("data_sources", {}).get(name, True)
                self.data_source_vars[name] = tk.BooleanVar(value=val)
            cb = ttk.Checkbutton(self.sources_container, text=name, variable=self.data_source_vars[name])
            cb.grid(row=i // 2, column=i % 2, sticky=tk.W, padx=10, pady=2)

    def save_settings(self):
        self.config.update({
            "api_key": self.oai_key_var.get(), "github_token": self.gh_token_var.get(),
            "groq_key": self.groq_key_var.get(), "openrouter_key": self.or_key_var.get(),
            "provider": self.provider_var.get(), "model": self.model_var.get(),
            "data_sources": {name: var.get() for name, var in self.data_source_vars.items()}
        })
        if config_manager.save_config(self.config): self.log("Settings saved.")
        else: messagebox.showerror("Error", "Could not save settings.")

    def refresh_status(self):
        self.log("Detecting WoW installation...")
        wow_path = config_utils.detect_wow_path()
        if wow_path:
            self.wow_path_label.config(text=f"WoW Path: {wow_path}")
            self.config["wow_path"] = wow_path
            savedvars_dir, scan_root = config_utils.detect_savedvars_dir(wow_path)
            if scan_root:
                addons = config_utils.detect_addons_from_scan_root(scan_root)
                self.rebuild_data_sources_ui(addons.keys())
            
            log_file = None
            for flavor in ["_retail_", "_classic_", "_classic_era_", "_ptr_"]:
                candidate = Path(wow_path) / flavor / "Logs" / "WoWChatLog.txt"
                if candidate.exists(): log_file = str(candidate); break
            
            if log_file: self.log_file_label.config(text=f"Log File: {log_file}")
            else: self.log_file_label.config(text="Log File: NOT FOUND (Run /chatlog)")
        else: self.wow_path_label.config(text="WoW Path: NOT FOUND")

    def toggle_bridge(self):
        if self.bridge_running:
            self.bridge_running = False
            if self.tailer: self.tailer.stop()
            self.start_btn.config(text="Start Bridge")
            self.log("Bridge stopped.")
        else:
            self.bridge_running = True
            self.start_btn.config(text="Stop Bridge")
            threading.Thread(target=self.bridge_loop, daemon=True).start()

    def bridge_loop(self):
        wow_path = self.config.get("wow_path") or config_utils.detect_wow_path()
        if not wow_path: self.log("[Error] WoW path not found."); self.root.after(0, self.toggle_bridge); return
        
        savedvars_dir, _ = config_utils.detect_savedvars_dir(wow_path)
        log_file = None
        for flavor in ["_retail_", "_classic_", "_classic_era_", "_ptr_"]:
            candidate = Path(wow_path) / flavor / "Logs" / "WoWChatLog.txt"
            if candidate.exists(): log_file = str(candidate); break
        
        if not log_file: self.log("[Error] Log not found."); self.root.after(0, self.toggle_bridge); return

        def handle_line(line):
            request = process_log_line(line, self.last_state, self.config, self.log)
            if request:
                context = "No SavedVariables found."
                if savedvars_dir:
                    state_file = Path(savedvars_dir) / "WowMCP_State.lua"
                    if state_file.exists():
                        try:
                            self.last_state = load_var(state_file, "WowMCP_State")
                            context = summarize_state_for_prompt(self.last_state, {"inventory": True, "quests": True})
                        except Exception as e: self.log(f"Error: {e}")
                
                self.log(f"Calling LLM...")
                response = call_llm(request["prompt"], context, self.config["provider"], self.config["model"], self.config)
                msg_type, payload = extract_msg_type_and_payload(response)
                success, msg = inject_to_clipboard(payload, msg_type)
                if success: self.log(f"Injected ({msg_type}). Paste in WoW.")
                else: self.log(f"Error: {msg}")

        self.log("Bridge active.")
        self.tailer = ChatLogTailer(log_file, handle_line)
        self.tailer.start()

if __name__ == "__main__":
    root = tk.Tk()
    app = WowMcpGui(root)
    root.mainloop()
