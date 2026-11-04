#!/usr/bin/env python3
"""轮询等待 XM4 的 tandem 通道可用，一旦连上立即跑握手。"""
import ctypes, ctypes.wintypes as wt, struct, select, time, sys

exec(open(__file__.rsplit("\\", 1)[0] + "/channel_scan.py", encoding="utf-8").read().split("def main()")[0])

T1 = 0x0C


def read_frames(s, wait=2.5):
    got = b""
    t0 = time.time()
    while time.time() - t0 < wait:
        r, _, _ = select.select([s], [], [], 0.3)
        if not r:
            continue
        b = ctypes.create_string_buffer(4096)
        m = ws2.recv(s, b, 4096, 0)
        if m <= 0:
            break
        got += b.raw[:m]
    return got


def split(raw):
    out, i = [], 0
    while True:
        i = raw.find(b"\x3e", i)
        if i < 0:
            return out
        j = raw.find(b"\x3c", i + 1)
        if j < 0:
            return out
        out.append(raw[i:j + 1])
        i = j + 1


def main():
    mac = os.environ.get("SONY_MAC", "")
    u64 = int(mac.replace(":", ""), 16)
    ws2.WSAStartup(0x0202, ctypes.create_string_buffer(512))
    deadline = time.time() + 240
    while time.time() < deadline:
        s = try_channel(u64, 9)
        if s is None:
            print(f"[{time.strftime('%H:%M:%S')}] 通道 9 不可用，继续等…", flush=True)
            time.sleep(5)
            continue
        print(f"[{time.strftime('%H:%M:%S')}] 通道 9 已连接，开始握手", flush=True)
        try:
            for name, payload in [("CONNECT_GET_PROTOCOL_INFO", b"\x00\x00"),
                                  ("CONNECT_GET_CAPABILITY_INFO", b"\x02\x00"),
                                  ("COMMON_GET_BATTERY_LEVEL", b"\x10\x00")]:
                f = frame(payload, T1, 0)
                ws2.send(s, f, len(f), 0)
                raw = read_frames(s)
                print(f"  {name}  -> {f.hex()}", flush=True)
                for fr in split(raw):
                    print(f"     <- {fr.hex()}", flush=True)
                if not raw:
                    print("     <- （无响应）", flush=True)
        finally:
            ws2.closesocket(s)
        return
    print("4 分钟内未等到通道可用", flush=True)


if __name__ == "__main__":
    main()
