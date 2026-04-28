# 这里是设置的配置
import json

CONFIG_FILE = "eew_config.json"

def load_config():
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            cfg = json.load(f)
            defaults = {
                "token": "",
                "lifetime": 300,
                "default_text": "当前没有地震信息",
                "font_size": 24,
                "window_width": 800,
                "window_height": 80,
                "scroll_speed": 2,
                "strong_color": "#FF0000",
                "medium_color": "#FFFF00",
                # 时空阈值
                "group_time_window": 300,
                "group_distance_km": 50
            }
            for k, v in defaults.items():
                if k not in cfg:
                    cfg[k] = v
            return cfg
    except Exception:
        return {
            "token": "",
            "lifetime": 300,
            "default_text": "当前没有地震信息",
            "font_size": 24,
            "window_width": 800,
            "window_height": 80,
            "scroll_speed": 2,
            "strong_color": "#FF0000",
            "medium_color": "#FFFF00",
            "group_time_window": 300,
            "group_distance_km": 50
        }

def save_config(cfg):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)