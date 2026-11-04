#!/usr/bin/env python3
"""
从 Android btsnoop_hci.log 提取 Sony tandem 会话（双向、按时间顺序）。

已实测确认的帧格式：
    [0x3E][dataType][seq][0x00][0x00][len_hi][len_lo][payload...][checksum][0x3C]
    checksum = sum(dataType .. payload[-1]) & 0xFF

传输：L2CAP cid 0x0047（PSM 上的 RFCOMM），DLCI 18，UIH 帧。
方向取自 btsnoop 记录 flags 的最低位（0=host→controller，1=controller→host）。

用法: python tandem_session.py <btsnoop_hci.log> [outdir]
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
START, END, TANDEM_DLCI = 0x3E, 0x3C, 18


def read_btsnoop(path):
    data = open(path, "rb").read()
    if data[:8] != b"btsnoop\x00":
        raise SystemExit("不是 btsnoop 文件")
    off, out = 16, []
    while off + 24 <= len(data):
        orig, incl, flags, drops, ts = struct.unpack(">IIIIQ", data[off:off + 24])
        off += 24
        out.append((ts, flags, data[off:off + incl]))
        off += incl
    return out


def iter_rfcomm(recs):
    """产出 (ts, direction, data)，只保留 tandem DLCI 的 UIH 数据段"""
    for ts, flags, pkt in recs:
        if not pkt or pkt[0] != 0x02 or len(pkt) < 5:
            continue
        direction = "in" if (flags & 1) else "out"
        body = pkt[1:]
        dlen = struct.unpack("<H", body[2:4])[0]
        l2 = body[4:4 + dlen]
        if len(l2) < 4:
            continue
        l2len, cid = struct.unpack("<HH", l2[0:4])
        p = l2[4:4 + l2len]
        if len(p) < 3:
            continue
        dlci = p[0] >> 2
        if dlci != TANDEM_DLCI:
            continue
        ctrl = p[1]
        if (ctrl & 0xEF) != 0xEF:        # 只要 UIH
            continue
        i = 2
        if p[i] & 1:
            ln, i = p[i] >> 1, i + 1
        else:
            if i + 1 >= len(p):
                continue
            ln, i = (p[i] >> 1) | (p[i + 1] << 7), i + 2
        yield ts, direction, p[i:i + ln]


def parse_frame(f):
    if len(f) < 9 or f[0] != START or f[-1] != END:
        return None
    dtype, seq = f[1], f[2]
    length = (f[5] << 8) | f[6]
    payload = f[7:7 + length]
    if len(payload) != length or 7 + length >= len(f):
        return None
    ck = f[7 + length]
    calc = sum(f[1:7 + length]) & 0xFF
    return {
        "type": dtype, "name": DATATYPE.get(dtype, "?"), "seq": seq,
        "length": length, "payload": payload.hex(),
        "ck_ok": ck == calc, "raw": f.hex(),
    }


def main():
    path = sys.argv[1]
    outdir = sys.argv[2] if len(sys.argv) > 2 else "tandem_out"
    os.makedirs(outdir, exist_ok=True)

    recs = read_btsnoop(path)
    bufs = {"out": bytearray(), "in": bytearray()}
    events = []                      # (ts, dir, frame)

    def drain(direction, ts):
        buf = bufs[direction]
        while True:
            if not buf:
                return
            if buf[0] != START:
                del buf[0]
                continue
            j = buf.find(END)
            if j < 0:
                return
            frame = bytes(buf[:j + 1])
            del buf[:j + 1]
            events.append((ts, direction, frame))

    for ts, direction, data in iter_rfcomm(recs):
        bufs[direction] += data
        drain(direction, ts)

    ok = bad = 0
    lines = []
    for ts, direction, frame in events:
        p = parse_frame(frame)
        if p is None:
            bad += 1
            lines.append(f"{ts}\t{direction}\tPARSE_FAIL\t{frame.hex()}")
            continue
        ok += 1
        lines.append(f"{ts}\t{direction}\t{p['name']}\tseq={p['seq']}\tlen={p['length']}\t"
                     f"ck={'OK' if p['ck_ok'] else 'BAD'}\t{p['payload']}\t{p['raw']}")

    open(os.path.join(outdir, "session.tsv"), "w", encoding="utf-8").write("\n".join(lines))
    print(f"帧总数 {len(events)}，解析成功 {ok}，失败 {bad}")
    c = collections.Counter(l.split('\t')[2] for l in lines if 'PARSE_FAIL' not in l)
    for k, v in c.most_common():
        print(f"  {v:4d}  {k}")
    if ok:
        print("校验和全部通过的帧占比: %.1f%%" % (100 * sum(1 for l in lines if 'ck=OK' in l) / ok))


if __name__ == "__main__":
    main()
