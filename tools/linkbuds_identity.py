#!/usr/bin/env python3
"""一次性把 LinkBuds S 的 v2 身份信息抓全：协议版本、两张支持功能表、型号/固件/系列。

用法: python linkbuds_identity.py [MAC]
"""
import os
import sys, time
import tandem_client as tc

V2_UUID = (0x956C7B26, 0xD49A, 0x4BA8, (0xB0, 0x3F, 0xB1, 0x7D, 0x39, 0x3C, 0xB6, 0xE2))


def hexs(b):
    return b.hex(" ") if b else "(无响应)"


def main():
    mac = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("SONY_MAC", "")
    tc.SONY_UUID = V2_UUID
    c = tc.Client(mac, 0)

    init = None
    for i in range(6):
        init = c.request(b"\x00\x00", wait=2.5, retries=0)
        if init:
            print(f"\n[INIT] 第 {i+1} 次: {hexs(init)}")
            break
        time.sleep(0.8)
    if not init:
        print("INIT 无响应，退出")
        return

    time.sleep(0.2)
    print(f"[CAPABILITY] {hexs(c.request(b'\x02\x00', wait=2.0, retries=0))}")
    time.sleep(0.2)
    t1 = c.request(b"\x06\x00", wait=3.0, retries=0)
    print(f"[SUPPORT T1] {hexs(t1)}")
    time.sleep(0.3)
    t2 = c.request(b"\x06\x00", dtype=tc.T2, wait=3.0, retries=0)
    print(f"[SUPPORT T2] {hexs(t2)}")
    time.sleep(0.3)
    for name, cmd in (("MODEL", b"\x04\x01"), ("FW", b"\x04\x02"), ("SERIES", b"\x04\x03")):
        print(f"[{name}] {hexs(c.request(cmd, wait=2.0, retries=0))}")
        time.sleep(0.2)


if __name__ == "__main__":
    main()
