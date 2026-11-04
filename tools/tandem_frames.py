#!/usr/bin/env python3
"""
从 btsnoop 中提取 Sony tandem 帧并校验解析。

帧格式（由实测字节推出，见 recon/sony-protocol-recon.md 第 11 节）：
    0x3E | dataType | seq | 0x00 | 0x00 | 0x00 | length | payload... | checksum | 0x3C
    checksum = sum(dataType .. payload[-1]) & 0xFF

用法: python tandem_frames.py <btsnoop_hci.log> [outdir]
"""
import sys, os, struct, collections

DATATYPE = {
    0x00: "DATA", 0x01: "ACK",
    0x02: "DATA_MC_NO1", 0x07: "DATA_SSH", 0x09: "DATA_ICD", 0x0A: "DATA_EV",
    0x0C: "DATA_MDR(T1)", 0x0D: "DATA_COMMON", 0x0E: "DATA_MDR_NO2(T2)",
    0x10: "SHOT", 0x12: "SHOT_MC_NO1", 0x19: "SHOT_ICD", 0x1A: "SHOT_EV",
    0x1C: "SHOT_MDR", 0x1D: "SHOT_COMMON", 0x1E: "SHOT_MDR_NO2",
    0x27: "LARGE_DATA_SSH", 0x2C: "LARGE_DATA_MDR", 0x2D: "LARGE_DATA_COMMON",
    0xFF: "UNKNOWN",
}
START, END = 0x3E, 0x3C


def read_btsnoop(path):
    data = open(path, "rb").read()
    if data[:8] != b"btsnoop\x00":
        raise SystemExit("不是 btsnoop 文件")
    off, recs = 16, []
    while off + 24 <= len(data):
        orig, incl, flags, drops, ts = struct.unpack(">IIIIQ", data[off:off + 24])
        off += 24
        recs.append((ts, flags, data[off:off + incl]))
        off += incl
    return recs


def rfcomm_streams(recs):
    """按方向拼接 tandem 通道（cid 0x0047）上的 RFCOMM 载荷"""
    streams = collections.defaultdict(bytearray)   # direction -> bytes
    for ts, flags, pkt in recs:
        if not pkt or pkt[0] != 0x02 or len(pkt) < 5:
            continue
        body = pkt[1:]
        # HCI ACL: handle(12bit)+flags(2+2) 共 2 字节，随后 2 字节数据长度（均小端）
        dlen = struct.unpack("<H", body[2:4])[0]
        l2 = body[4:4 + dlen]
        if len(l2) < 4:
            continue
        l2len, cid = struct.unpack("<HH", l2[0:4])
        if cid != 0x0047:          # 只看 tandem 通道
            continue
        p = l2[4:4 + l2len]
        if len(p) < 3:
            continue
        ctrl = p[1]
        i = 2
        if p[i] & 1:
            ln = p[i] >> 1
            i += 1
        else:
            ln = (p[i] >> 1) | (p[i + 1] << 7)
            i += 2
        streams["out" if ctrl == 0xEF else "in"] += p[i:i + ln]
    return streams


def split_frames(buf):
    """从流里切出 3E..3C 帧"""
    frames, i = [], 0
    n = len(buf)
    while i < n:
        if buf[i] != START:
            i += 1
            continue
        j = buf.find(END, i + 1)
        if j < 0:
            break
        frames.append(bytes(buf[i:j + 1]))
        i = j + 1
    return frames


def parse_frame(f):
    """返回 dict 或 None（长度/校验不符时返回 None）"""
    if len(f) < 8 or f[0] != START or f[-1] != END:
        return None
    dtype, seq = f[1], f[2]
    prefix = f[3:6]                      # 三个保留字节
    length = f[6]
    payload = f[7:7 + length]
    if len(payload) != length:
        return None
    checksum = f[7 + length]
    calc = sum(f[1:7 + length]) & 0xFF
    return {
        "type": dtype, "type_name": DATATYPE.get(dtype, "?"),
        "seq": seq, "prefix": prefix.hex(),
        "length": length, "payload": payload.hex(),
        "checksum": checksum, "checksum_ok": checksum == calc,
    }


def main():
    path = sys.argv[1]
    outdir = sys.argv[2] if len(sys.argv) > 2 else "tandem_out"
    os.makedirs(outdir, exist_ok=True)

    recs = read_btsnoop(path)
    streams = rfcomm_streams(recs)
    print("流长度:", {k: len(v) for k, v in streams.items()})

    rows, ok, bad = [], 0, 0
    for direction in ("out", "in"):
        for f in split_frames(streams[direction]):
            p = parse_frame(f)
            if p is None:
                bad += 1
                rows.append(f"{direction}\tPARSE_FAIL\t{f.hex()}")
                continue
            ok += 1
            rows.append("\t".join([
                direction, p["type_name"], f"0x{p['type']:02x}", f"seq={p['seq']}",
                f"len={p['length']}", f"ck={'OK' if p['checksum_ok'] else 'BAD'}",
                p["payload"], f.raw.hex() if hasattr(f, "raw") else f.hex(),
            ]))

    open(os.path.join(outdir, "frames.tsv"), "w", encoding="utf-8").write("\n".join(rows))
    print(f"解析成功 {ok} 帧，失败 {bad}")
    c = collections.Counter(r.split('\t')[1] for r in rows if not r.endswith("PARSE_FAIL") and '\t' in r)
    for k, v in c.most_common():
        print(f"  {v:4d}  {k}")


if __name__ == "__main__":
    main()
