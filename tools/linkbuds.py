#!/usr/bin/env python3
"""
LinkBuds S（WF-LS900N）等 v2 设备控制

与 v1 的区别：
  帧层完全相同（3E / 转义 / 4 字节长度 / 校验 / seq-ACK），连接方式相同（同一 Sony UUID）
  v2 握手多一步 `06 00`（GET_SUPPORT_FUNCTION）——缺它后面的族一律不响应
  命令字节含义不同：
      电量   22 <type>   00=整体 01=左右 02=充电盒
      降噪   66/68 17    [状态][总开关][NC模式][环境声模式][等级]
      均衡   56/58 00
      型号   04 01（普通串）而非 04 00

用法:
  python linkbuds.py status
  python linkbuds.py anc on|off|ambient
  python linkbuds.py level 0-20
  python linkbuds.py focus on|off
  python linkbuds.py eq off|bass|vocal|...          EQ 预设
  python linkbuds.py eqbands 3 0 0 0 0 0          自定义 6 段（-10..10）
  python linkbuds.py battery
  python linkbuds.py version          固件版本 + 系列
  python linkbuds.py stc on|off       智能对话（Speak-to-Chat）
  python linkbuds.py keys show                         左右耳当前预设
  python linkbuds.py keys left:playback                改左耳（volume/playback/quick_ambient/none）
  python linkbuds.py keys right:quick_ambient          改右耳
  python linkbuds.py keys both:none                    双耳
  python linkbuds.py dsee auto|off     DSEE Extreme
  python linkbuds.py quality hifi|stable   连接模式（音质/稳定）
  python linkbuds.py apo takenoff|off  自动断电（仅两态）
  python linkbuds.py voice on|off      通知和语音向导（T2）
  python linkbuds.py stc-ext [auto|high|low] [fast|mid|slow]   智能对话灵敏度/退出时间
  python linkbuds.py multi            多点连接（只读）
  python linkbuds.py sys             SYSTEM 族状态（按键分配/佩带检测/智能对话等）
"""
import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tandem_client as tc

MAC = os.environ.get("SONY_MAC", "")     # LinkBuds S
CHANNEL = 9                   # 实测：SDP 解析失败，必须写死通道
CODECS = {0x00: "unknown", 0x01: "SBC", 0x02: "AAC", 0x10: "LDAC",
          0x20: "aptX", 0x21: "aptX HD"}
MODES = {0x00: "降噪", 0x01: "环境声"}
EQ_PRESETS = {"off": 0x00, "bright": 0x10, "excited": 0x11, "mellow": 0x12,
              "relaxed": 0x13, "vocal": 0x14, "treble": 0x15, "bass": 0x16,
              "speech": 0x17}


def connect(mac=MAC, channel=CHANNEL):
    """v2 握手：INIT(重试) -> CAPABILITY -> SUPPORT_FUNCTION"""
    c = tc.Client(mac, channel)
    init = None
    for _ in range(5):
        init = c.request(b"\x00\x00", wait=2.5)
        if init:
            break
        time.sleep(0.8)
    if not init:
        raise OSError("INIT 无响应")
    if len(init) != 8:
        raise OSError(f"不是 v2 设备（INIT {len(init)} 字节）")
    c.request(b"\x02\x00", wait=2.0)
    time.sleep(0.3)
    c.request(b"\x06\x00", wait=2.0)
    time.sleep(0.3)
    return c


def xfer(c, payload, want=None, wait=2.5):
    """发送并主动收流。不能用 request()：v2 会同时推 a5/a9 播放信息，混在同一流里。"""
    want = (payload[0] | 0x01) if want is None else want
    c._send(tc.T1, payload)
    t_end = time.time() + wait
    while time.time() < t_end:
        for p, raw in c._read(0.4):
            if p["type"] == tc.ACK:
                continue
            c._send(tc.ACK, b"", seq=p["seq"] ^ 1)
            pl = p["payload"]
            if pl and pl[0] == want:
                return pl
    return None


# ---------------- 电池 ----------------

