#!/usr/bin/env python3
"""
WH-1000XM4 统一控制脚本（全部真机 + App 截图验证过）

用法:
    python xm4_control.py battery
    python xm4_control.py nc              降噪
    python xm4_control.py ambient [1-20]  环境声
    python xm4_control.py off             关闭降噪处理
    python xm4_control.py voice on|off    语音向导（Table#2）
    python xm4_control.py dsee auto|off   DSEE Extreme
    python xm4_control.py quality hifi|stable   蓝牙连接质量（声音质量优先 / 稳定连接优先）
    python xm4_control.py stc on|off      智能免摘（Speak-to-Chat）
    python xm4_control.py multipoint on|off   多点连接（写入后链路会断开重连）
    python xm4_control.py apo off|5min|30min|1h|3h|takenoff   自动断电
    python xm4_control.py pause on|off    取下耳机时暂停
    python xm4_control.py focus on|off    关注语音（环境声下聚焦人声）
    python xm4_control.py wind            风噪降低
    python xm4_control.py touch on|off     触摸式传感器控制面板
    python xm4_control.py version         固件版本 + 当前编解码器
    python xm4_control.py eq off|bass|vocal|...   EQ 预设
    python xm4_control.py eqbands <bass> <b1> <b2> <b3> <b4> <b5>   自定义 EQ，范围 -10..10
    python xm4_control.py status          读取全部可读状态

协议要点:
    帧  3E | 类型 | seq | 长度(4字节大端) | 载荷 | 校验和 | 3C     （载荷内 3C/3D/3E 需转义）
    表  T1=0x0C（NCASM/EQ/COMMON/AUDIO/SYSTEM）  T2=0x0E（LEA/语音向导）

参数寻址约定（本项目实测）:
    AUDIO   E6 <param>          -> E7 <param> <b> <val>
            E8 <param> <b> <val>
    SYSTEM  F6 <param>          -> F7 <param> <b> <val>
            F8 <param> <sub> <val>       (sub 实测固定 0x01)
    GENERAL D6 <param>          -> D7 <param> <b> <val>
            D8 <param> <b> <val>         (多点连接被设备拒绝，见下)
"""
import os
import sys
import time
sys.path.insert(0, __file__.rsplit("\\", 1)[0])
import tandem_client as tc

MAC = os.environ.get("SONY_MAC", "")


def _hex(r):
    return r.hex() if r else "无回显"


def cmd_battery(c):
    r = c.request(b"\x10\x00")
    if r and len(r) >= 3:
        print(f"电量: {r[2]}%   (raw {r.hex()})")
    else:
        print("读取失败")


def cmd_nc(c):
    print("降噪 ->", _hex(c.request(bytes.fromhex("6802110202010000"))))


def cmd_ambient(c, level=20):
    pl = bytes([0x68, 0x02, 0x11, 0x02, 0x00, 0x01, 0x00, level & 0xFF])
    print(f"环境声 {level} ->", _hex(c.request(pl)))


def cmd_off(c):
    print("关闭 ->", _hex(c.request(bytes.fromhex("6802000202010000"))))


def cmd_voice(c, state):
    val = 0x01 if state == "on" else 0x00
    pl = bytes([0x48, 0x01, 0x01, val])
    print(f"语音向导 {state} ->", _hex(c.request(pl, dtype=tc.T2)))


def cmd_dsee(c, state):
    val = 0x01 if state == "auto" else 0x00
    pl = bytes([0xE8, 0x02, 0x00, val])
    print(f"DSEE {state} ->", _hex(c.request(pl)))


def cmd_quality(c, mode):
    """AUDIO param 0x01: 0=声音质量优先, 1=稳定连接优先"""
    val = 0x00 if mode == "hifi" else 0x01
    pl = bytes([0xE8, 0x01, 0x00, val])
    print(f"连接质量 {mode} ->", _hex(c.request(pl)))


