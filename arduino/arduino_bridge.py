import time
import threading
import serial
import serial.tools.list_ports

class ArduinoBridge:
    """
    Serial communication bridge between Python AI QA System and Arduino Conveyor.
    Gracefully falls back to Simulation Mode if no hardware is plugged in.
    """
    def __init__(self, port=None, baudrate=115200, on_trigger_callback=None):
        self.port = port
        self.baudrate = baudrate
        self.on_trigger_callback = on_trigger_callback
        self.serial = None
        self.is_connected = False
        self.running = False
        self.thread = None

    def auto_detect_port(self):
        ports = serial.tools.list_ports.comports()
        for p in ports:
            # Common Arduino USB identifiers
            if "usbmodem" in p.device.lower() or "usbserial" in p.device.lower() or "arduino" in p.description.lower():
                return p.device
        return None

    def connect(self):
        if self.port is None:
            self.port = self.auto_detect_port()
            
        if self.port:
            try:
                self.serial = serial.Serial(self.port, self.baudrate, timeout=1.0)
                time.sleep(2) # Wait for Arduino auto-reset
                self.is_connected = True
                self.running = True
                self.thread = threading.Thread(target=self._read_loop, daemon=True)
                self.thread.start()
                print(f"[ArduinoBridge] Connected to Arduino on {self.port}")
                return True
            except Exception as e:
                print(f"[ArduinoBridge] Failed to open port {self.port}: {e}")
                
        print("[ArduinoBridge] No physical Arduino detected. Operating in Standalone Simulation Mode.")
        self.is_connected = False
        return False

    def _read_loop(self):
        while self.running and self.serial and self.serial.is_open:
            try:
                line = self.serial.readline().decode('utf-8', errors='ignore').strip()
                if line:
                    if line == "TRIGGER":
                        if self.on_trigger_callback:
                            self.on_trigger_callback()
                    elif line == "ARDUINO_READY":
                        print("[ArduinoBridge] Arduino reported READY.")
            except Exception as e:
                print(f"[ArduinoBridge] Read error: {e}")
                break

    def send_verdict(self, verdict):
        """Sends 'PASS' or 'FAIL' command to Arduino."""
        if self.is_connected and self.serial and self.serial.is_open:
            try:
                msg = f"{verdict.upper()}\n"
                self.serial.write(msg.encode('utf-8'))
                self.serial.flush()
                return True
            except Exception as e:
                print(f"[ArduinoBridge] Failed to send verdict: {e}")
                return False
        return False

    def close(self):
        self.running = False
        if self.serial and self.serial.is_open:
            self.serial.close()
            self.is_connected = False
