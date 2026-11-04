#!/usr/bin/env python3
"""
v2 协议探索（LinkBuds S / WF-LS900N、WF-1000XM4、XM5、CH720N…）

v1 与 v2 帧层相同，但命令字节含义不同：
  v2 电量   POWER_GET_STATUS  22 <type>   type 00=整体 01=左右 02=充电盒
  v2 降噪   NCASM_GET_PARAM   66 <type>   type 11/12/13… 见 libmdr NcAsmInquiredType
  v2 均衡   EQEBB_GET_PARAM   56 <type>   type 00=预设 01=EBB 31=自定义

用法:
  python linkbuds_explore.py AA:BB:CC:DD:EE:02            # 全量探测
  python linkbuds_explore.py <MAC> battery                # 只看电池
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tandem_client as tc

# v2 参数类型（来自 libmdr ProtocolV2T1.hpp）
POWER_TYPES = {0x00: "整体电量", 0x01: "左右耳电量", 0x02: "充电盒电量",
               0x03: "关机", 0x04: "自动关机", 0x06: "省电模式"}
NCASM_TYPES = {0x11: "降噪开关+环境声开关", 0x12: "降噪模式切换+环境声开关",
               0x13: "降噪+环境声无缝", 0x14: "降噪模式+环境声无缝",
               0x15: "自动降噪", 0x16: "单/双耳降噪模式",
               0x21: "环境声开关", 0x22: "环境声无缝", 0x30: "降噪/环境声切换"}
EQEBB_TYPES = {0x00: "预设 EQ", 0x01: "EBB（低音）", 0x02: "预设 EQ（不可自定义）",
               0x30: "音效", 0x31: "自定义 EQ"}


def connect(mac, channel=9):
    c = tc.Client(mac, channel=channel)
    init = None
    for _ in range(3):
        r = c.request(b"\x00\x00", wait=2.5)
        if r:
            init = r
            break
    if not init:
        raise OSError("设备对 INIT 无响应")
    print(f"INIT: {init.hex()}  ({len(init)} 字节)")
    if len(init) == 4:
        print("=> v1 设备，请用 xm4_control.py")
        raise SystemExit(1)
    if len(init) != 8:
        print(f"=> 未识别的协议版本（{len(init)} 字节），继续尝试 v2 命令")
    else:
        print("=> v2 协议")
    # v2 能力表
    r = c.request(bytes.fromhex("0200"), wait=2.5)
    print("能力表 02 00 ->", r.hex() if r else "无响应")
    return c


def scan(c, cmd, types, label):
    print(f"\n--- {label}（命令 0x{cmd:02X}）---")
    found = {}
    for t, name in types.items():
        r = c.request(bytes([cmd, t]), wait=1.2)
        if r:
            found[t] = r
            print(f"  0x{t:02X} {name:14s} -> {r.hex()}")
    if not found:
        print("  全部无响应")
    return found


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return
    mac = sys.argv[1]
    what = sys.argv[2] if len(sys.argv) > 2 else "all"
    try:
        channel = int(sys.argv[3]) if len(sys.argv) > 3 else 9
        c = connect(mac, channel)
    except OSError as e:
        print(f"连接失败: {e}")
        print("提示: 10049=设备不可达（在盒里/未开机）；10050=被其他客户端占用；10060=超时")
        return
    try:
        if what in ("all", "battery"):
            scan(c, 0x22, POWER_TYPES, "POWER_GET_STATUS")
        if what in ("all", "anc"):
            scan(c, 0x66, NCASM_TYPES, "NCASM_GET_PARAM")
            r = c.request(bytes.fromhex("6201"), wait=1.5)
            print("  NCASM 状态 62 01 ->", r.hex() if r else "无响应")
        if what in ("all", "eq"):
            scan(c, 0x56, EQEBB_TYPES, "EQEBB_GET_PARAM")
        if what == "all":
            # 固件/编解码：v2 用 CONNECT_GET_DEVICE_INFO(04) 与 COMMON_GET_STATUS(12)
            for payload, label in (("04 00", "设备信息 04 00"),
                                   ("04 01", "设备信息 04 01"),
                                   ("12 02", "编解码 12 02")):
                r = c.request(bytes.fromhex(payload), wait=1.5)
                print(f"\n{label} -> {r.hex() if r else '无响应'}")
    finally:
        tc.ws2.closesocket(c.sock)
        tc.ws2.WSACleanup()


if __name__ == "__main__":
    main()