def read_battery(c):
    out = {}
    r = xfer(c, bytes([0x22, 0x00]))
    if r and len(r) >= 3:
        out["整体"] = r[2]
    r = xfer(c, bytes([0x22, 0x01]))
    if r and len(r) >= 5:
        out["左"] = r[2]
        out["右"] = r[4]
    r = xfer(c, bytes([0x22, 0x02]))
    if r and len(r) >= 3:
        out["充电盒"] = r[2]
    return out


# ---------------- 降噪 ----------------
# 66/68 17 的载荷：[command][0x17][变更状态][总开关][NC模式][环境声模式][等级]
#   变更状态 00=渐变中 01=已完成
#   总开关   00=关闭处理 01=开启
#   NC模式   00=降噪 01=环境声
#   环境声模式 00=普通 01=关注语音
def read_anc(c):
    r = xfer(c, bytes([0x66, 0x17]))
    if r and len(r) >= 7:
        return {"effect": r[3], "mode": r[4], "focus": r[5], "level": r[6]}
    return None


def set_anc(c, mode=None, level=None, focus=None):
    cur = read_anc(c)
    if not cur:
        return None
    effect = cur["effect"]
    m = cur["mode"] if mode is None else mode
    f = cur["focus"] if focus is None else focus
    lv = cur["level"] if level is None else level
    if mode is not None:
        effect = 0x01
    p = bytes([0x68, 0x17, 0x01, effect, m, f, max(0, min(20, lv))])
    xfer(c, p)
    time.sleep(0.9)
    return read_anc(c)


def set_off(c):
    """关闭降噪处理（总开关置 0），保留模式与等级"""
    cur = read_anc(c)
    if not cur:
        return None
    p = bytes([0x68, 0x17, 0x01, 0x00, cur["mode"], cur["focus"], cur["level"]])
    xfer(c, p)
    time.sleep(0.9)
    return read_anc(c)


# ---------------- 均衡 / 信息 ----------------

def read_eq(c):
    r = xfer(c, bytes([0x56, 0x00]))
    if r and len(r) >= 10:
        return r[2], [b - 10 for b in r[4:10]]
    return None, None


def read_fw(c):
    """固件版本：04 02 -> 05 02 <len> <ascii>"""
    r = xfer(c, bytes([0x04, 0x02]))
    if r and len(r) >= 3 and r[1] == 0x02:
        return r[3:3 + r[2]].decode("ascii", "replace")
    return None


# --- CONNECT_GET_DEVICE_INFO / SERIES_AND_COLOR_INFO (0x04 0x03) -----------
# ModelColor enum from SonyHeadphonesClient/libmdr ProtocolV2.hpp. Codes
# 0x11..0x1E are the "_I" (second-generation) variants of 0x01..0x0E.
# Verified on the user's white WF-LS900N: 04 03 -> 05 03 60 02, i.e.
# series LINK_BUDS (0x60) + ModelColor.WHITE (0x02).
MODEL_COLORS = {
    0x00: ("默认", "DEFAULT", ""),
    0x01: ("黑色", "BLACK", "b"),
    0x02: ("白色", "WHITE", "w"),
    0x03: ("银色", "SILVER", "s"),
    0x04: ("红色", "RED", "r"),
    0x05: ("蓝色", "BLUE", "l"),
    0x06: ("粉色", "PINK", "p"),
    0x07: ("黄色", "YELLOW", "y"),
    0x08: ("绿色", "GREEN", "g"),
    0x09: ("灰色", "GRAY", "gray"),
    0x0A: ("金色", "GOLD", "gold"),
    0x0B: ("奶油色", "CREAM", "cream"),
    0x0C: ("橙色", "ORANGE", "orange"),
    0x0D: ("棕色", "BROWN", "brown"),
    0x0E: ("紫色", "VIOLET", "violet"),
}
SERIES_NAMES = {0x60: "LinkBuds"}