def cmd_stc(c, state):
    """SYSTEM param 0x05: 0=关, 1=开（智能免摘 / Speak-to-Chat）"""
    val = 0x01 if state == "on" else 0x00
    pl = bytes([0xF8, 0x05, 0x01, val])
    print(f"智能免摘 {state} ->", _hex(c.request(pl)))


def _enable_alerts(c):
    """ALERT_SET_STATUS(FIXED_MESSAGE, ENABLE) —— 不先开这个，敏感写入不会生效"""
    c._send(tc.T1, bytes.fromhex("940100"))
    for p, _ in c._read(1.2):
        if p["type"] != tc.ACK:
            c._send(tc.ACK, b"", seq=p["seq"] ^ 1)


def _write_with_alert(c, payload, wait=6.0):
    """写一帧并处理设备随后发来的 0x99 确认告警，返回收到的告警"""
    c._send(tc.T1, payload)
    alerts = []
    t_end = time.time() + wait
    while time.time() < t_end and not alerts:
        for p, _ in c._read(0.5):
            if p["type"] == tc.ACK:
                continue
            c._send(tc.ACK, b"", seq=p["seq"] ^ 1)
            pl = p["payload"]
            if pl and pl[0] == 0x99:
                alerts.append(pl)
    for pl in alerts:
        mt = pl[2] if len(pl) > 2 else 0x06
        c._send(tc.T1, bytes([0x98, 0x01, mt, 0x01]))
        for p, _ in c._read(1.0):
            if p["type"] != tc.ACK:
                c._send(tc.ACK, b"", seq=p["seq"] ^ 1)
    return alerts


def cmd_multipoint(c, state):
    """GENERAL_SETTING2 BOOLEAN：01=开，00=关。写入后链路会断开，需重连确认"""
    val = 0x01 if state == "on" else 0x00
    _enable_alerts(c)
    alerts = _write_with_alert(c, bytes([0xD8, 0xD2, 0x01, val]))
    if alerts:
        mt = alerts[0][2] if len(alerts[0]) > 2 else 0
        meaning = {0x06: "因切到多点而断开", 0x07: "因关闭多点而断开"}.get(mt, f"MT=0x{mt:02X}")
        print(f"多点连接 {state} -> 设备告警 {alerts[0].hex()}（{meaning}），已应答")
    else:
        print("未收到确认告警，写入可能被拒")

    # 设备会断开链路，重连后读回真实状态
    try:
        tc.ws2.closesocket(c.sock)
    except Exception:
        pass
    c.sock = None
    time.sleep(6)
    for _ in range(10):
        try:
            c2 = tc.Client(MAC)
            break
        except OSError:
            time.sleep(4)
    else:
        print("重连失败，请手动读状态确认")
        return
    r = c2.request(bytes.fromhex("d6d2"))
    print("重连读回:", r.hex() if r else "无响应")
    tc.ws2.closesocket(c2.sock)


CODECS = {0x00: "unknown", 0x01: "SBC", 0x02: "AAC", 0x10: "LDAC",
          0x20: "aptX", 0x21: "aptX HD"}


def _version(c):
    """固件版本：04 02 -> 05 02 <len> <ascii>"""
    r = c.request(bytes([0x04, 0x02]))
    if r and len(r) >= 4 and r[1] == 0x02:
        n = r[2]
        return r[3:3 + n].decode("ascii", "replace")
    return None


def _codec(c):
    r = c.request(bytes([0x18, 0x00]))
    if r and len(r) >= 3:
        return CODECS.get(r[2], f"0x{r[2]:02x}")
    return None


def cmd_version(c):
    v = _version(c)
    print("固件版本:", v or "读取失败")
    print("当前编解码器:", _codec(c) or "读取失败")


