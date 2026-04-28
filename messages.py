# 这里是消息类型，报数等判定
from utils import translate_location, format_latlon

def generate_warning_content(raw_data):
    typ = raw_data.get("type", "")
    if typ == 'cn_eew':
        prefix = "中国地震预警"
    elif typ == 'sc_eew':
        prefix = "四川地震预警"
    elif typ == 'fj_eew':
        prefix = "福建地震预警"
    elif typ == 'icl_eew':
        prefix = "大陆地震预警"
    elif typ == 'cwa_eew':
        prefix = "中央气象署预警"
    elif typ == 'sa_eew':
        prefix = "ShakeAlert预警"
    elif typ == 'jma_eew':
        prefix = "JMA地震预警"
    else:
        prefix = "地震预警"

    if raw_data.get("isfinal"):
        report_text = "(最终报)"
    else:
        report_num = raw_data.get("report_num", "")
        report_text = f"(第{report_num}报)" if report_num != "" else "(不明报)"

    hypocenter = raw_data.get("hypocenter", "未知")
    if typ == "sa_eew":
        try:
            hypocenter = translate_location(hypocenter)
        except Exception:
            pass

    lat = raw_data.get("latitude")
    lon = raw_data.get("longitude")
    latlon_txt = format_latlon(lat, lon)

    magnitude = raw_data.get("magnitude", "")
    depth = raw_data.get("depth", "")
    maxintensity = raw_data.get("maxintensity", "")
    maxshindo = raw_data.get("maxshindo", "")
    happen_time = raw_data.get("happen_time", "")

    content = (f"{prefix}{report_text} 震源:{hypocenter}{latlon_txt} 震级:M{magnitude} 深度:{depth}km ")
    if typ == 'cwa_eew' or typ == 'jma_eew':
        content += f"预估最大震度:{maxshindo} "
    else:
        content += f"预估最大烈度:{maxintensity} "

    if typ == 'jma_eew':
        ext = raw_data.get("ext", {}) or {}
        if ext.get("maxlg") is not None:
            content += f"预估长周期地震动阶级:{ext.get('maxlg')} "
        if raw_data.get("iswarn"):
            warnpref = ext.get("warnprefecture")
            warnzone = ext.get("warnzone")
            if warnpref:
                if isinstance(warnpref, list) and len(warnpref) > 10 and warnzone:
                    content += "警报区域:" + " ".join(warnzone) + " "
                else:
                    if isinstance(warnpref, list):
                        content += "警报区域:" + " ".join(warnpref) + " "
                    else:
                        content += f"警报区域:{warnpref} "
        else:
            warnarea = ext.get("warnarea")
            strong_shindo_set = {"4", "5-", "5+", "6-", "6+", "7"}
            if warnarea and (str(raw_data.get("maxshindo")) in strong_shindo_set):
                if isinstance(warnarea, list):
                    area_names = []
                    for a in warnarea:
                        if isinstance(a, dict):
                            area_names.append(a.get("area", ""))
                        else:
                            area_names.append(str(a))
                    content += "强震区域:" + " ".join([n for n in area_names if n]) + " "

    content += f"发生时间:{happen_time}"
    return content

def generate_report_content(typ, raw_msg, eq):
    hypocenter = eq.get("hypocenter") or raw_msg.get("hypocenter") or "未知"
    magnitude = eq.get("magnitude") or raw_msg.get("magnitude") or ""
    depth = eq.get("depth") or raw_msg.get("depth") or ""
    happen_time = eq.get("happen_time") or raw_msg.get("happen_time") or ""
    maxintensity = eq.get("maxintensity") or raw_msg.get("maxintensity") or ""
    maxshindo = eq.get("maxshindo") or raw_msg.get("maxshindo") or ""
    lat = eq.get("latitude") if eq.get("latitude") is not None else raw_msg.get("latitude")
    lon = eq.get("longitude") if eq.get("longitude") is not None else raw_msg.get("longitude")
    latlon_txt = format_latlon(lat, lon)

    if typ == "cenc_eqlist":
        flag = eq.get("flag") or raw_msg.get("flag") or ""
        if flag == "A":
            content = (f"中国地震台网(自动测定) 发生时间:{happen_time} 震源:{hypocenter}附近{latlon_txt} "
                       f"震级:M{magnitude}左右 深度:约{depth}km 预估最大烈度:{maxintensity} 最终结果请以正式速报为准")
        else:
            content = (f"中国地震台网(正式测定) 发生时间:{happen_time} 震源:{hypocenter}{latlon_txt} "
                       f"震级:M{magnitude} 深度:{depth}km 预估最大烈度:{maxintensity}")
        return content

    elif typ == "cwa_eqlist":
        content = (f"中央气象署地震情报 发生时间:{happen_time} 震源:{hypocenter}{latlon_txt} "
                   f"震级:M{magnitude} 深度:{depth}km 最大震度:{maxshindo}")
        return content

    elif typ == "jma_eqlist":
        ext = (eq.get("ext") if isinstance(eq, dict) else None) or raw_msg.get("ext", {}) or {}
        title = ext.get("title", "")
        comment = ext.get("comment", "")
        content = (f"日本{title} 发生时间:{happen_time} 震源:{hypocenter}{latlon_txt} "
                   f"震级:M{magnitude} 深度:{depth}km 最大震度:{maxshindo} 津波情报:{comment}")
        return content

    elif typ == "jma_lglist":
        eq_ext = (eq.get("ext") if isinstance(eq, dict) else None) or raw_msg.get("ext", {}) or {}
        maxlgint = eq.get("maxlgint") or raw_msg.get("maxlgint") or ""
        title = eq_ext.get("title", "")
        content = (f"日本{title} 发生时间:{happen_time} 震源:{hypocenter}{latlon_txt} "
                   f"震级:M{magnitude} 深度:{depth}km 最大长周期地震动阶级:{maxlgint}")
        return content

    else:
        # 禁止把原始 JSON 当字幕兜底
        return None