def parse_series_color(r, protocol="v2"):
    """Decode a SERIES_AND_COLOR_INFO reply into a display-ready dict.

    v2: 05 03 <series> <color>   (4 bytes)
    v1: 05 03 <color>            (3 bytes, no series field)
    Returns None when the reply is not a colour reply, so callers can degrade
    gracefully on a headset that does not implement this device-info type.
    """
    if not r or len(r) < 3 or r[0] != 0x05 or r[1] != 0x03:
        return None
    if len(r) >= 4:
        series, code = r[2], r[3]
    else:
        series, code = None, r[2]
    variant = ""
    base = code
    if 0x11 <= code <= 0x1E:
        base, variant = code - 0x10, "_I"
    name, en, suffix = MODEL_COLORS.get(base, ("未知", "UNKNOWN", ""))
    series_name = (SERIES_NAMES.get(series, "0x%02x" % series)
                   if series is not None else "")
    raw = r.hex(" ")
    return {
        "code": code, "base": base, "name": name, "en": en,
        "variant": variant, "suffix": suffix,
        "series": series, "series_name": series_name,
        "raw": raw,
        "label": "%s (0x%02x)" % (name + (" I" if variant else ""), code),
        "instruction": "04 03 → " + raw,
        "enum": "ModelColor.%s%s" % (en, variant),
    }


def read_color(c):
    """颜色识别指令：04 03 -> 05 03 <series> <color>（v2）。"""
    return parse_series_color(xfer(c, bytes([0x04, 0x03]), wait=1.2))


def read_series(c):
    """系列与颜色（旧字符串形式，保留兼容）：04 03 -> 05 03 <series> <color>"""
    r = xfer(c, bytes([0x04, 0x03]))
    if r and len(r) >= 4 and r[1] == 0x03:
        return f"series=0x{r[2]:02x} color=0x{r[3]:02x}"
    return None


def set_eqbands(c, vals):
    """自定义 6 段 EQ：58 00 A0 06 <6 个值>，值 = 增益 + 10（范围 -10..10 → 0..20）"""
    vals = list(vals)[:6]
    while len(vals) < 6:
        vals.append(0)
    payload = bytes([0x58, 0x00, 0xA0, 0x06] + [max(0, min(20, v + 10)) for v in vals])
    xfer(c, payload)
    time.sleep(0.9)
    return read_eq(c)


def read_model(c):
    r = xfer(c, bytes([0x04, 0x01]))
    if r and len(r) >= 3 and r[1] == 0x01:
        return r[3:3 + r[2]].decode("ascii", "replace")
    return None


def read_codec(c):
    r = xfer(c, bytes([0x12, 0x02]))
    if r and len(r) >= 3:
        return CODECS.get(r[2], f"0x{r[2]:02x}")
    return None


def anc_text(a):
    if not a:
        return "?"
    if a["effect"] == 0:
        return "关闭处理"
    return MODES.get(a["mode"], f"0x{a['mode']:02x}")


SYS_NAMES = {0x00: "振动", 0x01: "佩戴播放控制", 0x02: "智能对话1", 0x03: "按键分配",
             0x04: "语音助手", 0x05: "唤醒词", 0x06: "佩戴检测", 0x07: "耳塞选择",
             0x08: "通话设置", 0x09: "重置", 0x0A: "自动音量", 0x0D: "快捷访问",
             0x0E: "按键分配(受限)", 0x0F: "头部手势"}


def read_dsee(c):
    """DSEE Extreme（AUDIO 族 UPSCALING）：E6 01 -> e7 01 <0=关|1=自动>"""
    r = xfer(c, bytes([0xE6, 0x01]))
    if r and len(r) >= 3:
        return r[2]
    return None


def set_dsee(c, auto):
    xfer(c, bytes([0xE8, 0x01, 0x01 if auto else 0x00]))
    time.sleep(0.8)
    return read_dsee(c)


def read_quality(c):
    """连接模式：E6 00 -> e7 00 <0=音质优先|1=稳定优先>"""
    r = xfer(c, bytes([0xE6, 0x00]))
    if r and len(r) >= 3:
        return r[2]
    return None


def set_quality(c, stable):
    xfer(c, bytes([0xE8, 0x00, 0x01 if stable else 0x00]))
    time.sleep(0.8)
    return read_quality(c)


APO = {0x10: "取下即关", 0x11: "关闭"}


def read_apo(c):
    """自动断电：26 04 -> 27 04 <current> <last>"""
    r = xfer(c, bytes([0x26, 0x04]))
    if r and len(r) >= 4:
        return r[2]
    return None


def set_apo(c, val):
    xfer(c, bytes([0x28, 0x04, val]))
    time.sleep(0.8)
    return read_apo(c)


