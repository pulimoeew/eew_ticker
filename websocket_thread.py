# 这里是ws连接设定
import time
import json
import threading
import websocket

from PyQt6.QtCore import QThread, pyqtSignal

class NQWebSocket(QThread):
    message_signal = pyqtSignal(dict)
    state_signal = pyqtSignal(str)

    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.running = True
        self.ws = None
        self._lock = threading.Lock()

    def run(self):
        while self.running:
            token = self.parent.config.get("token", "").strip()
            if not token:
                self.state_signal.emit("disconnected")
                for _ in range(10):
                    if not self.running:
                        break
                    time.sleep(0.5)
                continue

            url = f"请输入API/?token={token}"
            self.state_signal.emit("connecting")
            try:
                with self._lock:
                    self.ws = websocket.WebSocketApp(
                        url,
                        on_message=lambda ws, msg: self.on_msg(msg),
                        on_open=lambda ws: self.state_signal.emit("connected"),
                        on_close=lambda ws: self.state_signal.emit("disconnected"),
                        on_error=lambda ws, e: self.state_signal.emit("disconnected")
                    )
                self.ws.run_forever(ping_interval=30, ping_timeout=10)
            except Exception:
                self.state_signal.emit("disconnected")
            finally:
                with self._lock:
                    try:
                        if self.ws:
                            try:
                                self.ws.close()
                            except Exception:
                                pass
                    finally:
                        self.ws = None

            if not self.running:
                break
            for _ in range(10):
                if not self.running:
                    break
                time.sleep(0.5)

    def stop(self):
        self.running = False
        with self._lock:
            if self.ws:
                try:
                    self.ws.keep_running = False
                    self.ws.close()
                except Exception:
                    pass
        try:
            self.wait(2000)
        except Exception:
            pass

    def on_msg(self, msg):
        try:
            data = json.loads(msg)
            if data.get("type") != "heartbeat":
                self.message_signal.emit(data)
        except Exception:
            pass