#!/usr/bin/env python3
"""
设备探测：判断协议版本（v1 / v2），并尝试常见查询。

用法: python probe_device.py AA:BB:CC:DD:EE:02

判别依据（来自 omarchy-sony-headphones 的握手逻辑）：
  INIT (00 00) 的响应 payload 长度为 4  -> v1（WH-1000XM2/XM3/XM4…）
  长度为 8                             -> v2（WF-1000XM4、XM5、LinkBuds、CH720N…）

v1 与 v2 帧层完全相同，只是命令字节含义不同，所以能连上不代表命令对。
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tandem_client as tc


def probe(mac, channel=tc.CHANNEL):
    print(f"连接 {mac} …")
    c = tc.Client(mac, channel)
    try:
        # 1) 握手：连发三次，设备偶尔忽略第一次
        init = None
        for i in range(3):
            r = c.request(b"\x00\x00", wait=2.5)
            if r:
                init = r
                break
        if not init:
            print("设备无响应（可能不在可连接状态，或已被其他客户端占用）")
            return
        print(f"INIT 响应: {init.hex()}  （{len(init)} 字节）")
        ver = "v1" if len(init) == 4 else ("v2" if len(init) == 8 else "未知")
        print(f"=> 判定协议: {ver}")

        if ver == "v1":
            print("\n--- v1 常见查询 ---")
            for label, payload, idx in (
                ("电量", "1000", 2),
                ("能力", "0200", None),
                ("固件", "0402", None),
                ("编解码器", "1800", 2),
                ("降噪参数", "6602", None),
            ):
                r = c.request(bytes.fromhex(payload), wait=2.0)
                print(f"  {label:8s} {payload} -> {r.hex() if r else '无响应'}")

        elif ver == "v2":
            print("\n--- v2 探测（命令字节与 v1 不同，逐个试）---")
            # v2: POWER 族 0x22 GET_STATUS，type 未知，先扫前几个
            for t in range(0x00, 0x06):
                r = c.request(bytes([0x22, t]), wait=1.2)
                print(f"  POWER_GET_STATUS 22 {t:02x} -> {r.hex() if r else '无响应'}")
            # COMMON 族
            for t in (0x00, 0x01):
                r = c.request(bytes([0x12, t]), wait=1.2)
                print(f"  COMMON_GET_STATUS 12 {t:02x} -> {r.hex() if r else '无响应'}")
            # 固件版本（v1 用 04 02，v2 未定）
            for payload in ("0402", "0400", "0401"):
                r = c.request(bytes.fromhex(payload), wait=1.2)
                print(f"  固件尝试 {payload} -> {r.hex() if r else '无响应'}")
    finally:
        tc.ws2.closesocket(c.sock)
        tc.ws2.WSACleanup()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    mac = sys.argv[1]
    ch = int(sys.argv[2]) if len(sys.argv) > 2 else tc.CHANNEL
    try:
        probe(mac, ch)
    except OSError as e:
        print(f"连接失败: {e}")
        print("提示: 10049=设备不可达（耳机在充电盒里/未开机）；10050=被其他客户端占用；10060=超时")
