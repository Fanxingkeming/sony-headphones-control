#!/usr/bin/env python3
"""
写操作验证（EQEBB_SET_PARAM）。

格式（抓包确认）:
    请求  58 01 <preset> 00
    响应  59 01 <preset> 06 <band0..band5>

策略：读当前预设 → 切到另一个 → 读回确认 → 复原 → 再读回。
用法: python write_test.py [MAC]
"""
import os
import sys
sys.path.insert(0, __file__.rsplit("\\", 1)[0])
import tandem_client as tc

MAC = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("SONY_MAC", "")
GET_STATUS = b"\x52\x01"


def set_preset(p):
    return bytes([0x58, 0x01, p, 0x00])


def main():
    c = tc.Client(MAC)
    try:
        print("\n--- 1. 读当前 EQ 状态 ---")
        st = c.request(GET_STATUS)
        print("     =>", st.hex() if st else "无响应")
        if not st or len(st) < 3:
            print("!! 读不到状态，放弃")
            return
        cur = st[2]
        print(f"     当前预设 = 0x{cur:02X}")

        target = 0x01 if cur != 0x01 else 0x00
        print(f"\n--- 2. 切到预设 0x{target:02X} ---")
        r = c.request(set_preset(target), wait=3.0)
        print("     响应:", r.hex() if r else "无响应")

        st2 = c.request(GET_STATUS)
        print("\n--- 3. 读回 ---")
        print("     =>", st2.hex() if st2 else "无响应")
        ok = bool(st2 and len(st2) >= 3 and st2[2] == target)
        print("     状态确实变化:", "是" if ok else "否")

        print(f"\n--- 4. 复原到 0x{cur:02X} ---")
        r = c.request(set_preset(cur), wait=3.0)
        print("     响应:", r.hex() if r else "无响应")
        st3 = c.request(GET_STATUS)
        print("     =>", st3.hex() if st3 else "无响应")
        print("     复原成功:", "是" if st3 and len(st3) >= 3 and st3[2] == cur else "否")
    finally:
        tc.ws2.closesocket(c.sock)
        tc.ws2.WSACleanup()


if __name__ == "__main__":
    main()