APO_SUBS = {0x03: "取下暂停", 0x04: "自动断电", 0x05: "智能免摘"}
# 自动断电取值：(c0, c1) -> 名称
AUTO_POWER_OFF = {
    "off": (0x11, 0x00), "5min": (0x00, 0x00), "30min": (0x01, 0x01),
    "1h": (0x02, 0x02), "3h": (0x03, 0x03), "takenoff": (0x10, 0x00),
}
AUTO_POWER_OFF_FROM = {v: k for k, v in AUTO_POWER_OFF.items()}
ASC_MODE = {0x00: "环境声", 0x01: "风噪降低", 0x02: "降噪"}


def cmd_apo(c, value):
    """自动断电：F8 04 01 <c0> <c1>"""
    if value not in AUTO_POWER_OFF:
        print("可用值: " + ", ".join(AUTO_POWER_OFF))
        return
    c0, c1 = AUTO_POWER_OFF[value]
    print(f"自动断电 {value} ->", _hex(c.request(bytes([0xF8, 0x04, 0x01, c0, c1]))))
    r = c.request(bytes([0xF6, 0x04]))
    if r and len(r) >= 5:
        print("  读回:", AUTO_POWER_OFF_FROM.get((r[3], r[4]), f"未知({r[3]:02x},{r[4]:02x})"))


def cmd_pause(c, state):
    """取下暂停：F8 03 01 <0|1>"""
    val = 0x01 if state == "on" else 0x00
    print(f"取下暂停 {state} ->", _hex(c.request(bytes([0xF8, 0x03, 0x01, val]))))
    r = c.request(bytes([0xF6, 0x03]))
    if r and len(r) >= 4:
        print("  读回:", "开" if r[3] else "关")


def cmd_focus(c, state):
    """关注语音：改写 ASC 参数里的 focus 字节，其余字段保持当前值"""
    r = c.request(bytes.fromhex("6602"))
    if not r or len(r) < 8:
        print("读取当前 ASC 参数失败")
        return
    payload = bytearray(r)
    payload[0] = 0x68          # RET -> SET
    payload[6] = 0x01 if state == "on" else 0x00
    print(f"关注语音 {state} ->", _hex(c.request(bytes(payload))))
    r2 = c.request(bytes.fromhex("6602"))
    if r2 and len(r2) >= 8:
        print(f"  读回: focus={r2[6]}  模式={ASC_MODE.get(r2[4], '?')}  等级={r2[7]}")


EQ_PRESETS = {
    "off": 0x00, "bright": 0x10, "excited": 0x11, "mellow": 0x12,
    "relaxed": 0x13, "vocal": 0x14, "treble": 0x15, "bass": 0x16,
    "speech": 0x17, "custom1": 0xA1, "custom2": 0xA2,
}


def cmd_eq(c, name):
    """EQ 预设：58 01 <preset> 00"""
    if name not in EQ_PRESETS:
        print("可用预设: " + ", ".join(EQ_PRESETS))
        return
    print(f"EQ 预设 {name} ->", _hex(c.request(bytes([0x58, 0x01, EQ_PRESETS[name], 0x00]))))


def cmd_eqbands(c, vals):
    """自定义 EQ：58 01 FF 06 + 6 个字节（低音 + 5 段，-10..10 映射到 0..20）"""
    if len(vals) != 6:
        print("需要 6 个值：低音 + 5 段，范围 -10..10")
        return
    data = [max(-10, min(10, v)) + 10 for v in vals]
    print(f"EQ 自定义 {vals} ->", _hex(c.request(bytes([0x58, 0x01, 0xFF, 0x06] + data))))
    r = c.request(bytes.fromhex("5601"))
    if r and len(r) >= 10:
        print("  读回 6 段:", [b - 10 for b in r[4:10]])


def cmd_wind(c):
    """风噪降低：ASC 模式字节 0x01"""
    r = c.request(bytes.fromhex("6602"))
    if not r or len(r) < 8:
        print("读取失败")
        return
    p = bytearray(r)
    p[0] = 0x68
    p[2] = 0x11
    p[4] = 0x01
    print("风噪降低 ->", _hex(c.request(bytes(p))))
    r2 = c.request(bytes.fromhex("6602"))
    if r2 and len(r2) >= 5:
        print("  读回模式:", ASC_MODE.get(r2[4], f"0x{r2[4]:02x}"))


