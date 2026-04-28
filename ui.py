# 这里是ui风格设定
import sys
import json
import time
from collections import OrderedDict
from datetime import datetime

from PyQt6.QtWidgets import *
from PyQt6.QtGui import *
from PyQt6.QtCore import *

from eew_config import load_config, save_config
from websocket_thread import NQWebSocket
from utils import haversine_km, format_latlon, is_same_cenc_event, stable_md5_hash
from messages import generate_warning_content, generate_report_content

class SettingsDialog(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle("设置")
        self.setFixedSize(420, 460)
        layout = QFormLayout(self)

        self.setStyleSheet("""
            QDialog { background-color: white; }
            QLabel { color: black; background: transparent; }
            QLineEdit, QSpinBox, QPushButton { background-color: white; color: black; border: 1px solid #aaa; }
            QSpinBox::up-button, QSpinBox::down-button { background-color: #f6f6f6; border: 1px solid #ccc; }
            QPushButton { padding: 4px 8px; }
        """)
        cfg = parent.config

        self.token_input = QLineEdit(cfg.get("token", ""))
        layout.addRow("WebSocket Token:", self.token_input)

        self.lifetime_input = QSpinBox()
        self.lifetime_input.setRange(1, 3600)
        self.lifetime_input.setValue(cfg.get("lifetime", 300))
        self.lifetime_input.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
        layout.addRow("地震信息有效期(秒/s):", self.lifetime_input)

        self.default_text = QLineEdit(cfg.get("default_text", "当前没有地震信息"))
        layout.addRow("默认字幕文本(白色):", self.default_text)

        self.font_size_input = QSpinBox()
        self.font_size_input.setRange(8, 72)
        self.font_size_input.setValue(cfg.get("font_size", 24))
        self.font_size_input.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
        layout.addRow("字幕字体大小:", self.font_size_input)

        self.window_width_input = QSpinBox()
        self.window_width_input.setRange(200, 3840)
        self.window_width_input.setValue(cfg.get("window_width", 800))
        self.window_width_input.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
        layout.addRow("窗口宽度:", self.window_width_input)

        self.window_height_input = QSpinBox()
        self.window_height_input.setRange(40, 800)
        self.window_height_input.setValue(cfg.get("window_height", 80))
        self.window_height_input.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
        layout.addRow("窗口高度:", self.window_height_input)

        self.scroll_speed_input = QSpinBox()
        self.scroll_speed_input.setRange(1, 40)
        self.scroll_speed_input.setValue(cfg.get("scroll_speed", 2))
        self.scroll_speed_input.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
        layout.addRow("字幕滚动速度:", self.scroll_speed_input)

        self.strong_color = QLineEdit(cfg.get("strong_color", "#FF0000"))
        layout.addRow("强有感颜色 (HEX):", self.strong_color)
        self.medium_color = QLineEdit(cfg.get("medium_color", "#FFFF00"))
        layout.addRow("有感颜色 (HEX):", self.medium_color)

        btn_layout = QHBoxLayout()
        save_btn = QPushButton("保存")
        save_btn.clicked.connect(lambda: self.save(parent))
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.close)
        btn_layout.addWidget(save_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addRow(btn_layout)

    def save(self, parent):
        parent.config["token"] = self.token_input.text().strip()
        parent.config["lifetime"] = int(self.lifetime_input.value())
        parent.config["default_text"] = self.default_text.text()
        parent.config["font_size"] = int(self.font_size_input.value())
        parent.config["window_width"] = int(self.window_width_input.value())
        parent.config["window_height"] = int(self.window_height_input.value())
        parent.config["scroll_speed"] = int(self.scroll_speed_input.value())
        parent.config["strong_color"] = self.strong_color.text().strip() or "#FF0000"
        parent.config["medium_color"] = self.medium_color.text().strip() or "#FFFF00"
        save_config(parent.config)
        parent.apply_settings(user_saved=True)
        self.close()

class LogDialog(QDialog):
    def __init__(self, logs):
        super().__init__()
        self.setWindowTitle("日志")
        self.setFixedSize(700, 420)
        self.setStyleSheet("""
            QDialog { background-color: white; }
            QTextEdit { background-color: white; color: black; }
            QLabel { color: black; background: transparent; }
        """)
        layout = QVBoxLayout(self)
        self.text_edit = QTextEdit()
        self.text_edit.setReadOnly(True)
        layout.addWidget(self.text_edit)
        for l in logs:
            self.text_edit.append(l)

class TickerWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.config = load_config()
        self.active_events = OrderedDict()
        self.log_messages = []
        self.scroll_pos = 0
        self.default_text = self.config.get("default_text", "当前没有地震信息")
        self.default_color = "#FFFFFF"
        self.scroll_speed = int(self.config.get("scroll_speed", 2))
        self.colors = {
            "strong": self.config.get("strong_color", "#FF0000"),
            "medium": self.config.get("medium_color", "#FFFF00"),
        }
        self.ws_state = "disconnected"

        self.setWindowTitle("地震信息滚动字幕")
        self.setStyleSheet("background-color: black;")
        self.apply_settings(init=True)

        self.ws_thread = NQWebSocket(self)
        self.ws_thread.message_signal.connect(self.on_message)
        self.ws_thread.state_signal.connect(self.set_ws_state)
        self.ws_thread.start()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.check_expired)
        self.timer.start(1000)
        self.scroll_timer = QTimer(self)
        self.scroll_timer.timeout.connect(self.scroll_tick)
        self.scroll_timer.start(20)

        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self.menu)

    def apply_settings(self, init=False, user_saved=False):
        # reload config
        self.config = load_config()
        w = int(self.config.get("window_width", 800))
        h = int(self.config.get("window_height", 80))
        self.setFixedSize(w, h)

        # 同步 default_text
        self.default_text = self.config.get("default_text", self.default_text)

        if not hasattr(self, "label") or init:
            self.label = QLabel(self.default_text, self)
            self.label.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
            self.label.setStyleSheet("background: transparent; color: " + self.default_color + ";")
            self.label.setFont(QFont("Courier New", int(self.config.get("font_size", 24))))
        else:
            self.label.setFont(QFont("Courier New", int(self.config.get("font_size", 24))))

        self.label.setGeometry(0, 10, w * 2, h - 20)

        if init or user_saved:
            self.scroll_pos = w

        self.scroll_speed = int(self.config.get("scroll_speed", 2))
        self.colors["strong"] = self.config.get("strong_color", self.colors["strong"])
        self.colors["medium"] = self.config.get("medium_color", self.colors["medium"])

        if not hasattr(self, "ws_indicator"):
            self.ws_indicator = QLabel(self)
            self.ws_indicator.setFixedSize(10, 10)
            self.ws_indicator.setStyleSheet("background-color: red; border-radius: 5px;")
            self.ws_indicator.show()
        self.ws_indicator.move(self.width() - 20, 10)

        # 若没有活动事件，立即显示默认文本信息and保持白色
        if not self.active_events:
            self.label.setText(self.default_text)
            self.label.setStyleSheet("background: transparent; color: " + self.default_color + ";")

    def resizeEvent(self, event):
        if hasattr(self, "label"):
            self.label.setGeometry(0, 10, self.width() * 2, self.config.get("window_height", 80) - 20)
        if hasattr(self, "ws_indicator"):
            self.ws_indicator.move(self.width() - 20, 10)
        super().resizeEvent(event)

    def menu(self, pos):
        m = QMenu(self)
        m.setStyleSheet("""
            QMenu { background-color: white; color: black; }
            QMenu::item { background-color: white; color: black; }
            QMenu::item:selected { background-color: #e6e6e6; }
        """)
        set_action = m.addAction("设置")
        log_action = m.addAction("消息日志")
        act = m.exec(self.mapToGlobal(pos))
        if act == set_action:
            dlg = SettingsDialog(self)
            dlg.exec()
        elif act == log_action:
            dlg = LogDialog(self.log_messages)
            dlg.exec()

    def set_ws_state(self, state):
        self.ws_state = state
        color_map = {"connected": "green", "connecting": "yellow", "disconnected": "red"}
        col = color_map.get(state, "red")
        self.ws_indicator.setStyleSheet(f"background-color: {col}; border-radius: 5px;")

    def make_event_key_eew(self, raw):
        v = raw.get("event_id") or raw.get("eventId") or raw.get("event_id_only")
        if v:
            return str(v)
        return None

    def on_message(self, data):
        typ = data.get("type", "")
        ALLOWED_TYPES = {
            "cn_eew", "sc_eew", "fj_eew", "icl_eew",
            "cwa_eew", "sa_eew", "jma_eew",
            "cenc_eqlist", "cwa_eqlist", "jma_eqlist", "jma_lglist"
        }

        if not typ:
            return

        try:
            self.log_messages.append(json.dumps(data, ensure_ascii=False))
        except Exception:
            pass

        if typ not in ALLOWED_TYPES:
            return

        self.colors["strong"] = self.config.get("strong_color", self.colors["strong"])
        self.colors["medium"] = self.config.get("medium_color", self.colors["medium"])

        EEW_TYPES = {"cn_eew", "sc_eew", "fj_eew", "icl_eew", "cwa_eew", "sa_eew", "jma_eew"}
        LIST_TYPES = {"cenc_eqlist", "cwa_eqlist", "jma_eqlist", "jma_lglist"}

        if typ in LIST_TYPES:
            items = data.get("data")
            if not isinstance(items, list) or not items:
                try:
                    self.log_messages.append(f"Expected non-empty list for {typ}. Ignored.")
                except Exception:
                    pass
                return

            eq = items[0]
            if not isinstance(eq, dict):
                return

            if eq.get("iscancel") or eq.get("is_cancel") or eq.get("cancel"):
                event_key = None
                if typ in ("jma_eqlist", "jma_lglist", "cwa_eqlist", "cenc_eqlist"):
                    eqid2 = eq.get("eq_id2") or eq.get("eq_id") or eq.get("eq_serial")
                    if eqid2:
                        event_key = f"{typ}_{str(eqid2)}"
                    else:
                        if typ == "cenc_eqlist":
                            for k, v in list(self.active_events.items()):
                                if not k.startswith("cenc_eqlist_"):
                                    continue
                                raw_eq = v.get("raw_eq")
                                if raw_eq and is_same_cenc_event(eq, raw_eq, self.config):
                                    event_key = k
                                    break
                if event_key and event_key in self.active_events:
                    try:
                        del self.active_events[event_key]
                        self.log_messages.append(f"取消预警(即时移除): {event_key}")
                    except Exception:
                        pass
                else:
                    try:
                        self.log_messages.append(f"收到取消但事件不存在 / 未匹配: {typ} {eq.get('eq_id2') or eq.get('eq_serial')}")
                    except Exception:
                        pass
                return

            event_key = None
            merged_by_spacetime = False
            if typ in ("jma_eqlist", "jma_lglist", "cwa_eqlist"):
                eqid2 = eq.get("eq_id2") or eq.get("eq_id") or eq.get("eq_serial")
                if not eqid2:
                    try:
                        self.log_messages.append(f"Missing eq_id2/eq_serial for {typ}; ignored.")
                    except Exception:
                        pass
                    return
                event_key = f"{typ}_{str(eqid2)}"
            elif typ == "cenc_eqlist":
                eqid2 = eq.get("eq_id2") or eq.get("eq_id")
                if eqid2:
                    event_key = f"{typ}_{str(eqid2)}"
                else:
                    matched = None
                    for k, v in list(self.active_events.items()):
                        if not k.startswith("cenc_eqlist_"):
                            continue
                        raw_eq = v.get("raw_eq")
                        if raw_eq and is_same_cenc_event(eq, raw_eq, self.config):
                            matched = k
                            break
                    if matched:
                        event_key = matched
                        merged_by_spacetime = True
                        try:
                            self.log_messages.append(f"时空合并: 新消息合并到已有事件 {matched}")
                        except Exception:
                            pass
                    else:
                        report_t = eq.get("report_time") or ""
                        hypoc = eq.get("hypocenter") or ""
                        # 使用稳定 md5 哈希替代 Python 内置 hash
                        event_key = f"{typ}_{report_t}_{stable_md5_hash(hypoc)}"

            try:
                content = generate_report_content(typ, data, eq)
            except Exception as e:
                try:
                    self.log_messages.append(f"generate_report_content error: {str(e)}")
                except Exception:
                    pass
                content = None

            if not content:
                return
            # 强有感判定for地震情报（写的一坨屎别看了）
            color = self.colors.get("medium")
            try:
                if typ == "cenc_eqlist":
                    if int(eq.get("maxintensity", data.get("maxintensity", 0))) >= 7:
                        color = self.colors.get("strong")
                elif typ == "cwa_eqlist":
                    if eq.get("maxshindo") in ["5-", "5+", "6-", "6+", "7"]:
                        color = self.colors.get("strong")
                elif typ == "jma_eqlist":
                    if eq.get("maxshindo") in ["5-", "5+", "6-", "6+", "7"]:
                        color = self.colors.get("strong")
                elif typ == "jma_lglist":
                    maxlgint_val = str(eq.get("maxlgint") or data.get("maxlgint") or "")
                    if maxlgint_val in ["3", "4"]:
                        color = self.colors.get("strong")
            except Exception:
                pass

            lat = None
            lon = None
            try:
                lat = float(eq.get("latitude")) if eq.get("latitude") is not None else None
                lon = float(eq.get("longitude")) if eq.get("longitude") is not None else None
            except Exception:
                lat = None
                lon = None

            ts = time.time()
            rpt = eq.get("report_time") or data.get("report_time") or ""
            if rpt:
                try:
                    ts = datetime.strptime(rpt, "%Y-%m-%d %H:%M:%S").timestamp()
                except Exception:
                    ts = time.time()
            else:
                ts = time.time()

            raw_eq_copy = dict(eq) if isinstance(eq, dict) else {}

            if event_key in self.active_events:
                self.active_events[event_key].update({
                    "text": content,
                    "timestamp": ts,
                    "color": color,
                    "type": typ,
                    "lat": lat,
                    "lon": lon,
                    "raw_eq": raw_eq_copy
                })
                try:
                    self.log_messages.append(f"更新事件: {event_key}")
                except Exception:
                    pass
            else:
                self.active_events[event_key] = {
                    "text": content,
                    "timestamp": ts,
                    "color": color,
                    "type": typ,
                    "lat": lat,
                    "lon": lon,
                    "raw_eq": raw_eq_copy
                }
                try:
                    if merged_by_spacetime:
                        pass
                    else:
                        self.log_messages.append(f"新增事件: {event_key}")
                except Exception:
                    pass

        elif typ in EEW_TYPES:
            raw = data
            event_key = self.make_event_key_eew(raw)
            if not event_key:
                try:
                    self.log_messages.append(f"Missing event_id for EEW {typ}; ignored.")
                except Exception:
                    pass
                return

            if raw.get("iscancel") or raw.get("is_cancel") or raw.get("cancel"):
                if event_key in self.active_events:
                    try:
                        del self.active_events[event_key]
                        self.log_messages.append(f"取消预警(即时移除): {event_key}")
                    except Exception:
                        pass
                else:
                    try:
                        self.log_messages.append(f"收到取消但事件不存在: {event_key}")
                    except Exception:
                        pass
                return

            try:
                content = generate_warning_content(raw)
            except Exception as e:
                try:
                    self.log_messages.append(f"generate_warning_content error: {str(e)}")
                except Exception:
                    pass
                content = None

            if not content:
                return

            # 强有感判定for EEW（写的一坨屎别看了）
            strong = False
            try:
                if typ == "jma_eew" and raw.get("iswarn"):
                    if raw.get("maxshindo") in ["4", "5-", "5+", "6-", "6+", "7"]:
                        strong = True
                elif typ == "cwa_eew":
                    if raw.get("maxshindo") in ["5-", "5+", "6-", "6+", "7"]:
                        strong = True
                elif typ in ["cn_eew", "sc_eew", "fj_eew", "icl_eew","sa_eew"]:
                    if int(raw.get("maxintensity", 0)) >= 7:
                        strong = True
            except Exception:
                pass

            color = self.colors.get("strong") if strong else self.colors.get("medium")
            msg = {"text": content, "timestamp": time.time(), "color": color, "type": typ, "event_key": event_key}

            if event_key in self.active_events:
                self.active_events[event_key].update({
                    "text": msg["text"],
                    "timestamp": msg["timestamp"],
                    "color": msg["color"],
                    "type": msg.get("type")
                })
                try:
                    self.log_messages.append(f"更新事件: {event_key}")
                except Exception:
                    pass
            else:
                self.active_events[event_key] = {
                    "text": msg["text"],
                    "timestamp": msg["timestamp"],
                    "color": msg["color"],
                    "type": msg.get("type")
                }
                try:
                    self.log_messages.append(f"新增事件: {event_key}")
                except Exception:
                    pass

    def check_expired(self):
        lifetime = int(self.config.get("lifetime", 300))
        now = time.time()
        removed = []
        for k, v in list(self.active_events.items()):
            if now - v.get("timestamp", now) >= lifetime:
                removed.append(k)
                try:
                    del self.active_events[k]
                except Exception:
                    pass
        if removed:
            try:
                self.log_messages.append(f"过期移除: {removed}")
            except Exception:
                pass
        if not self.active_events:
            self.label.setText(self.default_text)
            self.label.setStyleSheet("background: transparent; color: " + self.default_color + ";")

    def scroll_tick(self):
        self.scroll_pos -= int(self.scroll_speed)
        if self.active_events:
            display_text = "  |  ".join([v["text"] for v in self.active_events.values()])
        else:
            display_text = self.default_text

        fm = self.label.fontMetrics()
        text_width = fm.horizontalAdvance(display_text) + 20
        self.label.resize(max(text_width, 10), max(self.label.height(), 10))
        self.label.setText(display_text)

        if any(v.get("color") == self.colors.get("strong") for v in self.active_events.values()):
            color = self.colors.get("strong")
        elif self.active_events:
            color = self.colors.get("medium")
        else:
            color = self.default_color
        self.label.setStyleSheet("background: transparent; color: " + color + ";")

        if self.scroll_pos + self.label.width() < 0:
            self.scroll_pos = self.width()
        self.label.move(self.scroll_pos, 10)

    def closeEvent(self, event):
        try:
            self.ws_thread.stop()
        except Exception:
            pass
        event.accept()