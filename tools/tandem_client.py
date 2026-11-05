#!/usr/bin/env python3
"""
Sony WH-1000XM4 协议客户端（Windows / AF_BTH RFCOMM，无第三方依赖）

已实测可用：
    CONNECT_GET_PROTOCOL_INFO / CONNECT_GET_CAPABILITY_INFO
    COMMON_GET_BATTERY_LEVEL / NCASM_GET_STATUS / NCASM_GET_PARAM
    EQEBB_GET_STATUS / OPT_GET_STATUS

帧格式:
    3E | dataType | seq | 00 | 00 | len_hi | len_lo | payload | checksum | 3C
    checksum = sum(dataType..payload 末字节) & 0xFF
    ACK 的 seq = 被确认帧 seq XOR 1（"下一个期望序号"）

用法: python tandem_client.py [MAC]
"""
import ctypes, ctypes.wintypes as wt, struct, select, sys, time

AF_BTH, BTHPROTO_RFCOMM, SOCK_STREAM = 32, 3, 1
START, END = 0x3E, 0x3C
T1, T2, ACK = 0x0C, 0x0E, 0x01
# 索尼私有服务 UUID：port=0 时由 SDP 解析通道，跨设备通用
SONY_UUID = (0x96CC203E, 0x5068, 0x46AD, (0xB3, 0x2D, 0xE3, 0x16, 0xF5, 0xE0, 0x69, 0xBA))
CHANNEL = 0                      # 0 = 用 Sony UUID 走 SDP；填数字则直连该 RFCOMM 通道

CMDS = {
    0x00: "CONNECT_GET_PROTOCOL_INFO", 0x01: "CONNECT_RET_PROTOCOL_INFO",
    0x02: "CONNECT_GET_CAPABILITY_INFO", 0x03: "CONNECT_RET_CAPABILITY_INFO",
    0x10: "COMMON_GET_BATTERY_LEVEL", 0x11: "COMMON_RET_BATTERY_LEVEL",
    0x18: "COMMON_GET_AUDIO_CODEC", 0x19: "COMMON_RET_AUDIO_CODEC",
    0x36: "UPDT_GET_PARAM", 0x37: "UPDT_RET_PARAM",
    0x52: "EQEBB_GET_STATUS", 0x53: "EQEBB_RET_STATUS",
    0x56: "EQEBB_GET_PARAM", 0x57: "EQEBB_RET_PARAM",
    0x62: "NCASM_GET_STATUS", 0x63: "NCASM_RET_STATUS",
    0x66: "NCASM_GET_PARAM", 0x67: "NCASM_RET_PARAM",
    0x82: "OPT_GET_STATUS", 0x83: "OPT_RET_STATUS",
    0x86: "OPT_GET_PARAM", 0x87: "OPT_RET_PARAM",
    0xA2: "PLAY_GET_STATUS", 0xA3: "PLAY_RET_STATUS",
}


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


ESCAPE_SENTRY = 0x3D
ESCAPE_MAP = {0x3C: 0x2C, 0x3D: 0x2D, 0x3E: 0x2E}
UNESCAPE_MAP = {0x2C: 0x3C, 0x2D: 0x3D, 0x2E: 0x3E}


def escape_body(body):
    out = bytearray()
    for b in body:
        if b in ESCAPE_MAP:
            out.append(ESCAPE_SENTRY)
            out.append(ESCAPE_MAP[b])
        else:
            out.append(b)
    return bytes(out)


def unescape_body(body):
    out = bytearray()
    i = 0
    while i < len(body):
        if body[i] == ESCAPE_SENTRY and i + 1 < len(body) and body[i + 1] in UNESCAPE_MAP:
            out.append(UNESCAPE_MAP[body[i + 1]])
            i += 2
        else:
            out.append(body[i])
            i += 1
    return bytes(out)


def build_frame(dtype, seq, payload=b""):
    """3E | ESCAPE(type, seq, size(4 BE), payload, checksum) | 3C"""
    body = bytes([dtype, seq]) + len(payload).to_bytes(4, "big") + payload
    body += bytes([sum(body) & 0xFF])
    return bytes([START]) + escape_body(body) + bytes([END])