SENS = {"auto": 0x00, "high": 0x01, "low": 0x02}
SENS_NAME = {v: k for k, v in SENS.items()}
OFFTIME = {"fast": 0x00, "mid": 0x01, "slow": 0x02}
OFFTIME_NAME = {v: k for k, v in OFFTIME.items()}


def t2_cmd(c, payload, want=None, wait=2.2):
    """Table#2（type 0x0E）命令。v2 的 T2 与 v1 分开，语音向导在这张表上。"""
    want = (payload[0] | 0x01) if want is None else want
    c._send(tc.T2, payload)
    t_end = time.time() + wait
    while time.time() < t_end:
        for p, raw in c._read(0.4):
            if p["type"] == tc.ACK:
                continue
            c._send(tc.ACK, b"", seq=p["seq"] ^ 1)
            pl = p["payload"]
            if pl and pl[0] == want:
                return pl
    return None


def set_voice(c, on):
    """通知和语音向导（T2 48 01 <val>）：00 = 开，01 = 关。注意方向是反的。"""
    r = t2_cmd(c, bytes([0x48, 0x01, 0x00 if on else 0x01]))
    return None if not r or len(r) < 3 else r[2] == 0x00


def set_stc_ext(c, sens=None, offtime=None):
    """智能对话扩展：FC 02 <灵敏度> <关注语音> <退出时间>；读 FA 02。"""
    r = xfer(c, bytes([0xFA, 0x02]))
    if not r or len(r) < 5:
        return None
    s0, f0, t0 = r[2], r[3], r[4]
    s1 = s0 if sens is None else SENS[sens]
    t1 = t0 if offtime is None else OFFTIME[offtime]
    xfer(c, bytes([0xFC, 0x02, s1, f0, t1]))
    time.sleep(0.8)
    r = xfer(c, bytes([0xFA, 0x02]))
    if r and len(r) >= 5:
        return {"sensitivity": SENS_NAME.get(r[2], hex(r[2])),
                "off_time": OFFTIME_NAME.get(r[4], hex(r[4]))}
    return None


def read_multi(c):
    r = xfer(c, bytes([0xD6, 0xD2]))
    if r and len(r) >= 4:
        return r[3]
    return None


def read_stc(c):
    """智能对话（Speak-to-Chat）：F6 02 -> f7 02 <type> <OnOffSettingValue>

    ⚠️ OnOffSettingValue 是 00 = ON、01 = OFF，与直觉相反。
    App 里显示「关闭」时读到的就是 01。
    """
    r = xfer(c, bytes([0xF6, 0x02]))
    if r and len(r) >= 4:
        return r[3] == 0x00
    return None


def set_stc(c, on):
    xfer(c, bytes([0xF8, 0x02, 0x01, 0x00 if on else 0x01]))
    time.sleep(0.8)
    return read_stc(c)


def read_stc_ext(c):
    """智能对话扩展参数：FA 02 -> fb 02 <灵敏度> <关注语音> <退出时间>"""
    r = xfer(c, bytes([0xFA, 0x02]))
    if r and len(r) >= 5:
        return {"sensitivity": r[2], "voice_focus": r[3], "off_time": r[4]}
    return None


def read_keys(c):
    """按键/触摸分配：F6 03 -> f7 03 <len> <preset> <固定值>"""
    r = xfer(c, bytes([0xF6, 0x03]))
    if r and len(r) >= 5:
        return r[3], r[4]
    return None, None


KEY_PRESETS = {"volume": 0x10, "playback": 0x20, "quick_ambient": 0x35, "none": 0xFF}


def enable_alert(c):
    """触摸/多点的敏感写入需要先打开固定消息告警，否则设备只回旧值。"""
    c._send(tc.T1, bytes([0x94, 0x01, 0x00]))
    for p, raw in c._read(1.0):
        if p["type"] != tc.ACK:
            c._send(tc.ACK, b"", seq=p["seq"] ^ 1)


