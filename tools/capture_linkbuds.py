#!/usr/bin/env python3
"""录制 WF-LS900N 的 MDR 抓包，按 mos9527/SonyHeadphonesClient tests/ 的格式落盘。

每个帧存为单个 .bin 文件，内容 = 原始帧（含 3E/转义/校验/3C）。
文件名: mdr-packet-<ts>-<id:06>-<rx|tx>.type-<TYPE_STR>-<TYPE_HEX>.seq-<SEQ_HEX>.cmd-<CMD_STR>-<CMD_HEX>.bin
"""
import os, re, sys, time, json
import tandem_client as tc

V2_UUID = (0x956C7B26, 0xD49A, 0x4BA8, (0xB0, 0x3F, 0xB1, 0x7D, 0x39, 0x3C, 0xB6, 0xE2))
REPO = os.path.join(os.path.dirname(__file__), "..", "upstream", "shc")


def load_cmd_names():
    """从 ProtocolV2T1.hpp / ProtocolV2T2.hpp 里读 Command 枚举：byte -> name。"""
    out = {}
    for ns, path in (("t1", "libmdr/include/mdr/ProtocolV2T1.hpp"),
                     ("t2", "libmdr/include/mdr/ProtocolV2T2.hpp")):
        src = open(os.path.join(REPO, path), encoding="utf-8", errors="replace").read()
        # 找 enum class Command : UInt8 { ... }; 块（同一文件里第一个就是主命令枚举）
        m = re.search(r"enum class Command : UInt8\s*\{(.*?)\};", src, re.S)
        if m:
            for name, val in re.findall(r"(\w+)\s*=\s*0x([0-9A-Fa-f]+)", m.group(1)):
                out[(ns, int(val, 16))] = name
    return out


CMD_NAMES = load_cmd_names()
CMD_NAMES[("t1", 0x00)] = "NO_COMMAND"  # empty payload
CMD_NAMES[("t2", 0x00)] = "NO_COMMAND"
TYPE_NAMES = {0x01: "ACK", 0x0C: "DATA_MDR", 0x0E: "DATA_MDR_NO2"}


def cmd_str(dtype, payload):
    if dtype == tc.ACK:
        return "ACK"
    if not payload:
        return "NO_COMMAND"
    ns = "t1" if dtype == tc.T1 else "t2"
    return CMD_NAMES.get((ns, payload[0])) or "UNKNOWN"


def save_frame(out_dir, packet_id, direction, frame, timestamp_ms=None):
    p = tc.parse_frame(frame)
    if not p:
        return
    ts = int(timestamp_ms if timestamp_ms is not None else time.time() * 1000)
    type_str = TYPE_NAMES.get(p["type"], "INVALID")
    cmd = p["payload"][0] if p["payload"] else 0
    fname = (f"mdr-packet-{ts}-{packet_id:06}-{direction}."
              f"type-{type_str}-{p['type']:02x}."
              f"seq-{p['seq']:02x}."
              f"cmd-{cmd_str(p['type'], p['payload'])}-{cmd:02x}.bin")
    with open(os.path.join(out_dir, fname), "wb") as f:
        f.write(frame)


class CapturingClient(tc.Client):
    def __init__(self, mac, channel=0, out_dir=None):
        self._out_dir = out_dir
        self._t0 = None
        self._packet_id = 0
        super().__init__(mac, channel)

    def _send(self, dtype, payload=b"", seq=None):
        f = super()._send(dtype, payload, seq)
        self._packet_id += 1
        save_frame(self._out_dir, self._packet_id, "tx", f)
        return f

    def _read(self, wait=2.0):
        frames = super()._read(wait)
        for p, raw in frames:
            self._packet_id += 1
            save_frame(self._out_dir, self._packet_id, "rx", raw)
        return frames


def main():
    mac = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("SONY_MAC", "")
    out_dir = sys.argv[2] if len(sys.argv) > 2 else "../upstream/shc/tests/WF-LS900N-2.0.2"
    os.makedirs(out_dir, exist_ok=True)
    for f in os.listdir(out_dir):
        if f.endswith(".bin"):
            os.remove(os.path.join(out_dir, f))
    tc.SONY_UUID = V2_UUID
    c = CapturingClient(mac, 0, out_dir)
    plan = [
        ("init", b"\x00\x00", tc.T1),
        ("cap", b"\x02\x00", tc.T1),
        ("support t1", b"\x06\x00", tc.T1),
        ("support t2", b"\x06\x00", tc.T2),
        ("model", b"\x04\x01", tc.T1),
        ("fw", b"\x04\x02", tc.T1),
        ("series", b"\x04\x03", tc.T1),
        ("codec", b"\x12\x02", tc.T1),
        ("battery all", b"\x22\x00", tc.T1),
        ("battery lr", b"\x22\x01", tc.T1),
        ("battery case", b"\x22\x02", tc.T1),
        ("ncasm status", b"\x62\x02", tc.T1),
        ("ncasm param", b"\x66\x02", tc.T1),
        ("eq status", b"\x52\x01", tc.T1),
        ("eq param", b"\x56\x01", tc.T1),
        ("stc status", b"\xf6\x02", tc.T1),
        ("stc ext", b"\xfa\x02", tc.T1),
        ("battery t1", b"\x22\x00", tc.T1),
        ("power cap", b"\x20\x05", tc.T1),
        ("power param", b"\x26\x05", tc.T1),
        ("system status", b"\xf6\x00", tc.T1),
        ("wear status", b"\xf6\x06", tc.T1),
        ("gs status d2", b"\xd2\xd2", tc.T1),
        ("gs capability d2", b"\xd0\xd2", tc.T1),
        ("vg status on_off", b"\x42\x01\x00", tc.T2),
        ("vg status lang", b"\x42\x01\x01", tc.T2),
        ("vg cap lang", b"\x40\x01", tc.T2),
        ("vg param", b"\x46\x01", tc.T2),
        ("safe status", b"\x52\x00", tc.T2),
        ("safe param", b"\x56\x00", tc.T2),
    ]
    # 握手重试
    init = None
    for _ in range(6):
        if c.request(plan[0][1], wait=2.5, retries=0):
            break
        time.sleep(0.8)
    results = {}
    for name, payload, dtype in plan:
        r = c.request(payload, dtype=dtype, wait=2.0, retries=0)
        results[name] = r.hex(" ") if r else "(无响应)"
        time.sleep(0.2)
    print(json.dumps(results, indent=2, ensure_ascii=False))
    print(f"\n{sum(1 for _ in os.listdir(out_dir) if _.endswith('.bin'))} frames written to {out_dir}")


if __name__ == "__main__":
    main()