# sa地名翻译和东西经、北南纬的判定等（这块写的很shit）
import math
from datetime import datetime
import requests
import hashlib

# 注意：如果你要换翻译服务，把 URL / key 放到配置中更灵活
TRANSLATE_API = ("https://api.tjit.net/api/fanyi/?key=请输入key"
                 "&text=TEXT&from=auto&to=zh")

def translate_location(location):
    try:
        if not location:
            return location
        url = TRANSLATE_API.replace("TEXT", requests.utils.requote_uri(location))
        r = requests.get(url, timeout=5)
        data = r.json()
        if data.get("code") == 200 and data.get("data") and data["data"].get("trans_result"):
            return data["data"]["trans_result"][0]["dst"]
    except Exception:
        pass
    return location

def format_latlon(latitude, longitude):
    try:
        if latitude is None or longitude is None:
            return ""
        lat = float(latitude)
        lon = float(longitude)
        lat_dir = '北纬' if lat >= 0 else '南纬'
        lon_dir = '东经' if lon >= 0 else '西经'
        return f"({lat_dir}{abs(lat):.2f}度，{lon_dir}{abs(lon):.2f}度)"
    except Exception:
        return ""

def haversine_km(lat1, lon1, lat2, lon2):
    try:
        lat1, lon1, lat2, lon2 = map(float, [lat1, lon1, lat2, lon2])
    except Exception:
        return float('inf')
    R = 6371.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    return R * c

def stable_md5_hash(s):
    if s is None:
        s = ""
    return hashlib.md5(str(s).encode("utf-8")).hexdigest()

def is_same_cenc_event(eq_new, eq_old, cfg):
    """
    仅用于 cenc_eqlist 的兜底判断。
    使用 report_time 进行时间比对。
    若缺 report_time 或经纬度则保守不合并（返回 False）。
    """
    try:
        time_win = int(cfg.get("group_time_window", 300))
        dist_km = float(cfg.get("group_distance_km", 50))

        rt_new = eq_new.get("report_time") or ""
        rt_old = eq_old.get("report_time") or ""
        if not rt_new or not rt_old:
            return False

        try:
            t_new = datetime.strptime(rt_new, "%Y-%m-%d %H:%M:%S").timestamp()
            t_old = datetime.strptime(rt_old, "%Y-%m-%d %H:%M:%S").timestamp()
        except Exception:
            return False

        if abs(t_new - t_old) > time_win:
            return False

        lat_new = eq_new.get("latitude")
        lon_new = eq_new.get("longitude")
        lat_old = eq_old.get("latitude")
        lon_old = eq_old.get("longitude")
        if lat_new is None or lon_new is None or lat_old is None or lon_old is None:
            return False

        d = haversine_km(lat_new, lon_new, lat_old, lon_old)
        return d <= dist_km
    except Exception:
        return False