def _answer_alerts(c, wait=2.0):
    """收告警并回「接受」。v2 的 ALERT_SET_PARAM 是 98 00 <MT> 01（XM4 是 98 01 <MT> 01）。"""
    got = []
    t_end = time.time() + wait
    while time.time() < t_end:
        for p, raw in c._read(0.4):
            if p["type"] == tc.ACK:
                continue
            c._send(tc.ACK, b"", seq=p["seq"] ^ 1)
            if p["payload"] and p["payload"][0] == 0x99:
                got.append(p["payload"])
    for pl in got:
        mt = pl[2] if len(pl) > 2 else 0x0F
        c._send(tc.T1, bytes([0x98, 0x00, mt, 0x01]))
        time.sleep(0.3)
    return got


def set_key(c, left=None, right=None, confirm=True):
    """F8 03 02 <左 preset> <右 preset>

    左右只能各给一个预设，可接受值见 KEY_PRESETS；动作列表（单击/双击/长按）
    由预设决定，不能单独改。
    某些组合（例如两耳都设成环境声控制）会禁用语音助手，设备会发告警等确认，
    此时必须应答 98 00 <MT> 01 才真正生效 —— 不答就表现为「写入被静默忽略」。
    """
    cur = read_keys(c)
    if cur[0] is None:
        return None
    l = cur[0] if left is None else left
    r = cur[1] if right is None else right
    enable_alert(c)
    xfer(c, bytes([0xF8, 0x03, 0x02, l, r]))
    time.sleep(0.5)
    if confirm:
        _answer_alerts(c)
    time.sleep(0.8)
    return read_keys(c)


def cmd_sys(c):
    for t, name in SYS_NAMES.items():
        r = xfer(c, bytes([0xF6, t]), wait=1.2)
        if r:
            print(f"  {name:14s} F6 {t:02x} -> {r.hex()}")