def parse_frame(f):
    """输入含起止标记的原始帧；先反转义再校验"""
    if len(f) < 9 or f[0] != START or f[-1] != END:
        return None
    raw = unescape_body(f[1:-1])
    if len(raw) < 7:
        return None
    length = int.from_bytes(raw[2:6], "big")
    payload = raw[6:6 + length]
    if len(payload) != length or len(raw) < 6 + length + 1:
        return None
    ck = raw[6 + length]
    return {"type": raw[0], "seq": raw[1], "payload": payload,
            "ck_ok": ck == (sum(raw[:6 + length]) & 0xFF)}


class Client:
    def __init__(self, mac, channel=CHANNEL, timeout=5.0):
        self.seq = 0
        self.pending_seq = None      # 已发出、尚未被 ACK 的序号
        self.buf = b""
        self.timeout = timeout       # RFCOMM connect budget; UI probes use ~1.2s
        self.sock = self._connect(mac, channel)

    def _connect(self, mac, channel):
        ws2.WSAStartup(0x0202, ctypes.create_string_buffer(512))
        s = ws2.WSASocketW(AF_BTH, SOCK_STREAM, BTHPROTO_RFCOMM, None, 0, 0)
        nb = ctypes.c_ulong(1)
        ws2.ioctlsocket(s, 0x8004667E, ctypes.byref(nb))
        guid = GUID(*SONY_UUID) if channel == 0 else GUID(0, 0, 0, (0,) * 8)
        addr = SOCKADDR_BTH(AF_BTH, int(mac.replace(":", ""), 16), guid, channel)
        rc = ws2.connect(s, ctypes.byref(addr), ctypes.sizeof(addr))
        if rc != 0 and ws2.WSAGetLastError() != 10035:
            wsaerr = ws2.WSAGetLastError()
            if wsaerr == 10048:
                raise OSError("connect 失败, WSAError=10048（耳机正被另一个程序占用："
                              "可能是本机另一个实例，或手机上的 Sound Connect）")
            raise OSError(f"connect 失败, WSAError={wsaerr}")
        if rc != 0:
            t0 = time.time()
            ok = False
            while time.time() - t0 < self.timeout:
                _, w, x = select.select([], [s], [s], 0.25)
                if w or x:
                    ok = True
                    break
            if not ok:
                ws2.closesocket(s)
                raise OSError("connect 超时")
            eb, el = ctypes.create_string_buffer(4), ctypes.c_int(4)
            ws2.getsockopt(s, 0xFFFF, 0x1007, eb, ctypes.byref(el))
            err = struct.unpack("<i", eb.raw[:4])[0]
            if err:
                ws2.closesocket(s)
                if err == 10048:
                    raise OSError("connect 失败, SO_ERROR=10048（耳机正被另一个程序占用："
                                  "可能是本机另一个实例，或手机上的 Sound Connect）")
                raise OSError(f"connect 失败, SO_ERROR={err}")
        blk = ctypes.c_ulong(0)
        ws2.ioctlsocket(s, 0x8004667E, ctypes.byref(blk))
        print(f"[+] 已连接 {mac} (" + ("Sony UUID/SDP" if channel == 0 else f"channel={channel}") + ")")
        return s

    def _send(self, dtype, payload=b"", seq=None):
        """发送一帧。seq=None 时用的是“待确认序号”，且**不推进**——
        只有收到对应的 ACK 才推进（协议规定：未 ACK 应重发同一 seq）。"""
        s = self.seq if seq is None else seq
        f = build_frame(dtype, s, payload)
        if seq is None:
            self.pending_seq = s
        if ws2.send(self.sock, f, len(f), 0) != len(f):
            raise OSError(f"send 失败, WSAError={ws2.WSAGetLastError()}")
        return f

    def _read(self, wait=2.0, until=None):
        """Read frames for up to `wait` seconds.

        `until(frame)` lets a caller stop the moment its reply has arrived.
        Without it every read also paid the 0.2 s select timeout even when the
        answer was already decoded, which added ~200 ms to every single command.
        """
        frames = []
        t0 = time.time()
        while time.time() - t0 < wait:
            while True:
                i = self.buf.find(bytes([START]))
                if i < 0:
                    self.buf = b""
                    break
                self.buf = self.buf[i:]
                j = self.buf.find(bytes([END]), 1)
                if j < 0:
                    break
                raw, self.buf = self.buf[:j + 1], self.buf[j + 1:]
                p = parse_frame(raw)
                if p:
                    # 收到对端 ACK：只有此时才推进我方 seq
                    if (p["type"] == ACK and self.pending_seq is not None
                            and p["seq"] == (self.pending_seq ^ 1)):
                        self.seq = self.pending_seq ^ 1
                        self.pending_seq = None
                    frames.append((p, raw))
                    if until is not None and until(p):
                        return frames
            r, _, _ = select.select([self.sock], [], [], 0.2)
            if not r:
                if frames:
                    break
                continue
            chunk = ctypes.create_string_buffer(4096)
            n = ws2.recv(self.sock, chunk, 4096, 0)
            if n <= 0:
                break
            self.buf += chunk.raw[:n]
        return frames

    def request(self, payload, dtype=T1, wait=1.2, retries=1):
        """发请求，ACK 所有入站帧，返回 payload 首字节等于 (cmd|1) 的响应。

        未收到 ACK 时按协议重发同一 seq（retries 次），不推进序号。
        """
        want = payload[0] | 0x01
        sent = self._send(dtype, payload)
        print(f"  -> {sent.hex()}")
        deadline = time.time() + wait
        left = retries
        while True:
            while time.time() < deadline:
                for p, raw in self._read(
                        max(0.05, deadline - time.time()),
                        until=lambda q: bool(q["payload"]) and q["payload"][0] == want):
                    if p["type"] == ACK:
                        continue
                    ack = self._send(ACK, b"", seq=p["seq"] ^ 1)
                    print(f"     <- {raw.hex()}  [ACK {ack.hex()}]")
                    if p["payload"] and p["payload"][0] == want:
                        return p["payload"]
            if left <= 0 or self.pending_seq is None:
                return None
            left -= 1
            print(f"  ?? 未收到 ACK，重发同 seq ({sent.hex()})")
            ws2.send(self.sock, sent, len(sent), 0)
            deadline = time.time() + wait


