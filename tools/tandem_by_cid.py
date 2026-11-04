#!/usr/bin/env python3
"""
按 L2CAP cid 分通道解码 tandem 帧（索尼会同时开多个 RFCOMM 通道）。

用法: python tandem_by_cid.py <btsnoop> [outdir]
产出: <outdir>/cid_XX.tsv  —— 每个通道一个文件，字段与 tandem_session.tsv 相同
"""
import sys, os, struct, collections

DATATYPE = {
    0x00: "DATA", 0x01: "ACK", 0x02: "DATA_MC_NO1", 0x07: "DATA_SSH",
    0x09: "DATA_ICD", 0x0A: "DATA_EV", 0x0C: "DATA_MDR(T1)", 0x0D: "DATA_COMMON",
    0x0E: "DATA_MDR_NO2(T2)", 0x10: "SHOT", 0x1C: "SHOT_MDR", 0x2C: "LARGE_DATA_MDR",
    0xFF: "UNKNOWN",
}
START, END, TANDEM_DLCI = 0x3E, 0x3C, 18

CMDS = {
    0x00: "CONNECT_GET_PROTOCOL_INFO", 0x01: "CONNECT_RET_PROTOCOL_INFO",
    0x02: "CONNECT_GET_CAPABILITY_INFO", 0x03: "CONNECT_RET_CAPABILITY_INFO",
    0x10: "COMMON_GET_BATTERY_LEVEL", 0x11: "COMMON_RET_BATTERY_LEVEL",
    0x34: "UPDT_SET_STATUS", 0x35: "UPDT_NTFY_STATUS",
    0x36: "UPDT_GET_PARAM", 0x37: "UPDT_RET_PARAM",
    0x52: "EQEBB_GET_STATUS", 0x53: "EQEBB_RET_STATUS",
    0x56: "EQEBB_GET_PARAM", 0x57: "EQEBB_RET_PARAM",
    0x58: "EQEBB_SET_PARAM", 0x59: "EQEBB_NTFY_PARAM",
    0x60: "NCASM_GET_CAPABILITY", 0x61: "NCASM_RET_CAPABILITY",
    0x62: "NCASM_GET_STATUS", 0x63: "NCASM_RET_STATUS",
    0x65: "NCASM_NTFY_STATUS", 0x66: "NCASM_GET_PARAM", 0x67: "NCASM_RET_PARAM",
    0x68: "NCASM_SET_PARAM", 0x69: "NCASM_NTFY_PARAM",
    0x82: "OPT_GET_STATUS", 0x83: "OPT_RET_STATUS",
}


def read_btsnoop(path):
    data = open(path, "rb").read()
    off, out = 16, []
    while off + 24 <= len(data):
        orig, incl, flags, drops, ts = struct.unpack(">IIIIQ", data[off:off + 24])
        off += 24
        out.append((ts, flags, data[off:off + incl]))
        off += incl
    return out


def main():
    path = sys.argv[1]
    outdir = sys.argv[2] if len(sys.argv) > 2 else "by_cid"
    os.makedirs(outdir, exist_ok=True)

    bufs = collections.defaultdict(bytearray)     # (cid, dir) -> stream
    for ts, flags, pkt in read_btsnoop(path):
        if not pkt or pkt[0] != 0x02 or len(pkt) < 5:
            continue
        d = "in" if (flags & 1) else "out"
        body = pkt[1:]
        dlen = struct.unpack("<H", body[2:4])[0]
        l2 = body[4:4 + dlen]
        if len(l2) < 4:
            continue
        l2len, cid = struct.unpack("<HH", l2[0:4])
        p = l2[4:4 + l2len]
        if len(p) < 3:
            continue
        if (p[0] >> 2) != TANDEM_DLCI:
            continue
        ctrl = p[1]
        if (ctrl & 0xEF) != 0xEF:
            continue
        i = 2
        if p[i] & 1:
            ln, i = p[i] >> 1, i + 1
        else:
            if i + 1 >= len(p):
                continue
            ln, i = (p[i] >> 1) | (p[i + 1] << 7), i + 2
        bufs[(cid, d)] += p[i:i + ln]

    summary = {}
    for (cid, d), buf in bufs.items():
        rows = []
        i = 0
        while i < len(buf):
            i = buf.find(START, i)
            if i < 0:
                break
            j = buf.find(END, i + 1)
            if j < 0:
                break
            f = buf[i:j + 1]
            i = j + 1
            if len(f) < 9:
                continue
            length = (f[5] << 8) | f[6]
            if len(f) < 7 + length + 2:
                continue
            payload = f[7:7 + length]
            cmd = payload[0] if payload else None
            rows.append("\t".join([d, f"0x{f[1]:02x}", f"seq={f[2]}",
                                   f"len={length}", payload.hex(),
                                   CMDS.get(cmd, "") if cmd is not None else ""]))
        if rows:
            fn = f"{outdir}/cid_{cid:02x}_{d}.tsv"
            open(fn, "w", encoding="utf-8").write("\n".join(rows))
            summary[(cid, d)] = (len(rows), len(buf))

    for k, (n, b) in sorted(summary.items()):
        print(f"cid 0x{k[0]:02x} {k[1]:3s}: {n:4d} 帧, {b:6d} 字节 -> {outdir}/cid_{k[0]:02x}_{k[1]}.tsv")


if __name__ == "__main__":
    main()