def cmd_touch(c, state):
    """触摸式传感器控制面板：GENERAL_SETTING1（D1）布尔，D8 D1 01 <0|1>"""
    val = 0x01 if state == "on" else 0x00
    print(f"触摸面板 {state} ->", _hex(c.request(bytes([0xD8, 0xD1, 0x01, val]))))
    r = c.request(bytes([0xD6, 0xD1]))
    if r and len(r) >= 4:
        print("  读回:", "开" if r[3] else "关")


def cmd_status(c):
    def rd(desc, payload):
        r = c.request(bytes.fromhex(payload))
        if r and len(r) >= 4:
            print(f"  {desc:14s} = {r[-1]:3d}    (raw {r.hex()})")
        else:
            print(f"  {desc:14s} = 读取失败")

    r = c.request(b"\x10\x00")
    print(f"  电量           = {r[2] if r and len(r) >= 3 else '?'}%")
    print(f"  {'固件版本':14s} = {_version(c) or '?'}")
    print(f"  {'编解码器':14s} = {_codec(c) or '?'}")
    rd("DSEE(0关/1自动)", "e602")
    rd("连接质量(0质量/1稳定)", "e601")
    rd("智能免摘(0关/1开)", "f605")
    rd("多点连接(0关/1开)", "d6d2")
    rd("触摸面板(0关/1开)", "d6d1")
    rd("取下暂停(0关/1开)", "f603")
    r = c.request(bytes.fromhex("f604"))
    if r and len(r) >= 5:
        name = AUTO_POWER_OFF_FROM.get((r[3], r[4]), f"未知({r[3]:02x},{r[4]:02x})")
        print(f"  {'自动断电':14s} = {name}    (raw {r.hex()})")
    r = c.request(bytes.fromhex("6602"))
    if r and len(r) >= 8:
        print(f"  {'降噪模式':14s} = {ASC_MODE.get(r[4], '?')} / 关注语音={'开' if r[6] else '关'} / 等级={r[7]}    (raw {r.hex()})")



def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return
    action = sys.argv[1]
    arg = sys.argv[2] if len(sys.argv) > 2 else None
    try:
        c = tc.Client(MAC)
    except OSError as e:
        print(f"连接失败: {e}")
        print("提示: 耳机同一时间只接受一个 tandem 客户端，请在手机上关掉 Sound Connect（或关闭蓝牙）后重试。")
        return
    try:
        if action == "battery":
            cmd_battery(c)
        elif action == "nc":
            cmd_nc(c)
        elif action == "ambient":
            cmd_ambient(c, int(arg) if arg else 20)
        elif action == "off":
            cmd_off(c)
        elif action == "voice":
            cmd_voice(c, arg or "on")
        elif action == "dsee":
            cmd_dsee(c, arg or "auto")
        elif action == "quality":
            cmd_quality(c, arg or "hifi")
        elif action == "stc":
            cmd_stc(c, arg or "on")
        elif action == "multipoint":
            cmd_multipoint(c, arg or "on")
        elif action == "apo":
            cmd_apo(c, arg or "off")
        elif action == "pause":
            cmd_pause(c, arg or "on")
        elif action == "focus":
            cmd_focus(c, arg or "on")
        elif action == "wind":
            cmd_wind(c)
        elif action == "touch":
            cmd_touch(c, arg or "on")
        elif action == "version":
            cmd_version(c)
        elif action == "eq":
            cmd_eq(c, arg or "off")
        elif action == "eqbands":
            vals = [int(x) for x in sys.argv[2:]] if len(sys.argv) > 2 else []
            cmd_eqbands(c, vals)
        elif action == "status":
            cmd_status(c)
        else:
            print(__doc__)
    finally:
        if getattr(c, "sock", None):
            tc.ws2.closesocket(c.sock)
        tc.ws2.WSACleanup()


if __name__ == "__main__":
    main()