def connect_v2(mac, channel=9, tries=5):
    """v2 设备（LinkBuds / XM5 / WF-XM4…）的完整握手。

    v2 比 v1 多两步，且设备常忽略新会话的第一条 INIT，必须重试：
      00 00 INIT -> 8 字节响应
      02 00 GET_CAPABILITY_INFO
      06 00 GET_SUPPORT_FUNCTION   ← 少这一步，后面的族一律不响应
    """
    c = Client(mac, channel)
    init = None
    for _ in range(tries):
        init = c.request(b"\x00\x00", wait=2.5)
        if init:
            break
        time.sleep(0.8)
    if not init:
        raise OSError("INIT 无响应（设备可能被占用或未唤醒）")
    c.request(b"\x02\x00", wait=2.0)
    time.sleep(0.2)
    c.request(b"\x06\x00", wait=2.0)
    time.sleep(0.2)
    c.init_reply = init
    return c


def main():
    mac = sys.argv[1] if len(sys.argv) > 1 else "88:C9:E8:91:BE:6B"
    c = Client(mac)
    try:
        plan = [
            ("协议版本", b"\x00\x00"),
            ("能力信息", b"\x02\x00"),
            ("电量", b"\x10\x00"),
            ("降噪/环境声状态", b"\x62\x02"),
            ("降噪/环境声参数", b"\x66\x02"),
            ("EQ 状态", b"\x52\x01"),
            ("优化器状态", b"\x82\x01"),
        ]
        results = {}
        for name, payload in plan:
            print(f"\n=== {name}  ({CMDS.get(payload[0], hex(payload[0]))}) ===")
            r = c.request(payload)
            results[name] = r
            if r is None:
                print("     !! 无响应")
            elif name == "电量" and len(r) >= 3:
                print(f"*** 电量 = {r[2]}% ***")
    finally:
        ws2.closesocket(c.sock)
        ws2.WSACleanup()
    print("\n=== 汇总 ===")
    for k, v in results.items():
        print(f"  {k:16s} {v.hex() if v else '无响应'}")


if __name__ == "__main__":
    main()
