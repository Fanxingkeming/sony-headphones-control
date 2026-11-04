#!/usr/bin/env python3
"""
WH-1000XM4 降噪控制（全部经手机 App 截图验证）

  降噪    68 02 11 02 02 01 00 00
  环境声  68 02 11 02 00 01 00 <level>       level 1..20
  关闭    68 02 00 02 02 01 00 00

第 3 字节 = 模式组：0x11 = 降噪/环境声，0x00 = 关闭
第 5 字节 = 参数项：0x02 = 模式开关，0x00 = 环境声等级
第 8 字节 = 值

注意：66 02 查询不可靠（部分状态下无响应、有响应时也只回显最后一次 SET），
不要用它判断当前模式。验证请用手机 App 显示。

用法:
    python nc_control.py state
    python nc_control.py nc
    python nc_control.py ambient [level]
    python nc_control.py off
"""
import os
import sys
sys.path.insert(0, __file__.rsplit("\\", 1)[0])
import tandem_client as tc

MAC = os.environ.get("SONY_MAC", "")

NC = bytes.fromhex("6802110202010000")
OFF = bytes.fromhex("6802000202010000")


def ambient(level=20):
    return bytes([0x68, 0x02, 0x11, 0x02, 0x00, 0x01, 0x00, level & 0xFF])


def main():
    action = sys.argv[1] if len(sys.argv) > 1 else "state"
    level = int(sys.argv[2]) if len(sys.argv) > 2 else 20
    c = tc.Client(MAC)
    try:
        if action == "nc":
            print("→ 降噪 ", NC.hex(), "->", (c.request(NC) or b"").hex() or "无回显")
        elif action == "ambient":
            f = ambient(level)
            print(f"→ 环境声 level={level}", f.hex(), "->", (c.request(f) or b"").hex() or "无回显")
        elif action == "off":
            print("→ 关闭 ", OFF.hex(), "->", (c.request(OFF) or b"").hex() or "无回显")
        else:
            print("电量:", (c.request(b"\x10\x00") or b"").hex() or "无")
            print("参数:", (c.request(b"\x66\x02") or b"").hex() or "（该查询在部分状态下无响应）")
    finally:
        tc.ws2.closesocket(c.sock)
        tc.ws2.WSACleanup()


if __name__ == "__main__":
    main()
