import os
import time
from typing import Callable

class ChatLogTailer:
    def __init__(self, log_path: str, callback: Callable[[str], None]):
        self.log_path = log_path
        self.callback = callback
        self._stop = False
        self._last_pos = 0

    def start(self):
        """
        Monitors the file. Handles rotations/truncations.
        """
        print(f"[*] Starting tailer for: {self.log_path}")
        
        # Seek to end on startup to avoid processing old history
        if os.path.exists(self.log_path):
            self._last_pos = os.path.getsize(self.log_path)
            
        while not self._stop:
            if not os.path.exists(self.log_path):
                time.sleep(1)
                continue
                
            with open(self.log_path, 'r', encoding='utf-8', errors='replace') as f:
                # Check for file rotation or truncation
                curr_size = os.path.getsize(self.log_path)
                if curr_size < self._last_pos:
                    print("[!] File truncated, resetting tailer.")
                    self._last_pos = 0
                
                f.seek(self._last_pos)
                new_lines = f.readlines()
                
                if new_lines:
                    for line in new_lines:
                        line = line.strip()
                        if line:
                            self.callback(line)
                    self._last_pos = f.tell()
            
            # Real-time-ish polling (200ms)
            time.sleep(0.2)

    def stop(self):
        self._stop = True

if __name__ == "__main__":
    # Test script
    def dummy_cb(line):
        print(f"[LOG] {line}")
    
    path = "C:/Program Files (x86)/World of Warcraft/_retail_/Logs/WoWChatLog.txt"
    tailer = ChatLogTailer(path, dummy_cb)
    try:
        tailer.start()
    except KeyboardInterrupt:
        tailer.stop()
