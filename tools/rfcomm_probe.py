#!/usr/bin/env python3
"""探测 XM4 的 RFCOMM 通道：非阻塞 connect + select 超时，逐个通道试。"""
import os
import ctypes, ctypes.wintypes as wt, struct, sys, select, time

AF_BTH, BTHPROTO_RFCOMM, SOCK_STREAM = 32, 3, 1
SPP_GUID = (0x00001101, 0x0000, 0x1000, (0x80, 0x00, 0x00, 0x80, 0x5F, 0x9B, 0x34, 0xFB))


class GUID(ctypes.Structure):
    _pack_ = 1
    _fields_ = [("Data1", wt.DWORD), ("Data2", wt.WORD), ("Data3", wt.WORD),
                ("Data4", ctypes.c_ubyte * 8)]


class SOCKADDR_BTH(ctypes.Structure):
    _pack_ = 1
    _fields_ = [("addressFamily", ctypes.c_ushort),
                ("btAddr", ctypes.c_ulonglong),
                ("serviceClassId", GUID),
                ("port", ctypes.c_ulong)]


ws2 = ctypes.windll.ws2_32
ws2.WSASocketW.restype = ctypes.c_uint64
ws2.WSASocketW.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_int,
                           ctypes.c_void_p, ctypes.c_uint, ctypes.c_ulong]
ws2.connect.argtypes = [ctypes.c_uint64, ctypes.c_void_p, ctypes.c_int]
ws2.connect.restype = ctypes.c_int
ws2.ioctlsocket.argtypes = [ctypes.c_uint64, ctypes.c_long, ctypes.POINTER(ctypes.c_ulong)]
ws2.ioctlsocket.restype = ctypes.c_int
ws2.closesocket.argtypes = [ctypes.c_uint64]
ws2.WSAGetLastError.restype = ctypes.c_int
ws2.WSAGetLastError.argtypes = []

FIONBIO = 0x8004667E
WSAEWOULDBLOCK = 10035


def addr_for(mac, channel):
    raw = bytes(int(x, 16) for x in mac.split(":")) + b"\x00\x00"
    a = SOCKADDR_BTH()
    a.addressFamily = AF_BTH
    a.btAddr = int.from_bytes(raw, "little")
    a.serviceClassId = GUID(*SPP_GUID) if channel == 0 else GUID(0, 0, 0, (0,) * 8)
    a.port = channel
    return a


def probe(mac, channel, timeout=4.0):
    ws2.WSAStartup(0x0202, ctypes.create_string_buffer(512))
    s = ws2.WSASocketW(AF_BTH, SOCK_STREAM, BTHPROTO_RFCOMM, None, 0, 0)
    nonblock = ctypes.c_ulong(1)
    ws2.ioctlsocket(s, FIONBIO, ctypes.byref(nonblock))
    a = addr_for(mac, channel)
    rc = ws2.connect(s, ctypes.byref(a), ctypes.sizeof(a))
    if rc == 0:
        ws2.closesocket(s)
        return "CONNECTED"
    err = ws2.WSAGetLastError()
    if err != WSAEWOULDBLOCK:
        ws2.closesocket(s)
        return f"ERR {err}"
    t0 = time.time()
    while time.time() - t0 < timeout:
        _, w, x = select.select([], [s], [s], 0.25)
        if w or x:
            err = ws2.WSAGetLastError()
            ws2.closesocket(s)
            return "CONNECTED" if err == 0 else f"ERR {err}"
    ws2.closesocket(s)
    return "TIMEOUT"


if __name__ == "__main__":
    mac = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("SONY_MAC", "")
    for ch in [0] + list(range(1, 13)):
        r = probe(mac, ch, timeout=4.0) if ch == 0 else probe(mac, ch, timeout=3.0)
        print(f"channel {ch:2d}: {r}", flush=True)
        if r == "CONNECTED":
            break
