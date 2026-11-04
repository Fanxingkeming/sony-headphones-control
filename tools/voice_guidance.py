#!/usr/bin/env python3
"""
WH-1000XM4 语音向导开关（Table#2 命令，真机验证）

  请求  48 01 01 <val>   val: 00=关 01=开
  响应  49 01 01 <val>

用法: python voice_guidance.py on|off|state
"""
import os
import sys
sys.path.insert(0, __file__.rsplit("\\", 1)[0])
import tandem_client as tc

MAC = os.environ.get("SONY_MAC", "")


def main():
    action = sys.argv[1] if len(sys.argv) > 1 else "state"
    if action not in ("on", "off", "state"):
        print("用法: voice_guidance.py on|off|state")
        return
    c = tc.Client(MAC)
    try:
        if action == "state":
            # 无专用查询命令，读一次 48 01 01 00 的回显只能反映写入值
            print("提示：该功能没有可靠的读取命令，请用 App 查看当前状态")
            return
        val = 0x01 if action == "on" else 0x00
        payload = bytes([0x48, 0x01, 0x01, val])
        r = c.request(payload, dtype=tc.T2)
        print(f"→ 语音向导 {action}  {payload.hex()}  ->  {r.hex() if r else '无回显'}")
    finally:
        tc.ws2.closesocket(c.sock)
        tc.ws2.WSACleanup()


if __name__ == "__main__":
    main()