def cmd_status(c):
    print(f"  型号     = {read_model(c) or '?'}")
    b = read_battery(c)
    if "整体" in b:
        print(f"  电量     = {b['整体']}%  (左 {b.get('左', '?')}% / 右 {b.get('右', '?')}%)")
    if "充电盒" in b:
        print(f"  充电盒   = {b['充电盒']}%")
    print(f"  固件     = {read_fw(c) or '?'}")
    print(f"  编解码   = {read_codec(c) or '?'}")
    a = read_anc(c)
    if a:
        print(f"  降噪     = {anc_text(a)}  等级 {a['level']}  关注语音 {'开' if a['focus'] else '关'}")
    p, bands = read_eq(c)
    if p is not None:
        print(f"  均衡     = 预设 0x{p:02x}  六段 {bands}")
    print(f"  智能对话 = {'开' if read_stc(c) else '关'}")
    d = read_dsee(c)
    if d is not None:
        print(f"  DSEE     = {'自动' if d else '关闭'}")
    q = read_quality(c)
    if q is not None:
        print(f"  连接模式 = {'稳定优先' if q else '音质优先'}")
    a = read_apo(c)
    if a is not None:
        print(f"  自动断电 = {APO.get(a, hex(a))}")
    m = read_multi(c)
    if m is not None:
        print(f"  多点连接 = {'开' if m else '关'}（只读）")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return
    action = sys.argv[1]
    arg = sys.argv[2] if len(sys.argv) > 2 else None
    try:
        c = connect()
    except OSError as e:
        print(f"连接失败: {e}")
        print("提示: 取出耳机开机；通道固定 9；10049=不可达 10050=被占用")
        return
    try:
        if action == "status":
            cmd_status(c)
        elif action == "version":
            print("固件版本:", read_fw(c) or "读取失败")
            print("系列颜色:", read_series(c) or "读取失败")
            print("型号    :", read_model(c) or "读取失败")
        elif action == "stc":
            v = set_stc(c, arg != "off")
            print(f"智能对话 {arg} -> 读回 {'开' if v else '关'}")
            print("  扩展参数:", read_stc_ext(c))
        elif action == "keys":
            if arg == "show" or arg is None:
                p, t = read_keys(c)
                print(f"左=0x{p:02x} 右=0x{t:02x}" if p is not None else "读取失败")
            else:
                # keys left:playback  /  keys right:quick_ambient  /  keys both:none
                target, _, name = arg.partition(":")
                if name not in KEY_PRESETS:
                    print("用法: keys show | keys left:<名> | keys right:<名> | keys both:<名>")
                    print("可用: " + ", ".join(KEY_PRESETS))
                elif target == "left":
                    got = set_key(c, left=KEY_PRESETS[name])
                    print(f"左耳 {name} -> 左={got[0]:#04x} 右={got[1]:#04x}" if got[0] is not None else "失败")
                elif target == "right":
                    got = set_key(c, right=KEY_PRESETS[name])
                    print(f"右耳 {name} -> 左={got[0]:#04x} 右={got[1]:#04x}" if got[0] is not None else "失败")
                else:
                    got = set_key(c, KEY_PRESETS[name], KEY_PRESETS[name])
                    print(f"双耳 {name} -> 左={got[0]:#04x} 右={got[1]:#04x}" if got[0] is not None else "失败")
        elif action == "dsee":
            v = set_dsee(c, arg != "off")
            print(f"DSEE {arg} -> 读回 {'自动' if v else '关闭'}")
        elif action == "quality":
            v = set_quality(c, arg == "stable")
            print(f"连接模式 {arg} -> 读回 {'稳定优先' if v else '音质优先'}")
        elif action == "apo":
            val = 0x11 if arg == "off" else 0x10
            v = set_apo(c, val)
            print(f"自动断电 {APO.get(v, hex(v) if v is not None else '?')}")
            print("  注：LinkBuds S 只有「取下即关 / 关闭」两态，定时档被设备拒绝")
        elif action == "voice":
            v = set_voice(c, arg != "off")
            print(f"通知和语音向导 {arg} -> 回显 {'开' if v else '关'}" if v is not None else "无响应")
        elif action == "stc-ext":
            sens = sys.argv[2] if len(sys.argv) > 2 else None
            oft = sys.argv[3] if len(sys.argv) > 3 else None
            if sens and sens not in SENS:
                print("灵敏度可用: auto / high / low")
                return
            if oft and oft not in OFFTIME:
                print("退出时间可用: fast / mid / slow")
                return
            got = set_stc_ext(c, sens, oft)
            print(f"智能对话扩展 -> {got}" if got else "读取/写入失败")
        elif action == "multi":
            v = read_multi(c)
            print(f"多点连接 = {'开' if v else '关'}  (raw {v})" if v is not None else "读取失败")
            print("  注：v2 的写入被设备拒绝，只支持读取")
        elif action == "sys":
            cmd_sys(c)
        elif action == "battery":
            b = read_battery(c)
            print("整体:", b.get("整体"), " 左:", b.get("左"), " 右:", b.get("右"),
                  " 盒:", b.get("充电盒"))
        elif action == "anc":
            if arg == "off":
                a = set_off(c)
            elif arg in ("on", "nc"):
                a = set_anc(c, mode=0x00)
            elif arg == "ambient":
                a = set_anc(c, mode=0x01)
            else:
                print("用法: anc on|off|ambient")
                return
            print(f"降噪 {arg} -> {anc_text(a)}  等级 {a['level'] if a else '?'}")
        elif action == "level":
            lv = int(arg)
            a = set_anc(c, level=lv)
            print(f"环境声等级 {lv} -> 读回 {a['level'] if a else '?'}")
        elif action == "focus":
            a = set_anc(c, focus=0x01 if arg == "on" else 0x00)
            print(f"关注语音 {arg} -> 读回 {a['focus'] if a else '?'}")
        elif action == "eqbands":
            vals = [int(x) for x in sys.argv[2:]] if len(sys.argv) > 2 else []
            if len(vals) != 6:
                print("用法: eqbands <bass> <b1> <b2> <b3> <b4> <b5>   范围 -10..10")
                return
            p, b = set_eqbands(c, vals)
            print(f"EQ 自定义 {vals} -> 预设 0x{p:02x} 六段 {b}" if p is not None else "写入无读回")
        elif action == "eq":
            if arg not in EQ_PRESETS:
                print("可用: " + ", ".join(EQ_PRESETS))
                return
            xfer(c, bytes([0x58, 0x00, EQ_PRESETS[arg], 0x00]))
            time.sleep(0.6)
            p, b = read_eq(c)
            print(f"EQ {arg} -> 预设 0x{p:02x} 六段 {b}" if p is not None else "EQ 写入无读回")
        else:
            print(__doc__)
    finally:
        tc.ws2.closesocket(c.sock)
        tc.ws2.WSACleanup()


if __name__ == "__main__":
    main()
