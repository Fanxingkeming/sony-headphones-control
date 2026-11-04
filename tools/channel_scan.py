#!/usr/bin/env python3
"""对 XM4 的每个可连接 RFCOMM 通道发送 CONNECT_GET_PROTOCOL_INFO，看哪个有回应。"""
import os
import ctypes, ctypes.wintypes as wt, struct, sys, select, time

AF_BTH, BTHPROTO_RFCOMM, SOCK_STREAM = 32, 3, 1
START, END = 0x3E, 0x3C


class GUID(ctypes.Structure):
    _pack_ = 1
    _fields_ = [("Data1", wt.DWORD), ("Data2", wt.WORD), ("Data3", wt.WORD),
                ("Data4", ctypes.c_ubyte * 8)]


class SOCKADDR_BTH(ctypes.Structure):
    _pack_ = 1
    _fields_ = [("addressFamily", ctypes.c_ushort), ("btAddr", ctypes.c_ulonglong),
                ("serviceClassId", GUID), ("port", ctypes.c_ulong)]


ws2 = ctypes.windll.ws2_32
ws2.WSASocketW.restype = ctypes.c_uint64
ws2.WSASocketW.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_void_p,
                           ctypes.c_uint, ctypes.c_ulong]
ws2.connect.argtypes = [ctypes.c_uint64, ctypes.c_void_p, ctypes.c_int]
ws2.connect.restype = ctypes.c_int
ws2.send.argtypes = [ctypes.c_uint64, ctypes.c_char_p, ctypes.c_int, ctypes.c_int]
ws2.send.restype = ctypes.c_int
ws2.recv.argtypes = [ctypes.c_uint64, ctypes.c_char_p, ctypes.c_int, ctypes.c_int]
ws2.recv.restype = ctypes.c_int
ws2.closesocket.argtypes = [ctypes.c_uint64]
ws2.ioctlsocket.argtypes = [ctypes.c_uint64, ctypes.c_long, ctypes.POINTER(ctypes.c_ulong)]
ws2.getsockopt.argtypes = [ctypes.c_uint64, ctypes.c_int, ctypes.c_int, ctypes.c_char_p,
                           ctypes.POINTER(ctypes.c_int)]
ws2.WSAGetLastError.restype = ctypes.c_int


def frame(payload, dtype=0x0C, seq=0):
    body = bytes([dtype, seq, 0, 0]) + len(payload).to_bytes(2, "big") + payload
    return bytes([START]) + body + bytes([sum(body) & 0xFF, END])


def try_channel(mac_u64, ch):
    s = ws2.WSASocketW(AF_BTH, SOCK_STREAM, BTHPROTO_RFCOMM, None, 0, 0)
    nb = ctypes.c_ulong(1)
    ws2.ioctlsocket(s, 0x8004667E, ctypes.byref(nb))
    a = SOCKADDR_BTH(AF_BTH, mac_u64, GUID(0, 0, 0, (0,) * 8), ch)
    rc = ws2.connect(s, ctypes.byref(a), ctypes.sizeof(a))
    if rc != 0 and ws2.WSAGetLastError() != 10035:
        ws2.closesocket(s)
        return None
    ok = False
    if rc != 0:
        t0 = time.time()
        while time.time() - t0 < 3:
            _, w, x = select.select([], [s], [s], 0.2)
            if w or x:
                ok = True
                break
        if not ok:
            ws2.closesocket(s)
            return None
    eb = ctypes.create_string_buffer(4)
    el = ctypes.c_int(4)
    ws2.getsockopt(s, 0xFFFF, 0x1007, eb, ctypes.byref(el))
    if struct.unpack("<i", eb.raw[:4])[0] != 0:
        ws2.closesocket(s)
        return None
    blk = ctypes.c_ulong(0)
    ws2.ioctlsocket(s, 0x8004667E, ctypes.byref(blk))
    return s


def main():
    mac = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("SONY_MAC", "")
    u64 = int(mac.replace(":", ""), 16)
    ws2.WSAStartup(0x0202, ctypes.create_string_buffer(512))
    probe = frame(bytes([0x00, 0x00]))
    for ch in range(1, 31):
        s = try_channel(u64, ch)
        if s is None:
            continue
        print(f"channel {ch:2d}: 已连接", end="  ", flush=True)
        n = ws2.send(s, probe, len(probe), 0)
        print(f"send={n}", end="  ", flush=True)
        got = b""
        t0 = time.time()
        while time.time() - t0 < 2.5:
            r, _, _ = select.select([s], [], [], 0.3)
            if not r:
                continue
            buf = ctypes.create_string_buffer(2048)
            m = ws2.recv(s, buf, 2048, 0)
            if m <= 0:
                break
            got += buf.raw[:m]
        print(f"recv={got.hex() if got else '（无响应）'}", flush=True)
        ws2.closesocket(s)


if __name__ == "__main__":
    main()
