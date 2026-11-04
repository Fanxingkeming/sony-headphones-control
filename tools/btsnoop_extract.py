#!/usr/bin/env python3
"""
从 Android btsnoop_hci.log 里提取 Sony tandem 协议帧。

用法:
    python btsnoop_extract.py <btsnoop_hci.log> [outdir]

产出:
    <outdir>/acl_hex.txt        每个 ACL 包的原始十六进制
    <outdir>/rfcomm_payloads.txt RFCOMM 通道上的载荷（可能含 tandem 帧）
    <outdir>/tandem_frames.txt  按帧类型字节识别出的 tandem 帧
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


def read_records(path):
    """解析 btsnoop 容器，返回 [(ts, flags, hci_bytes)]"""
    with open(path, "rb") as f:
        data = f.read()
    if data[:8] != b"btsnoop\x00":
        raise SystemExit("不是 btsnoop 文件（magic 不匹配）")
    version, datalink = struct.unpack(">II", data[8:16])
    print(f"btsnoop version={version} datalink={datalink} size={len(data)}")
    off, recs = 16, []
    while off + 24 <= len(data):
        orig_len, incl_len, flags, drops, ts = struct.unpack(">IIIIQ", data[off:off + 24])
        off += 24
        pkt = data[off:off + incl_len]
        off += incl_len
        recs.append((ts, flags, pkt))
    return datalink, recs


def iter_acl(recs):
    """产出 ACL 数据包的 payload 部分（去掉 H4 type + handle/len 头）"""
    for ts, flags, pkt in recs:
        if not pkt:
            continue
        h4 = pkt[0]
        # H4: 0x02 ACL, 0x01 cmd, 0x04 event (部分日志不带 H4 头，靠长度判断)
        if h4 == 0x02 and len(pkt) >= 5:
            body = pkt[1:]
        elif h4 in (0x01, 0x04):
            continue
        else:
            body = pkt  # 无 H4 头
        if len(body) < 4:
            continue
        handle_len = struct.unpack("<H", body[0:2])[0]
        dlen = handle_len >> 12
        payload = body[4:4 + dlen] if dlen else body[4:]
        if payload:
            yield ts, payload


def parse_acl(payload):
    """拆 L2CAP，返回 (cid, l2cap_payload)"""
    if len(payload) < 4:
        return None, None
    l2len, cid = struct.unpack("<HH", payload[0:4])
    return cid, payload[4:4 + l2len]


def rfcomm_data(payload):
    """
    RFCOMM 帧：address(1) control(1) length(1~2) data
    UIH 帧 control & 0xEF == 0xEF。返回 info 字段（不含 FCS）。
    """
    if len(payload) < 3:
        return None
    addr, ctrl = payload[0], payload[1]
    dlci = addr >> 2
    i = 2
    if i >= len(payload):
        return None
    if (payload[i] & 1) == 0:      # 2 字节长度
        if i + 1 >= len(payload):
            return None
        length = (payload[i] >> 1) | (payload[i + 1] << 7)
        i += 2
    else:
        length = payload[i] >> 1
        i += 1
    data = payload[i:i + length]
    return dlci, ctrl, data


def main():
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    path = sys.argv[1]
    outdir = sys.argv[2] if len(sys.argv) > 2 else "btsnoop_out"
    os.makedirs(outdir, exist_ok=True)

    _, recs = read_records(path)
    print(f"records={len(recs)}")

    acl_lines, rf_lines, rf_by_dlci = [], [], collections.defaultdict(list)
    for ts, payload in iter_acl(recs):
        acl_lines.append(f"{ts} {payload.hex()}")
        cid, l2 = parse_acl(payload)
        if cid is None or cid in (0x0001, 0x0005):   # 跳过信令/LE 信令
            continue
        r = rfcomm_data(l2 or b"")
        if not r:
            continue
        dlci, ctrl, data = r
        rf_lines.append(f"ts={ts} cid=0x{cid:04x} dlci={dlci} ctrl=0x{ctrl:02x} {data.hex()}")
        rf_by_dlci[dlci].append(data)

    open(os.path.join(outdir, "acl_hex.txt"), "w", encoding="utf-8").write("\n".join(acl_lines))
    open(os.path.join(outdir, "rfcomm_payloads.txt"), "w", encoding="utf-8").write("\n".join(rf_lines))
    print(f"ACL 包 {len(acl_lines)} 个，RFCOMM 载荷 {len(rf_lines)} 个")
    print("各 DLCI 载荷数:", {k: len(v) for k, v in rf_by_dlci.items()})

    # 识别 tandem 帧：首字节是已知帧类型，且长度 >= 4
    frames = []
    for dlci, chunks in rf_by_dlci.items():
        for d in chunks:
            if len(d) < 4 or d[0] not in DATATYPE:
                continue
            frames.append(f"dlci={dlci} type=0x{d[0]:02x}({DATATYPE[d[0]]}) raw={d.hex()}")
    open(os.path.join(outdir, "tandem_frames.txt"), "w", encoding="utf-8").write("\n".join(frames))
    print(f"疑似 tandem 帧 {len(frames)} 个")
    for f in frames[:15]:
        print("  ", f)


if __name__ == "__main__":
    main()
