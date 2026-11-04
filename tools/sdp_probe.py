#!/usr/bin/env python3
"""验证 SonyHeadphonesClient 的连接路径对 LinkBuds S 是否可用。

客户端（libmdr-bt/src/Windows/ConnectionWindows.cpp）的做法是：
    SOCKADDR_BTH{ btAddr, serviceClassId = <UUID>, port = 0 }  -> 交给 SDP 解析通道
v2 设备用 956C7B26-D49A-4BA8-B03F-B17D393CB6E2，v1 用 96CC203E-...-E069BA。
本脚本分别用这两个 UUID + 硬编码通道 9 各试一次，报告 WSA 错误码。

用法: python sdp_probe.py [MAC]
"""
import os
import sys, time
import tandem_client as tc

UUID_V1 = (0x96CC203E, 0x5068, 0x46AD, (0xB3, 0x2D, 0xE3, 0x16, 0xF5, 0xE0, 0x69, 0xBA))
UUID_V2 = (0x956C7B26, 0xD49A, 0x4BA8, (0xB0, 0x3F, 0xB1, 0x7D, 0x39, 0x3C, 0xB6, 0xE2))


def attempt(mac, uuid, label):
    tc.SONY_UUID = uuid
    t0 = time.time()
    try:
        c = tc.Client(mac, 0)
        print(f"[OK ] {label}: SDP 解析成功，用时 {time.time()-t0:.1f}s")
        return c
    except Exception as e:
        print(f"[ERR] {label}: {e}")
        return None


def attempt_channel(mac, ch):
    t0 = time.time()
    try:
        c = tc.Client(mac, ch)
        print(f"[OK ] 直连通道 {ch}，用时 {time.time()-t0:.1f}s")
        return c
    except Exception as e:
        print(f"[ERR] 直连通道 {ch}: {e}")
        return None


def main():
    mac = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("SONY_MAC", "")
    print(f"目标 {mac}\n")
    c = attempt(mac, UUID_V2, "V2 UUID + SDP（客户端的 v2 路径）")
    if c is None:
        c = attempt(mac, UUID_V1, "V1 UUID + SDP")
    if c is None:
        c = attempt_channel(mac, 9)
    if c is None:
        print("\n三种方式都没连上（设备可能关机 / 被手机占用）")
        return

    print("\n--- 握手 ---")
    init = None
    for i in range(5):
        init = c.request(b"\x00\x00", wait=2.5)
        if init:
            print(f"INIT 第 {i+1} 次成功: {init.hex(' ')}  ({len(init)} 字节 -> "
                  f"{'v2' if len(init) == 8 else 'v1'})")
            break
        time.sleep(0.8)
    if not init:
        print("INIT 无响应")
        return
    print("CAPABILITY:", (c.request(b"\x02\x00", wait=2.0) or b"").hex(" "))
    time.sleep(0.2)
    print("SUPPORT_FN:", (c.request(b"\x06\x00", wait=2.0) or b"").hex(" "))
    time.sleep(0.2)
    print("MODEL     :", (c.request(b"\x04\x01", wait=2.0) or b"").hex(" "))
    time.sleep(0.2)
    print("BATTERY   :", (c.request(b"\x22\x00", wait=2.0) or b"").hex(" "))
    c.sock.close() if hasattr(c, "sock") else None


if __name__ == "__main__":
    main()
