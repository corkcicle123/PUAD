import os
import platform
import subprocess
import threading

class SoundAlert:
    """
    Non-blocking system audio feedback for inspection events (Mac/Linux/Windows).
    """
    def __init__(self, enabled=True):
        self.enabled = enabled
        self.is_mac = (platform.system() == 'Darwin')
        self.last_played = 0

    def play_pass(self):
        if not self.enabled or not self.is_mac:
            return
        threading.Thread(target=self._play_file, args=('/System/Library/Sounds/Ping.aiff',), daemon=True).start()

    def play_fail(self):
        if not self.enabled or not self.is_mac:
            return
        threading.Thread(target=self._play_file, args=('/System/Library/Sounds/Basso.aiff',), daemon=True).start()

    def play_capture(self):
        if not self.enabled or not self.is_mac:
            return
        threading.Thread(target=self._play_file, args=('/System/Library/Sounds/Tink.aiff',), daemon=True).start()

    def _play_file(self, sound_path):
        if os.path.exists(sound_path):
            try:
                subprocess.run(['afplay', sound_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception:
                pass
